"""
保存世界杯详细数据到JSON文件，稍后导入
"""

import json
import sqlite3
from pathlib import Path

DATA_DIR = Path('d:/football_tools')
OUTPUT_DIR = DATA_DIR / 'world_cup_processed'
OUTPUT_DIR.mkdir(exist_ok=True)

# 球队数据文件
TEAM_FILES = {
    'wc_teams_2014.json': {'season': '2014', 'league_id': 40},
    'wc_teams_2022.json': {'season': '2022', 'league_id': 40},
    'wc_teams_2026.json': {'season': '2026', 'league_id': 40},
    'wwc_teams_2023.json': {'season': '2023', 'league_id': 7541},
}


def process_teams():
    """处理球队数据"""
    print("=" * 60)
    print("处理世界杯球队和球员数据")
    print("=" * 60)

    all_teams = []
    all_players = []

    for filename, meta in TEAM_FILES.items():
        filepath = DATA_DIR / filename
        if not filepath.exists():
            print(f"\n{filename}: 文件不存在")
            continue

        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                teams = json.load(f)
        except Exception as e:
            print(f"\n{filename}: 读取失败 - {e}")
            continue

        if not isinstance(teams, list):
            print(f"\n{filename}: 数据格式错误")
            continue

        print(f"\n{meta['season']}: {len(teams)} 支球队")

        for team in teams:
            team_key = team.get('team_key')
            team_name = team.get('team_name', '')
            team_country = team.get('team_country', '')
            team_founded = team.get('team_founded')
            team_badge = team.get('team_badge', '')

            venue = team.get('venue', {})
            if isinstance(venue, list):
                venue = venue[0] if len(venue) > 0 else {}

            team_data = {
                'team_key': team_key,
                'team_name': team_name,
                'team_country': team_country,
                'team_founded': team_founded,
                'team_badge': team_badge,
                'venue_name': venue.get('venue_name', ''),
                'venue_city': venue.get('venue_city', ''),
                'venue_capacity': venue.get('venue_capacity', ''),
                'venue_address': venue.get('venue_address', ''),
                'venue_surface': venue.get('venue_surface', ''),
                'season': meta['season'],
                'league_id': meta['league_id']
            }
            all_teams.append(team_data)

            # 处理球员
            players = team.get('players', [])
            for p in players:
                player_data = {
                    'player_key': p.get('player_key', ''),
                    'player_id': p.get('player_id', '') or f"{team_key}_{p.get('player_key', '')}",
                    'team_key': team_key,
                    'team_name': team_name,
                    'player_name': p.get('player_name', ''),
                    'player_complete_name': p.get('player_complete_name', ''),
                    'player_number': p.get('player_number', ''),
                    'player_country': p.get('player_country', ''),
                    'player_type': p.get('player_type', ''),
                    'player_age': p.get('player_age'),
                    'player_birthdate': p.get('player_birthdate', ''),
                    'player_is_captain': p.get('player_is_captain', ''),
                    'player_image': p.get('player_image', ''),
                    'player_match_played': p.get('player_match_played'),
                    'player_goals': p.get('player_goals'),
                    'player_assists': p.get('player_assists'),
                    'player_yellow_cards': p.get('player_yellow_cards'),
                    'player_red_cards': p.get('player_red_cards'),
                    'player_injured': p.get('player_injured'),
                    'player_rating': p.get('player_rating'),
                    'season': meta['season'],
                    'league_id': meta['league_id']
                }
                all_players.append(player_data)

    # 保存处理后的数据
    print(f"\n保存数据...")

    with open(OUTPUT_DIR / 'teams_processed.json', 'w', encoding='utf-8') as f:
        json.dump(all_teams, f, ensure_ascii=False, indent=2)
    print(f"球队: {len(all_teams)}")

    with open(OUTPUT_DIR / 'players_processed.json', 'w', encoding='utf-8') as f:
        json.dump(all_players, f, ensure_ascii=False, indent=2)
    print(f"球员: {len(all_players)}")

    # 统计
    print(f"\n{'=' * 60}")
    print("数据统计:")
    print(f"  球队总数: {len(all_teams)}")
    print(f"  球员总数: {len(all_players)}")

    # 按赛季统计
    seasons = {}
    for t in all_teams:
        s = t['season']
        seasons[s] = seasons.get(s, 0) + 1
    print(f"\n按赛季:")
    for s, c in sorted(seasons.items(), reverse=True):
        print(f"  {s}: {c} 支球队")

    # 按位置统计球员
    positions = {}
    for p in all_players:
        pos = p['player_type'] or 'Unknown'
        positions[pos] = positions.get(pos, 0) + 1
    print(f"\n按位置:")
    for pos, c in sorted(positions.items(), key=lambda x: -x[1]):
        print(f"  {pos}: {c} 名球员")

    print(f"\n数据保存在: {OUTPUT_DIR}")


if __name__ == '__main__':
    process_teams()