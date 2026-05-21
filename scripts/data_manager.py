"""
数据管理工具 - 批量处理CSV数据
"""
import os
import csv
import json
from pathlib import Path
from collections import defaultdict

DATA_DIR = Path("D:/football_tools/data")

# 标准联赛CSV字段映射
STANDARD_LEAGUE_FIELDS = {
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
    'HF': 'home_fouls',
    'AF': 'away_fouls',
    'HC': 'home_corners',
    'AC': 'away_corners',
    'HY': 'home_yellow',
    'AY': 'away_yellow',
    'HR': 'home_red',
    'AR': 'away_red',
    'B365H': 'home_odds',
    'B365D': 'draw_odds',
    'B365A': 'away_odds',
    'Season': 'season',
    'Div': 'division'
}

# 标准杯赛CSV字段
STANDARD_CUP_FIELDS = [
    'match_date', 'match_time', 'stage', 'stage_round', 'group_name',
    'home_team', 'away_team', 'home_goals', 'away_goals',
    'home_goals_ht', 'away_goals_ht', 'home_goals_et', 'away_goals_et',
    'home_penalties', 'away_penalties', 'result', 'venue', 'attendance',
    'season', 'league_id'
]

def scan_all_csv_files():
    """扫描所有CSV文件"""
    csv_files = []
    for root, dirs, files in os.walk(DATA_DIR):
        for f in files:
            if f.endswith('.csv'):
                csv_files.append(Path(root) / f)
    return csv_files

def analyze_csv_structure(file_path):
    """分析单个CSV文件的结构"""
    try:
        with open(file_path, 'r', encoding='utf-8-sig') as f:
            reader = csv.reader(f)
            headers = next(reader)
            first_row = next(reader, None)

            return {
                'file': str(file_path),
                'headers': headers,
                'header_count': len(headers),
                'sample_row': first_row,
                'row_count': sum(1 for _ in reader) + 1  # +1 for first row
            }
    except Exception as e:
        return {'file': str(file_path), 'error': str(e)}

def get_file_category(file_path):
    """根据路径判断文件类型"""
    path_str = str(file_path)

    if '01_leagues' in path_str or '01_europe_leagues' in path_str:
        return 'league'
    elif '02_europe_cups' in path_str or 'cups' in path_str:
        return 'cup'
    elif '03_european_competitions' in path_str:
        return 'european'
    elif '04_international' in path_str:
        return 'international'
    elif '05_asia_leagues' in path_str:
        return 'asia'
    elif '06_south_america' in path_str:
        return 'south_america'
    elif '07_north_america' in path_str:
        return 'north_america'
    elif '08_africa' in path_str:
        return 'africa'
    else:
        return 'other'

def extract_league_season_from_filename(filename):
    """从文件名提取联赛和赛季"""
    # 格式: league_name_2024-2025.csv
    parts = filename.replace('.csv', '').split('_')
    if len(parts) >= 2:
        season = parts[-1]  # 最后一个是赛季
        league = '_'.join(parts[:-1])  # 其他部分是联赛名
        return league, season
    return filename.replace('.csv', ''), 'unknown'

def generate_data_report():
    """生成数据报告"""
    csv_files = scan_all_csv_files()

    report = {
        'total_files': len(csv_files),
        'by_category': defaultdict(int),
        'by_league': defaultdict(list),
        'issues': []
    }

    for file_path in csv_files:
        category = get_file_category(file_path)
        report['by_category'][category] += 1

        filename = file_path.name
        league, season = extract_league_season_from_filename(filename)
        report['by_league'][league].append({
            'season': season,
            'file': str(file_path),
            'category': category
        })

        # 检查文件结构
        info = analyze_csv_structure(file_path)
        if 'error' in info:
            report['issues'].append({
                'file': str(file_path),
                'error': info['error']
            })

    return report

def convert_league_csv_to_standard(input_file, output_file=None):
    """将联赛CSV转换为标准格式"""
    if output_file is None:
        output_file = input_file

    rows = []
    with open(input_file, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        original_headers = reader.fieldnames

        for row in reader:
            new_row = {}
            for old_key, new_key in STANDARD_LEAGUE_FIELDS.items():
                if old_key in row:
                    value = row[old_key]
                    # 处理空值
                    if value == '' or value == None:
                        new_row[new_key] = None
                    else:
                        new_row[new_key] = value

            # 保留原始数据中的赛季信息
            if 'season' not in new_row or new_row['season'] is None:
                league, season = extract_league_season_from_filename(input_file.name)
                new_row['season'] = season

            rows.append(new_row)

    # 写入标准格式
    standard_headers = list(STANDARD_LEAGUE_FIELDS.values())
    with open(output_file, 'w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=standard_headers)
        writer.writeheader()
        writer.writerows(rows)

    return len(rows)

def batch_convert_league_files():
    """批量转换联赛文件"""
    csv_files = scan_all_csv_files()
    converted = 0
    errors = []

    for file_path in csv_files:
        category = get_file_category(file_path)
        if category == 'league':
            try:
                count = convert_league_csv_to_standard(file_path)
                converted += 1
                print(f"✓ {file_path.name}: {count} rows")
            except Exception as e:
                errors.append({'file': str(file_path), 'error': str(e)})
                print(f"✗ {file_path.name}: {e}")

    return converted, errors

def validate_csv_data(file_path):
    """验证CSV数据完整性"""
    issues = []

    with open(file_path, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)

        for idx, row in enumerate(reader, start=2):
            # 检查必要字段
            required = ['Date', 'HomeTeam', 'AwayTeam']
            for field in required:
                if field not in row or row[field] == '':
                    issues.append({
                        'row': idx,
                        'issue': f"缺少必要字段: {field}"
                    })

            # 检查比分格式
            if 'FTHG' in row and row['FTHG'] != '':
                try:
                    int(row['FTHG'])
                except:
                    issues.append({
                        'row': idx,
                        'issue': f"主队比分格式错误: {row['FTHG']}"
                    })

    return issues

def list_all_leagues():
    """列出所有联赛"""
    report = generate_data_report()

    print("\n=== 数据统计 ===")
    print(f"总文件数: {report['total_files']}")

    print("\n=== 按类型分类 ===")
    for cat, count in sorted(report['by_category'].items()):
        print(f"{cat}: {count} 个文件")

    print("\n=== 按联赛分类 ===")
    for league, files in sorted(report['by_league'].items()):
        seasons = [f['season'] for f in files]
        print(f"{league}: {len(files)} 个赛季 ({min(seasons)} ~ {max(seasons)})")

    if report['issues']:
        print("\n=== 问题文件 ===")
        for issue in report['issues'][:10]:
            print(f"✗ {issue['file']}: {issue['error']}")

def interactive_menu():
    """交互式菜单"""
    while True:
        print("\n" + "="*50)
        print("📊 数据管理工具")
        print("="*50)
        print("1. 查看数据统计")
        print("2. 列出所有联赛")
        print("3. 分析单个文件")
        print("4. 验证数据完整性")
        print("5. 批量转换为标准格式")
        print("6. 查找特定联赛/赛季")
        print("0. 退出")
        print("="*50)

        choice = input("\n请选择操作: ").strip()

        if choice == '0':
            break
        elif choice == '1':
            report = generate_data_report()
            print(f"\n总文件数: {report['total_files']}")
            print(f"联赛文件: {report['by_category']['league']}")
            print(f"杯赛文件: {report['by_category']['cup']}")
        elif choice == '2':
            list_all_leagues()
        elif choice == '3':
            file_path = input("输入文件路径: ").strip()
            info = analyze_csv_structure(file_path)
            print(f"\n文件: {info['file']}")
            print(f"字段数: {info['header_count']}")
            print(f"数据行数: {info['row_count']}")
            print(f"字段列表: {info['headers'][:10]}...")
        elif choice == '4':
            file_path = input("输入文件路径: ").strip()
            issues = validate_csv_data(file_path)
            if issues:
                print(f"\n发现 {len(issues)} 个问题:")
                for issue in issues[:10]:
                    print(f"  行 {issue['row']}: {issue['issue']}")
            else:
                print("\n✓ 数据验证通过")
        elif choice == '5':
            print("\n开始批量转换...")
            converted, errors = batch_convert_league_files()
            print(f"\n完成: {converted} 个文件")
            if errors:
                print(f"错误: {len(errors)} 个")
        elif choice == '6':
            keyword = input("输入联赛名称关键词: ").strip().lower()
            report = generate_data_report()
            found = []
            for league, files in report['by_league'].items():
                if keyword in league.lower():
                    found.append((league, files))

            if found:
                print(f"\n找到 {len(found)} 个联赛:")
                for league, files in found:
                    print(f"\n{league}:")
                    for f in files:
                        print(f"  - {f['season']}: {Path(f['file']).name}")
            else:
                print("\n未找到匹配的联赛")

if __name__ == '__main__':
    interactive_menu()