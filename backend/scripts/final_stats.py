"""最终数据统计"""
import sqlite3

conn = sqlite3.connect('d:/football_tools/data/football_v2.db')
cursor = conn.cursor()

print("=" * 70)
print("国家队比赛数据最终统计")
print("=" * 70)

# 总数
cursor.execute("SELECT COUNT(*) FROM matches WHERE match_id LIKE 'intl_%'")
total = cursor.fetchone()[0]
print(f"\n国家队比赛总数: {total} 场")

# 按年份
cursor.execute("""
    SELECT substr(match_date, 1, 4) as year, COUNT(*) as matches
    FROM matches
    WHERE match_id LIKE 'intl_%' AND match_date != ''
    GROUP BY year
    ORDER BY year DESC
""")
years = cursor.fetchall()

print("\n按年份分布:")
for year, count in years:
    marker = " *" if int(year) >= 2020 else ""
    print(f"  {year}: {count} 场{marker}")

# 2020年后占比
cursor.execute("""
    SELECT COUNT(*) FROM matches
    WHERE match_id LIKE 'intl_%'
    AND match_date >= '2020-01-01'
    AND match_date != ''
""")
after_2020 = cursor.fetchone()[0]

print(f"\n2020年后数据: {after_2020} 场 ({after_2020*100/total:.1f}%)")

conn.close()