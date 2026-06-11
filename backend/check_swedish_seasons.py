import sqlite3
import sys
sys.stdout.reconfigure(encoding='utf-8')

conn = sqlite3.connect('data/football_v2.db')
conn.row_factory = sqlite3.Row
cursor = conn.cursor()

# 查看matches中的赛季分布
cursor.execute('''
    SELECT DISTINCT l.name_en, l.country, m.match_id
    FROM matches m
    LEFT JOIN leagues l ON m.league_id = l.league_id
    WHERE l.name_en LIKE '%Allsvenskan%' OR l.name_en LIKE '%Sweden%'
''')
rows = cursor.fetchall()

print('瑞典超比赛match_id示例:')
for row in rows[:20]:
    print(f'  {row["match_id"]}')

# 分析赛季命名
print('\n' + '=' * 80)

# 从match_id提取赛季
from collections import defaultdict
season_formats = defaultdict(list)

for row in rows:
    match_id = row['match_id']
    parts = match_id.split('_')
    if len(parts) >= 2:
        season_part = parts[1]
        season_formats[season_part].append(match_id)

print('\n瑞典超赛季格式统计:')
for season, examples in sorted(season_formats.items()):
    print(f'  {season}: {len(examples)}场比赛')
    if examples:
        print(f'    示例: {examples[0]}')

conn.close()