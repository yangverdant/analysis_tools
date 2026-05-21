"""
重新清洗J1和J2联赛数据 - 使用正确的文件格式
"""
import csv
from pathlib import Path
import sys

if sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')

DATA_DIR = Path("D:/football_tools/data/05_asia_leagues")
OUTPUT_DIR = Path("D:/football_tools/new_data/leagues")

# 标准字段映射
FIELD_MAPPING = {
    'Div': 'division',
    'Date': 'match_date',
    'Time': 'match_time',
    'HomeTeam': 'home_team',
    'AwayTeam': 'away_team',
    'FTHG': 'home_goals',
    'FTAG': 'away_goals',
    'FTR': 'result',
    'HTHG': 'home_goals_ht',
    'HTAG': 'away_goals_ht',
    'HTR': 'result_ht',
    'HS': 'home_shots',
    'AS': 'away_shots',
    'HST': 'home_shots_target',
    'AST': 'away_shots_target',
    'HC': 'home_corners',
    'AC': 'away_corners',
    'HF': 'home_fouls',
    'AF': 'away_fouls',
    'HY': 'home_yellow',
    'AY': 'away_yellow',
    'HR': 'home_red',
    'AR': 'away_red',
    'Referee': 'referee',
    'Attendance': 'attendance',
    'B365H': 'b365_home',
    'B365D': 'b365_draw',
    'B365A': 'b365_away',
}

STANDARD_FIELDS = [
    'season', 'match_date', 'match_time', 'round_num',
    'division', 'home_team', 'away_team',
    'home_goals', 'away_goals', 'result',
    'status',
    'home_goals_ht', 'away_goals_ht', 'result_ht',
    'home_shots', 'away_shots',
    'home_shots_target', 'away_shots_target',
    'home_corners', 'away_corners',
    'home_fouls', 'away_fouls',
    'home_yellow', 'away_yellow',
    'home_red', 'away_red',
    'referee', 'attendance',
    'b365_home', 'b365_draw', 'b365_away',
]

def parse_date(date_str):
    if not date_str:
        return None
    try:
        if len(date_str) == 10 and '-' in date_str:
            return date_str
        if len(date_str) == 8 and '-' in date_str:
            parts = date_str.split('-')
            yy = int(parts[0])
            year = 2000 + yy if yy < 100 else yy
            return f'{year}-{parts[1]}-{parts[2]}'
        return date_str
    except:
        return date_str

def calculate_round(matches):
    target_per_round = 9  # J1: 18队, 每轮9场
    date_counts = {}
    for m in matches:
        date = m.get('match_date')
        if date and date != 'null':
            if date not in date_counts:
                date_counts[date] = 0
            date_counts[date] += 1
    sorted_dates = sorted(date_counts.keys())
    rounds = {}
    round_num = 1
    current_round_matches = 0
    for date in sorted_dates:
        rounds[date] = round_num
        current_round_matches += date_counts[date]
        if current_round_matches >= target_per_round:
            round_num += 1
            current_round_matches = 0
    return rounds

def clean_csv_file(input_path, output_path, season):
    rows = []
    try:
        with open(input_path, 'r', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)
            for row in reader:
                new_row = {}
                for old_key, value in row.items():
                    if old_key is None:
                        continue
                    old_key_clean = old_key.strip().replace('﻿', '') if old_key else ''
                    if not old_key_clean or old_key_clean.startswith('Unnamed'):
                        continue
                    if old_key_clean in FIELD_MAPPING:
                        new_key = FIELD_MAPPING[old_key_clean]
                        if value == '' or value is None:
                            new_row[new_key] = 'null'
                        else:
                            new_row[new_key] = value
                new_row['season'] = season
                if 'match_date' in new_row and new_row['match_date']:
                    new_row['match_date'] = parse_date(new_row['match_date'])
                rows.append(new_row)

        rounds = calculate_round(rows)
        for row in rows:
            if row.get('match_date') and row['match_date'] != 'null':
                row['round_num'] = rounds.get(row['match_date'], None)
            else:
                row['round_num'] = None

        for row in rows:
            status = row.get('status', '').strip()
            if not status or status == 'null':
                home_goals = row.get('home_goals', '')
                away_goals = row.get('away_goals', '')
                if home_goals and home_goals != 'null' and away_goals and away_goals != 'null':
                    row['status'] = 'Finished'
                else:
                    row['status'] = 'Scheduled'

        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, 'w', encoding='utf-8', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=STANDARD_FIELDS, extrasaction='ignore')
            writer.writeheader()
            writer.writerows(rows)
        return len(rows)
    except Exception as e:
        print(f'  错误: {e}')
        return 0

def process_j_league(league_name):
    league_path = DATA_DIR / league_name
    output_path = OUTPUT_DIR / league_name

    if not league_path.exists():
        print(f'联赛目录不存在: {league_name}')
        return

    # 获取所有CSV文件，排除特殊文件
    all_csv_files = list(league_path.glob('*.csv'))
    csv_files = []
    for f in all_csv_files:
        if f.name.endswith('_all.csv'):
            continue
        if f.name.endswith('_history.csv'):
            continue
        if f.name == 'results.csv':
            continue
        if league_name == 'j1_league' and f.name.startswith('j2_league_'):
            continue
        csv_files.append(f)

    print(f'\n{league_name}:')

    total_rows = 0
    for csv_file in sorted(csv_files):
        # 从文件名提取赛季
        name = csv_file.stem
        parts = name.split('_')
        if len(parts) >= 2:
            season = parts[-1]
            if '-' not in season:
                # 单年份格式，转为赛季格式
                year = int(season)
                season = f'{year}-{str(year+1)[-2:]}'
        else:
            season = name

        output_file = output_path / f'{league_name}_{season}.csv'
        rows = clean_csv_file(csv_file, output_file, season)
        if rows > 0:
            print(f'  {csv_file.name} -> {season}: {rows}场')
            total_rows += rows

    print(f'  总计: {total_rows}场')

if __name__ == '__main__':
    print('='*60)
    print('重新清洗J1和J2联赛数据')
    print('='*60)

    process_j_league('j1_league')
    process_j_league('j2_league')

    print('\n完成!')