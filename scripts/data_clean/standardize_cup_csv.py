"""
统一杯赛CSV格式脚本
将所有杯赛数据转换为统一格式
"""
import os
import csv
import pandas as pd
from datetime import datetime

# 杯赛阶段映射 - 将各种Div代码映射到标准阶段
STAGE_MAPPING = {
    # 欧冠
    'CL': {'stage': 'league_phase', 'order': 1, 'is_group': True},
    'CLG': {'stage': 'group', 'order': 1, 'is_group': True},  # 旧格式小组赛
    'CL1': {'stage': 'round_of_16', 'order': 2},
    'CLQ': {'stage': 'quarterfinal', 'order': 3},
    'CLS': {'stage': 'semifinal', 'order': 4},
    'CLF': {'stage': 'final', 'order': 5},

    # 欧联杯
    'EL': {'stage': 'league_phase', 'order': 1, 'is_group': True},
    'ELG': {'stage': 'group', 'order': 1, 'is_group': True},
    'EL1': {'stage': 'round_of_16', 'order': 2},
    'ELQ': {'stage': 'quarterfinal', 'order': 3},
    'ELS': {'stage': 'semifinal', 'order': 4},
    'ELF': {'stage': 'final', 'order': 5},

    # 欧协杯
    'EC': {'stage': 'league_phase', 'order': 1, 'is_group': True},
    'ECG': {'stage': 'group', 'order': 1, 'is_group': True},
    'EC1': {'stage': 'round_of_16', 'order': 2},
    'ECQ': {'stage': 'quarterfinal', 'order': 3},
    'ECS': {'stage': 'semifinal', 'order': 4},
    'ECF': {'stage': 'final', 'order': 5},

    # 足总杯 - 用数字表示轮次
    'FA_R1': {'stage': 'first_round', 'order': 1},
    'FA_R2': {'stage': 'second_round', 'order': 2},
    'FA_R3': {'stage': 'third_round', 'order': 3},
    'FA_R4': {'stage': 'fourth_round', 'order': 4},
    'FA_R5': {'stage': 'fifth_round', 'order': 5},
    'FA_QF': {'stage': 'quarterfinal', 'order': 6},
    'FA_SF': {'stage': 'semifinal', 'order': 7},
    'FA_F': {'stage': 'final', 'order': 8},

    # 英格兰联赛杯
    'LC_R1': {'stage': 'first_round', 'order': 1},
    'LC_R2': {'stage': 'second_round', 'order': 2},
    'LC_R3': {'stage': 'third_round', 'order': 3},
    'LC_R4': {'stage': 'fourth_round', 'order': 4},
    'LC_R5': {'stage': 'fifth_round', 'order': 5},
    'LC_QF': {'stage': 'quarterfinal', 'order': 6},
    'LC_SF': {'stage': 'semifinal', 'order': 7, 'has_leg': True},
    'LC_F': {'stage': 'final', 'order': 8},

    # 德国杯
    'DFB_R1': {'stage': 'first_round', 'order': 1},
    'DFB_R2': {'stage': 'second_round', 'order': 2},
    'DFB_R3': {'stage': 'third_round', 'order': 3},
    'DFB_QF': {'stage': 'quarterfinal', 'order': 4},
    'DFB_SF': {'stage': 'semifinal', 'order': 5},
    'DFB_F': {'stage': 'final', 'order': 6},

    # 西班牙国王杯
    'CD_R1': {'stage': 'first_round', 'order': 1},
    'CD_R2': {'stage': 'second_round', 'order': 2},
    'CD_R3': {'stage': 'third_round', 'order': 3},
    'CD_R4': {'stage': 'fourth_round', 'order': 4},
    'CD_R5': {'stage': 'fifth_round', 'order': 5},
    'CD_QF': {'stage': 'quarterfinal', 'order': 6},
    'CD_SF': {'stage': 'semifinal', 'order': 7, 'has_leg': True},
    'CD_F': {'stage': 'final', 'order': 8},

    # 意大利杯
    'CI_R1': {'stage': 'first_round', 'order': 1},
    'CI_R2': {'stage': 'second_round', 'order': 2},
    'CI_R3': {'stage': 'third_round', 'order': 3},
    'CI_R4': {'stage': 'fourth_round', 'order': 4},
    'CI_QF': {'stage': 'quarterfinal', 'order': 5},
    'CI_SF': {'stage': 'semifinal', 'order': 6, 'has_leg': True},
    'CI_F': {'stage': 'final', 'order': 7},

    # 法国杯
    'CF_R7': {'stage': 'round_of_64', 'order': 1},
    'CF_R8': {'stage': 'round_of_32', 'order': 2},
    'CF_R9': {'stage': 'round_of_16', 'order': 3},
    'CF_QF': {'stage': 'quarterfinal', 'order': 4},
    'CF_SF': {'stage': 'semifinal', 'order': 5},
    'CF_F': {'stage': 'final', 'order': 6},

    # 默认
    'EC': {'stage': 'unknown', 'order': 0},  # 英格兰杯赛通用代码
}

# 标准输出字段
OUTPUT_COLUMNS = [
    'Div',           # 原始Div代码保留
    'Season',        # 赛季
    'Stage',         # 标准阶段名称
    'StageOrder',    # 阶段排序
    'GroupName',     # 小组名(A,B,C...)
    'GroupRound',    # 小组内轮次
    'Leg',           # 回合(1或2)
    'Date',          # 日期
    'Time',          # 时间
    'HomeTeam',      # 主队
    'AwayTeam',      # 客队
    'FTHG',          # 主队进球
    'FTAG',          # 客队进球
    'ETHG',          # 加时主队进球
    'ETAG',          # 加时客队进球
    'PTHG',          # 点球主队进球
    'PTAG',          # 点球客队进球
    'FTR',           # 结果(H/D/A)
    'Venue',         # 场地
    'Attendance',    # 观众数
    'Referee',       # 裁判
    'Status'         # 状态
]

def parse_season_from_filename(filename):
    """从文件名提取赛季"""
    # fa_cup_2024-2025.csv -> 2024-2025
    # champions_league_2024-25.csv -> 2024-2025
    parts = filename.replace('.csv', '').split('_')
    for part in parts:
        if '-' in part and len(part) >= 7:
            # 处理 2024-25 格式
            years = part.split('-')
            if len(years[1]) == 2:
                years[1] = years[0][:2] + years[1]
            return f"{years[0]}-{years[1]}"
    return 'unknown'

def infer_stage_from_data(row, filename):
    """根据数据推断阶段"""
    div = row.get('Div', '')

    # 直接映射
    if div in STAGE_MAPPING:
        return STAGE_MAPPING[div]

    # 根据文件名推断杯赛类型
    cup_type = None
    if 'fa_cup' in filename.lower():
        cup_type = 'FA'
    elif 'england_league_cup' in filename.lower() or 'efl_cup' in filename.lower():
        cup_type = 'LC'
    elif 'champions_league' in filename.lower():
        cup_type = 'CL'
    elif 'europa_league' in filename.lower():
        cup_type = 'EL'
    elif 'conference_league' in filename.lower():
        cup_type = 'EC'
    elif 'dfb_pokal' in filename.lower():
        cup_type = 'DFB'
    elif 'copa_del_rey' in filename.lower():
        cup_type = 'CD'
    elif 'italy_cup' in filename.lower() or 'coppa_italia' in filename.lower():
        cup_type = 'CI'
    elif 'coupe_de_france' in filename.lower():
        cup_type = 'CF'

    # 如果Div是EC且是足总杯文件
    if div == 'EC' and cup_type == 'FA':
        return {'stage': 'unknown_round', 'order': 0}

    # 默认返回
    return {'stage': 'unknown', 'order': 0}

def convert_cup_csv(input_path, output_path):
    """转换单个杯赛CSV文件"""
    filename = os.path.basename(input_path)
    season = parse_season_from_filename(filename)

    print(f"处理: {filename} -> 赛季: {season}")

    try:
        # 读取原始CSV
        df = pd.read_csv(input_path, encoding='utf-8', on_bad_lines='skip')
    except:
        try:
            df = pd.read_csv(input_path, encoding='latin-1', on_bad_lines='skip')
        except Exception as e:
            print(f"  无法读取: {e}")
            return

    if df.empty:
        print(f"  文件为空")
        return

    # 创建新的DataFrame
    output_data = []

    for idx, row in df.iterrows():
        # 推断阶段
        stage_info = infer_stage_from_data(row.to_dict(), filename)

        # 构建新行
        new_row = {
            'Div': row.get('Div', ''),
            'Season': season,
            'Stage': stage_info['stage'],
            'StageOrder': stage_info['order'],
            'GroupName': '',  # 小组赛需要额外处理
            'GroupRound': '',
            'Leg': '',
            'Date': row.get('Date', ''),
            'Time': row.get('Time', ''),
            'HomeTeam': row.get('HomeTeam', ''),
            'AwayTeam': row.get('AwayTeam', ''),
            'FTHG': row.get('FTHG', ''),
            'FTAG': row.get('FTAG', ''),
            'ETHG': '',  # 加时赛进球需要从其他字段提取
            'ETAG': '',
            'PTHG': '',
            'PTAG': '',
            'FTR': row.get('FTR', ''),
            'Venue': row.get('Venue', ''),
            'Attendance': row.get('Attendance', ''),
            'Referee': row.get('Referee', ''),
            'Status': row.get('Status', 'Finished')
        }

        # 处理小组赛
        if stage_info.get('is_group'):
            # 尝试从HomeTeam提取小组信息
            home_team = row.get('HomeTeam', '')
            # 欧冠小组赛格式: "Team (Country)"
            # 可以通过比赛顺序推断小组轮次

        output_data.append(new_row)

    # 写入新CSV
    output_df = pd.DataFrame(output_data, columns=OUTPUT_COLUMNS)
    output_df.to_csv(output_path, index=False, encoding='utf-8')
    print(f"  已转换 {len(output_data)} 条记录")

def process_all_cups():
    """处理所有杯赛目录"""
    base_path = 'd:/football_tools/data'

    cup_dirs = [
        '02_europe_cups/fa_cup',
        '02_europe_cups/england_league_cup',
        '02_europe_cups/dfb_pokal',
        '02_europe_cups/copa_del_rey',
        '02_europe_cups/italy_cup',
        '02_europe_cups/coupe_de_france',
        '02_europe_cups/austria_cup',
        '03_european_competitions/champions_league',
        '03_european_competitions/europa_league',
        '03_european_competitions/conference_league',
    ]

    output_base = 'd:/football_tools/data/cups_standardized'
    os.makedirs(output_base, exist_ok=True)

    for cup_dir in cup_dirs:
        full_path = os.path.join(base_path, cup_dir)
        if not os.path.exists(full_path):
            print(f"目录不存在: {full_path}")
            continue

        # 创建输出目录
        cup_name = os.path.basename(cup_dir)
        output_dir = os.path.join(output_base, cup_name)
        os.makedirs(output_dir, exist_ok=True)

        # 处理每个CSV文件
        for filename in os.listdir(full_path):
            if filename.endswith('.csv') and not filename.endswith('_all.csv'):
                input_path = os.path.join(full_path, filename)
                output_path = os.path.join(output_dir, filename)
                convert_cup_csv(input_path, output_path)

if __name__ == '__main__':
    process_all_cups()
    print("\n所有杯赛CSV已标准化完成!")