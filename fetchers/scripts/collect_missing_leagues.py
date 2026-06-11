"""采集解放者杯、欧协联、葡超数据到unified_football.db"""
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

# 目标联赛 (从API获取到的league_id)
TARGETS = [
    (18, 'copa_libertadores', 'Copa Libertadores', '解放者杯'),
    (266, 'primeira_liga', 'Primeira Liga', '葡超'),
]

# 欧协联需要从API确认league_id
# UEFA Europa Conference League = 770 (可能)

YEARS = ['2024', '2023', '2022']


def fetch_api(url):
    try:
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=30) as response:
            return json.loads(response.read().decode('utf-8'))
    except:
        return None


def find_conference_league_id():
    """从API获取欧协联的league_id"""
    url = f"{API_BASE}/?action=get_leagues&APIkey={API_KEY}"
    data = fetch_api(url)
    if isinstance(data, list):
        for lg in data:
            name = lg.get('league_name', '')
            if 'conference' in name.lower():
                lid = lg.get('league_id')
                country = lg.get('country_name', '')
                print(f"  找到: id={lid} name={name} country={country}")
                return lid, name
    return None, None


def collect_league(league_id, league_std, league_en, league_cn):
    """采集一个联赛的数据"""
    print(f"\n采集 {league_cn} ({league_en}) - league_id={league_id}")

    conn = sqlite3.connect(DB_PATH, timeout=30.0)
    cursor = conn.cursor()

    total_matches = 0
    total_odds = 0

    for year in YEARS:
        from_date = f"{year}-01-01"
        to_date = f"{year}-12-31"

        url = f"{API_BASE}/?action=get_events&APIkey={API_KEY}&league_id={league_id}&from={from_date}&to={to_date}"
        data = fetch_api(url)

        if not isinstance(data, list) or len(data) == 0:
            print(f"  {year}: 无数据")
            time.sleep(1)
            continue

        print(f"  {year}: {len(data)} 场比赛")

        for m in data:
            try:
                match_date = m.get('match_date', '')
                match_time = m.get('match_time', '')
                home_team = m.get('match_hometeam_name', '')
                away_team = m.get('match_awayteam_name', '')
                home_score = m.get('match_hometeam_score')
                away_score = m.get('match_awayteam_score')
                home_score_ht = m.get('match_hometeam_halftime_score')
                away_score_ht = m.get('match_awayteam_halftime_score')
                status_raw = m.get('match_status', '')
                stadium = m.get('match_stadium', '')
                referee = m.get('match_referee', '')
                round_name = m.get('match_round', '')
                league_name = m.get('league_name', '')

                # 状态映射
                status_map = {'FT': 'finished', 'Finished': 'finished', 'NS': 'scheduled',
                              'TBD': 'scheduled', 'Postponed': 'postponed', 'Cancelled': 'cancelled'}
                status = status_map.get(status_raw, status_raw or 'scheduled')

                # 比分
                def to_int(val):
                    try:
                        return int(val) if val not in (None, '', '-') else None
                    except:
                        return None

                # season
                year_int = int(year)
                month = int(match_date[5:7]) if len(match_date) >= 7 else 0
                if month >= 8:
                    season = f"{year_int}-{year_int+1}"
                else:
                    season = f"{year_int-1}-{year_int}"

                # match_key
                home_low = home_team.lower().strip()
                away_low = away_team.lower().strip()
                match_key = f"{match_date}|{home_low}|{away_low}"

                # 插入matches
                cursor.execute('''
                    INSERT OR IGNORE INTO matches
                    (match_key, date, time, home_team, away_team, league, league_standard, season, status,
                     home_score, away_score, venue, referee)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (match_key, match_date, match_time, home_team, away_team, league_name,
                      league_std, season, status, to_int(home_score), to_int(away_score), stadium, referee))

                if cursor.rowcount > 0:
                    total_matches += 1

                # match_data
                match_json = json.dumps({
                    'match_date': match_date,
                    'home_team': home_team,
                    'away_team': away_team,
                    'home_score': to_int(home_score),
                    'away_score': to_int(away_score),
                    'home_score_ht': to_int(home_score_ht),
                    'away_score_ht': to_int(away_score_ht),
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

            except Exception as e:
                pass

        conn.commit()
        time.sleep(1.5)

        # 也获取赔率
        url_odds = f"{API_BASE}/?action=get_odds&APIkey={API_KEY}&league_id={league_id}&from={from_date}&to={to_date}"
        odds_data = fetch_api(url_odds)

        if isinstance(odds_data, list) and len(odds_data) > 0:
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

    # 先找到欧协联league_id
    conf_id, conf_name = find_conference_league_id()
    if conf_id:
        TARGETS.append((conf_id, 'conference_league', conf_name, '欧协联'))
    else:
        print("  未找到欧协联，跳过")

    for league_id, league_std, league_en, league_cn in TARGETS:
        collect_league(league_id, league_std, league_en, league_cn)

    # 验证
    conn = sqlite3.connect(DB_PATH, timeout=30.0)
    cursor = conn.cursor()
    print(f"\n=== 采集后验证 ===")
    for league_id, league_std, league_en, league_cn in TARGETS:
        cursor.execute('SELECT COUNT(*) FROM matches WHERE league_standard = ?', (league_std,))
        cnt = cursor.fetchone()[0]
        print(f"  {league_cn}: {cnt}场")

    cursor.execute('SELECT COUNT(*) FROM matches')
    total = cursor.fetchone()[0]
    print(f"  总比赛数: {total:,}")
    conn.close()


if __name__ == '__main__':
    main()