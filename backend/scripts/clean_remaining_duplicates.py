"""处理剩余的相同日期+球队重复比赛"""
import sqlite3
from pathlib import Path

DB_PATH = Path('d:/football_tools/data/football_v2.db')

def main():
    conn = sqlite3.connect(DB_PATH, timeout=30.0)
    cursor = conn.cursor()

    print("检查剩余的相同日期+球队重复比赛...")

    # 获取重复的比赛组
    cursor.execute("""
        SELECT m.match_date, m.home_team_id, m.away_team_id,
               t1.name_en as home, t2.name_en as away,
               COUNT(*) as cnt
        FROM matches m
        JOIN teams t1 ON m.home_team_id = t1.team_id
        JOIN teams t2 ON m.away_team_id = t2.team_id
        WHERE m.match_date != '' AND m.match_date IS NOT NULL
        GROUP BY m.match_date, m.home_team_id, m.away_team_id
        HAVING COUNT(*) > 1
    """)
    duplicates = cursor.fetchall()

    print(f"发现 {len(duplicates)} 组重复")

    removed = 0
    for match_date, home_id, away_id, home_name, away_name, cnt in duplicates:
        # 获取这些重复比赛
        cursor.execute("""
            SELECT m.rowid, m.match_id, m.home_goals, m.away_goals, m.venue, m.source
            FROM matches m
            WHERE m.match_date = ? AND m.home_team_id = ? AND m.away_team_id = ?
            ORDER BY
                CASE WHEN m.home_goals IS NOT NULL THEN 1 ELSE 0 END DESC,
                CASE WHEN m.venue IS NOT NULL AND m.venue != '' THEN 1 ELSE 0 END DESC,
                m.rowid DESC
        """, (match_date, home_id, away_id))
        matches = cursor.fetchall()

        # 保留第一条（数据最完整的），删除其他
        for rowid, match_id, hg, ag, venue, source in matches[1:]:
            cursor.execute("DELETE FROM matches WHERE rowid = ?", (rowid,))
            removed += 1

    conn.commit()

    # VACUUM
    cursor.execute("VACUUM")

    print(f"删除重复: {removed} 条")

    # 最终统计
    cursor.execute("SELECT COUNT(*) FROM matches")
    total = cursor.fetchone()[0]
    print(f"剩余比赛: {total} 条")

    conn.close()

if __name__ == '__main__':
    main()
