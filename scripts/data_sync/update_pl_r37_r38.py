import pandas as pd

filepath = 'd:/football_tools/new_data/matches/clubs/leagues/premier_league/premier_league_2025-2026.csv'
df = pd.read_csv(filepath)

# 球队名称映射
team_map = {
    '维拉': 'Aston Villa', '利物浦': 'Liverpool', '曼联': 'Man United',
    '诺丁汉森林': "Nott'm Forest", '布伦特': 'Brentford', '水晶宫': 'Crystal Palace',
    '埃弗顿': 'Everton', '桑德兰': 'Sunderland', '利兹联': 'Leeds',
    '布莱顿': 'Brighton', '狼队': 'Wolves', '富勒姆': 'Fulham',
    '纽卡斯尔': 'Newcastle', '西汉姆': 'West Ham', '阿森纳': 'Arsenal',
    '伯恩利': 'Burnley', '伯恩茅斯': 'Bournemouth', '曼城': 'Man City',
    '切尔西': 'Chelsea', '热刺': 'Tottenham',
}

# 北京时间转英国当地时间（5月夏令时，减7小时）
updates = [
    # R37 已结束
    {'home': 'Aston Villa', 'away': 'Liverpool', 'date': '2026-05-15', 'time': '20:00', 'hg': 4, 'ag': 2, 'result': 'H', 'status': 'finished'},
    {'home': 'Man United', 'away': "Nott'm Forest", 'date': '2026-05-17', 'time': '12:30', 'hg': 3, 'ag': 2, 'result': 'H', 'status': 'finished'},
    {'home': 'Brentford', 'away': 'Crystal Palace', 'date': '2026-05-17', 'time': '15:00', 'hg': 2, 'ag': 2, 'result': 'D', 'status': 'finished'},
    {'home': 'Everton', 'away': 'Sunderland', 'date': '2026-05-17', 'time': '15:00', 'hg': 1, 'ag': 3, 'result': 'A', 'status': 'finished'},
    {'home': 'Leeds', 'away': 'Brighton', 'date': '2026-05-17', 'time': '15:00', 'hg': 1, 'ag': 0, 'result': 'H', 'status': 'finished'},
    {'home': 'Wolves', 'away': 'Fulham', 'date': '2026-05-17', 'time': '15:00', 'hg': 1, 'ag': 1, 'result': 'D', 'status': 'finished'},
    {'home': 'Newcastle', 'away': 'West Ham', 'date': '2026-05-17', 'time': '17:30', 'hg': 3, 'ag': 1, 'result': 'H', 'status': 'finished'},
    {'home': 'Arsenal', 'away': 'Burnley', 'date': '2026-05-18', 'time': '20:00', 'hg': 1, 'ag': 0, 'result': 'H', 'status': 'finished'},
    # R37 未开赛
    {'home': 'Bournemouth', 'away': 'Man City', 'date': '2026-05-19', 'time': '19:30', 'hg': None, 'ag': None, 'result': None, 'status': 'scheduled'},
    {'home': 'Chelsea', 'away': 'Tottenham', 'date': '2026-05-19', 'time': '20:15', 'hg': None, 'ag': None, 'result': None, 'status': 'scheduled'},
    # R38 未开赛
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
added = 0

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
        df.loc[idx, 'round_num'] = 37 if u['date'] <= '2026-05-19' else 38
        updated += 1
    else:
        new_row = {
            'season': '2025-2026',
            'match_date': u['date'],
            'match_time': u['time'],
            'round_num': 37 if u['date'] <= '2026-05-19' else 38,
            'division': 'premier_league',
            'home_team': u['home'],
            'away_team': u['away'],
            'home_goals': u['hg'],
            'away_goals': u['ag'],
            'result': u['result'],
            'status': u['status'],
        }
        df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
        added += 1

df.to_csv(filepath, index=False)
print(f'更新: {updated}, 新增: {added}, 总计: {len(df)}')
