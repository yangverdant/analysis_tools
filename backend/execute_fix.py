"""
执行赛季命名修复和重复数据清理
"""

import sqlite3
import sys
sys.stdout.reconfigure(encoding='utf-8')

DB_PATH = 'data/football_v2.db'

def main():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    print('=' * 80)
    print('开始修复赛季命名...')
    print('=' * 80)

    # 1. 先合并瑞典超的重复赛季
    print('\n步骤1: 合并瑞典超重复赛季...')

    # 2023赛季: season_id=2 和 194
    print('  合并2023赛季 (season_id=194 → 2)...')
    cursor.execute("UPDATE matches SET season_id = 2 WHERE season_id = 194")
    cursor.execute("DELETE FROM seasons WHERE season_id = 194")
    print('  ✓ 完成')

    # 2024赛季: season_id=3 和 193
    print('  合并2024赛季 (season_id=193 → 3)...')
    cursor.execute("UPDATE matches SET season_id = 3 WHERE season_id = 193")
    cursor.execute("DELETE FROM seasons WHERE season_id = 193")
    print('  ✓ 完成')

    # 2. 删除瑞典超season_id=5的重复数据
    print('\n步骤2: 删除瑞典超season_id=5的重复数据...')

    # 获取要删除的match_id
    cursor.execute('''
        SELECT m.match_id
        FROM matches m
        LEFT JOIN leagues l ON m.league_id = l.league_id
        WHERE (l.name_en LIKE '%Allsvenskan%' OR l.name_cn LIKE '%瑞典%')
        AND m.season_id = 5
    ''')
    to_delete = [row[0] for row in cursor.fetchall()]
    print(f"  找到 {len(to_delete)} 条重复记录")

    for match_id in to_delete:
        cursor.execute(f"DELETE FROM matches WHERE match_id = '{match_id}'")
    print(f"  ✓ 已删除 {len(to_delete)} 条重复记录")

    cursor.execute("DELETE FROM seasons WHERE season_id = 5")
    print('  ✓ 已删除空赛季记录 season_id=5')

    # 3. 更新赛季命名（不跨年联赛）
    print('\n步骤3: 更新赛季命名...')

    season_fixes = [
        # 瑞典超 - 现在只有season_id=2,3,4
        (2, '2023-24', '2023'),
        (3, '2024-25', '2024'),
        (4, '2025-26', '2025'),
        # 挪超
        (23, '2023-24', '2023'),
        (24, '2024-25', '2024'),
        (25, '2025-26', '2025'),
        (26, '2026-27', '2026'),
        # 芬超
        (103, '2023-24', '2023'),
        (104, '2024-25', '2024'),
        (105, '2025-26', '2025'),
        (106, '2026-27', '2026'),
        # 巴甲
        (8, '2026-2026', '2026'),
        # J联赛
        (32, '2025-26', '2025'),
        # K联赛
        (37, '2025-26', '2025'),
    ]

    for season_id, old_name, new_name in season_fixes:
        try:
            cursor.execute(f"UPDATE seasons SET season_name = '{new_name}' WHERE season_id = {season_id}")
            print(f"  ✓ season_id={season_id}: '{old_name}' → '{new_name}'")
        except Exception as e:
            print(f"  ✗ season_id={season_id}: {e}")

    # 4. 更新matches表中的match_id
    print('\n步骤4: 更新match_id中的赛季部分...')

    for season_id, old_name, new_name in season_fixes:
        cursor.execute(f"""
            UPDATE matches
            SET match_id = REPLACE(match_id, '_{old_name}_', '_{new_name}_')
            WHERE season_id = {season_id}
        """)

    print('  ✓ match_id更新完成')

    # 提交更改
    conn.commit()

    # 5. 验证修复结果
    print('\n' + '=' * 80)
    print('验证修复结果...')
    print('=' * 80)

    # 瑞典超
    cursor.execute('''
        SELECT DISTINCT s.season_id, s.season_name, COUNT(m.match_id) as match_count
        FROM seasons s
        LEFT JOIN matches m ON s.season_id = m.season_id
        LEFT JOIN leagues l ON m.league_id = l.league_id
        WHERE l.name_en LIKE '%Allsvenskan%' OR l.name_cn LIKE '%瑞典%'
        GROUP BY s.season_id, s.season_name
        ORDER BY s.season_name
    ''')
    rows = cursor.fetchall()

    print('\n瑞典超赛季命名（修复后）:')
    for row in rows:
        status = '✓' if '-' not in str(row[1]) else '✗'
        print(f"  {status} season_id={row[0]}, season_name='{row[1]}', 比赛数={row[2]}")

    # 挪超
    cursor.execute('''
        SELECT DISTINCT s.season_id, s.season_name, COUNT(m.match_id) as match_count
        FROM seasons s
        LEFT JOIN matches m ON s.season_id = m.season_id
        LEFT JOIN leagues l ON m.league_id = l.league_id
        WHERE l.name_en LIKE '%Eliteserien%' OR l.name_cn LIKE '%挪超%'
        GROUP BY s.season_id, s.season_name
        ORDER BY s.season_name
    ''')
    rows = cursor.fetchall()

    print('\n挪超赛季命名（修复后）:')
    for row in rows:
        status = '✓' if '-' not in str(row[1]) else '✗'
        print(f"  {status} season_id={row[0]}, season_name='{row[1]}', 比赛数={row[2]}")

    # 芬超
    cursor.execute('''
        SELECT DISTINCT s.season_id, s.season_name, COUNT(m.match_id) as match_count
        FROM seasons s
        LEFT JOIN matches m ON s.season_id = m.season_id
        LEFT JOIN leagues l ON m.league_id = l.league_id
        WHERE l.name_en LIKE '%Veikkausliiga%' OR l.name_cn LIKE '%芬超%'
        GROUP BY s.season_id, s.season_name
        ORDER BY s.season_name
    ''')
    rows = cursor.fetchall()

    print('\n芬超赛季命名（修复后）:')
    for row in rows:
        status = '✓' if '-' not in str(row[1]) else '✗'
        print(f"  {status} season_id={row[0]}, season_name='{row[1]}', 比赛数={row[2]}")

    # 检查是否还有重复
    cursor.execute('''
        SELECT m.match_date, m.home_team_id, m.away_team_id, COUNT(*) as count
        FROM matches m
        LEFT JOIN leagues l ON m.league_id = l.league_id
        WHERE l.name_en LIKE '%Allsvenskan%' OR l.name_cn LIKE '%瑞典%'
        GROUP BY m.match_date, m.home_team_id, m.away_team_id
        HAVING count > 1
    ''')
    duplicates = cursor.fetchall()

    print(f'\n瑞典超重复比赛检查: {len(duplicates)} 组')

    conn.close()
    print('\n✓ 修复完成！')


if __name__ == '__main__':
    main()