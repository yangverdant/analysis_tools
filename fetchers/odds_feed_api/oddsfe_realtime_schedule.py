"""
oddsfe_realtime_schedule.py — 实时刷新schedule数据
每天运行一次，采集过去N天+未来N天的schedule数据
auth自动从active.js获取，无需手动配置
输出: oddsfe_realtime_schedule.csv（追加写入，保留历史）
"""

import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

import requests
import csv
import re
import time
import random
from datetime import datetime, timedelta
from bs4 import BeautifulSoup
from oddsfe_auth import get_schedule_auth, get_event_auth

USER_AGENTS = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:127.0) Gecko/20100101 Firefox/127.0',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 14_5) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Safari/605.1.15',
]

MARKET_TYPES = ['1X2', 'OVER_UNDER', 'ASIAN_HANDICAP', 'BOTH_TEAMS_TO_SCORE']
LIVE_OPTIONS = [False, True]

OUTPUT_DIR = os.path.dirname(__file__)


def random_ua():
    return random.choice(USER_AGENTS)


def create_session():
    s = requests.Session()
    s.trust_env = False
    return s


def fetch_schedule(session, date_str, max_retries=3):
    """获取某天所有赛事（JSON），auth自动获取"""
    url = f'https://oddsfe.com/bind/schedule/football/{date_str}'
    auth = get_schedule_auth()

    for attempt in range(max_retries):
        try:
            headers = {
                'User-Agent': random_ua(),
                'Accept': 'application/json, text/plain, */*',
                'Origin': 'https://oddsfe.com',
                'Referer': f'https://oddsfe.com/schedule/football/{date_str}',
            }
            headers.update(auth)
            r = session.get(url, headers=headers, timeout=20)
            if r.status_code == 200:
                return r.json()
            elif r.status_code == 401:
                print(f'  [401] Auth可能过期，重新获取...')
                from oddsfe_auth import _refresh_auth
                _refresh_auth()
                auth = get_schedule_auth()
                headers.update(auth)
                continue
            elif r.status_code == 429:
                print(f'  [RATE LIMIT] {date_str}, waiting...')
                time.sleep(random.uniform(5, 10))
                continue
            else:
                print(f'  [WARN] {date_str}: status={r.status_code}')
                return None
        except requests.exceptions.RequestException as e:
            print(f'  [ERROR] {date_str} attempt {attempt+1}: {e}')
            if attempt < max_retries - 1:
                time.sleep(3)
    return None


def flatten_event(event):
    """将schedule的event数据展开为一行"""
    row = {}
    row['event_id'] = event.get('event_id', '')
    row['event_start_at'] = event.get('event_start_at', '')
    row['event_status'] = event.get('event_status', '')
    row['event_status_details'] = event.get('event_status_details', '')
    row['event_winner'] = event.get('event_winner', '')
    row['event_score_home'] = event.get('event_score_home', '')
    row['event_score_away'] = event.get('event_score_away', '')

    tournament = event.get('tournament', {}) or {}
    row['tournament_id'] = tournament.get('id', '')
    row['tournament_name'] = tournament.get('name', '')
    row['tournament_slug'] = tournament.get('slug', '')

    season = event.get('season', {}) or {}
    row['season_id'] = season.get('id', '')
    row['season_slug'] = season.get('slug', '')

    category = event.get('category', {}) or {}
    row['category_id'] = category.get('id', '')
    row['category_name'] = category.get('name', '')
    row['category_slug'] = category.get('slug', '')

    row['team_home_id'] = event.get('team_home_id', '')
    row['team_home_name'] = event.get('team_home_name', '')
    row['team_away_id'] = event.get('team_away_id', '')
    row['team_away_name'] = event.get('team_away_name', '')

    row['main_out_0'] = event.get('main_out_0', '')
    row['main_out_1'] = event.get('main_out_1', '')
    row['main_out_2'] = event.get('main_out_2', '')

    row['main_volume_0'] = event.get('main_volume_0', '')
    row['main_volume_1'] = event.get('main_volume_1', '')
    row['main_volume_2'] = event.get('main_volume_2', '')

    row['event_outcome_0'] = event.get('event_outcome_0', '')
    row['event_outcome_1'] = event.get('event_outcome_1', '')
    row['event_outcome_2'] = event.get('event_outcome_2', '')
    row['event_pin_event_id'] = event.get('event_pin_event_id', '')
    row['sum_tournament_outcome_volume'] = event.get('sum_tournament_outcome_volume', '')

    return row


SCHEDULE_FIELDS = [
    'event_id', 'event_start_at', 'event_status', 'event_status_details', 'event_winner',
    'event_score_home', 'event_score_away', 'tournament_id', 'tournament_name',
    'tournament_slug', 'season_id', 'season_slug', 'category_id', 'category_name',
    'category_slug', 'team_home_id', 'team_home_name', 'team_away_id', 'team_away_name',
    'main_out_0', 'main_out_1', 'main_out_2', 'main_volume_0', 'main_volume_1',
    'main_volume_2', 'event_outcome_0', 'event_outcome_1', 'event_outcome_2',
    'event_pin_event_id', 'sum_tournament_outcome_volume',
]


def run_realtime(past_days=3, future_days=10):
    """采集过去past_days天 + 未来future_days天的schedule数据"""
    session = create_session()
    today = datetime.now()
    start = today - timedelta(days=past_days)
    end = today + timedelta(days=future_days)
    total_days = (end - start).days + 1

    output_csv = os.path.join(OUTPUT_DIR, 'oddsfe_realtime_schedule.csv')
    need_header = not os.path.exists(output_csv) or os.path.getsize(output_csv) == 0

    total_events = 0
    failed_days = []

    for day_offset in range(total_days):
        current_date = start + timedelta(days=day_offset)
        date_str = current_date.strftime('%Y-%m-%d')

        print(f'[{day_offset+1}/{total_days}] {date_str} ...')

        schedule_data = fetch_schedule(session, date_str)
        if schedule_data is None:
            failed_days.append(date_str)
            time.sleep(2)
            continue

        day_events = 0
        for tournament in schedule_data:
            events = tournament.get('events', [])
            for event in events:
                row = flatten_event(event)

                mode = 'w' if need_header and total_events == 0 else 'a'
                with open(output_csv, mode, newline='', encoding='utf-8-sig') as f:
                    writer = csv.DictWriter(f, fieldnames=SCHEDULE_FIELDS)
                    if need_header and total_events == 0:
                        writer.writeheader()
                    writer.writerow(row)
                need_header = False
                day_events += 1
                total_events += 1

        print(f'  -> {day_events} events (total: {total_events})')
        time.sleep(0.5)

    print(f'\nDone! {total_events} events, failed: {len(failed_days)}')
    if failed_days:
        print(f'Failed days: {failed_days}')
    return total_events


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description='oddsfe实时schedule采集')
    parser.add_argument('--past-days', type=int, default=3, help='刷新过去N天')
    parser.add_argument('--future-days', type=int, default=10, help='采集未来N天')
    args = parser.parse_args()
    run_realtime(args.past_days, args.future_days)