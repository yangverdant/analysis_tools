"""验证国家队数据导入结果"""
import sqlite3

conn = sqlite3.connect('d:/football_tools/data/football_v2.db')
cursor = conn.cursor()

# Count international matches
cursor.execute("SELECT COUNT(*) FROM matches WHERE match_id LIKE 'intl_%'")
intl_matches = cursor.fetchone()[0]

# Count national teams
cursor.execute("SELECT COUNT(*) FROM teams WHERE team_type = 'national'")
national_teams = cursor.fetchone()[0]

# Count matches by competition
cursor.execute('''
    SELECT l.name_cn, COUNT(m.match_id) as matches
    FROM matches m
    JOIN leagues l ON m.league_id = l.league_id
    WHERE m.match_id LIKE 'intl_%'
    GROUP BY l.league_id
    ORDER BY matches DESC
    LIMIT 15
''')
by_competition = cursor.fetchall()

print(f'国家队比赛总数: {intl_matches}')
print(f'国家队数量: {national_teams}')
print()
print('按赛事统计:')
for name, count in by_competition:
    print(f'  {name}: {count} 场')

conn.close()
