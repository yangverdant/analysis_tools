"""
生成世界杯球队统计文件
"""
import csv
from pathlib import Path
from collections import defaultdict

def generate_world_cup_teams():
    """从世界杯标准化数据生成球队统计"""
    input_dir = Path('D:/football_tools/new_data/cups/world_cup')
    output_dir = Path('D:/football_tools/new_data/teams')
    output_dir.mkdir(parents=True, exist_ok=True)

    teams_by_season = defaultdict(set)
    team_cn_map = defaultdict(set)

    for csv_file in sorted(input_dir.glob('*.csv')):
        season = csv_file.stem.replace('world_cup_', '')

        with open(csv_file, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                home_team = row.get('home_team', '').strip()
                home_team_cn = row.get('home_team_cn', '').strip()
                away_team = row.get('away_team', '').strip()
                away_team_cn = row.get('away_team_cn', '').strip()

                if home_team:
                    teams_by_season[season].add(home_team)
                    if home_team_cn:
                        team_cn_map[home_team].add(home_team_cn)

                if away_team:
                    teams_by_season[season].add(away_team)
                    if away_team_cn:
                        team_cn_map[away_team].add(away_team_cn)

    # 写入球队统计文件
    rows = []
    all_teams = set()
    missing_cn = set()

    for season in sorted(teams_by_season.keys()):
        for team in sorted(teams_by_season[season]):
            cn_names = team_cn_map.get(team, set())
            cn_name = list(cn_names)[0] if cn_names else ''

            rows.append({
                'season': season,
                'league_en': 'world_cup',
                'league_cn': '世界杯',
                'team_en': team,
                'team_cn': cn_name
            })

            all_teams.add(team)
            if not cn_name:
                missing_cn.add(team)

    output_file = output_dir / 'world_cup_teams.csv'
    with open(output_file, 'w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=['season', 'league_en', 'league_cn', 'team_en', 'team_cn'])
        writer.writeheader()
        writer.writerows(rows)

    print('='*60)
    print('世界杯球队统计')
    print('='*60)
    print(f'赛季数: {len(teams_by_season)}')
    print(f'球队数: {len(all_teams)}')
    print(f'记录数: {len(rows)}')
    print(f'有中文名: {len(all_teams) - len(missing_cn)}')
    print(f'缺中文名: {len(missing_cn)}')

    if missing_cn:
        print('\n缺失中文名:')
        for team in sorted(missing_cn):
            print(f'  {team}')

if __name__ == '__main__':
    generate_world_cup_teams()