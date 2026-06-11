import sqlite3
import sys
sys.stdout.reconfigure(encoding='utf-8')

conn = sqlite3.connect('data/football_v2.db')
conn.row_factory = sqlite3.Row
cursor = conn.cursor()

# 先查看matches表结构
cursor.execute("PRAGMA table_info(matches)")
columns = [col[1] for col in cursor.fetchall()]
print('matches表字段:', columns)

# 查找瑞典超的比赛
cursor.execute('''
    SELECT m.match_id, m.match_date, m.match_time, m.home_team_id, m.away_team_id,
           m.home_goals, m.away_goals, m.status, m.league_id, l.name_en as league_name
    FROM matches m
    LEFT JOIN leagues l ON m.league_id = l.league_id
    WHERE l.name_en LIKE '%Allsvenskan%' OR l.name_cn LIKE '%瑞典%'
    ORDER BY m.match_date, m.home_team_id
''')
rows = cursor.fetchall()

print(f'\n瑞典超比赛总数: {len(rows)}')

if len(rows) == 0:
    print('没有找到瑞典超比赛，检查所有联赛...')
    cursor.execute("SELECT DISTINCT league_id, name_en, name_cn FROM leagues WHERE name_en LIKE '%Allsvenskan%' OR name_cn LIKE '%瑞典%' OR name_en LIKE '%Sweden%'")
    leagues = cursor.fetchall()
    print('瑞典相关联赛:', [dict(l) for l in leagues])

# 检查重复比赛（相同日期+相同球队ID）
from collections import defaultdict
match_key_counts = defaultdict(list)

for row in rows:
    key = f"{row['match_date']}_{row['home_team_id']}_{row['away_team_id']}"
    match_key_counts[key].append({
        'match_id': row['match_id'],
        'time': row['match_time'],
        'goals': f"{row['home_goals']}-{row['away_goals']}",
        'status': row['status']
    })

# 找出重复的
duplicates = {k: v for k, v in match_key_counts.items() if len(v) > 1}

if duplicates:
    print(f'\n发现重复比赛: {len(duplicates)} 组')
    for key, matches in list(duplicates.items())[:10]:  # 只显示前10组
        parts = key.split('_')
        print(f'\n  日期: {parts[0]}, home_team_id: {parts[1]}, away_team_id: {parts[2]}')
        for m in matches:
            print(f'    - match_id: {m["match_id"]}, time: {m["time"]}, goals: {m["goals"]}, status: {m["status"]}')
else:
    print('\n没有发现重复比赛')

conn.close()