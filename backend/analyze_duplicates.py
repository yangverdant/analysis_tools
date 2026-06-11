import sqlite3
import sys
sys.stdout.reconfigure(encoding='utf-8')

conn = sqlite3.connect('data/football_v2.db')
conn.row_factory = sqlite3.Row
cursor = conn.cursor()

# 查找所有重复比赛
cursor.execute('''
    SELECT m.match_id, m.match_date, m.home_team_id, m.away_team_id,
           m.home_goals, m.away_goals, m.status, m.match_time, m.season_id,
           ht.name_en as home_team, at.name_en as away_team
    FROM matches m
    LEFT JOIN leagues l ON m.league_id = l.league_id
    LEFT JOIN teams ht ON m.home_team_id = ht.team_id
    LEFT JOIN teams at ON m.away_team_id = at.team_id
    WHERE l.name_en LIKE '%Allsvenskan%' OR l.name_cn LIKE '%瑞典%'
    ORDER BY m.match_date, m.home_team_id, m.away_team_id
''')
rows = cursor.fetchall()

from collections import defaultdict
match_key_counts = defaultdict(list)

for row in rows:
    key = f"{row['match_date']}_{row['home_team_id']}_{row['away_team_id']}"
    match_key_counts[key].append({
        'match_id': row['match_id'],
        'season_id': row['season_id'],
        'time': row['match_time'],
        'goals': f"{row['home_goals']}-{row['away_goals']}",
        'status': row['status'],
        'home_team': row['home_team'],
        'away_team': row['away_team']
    })

# 找出重复的
duplicates = {k: v for k, v in match_key_counts.items() if len(v) > 1}

print(f'发现重复比赛: {len(duplicates)} 组')
print('=' * 80)

# 分析重复原因
to_delete = []
for key, matches in duplicates.items():
    parts = key.split('_')
    date, home_id, away_id = parts[0], parts[1], parts[2]

    m1, m2 = matches[0], matches[1]

    print(f'\n日期: {date}')
    print(f'比赛: {m1["home_team"]} vs {m1["away_team"]}')

    for i, m in enumerate(matches, 1):
        print(f'  版本{i}: match_id={m["match_id"]}')
        print(f'         season_id={m["season_id"]}, time={m["time"]}, goals={m["goals"]}')

    # 决定删除哪个
    # 规则：保留时间更合理的版本
    time1 = m1['time'] or '00:00'
    time2 = m2['time'] or '00:00'

    def time_score(t):
        h = int(t.split(':')[0])
        if 14 <= h <= 21:
            return 10
        elif 13 <= h <= 22:
            return 8
        else:
            return 0

    score1 = time_score(time1)
    score2 = time_score(time2)

    if score1 >= score2:
        to_delete.append(m2['match_id'])
        print(f'  -> 建议删除版本2 (时间{time2}不如{time1}合理)')
    else:
        to_delete.append(m1['match_id'])
        print(f'  -> 建议删除版本1 (时间{time1}不如{time2}合理)')

print('\n' + '=' * 80)
print(f'总计建议删除: {len(to_delete)} 条记录')
print('\n要删除的match_id列表:')
for mid in to_delete:
    print(f'  "{mid}"')

# 生成SQL
print('\n' + '=' * 80)
print('删除SQL:')
print('DELETE FROM matches WHERE match_id IN (')
for i, mid in enumerate(to_delete):
    if i < len(to_delete) - 1:
        print(f'  "{mid}",')
    else:
        print(f'  "{mid}"')
print(');')

conn.close()