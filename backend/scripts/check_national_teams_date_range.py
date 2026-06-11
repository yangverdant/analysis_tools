"""检查国家队比赛数据的时间分布"""
import sqlite3
from datetime import datetime

conn = sqlite3.connect('d:/football_tools/data/football_v2.db')
cursor = conn.cursor()

print("=" * 70)
print("国家队比赛数据时间分布检查")
print("=" * 70)

# 1. 按年份统计
cursor.execute("""
    SELECT substr(match_date, 1, 4) as year, COUNT(*) as matches
    FROM matches
    WHERE match_id LIKE 'intl_%' AND match_date != ''
    GROUP BY year
    ORDER BY year DESC
""")
year_stats = cursor.fetchall()

print("\n按年份统计:")
total = 0
for year, count in year_stats:
    total += count
    print(f"  {year}: {count} 场")
print(f"  总计: {total} 场")

# 2. 2020年后的数据占比
cursor.execute("""
    SELECT COUNT(*) FROM matches
    WHERE match_id LIKE 'intl_%'
    AND match_date >= '2020-01-01'
    AND match_date != ''
""")
after_2020 = cursor.fetchone()[0]

cursor.execute("""
    SELECT COUNT(*) FROM matches
    WHERE match_id LIKE 'intl_%'
    AND match_date < '2020-01-01'
    AND match_date != ''
""")
before_2020 = cursor.fetchone()[0]

print(f"\n2020年后数据: {after_2020} 场 ({after_2020*100/(after_2020+before_2020):.1f}%)")
print(f"2020年前数据: {before_2020} 场 ({before_2020*100/(after_2020+before_2020):.1f}%)")

# 3. 按赛事+年份交叉统计（2020年后）
print("\n主要赛事 2020年后数据分布:")
cursor.execute("""
    SELECT l.name_cn, substr(m.match_date, 1, 4) as year, COUNT(*) as matches
    FROM matches m
    JOIN leagues l ON m.league_id = l.league_id
    WHERE m.match_id LIKE 'intl_%'
    AND m.match_date >= '2020-01-01'
    AND m.match_date != ''
    GROUP BY l.name_cn, year
    ORDER BY matches DESC
    LIMIT 30
""")
cross_stats = cursor.fetchall()

for name, year, count in cross_stats:
    print(f"  {name} {year}: {count} 场")

# 4. 检查缺失的比赛时间
cursor.execute("""
    SELECT COUNT(*) FROM matches
    WHERE match_id LIKE 'intl_%'
    AND match_time = '' OR match_time IS NULL
""")
missing_time = cursor.fetchone()[0]

cursor.execute("""
    SELECT COUNT(*) FROM matches
    WHERE match_id LIKE 'intl_%'
    AND (venue = '' OR venue IS NULL)
""")
missing_venue = cursor.fetchone()[0]

print(f"\n缺失数据统计:")
print(f"  缺失比赛时间: {missing_time} 场")
print(f"  缺失场馆信息: {missing_venue} 场")

conn.close()