import pandas as pd
import os

# Correct teams for each league and season
correct_teams = {
    'premier_league': {
        '2024-2025': [
            'Arsenal', 'Aston Villa', 'Bournemouth', 'Brentford', 'Brighton',
            'Chelsea', 'Crystal Palace', 'Everton', 'Fulham', 'Liverpool',
            'Man City', 'Man United', 'Newcastle', "Nott'm Forest", 'Tottenham',
            'West Ham', 'Wolves', 'Ipswich', 'Leicester', 'Southampton'
        ],
        '2025-2026': [
            'Arsenal', 'Aston Villa', 'Bournemouth', 'Brentford', 'Brighton',
            'Chelsea', 'Crystal Palace', 'Everton', 'Fulham', 'Liverpool',
            'Man City', 'Man United', 'Newcastle', "Nott'm Forest", 'Tottenham',
            'West Ham', 'Wolves', 'Ipswich', 'Leicester', 'Southampton'
        ]
    },
    'la_liga': {
        '2024-2025': [
            'Ath Bilbao', 'Ath Madrid', 'Barcelona', 'Betis', 'Celta',
            'Espanol', 'Getafe', 'Girona', 'Las Palmas', 'Leganes',
            'Mallorca', 'Osasuna', 'Real Madrid', 'Sevilla', 'Sociedad',
            'Valencia', 'Vallecano', 'Villarreal', 'Alaves', 'Valladolid'
        ],
        '2025-2026': [
            'Ath Bilbao', 'Ath Madrid', 'Barcelona', 'Betis', 'Celta',
            'Espanol', 'Getafe', 'Girona', 'Las Palmas', 'Leganes',
            'Mallorca', 'Osasuna', 'Real Madrid', 'Sevilla', 'Sociedad',
            'Valencia', 'Vallecano', 'Villarreal', 'Alaves', 'Valladolid'
        ]
    },
    'bundesliga': {
        '2024-2025': [
            'Bayern Munich', 'Dortmund', 'Leverkusen', 'RB Leipzig', 'Wolfsburg',
            'Freiburg', 'Ein Frankfurt', 'Mainz', 'Augsburg', 'Werder Bremen',
            'Stuttgart', 'Hoffenheim', 'Union Berlin', 'Heidenheim', 'St Pauli',
            'Holstein Kiel', 'Bochum', "M'gladbach"
        ],
        '2025-2026': [
            'Bayern Munich', 'Dortmund', 'Leverkusen', 'RB Leipzig', 'Wolfsburg',
            'Freiburg', 'Ein Frankfurt', 'Mainz', 'Augsburg', 'Werder Bremen',
            'Stuttgart', 'Hoffenheim', 'Union Berlin', 'Heidenheim', 'St Pauli',
            'Holstein Kiel', 'Darmstadt', "M'gladbach"
        ]
    },
    'serie_a': {
        '2024-2025': [
            'Atalanta', 'Bologna', 'Cagliari', 'Empoli', 'Fiorentina',
            'Genoa', 'Inter', 'Juventus', 'Lazio', 'Lecce',
            'Milan', 'Monza', 'Napoli', 'Parma', 'Roma',
            'Torino', 'Udinese', 'Venezia', 'Verona', 'Como'
        ],
        '2025-2026': [
            'Atalanta', 'Bologna', 'Cagliari', 'Empoli', 'Fiorentina',
            'Genoa', 'Inter', 'Juventus', 'Lazio', 'Lecce',
            'Milan', 'Monza', 'Napoli', 'Parma', 'Roma',
            'Torino', 'Udinese', 'Venezia', 'Verona', 'Como'
        ]
    },
    'ligue_1': {
        '2024-2025': [
            'Paris SG', 'Marseille', 'Monaco', 'Lille', 'Lyon',
            'Nice', 'Lens', 'Rennes', 'Strasbourg', 'Montpellier',
            'Nantes', 'Toulouse', 'Reims', 'Brest', 'Le Havre',
            'Auxerre', 'Angers', 'Saint-Etienne'
        ],
        '2025-2026': [
            'Paris SG', 'Marseille', 'Monaco', 'Lille', 'Lyon',
            'Nice', 'Lens', 'Rennes', 'Strasbourg', 'Montpellier',
            'Nantes', 'Toulouse', 'Reims', 'Brest', 'Le Havre',
            'Auxerre', 'Angers', 'Saint-Etienne'
        ]
    }
}

expected_matches = {
    'premier_league': 380,
    'la_liga': 380,
    'bundesliga': 306,
    'serie_a': 380,
    'ligue_1': 306
}

files = {
    'premier_league': 'd:/football_tools/new_data/matches/clubs/leagues/premier_league',
    'la_liga': 'd:/football_tools/new_data/matches/clubs/leagues/la_liga',
    'bundesliga': 'd:/football_tools/new_data/matches/clubs/leagues/bundesliga',
    'serie_a': 'd:/football_tools/new_data/matches/clubs/leagues/serie_a',
    'ligue_1': 'd:/football_tools/new_data/matches/clubs/leagues/ligue_1'
}

print('=' * 80)
print('五大联赛数据完整性检查')
print('=' * 80)

for league, base_path in files.items():
    print(f'\n{league.upper()}')
    print('-' * 40)

    for season in ['2024-2025', '2025-2026']:
        filepath = f'{base_path}/{league}_{season}.csv'

        if not os.path.exists(filepath):
            print(f'{season}: FILE NOT FOUND')
            continue

        df = pd.read_csv(filepath)
        home_col = 'HomeTeam' if 'HomeTeam' in df.columns else 'home_team'
        away_col = 'AwayTeam' if 'AwayTeam' in df.columns else 'away_team'

        # Stats
        total_matches = len(df)
        finished = len(df[df['status'] == 'finished']) if 'status' in df.columns else 'N/A'
        scheduled = len(df[df['status'] == 'scheduled']) if 'status' in df.columns else 'N/A'

        # Teams
        actual_teams = set(df[home_col].unique()) | set(df[away_col].unique())
        expected_teams = set(correct_teams[league][season])

        missing = expected_teams - actual_teams
        extra = actual_teams - expected_teams

        # Check
        teams_ok = len(actual_teams) == len(expected_teams) and len(missing) == 0 and len(extra) == 0
        matches_ok = total_matches == expected_matches[league]

        status = 'OK' if (teams_ok and matches_ok) else 'ISSUES'

        print(f'{season}: {status}')
        print(f'  Matches: {total_matches}/{expected_matches[league]}', end='')
        print(f' (OK)' if matches_ok else f' (MISSING {expected_matches[league] - total_matches})')
        print(f'  Teams: {len(actual_teams)}/{len(expected_teams)}', end='')
        print(f' (OK)' if teams_ok else '')

        if missing:
            print(f'  Missing teams: {sorted(missing)}')
        if extra:
            print(f'  Extra teams: {sorted(extra)}')

        # Check duplicates
        df['match_key'] = df[home_col] + '_' + df[away_col]
        dup_count = df.duplicated(subset=['match_key']).sum()
        if dup_count > 0:
            print(f'  Duplicates: {dup_count}')

print('\n' + '=' * 80)
print('检查完成')
