import pandas as pd

filepath = 'd:/football_tools/new_data/matches/clubs/leagues/premier_league/premier_league_2025-2026.csv'
df = pd.read_csv(filepath)

# 先按日期排序
df = df.sort_values('match_date').reset_index(drop=True)

# 记录每支球队出现次数
team_count = {}

for idx, row in df.iterrows():
    home = row['home_team']
    away = row['away_team']

    team_count[home] = team_count.get(home, 0) + 1
    team_count[away] = team_count.get(away, 0) + 1

    round_num = team_count[home]
    df.loc[idx, 'round_num'] = round_num

df.to_csv(filepath, index=False)

# 验证
print(f'总场次: {len(df)}')
all_ok = True
for r in range(1, 39):
    count = len(df[df['round_num'] == r])
    if count != 10:
        print(f'R{r}: {count}场')
        all_ok = False
if all_ok:
    print('每轮10场 OK')

print(f'球队数: {len(set(df["home_team"]) | set(df["away_team"]))}')

# 抽查几轮
for r in [1, 10, 36, 37, 38]:
    print(f'\nR{r}:')
    for _, row in df[df['round_num'] == r].iterrows():
        hg = int(row['home_goals']) if pd.notna(row['home_goals']) else ''
        ag = int(row['away_goals']) if pd.notna(row['away_goals']) else ''
        score = f'{hg}-{ag}' if hg != '' else 'vs'
        print(f"  {row['match_date']} {row['home_team']} {score} {row['away_team']}")