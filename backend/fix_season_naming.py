"""
修复不跨年联赛的赛季命名

根据地理位置规则：
- 跨年联赛（欧洲主流）：使用 YYYY-YYYY 格式，如 2025-2026
- 不跨年联赛（北欧、南美、亚洲等）：使用 YYYY 格式，如 2025
"""

import sqlite3
import sys
sys.stdout.reconfigure(encoding='utf-8')

# 数据库路径
DB_PATH = 'data/football_v2.db'

# 不跨年联赛的国家列表（需要单年格式）
SAME_YEAR_COUNTRIES = [
    'Sweden',      # 瑞典超 4-11月
    'Norway',      # 挪超 4-11月
    'Finland',     # 芬超 4-10月
    'Iceland',     # 冰岛超 5-9月
    'Brazil',      # 巴甲 4-12月
    'Argentina',   # 阿甲 2-12月
    'Chile',       # 智利甲 2-11月
    'Colombia',    # 哥伦甲 1-12月
    'Mexico',      # 墨超 1-12月
    'USA',         # 美职联 2-10月
    'Japan',       # J联赛 2-12月
    'South Korea', # K联赛 3-11月
    'China',       # 中超 3-11月
]

# 丹麦超是跨年的（7月开始，次年5月结束）
# 澳超是跨年的（10月开始，次年5月结束）

def analyze_seasons():
    """分析所有联赛的赛季命名"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    print('=' * 80)
    print('联赛赛季命名分析')
    print('=' * 80)

    # 查询所有联赛及其赛季
    cursor.execute('''
        SELECT DISTINCT l.league_id, l.name_en, l.name_cn, l.country,
               s.season_id, s.season_name, COUNT(m.match_id) as match_count
        FROM leagues l
        LEFT JOIN matches m ON l.league_id = m.league_id
        LEFT JOIN seasons s ON m.season_id = s.season_id
        WHERE s.season_id IS NOT NULL
        GROUP BY l.league_id, l.name_en, s.season_id, s.season_name
        ORDER BY l.country, l.name_en, s.season_name
    ''')
    rows = cursor.fetchall()

    # 按国家分组
    from collections import defaultdict
    country_leagues = defaultdict(list)

    for row in rows:
        country = row['country'] or 'Unknown'
        country_leagues[country].append(row)

    # 分析每个国家
    issues = []

    for country in sorted(country_leagues.keys()):
        leagues = country_leagues[country]

        is_same_year_country = country in SAME_YEAR_COUNTRIES

        for row in leagues:
            season_name = row['season_name'] or ''

            # 检查格式是否正确
            has_cross_year_format = '-' in season_name

            if is_same_year_country and has_cross_year_format:
                # 不跨年联赛使用了跨年格式 - 错误
                issues.append({
                    'league_id': row['league_id'],
                    'league_name': row['name_en'],
                    'country': country,
                    'season_id': row['season_id'],
                    'season_name': season_name,
                    'match_count': row['match_count'],
                    'issue': 'should_be_same_year',
                    'correct_format': season_name.split('-')[0]  # 取第一部分作为单年
                })

    print(f'\n发现 {len(issues)} 个需要修复的赛季命名:')
    print('-' * 80)

    for issue in issues:
        print(f"  [{issue['country']}] {issue['league_name']}")
        print(f"    当前: {issue['season_name']} → 应改为: {issue['correct_format']}")
        print(f"    season_id: {issue['season_id']}, 比赛数: {issue['match_count']}")

    conn.close()
    return issues


def fix_seasons(issues, dry_run=True):
    """修复赛季命名"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    print('\n' + '=' * 80)
    print('修复SQL语句:')
    print('=' * 80)

    for issue in issues:
        old_name = issue['season_name']
        new_name = issue['correct_format']
        season_id = issue['season_id']

        # 更新seasons表
        sql = f"UPDATE seasons SET season_name = '{new_name}' WHERE season_id = {season_id};"
        print(sql)

        if not dry_run:
            cursor.execute(sql)

    # 同时需要更新matches表中match_id的赛季部分
    print('\n-- 更新matches表中的match_id')
    for issue in issues:
        old_name = issue['season_name']
        new_name = issue['correct_format']
        season_id = issue['season_id']

        # 更新match_id中的赛季部分
        sql = f"""
        UPDATE matches
        SET match_id = REPLACE(match_id, '_{old_name}_', '_{new_name}_')
        WHERE season_id = {season_id};
        """
        print(sql)

        if not dry_run:
            cursor.execute(sql)

    if not dry_run:
        conn.commit()
        print('\n✓ 数据库已更新')
    else:
        print('\n⚠ 仅显示SQL，未执行（dry_run=True）')

    conn.close()


def check_duplicates():
    """检查瑞典超的重复数据"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    print('\n' + '=' * 80)
    print('瑞典超重复数据检查')
    print('=' * 80)

    cursor.execute('''
        SELECT m.match_id, m.match_date, m.home_team_id, m.away_team_id,
               m.home_goals, m.away_goals, m.season_id,
               ht.name_en as home_team, at.name_en as away_team
        FROM matches m
        LEFT JOIN leagues l ON m.league_id = l.league_id
        LEFT JOIN teams ht ON m.home_team_id = ht.team_id
        LEFT JOIN teams at ON m.away_team_id = at.team_id
        WHERE l.name_en LIKE '%Allsvenskan%' OR l.name_cn LIKE '%瑞典%'
        ORDER BY m.match_date, m.home_team_id, m.away_team_id
    ''')
    rows = cursor.fetchall()

    from collections import defaultdict
    match_key_counts = defaultdict(list)

    for row in rows:
        key = f"{row['match_date']}_{row['home_team_id']}_{row['away_team_id']}"
        match_key_counts[key].append({
            'match_id': row['match_id'],
            'season_id': row['season_id'],
            'goals': f"{row['home_goals']}-{row['away_goals']}",
            'home_team': row['home_team'],
            'away_team': row['away_team']
        })

    duplicates = {k: v for k, v in match_key_counts.items() if len(v) > 1}

    print(f'\n发现重复比赛: {len(duplicates)} 组')

    to_delete = []
    for key, matches in duplicates.items():
        parts = key.split('_')
        date, home_id, away_id = parts[0], parts[1], parts[2]

        m1, m2 = matches[0], matches[1]

        print(f'\n日期: {date}')
        print(f'比赛: {m1["home_team"]} vs {m1["away_team"]}')

        for i, m in enumerate(matches, 1):
            print(f'  版本{i}: match_id={m["match_id"]}, season_id={m["season_id"]}, 比分={m["goals"]}')

        # 保留season_id较小的（较早导入的）
        if m1['season_id'] <= m2['season_id']:
            to_delete.append(m2['match_id'])
            print(f'  → 建议删除版本2')
        else:
            to_delete.append(m1['match_id'])
            print(f'  → 建议删除版本1')

    print(f'\n总计建议删除: {len(to_delete)} 条记录')

    conn.close()
    return to_delete


if __name__ == '__main__':
    # 1. 分析赛季命名问题
    issues = analyze_seasons()

    # 2. 检查重复数据
    to_delete = check_duplicates()

    # 3. 生成修复SQL（不执行）
    print('\n' + '=' * 80)
    print('如需执行修复，请运行:')
    print('  python fix_season_naming.py --execute')
    print('=' * 80)

    import sys
    if '--execute' in sys.argv:
        confirm = input('确认要执行修复吗？(yes/no): ')
        if confirm.lower() == 'yes':
            fix_seasons(issues, dry_run=False)
            print('\n修复完成！')
        else:
            print('已取消')
