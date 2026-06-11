"""采集葡超和欧协联 - 按赛季日期范围"""
import json
import sqlite3
import urllib.request
import time
import sys
from pathlib import Path
from datetime import datetime

sys.stdout.reconfigure(encoding='utf-8')

DB_PATH = Path('d:/football_tools/data/unified_football.db')
API_KEY = 'bf82d62ee5412d32a95362699389583fdbefa113f4efb371b87b585f12d64443'
API_BASE = 'https://apiv3.apifootball.com'

# 目标联赛（按赛季日期范围，不用年份）
TARGETS = [
    {
        'league_id': 266,
        'league_std': 'primeira_liga',
        'league_en': 'Primeira Liga',
        'league_cn': '葡超',
        'seasons': [
            ('2024-25', '2024-08-01', '2025-06-30'),
            ('2023-24', '2023-08-01', '2024-06-30'),
        ]
    },
    {
        'league_id': 683,
        'league_std': 'conference_league',
        'league_en': 'UEFA Europa Conference League',
        'league_cn': '欧协联',
        'seasons': [
            ('2024-25', '2024-07-01', '2025-06-30'),
            ('2023-24', '2023-07-01', '2024-06-30'),
        ]
    },
    {
        'league_id': 18,
        'league_std': 'copa_libertadores',
        'league_en': 'Copa Libertadores',
        'league_cn': '解放者杯',
        'seasons': [
            ('2024-25', '2024-01-01', '2025-06-30'),
            ('2023-24', '2023-01-01', '2024-06-30'),
        ]
    },
]


def fetch_api(url):
    try:
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=30) as response:
            return json.loads(response.read().decode('utf-8'))
    except:
        return None


def collect_league(target):
    league_id = target['league_id']
    league_std = target['league_std']
    league_en = target['league_en']
    league_cn = target['league_cn']

    print(f"\n采集 {league_cn} ({league_en}) - league_id={league_id}")

    conn = sqlite3.connect(DB_PATH, timeout=30.0)
    cursor = conn.cursor()

    total_matches = 0
    total_odds = 0

    for season_name, from_date, to_date in target['seasons']:
        url = f"{API_BASE}/?action=get_events&APIkey={API_KEY}&league_id={league_id}&from={from_date}&to={to_date}"
        data = fetch_api(url)

        if not isinstance(data, list) or len(data) == 0:
            print(f"  {season_name}: 无数据")
            time.sleep(1)
            continue

        print(f"  {season_name}: {len(data)} 场比赛")

        for m in data:
            try:
                match_date = m.get('match_date', '')
                match_time = m.get('match_time', '')
                home_team = m.get('match_hometeam_name', '')
                away_team = m.get('match_awayteam_name', '')
                home_score = m.get('match_hometeam_score')
                away_score = m.get('match_awayteam_score')
                status_raw = m.get('match_status', '')
                stadium = m.get('match_stadium', '')
                referee = m.get('match_referee', '')
                round_name = m.get('match_round', '')
                league_name = m.get('league_name', '')

                status_map = {'FT': 'finished', 'Finished': 'finished', 'NS': 'scheduled',
                              'TBD': 'scheduled', 'Postponed': 'postponed'}
                status = status_map.get(status_raw, status_raw or 'scheduled')

                def to_int(val):
                    try:
                        return int(val) if val not in (None, '', '-') else None
                    except:
                        return None

                home_low = home_team.lower().strip()
                away_low = away_team.lower().strip()
                match_key = f"{match_date}|{home_low}|{away_low}"

                cursor.execute('''
                    INSERT OR IGNORE INTO matches
                    (match_key, date, time, home_team, away_team, league, league_standard, season, status,
                     home_score, away_score, venue, referee)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (match_key, match_date, match_time, home_team, away_team, league_name,
                      league_std, season_name, status, to_int(home_score), to_int(away_score), stadium, referee))

                if cursor.rowcount > 0:
                    total_matches += 1

                # match_data
                match_json = json.dumps({
                    'match_date': match_date,
                    'home_team': home_team,
                    'away_team': away_team,
                    'home_score': to_int(home_score),
                    'away_score': to_int(away_score),
                    'status': status,
                    'round': round_name,
                    'stadium': stadium,
                    'referee': referee,
                    'league_id': league_id,
                    'league_name': league_name,
                    'source': 'apifootball'
                }, ensure_ascii=False)

                cursor.execute('''
                    INSERT OR REPLACE INTO match_data
                    (match_key, source, data_type, data_json)
                    VALUES (?, 'apifootball', 'match', ?)
                ''', (match_key, match_json))

            except:
                pass

        conn.commit()
        time.sleep(1.5)

        # 赔率
        url_odds = f"{API_BASE}/?action=get_odds&APIkey={API_KEY}&league_id={league_id}&from={from_date}&to={to_date}"
        odds_data = fetch_api(url_odds)

        if isinstance(odds_data, list) and len(odds_data) > 0:
            print(f"  {season_name} odds: {len(odds_data)} 条")
            for o in odds_data:
                try:
                    o_home = o.get('match_hometeam_name', '')
                    o_away = o.get('match_awayteam_name', '')
                    o_date = o.get('match_date', '')
                    odds_1 = o.get('odd_1', '')
                    odds_x = o.get('odd_x', '')
                    odds_2 = o.get('odd_2', '')
                    bookmaker = o.get('odd_bookmakers', '')

                    if odds_1 and odds_x and odds_2:
                        o_key = f"{o_date}|{o_home.lower().strip()}|{o_away.lower().strip()}"
                        odds_json = json.dumps({
                            'home': float(odds_1),
                            'draw': float(odds_x),
                            'away': float(odds_2),
                            'bookmaker': bookmaker
                        }, ensure_ascii=False)

                        cursor.execute('''
                            INSERT OR IGNORE INTO match_data
                            (match_key, source, data_type, data_json)
                            VALUES (?, 'apifootball', 'odds', ?)
                        ''', (o_key, odds_json))
                        total_odds += cursor.rowcount
                except:
                    pass
            conn.commit()
            time.sleep(1.5)

    conn.close()
    print(f"  总计: 新增{total_matches}场比赛, {total_odds}条赔率")


def main():
    print("=" * 60)
    print(f"采集解放者杯、欧协联、葡超数据")
    print(f"时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)

    for target in TARGETS:
        collect_league(target)

    # 验证
    conn = sqlite3.connect(DB_PATH, timeout=30.0)
    cursor = conn.cursor()
    print(f"\n=== 采集后验证 ===")
    for target in TARGETS:
        cursor.execute('SELECT season, COUNT(*) FROM matches WHERE league_standard = ? GROUP BY season ORDER BY season DESC', (target['league_std'],))
        rows = cursor.fetchall()
        total = sum(c for _, c in rows)
        print(f"  {target['league_cn']}: {total}场")
        for s, c in rows:
            print(f"    {s}: {c}场")

    cursor.execute('SELECT COUNT(*) FROM matches')
    print(f"\n  总比赛数: {cursor.fetchone()[0]:,}")
    conn.close()


if __name__ == '__main__':
    main()