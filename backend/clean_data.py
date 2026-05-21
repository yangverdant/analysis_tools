import sqlite3
conn = sqlite3.connect("D:/football_tools/data/football_v2.db")
cursor = conn.cursor()

print("=== 清理脏数据 ===\n")

# 1. 清理无效赛季（如 "2026-2026"）
cursor.execute("SELECT season_id, season_name FROM seasons WHERE season_name LIKE '%-%' AND LENGTH(season_name) < 7")
invalid_seasons = cursor.fetchall()
print(f"无效赛季: {invalid_seasons}")
for s in invalid_seasons:
    cursor.execute("DELETE FROM matches WHERE season_id = ?", (s[0],))
    cursor.execute("DELETE FROM seasons WHERE season_id = ?", (s[0],))
print(f"删除了 {len(invalid_seasons)} 个无效赛季\n")

# 2. 检查并删除没有比赛的联赛
cursor.execute("""
    SELECT l.league_id, l.name_en, l.name_cn
    FROM leagues l
    LEFT JOIN matches m ON l.league_id = m.league_id
    GROUP BY l.league_id
    HAVING COUNT(m.match_id) = 0
""")
empty_leagues = cursor.fetchall()
print(f"无比赛数据的联赛 ({len(empty_leagues)} 个):")
for l in empty_leagues[:20]:
    print(f"  {l[0]}: {l[1]} ({l[2]})")

# 不删除，只是标记
print()

# 3. 检查洲际赛事的联赛类型
cursor.execute("""
    SELECT league_id, name_en, name_cn, competition_type, is_international
    FROM leagues
    WHERE name_en LIKE '%World Cup%' OR name_en LIKE '%Euro%' OR name_en LIKE '%Cup%'
       OR name_cn LIKE '%杯%' OR name_cn LIKE '%世界杯%' OR name_cn LIKE '%欧洲杯%'
""")
cup_leagues = cursor.fetchall()
print(f"\n杯赛/洲际赛事 ({len(cup_leagues)} 个):")
for l in cup_leagues:
    print(f"  {l[0]}: {l[1]} ({l[2]}) - type={l[3]}, intl={l[4]}")

conn.commit()
conn.close()
print("\n清理完成!")
