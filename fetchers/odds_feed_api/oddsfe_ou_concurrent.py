"""
oddsfe_ou_concurrent.py — 并发O/U+1X2采集器，直写oddsfe_merged.db

设计原则:
1. 只采2个URL/event (OVER_UNDER prematch + 1X2 prematch)，不是8个
2. ThreadPoolExecutor(max_workers=8) 并发
3. 直接写oddsfe_merged.db，跳过中间CSV
4. 每worker延迟0.3-0.8s，8线程并发 → 60场 ≈ 4秒 vs 原来单线程24分钟
5. DB用WAL模式防锁

用法:
    python -m fetchers.odds_feed_api.oddsfe_ou_concurrent --past-days 1 --future-days 5
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

import sqlite3
import requests
import re
import time
import random
import logging
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from bs4 import BeautifulSoup

from fetchers.odds_feed_api.oddsfe_auth import get_schedule_auth, get_event_auth, _refresh_auth
from fetchers.odds_feed_api.oddsfe_realtime_schedule import fetch_schedule, flatten_event, create_session

logger = logging.getLogger(__name__)

USER_AGENTS = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:127.0) Gecko/20100101 Firefox/127.0',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 14_5) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Safari/605.1.15',
]

# 只采2个markets (不是4x2=8个)
OU_MARKETS = [
    ('OVER_UNDER', False),  # O/U prematch
    ('1X2', False),         # 1X2 prematch (for baseline)
]

MAX_WORKERS = 8
EVENT_DELAY = (0.3, 0.8)
RETRY_DELAY = (2, 5)
ODDSFE_DB_DEFAULT = os.path.join(os.path.dirname(__file__), 'oddsfe_merged.db')

# Thread-local storage for sessions
_thread_local = threading.local()


def _get_session():
    if not hasattr(_thread_local, 'session'):
        _thread_local.session = create_session()
    return _thread_local.session


def _random_ua():
    return random.choice(USER_AGENTS)


def _random_delay(lo, hi):
    if hi > 0:
        time.sleep(max(0.05, random.uniform(lo, hi)))


def _ensure_wal(db_path: str):
    """确保oddsfe_merged.db使用WAL模式（支持并发读写）"""
    conn = sqlite3.connect(db_path)
    conn.execute('PRAGMA journal_mode=WAL')
    conn.close()


# ==================== Schedule Fetching ====================

def get_event_ids_for_range(
    past_days: int = 2,
    future_days: int = 5,
) -> List[Dict]:
    """Fetch schedule for date range, return list of event metadata dicts."""
    session = create_session()
    today = datetime.utcnow()
    start = today - timedelta(days=past_days)
    end = today + timedelta(days=future_days)
    total_days = (end - start).days + 1

    events = []
    for day_offset in range(total_days):
        current_date = start + timedelta(days=day_offset)
        date_str = current_date.strftime('%Y-%m-%d')

        try:
            schedule_data = fetch_schedule(session, date_str)
        except Exception as e:
            logger.warning(f'Schedule fetch failed for {date_str}: {e}')
            continue

        if schedule_data is None:
            continue

        for tournament in schedule_data:
            for event in tournament.get('events', []):
                row = flatten_event(event)
                events.append(row)

        _random_delay(0.2, 0.5)

    logger.info(f'Schedule: {len(events)} events for {start.date()} to {end.date()}')
    return events


# ==================== Detail Fetching (single event, single market) ====================

def fetch_market_html(session, event_id: str, market: str, live: bool, max_retries=2) -> Optional[str]:
    """Fetch one market page for one event. Returns HTML or None."""
    url = f'https://oddsfe.com/events/{event_id}?mt={market}&live={str(live).lower()}'
    auth = get_event_auth()

    for attempt in range(max_retries):
        try:
            headers = {
                'User-Agent': _random_ua(),
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                'Referer': f'https://oddsfe.com/events/{event_id}',
            }
            headers.update(auth)
            r = session.get(url, headers=headers, timeout=30)

            if r.status_code == 200:
                return r.text
            elif r.status_code == 401:
                _refresh_auth()
                auth = get_event_auth()
                continue
            elif r.status_code == 429:
                _random_delay(*RETRY_DELAY)
                continue
            else:
                return None
        except requests.exceptions.RequestException:
            if attempt < max_retries - 1:
                _random_delay(*RETRY_DELAY)
    return None


# ==================== HTML Parsing ====================

def parse_accordion_header(header_div, market_type):
    """解析 accordion header: 盘口线值 + 摘要赔率(PINNACLE)"""
    result = {'line': '', 'summary_odds': [], 'market_outcome_id': ''}

    col5 = header_div.find('div', class_='col-5')
    if col5:
        for span in col5.find_all('span'):
            if 'fw-semibold' in span.get('class', []):
                result['line'] = span.get_text(strip=True)
                break

    for col in header_div.find_all('div', class_=re.compile(r'^col\b')):
        classes = col.get('class', [])
        if 'col-5' in classes or 'col-3' in classes:
            continue
        text = col.get_text(strip=True)
        if text and re.match(r'^[\d.]', text):
            result['summary_odds'].append(text.split()[0])

    id_div = header_div.find('div', class_='col-3')
    if id_div:
        id_text = id_div.get_text(strip=True)
        if id_text.isdigit():
            result['market_outcome_id'] = id_text

    return result


def parse_bookmaker_row(row):
    """解析一个 bookmaker 行"""
    result = {'bookmaker': '', 'odds': [], 'volume': [], 'time': '', 'is_closed': False}

    cols = row.find_all('div', class_=lambda c: c and c.startswith('col'))
    if len(cols) < 2:
        return result

    name_col = cols[0]
    link = name_col.find('a')
    if link:
        result['bookmaker'] = link.get_text(strip=True)
    else:
        result['bookmaker'] = name_col.get_text(strip=True)

    for col in cols[1:]:
        main_text = ''
        vol_p = col.find('p', class_='fs-9')
        if vol_p:
            volume_text = vol_p.get_text(strip=True).replace('\xa0', '').replace(' ', '').replace('€', '')
            vol_p.extract()
            main_text = col.get_text(strip=True)
        else:
            main_text = col.get_text(strip=True)

        if col.get('class') and 'col-3' in col.get('class', []):
            time_p = col.find('p')
            if time_p:
                result['time'] = time_p.get_text(strip=True)
                if 'line-through' in time_p.get('class', []):
                    result['is_closed'] = True
            continue

        if main_text and re.match(r'^\d', main_text):
            result['odds'].append(main_text)
        if vol_p:
            vol_clean = volume_text.replace(' ', '') if 'volume_text' in dir() else ''
            if vol_clean:
                result['volume'].append(vol_clean)

    return result


def parse_ou_market(html: str) -> Dict:
    """Parse OVER_UNDER premarket HTML, extract Pinnacle O/U lines.

    Returns: {
        'ou_lines': str,      # packed format for OVER_UNDER_prematch_lines column
        'ou_line_count': int,
        'pinnacle_best': {    # best Pinnacle line
            'line': float, 'over': float, 'under': float
        }
    }
    """
    result = {'ou_lines': '', 'ou_line_count': 0, 'pinnacle_best': None}
    if not html:
        return result

    soup = BeautifulSoup(html, 'html.parser')
    accordion_items = soup.find_all('div', class_='accordion-item')

    if not accordion_items:
        return result

    all_lines = []
    pinnacle_lines = {}  # {line_val: {'over': odds, 'under': odds}}

    for item in accordion_items:
        header = item.find('div', class_='accordion-row')
        if not header:
            continue

        header_info = parse_accordion_header(header, 'OVER_UNDER')
        line_value = header_info['line']
        summary_odds = header_info['summary_odds']
        moid = header_info['market_outcome_id']

        # Extract bookmaker data
        body = item.find('div', class_='accordion-body')
        bookmakers = []
        pinnacle_in_line = None

        if body:
            bk_rows = body.find_all('div', class_='row border-bottom cast-hover')
            for bk_row in bk_rows:
                bk_info = parse_bookmaker_row(bk_row)
                if bk_info['bookmaker'] and bk_info['odds']:
                    bk_str = bk_info['bookmaker'] + ':' + ':'.join(bk_info['odds'])
                    if bk_info['time']:
                        bk_str += ':' + bk_info['time']
                    if bk_info['is_closed']:
                        bk_str += ':CLOSED'
                    bookmakers.append(bk_str)

                    # Track Pinnacle
                    if bk_info['bookmaker'] == 'PINNACLE' and len(bk_info['odds']) >= 2:
                        try:
                            pinnacle_in_line = {
                                'over': float(bk_info['odds'][0]),
                                'under': float(bk_info['odds'][1])
                            }
                        except ValueError:
                            pass

        # Pack line data
        summary = '/'.join(summary_odds)
        line_str = f"{line_value}:{summary}:{moid}|{';'.join(bookmakers)}"
        all_lines.append(line_str)

        # If Pinnacle not in bookmaker rows, try summary_odds
        if pinnacle_in_line:
            pinnacle_lines[line_value] = pinnacle_in_line
        elif summary_odds and len(summary_odds) >= 2:
            try:
                pinnacle_lines[line_value] = {
                    'over': float(summary_odds[0]),
                    'under': float(summary_odds[1])
                }
            except ValueError:
                pass

    result['ou_lines'] = '||'.join(all_lines)
    result['ou_line_count'] = len(all_lines)

    # Find best Pinnacle line (smallest over/under odds gap)
    if pinnacle_lines:
        best_line = None
        best_gap = float('inf')
        for line_val, odds in pinnacle_lines.items():
            try:
                gap = abs(odds['over'] - odds['under'])
                if gap < best_gap:
                    best_gap = gap
                    best_line = float(line_val)
                    best_over = odds['over']
                    best_under = odds['under']
            except (ValueError, KeyError):
                continue

        if best_line is not None:
            result['pinnacle_best'] = {
                'line': best_line,
                'over': best_over,
                'under': best_under
            }

    return result


def parse_1x2_market(html: str) -> Dict:
    """Parse 1X2 prematch HTML, extract Pinnacle 1X2 odds.

    Returns: {
        'x12_lines': str,
        'x12_line_count': int,
        'pinnacle_1x2': {'home': float, 'draw': float, 'away': float}
    }
    """
    result = {'x12_lines': '', 'x12_line_count': 0, 'pinnacle_1x2': None}
    if not html:
        return result

    soup = BeautifulSoup(html, 'html.parser')
    accordion_items = soup.find_all('div', class_='accordion-item')

    if not accordion_items:
        return result

    all_lines = []

    for item in accordion_items:
        header = item.find('div', class_='accordion-row')
        if not header:
            continue

        header_info = parse_accordion_header(header, '1X2')
        line_value = header_info['line']
        summary_odds = header_info['summary_odds']
        moid = header_info['market_outcome_id']

        body = item.find('div', class_='accordion-body')
        bookmakers = []
        pinnacle_in_line = None

        if body:
            bk_rows = body.find_all('div', class_='row border-bottom cast-hover')
            for bk_row in bk_rows:
                bk_info = parse_bookmaker_row(bk_row)
                if bk_info['bookmaker'] and bk_info['odds']:
                    bk_str = bk_info['bookmaker'] + ':' + ':'.join(bk_info['odds'])
                    if bk_info['time']:
                        bk_str += ':' + bk_info['time']
                    if bk_info['is_closed']:
                        bk_str += ':CLOSED'
                    bookmakers.append(bk_str)

                    if bk_info['bookmaker'] == 'PINNACLE' and len(bk_info['odds']) >= 3:
                        try:
                            pinnacle_in_line = {
                                'home': float(bk_info['odds'][0]),
                                'draw': float(bk_info['odds'][1]),
                                'away': float(bk_info['odds'][2])
                            }
                        except ValueError:
                            pass

        summary = '/'.join(summary_odds)
        line_str = f"{line_value}:{summary}:{moid}|{';'.join(bookmakers)}"
        all_lines.append(line_str)

        # Use first Pinnacle entry found
        if pinnacle_in_line and not result['pinnacle_1x2']:
            result['pinnacle_1x2'] = pinnacle_in_line

    result['x12_lines'] = '||'.join(all_lines)
    result['x12_line_count'] = len(all_lines)

    # If no Pinnacle in bookmaker rows, try summary_odds from first line
    if not result['pinnacle_1x2'] and accordion_items:
        header = accordion_items[0].find('div', class_='accordion-row')
        if header:
            hi = parse_accordion_header(header, '1X2')
            if len(hi['summary_odds']) >= 3:
                try:
                    result['pinnacle_1x2'] = {
                        'home': float(hi['summary_odds'][0]),
                        'draw': float(hi['summary_odds'][1]),
                        'away': float(hi['summary_odds'][2])
                    }
                except ValueError:
                    pass

    return result


# ==================== Single Event Fetcher ====================

def fetch_event_detail(event_id: str) -> Optional[Dict]:
    """Fetch O/U + 1X2 prematch for one event.

    Returns: {
        'event_id': str,
        'ou_lines': str,
        'ou_line_count': int,
        'pinnacle_best': dict or None,
        'x12_lines': str,
        'x12_line_count': int,
        'pinnacle_1x2': dict or None,
    }
    """
    session = _get_session()
    result = {'event_id': event_id}

    # Fetch OVER_UNDER prematch
    ou_html = fetch_market_html(session, event_id, 'OVER_UNDER', False)
    ou_data = parse_ou_market(ou_html)
    result.update(ou_data)
    _random_delay(*EVENT_DELAY)

    # Fetch 1X2 prematch
    x12_html = fetch_market_html(session, event_id, '1X2', False)
    x12_data = parse_1x2_market(x12_html)
    result.update(x12_data)

    return result


# ==================== DB Writer ====================

# Lock for DB writes (SQLite WAL mode allows concurrent reads but serializes writes)
_db_lock = threading.Lock()


def _upsert_event_to_db(db_path: str, event_meta: Dict, detail: Dict):
    """INSERT OR REPLACE an event into oddsfe_merged.db.

    Only updates odds columns, preserves existing base data if event already exists.
    """
    event_id = event_meta.get('event_id') or detail.get('event_id')
    if not event_id:
        return

    with _db_lock:
        conn = sqlite3.connect(db_path, timeout=30)
        try:
            # Check if event exists
            existing = conn.execute(
                'SELECT event_id FROM oddsfe WHERE event_id = ?', (event_id,)
            ).fetchone()

            if existing:
                # Update only odds columns (quote column names starting with digits)
                updates = {}
                if detail.get('ou_lines'):
                    updates['OVER_UNDER_prematch_lines'] = detail['ou_lines']
                if detail.get('ou_line_count'):
                    updates['OVER_UNDER_prematch_line_count'] = str(detail['ou_line_count'])
                if detail.get('x12_lines'):
                    updates['"1X2_prematch_lines"'] = detail['x12_lines']
                if detail.get('x12_line_count'):
                    updates['"1X2_prematch_line_count"'] = str(detail['x12_line_count'])

                # Write Pinnacle best line to expanded columns
                pb = detail.get('pinnacle_best')
                if pb:
                    updates['OVER_UNDER_prematch_PINNACLE_line'] = str(pb['line'])
                    updates['OVER_UNDER_prematch_PINNACLE_over'] = str(pb['over'])
                    updates['OVER_UNDER_prematch_PINNACLE_under'] = str(pb['under'])

                p1x2 = detail.get('pinnacle_1x2')
                if p1x2:
                    updates['"1X2_prematch_PINNACLE_home"'] = str(p1x2['home'])
                    updates['"1X2_prematch_PINNACLE_draw"'] = str(p1x2['draw'])
                    updates['"1X2_prematch_PINNACLE_away"'] = str(p1x2['away'])

                if updates:
                    set_clause = ', '.join(f'{k} = ?' for k in updates)
                    conn.execute(
                        f'UPDATE oddsfe SET {set_clause} WHERE event_id = ?',
                        list(updates.values()) + [event_id]
                    )
                    conn.commit()
            else:
                # Insert new event with base data + odds
                # Use a mapping of python key -> quoted SQL column name
                col_map = {}  # {quoted_col_name: value}
                for field in ['event_id', 'event_start_at', 'event_status',
                              'tournament_id', 'tournament_name', 'tournament_slug',
                              'season_id', 'season_slug',
                              'category_id', 'category_name', 'category_slug',
                              'team_home_id', 'team_home_name',
                              'team_away_id', 'team_away_name',
                              'main_out_0', 'main_out_1', 'main_out_2',
                              'main_volume_0', 'main_volume_1', 'main_volume_2',
                              'event_outcome_0', 'event_outcome_1', 'event_outcome_2',
                              'event_pin_event_id', 'sum_tournament_outcome_volume']:
                    val = event_meta.get(field, '')
                    if val:
                        col_map[field] = str(val)

                # Add odds columns (quote 1X2 columns that start with digits)
                if detail.get('ou_lines'):
                    col_map['OVER_UNDER_prematch_lines'] = detail['ou_lines']
                if detail.get('ou_line_count'):
                    col_map['OVER_UNDER_prematch_line_count'] = str(detail['ou_line_count'])
                if detail.get('x12_lines'):
                    col_map['"1X2_prematch_lines"'] = detail['x12_lines']
                if detail.get('x12_line_count'):
                    col_map['"1X2_prematch_line_count"'] = str(detail['x12_line_count'])

                pb = detail.get('pinnacle_best')
                if pb:
                    col_map['OVER_UNDER_prematch_PINNACLE_line'] = str(pb['line'])
                    col_map['OVER_UNDER_prematch_PINNACLE_over'] = str(pb['over'])
                    col_map['OVER_UNDER_prematch_PINNACLE_under'] = str(pb['under'])

                p1x2 = detail.get('pinnacle_1x2')
                if p1x2:
                    col_map['"1X2_prematch_PINNACLE_home"'] = str(p1x2['home'])
                    col_map['"1X2_prematch_PINNACLE_draw"'] = str(p1x2['draw'])
                    col_map['"1X2_prematch_PINNACLE_away"'] = str(p1x2['away'])

                if col_map:
                    col_names = ','.join(col_map.keys())
                    placeholders = ','.join(['?'] * len(col_map))
                    conn.execute(
                        f'INSERT OR IGNORE INTO oddsfe ({col_names}) VALUES ({placeholders})',
                        list(col_map.values())
                    )
                    conn.commit()
        except Exception as e:
            logger.error(f'DB write failed for event {event_id}: {e}')
        finally:
            conn.close()


# ==================== Worker ====================

def _process_event(event_meta: Dict, db_path: str) -> Dict:
    """Worker function: fetch detail for one event and write to DB."""
    event_id = event_meta.get('event_id', '')
    try:
        detail = fetch_event_detail(event_id)
        if detail:
            _upsert_event_to_db(db_path, event_meta, detail)

            has_ou = bool(detail.get('ou_lines'))
            has_1x2 = bool(detail.get('x12_lines'))
            return {
                'event_id': event_id,
                'status': 'ok',
                'ou': has_ou,
                'x12': has_1x2,
                'pinnacle_ou': detail.get('pinnacle_best') is not None,
            }
        else:
            return {'event_id': event_id, 'status': 'no_data'}
    except Exception as e:
        logger.debug(f'Event {event_id} failed: {e}')
        return {'event_id': event_id, 'status': 'error', 'error': str(e)}


# ==================== Main Entry Point ====================

def collect_ou_concurrent(
    past_days: int = 2,
    future_days: int = 5,
    oddsfe_db_path: str = None,
    max_workers: int = MAX_WORKERS,
    date_filter: str = None,
) -> Dict:
    """Concurrent O/U+1X2 collection -> direct DB write.

    Args:
        past_days: How many days back to fetch schedule
        future_days: How many days forward to fetch schedule
        oddsfe_db_path: Path to oddsfe_merged.db
        max_workers: Number of concurrent threads
        date_filter: Optional YYYY-MM-DD to filter events by start date

    Returns:
        {'scheduled': N, 'details_fetched': N, 'ou_written': N,
         'pinnacle_ou': N, 'errors': N}
    """
    if oddsfe_db_path is None:
        oddsfe_db_path = ODDSFE_DB_DEFAULT

    if not os.path.exists(oddsfe_db_path):
        logger.error(f'oddsfe_merged.db not found at {oddsfe_db_path}')
        return {'scheduled': 0, 'errors': 1}

    # Enable WAL mode
    _ensure_wal(oddsfe_db_path)

    # Step 1: Fetch schedule
    logger.info('Fetching schedule...')
    events = get_event_ids_for_range(past_days, future_days)

    if not events:
        logger.warning('No events found in schedule')
        return {'scheduled': 0, 'errors': 0}

    # Optional date filter
    if date_filter:
        events = [e for e in events if e.get('event_start_at', '').startswith(date_filter)]
        logger.info(f'After date filter ({date_filter}): {len(events)} events')

    # Filter: skip events that already have fresh O/U data (< 6 hours old)
    # This is optional — for daily refresh we want to update existing data too
    # But for large backfills we can skip existing
    total = len(events)
    logger.info(f'Collecting O/U+1X2 for {total} events with {max_workers} workers...')

    # Step 2: Concurrent detail fetch + DB write
    results = {
        'scheduled': total,
        'details_fetched': 0,
        'ou_written': 0,
        'pinnacle_ou': 0,
        'errors': 0,
        'no_data': 0,
    }

    start_time = time.time()

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(_process_event, event, oddsfe_db_path): event
            for event in events
        }

        for i, future in enumerate(as_completed(futures), 1):
            try:
                result = future.result()
                results['details_fetched'] += 1

                if result.get('status') == 'ok':
                    if result.get('ou'):
                        results['ou_written'] += 1
                    if result.get('pinnacle_ou'):
                        results['pinnacle_ou'] += 1
                elif result.get('status') == 'no_data':
                    results['no_data'] += 1
                else:
                    results['errors'] += 1
            except Exception as e:
                results['errors'] += 1
                logger.debug(f'Future error: {e}')

            # Progress log every 50 events
            if i % 50 == 0:
                elapsed = time.time() - start_time
                rate = i / elapsed if elapsed > 0 else 0
                logger.info(f'Progress: {i}/{total} ({rate:.1f}/s) OU:{results["ou_written"]} PIN:{results["pinnacle_ou"]}')

    elapsed = time.time() - start_time
    logger.info(
        f'Done in {elapsed:.1f}s — '
        f'Scheduled:{results["scheduled"]} '
        f'Fetched:{results["details_fetched"]} '
        f'OU:{results["ou_written"]} '
        f'PinnacleOU:{results["pinnacle_ou"]} '
        f'Errors:{results["errors"]}'
    )

    return results


# ==================== CLI ====================

if __name__ == '__main__':
    import argparse

    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s [%(levelname)s] %(message)s',
        datefmt='%H:%M:%S'
    )

    parser = argparse.ArgumentParser(description='oddsfe并发O/U采集器')
    parser.add_argument('--past-days', type=int, default=2, help='采集过去N天')
    parser.add_argument('--future-days', type=int, default=5, help='采集未来N天')
    parser.add_argument('--workers', type=int, default=MAX_WORKERS, help='并发线程数')
    parser.add_argument('--db', default=None, help='oddsfe_merged.db路径')
    parser.add_argument('--date', default=None, help='只采集指定日期(YYYY-MM-DD)的赛事')
    args = parser.parse_args()

    result = collect_ou_concurrent(
        past_days=args.past_days,
        future_days=args.future_days,
        oddsfe_db_path=args.db,
        max_workers=args.workers,
        date_filter=args.date,
    )

    print(f'\nResult: {result}')
