"""
杯赛数据完整处理脚本
1. 统一CSV格式
2. 推断比赛阶段
3. 导入数据库
"""
import os
import csv
import json
import sqlite3
import pandas as pd
from datetime import datetime

# 数据库路径
DB_PATH = 'd:/football_tools/data/football_unified.db'
OUTPUT_DIR = 'd:/football_tools/data/cups_final'

# 杯赛ID映射
CUP_IDS = {
    'fa_cup': 42,
    'england_league_cup': 43,
    'dfb_pokal': 44,
    'copa_del_rey': 45,
    'italy_cup': 46,
    'coupe_de_france': 47,
    'champions_league': 48,
    'europa_league': 49,
    'conference_league': 50,
    'world_cup': 51,
    'euro': 53,
    'austria_cup': None,  # 需要分配ID
}

# 杯赛频率配置
CUP_FREQUENCY = {
    'fa_cup': 'yearly',              # 每年一届
    'england_league_cup': 'yearly',   # 每年一届
    'dfb_pokal': 'yearly',            # 每年一届
    'copa_del_rey': 'yearly',         # 每年一届
    'italy_cup': 'yearly',            # 每年一届
    'coupe_de_france': 'yearly',      # 每年一届
    'champions_league': 'yearly',     # 每年一届
    'europa_league': 'yearly',        # 每年一届
    'conference_league': 'yearly',    # 每年一届
    'world_cup': 'quadrennial',       # 四年一届
    'euro': 'quadrennial',            # 四年一届
    'austria_cup': 'yearly',          # 每年一届
}

# 阶段映射
STAGE_MAPPING = {
    'qualifying': {'name': '预选赛', 'order': 1},
    'playoff': {'name': '附加赛', 'order': 2},
    'group': {'name': '小组赛', 'order': 3},
    'league_phase': {'name': '联赛阶段', 'order': 3},
    'round_of_32': {'name': '32强', 'order': 4},
    'round_of_16': {'name': '16强', 'order': 5},
    'quarterfinal': {'name': '八强', 'order': 6},
    'semifinal': {'name': '半决赛', 'order': 7},
    'final': {'name': '决赛', 'order': 8},
    'first_round': {'name': '第一轮', 'order': 1},
    'second_round': {'name': '第二轮', 'order': 2},
    'third_round': {'name': '第三轮', 'order': 3},
    'fourth_round': {'name': '第四轮', 'order': 4},
    'fifth_round': {'name': '第五轮', 'order': 5},
}

# 统一输出字段
OUTPUT_COLUMNS = [
    'match_id',
    'league_id',
    'season',
    'stage',
    'stage_order',
    'group_name',
    'group_round',
    'leg',
    'match_date',
    'match_time',
    'home_team_id',
    'away_team_id',
    'home_team',
    'away_team',
    'home_team_cn',
    'away_team_cn',
    'home_goals',
    'away_goals',
    'home_goals_ht',
    'away_goals_ht',
    'home_goals_et',
    'away_goals_et',
    'home_penalties',
    'away_penalties',
    'result',
    'venue',
    'attendance',
    'referee',
    'status'
]

def parse_season(filename, cup_name='unknown'):
    """从文件名提取赛季"""
    import re

    # 四年一届杯赛的特殊处理（如 euro_2000.csv 表示2000年那一届）
    if CUP_FREQUENCY.get(cup_name) == 'quadrennial':
        # 匹配单年份格式：euro_2000.csv, world_cup_2022.csv
        match = re.search(r'_(\d{4})\.csv', filename)
        if match:
            year = match.group(1)
            return year  # 直接返回年份，如 "2000", "2024"
        # 匹配年份范围格式（用于预选赛数据）
        match = re.search(r'(\d{4})-(\d{4})', filename)
        if match:
            return f"{match.group(1)}-{match.group(2)}"

    # 每年一届杯赛的标准处理
    # 匹配 2024-2025 或 2024-25 格式
    match = re.search(r'(\d{4})-?(\d{2,4})', filename)
    if match:
        year1 = match.group(1)
        year2 = match.group(2)
        if len(year2) == 2:
            year2 = year1[:2] + year2
        return f"{year1}-{year2}"
    return 'unknown'

def infer_stage_from_matchcount(match_count, cup_name, date_str):
    """根据比赛数量和日期推断阶段"""
    # 足总杯逻辑
    if cup_name == 'fa_cup':
        if match_count >= 40:
            return 'qualifying'
        elif match_count >= 32:
            return 'third_round'
        elif match_count >= 16:
            return 'fourth_round'
        elif match_count >= 8:
            return 'fifth_round'
        elif match_count >= 4:
            return 'quarterfinal'
        elif match_count >= 2:
            return 'semifinal'
        else:
            return 'final'

    # 欧冠逻辑
    elif cup_name == 'champions_league':
        if match_count >= 16:
            return 'league_phase'
        elif match_count >= 8:
            return 'quarterfinal'
        elif match_count >= 4:
            return 'semifinal'
        else:
            return 'final'

    # 默认逻辑
    return 'unknown'

def process_cup_csv(input_path, output_path, cup_name, league_id, start_match_id=1000000):
    """处理单个杯赛CSV文件"""
    filename = os.path.basename(input_path)
    season = parse_season(filename, cup_name)

    print(f"处理: {filename} (赛季: {season}, 联赛ID: {league_id})")

    try:
        df = pd.read_csv(input_path, encoding='utf-8', on_bad_lines='skip')
    except:
        try:
            df = pd.read_csv(input_path, encoding='latin-1', on_bad_lines='skip')
        except Exception as e:
            print(f"  无法读取: {e}")
            return []

    if df.empty:
        print(f"  文件为空")
        return []

    # 按日期分组推断阶段
    df['Date'] = pd.to_datetime(df.get('Date', ''), errors='coerce')
    df = df.dropna(subset=['Date'])
    df = df.sort_values('Date')

    # 按日期分组
    date_groups = df.groupby(df['Date'].dt.date)

    output_data = []
    match_id = start_match_id

    for date, group in date_groups:
        match_count = len(group)
        date_str = str(date)

        # 推断阶段
        stage = infer_stage_from_matchcount(match_count, cup_name, date_str)
        stage_info = STAGE_MAPPING.get(stage, {'name': stage, 'order': 0})

        for idx, row in group.iterrows():
            match_id += 1

            # 构建输出行
            output_row = {
                'match_id': match_id,
                'league_id': league_id,
                'season': season,
                'stage': stage,
                'stage_order': stage_info['order'],
                'group_name': '',  # 小组赛需要额外处理
                'group_round': '',
                'leg': '',
                'match_date': row.get('Date', ''),
                'match_time': row.get('Time', ''),
                'home_team_id': 0,
                'away_team_id': 0,
                'home_team': row.get('HomeTeam', ''),
                'away_team': row.get('AwayTeam', ''),
                'home_team_cn': '',
                'away_team_cn': '',
                'home_goals': row.get('FTHG', None),
                'away_goals': row.get('FTAG', None),
                'home_goals_ht': row.get('HTHG', None),
                'away_goals_ht': row.get('HTAG', None),
                'home_goals_et': None,
                'away_goals_et': None,
                'home_penalties': None,
                'away_penalties': None,
                'result': row.get('FTR', ''),
                'venue': row.get('Venue', ''),
                'attendance': row.get('Attendance', ''),
                'referee': row.get('Referee', ''),
                'status': row.get('Status', 'Finished') or 'Finished'
            }

            output_data.append(output_row)

    # 保存CSV
    if output_data:
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        output_df = pd.DataFrame(output_data, columns=OUTPUT_COLUMNS)
        output_df.to_csv(output_path, index=False, encoding='utf-8')
        print(f"  已转换 {len(output_data)} 条记录")

    return output_data

def process_all_cups():
    """处理所有杯赛"""
    base_path = 'd:/football_tools/data'
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    cup_dirs = {
        'fa_cup': '02_europe_cups/fa_cup',
        'england_league_cup': '02_europe_cups/england_league_cup',
        'dfb_pokal': '02_europe_cups/dfb_pokal',
        'copa_del_rey': '02_europe_cups/copa_del_rey',
        'italy_cup': '02_europe_cups/italy_cup',
        'coupe_de_france': '02_europe_cups/coupe_de_france',
        'austria_cup': '02_europe_cups/austria_cup',
        'champions_league': '03_european_competitions/champions_league',
        'europa_league': '03_european_competitions/europa_league',
        'conference_league': '03_european_competitions/conference_league',
        'world_cup': '04_international/world_cup',
        'euro': '04_international/euro',
    }

    all_matches = []
    global_match_id = 1000000  # 全局match_id计数器

    for cup_name, cup_dir in cup_dirs.items():
        full_path = os.path.join(base_path, cup_dir)
        if not os.path.exists(full_path):
            print(f"目录不存在: {full_path}")
            continue

        league_id = CUP_IDS.get(cup_name)
        output_dir = os.path.join(OUTPUT_DIR, cup_name)
        os.makedirs(output_dir, exist_ok=True)

        for filename in os.listdir(full_path):
            if filename.endswith('.csv') and 'all' not in filename.lower():
                input_path = os.path.join(full_path, filename)
                output_path = os.path.join(output_dir, filename)

                matches = process_cup_csv(input_path, output_path, cup_name, league_id, global_match_id)
                # 更新全局计数器
                if matches:
                    global_match_id = max(m['match_id'] for m in matches) + 1
                all_matches.extend(matches)

    # 合并所有杯赛数据
    if all_matches:
        all_df = pd.DataFrame(all_matches, columns=OUTPUT_COLUMNS)
        all_path = os.path.join(OUTPUT_DIR, 'all_cups_matches.csv')
        all_df.to_csv(all_path, index=False, encoding='utf-8')
        print(f"\n总计: {len(all_matches)} 条杯赛比赛记录")
        print(f"合并文件: {all_path}")

    return all_matches

def import_to_database(matches):
    """导入数据库"""
    if not matches:
        print("没有数据需要导入")
        return

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # 检查matches表是否存在
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='matches'")
    if not cursor.fetchone():
        print("matches表不存在，请先运行build_database.py")
        return

    # 导入数据
    inserted = 0
    for match in matches:
        try:
            cursor.execute('''
                INSERT OR REPLACE INTO matches (
                    match_id, league_id, match_date, match_time,
                    home_team, away_team, home_goals, away_goals,
                    home_odds, draw_odds, away_odds, status
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                match['match_id'],
                match['league_id'],
                match['match_date'],
                match['match_time'],
                match['home_team'],
                match['away_team'],
                match['home_goals'],
                match['away_goals'],
                None, None, None,  # odds
                match['status']
            ))
            inserted += 1
        except Exception as e:
            pass

    conn.commit()
    conn.close()
    print(f"已导入 {inserted} 条记录到数据库")

if __name__ == '__main__':
    print("=" * 60)
    print("杯赛数据处理脚本")
    print("=" * 60)

    # 1. 处理所有杯赛CSV
    matches = process_all_cups()

    # 2. 导入数据库（可选）
    print("\n是否导入数据库? (y/n): ", end='')
    # import_to_database(matches)  # 取消注释以导入

    print("\n处理完成!")
