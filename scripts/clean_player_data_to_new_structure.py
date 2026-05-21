"""
清洗data/players数据到new_data/players目录
1. 提取球员基本信息到profiles
2. 按赛事整理到performance目录
"""
import pandas as pd
import os
from datetime import datetime

SOURCE_DIR = 'd:/football_tools/data/players'
TARGET_DIR = 'd:/football_tools/new_data/players'

def clean_player_data():
    """清洗球员数据"""

    print("=" * 60)
    print("清洗球员数据到新结构")
    print("=" * 60)

    # 读取所有球员数据
    all_players_file = os.path.join(SOURCE_DIR, 'all_players_complete.csv')

    if not os.path.exists(all_players_file):
        print("未找到 all_players_complete.csv")
        return

    # 读取数据，跳过第二行（子标题）
    df = pd.read_csv(all_players_file, skiprows=[1])

    print(f"\n总记录数: {len(df)}")
    print(f"原始字段: {list(df.columns)}")

    # 清理字段名 - 使用新的列名避免重复
    df.columns = [
        'league', 'season_orig', 'team', 'player', 'nation', 'pos', 'age', 'born',
        'MP', 'Starts', 'Min', '90s',
        'Gls', 'Ast', 'G+A', 'G-PK', 'PK', 'PKatt', 'CrdY', 'CrdR',
        'Gls_per90', 'Ast_per90', 'G+A_per90', 'G-PK_per90', 'G+A-PK_per90',
        'season', 'club', 'competition'
    ]

    print(f"新字段: {list(df.columns)}")

    # 提取唯一球员列表
    print("\n提取球员基本信息...")

    # 按球员名分组，取最新记录
    player_profiles = []

    for player_name, group in df.groupby('player'):
        # 取最新赛季的记录
        latest = group.sort_values('season', ascending=False).iloc[0]

        # 判断是否退役（年龄>35或最后记录超过5年）
        current_year = datetime.now().year
        last_season = latest['season'] if pd.notna(latest['season']) else 2000
        age = latest['age'] if pd.notna(latest['age']) else 0

        is_retired = (age > 35) or (current_year - last_season > 5)

        # 生成球员ID
        nation = latest['nation'] if pd.notna(latest['nation']) else ''
        birth_year = int(latest['born']) if pd.notna(latest['born']) else 0

        player_id = f"{player_name.lower().replace(' ', '_')}_{birth_year}"

        profile = {
            'player_id': player_id,
            'player_name': player_name,
            'full_name': '',
            'nation': nation,
            'birth_date': f"{birth_year}-01-01" if birth_year else '',
            'birth_place': '',
            'age': int(age) if pd.notna(age) else 0,
            'height': '',
            'weight': '',
            'foot': '',
            'position_main': str(latest['pos']).split(',')[0] if pd.notna(latest['pos']) else '',
            'position_other': '',
            'current_club': latest['club'] if pd.notna(latest['club']) else '',
            'club_join_date': '',
            'contract_expire': '',
            'market_value': '',
            'market_value_peak': '',
            'national_team': nation,
            'national_debut': '',
            'caps': '',
            'goals_national': '',
            'assists_national': '',
            'status': 'retired' if is_retired else 'active',
            'injury_prone': ''
        }

        player_profiles.append(profile)

    # 保存在役球员
    active_df = pd.DataFrame([p for p in player_profiles if p['status'] == 'active'])
    retired_df = pd.DataFrame([p for p in player_profiles if p['status'] == 'retired'])

    active_dir = os.path.join(TARGET_DIR, 'active')
    retired_dir = os.path.join(TARGET_DIR, 'retired')

    os.makedirs(active_dir, exist_ok=True)
    os.makedirs(retired_dir, exist_ok=True)

    active_file = os.path.join(active_dir, 'profiles.csv')
    retired_file = os.path.join(retired_dir, 'profiles.csv')

    active_df.to_csv(active_file, index=False, encoding='utf-8-sig')
    retired_df.to_csv(retired_file, index=False, encoding='utf-8-sig')

    print(f"  在役球员: {len(active_df)} -> {active_file}")
    print(f"  退役球员: {len(retired_df)} -> {retired_file}")

    # 按赛事保存表现数据
    print("\n整理赛事表现数据...")

    competitions = df['league'].unique()

    for comp in competitions:
        if pd.isna(comp):
            continue

        comp_df = df[df['league'] == comp]

        # 确定目标目录
        if 'World Cup' in str(comp):
            comp_dir = os.path.join(TARGET_DIR, 'performance', 'world_cup')
        elif 'European Championship' in str(comp):
            comp_dir = os.path.join(TARGET_DIR, 'performance', 'euro')
        elif 'Copa America' in str(comp):
            comp_dir = os.path.join(TARGET_DIR, 'performance', 'copa_america')
        elif 'Africa Cup' in str(comp):
            comp_dir = os.path.join(TARGET_DIR, 'performance', 'africa_cup')
        elif 'Asian Cup' in str(comp):
            comp_dir = os.path.join(TARGET_DIR, 'performance', 'asian_cup')
        else:
            comp_dir = os.path.join(TARGET_DIR, 'performance', 'other')

        os.makedirs(comp_dir, exist_ok=True)

        # 标准化字段
        standard_cols = ['league', 'season', 'team', 'player', 'nation', 'pos', 'age', 'club', 'born',
                        'MP', 'Starts', 'Min', '90s', 'Gls', 'Ast', 'G+A', 'G-PK', 'PK', 'PKatt', 'CrdY', 'CrdR',
                        'Gls_per90', 'Ast_per90', 'G+A_per90', 'G-PK_per90', 'G+A-PK_per90']

        # 选择存在的字段
        available_cols = [c for c in standard_cols if c in comp_df.columns]
        comp_df_clean = comp_df[available_cols].copy()

        # 保存
        comp_name = str(comp).replace('INT-', '').replace(' ', '_').lower()
        output_file = os.path.join(comp_dir, f'{comp_name}_players_all.csv')
        comp_df_clean.to_csv(output_file, index=False, encoding='utf-8-sig')

        print(f"  {comp}: {len(comp_df_clean)} 条记录 -> {output_file}")

    print("\n" + "=" * 60)
    print("清洗完成!")
    print("=" * 60)

if __name__ == '__main__':
    clean_player_data()
