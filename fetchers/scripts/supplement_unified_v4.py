"""
补充 unified_football.db - v4 精确匹配
用 team_aliases.json + 09_other_data 映射做精确队名匹配
"""
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
    633: 'uefa_nations_league',
    354: 'euro_qualifiers',
    356: 'friendlies',
    17: 'copa_america',
    29: 'africa_cup_of_nations',
    347: 'afc_asian_cup',
    219: 'k_league_1',
    218: 'k_league_2',
    209: 'j1_league',
    212: 'j2_league',
}

YEARS = ['2024', '2023', '2022', '2021', '2020']


def build_alias_index():
    """构建 队名任意别名 → 标准英文名 的完整索引"""
    index = {}

    # 1. team_aliases.json (主要联赛的详细别名)
    with open('d:/football_tools/fetchers/common/data/team_aliases.json', 'r', encoding='utf-8') as f:
        aliases = json.load(f)

    for league_name, teams in aliases.items():
        if not isinstance(teams, dict):
            continue
        for std_name, info in teams.items():
            if not isinstance(info, dict):
                continue
            key = std_name.lower().strip()
            index[key] = std_name
            # 英文别名
            for alias in info.get('en_aliases', []):
                a = alias.lower().strip()
                if a and a not in index:
                    index[a] = std_name
            # 中文名
            cn = info.get('cn', '')
            if cn:
                index[cn.lower().strip()] = std_name
            # 中文别名
            for alias in info.get('cn_aliases', []):
                a = alias.lower().strip()
                if a and a not in index:
                    index[a] = std_name
            # 德文名
            de = info.get('de', '')
            if de:
                index[de.lower().strip()] = std_name

    # 2. linkage/team_name_mapping.json (2900+条目)
    with open('d:/football_tools/data/linkage/team_name_mapping.json', 'r', encoding='utf-8') as f:
        mapping = json.load(f)
    for k, v in mapping.items():
        a = k.lower().strip()
        std = v.strip()
        if a and std and a not in index:
            index[a] = std
            # 也把标准名小写加入
            std_low = std.lower().strip()
            if std_low not in index:
                index[std_low] = std

    # 3. 09_other_data/team_name_mapping.json (缩写→全称)
    with open('d:/football_tools/data/09_other_data/team_name_mapping.json', 'r', encoding='utf-8') as f:
        mapping2 = json.load(f)
    for k, v in mapping2.items():
        a = k.lower().strip()
        std = v.strip()
        if a and std and a not in index:
            index[a] = std

    print(f"队名索引构建完成: {len(index)} 个别名")
    return index


def lookup_std_name(name, index):
    """用索引查找标准队名"""
    if not name:
        return name
    low = name.lower().strip()
    if low in index:
        return index[low]
    # 去掉FC/CF等后缀再试
    for suffix in [' fc', ' cf', ' sc', ' ac', ' afc', ' rb', ' sv', ' vfl', ' as', ' ud', ' cd']:
        stripped = low.replace(suffix, '').strip()
        if stripped in index:
            return index[stripped]
    return name  # 找不到就返回原名


def fetch_api(url):
    try:
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=30) as response:
            return json.loads(response.read().decode('utf-8'))
    except:
        return None


def main():
    print("=" * 60)
    print(f"精确匹配补充缺失数据 v4")
    print(f"时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)

    # 构建队名索引
    alias_index = build_alias_index()

    conn = sqlite3.connect(DB_PATH, timeout=30.0)
    cursor = conn.cursor()

    # 先把数据库里的队名也标准化
    cursor.execute('SELECT DISTINCT home_team FROM matches WHERE home_team IS NOT NULL AND home_team != ""')
    db_teams = set(r[0] for r in cursor.fetchall())
    cursor.execute('SELECT DISTINCT away_team FROM matches WHERE away_team IS NOT NULL AND away_team != ""')
    db_teams.update(r[0] for r in cursor.fetchall())

    # 为数据库中的每个队名找到标准名
    db_team_to_std = {}
    for team in db_teams:
        std = lookup_std_name(team, alias_index)
        if std != team:
            db_team_to_std[team] = std

    print(f"数据库队名可标准化: {len(db_team_to_std)} 个")

    # 开始按联赛获取API数据
    total_updated = 0

    for league_id, league_std in LEAGUE_MAP.items():
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

            # 用标准名建索引加速查找
            db_idx = {}
            for mk, db_h, db_a, db_t, db_v, db_r, db_hs, db_as in db_matches:
                std_h = lookup_std_name(db_h, alias_index)
                std_a = lookup_std_name(db_a, alias_index)
                key = (std_h.lower(), std_a.lower())
                if key not in db_idx:
                    db_idx[key] = []
                db_idx[key].append((mk, db_h, db_a, db_t, db_v, db_r, db_hs, db_as))

            for api_m in data:
                api_home = api_m.get('match_hometeam_name', '')
                api_away = api_m.get('match_awayteam_name', '')
                api_time = api_m.get('match_time', '')
                api_stadium = api_m.get('match_stadium', '')
                api_referee = api_m.get('match_referee', '')
                api_hs = api_m.get('match_hometeam_score')
                api_as = api_m.get('match_awayteam_score')

                # API队名标准化
                std_api_h = lookup_std_name(api_home, alias_index)
                std_api_a = lookup_std_name(api_away, alias_index)
                lookup_key = (std_api_h.lower(), std_api_a.lower())

                if lookup_key not in db_idx:
                    continue

                for mk, db_h, db_a, db_t, db_v, db_r, db_hs, db_as in db_idx[lookup_key]:
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