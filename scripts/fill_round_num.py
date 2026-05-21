import pandas as pd

filepath = 'd:/football_tools/new_data/matches/clubs/leagues/premier_league/premier_league_2025-2026.csv'
df = pd.read_csv(filepath)

print(f'总场次: {len(df)}')
print(f'round_num空值: {df["round_num"].isna().sum()}')

# 按日期排序
df = df.sort_values('match_date').reset_index(drop=True)

# 每10场为一轮
for i in range(38):
    start = i * 10
    end = start + 10
    df.loc[start:end-1, 'round_num'] = i + 1

# 验证
print('\n各轮场次:')
all_ok = True
for r in range(1, 39):
    count = len(df[df['round_num'] == r])
    if count != 10:
        print(f'  R{r}: {count}场')
        all_ok = False
if all_ok:
    print('  每轮10场 OK')

print(f'\nround_num空值: {df["round_num"].isna().sum()}')

# 保存
df.to_csv(filepath, index=False)
print('已保存')

# 显示每轮首场日期
print('\n每轮首场:')
for r in range(1, 39):
    round_df = df[df['round_num'] == r]
    first = round_df.iloc[0]
    print(f"  R{r}: {first['match_date']} {first['home_team']} vs {first['away_team']}")
