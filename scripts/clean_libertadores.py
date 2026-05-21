import pandas as pd
import re
import os

def clean_team_name(name):
    """Remove country code from team name, e.g., 'Monagas SC (VEN)' -> 'Monagas SC'"""
    if pd.isna(name):
        return name
    # Remove (XXX) pattern at the end
    cleaned = re.sub(r'\s*\([A-Z]{3}\)\s*$', '', str(name))
    return cleaned.strip()

def determine_round(date, home_team, away_team):
    """Determine the round based on date and match context"""
    # This is simplified - in reality would need more context
    # For now, return 'group' as placeholder
    return 'group'

def calculate_result(home_goals, away_goals):
    """Calculate match result"""
    if pd.isna(home_goals) or pd.isna(away_goals):
        return ''
    if home_goals > away_goals:
        return 'H'
    elif home_goals < away_goals:
        return 'A'
    else:
        return 'D'

def clean_libertadores_data(input_file, output_file):
    """Clean and transform libertadores data"""

    # Read CSV
    df = pd.read_csv(input_file)

    # Skip if empty (only header)
    if len(df) == 0:
        print(f"Skipping {input_file} - no data")
        return None

    # Create new dataframe with standardized fields
    new_df = pd.DataFrame()

    # Basic fields
    new_df['competition'] = 'libertadores'

    # Extract season from filename
    filename = os.path.basename(input_file)
    if 'all' in filename:
        # For all.csv, extract year from date
        new_df['season'] = df['Date'].apply(lambda x: str(x)[:4] if pd.notna(x) else '')
    else:
        # Extract from filename like copa_libertadores_2025.csv
        match = re.search(r'(\d{4})', filename)
        if match:
            new_df['season'] = match.group(1)
        else:
            new_df['season'] = ''

    new_df['round'] = df.apply(lambda row: determine_round(row['Date'], row['HomeTeam'], row['AwayTeam']), axis=1)
    new_df['leg'] = ''  # Will need to be filled later
    new_df['match_date'] = df['Date']
    new_df['match_time'] = df['Time']
    new_df['neutral'] = False  # Most club matches are not neutral

    # Clean team names
    new_df['home_team'] = df['HomeTeam'].apply(clean_team_name)
    new_df['away_team'] = df['AwayTeam'].apply(clean_team_name)

    # Goals
    new_df['home_goals'] = df['FTHG']
    new_df['away_goals'] = df['FTAG']
    new_df['result'] = df.apply(lambda row: calculate_result(row['FTHG'], row['FTAG']), axis=1)

    # Half time
    new_df['home_goals_ht'] = df['HTHG']
    new_df['away_goals_ht'] = df['HTAG']
    new_df['result_ht'] = df.apply(lambda row: calculate_result(row['HTHG'], row['HTAG']), axis=1)

    # Extra time and penalties (not in source data)
    new_df['home_goals_et'] = ''
    new_df['away_goals_et'] = ''
    new_df['home_penalties'] = ''
    new_df['away_penalties'] = ''

    # Stats
    new_df['home_shots'] = df['HS']
    new_df['away_shots'] = df['AS']
    new_df['home_shots_target'] = df['HST']
    new_df['away_shots_target'] = df['AST']
    new_df['home_corners'] = df['HC']
    new_df['away_corners'] = df['AC']
    new_df['home_fouls'] = df['HF']
    new_df['away_fouls'] = df['AF']
    new_df['home_yellow'] = df['HY']
    new_df['away_yellow'] = df['AY']
    new_df['home_red'] = df['HR']
    new_df['away_red'] = df['AR']

    # Other
    new_df['referee'] = df['Referee']
    new_df['attendance'] = df['Attendance']

    # Status
    new_df['status'] = df['Status'].apply(lambda x: 'finished' if x == 'Finished' else 'scheduled' if pd.notna(x) else '')

    # Odds - use average odds
    new_df['home_odds'] = df['AvgH']
    new_df['draw_odds'] = df['AvgD']
    new_df['away_odds'] = df['AvgA']

    # Save
    new_df.to_csv(output_file, index=False)
    print(f"Processed {input_file} -> {output_file} ({len(new_df)} matches)")

    return new_df

# Process all files
input_dir = 'd:/football_tools/data/06_south_america/copa_libertadores'
output_dir = 'd:/football_tools/new_data/matches/clubs/cups/libertadores'

# Process only files with data
files_to_process = [
    'copa_libertadores_2025.csv',
    'copa_libertadores_all.csv'
]

all_data = []
for filename in files_to_process:
    input_file = os.path.join(input_dir, filename)

    # Determine output filename
    if 'all' in filename:
        output_file = os.path.join(output_dir, 'libertadores_all.csv')
    else:
        # Convert copa_libertadores_2025.csv -> libertadores_2025.csv
        output_filename = filename.replace('copa_libertadores_', 'libertadores_')
        output_file = os.path.join(output_dir, output_filename)

    df = clean_libertadores_data(input_file, output_file)
    if df is not None:
        all_data.append(df)

# Create combined file
if all_data:
    combined = pd.concat(all_data, ignore_index=True)
    # Remove duplicates based on date, time, home_team, away_team
    combined = combined.drop_duplicates(subset=['match_date', 'match_time', 'home_team', 'away_team'])
    combined = combined.sort_values('match_date').reset_index(drop=True)
    combined.to_csv(os.path.join(output_dir, 'libertadores_combined.csv'), index=False)
    print(f"\nCombined file: {len(combined)} unique matches")

print("\nDone!")
