import pandas as pd

leagues = {
    'la_liga': 'd:/football_tools/new_data/matches/clubs/leagues/la_liga/la_liga_2025-2026.csv',
    'bundesliga': 'd:/football_tools/new_data/matches/clubs/leagues/bundesliga/bundesliga_2025-2026.csv',
    'serie_a': 'd:/football_tools/new_data/matches/clubs/leagues/serie_a/serie_a_2025-2026.csv',
    'ligue_1': 'd:/football_tools/new_data/matches/clubs/leagues/ligue_1/ligue_1_2025-2026.csv',
}

for key, path in leagues.items():
    df = pd.read_csv(path)
    print(f'{key}: {len(df)} rows')

    # 统一status
    df['status'] = df['status'].str.lower()

    # 按日期排序
    df = df.sort_values('match_date').reset_index(drop=True)

    # 用球队出现次数法补round_num
    team_count = {}
    for idx, row in df.iterrows():
        home = row['home_team']
        away = row['away_team']
        team_count[home] = team_count.get(home, 0) + 1
        team_count[away] = team_count.get(away, 0) + 1
        df.loc[idx, 'round_num'] = team_count[home]

    df.to_csv(path, index=False)

    # 验证
    teams = set(df['home_team'].unique()) | set(df['away_team'].unique())
    per_round = len(teams) // 2
    max_round = int(df['round_num'].max())

    wrong = []
    for r in range(1, max_round + 1):
        count = len(df[df['round_num'] == r])
        if count != per_round:
            wrong.append(f'R{r}:{count}')

    print(f'  teams: {len(teams)}, per_round: {per_round}, max_round: {max_round}')
    if wrong:
        print(f'  wrong rounds: {wrong}')
    else:
        print(f'  all rounds OK')
    print()
