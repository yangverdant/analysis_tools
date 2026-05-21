#!/usr/bin/env python3
"""
测试数据库和API功能
"""
import sqlite3
import os

DATABASE_PATH = 'd:/football_tools/data/football_unified.db'

def test_database():
    """测试数据库"""
    print("=" * 60)
    print("数据库测试")
    print("=" * 60)

    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # 1. 统计数据
    print("\n[统计数据]")
    cursor.execute('SELECT COUNT(*) FROM teams')
    print(f"球队数: {cursor.fetchone()[0]}")

    cursor.execute('SELECT COUNT(*) FROM matches')
    print(f"比赛数: {cursor.fetchone()[0]}")

    cursor.execute('SELECT COUNT(*) FROM leagues')
    print(f"联赛数: {cursor.fetchone()[0]}")

    cursor.execute('SELECT COUNT(*) FROM fifa_rankings')
    print(f"FIFA国家队排名: {cursor.fetchone()[0]}")

    # 2. 联赛列表
    print("\n[联赛列表]")
    cursor.execute('SELECT league_id, name, country FROM leagues ORDER BY tier, country LIMIT 10')
    for row in cursor.fetchall():
        print(f"  {row['league_id']}: {row['name']} ({row['country']})")

    # 3. 球队列表
    print("\n[球队列表 (前10个)]")
    cursor.execute('SELECT team_id, canonical_name, team_type, country FROM teams LIMIT 10')
    for row in cursor.fetchall():
        print(f"  {row['team_id']}: {row['canonical_name']} ({row['team_type']}, {row['country']})")

    # 4. 积分榜测试 (英超)
    print("\n[英超积分榜测试]")
    cursor.execute("""
        SELECT league_id FROM leagues WHERE league_code = 'premier_league'
    """)
    pl = cursor.fetchone()
    if pl:
        league_id = pl['league_id']
        cursor.execute("""
            SELECT
                t.canonical_name as team_name,
                COUNT(*) as matches,
                SUM(CASE
                    WHEN (m.home_team_id = t.team_id AND m.home_goals > m.away_goals) THEN 1
                    WHEN (m.away_team_id = t.team_id AND m.away_goals > m.home_goals) THEN 1
                    ELSE 0
                END) as wins,
                SUM(CASE WHEN m.home_goals = m.away_goals THEN 1 ELSE 0 END) as draws,
                SUM(CASE
                    WHEN (m.home_team_id = t.team_id AND m.home_goals < m.away_goals) THEN 1
                    WHEN (m.away_team_id = t.team_id AND m.away_goals < m.home_goals) THEN 1
                    ELSE 0
                END) as losses
            FROM teams t
            JOIN matches m ON (t.team_id = m.home_team_id OR t.team_id = m.away_team_id)
            WHERE m.league_id = ?
            GROUP BY t.team_id, t.canonical_name
            ORDER BY wins DESC
            LIMIT 5
        """, (league_id,))
        for row in cursor.fetchall():
            print(f"  {row['team_name']}: {row['wins']}胜 {row['draws']}平 {row['losses']}负")

    # 5. FIFA排名
    print("\n[FIFA国家队排名 TOP 10]")
    cursor.execute("""
        SELECT country, rank, points
        FROM fifa_rankings
        WHERE rank_date = (SELECT MAX(rank_date) FROM fifa_rankings)
        ORDER BY rank
        LIMIT 10
    """)
    for row in cursor.fetchall():
        print(f"  #{row['rank']}: {row['country']} ({row['points']}分)")

    # 6. 今日比赛
    print("\n[最近比赛]")
    cursor.execute("""
        SELECT
            m.match_date,
            ht.canonical_name as home_team,
            at.canonical_name as away_team,
            m.home_goals,
            m.away_goals,
            l.name as league
        FROM matches m
        JOIN teams ht ON m.home_team_id = ht.team_id
        JOIN teams at ON m.away_team_id = at.team_id
        JOIN leagues l ON m.league_id = l.league_id
        ORDER BY m.match_date DESC
        LIMIT 5
    """)
    for row in cursor.fetchall():
        score = f"{row['home_goals']}-{row['away_goals']}" if row['home_goals'] is not None else "未开始"
        print(f"  {row['match_date']}: {row['home_team']} {score} {row['away_team']} ({row['league']})")

    conn.close()
    print("\n" + "=" * 60)
    print("测试完成!")
    print("=" * 60)


if __name__ == '__main__':
    test_database()