"""
oddsfe_realtime_detail.py — 实时刷新详情页赔率数据
读取 oddsfe_realtime_schedule.csv 中的 event_id，采集详情页赔率
auth自动从active.js获取，无需手动配置
输出: oddsfe_realtime_detail.csv（追加写入，保留历史）
"""

import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

import requests
import csv
import re
import time
import random
from datetime import datetime
from bs4 import BeautifulSoup
from oddsfe_auth import get_event_auth

USER_AGENTS = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:127.0) Gecko/20100101 Firefox/127.0',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 14_5) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Safari/605.1.15',
]

MARKET_TYPES = ['1X2', 'OVER_UNDER', 'ASIAN_HANDICAP', 'BOTH_TEAMS_TO_SCORE']
LIVE_OPTIONS = [False, True]

OUTPUT_DIR = os.path.dirname(__file__)
DETAIL_DELAY = (0.3, 0.8)
RETRY_DELAY = (3, 6)


def random_ua():
    return random.choice(USER_AGENTS)


def random_delay(lo, hi):
    if hi > 0:
        time.sleep(max(0.1, random.uniform(lo, hi)))


def create_session():
    s = requests.Session()
    s.trust_env = False
    return s


def parse_event_odds(session, event_id, max_retries=2):
    """解析赛事详情页，提取多市场赔率"""
    result = {'event_id': event_id}

    for mt in MARKET_TYPES:
        for live in LIVE_OPTIONS:
            live_str = 'live' if live else 'prematch'
            key_prefix = f'{mt}_{live_str}'

            url = f'https://oddsfe.com/events/{event_id}?mt={mt}&live={live}'
            auth = get_event_auth()

            for attempt in range(max_retries):
                try:
                    headers = {
                        'User-Agent': random_ua(),
                        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                        'Referer': f'https://oddsfe.com/events/{event_id}',
                    }
                    headers.update(auth)

                    r = session.get(url, headers=headers, timeout=30)
                    if r.status_code == 200:
                        soup = BeautifulSoup(r.text, 'html.parser')
                        bk_rows = soup.find_all('div', class_='row border-bottom cast-hover')

                        bookmakers = []
                        for row in bk_rows:
                            cols = row.find_all('div', class_=re.compile(r'^col'))
                            if len(cols) < 3:
                                continue

                            # bookmaker name in col-5
                            name_col = cols[0]
                            bk_name = name_col.get_text(strip=True)

                            # odds values in remaining cols
                            odds_values = []
                            for c in cols[1:]:
                                # 只取第一个文本节点，避免混入volume数据
                                text = c.get_text(strip=True)
                                # 清理volume信息 (如 "1.95 (123)")
                                if '(' in text:
                                    text = text.split('(')[0].strip()
                                if text:
                                    odds_values.append(text)

                            if bk_name and odds_values:
                                bookmakers.append(f"{bk_name}:{':'.join(odds_values)}")

                        if bookmakers:
                            result[f'{key_prefix}_bookmakers'] = ';'.join(bookmakers)
                        else:
                            result[f'{key_prefix}_bookmakers'] = ''

                        random_delay(*DETAIL_DELAY)
                        break

                    elif r.status_code == 401:
                        print(f'  [401] Event {event_id} auth expired, refreshing...')
                        from oddsfe_auth import _refresh_auth
                        _refresh_auth()
                        auth = get_event_auth()
                        continue
                    elif r.status_code == 429:
                        print(f'  [RATE LIMIT] Event {event_id}, backing off...')
                        random_delay(*RETRY_DELAY)
                        continue
                    else:
                        result[f'{key_prefix}_bookmakers'] = ''
                        break

                except requests.exceptions.RequestException as e:
                    if attempt < max_retries - 1:
                        random_delay(*RETRY_DELAY)
                        continue
                    result[f'{key_prefix}_bookmakers'] = ''

    return result


DETAIL_FIELDS = ['event_id']
for mt in MARKET_TYPES:
    for live in LIVE_OPTIONS:
        live_str = 'live' if live else 'prematch'
        DETAIL_FIELDS.append(f'{mt}_{live_str}_bookmakers')


def run_detail(schedule_csv=None, output_csv=None, skip_existing=True):
    """从schedule CSV读取event_id，采集详情页赔率"""
    if schedule_csv is None:
        schedule_csv = os.path.join(OUTPUT_DIR, 'oddsfe_realtime_schedule.csv')
    if output_csv is None:
        output_csv = os.path.join(OUTPUT_DIR, 'oddsfe_realtime_detail.csv')

    # 读取已完成的event_id
    done_ids = set()
    if skip_existing and os.path.exists(output_csv):
        with open(output_csv, 'r', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)
            for row in reader:
                done_ids.add(row['event_id'])

    # 读取schedule中的event_id
    event_ids = []
    with open(schedule_csv, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        for row in reader:
            eid = row.get('event_id', '')
            if eid and eid not in done_ids:
                event_ids.append(eid)

    if not event_ids:
        print('No new events to fetch.')
        return 0

    print(f'Fetching {len(event_ids)} events (skip: {len(done_ids)} done)...')

    session = create_session()
    need_header = not os.path.exists(output_csv) or os.path.getsize(output_csv) == 0

    total = 0
    failed = []

    for i, eid in enumerate(event_ids):
        print(f'[{i+1}/{len(event_ids)}] Event {eid}...', end=' ')

        try:
            odds_data = parse_event_odds(session, eid)

            # 检查是否有赔率数据
            has_odds = any(v for k, v in odds_data.items() if k != 'event_id' and v)
            if has_odds:
                print('OK (has odds)')
            else:
                print('OK (no odds)')

            mode = 'w' if need_header and total == 0 else 'a'
            with open(output_csv, mode, newline='', encoding='utf-8-sig') as f:
                writer = csv.DictWriter(f, fieldnames=DETAIL_FIELDS)
                if need_header and total == 0:
                    writer.writeheader()
                writer.writerow(odds_data)
            need_header = False
            total += 1

        except Exception as e:
            print(f'FAILED: {e}')
            failed.append(eid)

        random_delay(*DETAIL_DELAY)

    print(f'\nDone! {total} events fetched, {len(failed)} failed.')
    if failed:
        print(f'Failed: {failed[:10]}...' if len(failed) > 10 else f'Failed: {failed}')
    return total


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description='oddsfe实时详情赔率采集')
    parser.add_argument('--schedule', default=None, help='schedule CSV路径')
    parser.add_argument('--output', default=None, help='输出CSV路径')
    parser.add_argument('--no-skip', action='store_true', help='不跳过已存在的event_id')
    args = parser.parse_args()
    run_detail(args.schedule, args.output, skip_existing=not args.no_skip)
