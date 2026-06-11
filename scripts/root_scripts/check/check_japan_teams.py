import sqlite3
conn = sqlite3.connect('data/football_v2.db')
cursor = conn.cursor()

# 查找清水鼓动和大阪钢巴
cursor.execute("SELECT team_id, name FROM teams WHERE name LIKE '%Shimizu%' OR name LIKE '%Gamba%' OR name LIKE '%Osaka%'")
print('=== 球队 ===')
for row in cursor.fetchall():
    print(row)

# 查找日本联赛
cursor.execute("SELECT league_id, name FROM leagues WHERE name LIKE '%Japan%' OR name LIKE '%J-League%' OR name LIKE '%J1%'")
print('\n=== 联赛 ===')
for row in cursor.fetchall():
    print(row)

# 查看这两个球队的比赛数据量
cursor.execute("SELECT team_id, name FROM teams WHERE team_id IN (821, 374)")
print('\n=== 目标球队 ===')
for row in cursor.fetchall():
    print(row)

conn.close()
