"""
数据验证脚本
检查爬取的数据是否正确、完整、符合CSV字段要求
"""
import os
import pandas as pd
from datetime import datetime

DATA_DIR = 'd:/football_tools/data'

# 必需字段
REQUIRED_COLUMNS = ['Date', 'HomeTeam', 'AwayTeam', 'FTHG', 'FTAG', 'FTR']

# 可选但重要的字段
IMPORTANT_COLUMNS = ['Time', 'HTHG', 'HTAG', 'HTR', 'Referee', 'HS', 'AS', 'B365H', 'B365D', 'B365A']


def validate_csv_file(filepath):
    """验证单个CSV文件"""
    issues = []

    try:
        df = pd.read_csv(filepath, encoding='utf-8')
    except Exception as e:
        return [{'type': 'READ_ERROR', 'message': str(e)}]

    if df.empty:
        return [{'type': 'EMPTY', 'message': '文件为空'}]

    # 检查必需字段
    missing_required = [col for col in REQUIRED_COLUMNS if col not in df.columns]
    if missing_required:
        issues.append({
            'type': 'MISSING_REQUIRED',
            'message': f'缺少必需字段: {missing_required}'
        })

    # 检查数据完整性
    if 'Date' in df.columns:
        # 检查日期格式
        try:
            df['Date'] = pd.to_datetime(df['Date'], errors='coerce')
            invalid_dates = df['Date'].isna().sum()
            if invalid_dates > 0:
                issues.append({
                    'type': 'INVALID_DATE',
                    'message': f'{invalid_dates} 条日期格式错误'
                })
        except:
            pass

    # 检查比分数据
    if 'FTHG' in df.columns and 'FTAG' in df.columns:
        # 检查比分是否为数字
        invalid_scores = df[df['FTHG'].notna() & df['FTAG'].notna() &
                           (df['FTHG'].apply(lambda x: not isinstance(x, (int, float))) |
                            df['FTAG'].apply(lambda x: not isinstance(x, (int, float))))]
        if len(invalid_scores) > 0:
            issues.append({
                'type': 'INVALID_SCORE',
                'message': f'{len(invalid_scores)} 条比分数据格式错误'
            })

    # 检查结果字段
    if 'FTR' in df.columns:
        valid_results = ['H', 'D', 'A', None, '']
        invalid_results = df[~df['FTR'].isin(valid_results)]
        if len(invalid_results) > 0:
            issues.append({
                'type': 'INVALID_RESULT',
                'message': f'{len(invalid_results)} 条结果数据异常: {invalid_results["FTR"].unique()}'
            })

    return issues


def validate_all_leagues():
    """验证所有联赛数据"""
    print("=" * 60)
    print("数据验证报告")
    print("=" * 60)
    print(f"验证时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")

    leagues_dir = os.path.join(DATA_DIR, '01_leagues')
    if not os.path.exists(leagues_dir):
        print("联赛数据目录不存在")
        return

    total_files = 0
    valid_files = 0
    total_records = 0
    all_issues = []

    for country in os.listdir(leagues_dir):
        country_dir = os.path.join(leagues_dir, country)
        if not os.path.isdir(country_dir):
            continue

        for filename in os.listdir(country_dir):
            if not filename.endswith('.csv'):
                continue

            filepath = os.path.join(country_dir, filename)
            total_files += 1

            issues = validate_csv_file(filepath)

            if not issues:
                valid_files += 1
                try:
                    df = pd.read_csv(filepath, encoding='utf-8')
                    total_records += len(df)
                    print(f"[OK] {country}/{filename}: {len(df)} 条记录")
                except:
                    pass
            else:
                print(f"[ERROR] {country}/{filename}:")
                for issue in issues:
                    print(f"    - {issue['message']}")
                    all_issues.append({
                        'file': filepath,
                        **issue
                    })

    print("\n" + "=" * 60)
    print(f"验证完成:")
    print(f"  总文件数: {total_files}")
    print(f"  有效文件: {valid_files}")
    print(f"  问题文件: {total_files - valid_files}")
    print(f"  总记录数: {total_records}")

    if all_issues:
        print(f"\n发现 {len(all_issues)} 个问题，请检查！")

    return all_issues


def validate_data_integrity():
    """验证数据完整性"""
    print("\n" + "=" * 60)
    print("数据完整性检查")
    print("=" * 60)

    # 检查是否有重复比赛
    leagues_dir = os.path.join(DATA_DIR, '01_leagues')

    for country in os.listdir(leagues_dir):
        country_dir = os.path.join(leagues_dir, country)
        if not os.path.isdir(country_dir):
            continue

        for filename in os.listdir(country_dir):
            if not filename.endswith('.csv'):
                continue

            filepath = os.path.join(country_dir, filename)
            try:
                df = pd.read_csv(filepath, encoding='utf-8')
                if 'Date' in df.columns and 'HomeTeam' in df.columns and 'AwayTeam' in df.columns:
                    duplicates = df[df.duplicated(subset=['Date', 'HomeTeam', 'AwayTeam'], keep=False)]
                    if len(duplicates) > 0:
                        print(f"[WARN] {filename}: 发现 {len(duplicates)} 条重复记录")
            except:
                pass


if __name__ == '__main__':
    validate_all_leagues()
    validate_data_integrity()
