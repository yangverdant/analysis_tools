"""
按联赛批量补充 unified_football.db 缺失数据
效率更高：一次请求获取整个联赛的所有比赛
"""
import json
import sqlite3
import urllib.request
import time
import re
from pathlib import Path
from datetime import datetime

DB_PATH = Path('d:/football_tools/data/unified_football.db')
API_KEY = 'bf82d62ee5412d32a95362699389583fdbefa113f4efb371b87b585f12d64443'
API_BASE = 'https://apiv3.apifootball.com'

# apifootball league_id → league_standard 映射
LEAGUE_MAP = {
    152: ('premier_league', '英超'),
    153: ('championship', '英冠'),
    302: ('la_liga', '西甲'),
    168: ('bundesliga', '德甲'),
    167: ('bundesliga_2', '德乙'),
    262: ('serie_a', '意甲'),
    263: ('serie_b', '意乙'),
    168: ('ligue_1', '法甲'),
    169: ('ligue_2', '法乙'),
    148: ('eredivisie', '荷甲'),
    154: ('primeira_liga', '葡超'),
    3: ('champions_league', '欧冠'),
    4: ('europa_league', '欧联'),
    1: ('world_cup', '世界杯'),
    633: ('uefa_nations_league', '欧国联'),
    354: ('euro_qualifiers', '欧洲杯预选赛'),
    356: ('friendlies', '友谊赛'),
    28: ('world_cup', '世界杯'),
    347: ('afc_asian_cup', '亚洲杯'),
    29: ('africa_cup_of_nations', '非洲杯'),
    17: ('copa_america', '美洲杯'),
    15: ('gold_cup', '金杯赛'),
    39: ('k_league_1', 'K联赛1'),
    40: ('k_league_2', 'K联赛2'),
    98: ('j1_league', 'J1联赛'),
    99: ('j2_league', 'J2联赛'),
    100: ('j3_league', 'J3联赛'),
}

SEASONS = ['2024-2025', '2023-2024', '2022-2023', '2021-2022', '2020-2021']


def normalize_team(name):
    """简化队名"""
    if not name:
        return ''
    n = name.lower().strip()
    for suffix in [' fc', ' cf', ' sc', ' ac', ' afc', ' rb', ' sv', ' vfl', ' as', ' ud', ' cd']:
        n = n.replace(suffix, '')
    n = re.sub(r'\s+', ' ', n).strip()
    return n


def teams_match(n1, n2):
    """模糊匹配队名"""
    a = normalize_team(n1)
    b = normalize_team(n2)
    if a == b:
        return True
    if a in b or b in a:
        return True
    # 关键词匹配
    words_a = set(a.split()) - {'united', 'city', 'town', 'fc', 'cf', 'sc', 'ac', 'rb', 'as', 'ud', 'cd'}
    words_b = set(b.split()) - {'united', 'city', 'town', 'fc', 'cf', 'sc', 'ac', 'rb', 'as', 'ud', 'cd'}
    if words_a & words_b:
        return True
    return False


def fetch_api(url):
    try:
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=30) as response:
            return json.loads(response.read().decode('utf-8'))
    except:
        return None


def main():
    print("=" * 60)
    print(f"按联赛批量补充缺失数据")
    print(f"时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)

    conn = sqlite3.connect(DB_PATH, timeout=30.0)
    cursor = conn.cursor()

    # 先看还有多少缺失
    cursor.execute('SELECT COUNT(*) FROM matches')
    total = cursor.fetchone()[0]
    cursor.execute('SELECT COUNT(*) FROM matches WHERE time IS NULL OR time = ""')
    no_time = cursor.fetchone()[0]
    cursor.execute('SELECT COUNT(*) FROM matches WHERE venue IS NULL OR venue = ""')
    no_venue = cursor.fetchone()[0]
    cursor.execute('SELECT COUNT(*) FROM matches WHERE referee IS NULL OR referee = ""')
    no_ref = cursor.fetchone()[0]
    print(f"  当前缺失: time={no_time}, venue={no_venue}, referee={no_ref}")

    # 看数据库中有哪些league_standard
    cursor.execute('SELECT league_standard, COUNT(*) FROM matches GROUP BY league_standard ORDER BY COUNT(*) DESC')
    db_leagues = cursor.fetchall()
    print(f"\n数据库联赛分布:")
    for lg, cnt in db_leagues[:15]:
        print(f"  {lg}: {cnt}")

    # 对每个联赛，获取对应日期范围内的比赛
    total_updated = 0

    for league_id, (league_std, league_cn) in LEAGUE_MAP.items():
        # 找出该联赛中缺失数据的比赛日期
        cursor.execute("""
            SELECT date, COUNT(*) as cnt,
                   SUM(CASE WHEN time IS NULL OR time = '' THEN 1 ELSE 0 END) as no_time
            FROM matches
            WHERE league_standard = ?
            AND (time IS NULL OR time = '' OR venue IS NULL OR venue = '')
            GROUP BY date
            ORDER BY date DESC
        """, (league_std,))
        dates = cursor.fetchall()

        if not dates:
            continue

        print(f"\n{league_cn} ({league_std}): {len(dates)} 个日期需要补充")

        for date, cnt, no_t in dates:
            url = f"{API_BASE}/?action=get_events&APIkey={API_KEY}&league_id={league_id}&from={date}&to={date}"
            data = fetch_api(url)

            if not isinstance(data, list):
                continue

            # 获取该日期该联赛的数据库比赛
            cursor.execute('SELECT match_key, home_team, away_team, time, venue, referee FROM matches WHERE date = ? AND league_standard = ?', (date, league_std))
            db_matches = cursor.fetchall()

            updated = 0
            for api_m in data:
                api_home = api_m.get('match_hometeam_name', '')
                api_away = api_m.get('match_awayteam_name', '')
                api_time = api_m.get('match_time', '')
                api_stadium = api_m.get('match_stadium', '')
                api_referee = api_m.get('match_referee', '')

                for mk, db_h, db_a, db_t, db_v, db_r in db_matches:
                    if teams_match(api_home, db_h) and teams_match(api_away, db_a):
                        updates = {}
                        if (not db_t or db_t == '') and api_time and api_time != '-':
                            updates['time'] = api_time
                        if (not db_v or db_v == '') and api_stadium:
                            updates['venue'] = api_stadium
                        if (not db_r or db_r == '') and api_referee:
                            updates['referee'] = api_referee

                        if updates:
                            set_clause = ', '.join([f'[{k}] = ?' for k in updates])
                            vals = list(updates.values()) + [mk]
                            cursor.execute(f'UPDATE matches SET {set_clause} WHERE match_key = ?', vals)
                            updated += cursor.rowcount
                        break

            if updated > 0:
                conn.commit()
                total_updated += updated

            time.sleep(0.8)

        print(f"  {league_cn}: 本轮更新 {total_updated} 条")

    conn.commit()

    # 最终报告
    cursor.execute('SELECT COUNT(*) FROM matches')
    total = cursor.fetchone()[0]
    print(f"\n=== 最终统计 ===")
    print(f"matches总数: {total:,}")
    for f in ['time', 'venue', 'referee', 'league_standard', 'season', 'home_score', 'away_score']:
        cursor.execute(f'SELECT COUNT(*) FROM matches WHERE [{f}] IS NULL OR [{f}] = ""')
        missing = cursor.fetchone()[0]
        pct = missing * 100 / total
        tag = '[!]' if pct > 10 else '[OK]'
        print(f"  {tag} {f}: 缺失 {missing:,} ({pct:.1f}%)")

    conn.close()
    print(f"\n总更新: {total_updated} 条")


if __name__ == '__main__':
    main()