"""
oddsfe_realtime_detail_v2.py — 增强版详情采集器
相比 v1 的改进:
1. 采集 score_details（半场/加时/点球比分）
2. 采集多条盘口线的赔率（不只是第一条）
3. 采集赔率时间戳
4. 使用 /bind/event/ API 获取 score_details

输出: oddsfe_realtime_detail_v2.csv
"""

import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

import requests
import csv
import re
import time
import random
import json
from datetime import datetime
from bs4 import BeautifulSoup
from oddsfe_auth import get_event_auth, get_schedule_auth

USER_AGENTS = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:127.0) Gecko/20100101 Firefox/127.0',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 14_5) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Safari/605.1.15',
]

MARKET_TYPES = ['1X2', 'OVER_UNDER', 'ASIAN_HANDICAP', 'BOTH_TEAMS_TO_SCORE']
LIVE_OPTIONS = [False, True]

OUTPUT_DIR = os.path.dirname(__file__)
DETAIL_DELAY = (0.1, 0.3)
RETRY_DELAY = (2, 4)


def random_ua():
    return random.choice(USER_AGENTS)


def random_delay(lo, hi):
    if hi > 0:
        time.sleep(max(0.1, random.uniform(lo, hi)))


def create_session():
    s = requests.Session()
    s.trust_env = False
    return s


def fetch_event_json(session, event_id, max_retries=2):
    """从 /bind/event/ API 获取赛事详情 (score_details 等)"""
    url = f'https://oddsfe.com/bind/event/{event_id}'
    auth = get_event_auth()

    for attempt in range(max_retries):
        try:
            headers = {
                'User-Agent': random_ua(),
                'Accept': 'application/json',
                'Origin': 'https://oddsfe.com',
                'Referer': f'https://oddsfe.com/events/{event_id}',
            }
            headers.update(auth)
            r = session.get(url, headers=headers, timeout=20)
            if r.status_code == 200:
                return r.json()
            elif r.status_code == 401:
                from oddsfe_auth import _refresh_auth
                _refresh_auth()
                auth = get_event_auth()
                continue
            else:
                return None
        except requests.exceptions.RequestException:
            if attempt < max_retries - 1:
                random_delay(*RETRY_DELAY)
    return None


def parse_accordion_header(header_div, market_type):
    """
    解析 accordion header: 提取盘口线值 + 摘要赔率(PINNACLE)
    返回: {'line': '-1.5', 'summary_odds': ['4.17', '1.25'], 'market_outcome_id': '48951222'}
    """
    result = {'line': '', 'summary_odds': [], 'market_outcome_id': ''}

    # 找 col-5 里的盘口线值
    col5 = header_div.find('div', class_='col-5')
    if col5:
        # 找 fw-semibold 的 span (盘口线值)
        for span in col5.find_all('span'):
            if 'fw-semibold' in span.get('class', []):
                result['line'] = span.get_text(strip=True)
                break

    # 找 col 里的摘要赔率值 (PINNACLE赔率, 非 col-5 和 col-3)
    for col in header_div.find_all('div', class_=re.compile(r'^col\b')):
        classes = col.get('class', [])
        if 'col-5' in classes or 'col-3' in classes:
            continue
        text = col.get_text(strip=True)
        if text and re.match(r'^[\d.]', text):
            result['summary_odds'].append(text.split()[0])

    # 找 market_outcome_id (col-3 里)
    id_div = header_div.find('div', class_='col-3')
    if id_div:
        id_text = id_div.get_text(strip=True)
        if id_text.isdigit():
            result['market_outcome_id'] = id_text

    return result


def parse_bookmaker_row(row):
    """
    解析一个 bookmaker 行
    返回: {'bookmaker': 'PINNACLE', 'odds': ['4.19', '1.25'], 'volume': ['2400', '2400'], 'time': '05-30 04:48', 'is_closed': False}
    """
    result = {'bookmaker': '', 'odds': [], 'volume': [], 'time': '', 'is_closed': False}

    cols = row.find_all('div', class_=lambda c: c and c.startswith('col'))
    if len(cols) < 2:
        return result

    # bookmaker name in col-5
    name_col = cols[0]
    link = name_col.find('a')
    if link:
        result['bookmaker'] = link.get_text(strip=True)
    else:
        result['bookmaker'] = name_col.get_text(strip=True)

    # odds values in remaining cols
    for col in cols[1:]:
        # 赔率值: 第一个文本节点 (纯数字)
        main_text = ''
        volume_text = ''

        # 检查是否有 volume (<p class="fs-9">)
        vol_p = col.find('p', class_='fs-9')
        if vol_p:
            volume_text = vol_p.get_text(strip=True).replace('\xa0', '').replace(' ', '').replace('€', '')
            # 赔率值是 volume 前面的文本
            vol_p.extract()
            main_text = col.get_text(strip=True)
        else:
            main_text = col.get_text(strip=True)

        # 检查是否是时间列 (col-3)
        if col.get('class') and 'col-3' in col.get('class', []):
            time_p = col.find('p')
            if time_p:
                result['time'] = time_p.get_text(strip=True)
                # 检查 line-through (已关闭)
                if 'line-through' in time_p.get('class', []):
                    result['is_closed'] = True
            continue

        # 赔率值
        if main_text and re.match(r'^\d', main_text):
            result['odds'].append(main_text)
        if volume_text:
            # volume: "2400" 或 "2 400"
            vol_clean = volume_text.replace(' ', '')
            result['volume'].append(vol_clean)

    return result


def parse_event_odds_v2(session, event_id, max_retries=2):
    """
    解析赛事详情页 v2 — 多条盘口线 + score_details
    返回 dict
    """
    result = {'event_id': event_id}

    # 1. 先从 /bind/event/ API 获取 score_details
    event_json = fetch_event_json(session, event_id)
    if event_json:
        result['score_details'] = event_json.get('score_details', '')
        result['event_comments'] = event_json.get('comments', '')
        result['event_status_details'] = event_json.get('event_status_details', '')
        result['event_pin_event_id'] = event_json.get('event_pin_event_id', '')
    else:
        result['score_details'] = ''
        result['event_comments'] = ''
        result['event_status_details'] = ''
        result['event_pin_event_id'] = ''

    # 2. 遍历 4 markets x 2 timings
    # 优化: 先请求1X2_prematch，如果完全空则跳过剩余7个请求
    first_market_empty = None  # None=未检查, True=空, False=有数据

    for mt in MARKET_TYPES:
        for live in LIVE_OPTIONS:
            live_str = 'live' if live else 'prematch'
            key_prefix = f'{mt}_{live_str}'

            # 如果第一个市场(1X2_prematch)确认空，直接跳过剩余所有
            if first_market_empty is True and (mt != '1X2' or live != False):
                result[f'{key_prefix}_lines'] = ''
                result[f'{key_prefix}_line_count'] = '0'
                continue

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

                        # 找所有 accordion-item (每条盘口线)
                        accordion_items = soup.find_all('div', class_='accordion-item')

                        lines_data = []
                        for item in accordion_items:
                            # accordion header: 盘口线 + 摘要赔率(PINNACLE)
                            header = item.find('div', class_='accordion-row')
                            if not header:
                                continue

                            header_info = parse_accordion_header(header, mt)
                            line_value = header_info['line']
                            summary_odds = header_info['summary_odds']
                            moid = header_info['market_outcome_id']

                            # accordion body: 各bookmaker的赔率
                            body = item.find('div', class_='accordion-body')
                            if not body:
                                # 有些accordion可能没有body（只有header摘要）
                                lines_data.append({
                                    'line': line_value,
                                    'summary_odds': summary_odds,
                                    'market_outcome_id': moid,
                                    'bookmakers': [],
                                })
                                continue

                            bk_rows = body.find_all('div', class_='row border-bottom cast-hover')
                            bookmakers = []
                            for bk_row in bk_rows:
                                bk_info = parse_bookmaker_row(bk_row)
                                if bk_info['bookmaker'] and bk_info['odds']:
                                    bk_str = bk_info['bookmaker'] + ':' + ':'.join(bk_info['odds'])
                                    if bk_info['time']:
                                        bk_str += ':' + bk_info['time']
                                    if bk_info['is_closed']:
                                        bk_str += ':CLOSED'
                                    if bk_info['volume']:
                                        bk_str += ':V' + '+'.join(bk_info['volume'])
                                    bookmakers.append(bk_str)

                            lines_data.append({
                                'line': line_value,
                                'summary_odds': summary_odds,
                                'market_outcome_id': moid,
                                'bookmakers': bookmakers,
                            })

                        # 存储: 每条盘口线一个字段
                        # 格式: line:summary_odds:moid|bk1:o1:o2:time:closed;bk2:...||line2:...
                        all_lines = []
                        for ld in lines_data:
                            summary = '/'.join(ld['summary_odds'])
                            moid = ld['market_outcome_id']
                            line_str = f"{ld['line']}:{summary}:{moid}|{';'.join(ld['bookmakers'])}"
                            all_lines.append(line_str)

                        result[f'{key_prefix}_lines'] = '||'.join(all_lines)
                        result[f'{key_prefix}_line_count'] = str(len(lines_data))

                        # 标记第一个市场是否有数据
                        if mt == '1X2' and live == False:
                            first_market_empty = len(lines_data) == 0

                        random_delay(*DETAIL_DELAY)
                        break

                    elif r.status_code == 401:
                        from oddsfe_auth import _refresh_auth
                        _refresh_auth()
                        auth = get_event_auth()
                        continue
                    elif r.status_code == 429:
                        random_delay(*RETRY_DELAY)
                        continue
                    else:
                        result[f'{key_prefix}_lines'] = ''
                        result[f'{key_prefix}_line_count'] = '0'
                        # 非200状态码无法判断是否有赔率，保守处理不跳过
                        if mt == '1X2' and live == False:
                            first_market_empty = False  # 不确定，继续请求其他市场
                        break

                except requests.exceptions.RequestException:
                    if attempt < max_retries - 1:
                        random_delay(*RETRY_DELAY)
                        continue
                    result[f'{key_prefix}_lines'] = ''
                    result[f'{key_prefix}_line_count'] = '0'
                    if mt == '1X2' and live == False:
                        first_market_empty = False

    return result


# CSV 字段定义
DETAIL_V2_FIELDS = ['event_id', 'score_details', 'event_comments', 'event_status_details', 'event_pin_event_id']
for mt in MARKET_TYPES:
    for live in LIVE_OPTIONS:
        live_str = 'live' if live else 'prematch'
        DETAIL_V2_FIELDS.append(f'{mt}_{live_str}_lines')
        DETAIL_V2_FIELDS.append(f'{mt}_{live_str}_line_count')


def run_detail(event_ids=None, schedule_csv=None, output_csv=None, skip_existing=True):
    """采集详情页赔率
    可直接传入event_ids列表，或从schedule CSV读取
    """
    if event_ids is None:
        if schedule_csv is None:
            schedule_csv = os.path.join(OUTPUT_DIR, 'oddsfe_realtime_schedule.csv')
        event_ids = []
        with open(schedule_csv, 'r', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)
            for row in reader:
                eid = row.get('event_id', '')
                if eid:
                    event_ids.append(eid)

    if output_csv is None:
        output_csv = os.path.join(OUTPUT_DIR, 'oddsfe_realtime_detail_v2.csv')

    # 读取已完成的event_id
    done_ids = set()
    if skip_existing and os.path.exists(output_csv):
        with open(output_csv, 'r', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)
            for row in reader:
                done_ids.add(row['event_id'])

    # 过滤掉已完成的
    event_ids = [eid for eid in event_ids if eid not in done_ids]

    if not event_ids:
        print('No new events to fetch.')
        return 0

    print(f'Fetching {len(event_ids)} events (skip: {len(done_ids)} done)...')

    session = create_session()
    need_header = not os.path.exists(output_csv) or os.path.getsize(output_csv) == 0

    total = 0
    failed = []

    for i, eid in enumerate(event_ids):
        print(f'[{i+1}/{len(event_ids)}] Event {eid}...', end=' ', flush=True)

        try:
            odds_data = parse_event_odds_v2(session, eid)

            # 检查是否有赔率数据
            has_odds = any(v for k, v in odds_data.items()
                          if k not in ('event_id', 'score_details', 'event_comments', 'event_status_details', 'event_pin_event_id')
                          and '_lines' in k and v)
            has_score = bool(odds_data.get('score_details'))
            status = []
            if has_odds:
                status.append('odds')
            if has_score:
                status.append('score')
            print('+'.join(status) if status else 'no data')

            mode = 'w' if need_header and total == 0 else 'a'
            with open(output_csv, mode, newline='', encoding='utf-8-sig') as f:
                writer = csv.DictWriter(f, fieldnames=DETAIL_V2_FIELDS)
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
    parser = argparse.ArgumentParser(description='oddsfe增强版详情采集 (v2)')
    parser.add_argument('--schedule', default=None, help='schedule CSV路径')
    parser.add_argument('--output', default=None, help='输出CSV路径')
    parser.add_argument('--no-skip', action='store_true', help='不跳过已存在的event_id')
    parser.add_argument('--worker', type=int, default=None, help='Worker编号 (0-5)')
    parser.add_argument('--total-workers', type=int, default=6, help='总Worker数')
    parser.add_argument('--source-csv', default=None, help='从指定CSV读取event_id (默认v2)')
    parser.add_argument('--source-ids', default=None, help='从txt文件读取event_id列表')
    parser.add_argument('--year', default=None, help='只采集指定年份的event (如2026)')
    args = parser.parse_args()

    # 读取event_id列表
    all_ids = []
    if args.source_ids:
        with open(args.source_ids, 'r') as f:
            all_ids = [line.strip() for line in f if line.strip()]
    elif args.source_csv:
        with open(args.source_csv, 'r', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)
            for row in reader:
                eid = row.get('event_id', '')
                start = row.get('event_start_at', '')
                if args.year:
                    if not start.startswith(args.year):
                        continue
                if eid:
                    all_ids.append(eid)
    else:
        source_csv = os.path.join(OUTPUT_DIR, 'oddsfe_data_full_v2.csv')
        with open(source_csv, 'r', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)
            for row in reader:
                eid = row.get('event_id', '')
                start = row.get('event_start_at', '')
                if args.year:
                    if not start.startswith(args.year):
                        continue
                if eid:
                    all_ids.append(eid)

    # 按worker分配
    if args.worker is not None:
        per = len(all_ids) // args.total_workers
        start_idx = args.worker * per
        end_idx = (args.worker + 1) * per if args.worker < args.total_workers - 1 else len(all_ids)
        event_ids = all_ids[start_idx:end_idx]
        output = args.output or os.path.join(OUTPUT_DIR, f'oddsfe_detail_v2_2026_w{args.worker}.csv')
        print(f'Worker {args.worker}: {start_idx}-{end_idx} ({len(event_ids)} events) -> {os.path.basename(output)}')
        run_detail(event_ids=event_ids, output_csv=output, skip_existing=not args.no_skip)
    else:
        output = args.output or os.path.join(OUTPUT_DIR, 'oddsfe_realtime_detail_v2_2026.csv')
        run_detail(event_ids=all_ids, output_csv=output, skip_existing=not args.no_skip)
