"""
按联赛批量补充 unified_football.db 缺失数据
用正确的API league_id + 模糊匹配队名
"""
import json
import sqlite3
import urllib.request
import time
import re
import sys
from pathlib import Path
from datetime import datetime

sys.stdout.reconfigure(encoding='utf-8')

DB_PATH = Path('d:/football_tools/data/unified_football.db')
API_KEY = 'bf82d62ee5412d32a95362699389583fdbefa113f4efb371b87b585f12d64443'
API_BASE = 'https://apiv3.apifootball.com'

# 正确的league_id映射 (从API验证)
LEAGUE_MAP = {
    152: 'premier_league',
    153: 'championship',
    302: 'la_liga',
    175: 'bundesliga',
    171: 'bundesliga_2',
    207: 'serie_a',
    206: 'serie_b',
    168: 'ligue_1',
    164: 'ligue_2',
    244: 'eredivisie',
    266: 'primeira_liga',
    301: 'segunda_division',
    3: 'champions_league',
    4: 'europa_league',
    28: 'world_cup',
    1: 'euro',
    633: 'uefa_nations_league',
    354: 'euro_qualifiers',
    356: 'friendlies',
    17: 'copa_america',
    15: 'gold_cup',
    29: 'africa_cup_of_nations',
    347: 'afc_asian_cup',
    22: 'afc_wc_qualifiers',
    21: 'caf_wc_qualifiers',
    23: 'concacaf_wc_qualifiers',
    24: 'uefa_wc_qualifiers',
    27: 'conmebol_wc_qualifiers',
    219: 'k_league_1',
    218: 'k_league_2',
    209: 'j1_league',
    212: 'j2_league',
    601: 'j3_league',
    146: 'fa_cup',
    147: 'efl_cup',
    172: 'dfb_pokal',
    205: 'coppa_italia',
    165: 'coupe_de_france',
    300: 'copa_del_rey',
    332: 'mls',
    235: 'liga_mx',
    99: 'brasileirao',
}

# 反向映射: league_standard → league_id
STD_TO_ID = {v: k for k, v in LEAGUE_MAP.items()}

# 年份范围
YEARS = ['2024', '2023', '2022', '2021', '2020']


def normalize_team(name):
    if not name:
        return ''
    n = name.lower().strip()
    for suffix in [' fc', ' cf', ' sc', ' ac', ' afc', ' rb', ' sv', ' vfl', ' as', ' ud', ' cd']:
        n = n.replace(suffix, '')
    n = re.sub(r'\s+', ' ', n).strip()
    return n


def teams_match(n1, n2):
    a = normalize_team(n1)
    b = normalize_team(n2)
    if a == b:
        return True
    if a in b or b in a:
        return True
    skip = {'united', 'city', 'town', 'fc', 'cf', 'sc', 'ac', 'rb', 'as', 'ud', 'cd'}
    words_a = set(a.split()) - skip
    words_b = set(b.split()) - skip
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

    # 统计当前缺失
    cursor.execute('SELECT COUNT(*) FROM matches')
    total = cursor.fetchone()[0]

    cursor.execute('SELECT COUNT(*) FROM matches WHERE time IS NULL OR time = ""')
    no_time = cursor.fetchone()[0]
    cursor.execute('SELECT COUNT(*) FROM matches WHERE venue IS NULL OR venue = ""')
    no_venue = cursor.fetchone()[0]
    cursor.execute('SELECT COUNT(*) FROM matches WHERE referee IS NULL OR referee = ""')
    no_ref = cursor.fetchone()[0]

    print(f"  当前: time缺失 {no_time} ({no_time*100/total:.1f}%), venue缺失 {no_venue} ({no_venue*100/total:.1f}%), referee缺失 {no_ref} ({no_ref*100/total:.1f}%)")

    total_updated = 0
    total_leagues = 0

    for league_id, league_std in LEAGUE_MAP.items():
        # 看该联赛在数据库中有多少缺失数据的比赛
        cursor.execute("""
            SELECT COUNT(*) FROM matches
            WHERE league_standard = ?
            AND (time IS NULL OR time = '' OR venue IS NULL OR venue = '' OR referee IS NULL OR referee = '')
        """, (league_std,))
        missing_cnt = cursor.fetchone()[0]

        if missing_cnt == 0:
            continue

        total_leagues += 1
        league_updated = 0

        print(f"\n[{league_std}] league_id={league_id}, 缺失{missing_cnt}场")

        for year in YEARS:
            from_date = f"{year}-01-01"
            to_date = f"{year}-12-31"

            url = f"{API_BASE}/?action=get_events&APIkey={API_KEY}&league_id={league_id}&from={from_date}&to={to_date}"
            data = fetch_api(url)

            if not isinstance(data, list) or len(data) == 0:
                continue

            # 获取该联赛该年份的数据库比赛
            cursor.execute("""
                SELECT match_key, home_team, away_team, time, venue, referee, home_score, away_score
                FROM matches
                WHERE league_standard = ? AND date >= ? AND date <= ?
                AND (time IS NULL OR time = '' OR venue IS NULL OR venue = '' OR referee IS NULL OR referee = '')
            """, (league_std, from_date, to_date))
            db_matches = cursor.fetchall()

            for api_m in data:
                api_home = api_m.get('match_hometeam_name', '')
                api_away = api_m.get('match_awayteam_name', '')
                api_time = api_m.get('match_time', '')
                api_stadium = api_m.get('match_stadium', '')
                api_referee = api_m.get('match_referee', '')
                api_home_score = api_m.get('match_hometeam_score')
                api_away_score = api_m.get('match_awayteam_score')

                for mk, db_h, db_a, db_t, db_v, db_r, db_hs, db_as in db_matches:
                    if teams_match(api_home, db_h) and teams_match(api_away, db_a):
                        updates = {}
                        if (not db_t or db_t == '') and api_time and api_time != '-':
                            updates['time'] = api_time
                        if (not db_v or db_v == '') and api_stadium:
                            updates['venue'] = api_stadium
                        if (not db_r or db_r == '') and api_referee:
                            updates['referee'] = api_referee
                        if db_hs is None and api_home_score and api_home_score not in ('', '-'):
                            try:
                                updates['home_score'] = int(api_home_score)
                            except:
                                pass
                        if db_as is None and api_away_score and api_away_score not in ('', '-'):
                            try:
                                updates['away_score'] = int(api_away_score)
                            except:
                                pass

                        if updates:
                            set_clause = ', '.join([f'[{k}] = ?' for k in updates])
                            vals = list(updates.values()) + [mk]
                            cursor.execute(f'UPDATE matches SET {set_clause} WHERE match_key = ?', vals)
                            league_updated += cursor.rowcount
                        break

            conn.commit()
            time.sleep(1.5)

        total_updated += league_updated
        print(f"  本轮更新: {league_updated} 条")

    conn.commit()

    # 时区统一：API返回UTC，转为北京时间+8
    print("\n[时区统一] UTC → 北京时间(UTC+8)")
    cursor.execute("SELECT match_key, time FROM matches WHERE time IS NOT NULL AND time != ''")
    all_times = cursor.fetchall()
    tz_updated = 0

    for mk, t in all_times:
        try:
            parts = t.split(':')
            h = int(parts[0])
            m = int(parts[1])
            new_h = (h + 8) % 24
            new_time = f"{new_h:02d}:{m:02d}"
            if new_time != t:
                cursor.execute('UPDATE matches SET time = ? WHERE match_key = ?', (new_time, mk))
                tz_updated += cursor.rowcount
        except:
            pass

    conn.commit()
    print(f"  时区修正: {tz_updated} 条")

    # 最终报告
    print(f"\n{'=' * 60}")
    print("最终统计")
    print(f"{'=' * 60}")
    cursor.execute('SELECT COUNT(*) FROM matches')
    total = cursor.fetchone()[0]
    for f in ['time', 'venue', 'referee', 'league_standard', 'season', 'home_score', 'away_score']:
        cursor.execute(f'SELECT COUNT(*) FROM matches WHERE [{f}] IS NULL OR [{f}] = ""')
        missing = cursor.fetchone()[0]
        pct = missing * 100 / total
        tag = '[!]' if pct > 10 else '[OK]'
        print(f"  {tag} {f}: 缺失 {missing:,} ({pct:.1f}%)")

    conn.close()
    print(f"\n完成! 总更新: {total_updated} 条, 时区修正: {tz_updated} 条")


if __name__ == '__main__':
    main()