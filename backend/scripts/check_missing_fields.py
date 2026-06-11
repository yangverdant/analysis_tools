"""重新检查国家队比赛缺失字段"""
import sqlite3

conn = sqlite3.connect('d:/football_tools/data/football_v2.db')
cursor = conn.cursor()

print("=" * 70)
print("国家队比赛缺失字段详细检查")
print("=" * 70)

# 1. 检查match_time字段实际值分布
cursor.execute("""
    SELECT
        CASE
            WHEN match_time IS NULL THEN 'NULL'
            WHEN match_time = '' THEN '空字符串'
            ELSE '有值'
        END as time_status,
        COUNT(*) as matches
    FROM matches
    WHERE match_id LIKE 'intl_%'
    GROUP BY time_status
""")
time_stats = cursor.fetchall()
print("\n比赛时间字段状态:")
for status, count in time_stats:
    print(f"  {status}: {count} 场")

# 2. 查看一些实际的match_time值
cursor.execute("""
    SELECT match_time, COUNT(*) as cnt
    FROM matches
    WHERE match_id LIKE 'intl_%' AND match_time IS NOT NULL AND match_time != ''
    GROUP BY match_time
    ORDER BY cnt DESC
    LIMIT 10
""")
time_values = cursor.fetchall()
print("\n常见比赛时间值:")
for time_val, count in time_values:
    print(f"  {time_val}: {count} 场")

# 3. 2020年后缺失时间的详细检查
cursor.execute("""
    SELECT match_id, match_date, match_time
    FROM matches
    WHERE match_id LIKE 'intl_%'
    AND match_date >= '2020-01-01'
    LIMIT 20
""")
samples = cursor.fetchall()
print("\n2020年后比赛样例:")
for match_id, date, time in samples:
    print(f"  {match_id}: {date} {time if time else '(无时间)'}")

# 4. 检查场馆信息
cursor.execute("""
    SELECT COUNT(*) FROM matches
    WHERE match_id LIKE 'intl_%'
    AND venue IS NOT NULL AND venue != ''
""")
has_venue = cursor.fetchone()[0]

cursor.execute("""
    SELECT COUNT(*) FROM matches
    WHERE match_id LIKE 'intl_%'
    AND venue IS NULL OR venue = ''
""")
no_venue = cursor.fetchone()[0]

print(f"\n场馆信息:")
print(f"  有场馆: {has_venue} 场")
print(f"  无场馆: {no_venue} 场")

conn.close()