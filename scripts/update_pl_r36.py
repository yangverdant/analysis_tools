import pandas as pd

filepath = 'd:/football_tools/new_data/matches/clubs/leagues/premier_league/premier_league_2025-2026.csv'
df = pd.read_csv(filepath)

# R36数据（北京时间转英国当地时间，5月减7小时）
updates = [
    {'home': 'Liverpool', 'away': 'Chelsea', 'date': '2026-05-09', 'time': '12:30', 'hg': 1, 'ag': 1, 'result': 'D', 'status': 'finished'},
    {'home': 'Brighton', 'away': 'Wolves', 'date': '2026-05-09', 'time': '15:00', 'hg': 3, 'ag': 0, 'result': 'H', 'status': 'finished'},
    {'home': 'Fulham', 'away': 'Bournemouth', 'date': '2026-05-09', 'time': '15:00', 'hg': 0, 'ag': 1, 'result': 'A', 'status': 'finished'},
    {'home': 'Sunderland', 'away': 'Man United', 'date': '2026-05-09', 'time': '15:00', 'hg': 0, 'ag': 0, 'result': 'D', 'status': 'finished'},
    {'home': 'Man City', 'away': 'Brentford', 'date': '2026-05-09', 'time': '17:30', 'hg': 3, 'ag': 0, 'result': 'H', 'status': 'finished'},
    {'home': 'Burnley', 'away': 'Aston Villa', 'date': '2026-05-10', 'time': '14:00', 'hg': 2, 'ag': 2, 'result': 'D', 'status': 'finished'},
    {'home': 'Crystal Palace', 'away': 'Everton', 'date': '2026-05-10', 'time': '14:00', 'hg': 2, 'ag': 2, 'result': 'D', 'status': 'finished'},
    {'home': "Nott'm Forest", 'away': 'Newcastle', 'date': '2026-05-10', 'time': '14:00', 'hg': 1, 'ag': 1, 'result': 'D', 'status': 'finished'},
    {'home': 'West Ham', 'away': 'Arsenal', 'date': '2026-05-10', 'time': '16:30', 'hg': 0, 'ag': 1, 'result': 'A', 'status': 'finished'},
    {'home': 'Tottenham', 'away': 'Leeds', 'date': '2026-05-11', 'time': '20:00', 'hg': 1, 'ag': 1, 'result': 'D', 'status': 'finished'},
]

for u in updates:
    mask = (df['home_team'] == u['home']) & (df['away_team'] == u['away'])
    if mask.any():
        idx = df[mask].index[0]
        df.loc[idx, 'match_date'] = u['date']
        df.loc[idx, 'match_time'] = u['time']
        df.loc[idx, 'home_goals'] = u['hg']
        df.loc[idx, 'away_goals'] = u['ag']
        df.loc[idx, 'result'] = u['result']
        df.loc[idx, 'status'] = u['status']
        df.loc[idx, 'round_num'] = 36

df.to_csv(filepath, index=False)

# 验证
r36 = df[df['round_num'] == 36]
print(f'R36: {len(r36)}场')
for _, row in r36.iterrows():
    hg = int(row['home_goals']) if pd.notna(row['home_goals']) else ''
    ag = int(row['away_goals']) if pd.notna(row['away_goals']) else ''
    score = f'{hg}-{ag}' if hg != '' else 'vs'
    print(f"  {row['match_date']} {row['match_time']} {row['home_team']} {score} {row['away_team']} {row['status']}")
