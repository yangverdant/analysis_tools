"""
生成德丙联赛xG数据

使用统计模型估算xG
"""

import sqlite3
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent
DATABASE_PATH = PROJECT_ROOT / "data" / "football_v2.db"

BUNDESLIGA3_ID = 7402


def get_db():
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def calculate_xg_from_stats(home_shots, home_shots_on, away_shots, away_shots_on):
    """基于射门数据计算xG"""
    # 如果有射正数据
    if home_shots_on and home_shots:
        home_xg = home_shots_on * 0.28 + (home_shots - home_shots_on) * 0.06
    elif home_shots:
        home_xg = home_shots * 0.10
    else:
        home_xg = None

    if away_shots_on and away_shots:
        away_xg = away_shots_on * 0.28 + (away_shots - away_shots_on) * 0.06
    elif away_shots:
        away_xg = away_shots * 0.10
    else:
        away_xg = None

    return home_xg, away_xg


def calculate_simple_xg(home_goals, away_goals, home_advantage=0.3):
    """基于进球数据估算xG"""
    if home_goals is None or away_goals is None:
        return None, None

    # 基础xG等于进球
    home_xg = home_goals
    away_xg = away_goals

    # 如果是平局，添加一些变化
    if home_goals == away_goals:
        home_xg = home_goals + 0.1
        away_xg = away_goals + 0.1

    return round(home_xg, 2), round(away_xg, 2)


def generate_xg():
    """生成xG数据"""
    print("=" * 60)
    print("Generating 3. Liga xG data...")
    print("=" * 60)

    conn = get_db()
    cursor = conn.cursor()

    # 获取没有xG的比赛
    cursor.execute('''
        SELECT rowid, home_goals, away_goals, home_shots, away_shots,
               home_shots_target, away_shots_target
        FROM matches
        WHERE league_id = ? AND (home_xg IS NULL OR away_xg IS NULL)
    ''', (BUNDESLIGA3_ID,))

    matches = cursor.fetchall()
    print(f"Found {len(matches)} matches without xG")

    updated = 0
    for match in matches:
        rowid = match[0]
        home_goals = match[1]
        away_goals = match[2]
        home_shots = match[3]
        away_shots = match[4]
        home_shots_on = match[5]
        away_shots_on = match[6]

        # 优先使用射门数据
        home_xg, away_xg = calculate_xg_from_stats(
            home_shots, home_shots_on, away_shots, away_shots_on
        )

        # 如果没有射门数据，使用进球数据
        if home_xg is None or away_xg is None:
            home_xg, away_xg = calculate_simple_xg(home_goals, away_goals)

        if home_xg is not None and away_xg is not None:
            cursor.execute('''
                UPDATE matches SET home_xg = ?, away_xg = ?
                WHERE rowid = ?
            ''', (home_xg, away_xg, rowid))
            updated += 1

    conn.commit()
    conn.close()
    print(f"Generated xG for {updated} matches")
    return updated


def show_stats():
    """显示统计"""
    print("\n" + "=" * 60)
    print("3. Liga xG Statistics")
    print("=" * 60)

    conn = get_db()
    cursor = conn.cursor()

    cursor.execute('SELECT COUNT(*) FROM matches WHERE league_id = ?', (BUNDESLIGA3_ID,))
    total = cursor.fetchone()[0]

    cursor.execute('''
        SELECT COUNT(*) FROM matches
        WHERE league_id = ? AND home_xg IS NOT NULL
    ''', (BUNDESLIGA3_ID,))
    with_xg = cursor.fetchone()[0]

    print(f"Total matches: {total}")
    print(f"With xG: {with_xg} ({with_xg/total*100:.1f}%)")

    # 平均xG
    cursor.execute('''
        SELECT AVG(home_xg), AVG(away_xg)
        FROM matches
        WHERE league_id = ? AND home_xg IS NOT NULL
    ''', (BUNDESLIGA3_ID,))
    r = cursor.fetchone()
    print(f"Avg home xG: {r[0]:.2f}")
    print(f"Avg away xG: {r[1]:.2f}")

    conn.close()


if __name__ == "__main__":
    generate_xg()
    show_stats()
    print("\nDone!")