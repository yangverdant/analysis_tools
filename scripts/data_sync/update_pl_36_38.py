import pandas as pd

filepath = 'd:/football_tools/new_data/matches/clubs/leagues/premier_league/premier_league_2025-2026.csv'
df = pd.read_csv(filepath)

# 用户提供的第36-38轮数据（北京时间，需转换为英国当地时间）
# 5月英国夏令时UTC+1，北京时间减7小时
updates = [
    # 第36轮
    {'home': 'Liverpool', 'away': 'Bournemouth', 'date': '2026-05-09', 'time': '12:30', 'hg': 4, 'ag': 2, 'result': 'H', 'status': 'finished'},
    {'home': 'Aston Villa', 'away': 'Newcastle', 'date': '2026-05-09', 'time': '12:30', 'hg': 0, 'ag': 0, 'result': 'D', 'status': 'finished'},
    {'home': 'Brighton', 'away': 'Wolves', 'date': '2026-05-09', 'time': '15:00', 'hg': 3, 'ag': 0, 'result': 'H', 'status': 'finished'},
    {'home': 'Sunderland', 'away': 'West Ham', 'date': '2026-05-09', 'time': '15:00', 'hg': 3, 'ag': 0, 'result': 'H', 'status': 'finished'},
    {'home': 'Tottenham', 'away': 'Burnley', 'date': '2026-05-09', 'time': '15:00', 'hg': 3, 'ag': 0, 'result': 'H', 'status': 'finished'},
    {'home': 'Wolves', 'away': 'Man City', 'date': '2026-05-09', 'time': '17:30', 'hg': 0, 'ag': 4, 'result': 'A', 'status': 'finished'},
    {'home': "Nott'm Forest", 'away': 'Brentford', 'date': '2026-05-10', 'time': '14:00', 'hg': 3, 'ag': 1, 'result': 'H', 'status': 'finished'},
    {'home': 'Chelsea', 'away': 'Crystal Palace', 'date': '2026-05-10', 'time': '14:00', 'hg': 0, 'ag': 0, 'result': 'D', 'status': 'finished'},
    {'home': 'Man United', 'away': 'Arsenal', 'date': '2026-05-10', 'time': '16:30', 'hg': 0, 'ag': 1, 'result': 'A', 'status': 'finished'},
    {'home': 'Leeds', 'away': 'Everton', 'date': '2026-05-11', 'time': '20:00', 'hg': 1, 'ag': 0, 'result': 'H', 'status': 'finished'},
    # 第37轮
    {'home': 'Aston Villa', 'away': 'Liverpool', 'date': '2026-05-15', 'time': '20:00', 'hg': 4, 'ag': 2, 'result': 'H', 'status': 'finished'},
    {'home': 'Man United', 'away': "Nott'm Forest", 'date': '2026-05-17', 'time': '12:30', 'hg': 3, 'ag': 2, 'result': 'H', 'status': 'finished'},
    {'home': 'Brentford', 'away': 'Crystal Palace', 'date': '2026-05-17', 'time': '15:00', 'hg': 2, 'ag': 2, 'result': 'D', 'status': 'finished'},
    {'home': 'Everton', 'away': 'Sunderland', 'date': '2026-05-17', 'time': '15:00', 'hg': 1, 'ag': 3, 'result': 'A', 'status': 'finished'},
    {'home': 'Leeds', 'away': 'Brighton', 'date': '2026-05-17', 'time': '15:00', 'hg': 1, 'ag': 0, 'result': 'H', 'status': 'finished'},
    {'home': 'Wolves', 'away': 'Fulham', 'date': '2026-05-17', 'time': '15:00', 'hg': 1, 'ag': 1, 'result': 'D', 'status': 'finished'},
    {'home': 'Newcastle', 'away': 'West Ham', 'date': '2026-05-17', 'time': '17:30', 'hg': 3, 'ag': 1, 'result': 'H', 'status': 'finished'},
    {'home': 'Arsenal', 'away': 'Burnley', 'date': '2026-05-18', 'time': '20:00', 'hg': 1, 'ag': 0, 'result': 'H', 'status': 'finished'},
    {'home': 'Bournemouth', 'away': 'Man City', 'date': '2026-05-19', 'time': '19:30', 'hg': None, 'ag': None, 'result': None, 'status': 'scheduled'},
    {'home': 'Chelsea', 'away': 'Tottenham', 'date': '2026-05-19', 'time': '20:15', 'hg': None, 'ag': None, 'result': None, 'status': 'scheduled'},
    # 第38轮
    {'home': 'Brighton', 'away': 'Man United', 'date': '2026-05-24', 'time': '16:00', 'hg': None, 'ag': None, 'result': None, 'status': 'scheduled'},
    {'home': 'Burnley', 'away': 'Wolves', 'date': '2026-05-24', 'time': '16:00', 'hg': None, 'ag': None, 'result': None, 'status': 'scheduled'},
    {'home': 'Crystal Palace', 'away': 'Arsenal', 'date': '2026-05-24', 'time': '16:00', 'hg': None, 'ag': None, 'result': None, 'status': 'scheduled'},
    {'home': 'Fulham', 'away': 'Newcastle', 'date': '2026-05-24', 'time': '16:00', 'hg': None, 'ag': None, 'result': None, 'status': 'scheduled'},
    {'home': 'Liverpool', 'away': 'Brentford', 'date': '2026-05-24', 'time': '16:00', 'hg': None, 'ag': None, 'result': None, 'status': 'scheduled'},
    {'home': 'Man City', 'away': 'Aston Villa', 'date': '2026-05-24', 'time': '16:00', 'hg': None, 'ag': None, 'result': None, 'status': 'scheduled'},
    {'home': "Nott'm Forest", 'away': 'Bournemouth', 'date': '2026-05-24', 'time': '16:00', 'hg': None, 'ag': None, 'result': None, 'status': 'scheduled'},
    {'home': 'Sunderland', 'away': 'Chelsea', 'date': '2026-05-24', 'time': '16:00', 'hg': None, 'ag': None, 'result': None, 'status': 'scheduled'},
    {'home': 'Tottenham', 'away': 'Everton', 'date': '2026-05-24', 'time': '16:00', 'hg': None, 'ag': None, 'result': None, 'status': 'scheduled'},
    {'home': 'West Ham', 'away': 'Leeds', 'date': '2026-05-24', 'time': '16:00', 'hg': None, 'ag': None, 'result': None, 'status': 'scheduled'},
]

updated = 0
not_found = 0

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
        updated += 1
    else:
        not_found += 1
        print(f"未找到: {u['home']} vs {u['away']}")

df.to_csv(filepath, index=False)
print(f'\n更新: {updated} 条, 未找到: {not_found} 条')
