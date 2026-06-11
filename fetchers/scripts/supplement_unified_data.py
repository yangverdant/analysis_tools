"""
补充 unified_football.db 的缺失数据
核心问题：API队名和数据库队名不一致，需要模糊匹配
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

LEAGUE_STANDARD_MAP = {
    'Premier League': 'premier_league',
    'Championship': 'championship',
    'La Liga': 'la_liga',
    'LaLiga': 'la_liga',
    'Bundesliga': 'bundesliga',
    'Bundesliga 2': 'bundesliga_2',
    'Serie A': 'serie_a',
    'Ligue 1': 'ligue_1',
    'Ligue 2': 'ligue_2',
    'Eredivisie': 'eredivisie',
    'Primeira Liga': 'primeira_liga',
    'Segunda Division': 'segunda_division',
    'Scottish Premiership': 'scottish_premiership',
    'Jupiler Pro League': 'jupiler_pro_league',
    'MLS': 'mls',
    'Liga MX': 'liga_mx',
    'AFC Asian Cup': 'afc_asian_cup',
    'AFC World Cup Qualifiers': 'afc_wc_qualifiers',
    'CAF World Cup Qualifiers': 'caf_wc_qualifiers',
    'Concacaf World Cup Qualifiers': 'concacaf_wc_qualifiers',
    'UEFA World Cup Qualifiers': 'uefa_wc_qualifiers',
    'UEFA European Championship': 'euro',
    'UEFA Euro Qualifiers': 'euro_qualifiers',
    'UEFA Nations League': 'uefa_nations_league',
    'World Cup': 'world_cup',
    'Friendlies': 'friendlies',
    'Copa America': 'copa_america',
    'Gold Cup': 'gold_cup',
    'Africa Cup of Nations': 'africa_cup_of_nations',
    'Champions League': 'champions_league',
    'Europa League': 'europa_league',
    'Conference League': 'conference_league',
    'FA Cup': 'fa_cup',
    'EFL Cup': 'efl_cup',
    'K League 1': 'k_league_1',
    'K League 2': 'k_league_2',
    'J1 League': 'j1_league',
    'J2 League': 'j2_league',
}


def normalize_team_name(name):
    """简化队名用于匹配"""
    if not name:
        return ''
    n = name.lower().strip()
    # 移除常见后缀
    for suffix in [' fc', ' cf', ' sc', ' ac', ' afc', ' bfc', ' cfc',
                   ' ssc', ' as', ' ud', ' cd', ' rb', ' sv', ' vfl',
                   ' fc ', ' cf ', ' sc ', ' ac ', ' rb ']:
        n = n.replace(suffix, ' ')
    # 移除城市名前缀
    n = re.sub(r'\b(fc|cf|sc|ac|afc|ssc|as|ud|cd|rb|sv|vfl|1\.|1|fk|sk|ks|tsv|e\d+)\b', '', n)
    n = re.sub(r'\s+', ' ', n).strip()
    return n


def teams_match(name1, name2):
    """判断两个队名是否指向同一队伍"""
    if not name1 or not name2:
        return False
    n1 = normalize_team_name(name1)
    n2 = normalize_team_name(name2)
    if n1 == n2:
        return True
    # 一个包含另一个
    if n1 in n2 or n2 in n1:
        return True
    # 核心词匹配（取最长的词）
    words1 = set(n1.split())
    words2 = set(n2.split())
    common = words1 & words2
    if common and len(common) >= min(len(words1), len(words2), 1):
        # 至少有一个关键词匹配且不是太短的通用词
        skip_words = {'united', 'city', 'fc', 'cf', 'sc', 'ac', 'rb', 'as', 'ud', 'cd'}
        meaningful_common = common - skip_words
        if meaningful_common:
            return True
    return False


def fetch_api(url):
    try:
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=30) as response:
            return json.loads(response.read().decode('utf-8'))
    except:
        return None


def extract_season(date_str):
    if not date_str:
        return ''
    try:
        year = int(date_str[:4])
        month = int(date_str[5:7])
    except:
        return ''
    if month >= 8:
        return f"{year}-{year+1}"
    else:
        return f"{year-1}-{year}"


def step1_local_fixes(conn):
    """本地修复 season 和 league_standard（不需要API）"""
    cursor = conn.cursor()
    print("\n[Step 1] 本地修复 season 和 league_standard")

    # 修复league_standard
    cursor.execute('SELECT DISTINCT league FROM matches WHERE league_standard IS NULL OR league_standard = ""')
    leagues = cursor.fetchall()
    updated = 0
    for (league,) in leagues:
        std = LEAGUE_STANDARD_MAP.get(league, league.lower().replace(' ', '_').replace('-', '_') if league else '')
        if std:
            cursor.execute('UPDATE matches SET league_standard = ? WHERE league = ? AND (league_standard IS NULL OR league_standard = "")', (std, league))
            updated += cursor.rowcount
    conn.commit()
    print(f"  league_standard 修复: {updated} 条")

    # 修复season
    cursor.execute('SELECT match_key, date FROM matches WHERE season IS NULL OR season = ""')
    no_season = cursor.fetchall()
    updated = 0
    for mk, date in no_season:
        season = extract_season(date)
        if season:
            cursor.execute('UPDATE matches SET season = ? WHERE match_key = ?', (season, mk))
            updated += cursor.rowcount
    conn.commit()
    print(f"  season 修复: {updated} 条")


def step2_supplement_from_apifootball(conn):
    """从apifootball按日期获取比赛详情，模糊匹配队名"""
    cursor = conn.cursor()
    print("\n[Step 2] 从 API-Football 补充比赛详情（模糊匹配）")

    # 找出缺失字段最多的日期
    cursor.execute("""
        SELECT date,
               SUM(CASE WHEN time IS NULL OR time = '' THEN 1 ELSE 0 END) as no_time,
               SUM(CASE WHEN venue IS NULL OR venue = '' THEN 1 ELSE 0 END) as no_venue
        FROM matches
        WHERE (time IS NULL OR time = '')
           OR (venue IS NULL OR venue = '')
        GROUP BY date
        HAVING no_time > 0 OR no_venue > 0
        ORDER BY date DESC
    """)
    dates = cursor.fetchall()

    print(f"  需要补充的日期: {len(dates)} 天")

    total_updated = 0
    processed = 0

    for date, no_time, no_venue in dates:
        processed += 1
        url = f"{API_BASE}/?action=get_events&APIkey={API_KEY}&from={date}&to={date}"
        data = fetch_api(url)

        if not isinstance(data, list) or len(data) == 0:
            continue

        # 获取该日期的数据库比赛
        cursor.execute('SELECT match_key, home_team, away_team, time, venue, referee, home_score, away_score FROM matches WHERE date = ?', (date,))
        db_matches = cursor.fetchall()

        updated_this = 0

        for api_match in data:
            api_home = api_match.get('match_hometeam_name', '')
            api_away = api_match.get('match_awayteam_name', '')
            api_time = api_match.get('match_time', '')
            api_stadium = api_match.get('match_stadium', '')
            api_referee = api_match.get('match_referee', '')
            api_home_score = api_match.get('match_hometeam_score')
            api_away_score = api_match.get('match_awayteam_score')
            api_league = api_match.get('league_name', '')
            api_league_id = api_match.get('league_id')

            # 在数据库中模糊匹配
            for mk, db_home, db_away, db_time, db_venue, db_ref, db_hs, db_as in db_matches:
                if teams_match(api_home, db_home) and teams_match(api_away, db_away):
                    updates = {}

                    if (not db_time or db_time == '') and api_time and api_time != '-':
                        updates['time'] = api_time

                    if (not db_venue or db_venue == '') and api_stadium:
                        updates['venue'] = api_stadium

                    if (not db_ref or db_ref == '') and api_referee:
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
                        values = list(updates.values()) + [mk]
                        cursor.execute(f'UPDATE matches SET {set_clause} WHERE match_key = ?', values)
                        updated_this += cursor.rowcount
                    break  # 匹配到了就跳出

        if updated_this > 0:
            conn.commit()
            total_updated += updated_this

        if processed % 50 == 0:
            print(f"  进度: {processed}/{len(dates)}, 已更新: {total_updated}")

        time.sleep(0.8)

    conn.commit()
    print(f"  总更新: {total_updated} 条")


def step3_backfill_scores(conn):
    """补充缺失比分 - 对已结束但无比分的比赛尝试从API获取"""
    cursor = conn.cursor()
    print("\n[Step 3] 补充已结束比赛缺失比分")

    cursor.execute("""
        SELECT match_key, date, home_team, away_team, status
        FROM matches
        WHERE status = 'finished'
        AND (home_score IS NULL OR away_score IS NULL)
        ORDER BY date DESC
    """)
    no_score = cursor.fetchall()
    print(f"  缺失比分的已结束比赛: {len(no_score)} 场")

    updated = 0
    processed = 0

    for mk, date, home, away, status in no_score:
        processed += 1
        url = f"{API_BASE}/?action=get_events&APIkey={API_KEY}&from={date}&to={date}"
        data = fetch_api(url)

        if isinstance(data, list):
            for api_match in data:
                api_home = api_match.get('match_hometeam_name', '')
                api_away = api_match.get('match_awayteam_name', '')
                api_home_score = api_match.get('match_hometeam_score')
                api_away_score = api_match.get('match_awayteam_score')

                if teams_match(api_home, home) and teams_match(api_away, away):
                    updates = {}
                    if api_home_score and api_home_score not in ('', '-'):
                        try:
                            updates['home_score'] = int(api_home_score)
                        except:
                            pass
                    if api_away_score and api_away_score not in ('', '-'):
                        try:
                            updates['away_score'] = int(api_away_score)
                        except:
                            pass

                    if updates:
                        set_clause = ', '.join([f'[{k}] = ?' for k in updates])
                        values = list(updates.values()) + [mk]
                        cursor.execute(f'UPDATE matches SET {set_clause} WHERE match_key = ?', values)
                        updated += cursor.rowcount
                    break

        if processed % 20 == 0:
            conn.commit()
            print(f"  进度: {processed}/{len(no_score)}, 已更新: {updated}")

        time.sleep(0.8)

    conn.commit()
    print(f"  总更新: {updated} 条")


def step4_backfill_odds(conn):
    """补充赔率数据"""
    cursor = conn.cursor()
    print("\n[Step 4] 补充赔率数据")

    cursor.execute("""
        SELECT m.match_key, m.date, m.home_team, m.away_team
        FROM matches m
        WHERE m.status = 'scheduled' OR m.date >= '2025-01-01'
        ORDER BY m.date DESC
        LIMIT 200
    """)
    recent_matches = cursor.fetchall()

    print(f"  处理近期比赛: {len(recent_matches)} 场")

    added = 0
    for mk, date, home, away in recent_matches:
        # 检查是否已有odds
        cursor.execute('SELECT COUNT(*) FROM match_data WHERE match_key = ? AND data_type = "odds"', (mk,))
        if cursor.fetchone()[0] > 0:
            continue

        url = f"{API_BASE}/?action=get_odds&APIkey={API_KEY}&from={date}&to={date}"
        data = fetch_api(url)

        if isinstance(data, list):
            for odds_record in data:
                try:
                    odds_home_name = odds_record.get('match_hometeam_name', '')
                    odds_away_name = odds_record.get('match_awayteam_name', '')

                    if teams_match(odds_home_name, home) and teams_match(odds_away_name, away):
                        odds_1 = odds_record.get('odd_1', '')
                        odds_x = odds_record.get('odd_x', '')
                        odds_2 = odds_record.get('odd_2', '')
                        bookmaker = odds_record.get('odd_bookmakers', '')

                        if odds_1 and odds_x and odds_2:
                            odds_json = json.dumps({
                                'home': float(odds_1),
                                'draw': float(odds_x),
                                'away': float(odds_2),
                                'bookmaker': bookmaker
                            }, ensure_ascii=False)

                            cursor.execute("""
                                INSERT OR IGNORE INTO match_data
                                (match_key, source, data_type, data_json)
                                VALUES (?, 'apifootball', 'odds', ?)
                            """, (mk, odds_json))
                            added += cursor.rowcount
                            break
                except:
                    pass

        time.sleep(1)

    conn.commit()
    print(f"  新增odds: {added} 条")


def generate_report(conn):
    cursor = conn.cursor()
    print("\n" + "=" * 60)
    print("补充后数据统计")
    print("=" * 60)

    cursor.execute('SELECT COUNT(*) FROM matches')
    total = cursor.fetchone()[0]

    for f in ['time', 'venue', 'referee', 'league_standard', 'season', 'home_score', 'away_score']:
        cursor.execute(f'SELECT COUNT(*) FROM matches WHERE [{f}] IS NULL OR [{f}] = ""')
        missing = cursor.fetchone()[0]
        pct = missing * 100 / total
        tag = '[!]' if pct > 10 else '[OK]'
        print(f"  {tag} {f}: 缺失 {missing} ({pct:.1f}%)")

    cursor.execute("SELECT COUNT(DISTINCT match_key) FROM match_data WHERE data_type = 'odds'")
    odds_cnt = cursor.fetchone()[0]
    print(f"\n  odds覆盖: {odds_cnt}/{total} ({odds_cnt*100/total:.1f}%)")

    cursor.execute("SELECT COUNT(DISTINCT match_key) FROM match_data")
    md_cnt = cursor.fetchone()[0]
    print(f"  match_data覆盖: {md_cnt}/{total} ({md_cnt*100/total:.1f}%)")


def main():
    print("=" * 60)
    print(f"补充 unified_football.db 缺失数据")
    print(f"时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)

    conn = sqlite3.connect(DB_PATH, timeout=30.0)

    step1_local_fixes(conn)
    step2_supplement_from_apifootball(conn)
    step3_backfill_scores(conn)
    step4_backfill_odds(conn)
    generate_report(conn)

    conn.close()
    print("\n完成!")


if __name__ == '__main__':
    main()
