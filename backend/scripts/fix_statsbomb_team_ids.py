"""
修复statsbomb_shots表的team_id字段

从match_id解析球队信息，填充team_id和team_name
"""

import sqlite3
import re
from typing import Dict, Optional


def parse_match_id(match_id: str) -> Dict:
    """
    解析match_id获取球队信息

    match_id格式: la_liga_2019-2020_2020-02-15_barcelona_vs_getafe
    """
    parts = match_id.split('_')

    # 找到日期部分 (YYYY-MM-DD)
    date_idx = None
    for i, part in enumerate(parts):
        if re.match(r'\d{4}-\d{2}-\d{2}', part):
            date_idx = i
            break

    if date_idx is None:
        return {}

    # 日期后面的部分是球队名
    team_parts = parts[date_idx + 1:]

    # 找到 'vs' 分隔符
    vs_idx = None
    for i, part in enumerate(team_parts):
        if part == 'vs':
            vs_idx = i
            break

    if vs_idx is None:
        return {}

    # 主队名 (vs之前)
    home_team = '_'.join(team_parts[:vs_idx])
    # 客队名 (vs之后)
    away_team = '_'.join(team_parts[vs_idx + 1:])

    return {
        'home_team': home_team,
        'away_team': away_team
    }


def normalize_team_name(team_name: str) -> str:
    """标准化球队名"""
    # 常见映射
    mappings = {
        'barcelona': 'Barcelona',
        'real_madrid': 'Real Madrid',
        'atletico_madrid': 'Atletico Madrid',
        'getafe': 'Getafe',
        'valencia': 'Valencia',
        'sevilla': 'Sevilla',
        'real_sociedad': 'Real Sociedad',
        'athletic_bilbao': 'Athletic Bilbao',
        'villarreal': 'Villarreal',
        'real_betis': 'Real Betis',
        'levante': 'Levante',
        'alaves': 'Alaves',
        'osasuna': 'Osasuna',
        'granada': 'Granada',
        'mallorca': 'Mallorca',
        'leganes': 'Leganes',
        'espanyol': 'Espanyol',
        'celta_vigo': 'Celta Vigo',
        'eibar': 'Eibar',
    }

    normalized = team_name.lower().replace('_', ' ')
    return mappings.get(team_name.lower(), normalized.title())


def fix_team_ids(db_path: str):
    """修复team_id字段"""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # 获取所有需要修复的射门记录
    cursor.execute("""
        SELECT shot_id, match_id, location_x, location_y
        FROM statsbomb_shots
        WHERE team_id IS NULL
    """)
    shots = cursor.fetchall()

    print(f"需要修复的射门记录: {len(shots)}")

    # 获取teams表的映射
    cursor.execute("SELECT team_id, name_en, name_cn FROM teams")
    teams = {row['name_en'].lower(): row['team_id'] for row in cursor.fetchall()}

    # 添加中文映射
    for row in cursor.fetchall():
        if row['name_cn']:
            teams[row['name_cn'].lower()] = row['team_id']

    updated = 0

    for shot in shots:
        match_info = parse_match_id(shot['match_id'])
        if not match_info:
            continue

        home_team = match_info['home_team']
        away_team = match_info['away_team']

        # 根据射门位置判断是主队还是客队
        # location_x > 60 表示进攻方向朝右（主队进攻）
        # 简化判断：假设主队进攻方向朝右
        location_x = shot['location_x'] or 0

        if location_x > 60:
            team_name = normalize_team_name(home_team)
        else:
            team_name = normalize_team_name(away_team)

        # 查找team_id
        team_id = teams.get(team_name.lower())
        if team_id:
            cursor.execute("""
                UPDATE statsbomb_shots
                SET team_id = ?, team_name = ?
                WHERE shot_id = ?
            """, (team_id, team_name, shot['shot_id']))
            updated += 1

        if updated % 1000 == 0:
            conn.commit()
            print(f"已更新 {updated} 条记录...")

    conn.commit()
    print(f"完成! 共更新 {updated} 条记录")

    # 验证
    cursor.execute("SELECT COUNT(*) FROM statsbomb_shots WHERE team_id IS NOT NULL")
    with_team = cursor.fetchone()[0]
    print(f"现在有team_id的记录: {with_team}")

    conn.close()


def main():
    db_path = r"d:\football_tools\data\football_v2.db"

    print("修复statsbomb_shots表的team_id字段")
    print("=" * 60)

    # 测试解析
    test_match_id = "la_liga_2019-2020_2020-02-15_barcelona_vs_getafe"
    result = parse_match_id(test_match_id)
    print(f"\n测试解析: {test_match_id}")
    print(f"  主队: {result.get('home_team')}")
    print(f"  客队: {result.get('away_team')}")

    # 执行修复
    print("\n开始修复...")
    fix_team_ids(db_path)


if __name__ == "__main__":
    main()