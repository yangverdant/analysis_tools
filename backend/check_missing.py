import sqlite3
conn = sqlite3.connect('data/football_v2.db')
conn.row_factory = sqlite3.Row
cursor = conn.cursor()

cursor.execute('''
    SELECT m.match_id, m.match_date, m.status,
           ht.name_en as home_team, at.name_en as away_team,
           l.name_en as league
    FROM matches m
    LEFT JOIN teams ht ON m.home_team_id = ht.team_id
    LEFT JOIN teams at ON m.away_team_id = at.team_id
    LEFT JOIN leagues l ON m.league_id = l.league_id
    WHERE m.status = 'finished'
    AND (m.home_goals IS NULL OR m.away_goals IS NULL)
    ORDER BY m.match_date DESC
    LIMIT 10
''')
rows = cursor.fetchall()

print('缺失比分的已结束比赛:')
for row in rows:
    print(f'  {row["match_date"]} | {row["league"]} | {row["home_team"]} vs {row["away_team"]}')

conn.close()
