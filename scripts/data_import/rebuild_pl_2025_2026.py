import pandas as pd

# 1. 从原始数据恢复
src = 'd:/football_tools/data/01_europe_leagues/premier_league/premier_league_2025-2026.csv'
dst = 'd:/football_tools/new_data/matches/clubs/leagues/premier_league/premier_league_2025-2026.csv'
df = pd.read_csv(src)

print(f'原始数据: {len(df)} 行')

# 2. 标准化字段名
field_mapping = {
    'Div': 'division', 'Date': 'match_date', 'Time': 'match_time',
    'HomeTeam': 'home_team', 'AwayTeam': 'away_team',
    'FTHG': 'home_goals', 'FTAG': 'away_goals', 'FTR': 'result',
    'HTHG': 'home_goals_ht', 'HTAG': 'away_goals_ht', 'HTR': 'result_ht',
    'HS': 'home_shots', 'AS': 'away_shots',
    'HST': 'home_shots_target', 'AST': 'away_shots_target',
    'HF': 'home_fouls', 'AF': 'away_fouls',
    'HC': 'home_corners', 'AC': 'away_corners',
    'HY': 'home_yellow', 'AY': 'away_yellow',
    'HR': 'home_red', 'AR': 'away_red',
    'Referee': 'referee', 'Attendance': 'attendance',
    'Status': 'status'
}
cols_to_rename = {k: v for k, v in field_mapping.items() if k in df.columns}
df = df.rename(columns=cols_to_rename)

# 3. 添加season列
df['season'] = '2025-2026'

# 4. 统一球队名称
team_name_fix = {
    'Nottm Forest': "Nott'm Forest",
}
df['home_team'] = df['home_team'].replace(team_name_fix)
df['away_team'] = df['away_team'].replace(team_name_fix)

# 5. 删除错误球队（Leicester, Southampton不属于2025-2026英超）
correct_teams = set([
    'Arsenal', 'Aston Villa', 'Bournemouth', 'Brentford', 'Brighton',
    'Burnley', 'Chelsea', 'Crystal Palace', 'Everton', 'Fulham',
    'Leeds', 'Liverpool', 'Man City', 'Man United', 'Newcastle',
    "Nott'm Forest", 'Sunderland', 'Tottenham', 'West Ham', 'Wolves',
    'Ipswich',  # 可能有Ipswich的数据
])
wrong_teams = (set(df['home_team'].unique()) | set(df['away_team'].unique())) - correct_teams
if wrong_teams:
    print(f'删除错误球队: {sorted(wrong_teams)}')
    df = df[~(df['home_team'].isin(wrong_teams) | df['away_team'].isin(wrong_teams))]

# 6. 去重
df['match_key'] = df['home_team'] + '_' + df['away_team']
before = len(df)
df = df.drop_duplicates(subset='match_key', keep='first')
df = df.drop(columns=['match_key'])
print(f'去重: {before} -> {len(df)}')

# 7. 按日期排序
df = df.sort_values('match_date').reset_index(drop=True)

# 8. 用球队出现次数法补round_num
team_count = {}
for idx, row in df.iterrows():
    home = row['home_team']
    away = row['away_team']
    team_count[home] = team_count.get(home, 0) + 1
    team_count[away] = team_count.get(away, 0) + 1
    df.loc[idx, 'round_num'] = team_count[home]

# 9. 统一status字段
df['status'] = df['status'].str.lower()

# 10. 标准化列顺序
standard_cols = ['season', 'match_date', 'match_time', 'round_num', 'division',
                 'home_team', 'away_team', 'home_goals', 'away_goals', 'result', 'status',
                 'home_goals_ht', 'away_goals_ht', 'result_ht',
                 'home_shots', 'away_shots', 'home_shots_target', 'away_shots_target',
                 'home_corners', 'away_corners', 'home_fouls', 'away_fouls',
                 'home_yellow', 'away_yellow', 'home_red', 'away_red',
                 'referee', 'attendance']
other_cols = [c for c in df.columns if c not in standard_cols]
df = df[standard_cols + other_cols]

# 11. 保存
df.to_csv(dst, index=False)

# 12. 验证
print(f'\n最终数据: {len(df)} 行')
print(f'球队数: {len(set(df["home_team"]) | set(df["away_team"]))}')
print(f'已完成: {len(df[df["status"] == "finished"])}')
print(f'未开赛: {len(df[df["status"] == "scheduled"])}')

all_ok = True
for r in range(1, 39):
    count = len(df[df['round_num'] == r])
    if count != 10:
        print(f'R{r}: {count}场 (应为10)')
        all_ok = False
if all_ok:
    print('每轮10场 OK')

# 显示R1和R38
for r in [1, 38]:
    print(f'\nR{r}:')
    for _, row in df[df['round_num'] == r].iterrows():
        hg = int(row['home_goals']) if pd.notna(row['home_goals']) else ''
        ag = int(row['away_goals']) if pd.notna(row['away_goals']) else ''
        score = f'{hg}-{ag}' if hg != '' else 'vs'
        print(f"  {row['match_date']} {row['home_team']} {score} {row['away_team']}")