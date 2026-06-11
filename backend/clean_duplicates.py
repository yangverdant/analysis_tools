import sqlite3
import sys
sys.stdout.reconfigure(encoding='utf-8')

conn = sqlite3.connect('data/football_v2.db')
conn.row_factory = sqlite3.Row
cursor = conn.cursor()

# 查找所有重复比赛
cursor.execute('''
    SELECT m.match_id, m.match_date, m.home_team_id, m.away_team_id,
           m.home_goals, m.away_goals, m.status, m.match_time, m.season_id
    FROM matches m
    LEFT JOIN leagues l ON m.league_id = l.league_id
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
        'status': row['status']
    })

# 找出重复的
duplicates = {k: v for k, v in match_key_counts.items() if len(v) > 1}

print(f'发现重复比赛: {len(duplicates)} 组')

# 决定保留哪个版本
# 规则：保留 match_time 更合理的版本（瑞典当地时间通常是下午）
# 或者保留 season_id 更合理的版本

to_delete = []
for key, matches in duplicates.items():
    # 检查时间差异
    # 保留时间更合理的版本（瑞典当地时间 14:00-21:00 是合理的）
    # 删除时间异常的版本

    # 比较两个版本
    m1, m2 = matches[0], matches[1]

    # 如果时间相同，保留第一个
    if m1['time'] == m2['time']:
        # 保留 season_id 更小的（更早的赛季）
        if m1['season_id'] <= m2['season_id']:
            to_delete.append(m2['match_id'])
        else:
            to_delete.append(m1['match_id'])
    else:
        # 时间不同，保留时间更合理的
        # 瑞典比赛通常在下午（14:00-21:00当地时间）
        # 21:00可能是UTC时间转换后的

        # 简单规则：保留时间更晚的（可能是正确的当地时间）
        # 或者保留时间在14:00-22:00范围内的

        time1 = m1['time'] or '00:00'
        time2 = m2['time'] or '00:00'

        # 检查哪个时间更合理
        def time_score(t):
            h = int(t.split(':')[0])
            # 瑞典比赛通常在14:00-21:00
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
        else:
            to_delete.append(m1['match_id'])

print(f'建议删除: {len(to_delete)} 条记录')

# 显示要删除的match_id
print('\n要删除的match_id:')
for mid in to_delete[:20]:
    print(f'  {mid}')

# 执行删除
if to_delete:
    print(f'\n确认删除 {len(to_delete)} 条重复记录?')
    confirm = input('输入 YES 确认删除: ')

    if confirm == 'YES':
        for mid in to_delete:
            cursor.execute("DELETE FROM matches WHERE match_id = ?", (mid,))
        conn.commit()
        print(f'已删除 {len(to_delete)} 条记录')
    else:
        print('取消删除')

conn.close()