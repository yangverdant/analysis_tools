"""
数据库数据质量检查和清理脚本
检查重复数据、脏数据、数据完整性
"""
import sqlite3
from pathlib import Path
from datetime import datetime

DB_PATH = Path('d:/football_tools/data/football_v2.db')

def check_duplicates(conn):
    """检查重复数据"""
    cursor = conn.cursor()
    print("\n" + "=" * 70)
    print("1. 重复数据检查")
    print("=" * 70)

    issues = []

    # 1.1 检查重复的match_id
    cursor.execute("""
        SELECT match_id, COUNT(*) as cnt
        FROM matches
        GROUP BY match_id
        HAVING COUNT(*) > 1
    """)
    dup_matches = cursor.fetchall()
    if dup_matches:
        print(f"  [警告] 发现 {len(dup_matches)} 个重复的match_id")
        issues.append(('duplicate_match_id', len(dup_matches)))
    else:
        print(f"  [OK] match_id 无重复")

    # 1.2 检查相同日期+主客队的比赛（可能是同一场比赛不同ID）
    cursor.execute("""
        SELECT m.match_date, t1.name_en as home, t2.name_en as away, COUNT(*) as cnt
        FROM matches m
        JOIN teams t1 ON m.home_team_id = t1.team_id
        JOIN teams t2 ON m.away_team_id = t2.team_id
        WHERE m.match_date != '' AND m.match_date IS NOT NULL
        GROUP BY m.match_date, m.home_team_id, m.away_team_id
        HAVING COUNT(*) > 1
    """)
    dup_date_teams = cursor.fetchall()
    if dup_date_teams:
        print(f"  [警告] 发现 {len(dup_date_teams)} 组相同日期+球队的比赛（可能重复）")
        issues.append(('duplicate_date_teams', len(dup_date_teams)))
        # 显示前5个
        for date, home, away, cnt in dup_date_teams[:5]:
            print(f"    {date}: {home} vs {away} ({cnt}条)")
    else:
        print(f"  [OK] 日期+球队组合无重复")

    # 1.3 检查重复的球队
    cursor.execute("""
        SELECT name_en, COUNT(*) as cnt
        FROM teams
        GROUP BY name_en
        HAVING COUNT(*) > 1
    """)
    dup_teams = cursor.fetchall()
    if dup_teams:
        print(f"  [警告] 发现 {len(dup_teams)} 个重复的球队名称")
        issues.append(('duplicate_teams', len(dup_teams)))
        for name, cnt in dup_teams[:10]:
            print(f"    {name}: {cnt}条")
    else:
        print(f"  [OK] 球队名称无重复")

    # 1.4 检查重复的联赛
    cursor.execute("""
        SELECT league_id, COUNT(*) as cnt
        FROM leagues
        GROUP BY league_id
        HAVING COUNT(*) > 1
    """)
    dup_leagues = cursor.fetchall()
    if dup_leagues:
        print(f"  [警告] 发现 {len(dup_leagues)} 个重复的联赛ID")
        issues.append(('duplicate_leagues', len(dup_leagues)))
    else:
        print(f"  [OK] 联赛ID无重复")

    return issues


def check_dirty_data(conn):
    """检查脏数据"""
    cursor = conn.cursor()
    print("\n" + "=" * 70)
    print("2. 脏数据检查")
    print("=" * 70)

    issues = []

    # 2.1 检查无效日期
    cursor.execute("""
        SELECT match_id, match_date FROM matches
        WHERE match_date IS NOT NULL AND match_date != ''
        AND (
            length(match_date) != 10
            OR match_date NOT LIKE '____-__-__'
            OR substr(match_date, 1, 4) < '1900'
            OR substr(match_date, 1, 4) > '2030'
        )
    """)
    invalid_dates = cursor.fetchall()
    if invalid_dates:
        print(f"  [警告] 发现 {len(invalid_dates)} 条无效日期")
        issues.append(('invalid_dates', len(invalid_dates)))
        for mid, date in invalid_dates[:5]:
            print(f"    {mid}: '{date}'")
    else:
        print(f"  [OK] 日期格式正常")

    # 2.2 检查无效比分
    cursor.execute("""
        SELECT match_id, home_goals, away_goals
        FROM matches
        WHERE (home_goals < 0 OR home_goals > 30)
           OR (away_goals < 0 OR away_goals > 30)
    """)
    invalid_scores = cursor.fetchall()
    if invalid_scores:
        print(f"  [警告] 发现 {len(invalid_scores)} 条异常比分")
        issues.append(('invalid_scores', len(invalid_scores)))
    else:
        print(f"  [OK] 比分范围正常")

    # 2.3 检查空球队名
    cursor.execute("""
        SELECT team_id, name_en FROM teams
        WHERE name_en IS NULL OR name_en = '' OR trim(name_en) = ''
    """)
    empty_names = cursor.fetchall()
    if empty_names:
        print(f"  [警告] 发现 {len(empty_names)} 个空球队名")
        issues.append(('empty_team_names', len(empty_names)))
    else:
        print(f"  [OK] 球队名不为空")

    # 2.4 检查无效的league_id引用
    cursor.execute("""
        SELECT DISTINCT m.league_id
        FROM matches m
        LEFT JOIN leagues l ON m.league_id = l.league_id
        WHERE l.league_id IS NULL
    """)
    invalid_league_refs = cursor.fetchall()
    if invalid_league_refs:
        print(f"  [警告] 发现 {len(invalid_league_refs)} 个无效联赛引用")
        issues.append(('invalid_league_refs', len(invalid_league_refs)))
        for (lid,) in invalid_league_refs[:10]:
            print(f"    league_id: {lid}")
    else:
        print(f"  [OK] 联赛引用有效")

    # 2.5 检查无效的team_id引用
    cursor.execute("""
        SELECT COUNT(*)
        FROM matches m
        LEFT JOIN teams t ON m.home_team_id = t.team_id
        WHERE t.team_id IS NULL
    """)
    invalid_home_refs = cursor.fetchone()[0]

    cursor.execute("""
        SELECT COUNT(*)
        FROM matches m
        LEFT JOIN teams t ON m.away_team_id = t.team_id
        WHERE t.team_id IS NULL
    """)
    invalid_away_refs = cursor.fetchone()[0]

    if invalid_home_refs > 0 or invalid_away_refs > 0:
        print(f"  [警告] 无效主队引用: {invalid_home_refs}, 无效客队引用: {invalid_away_refs}")
        issues.append(('invalid_team_refs', invalid_home_refs + invalid_away_refs))
    else:
        print(f"  [OK] 球队引用有效")

    # 2.6 检查无效的season_id引用
    cursor.execute("""
        SELECT COUNT(*)
        FROM matches m
        LEFT JOIN seasons s ON m.season_id = s.season_id
        WHERE s.season_id IS NULL
    """)
    invalid_season_refs = cursor.fetchone()[0]

    if invalid_season_refs > 0:
        print(f"  [警告] 无效赛季引用: {invalid_season_refs}")
        issues.append(('invalid_season_refs', invalid_season_refs))
    else:
        print(f"  [OK] 赛季引用有效")

    return issues


def check_data_integrity(conn):
    """检查数据完整性"""
    cursor = conn.cursor()
    print("\n" + "=" * 70)
    print("3. 数据完整性检查")
    print("=" * 70)

    issues = []

    # 3.1 比赛数据统计
    cursor.execute("SELECT COUNT(*) FROM matches")
    total_matches = cursor.fetchone()[0]
    print(f"\n  比赛总数: {total_matches}")

    # 3.2 缺失字段统计
    cursor.execute("""
        SELECT
            COUNT(CASE WHEN match_date IS NULL OR match_date = '' THEN 1 END) as no_date,
            COUNT(CASE WHEN match_time IS NULL OR match_time = '' THEN 1 END) as no_time,
            COUNT(CASE WHEN venue IS NULL OR venue = '' THEN 1 END) as no_venue,
            COUNT(CASE WHEN referee IS NULL OR referee = '' THEN 1 END) as no_referee,
            COUNT(CASE WHEN home_goals IS NULL THEN 1 END) as no_home_goals,
            COUNT(CASE WHEN away_goals IS NULL THEN 1 END) as no_away_goals
        FROM matches
    """)
    missing = cursor.fetchone()
    print(f"\n  缺失字段统计:")
    print(f"    缺失日期: {missing[0]}")
    print(f"    缺失时间: {missing[1]}")
    print(f"    缺失场馆: {missing[2]}")
    print(f"    缺失裁判: {missing[3]}")
    print(f"    缺失主队进球: {missing[4]}")
    print(f"    缺失客队进球: {missing[5]}")

    # 3.3 检查已结束比赛但没有比分
    cursor.execute("""
        SELECT COUNT(*) FROM matches
        WHERE status = 'finished'
        AND (home_goals IS NULL OR away_goals IS NULL)
    """)
    finished_no_score = cursor.fetchone()[0]
    if finished_no_score > 0:
        print(f"\n  [警告] {finished_no_score} 场已结束比赛缺少比分")
        issues.append(('finished_no_score', finished_no_score))
    else:
        print(f"\n  [OK] 已结束比赛比分完整")

    # 3.4 球队数据统计
    cursor.execute("SELECT COUNT(*) FROM teams")
    total_teams = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM teams WHERE team_type = 'club'")
    club_teams = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM teams WHERE team_type = 'national'")
    national_teams = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM teams WHERE team_type IS NULL OR team_type = ''")
    unknown_teams = cursor.fetchone()[0]

    print(f"\n  球队统计:")
    print(f"    总数: {total_teams}")
    print(f"    俱乐部: {club_teams}")
    print(f"    国家队: {national_teams}")
    print(f"    未分类: {unknown_teams}")

    # 3.5 联赛数据统计
    cursor.execute("SELECT COUNT(*) FROM leagues")
    total_leagues = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM seasons")
    total_seasons = cursor.fetchone()[0]

    print(f"\n  联赛统计:")
    print(f"    联赛数: {total_leagues}")
    print(f"    赛季数: {total_seasons}")

    return issues


def check_data_sources(conn):
    """检查数据来源"""
    cursor = conn.cursor()
    print("\n" + "=" * 70)
    print("4. 数据来源统计")
    print("=" * 70)

    cursor.execute("""
        SELECT source, COUNT(*) as cnt
        FROM matches
        GROUP BY source
        ORDER BY cnt DESC
    """)
    sources = cursor.fetchall()

    for source, cnt in sources:
        pct = cnt * 100.0 / sum(c for _, c in sources)
        print(f"  {source or '未知'}: {cnt} ({pct:.1f}%)")


def generate_report(conn, all_issues):
    """生成问题汇总报告"""
    cursor = conn.cursor()
    print("\n" + "=" * 70)
    print("5. 问题汇总")
    print("=" * 70)

    if not all_issues:
        print("\n  [OK] 数据质量良好，未发现严重问题")
        return

    print(f"\n  发现 {len(all_issues)} 类问题:")
    for issue_type, count in all_issues:
        print(f"    - {issue_type}: {count}")

    # 提供修复建议
    print("\n  修复建议:")
    for issue_type, count in all_issues:
        if issue_type == 'duplicate_teams':
            print(f"    - 重复球队: 运行清理脚本合并重复球队")
        elif issue_type == 'duplicate_date_teams':
            print(f"    - 相同日期球队: 检查并删除重复比赛")
        elif issue_type == 'invalid_league_refs':
            print(f"    - 无效联赛引用: 创建缺失的联赛记录")
        elif issue_type == 'finished_no_score':
            print(f"    - 已结束无比分: 从API补充比分数据")


def main():
    print("=" * 70)
    print(f"数据库数据质量检查")
    print(f"数据库: {DB_PATH}")
    print(f"时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 70)

    conn = sqlite3.connect(DB_PATH, timeout=30.0)

    all_issues = []

    # 运行各项检查
    all_issues.extend(check_duplicates(conn))
    all_issues.extend(check_dirty_data(conn))
    all_issues.extend(check_data_integrity(conn))
    check_data_sources(conn)
    generate_report(conn, all_issues)

    conn.close()

    print("\n" + "=" * 70)
    print("检查完成!")
    print("=" * 70)


if __name__ == '__main__':
    main()
