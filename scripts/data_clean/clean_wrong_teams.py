import pandas as pd
import os

# 定义每个联赛的正确球队（2025-2026赛季）
correct_teams = {
    'premier_league': [
        'Arsenal', 'Aston Villa', 'Bournemouth', 'Brentford', 'Brighton',
        'Chelsea', 'Crystal Palace', 'Everton', 'Fulham', 'Liverpool',
        'Man City', 'Man United', 'Newcastle', 'Nott\'m Forest', 'Tottenham',
        'West Ham', 'Wolves', 'Ipswich', 'Leicester', 'Southampton'
    ],
    'la_liga': [
        'Ath Bilbao', 'Ath Madrid', 'Barcelona', 'Betis', 'Celta',
        'Espanol', 'Getafe', 'Girona', 'Las Palmas', 'Leganes',
        'Mallorca', 'Osasuna', 'Real Madrid', 'Sevilla', 'Sociedad',
        'Valencia', 'Vallecano', 'Villarreal', 'Alaves', 'Valladolid'
    ],
    'bundesliga': [
        'Bayern Munich', 'Dortmund', 'Leverkusen', 'RB Leipzig', 'Wolfsburg',
        'Freiburg', 'Ein Frankfurt', 'Mainz', 'Augsburg', 'Werder Bremen',
        'Stuttgart', 'Hoffenheim', 'Union Berlin', 'Darmstadt', 'Heidenheim',
        'St Pauli', 'Holstein Kiel', 'M\'gladbach'
    ],
    'serie_a': [
        'Atalanta', 'Bologna', 'Cagliari', 'Empoli', 'Fiorentina',
        'Genoa', 'Inter', 'Juventus', 'Lazio', 'Lecce',
        'Milan', 'Monza', 'Napoli', 'Parma', 'Roma',
        'Torino', 'Udinese', 'Venezia', 'Verona', 'Como'
    ],
    'ligue_1': [
        'Paris SG', 'Marseille', 'Monaco', 'Lille', 'Lyon',
        'Nice', 'Lens', 'Rennes', 'Strasbourg', 'Montpellier',
        'Nantes', 'Toulouse', 'Reims', 'Brest', 'Le Havre',
        'Auxerre', 'Angers', 'Saint-Etienne'
    ]
}

# 文件路径
files = {
    'premier_league': 'd:/football_tools/new_data/matches/clubs/leagues/premier_league/premier_league_2025-2026.csv',
    'la_liga': 'd:/football_tools/new_data/matches/clubs/leagues/la_liga/la_liga_2025-2026.csv',
    'bundesliga': 'd:/football_tools/new_data/matches/clubs/leagues/bundesliga/bundesliga_2025-2026.csv',
    'serie_a': 'd:/football_tools/new_data/matches/clubs/leagues/serie_a/serie_a_2025-2026.csv',
    'ligue_1': 'd:/football_tools/new_data/matches/clubs/leagues/ligue_1/ligue_1_2025-2026.csv'
}

for league, filepath in files.items():
    if not os.path.exists(filepath):
        print(f"File not found: {filepath}")
        continue

    # 读取文件
    df = pd.read_csv(filepath)
    original_count = len(df)

    # 获取球队列名
    home_col = 'HomeTeam' if 'HomeTeam' in df.columns else 'home_team'
    away_col = 'AwayTeam' if 'AwayTeam' in df.columns else 'away_team'

    # 找出错误球队
    teams = set(correct_teams[league])
    wrong_home = set(df[home_col].unique()) - teams
    wrong_away = set(df[away_col].unique()) - teams
    wrong_teams = wrong_home | wrong_away

    if wrong_teams:
        print(f"\n{league}: Found wrong teams: {wrong_teams}")

        # 删除包含错误球队的行
        df_clean = df[~(df[home_col].isin(wrong_teams) | df[away_col].isin(wrong_teams))]
        removed_count = original_count - len(df_clean)

        # 保存清理后的文件
        df_clean.to_csv(filepath, index=False)
        print(f"  Removed {removed_count} rows, saved {len(df_clean)} rows")
    else:
        print(f"\n{league}: No wrong teams found")
