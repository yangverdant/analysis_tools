"""
数据库清理脚本
清理重复数据、脏数据、修复引用问题
"""
import sqlite3
from pathlib import Path
from datetime import datetime

DB_PATH = Path('d:/football_tools/data/football_v2.db')


def clean_duplicates(conn):
    """清理重复数据"""
    cursor = conn.cursor()
    print("\n" + "=" * 70)
    print("1. 清理重复数据")
    print("=" * 70)

    # 1.1 删除重复的match_id（保留最新的）
    cursor.execute("""
        DELETE FROM matches
        WHERE rowid NOT IN (
            SELECT MAX(rowid)
            FROM matches
            GROUP BY match_id
        )
    """)
    removed_matches = cursor.rowcount
    conn.commit()
    print(f"  删除重复match_id: {removed_matches} 条")

    # 1.2 清理相同日期+球队的重复比赛
    # 策略：保留有完整数据的记录（有比分、有场馆等）
    cursor.execute("""
        DELETE FROM matches
        WHERE rowid IN (
            SELECT m1.rowid
            FROM matches m1
            INNER JOIN matches m2 ON m1.match_date = m2.match_date
                AND m1.home_team_id = m2.home_team_id
                AND m1.away_team_id = m2.away_team_id
            WHERE m1.rowid < m2.rowid
        )
    """)
    removed_dup_date = cursor.rowcount
    conn.commit()
    print(f"  删除重复日期+球队比赛: {removed_dup_date} 条")

    # 1.3 合并重复球队（保留ID最小的）
    cursor.execute("""
        SELECT name_en, MIN(team_id) as keep_id
        FROM teams
        GROUP BY name_en
        HAVING COUNT(*) > 1
    """)
    dup_teams = cursor.fetchall()

    merged = 0
    for name_en, keep_id in dup_teams:
        # 更新matches中的引用
        cursor.execute("""
            UPDATE matches SET home_team_id = ?
            WHERE home_team_id IN (
                SELECT team_id FROM teams WHERE name_en = ? AND team_id != ?
            )
        """, (keep_id, name_en, keep_id))

        cursor.execute("""
            UPDATE matches SET away_team_id = ?
            WHERE away_team_id IN (
                SELECT team_id FROM teams WHERE name_en = ? AND team_id != ?
            )
        """, (keep_id, name_en, keep_id))

        # 删除重复球队
        cursor.execute("""
            DELETE FROM teams
            WHERE name_en = ? AND team_id != ?
        """, (name_en, keep_id))

        merged += cursor.rowcount

    conn.commit()
    print(f"  合并重复球队: {merged} 个")


def clean_dirty_data(conn):
    """清理脏数据"""
    cursor = conn.cursor()
    print("\n" + "=" * 70)
    print("2. 清理脏数据")
    print("=" * 70)

    # 2.1 删除无效日期的比赛（2031年等明显错误）
    cursor.execute("""
        DELETE FROM matches
        WHERE match_date > '2030-12-31'
           OR match_date < '1900-01-01'
           OR length(match_date) != 10
    """)
    removed_dates = cursor.rowcount
    conn.commit()
    print(f"  删除无效日期比赛: {removed_dates} 条")

    # 2.2 修正异常比分（设为NULL）
    cursor.execute("""
        UPDATE matches
        SET home_goals = NULL
        WHERE home_goals < 0 OR home_goals > 30
    """)

    cursor.execute("""
        UPDATE matches
        SET away_goals = NULL
        WHERE away_goals < 0 OR away_goals > 30
    """)
    conn.commit()
    print(f"  修正异常比分: {cursor.rowcount} 条")

    # 2.3 清理空字符串为NULL
    cursor.execute("UPDATE teams SET name_cn = NULL WHERE name_cn = ''")
    cursor.execute("UPDATE teams SET country = NULL WHERE country = ''")
    cursor.execute("UPDATE leagues SET name_cn = NULL WHERE name_cn = ''")
    conn.commit()
    print(f"  清理空字符串字段")


def fix_references(conn):
    """修复引用问题"""
    cursor = conn.cursor()
    print("\n" + "=" * 70)
    print("3. 修复引用问题")
    print("=" * 70)

    # 3.1 创建缺失的联赛记录
    cursor.execute("""
        SELECT DISTINCT m.league_id
        FROM matches m
        LEFT JOIN leagues l ON m.league_id = l.league_id
        WHERE l.league_id IS NULL AND m.league_id IS NOT NULL
    """)
    missing_leagues = cursor.fetchall()

    for (league_id,) in missing_leagues:
        cursor.execute("""
            INSERT OR IGNORE INTO leagues (league_id, name_en, name_cn, competition_type, country)
            VALUES (?, ?, ?, 'league', 'Unknown')
        """, (league_id, f'League {league_id}', f'联赛{league_id}'))

    conn.commit()
    print(f"  创建缺失联赛: {len(missing_leagues)} 个")

    # 3.2 创建缺失的球队记录
    cursor.execute("""
        SELECT DISTINCT m.home_team_id
        FROM matches m
        LEFT JOIN teams t ON m.home_team_id = t.team_id
        WHERE t.team_id IS NULL AND m.home_team_id IS NOT NULL
    """)
    missing_home = cursor.fetchall()

    cursor.execute("""
        SELECT DISTINCT m.away_team_id
        FROM matches m
        LEFT JOIN teams t ON m.away_team_id = t.team_id
        WHERE t.team_id IS NULL AND m.away_team_id IS NOT NULL
    """)
    missing_away = cursor.fetchall()

    missing_teams = set(missing_home + missing_away)

    for (team_id,) in missing_teams:
        cursor.execute("""
            INSERT OR IGNORE INTO teams (team_id, name_en, name_cn, country, team_type)
            VALUES (?, ?, '', 'Unknown', 'club')
        """, (team_id, f'Team {team_id}'))

    conn.commit()
    print(f"  创建缺失球队: {len(missing_teams)} 个")

    # 3.3 创建缺失的赛季记录
    cursor.execute("""
        SELECT DISTINCT m.league_id, m.match_date
        FROM matches m
        LEFT JOIN seasons s ON m.season_id = s.season_id
        WHERE s.season_id IS NULL AND m.match_date IS NOT NULL AND m.match_date != ''
    """)
    matches_without_season = cursor.fetchall()

    # 按联赛+年份创建赛季
    seasons_created = set()
    created_count = 0

    for league_id, match_date in matches_without_season:
        if not match_date or len(match_date) < 4:
            continue

        year = match_date[:4]
        key = (league_id, year)

        if key not in seasons_created:
            seasons_created.add(key)

            # 检查是否已存在
            cursor.execute("""
                SELECT season_id FROM seasons
                WHERE league_id = ? AND season_name = ?
            """, (league_id, year))
            existing = cursor.fetchone()

            if not existing:
                cursor.execute("""
                    INSERT INTO seasons (season_name, league_id)
                    VALUES (?, ?)
                """, (year, league_id))
                created_count += 1

    conn.commit()
    print(f"  创建缺失赛季: {created_count} 个")

    # 3.4 更新matches中的season_id
    cursor.execute("""
        UPDATE matches
        SET season_id = (
            SELECT s.season_id
            FROM seasons s
            WHERE s.league_id = matches.league_id
            AND s.season_name = substr(matches.match_date, 1, 4)
        )
        WHERE season_id IS NULL OR season_id NOT IN (SELECT season_id FROM seasons)
    """)
    updated_seasons = cursor.rowcount
    conn.commit()
    print(f"  更新赛季引用: {updated_seasons} 条")


def clean_finished_without_score(conn):
    """处理已结束但无比分的比赛"""
    cursor = conn.cursor()
    print("\n" + "=" * 70)
    print("4. 处理已结束无比分比赛")
    print("=" * 70)

    # 将已结束但无比分的比赛状态改为scheduled（待补充数据）
    cursor.execute("""
        UPDATE matches
        SET status = 'scheduled'
        WHERE status = 'finished'
        AND (home_goals IS NULL OR away_goals IS NULL)
    """)
    updated = cursor.rowcount
    conn.commit()
    print(f"  将无比分的已结束比赛改为scheduled: {updated} 条")


def optimize_database(conn):
    """优化数据库"""
    cursor = conn.cursor()
    print("\n" + "=" * 70)
    print("5. 优化数据库")
    print("=" * 70)

    # VACUUM
    print("  执行VACUUM...")
    cursor.execute("VACUUM")
    print("  VACUUM完成")

    # ANALYZE
    print("  执行ANALYZE...")
    cursor.execute("ANALYZE")
    print("  ANALYZE完成")


def generate_summary(conn):
    """生成清理后统计"""
    cursor = conn.cursor()
    print("\n" + "=" * 70)
    print("清理后数据统计")
    print("=" * 70)

    cursor.execute("SELECT COUNT(*) FROM matches")
    matches = cursor.fetchone()[0]
    print(f"  比赛总数: {matches}")

    cursor.execute("SELECT COUNT(*) FROM teams")
    teams = cursor.fetchone()[0]
    print(f"  球队总数: {teams}")

    cursor.execute("SELECT COUNT(*) FROM leagues")
    leagues = cursor.fetchone()[0]
    print(f"  联赛总数: {leagues}")

    cursor.execute("SELECT COUNT(*) FROM seasons")
    seasons = cursor.fetchone()[0]
    print(f"  赛季总数: {seasons}")


def main():
    print("=" * 70)
    print(f"数据库清理脚本")
    print(f"数据库: {DB_PATH}")
    print(f"时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 70)

    conn = sqlite3.connect(DB_PATH, timeout=30.0)

    # 先备份数据库（在内存中保留清理前的状态）
    print("\n开始清理...")

    try:
        clean_duplicates(conn)
        clean_dirty_data(conn)
        fix_references(conn)
        clean_finished_without_score(conn)
        optimize_database(conn)
        generate_summary(conn)

        print("\n" + "=" * 70)
        print("清理完成!")
        print("=" * 70)

    except Exception as e:
        print(f"\n清理过程中出错: {e}")
        conn.rollback()

    conn.close()


if __name__ == '__main__':
    main()
