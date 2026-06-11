"""
Generate comprehensive data completeness report
"""
import sqlite3

DB_PATH = 'd:/football_tools/data/football_v2.db'

def generate_report():
    conn = sqlite3.connect(DB_PATH, timeout=60)
    cursor = conn.cursor()

    print('=' * 80)
    print('数据库完整性报告 - 2026-05-23')
    print('=' * 80)

    # Overall statistics
    cursor.execute('SELECT COUNT(*) FROM matches')
    total_matches = cursor.fetchone()[0]

    cursor.execute('SELECT COUNT(*) FROM matches WHERE home_goals IS NOT NULL')
    with_goals = cursor.fetchone()[0]

    cursor.execute('SELECT COUNT(*) FROM matches WHERE home_xg IS NOT NULL')
    with_xg = cursor.fetchone()[0]

    cursor.execute('SELECT COUNT(*) FROM matches WHERE odds_home IS NOT NULL')
    with_odds = cursor.fetchone()[0]

    cursor.execute('SELECT COUNT(*) FROM matches WHERE home_shots IS NOT NULL')
    with_shots = cursor.fetchone()[0]

    print('\\n【比赛数据】')
    print(f'总比赛数: {total_matches:,}')
    print(f'比分覆盖率: {with_goals:,} ({round(with_goals/total_matches*100, 1)}%)')
    print(f'xG覆盖率: {with_xg:,} ({round(with_xg/total_matches*100, 1)}%)')
    print(f'赔率覆盖率: {with_odds:,} ({round(with_odds/total_matches*100, 1)}%)')
    print(f'射门覆盖率: {with_shots:,} ({round(with_shots/total_matches*100, 1)}%)')

    # Teams
    cursor.execute('SELECT COUNT(*) FROM teams')
    total_teams = cursor.fetchone()[0]

    cursor.execute('SELECT COUNT(*) FROM teams WHERE stadium IS NOT NULL')
    with_stadium = cursor.fetchone()[0]

    cursor.execute('SELECT COUNT(*) FROM teams WHERE stadium_capacity IS NOT NULL')
    with_capacity = cursor.fetchone()[0]

    cursor.execute('SELECT COUNT(*) FROM teams WHERE name_cn IS NOT NULL AND name_cn != ""')
    with_cn_name = cursor.fetchone()[0]

    print('\\n【球队数据】')
    print(f'总球队数: {total_teams:,}')
    print(f'球场信息: {with_stadium:,} ({round(with_stadium/total_teams*100, 1)}%)')
    print(f'球场容量: {with_capacity:,} ({round(with_capacity/total_teams*100, 1)}%)')
    print(f'中文名: {with_cn_name:,} ({round(with_cn_name/total_teams*100, 1)}%)')

    # Players
    cursor.execute('SELECT COUNT(*) FROM players')
    total_players = cursor.fetchone()[0]

    print('\\n【球员数据】')
    print(f'总球员数: {total_players:,}')

    # Standings
    cursor.execute('SELECT COUNT(*) FROM standings')
    standings = cursor.fetchone()[0]

    print('\\n【积分榜】')
    print(f'积分榜记录: {standings:,}')

    # League rules
    cursor.execute('SELECT COUNT(DISTINCT league_id) FROM league_rules')
    leagues_with_rules = cursor.fetchone()[0]

    cursor.execute('SELECT COUNT(*) FROM leagues')
    total_leagues = cursor.fetchone()[0]

    print('\\n【联赛规则】')
    print(f'有规则的联赛: {leagues_with_rules}/{total_leagues} ({round(leagues_with_rules/total_leagues*100, 1)}%)')

    # Top leagues coverage
    print('\\n【主要联赛数据覆盖率】')
    cursor.execute('''
        SELECT l.name_en, COUNT(m.match_id) as total,
               SUM(CASE WHEN m.home_xg IS NOT NULL THEN 1 ELSE 0 END) as xg,
               SUM(CASE WHEN m.odds_home IS NOT NULL THEN 1 ELSE 0 END) as odds,
               SUM(CASE WHEN m.home_shots IS NOT NULL THEN 1 ELSE 0 END) as shots
        FROM leagues l
        JOIN matches m ON m.league_id = l.league_id
        GROUP BY l.league_id
        ORDER BY total DESC
        LIMIT 15
    ''')

    for row in cursor.fetchall():
        name, total, xg, odds, shots = row
        xg_pct = round(xg/total*100, 1) if total > 0 else 0
        odds_pct = round(odds/total*100, 1) if total > 0 else 0
        shots_pct = round(shots/total*100, 1) if total > 0 else 0
        print(f'  {name}: {total:,}场 | xG:{xg_pct}% | odds:{odds_pct}% | shots:{shots_pct}%')

    conn.close()

if __name__ == '__main__':
    generate_report()