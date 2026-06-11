"""
补充 unified_football.db 缺失数据 - v3
策略：先建立队名映射表，再批量更新
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

# 常见队名映射（DB名 → API名 的核心词映射）
TEAM_NAME_MAP = {
    'man united': 'manchester united',
    'man city': 'manchester city',
    'nottm forest': 'nottingham forest',
    'sheff united': 'sheffield united',
    'sheffield utd': 'sheffield united',
    'spurs': 'tottenham hotspur',
    'tottenham': 'tottenham hotspur',
    'wolves': 'wolverhampton wanderers',
    'wolverhampton': 'wolverhampton wanderers',
    'brighton': 'brighton and hove albion',
    'newcastle': 'newcastle united',
    'west ham': 'west ham united',
    'aston villa': 'aston villa',
    'crystal palace': 'crystal palace',
    'bournemouth': 'afc bournemouth',
    'brentford': 'brentford',
    'fulham': 'fulham',
    'everton': 'everton',
    'ipswich': 'ipswich town',
    'leicester': 'leicester city',
    'southampton': 'southampton',
    'arsenal': 'arsenal',
    'liverpool': 'liverpool',
    'chelsea': 'chelsea',
    'barcelona': 'barcelona',
    'real madrid': 'real madrid',
    'atletico madrid': 'atletico madrid',
    'ath madrid': 'atletico madrid',
    'ath bilbao': 'athletic bilbao',
    'athletic bilbao': 'athletic bilbao',
    'sociedad': 'real sociedad',
    'villarreal': 'villarreal',
    'betis': 'real betis',
    'celta vigo': 'celta de vigo',
    'paris sg': 'paris saint-germain',
    'paris saint-germain': 'paris saint-germain',
    'bayern munich': 'bayern munich',
    'bayern': 'bayern munich',
    'dortmund': 'borussia dortmund',
    'b munich': 'bayern munich',
    'leverkusen': 'bayer leverkusen',
    'stuttgart': 'vfb stuttgart',
    'inter': 'inter milan',
    'inter milan': 'inter milan',
    'ac milan': 'ac milan',
    'milan': 'ac milan',
    'juventus': 'juventus',
    'napoli': 'napoli',
    'roma': 'as roma',
    'as rome': 'as roma',
    'lazio': 'lazio',
    'fiorentina': 'fiorentina',
    'atalanta': 'atalanta',
    'corinthians': 'corinthians',
    'flamengo': 'flamengo',
    'palmeiras': 'palmeiras',
    'sao paulo': 'sao paulo',
}

# league_id映射
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
    24: 'uefa_wc_qualifiers',
    219: 'k_league_1',
    218: 'k_league_2',
    209: 'j1_league',
    212: 'j2_league',
}

YEARS = ['2024', '2023', '2022', '2021', '2020']


def normalize(name):
    """更激进的队名标准化"""
    if not name:
        return ''
    n = name.lower().strip()
    # 先用映射表
    for k, v in TEAM_NAME_MAP.items():
        if n == k or n.startswith(k):
            n = v
            break
    # 移除常见后缀和前缀
    for s in [' fc', ' cf', ' sc', ' ac', ' afc', ' rb', ' sv', ' vfl',
              ' as', ' ud', ' cd', ' 1.', ' fk', ' sk', ' ks', ' tsv',
              ' bfc', ' cfc', ' ssc']:
        n = n.replace(s, ' ')
    n = re.sub(r'\s+', ' ', n).strip()
    return n


def teams_match(n1, n2):
    a = normalize(n1)
    b = normalize(n2)
    if a == b:
        return True
    # 互相包含
    if a in b or b in a:
        return True
    # 去掉形容词后比较核心词
    skip = {'united', 'city', 'town', 'club', 'fc', 'cf', 'sc', 'ac', 'rb', 'as', 'ud', 'cd',
            'real', 'de', 'la', 'del', 'and', 'the', 'of'}
    words_a = set(a.split()) - skip
    words_b = set(b.split()) - skip
    if words_a and words_b and (words_a & words_b):
        return True
    return False


def fetch_api(url):
    try:
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=30) as response:
            return json.loads(response.read().decode('utf-8'))
    except:
        return None


def build_team_alias_cache(conn):
    """从team_aliases构建映射"""
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM team_aliases')
    aliases = {}
    for row in cursor.fetchall():
        # team_aliases 格式可能不同，先跳过
        pass
    return aliases


def main():
    print("=" * 60)
    print(f"按联赛补充缺失数据 v3 (改进队名匹配)")
    print(f"时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)

    conn = sqlite3.connect(DB_PATH, timeout=30.0)
    cursor = conn.cursor()

    cursor.execute('SELECT COUNT(*) FROM matches')
    total = cursor.fetchone()[0]

    for f in ['time', 'venue', 'referee']:
        cursor.execute(f'SELECT COUNT(*) FROM matches WHERE [{f}] IS NULL OR [{f}] = ""')
        missing = cursor.fetchone()[0]
        print(f"  缺失 {f}: {missing} ({missing*100/total:.1f}%)")

    total_updated = 0

    for league_id, league_std in LEAGUE_MAP.items():
        # 该联赛有多少缺失
        cursor.execute("""
            SELECT COUNT(*) FROM matches
            WHERE league_standard = ?
            AND (time IS NULL OR time = '' OR venue IS NULL OR venue = '' OR referee IS NULL OR referee = '')
        """, (league_std,))
        missing = cursor.fetchone()[0]
        if missing == 0:
            continue

        print(f"\n[{league_std}] league_id={league_id}, 缺失{missing}场")

        league_updated = 0

        for year in YEARS:
            url = f"{API_BASE}/?action=get_events&APIkey={API_KEY}&league_id={league_id}&from={year}-01-01&to={year}-12-31"
            data = fetch_api(url)

            if not isinstance(data, list) or len(data) == 0:
                continue

            # 获取该联赛该年份缺失数据的比赛
            cursor.execute("""
                SELECT match_key, home_team, away_team, time, venue, referee, home_score, away_score
                FROM matches
                WHERE league_standard = ? AND date >= ? AND date <= ?
                AND (time IS NULL OR time = '' OR venue IS NULL OR venue = '' OR referee IS NULL OR referee = '')
            """, (league_std, f"{year}-01-01", f"{year}-12-31"))
            db_matches = cursor.fetchall()

            # 为DB比赛建立索引
            matched_count = 0

            for api_m in data:
                api_home = api_m.get('match_hometeam_name', '')
                api_away = api_m.get('match_awayteam_name', '')
                api_date = api_m.get('match_date', '')
                api_time = api_m.get('match_time', '')
                api_stadium = api_m.get('match_stadium', '')
                api_referee = api_m.get('match_referee', '')
                api_hs = api_m.get('match_hometeam_score')
                api_as = api_m.get('match_awayteam_score')

                for mk, db_h, db_a, db_t, db_v, db_r, db_hs, db_as in db_matches:
                    if teams_match(api_home, db_h) and teams_match(api_away, db_a):
                        updates = {}
                        if (not db_t or db_t == '') and api_time and api_time != '-':
                            updates['time'] = api_time
                        if (not db_v or db_v == '') and api_stadium:
                            updates['venue'] = api_stadium
                        if (not db_r or db_r == '') and api_referee:
                            updates['referee'] = api_referee
                        if db_hs is None and api_hs and api_hs not in ('', '-'):
                            try:
                                updates['home_score'] = int(api_hs)
                            except:
                                pass
                        if db_as is None and api_as and api_as not in ('', '-'):
                            try:
                                updates['away_score'] = int(api_as)
                            except:
                                pass

                        if updates:
                            set_clause = ', '.join([f'[{k}] = ?' for k in updates])
                            vals = list(updates.values()) + [mk]
                            cursor.execute(f'UPDATE matches SET {set_clause} WHERE match_key = ?', vals)
                            league_updated += cursor.rowcount
                            matched_count += 1
                        break

            conn.commit()
            time.sleep(1.5)

        total_updated += league_updated
        print(f"  更新: {league_updated} 条")

    # 时区统一 UTC→北京+8
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
    print(f"\n完成! 更新: {total_updated}, 时区修正: {tz_updated}")


if __name__ == '__main__':
    main()