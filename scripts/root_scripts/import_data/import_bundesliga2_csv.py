"""
从本地CSV文件导入德乙数据到数据库

CSV文件位置: data/01_europe_leagues/bundesliga_2/
"""

import sqlite3
import csv
import os
from pathlib import Path
from datetime import datetime

# 项目根目录
PROJECT_ROOT = Path(__file__).parent
DATABASE_PATH = PROJECT_ROOT / "data" / "football_v2.db"
CSV_DIR = PROJECT_ROOT / "data" / "01_europe_leagues" / "bundesliga_2"

# 德乙联赛ID
BUNDESLIGA_2_ID = 8

# 赛季ID映射 (根据数据库中的season_id)
SEASON_MAP = {
    '2000-2001': 13,
    '2001-2002': 14,
    '2002-2003': 15,
    '2003-2004': 16,
    '2004-2005': 17,
    '2005-2006': 18,
    '2006-2007': 19,
    '2007-2008': 20,
    '2008-2009': 21,
    '2009-2010': 22,
    '2010-2011': 23,
    '2011-2012': 24,
    '2012-2013': 25,
    '2013-2014': 26,
    '2014-2015': 27,
    '2015-2016': 28,
    '2016-2017': 29,
    '2017-2018': 30,
    '2018-2019': 31,
    '2019-2020': 32,
    '2020-2021': 33,
    '2021-2022': 34,
    '2022-2023': 35,
    '2023-2024': 36,
    '2024-2025': 125,
    '2025-2026': 126,
}


def get_db():
    """获取数据库连接"""
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def parse_date(date_str: str, season: str) -> str:
    """解析日期字符串为YYYY-MM-DD格式"""
    if not date_str:
        return None

    # 尝试多种格式
    try:
        # 格式1: DD/MM/YY
        if '/' in date_str:
            parts = date_str.split('/')
            day, month = int(parts[0]), int(parts[1])
            year = int(parts[2]) if len(parts) > 2 else None
            if year is not None:
                # 推断世纪
                if year >= 0 and year <= 26:
                    full_year = 2000 + year
                else:
                    full_year = 1900 + year
                return f"{full_year:04d}-{month:02d}-{day:02d}"

        # 格式2: YY-MM-DD
        if '-' in date_str and len(date_str.split('-')[0]) == 2:
            parts = date_str.split('-')
            year, month, day = int(parts[0]), int(parts[1]), int(parts[2])
            if year >= 0 and year <= 26:
                full_year = 2000 + year
            else:
                full_year = 1900 + year
            return f"{full_year:04d}-{month:02d}-{day:02d}"

        # 格式3: YYYY-MM-DD
        if '-' in date_str and len(date_str.split('-')[0]) == 4:
            return date_str

    except Exception as e:
        pass

    return None


def get_or_create_team(conn, team_name: str, country: str = 'Germany') -> int:
    """获取或创建球队，返回team_id"""
    cursor = conn.cursor()

    # 尝试查找球队
    cursor.execute('''
        SELECT team_id FROM teams
        WHERE name_en = ? OR name_cn = ? OR name_en LIKE ?
    ''', (team_name, team_name, f'%{team_name}%'))

    row = cursor.fetchone()
    if row:
        return row[0]

    # 创建新球队
    cursor.execute('''
        INSERT INTO teams (name_en, name_cn, country, created_at, updated_at)
        VALUES (?, '', ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
    ''', (team_name, country))

    return cursor.lastrowid


def import_csv_file(csv_path: Path, conn) -> dict:
    """导入单个CSV文件"""
    result = {
        'file': csv_path.name,
        'total': 0,
        'inserted': 0,
        'updated': 0,
        'skipped': 0,
        'errors': []
    }

    # 从文件名提取赛季
    filename = csv_path.stem  # e.g., bundesliga_2_2023-2024
    season_str = filename.replace('bundesliga_2_', '')
    season_id = SEASON_MAP.get(season_str)

    if not season_id:
        result['errors'].append(f"Unknown season: {season_str}")
        return result

    cursor = conn.cursor()

    try:
        with open(csv_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)

            for row in reader:
                result['total'] += 1

                try:
                    home_team = row.get('HomeTeam', '').strip()
                    away_team = row.get('AwayTeam', '').strip()

                    if not home_team or not away_team:
                        result['skipped'] += 1
                        continue

                    # 解析日期
                    date_str = row.get('Date', '')
                    match_date = parse_date(date_str, season_str)

                    if not match_date:
                        result['skipped'] += 1
                        continue

                    # 获取球队ID
                    home_team_id = get_or_create_team(conn, home_team)
                    away_team_id = get_or_create_team(conn, away_team)

                    # 比赛数据
                    match_time = row.get('Time', '')
                    home_goals = row.get('FTHG')
                    away_goals = row.get('FTAG')
                    ftr = row.get('FTR', '')  # H/D/A
                    status = 'finished' if home_goals and away_goals else 'scheduled'

                    # 尝试转换为整数
                    try:
                        home_goals = int(home_goals) if home_goals else None
                        away_goals = int(away_goals) if away_goals else None
                    except:
                        home_goals = None
                        away_goals = None

                    # 检查是否已存在
                    cursor.execute('''
                        SELECT match_id FROM matches
                        WHERE match_date = ? AND home_team_id = ? AND away_team_id = ?
                    ''', (match_date, home_team_id, away_team_id))

                    existing = cursor.fetchone()

                    if existing:
                        # 更新
                        cursor.execute('''
                            UPDATE matches SET
                                home_goals = COALESCE(?, home_goals),
                                away_goals = COALESCE(?, away_goals),
                                status = ?,
                                match_time = COALESCE(?, match_time),
                                season_id = ?,
                                updated_at = CURRENT_TIMESTAMP
                            WHERE match_id = ?
                        ''', (home_goals, away_goals, status, match_time or None, season_id, existing[0]))
                        result['updated'] += 1
                    else:
                        # 插入
                        cursor.execute('''
                            INSERT INTO matches (
                                match_date, match_time, home_team_id, away_team_id,
                                home_goals, away_goals, status, league_id, season_id,
                                result, source, created_at, updated_at
                            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'csv_import',
                                      CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                        ''', (match_date, match_time or None, home_team_id, away_team_id,
                              home_goals, away_goals, status, BUNDESLIGA_2_ID, season_id, ftr))
                        result['inserted'] += 1

                except Exception as e:
                    result['errors'].append(str(e))
                    result['skipped'] += 1

        conn.commit()

    except Exception as e:
        result['errors'].append(f"File error: {e}")

    return result


def main():
    """主函数"""
    print("=" * 60)
    print("从CSV导入德乙数据")
    print("=" * 60)

    conn = get_db()

    # 获取所有CSV文件
    csv_files = sorted(CSV_DIR.glob("bundesliga_2_*.csv"))
    # 排除 _all.csv
    csv_files = [f for f in csv_files if '_all' not in f.name]

    print(f"\n找到 {len(csv_files)} 个CSV文件")

    total_result = {
        'total': 0,
        'inserted': 0,
        'updated': 0,
        'skipped': 0
    }

    for csv_file in csv_files:
        print(f"\n处理: {csv_file.name}")
        result = import_csv_file(csv_file, conn)

        print(f"  总计: {result['total']}, 新增: {result['inserted']}, 更新: {result['updated']}, 跳过: {result['skipped']}")

        if result['errors']:
            print(f"  错误: {len(result['errors'])} 条")
            for err in result['errors'][:3]:
                print(f"    - {err}")

        total_result['total'] += result['total']
        total_result['inserted'] += result['inserted']
        total_result['updated'] += result['updated']
        total_result['skipped'] += result['skipped']

    conn.close()

    print("\n" + "=" * 60)
    print("导入统计")
    print("=" * 60)
    print(f"总记录: {total_result['total']}")
    print(f"新增: {total_result['inserted']}")
    print(f"更新: {total_result['updated']}")
    print(f"跳过: {total_result['skipped']}")

    # 最终统计
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute('SELECT COUNT(*) FROM matches WHERE league_id = ?', (BUNDESLIGA_2_ID,))
    match_count = cursor.fetchone()[0]
    print(f"\n德乙比赛总数: {match_count} 场")

    cursor.execute('''
        SELECT season_id, COUNT(*) as cnt
        FROM matches
        WHERE league_id = ?
        GROUP BY season_id
        ORDER BY season_id
    ''', (BUNDESLIGA_2_ID,))

    print("\n各赛季比赛数:")
    for row in cursor.fetchall():
        print(f"  season {row[0]}: {row[1]} 场")

    conn.close()
    print("\n导入完成！")


if __name__ == "__main__":
    main()
