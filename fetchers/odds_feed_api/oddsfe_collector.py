"""
oddsfe_collector.py — 从 oddsfe.com 采集足球赛事数据
按日期遍历 /bind/schedule/ 获取赛事列表，再从 /events/{id} 页面解析多市场赔率
输出: CSV 文件，每行一场比赛的完整数据
"""

import requests
import json
import csv
import re
import time
import os
import random
from datetime import datetime, timedelta
from bs4 import BeautifulSoup

# ============================================================
# 反爬配置
# ============================================================
USER_AGENTS = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:127.0) Gecko/20100101 Firefox/127.0',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 14_5) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Safari/605.1.15',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36 Edg/125.0.0.0',
    'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 14_5) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36',
]

import sys
sys.path.insert(0, os.path.dirname(__file__))
from oddsfe_auth import get_schedule_auth, get_event_auth

MARKET_TYPES = ['1X2', 'OVER_UNDER', 'ASIAN_HANDICAP', 'BOTH_TEAMS_TO_SCORE']
LIVE_OPTIONS = [False, True]

# 延迟配置（秒）
SCHEDULE_DELAY = (3, 6)      # schedule请求间隔范围
DETAIL_DELAY = (2, 4)        # 详情页内子请求间隔范围
EVENT_DELAY = (4, 8)         # 不同赛事间间隔范围
DAY_DELAY = (5, 10)          # 不同天之间间隔范围
RETRY_DELAY = (10, 20)       # 失败重试间隔


def random_delay(delay_range, jitter=True):
    """随机延迟，模拟人类行为"""
    lo, hi = delay_range
    delay = random.uniform(lo, hi)
    if jitter:
        delay += random.uniform(-0.5, 0.5)
    time.sleep(max(0.5, delay))


def random_ua():
    """随机User-Agent"""
    return random.choice(USER_AGENTS)


def create_session():
    s = requests.Session()
    s.trust_env = False
    return s


# ============================================================
# 数据获取：/bind/schedule/ (JSON API)
# ============================================================
def fetch_schedule(session, date_str, max_retries=3):
    """获取某天所有赛事（JSON），带重试"""
    url = f'https://oddsfe.com/bind/schedule/football/{date_str}'

    for attempt in range(max_retries):
        try:
            headers = {
                'User-Agent': random_ua(),
                'Accept': 'application/json, text/plain, */*',
                'Origin': 'https://oddsfe.com',
                'Referer': f'https://oddsfe.com/schedule/football/{date_str}',
            }
            headers.update(get_schedule_auth())

            r = session.get(url, headers=headers, timeout=20)
            if r.status_code == 200:
                return r.json()
            elif r.status_code == 429:
                print(f'  [RATE LIMIT] Schedule {date_str}, waiting...')
                random_delay(RETRY_DELAY)
                continue
            else:
                print(f'  [WARN] Schedule {date_str}: status={r.status_code}')
                return None
        except requests.exceptions.RequestException as e:
            print(f'  [ERROR] Schedule {date_str} attempt {attempt+1}: {e}')
            if attempt < max_retries - 1:
                random_delay(RETRY_DELAY)

    return None


# ============================================================
# 数据获取：/events/{id} (HTML解析 — 多市场赔率)
# ============================================================
def parse_event_odds(session, event_id):
    """解析赛事详情页，提取多市场赔率"""
    result = {}

    for mt in MARKET_TYPES:
        for live in LIVE_OPTIONS:
            live_str = 'live' if live else 'prematch'
            key_prefix = f'{mt}_{live_str}'

            url = f'https://oddsfe.com/events/{event_id}?mt={mt}&live={live}'
            headers = {
                'User-Agent': random_ua(),
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                'Referer': f'https://oddsfe.com/events/{event_id}',
            }

            try:
                r = session.get(url, headers=headers, timeout=20)
                if r.status_code != 200:
                    if r.status_code == 429:
                        print(f'    [RATE LIMIT] Event {event_id}, backing off...')
                        random_delay(RETRY_DELAY)
                    continue

                soup = BeautifulSoup(r.text, 'html.parser')
                bk_rows = soup.find_all('div', class_='row border-bottom cast-hover')

                bookmakers = []
                for row in bk_rows:
                    cols = row.find_all('div', class_=re.compile(r'^col'))
                    if len(cols) < 3:
                        continue

                    bk_data = {}
                    name_col = cols[0]
                    bk_data['bookmaker'] = name_col.get_text(strip=True)
                    link = name_col.find('a')
                    bk_data['history_link'] = link.get('href', '') if link else ''

                    odds_values = []
                    for c in cols[1:]:
                        text = c.get_text(strip=True)
                        odds_values.append(text)
                    bk_data['odds'] = odds_values

                    bookmakers.append(bk_data)

                if bookmakers:
                    result[key_prefix] = bookmakers

                random_delay(DETAIL_DELAY)

            except requests.exceptions.RequestException as e:
                print(f'    [WARN] Event {event_id} {mt} live={live}: {e}')
                random_delay(RETRY_DELAY)
                continue

    return result


def flatten_odds_to_row(event, odds_data):
    """将schedule的event数据 + HTML赔率数据合并为一行"""

    row = {}

    # --- 基础赛事信息 (来自 /bind/schedule/) ---
    row['event_id'] = event.get('event_id', '')
    row['event_start_at'] = event.get('event_start_at', '')
    row['event_status'] = event.get('event_status', '')

    # 赛事结果
    row['event_winner'] = event.get('event_winner', '')
    row['event_score_home'] = event.get('event_score_home', '')
    row['event_score_away'] = event.get('event_score_away', '')

    # 联赛信息
    tournament = event.get('tournament', {}) or {}
    row['tournament_id'] = tournament.get('id', '')
    row['tournament_name'] = tournament.get('name', '')
    row['tournament_slug'] = tournament.get('slug', '')

    # 赛季
    season = event.get('season', {}) or {}
    row['season_id'] = season.get('id', '')
    row['season_slug'] = season.get('slug', '')

    # 地区
    category = event.get('category', {}) or {}
    row['category_id'] = category.get('id', '')
    row['category_name'] = category.get('name', '')
    row['category_slug'] = category.get('slug', '')

    # 主队
    row['team_home_id'] = event.get('team_home_id', '')
    row['team_home_name'] = event.get('team_home_name', '')

    # 客队
    row['team_away_id'] = event.get('team_away_id', '')
    row['team_away_name'] = event.get('team_away_name', '')

    # Pinnacle 赔率 (来自schedule摘要)
    row['main_out_0'] = event.get('main_out_0', '')  # 主胜
    row['main_out_1'] = event.get('main_out_1', '')  # 平局
    row['main_out_2'] = event.get('main_out_2', '')  # 客胜

    # Pinnacle 投注量
    row['main_volume_0'] = event.get('main_volume_0', '')
    row['main_volume_1'] = event.get('main_volume_1', '')
    row['main_volume_2'] = event.get('main_volume_2', '')

    # 其他schedule字段
    row['event_outcome_0'] = event.get('event_outcome_0', '')
    row['event_outcome_1'] = event.get('event_outcome_1', '')
    row['event_outcome_2'] = event.get('event_outcome_2', '')
    row['event_pin_event_id'] = event.get('event_pin_event_id', '')
    row['sum_tournament_outcome_volume'] = event.get('sum_tournament_outcome_volume', '')

    # --- 多市场赔率 (来自 /events/{id} HTML解析) ---
    # 格式: {MARKET}_{live/prematch}_odds 列
    # 每个bookmaker一行，用 | 分隔
    for mt in MARKET_TYPES:
        for live in LIVE_OPTIONS:
            live_str = 'live' if live else 'prematch'
            key = f'{mt}_{live_str}'
            bk_list = odds_data.get(key, [])

            if bk_list:
                # 合并所有bookmaker数据为一个字符串
                # 格式: bookmaker1:odds1|odds2|odds3;bookmaker2:odds1|odds2|odds3
                parts = []
                for bk in bk_list:
                    name = bk.get('bookmaker', '')
                    odds = '|'.join(bk.get('odds', []))
                    parts.append(f'{name}:{odds}')
                row[f'{key}_bookmakers'] = ';'.join(parts)
            else:
                row[f'{key}_bookmakers'] = ''

    return row


# ============================================================
# 主采集流程
# ============================================================
def collect_range(start_date, end_date, output_csv, fetch_detail=True):
    """
    按日期遍历采集
    start_date/end_date: 'YYYY-MM-DD' 格式
    fetch_detail: 是否获取详细赔率（/events/{id}页面），False则只采集schedule数据
    """
    session = create_session()

    start = datetime.strptime(start_date, '%Y-%m-%d')
    end = datetime.strptime(end_date, '%Y-%m-%d')
    total_days = (end - start).days + 1

    all_rows = []
    fieldnames = None
    total_events = 0
    failed_days = []

    for day_offset in range(total_days):
        current_date = start + timedelta(days=day_offset)
        date_str = current_date.strftime('%Y-%m-%d')

        print(f'[{day_offset+1}/{total_days}] Fetching {date_str} ...')

        # 1. 获取schedule
        schedule_data = fetch_schedule(session, date_str)
        if not schedule_data:
            failed_days.append(date_str)
            random_delay(DAY_DELAY)
            continue

        # 2. 遍历每个tournament的每个event
        day_events = 0
        for tournament in schedule_data:
            events = tournament.get('events', [])
            for event in events:
                odds_data = {}

                if fetch_detail:
                    eid = event.get('event_id')
                    if eid:
                        odds_data = parse_event_odds(session, eid)
                        random_delay(EVENT_DELAY)

                row = flatten_odds_to_row(event, odds_data)
                all_rows.append(row)

                if fieldnames is None:
                    fieldnames = list(row.keys())

                day_events += 1

        total_events += day_events
        print(f'  -> {day_events} events (total: {total_events})')

        # 3. 每天保存一次（增量写入，防止中断丢数据）
        if all_rows and fieldnames:
            save_csv(all_rows, output_csv, fieldnames)

        random_delay(DAY_DELAY)

    # 最终保存
    if all_rows and fieldnames:
        save_csv(all_rows, output_csv, fieldnames)

    print(f'\nDone! Total: {total_events} events saved to {output_csv}')
    if failed_days:
        print(f'Failed days ({len(failed_days)}): {failed_days}')
    return all_rows


def save_csv(rows, filepath, fieldnames):
    """保存CSV（覆盖写入）"""
    with open(filepath, 'w', newline='', encoding='utf-8-sig') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


# ============================================================
# 命令行入口
# ============================================================
if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description='oddsfe.com 赛事数据采集器')
    parser.add_argument('--start', default='2024-08-16', help='开始日期 YYYY-MM-DD')
    parser.add_argument('--end', default='2026-06-09', help='结束日期 YYYY-MM-DD')
    parser.add_argument('--output', default=None, help='输出CSV路径')
    parser.add_argument('--no-detail', action='store_true', help='不获取详细赔率(只用schedule数据)')

    args = parser.parse_args()

    output = args.output or os.path.join(os.path.dirname(__file__), 'oddsfe_data.csv')

    collect_range(
        start_date=args.start,
        end_date=args.end,
        output_csv=output,
        fetch_detail=not args.no_detail,
    )
