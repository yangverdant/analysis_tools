"""
同步new_data/teams目录下所有CSV文件的字段名
统一使用英文字段名: season, league_en, league_cn, team_en, team_cn
"""
import pandas as pd
import os

TEAMS_DIR = 'd:/football_tools/new_data/teams'

# 标准字段名（英文）
STANDARD_COLUMNS = {
    '赛季': 'season',
    '联赛英文名': 'league_en',
    '联赛中文名': 'league_cn',
    '英文球队名': 'team_en',
    '中文球队名': 'team_cn',
    'season': 'season',
    'league_en': 'league_en',
    'league_cn': 'league_cn',
    'team_en': 'team_en',
    'team_cn': 'team_cn'
}

def sync_csv_headers():
    """同步所有CSV文件的字段名"""

    files = [f for f in os.listdir(TEAMS_DIR) if f.endswith('.csv')]

    print("=" * 60)
    print("同步CSV文件字段名")
    print("=" * 60)

    updated_count = 0

    for filename in sorted(files):
        filepath = os.path.join(TEAMS_DIR, filename)

        try:
            # 读取文件
            df = pd.read_csv(filepath)

            # 检查是否需要更新
            current_cols = list(df.columns)
            needs_update = False

            for col in current_cols:
                if col in STANDARD_COLUMNS and col != STANDARD_COLUMNS[col]:
                    needs_update = True
                    break

            if needs_update:
                # 重命名列
                new_columns = []
                for col in current_cols:
                    if col in STANDARD_COLUMNS:
                        new_columns.append(STANDARD_COLUMNS[col])
                    else:
                        new_columns.append(col)

                df.columns = new_columns

                # 保存文件
                df.to_csv(filepath, index=False, encoding='utf-8-sig')

                print(f"  更新: {filename}")
                print(f"    旧字段: {current_cols}")
                print(f"    新字段: {new_columns}")
                updated_count += 1
            else:
                print(f"  跳过: {filename} (已是标准格式)")

        except Exception as e:
            print(f"  错误: {filename} - {e}")

    print("\n" + "=" * 60)
    print(f"完成! 更新了 {updated_count} 个文件")
    print("=" * 60)

def verify_sync():
    """验证同步结果"""

    files = [f for f in os.listdir(TEAMS_DIR) if f.endswith('.csv')]

    print("\n验证同步结果:")
    print("-" * 60)

    all_standard = True
    for filename in sorted(files):
        filepath = os.path.join(TEAMS_DIR, filename)
        try:
            df = pd.read_csv(filepath, nrows=1)
            cols = list(df.columns)

            is_standard = cols == ['season', 'league_en', 'league_cn', 'team_en', 'team_cn']
            status = "✓" if is_standard else "✗"
            print(f"  {status} {filename}: {cols}")

            if not is_standard:
                all_standard = False

        except Exception as e:
            print(f"  ✗ {filename}: 错误 - {e}")
            all_standard = False

    print("\n" + "=" * 60)
    if all_standard:
        print("所有文件字段名已统一!")
    else:
        print("部分文件仍有问题，请检查")
    print("=" * 60)

if __name__ == '__main__':
    sync_csv_headers()
    verify_sync()