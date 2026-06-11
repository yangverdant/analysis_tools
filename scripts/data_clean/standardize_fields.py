"""
CSV字段标准化工具 - 将所有CSV文件统一为标准格式
"""
import os
import csv
import json
from pathlib import Path
from collections import Counter

DATA_DIR = Path("D:/football_tools/data")
OUTPUT_DIR = Path("D:/football_tools/data/standardized")

# 标准字段映射 (原字段 -> 标准字段)
FIELD_MAPPING = {
    # 核心比赛信息
    'Date': 'match_date',
    'Time': 'match_time',
    'HomeTeam': 'home_team',
    'AwayTeam': 'away_team',
    'FTHG': 'home_goals',
    'FTAG': 'away_goals',
    'FTR': 'result',
    'Status': 'status',

    # 半场数据
    'HTHG': 'home_goals_ht',
    'HTAG': 'away_goals_ht',
    'HTR': 'result_ht',

    # 射门统计
    'HS': 'home_shots',
    'AS': 'away_shots',
    'HST': 'home_shots_target',
    'AST': 'away_shots_target',

    # 犯规统计
    'HF': 'home_fouls',
    'AF': 'away_fouls',
    'HC': 'home_corners',
    'AC': 'away_corners',
    'HY': 'home_yellow',
    'AY': 'away_yellow',
    'HR': 'home_red',
    'AR': 'away_red',

    # 其他比赛信息
    'Div': 'division',
    'Referee': 'referee',
    'Attendance': 'attendance',
    'Season': 'season',

    # 赔率 (使用Bet365作为默认)
    'B365H': 'home_odds',
    'B365D': 'draw_odds',
    'B365A': 'away_odds',

    # 备用赔率
    'MaxH': 'max_home_odds',
    'MaxD': 'max_draw_odds',
    'MaxA': 'max_away_odds',
    'AvgH': 'avg_home_odds',
    'AvgD': 'avg_draw_odds',
    'AvgA': 'avg_away_odds',

    # 大小球
    'B365>2.5': 'over_2_5_odds',
    'B365<2.5': 'under_2_5_odds',

    # 亚盘
    'AHh': 'asian_handicap',
    'B365AHH': 'ah_home_odds',
    'B365AHA': 'ah_away_odds',
}

# 标准字段列表 (按顺序)
STANDARD_FIELDS = [
    # 基本信息
    'match_date', 'match_time', 'status',
    'home_team', 'away_team',
    'home_goals', 'away_goals', 'result',

    # 半场
    'home_goals_ht', 'away_goals_ht', 'result_ht',

    # 统计
    'home_shots', 'away_shots',
    'home_shots_target', 'away_shots_target',
    'home_corners', 'away_corners',
    'home_fouls', 'away_fouls',
    'home_yellow', 'away_yellow',
    'home_red', 'away_red',

    # 赔率
    'home_odds', 'draw_odds', 'away_odds',
    'max_home_odds', 'max_draw_odds', 'max_away_odds',
    'avg_home_odds', 'avg_draw_odds', 'avg_away_odds',

    # 其他
    'division', 'season', 'league_id',
    'referee', 'attendance',
]

def get_file_info(file_path):
    """从文件路径提取联赛和赛季信息"""
    # 从文件名提取
    filename = file_path.name.replace('.csv', '')
    parts = filename.split('_')

    # 最后一部分通常是赛季
    season = parts[-1] if len(parts) > 1 else 'unknown'
    league_name = '_'.join(parts[:-1]) if len(parts) > 1 else filename

    # 从路径提取国家/地区
    path_parts = str(file_path).split('/')
    country = 'unknown'
    for part in path_parts:
        if part in ['england', 'spain', 'germany', 'italy', 'france',
                    'netherlands', 'portugal', 'belgium', 'turkey', 'greece',
                    'scotland', 'brazil', 'argentina', 'japan', 'china']:
            country = part
            break

    return {
        'league_name': league_name,
        'season': season,
        'country': country
    }

def convert_row(row, file_info):
    """转换单行数据"""
    new_row = {}

    # 映射字段
    for old_key, value in row.items():
        # 清理字段名
        old_key_clean = old_key.strip().replace('﻿', '')

        if old_key_clean in FIELD_MAPPING:
            new_key = FIELD_MAPPING[old_key_clean]
            # 处理空值
            if value == '' or value is None:
                new_row[new_key] = None
            else:
                new_row[new_key] = value

    # 添加文件信息
    if 'season' not in new_row or new_row['season'] is None:
        new_row['season'] = file_info['season']

    return new_row

def convert_csv_file(input_path, output_path=None):
    """转换单个CSV文件"""
    file_info = get_file_info(input_path)

    rows = []
    original_headers = []
    converted_count = 0

    try:
        with open(input_path, 'r', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)
            original_headers = reader.fieldnames or []

            for row in reader:
                new_row = convert_row(row, file_info)
                rows.append(new_row)
                converted_count += 1

    except Exception as e:
        return {'error': str(e), 'file': str(input_path)}

    # 写入标准格式
    if output_path is None:
        output_path = input_path  # 覆盖原文件

    # 确保输出目录存在
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, 'w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=STANDARD_FIELDS, extrasaction='ignore')
        writer.writeheader()
        writer.writerows(rows)

    return {
        'input': str(input_path),
        'output': str(output_path),
        'rows': converted_count,
        'original_fields': len(original_headers),
        'standard_fields': len(STANDARD_FIELDS)
    }

def batch_convert(dry_run=True, limit=None):
    """批量转换所有CSV文件"""
    # 扫描所有CSV文件
    csv_files = []
    for root, dirs, files in os.walk(DATA_DIR):
        # 跳过输出目录
        if 'standardized' in root:
            continue
        for f in files:
            if f.endswith('.csv'):
                csv_files.append(Path(root) / f)

    if limit:
        csv_files = csv_files[:limit]

    print(f"\n找到 {len(csv_files)} 个CSV文件")
    print(f"模式: {'预览模式 (不实际修改文件)' if dry_run else '转换模式'}")
    print("-" * 60)

    results = []
    success = 0
    errors = 0

    for i, file_path in enumerate(csv_files, 1):
        if dry_run:
            # 预览模式：只分析不转换
            try:
                with open(file_path, 'r', encoding='utf-8-sig') as f:
                    reader = csv.DictReader(f)
                    headers = reader.fieldnames or []
                    row_count = sum(1 for _ in reader)

                    # 检查字段匹配
                    matched = sum(1 for h in headers if h.strip().replace('﻿', '') in FIELD_MAPPING)
                    match_rate = matched / len(headers) * 100 if headers else 0

                    print(f"[{i:4}/{len(csv_files)}] {file_path.name}")
                    print(f"         字段: {len(headers)}, 匹配: {matched} ({match_rate:.1f}%), 行数: {row_count}")

                    success += 1
            except Exception as e:
                print(f"[{i:4}/{len(csv_files)}] {file_path.name} - 错误: {e}")
                errors += 1
        else:
            # 转换模式
            result = convert_csv_file(file_path)
            if 'error' in result:
                print(f"[{i:4}/{len(csv_files)}] ✗ {file_path.name} - {result['error']}")
                errors += 1
            else:
                print(f"[{i:4}/{len(csv_files)}] ✓ {file_path.name} - {result['rows']} 行")
                success += 1
            results.append(result)

    print("-" * 60)
    print(f"完成: 成功 {success}, 错误 {errors}")

    return results

def show_field_mapping():
    """显示字段映射表"""
    print("\n" + "="*60)
    print("CSV字段标准映射表")
    print("="*60)
    print("\n【原字段】 -> 【标准字段】\n")

    # 按类别分组显示
    categories = {
        '核心比赛信息': ['Date', 'Time', 'HomeTeam', 'AwayTeam', 'FTHG', 'FTAG', 'FTR', 'Status'],
        '半场数据': ['HTHG', 'HTAG', 'HTR'],
        '射门统计': ['HS', 'AS', 'HST', 'AST'],
        '犯规统计': ['HF', 'AF', 'HC', 'AC', 'HY', 'AY', 'HR', 'AR'],
        '比赛信息': ['Div', 'Referee', 'Attendance', 'Season'],
        '赔率数据': ['B365H', 'B365D', 'B365A', 'MaxH', 'MaxD', 'MaxA', 'AvgH', 'AvgD', 'AvgA'],
        '大小球': ['B365>2.5', 'B365<2.5'],
        '亚盘': ['AHh', 'B365AHH', 'B365AHA'],
    }

    for category, fields in categories.items():
        print(f"\n{category}:")
        for old in fields:
            new = FIELD_MAPPING.get(old, '未映射')
            print(f"  {old:15} -> {new}")

    print("\n" + "="*60)

if __name__ == '__main__':
    import sys

    if len(sys.argv) > 1:
        cmd = sys.argv[1]
        if cmd == 'preview':
            batch_convert(dry_run=True)
        elif cmd == 'convert':
            batch_convert(dry_run=False)
        elif cmd == 'mapping':
            show_field_mapping()
        elif cmd == 'test':
            batch_convert(dry_run=True, limit=10)
        else:
            print(f"未知命令: {cmd}")
    else:
        print("\nCSV字段标准化工具")
        print("="*40)
        print("用法:")
        print("  python standardize_fields.py preview   - 预览转换结果")
        print("  python standardize_fields.py convert   - 执行转换")
        print("  python standardize_fields.py mapping   - 显示字段映射")
        print("  python standardize_fields.py test      - 测试前10个文件")
        print("="*40)
