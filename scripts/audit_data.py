import sqlite3
c = sqlite3.connect("/opt/football_tools/data/football_v2.db")

print("=== 分析用数据现状 ===\n")

# 1. matches
total = c.execute("SELECT COUNT(*) FROM matches").fetchone()[0]
scheduled = c.execute("""SELECT COUNT(*) FROM matches WHERE status='scheduled' AND match_date>='2026-06-10'""").fetchone()[0]
finished = c.execute("""SELECT COUNT(*) FROM matches WHERE status='finished'""").fetchone()[0]
no_time = c.execute("""SELECT COUNT(*) FROM matches WHERE (match_time IS NULL OR match_time='') AND status='scheduled' AND match_date>='2026-06-10'""").fetchone()[0]
print(f"1. matches 比赛记录: {total:,}场")
print(f"   已完赛: {finished:,}场")
print(f"   6月scheduled: {scheduled}场")
print(f"   其中无开球时间: {no_time}场")

print("   time_type分布:")
for r in c.execute("""SELECT time_type, COUNT(*) FROM matches WHERE status='scheduled' AND match_date>='2026-06-10' GROUP BY time_type""").fetchall():
    tt = r[0] if r[0] else "空"
    print(f"     {tt}: {r[1]}场")

print("   数据源前缀:")
for r in c.execute("""SELECT CASE
    WHEN match_id LIKE 'friendly_%' THEN 'apifootball(friendly)'
    WHEN match_id LIKE 'world_cup_%' THEN 'apifootball(world_cup)'
    WHEN match_id LIKE 'csv_%' THEN 'oddsfe(csv)'
    WHEN match_id LIKE 'wc_%' THEN 'sportmonks'
    WHEN match_id LIKE 'intl_%' THEN 'apifootball(历史)'
    WHEN match_id LIKE 'eredivisie_%' THEN 'apifootball(荷甲)'
    ELSE '其他'
    END as src, COUNT(*) FROM matches WHERE status='scheduled' AND match_date>='2026-06-10' GROUP BY src ORDER BY 2 DESC""").fetchall():
    print(f"     {r[0]}: {r[1]}场")

# 2. teams
t_total = c.execute("SELECT COUNT(*) FROM teams").fetchone()[0]
t_cn = c.execute("SELECT COUNT(*) FROM teams WHERE name_cn IS NOT NULL AND name_cn != ''").fetchone()[0]
print(f"\n2. teams 球队: {t_total:,}个")
print(f"   有中文名: {t_cn:,}个({t_cn*100//t_total}%)")
print(f"   缺中文名: {t_total-t_cn:,}个")

# 3. leagues
l_total = c.execute("SELECT COUNT(*) FROM leagues").fetchone()[0]
l_garbage = c.execute("""SELECT COUNT(*) FROM leagues WHERE name_cn LIKE '联赛%'""").fetchone()[0]
print(f"\n3. leagues 联赛: {l_total}个")
print(f"   垃圾联赛(联赛XXX): {l_garbage}个")

# 4-8
print(f"\n4. elo_ratings Elo评分: {c.execute('SELECT COUNT(*) FROM elo_ratings').fetchone()[0]:,}条")
print(f"5. standings 积分榜: {c.execute('SELECT COUNT(*) FROM standings').fetchone()[0]}条")
print(f"6. team_form 球队状态: {c.execute('SELECT COUNT(*) FROM team_form').fetchone()[0]:,}条")
print(f"7. match_odds 赔率: {c.execute('SELECT COUNT(*) FROM match_odds').fetchone()[0]:,}条")
lm = c.execute('SELECT COUNT(*) FROM lottery_matches').fetchone()[0]
lo = c.execute('SELECT COUNT(*) FROM lottery_odds').fetchone()[0]
la = c.execute('SELECT COUNT(*) FROM lottery_analysis_reports').fetchone()[0]
print(f"8. lottery 体彩: {lm}场, 赔率{lo}条, 分析{la}条")
print(f"9. matches_quarantine 隔离: {c.execute('SELECT COUNT(*) FROM matches_quarantine').fetchone()[0]}条")

# 数据质量问题
print("\n=== 数据质量问题 ===")

dups = c.execute("""SELECT COUNT(*) FROM (
    SELECT home_team_id, away_team_id, match_date, COUNT(*) as cnt
    FROM matches WHERE status='scheduled' AND match_date>='2026-06-10'
    GROUP BY home_team_id, away_team_id, match_date HAVING cnt>1
)""").fetchone()[0]
print(f"1. 同队同日重复: {dups}组")

friendly_june = c.execute("""SELECT COUNT(*) FROM matches WHERE league_id=17 AND status='scheduled' AND match_date>='2026-06-10'""").fetchone()[0]
print(f"2. 标为友谊赛的6月比赛: {friendly_june}场(可能含误标)")

no_cn_teams = c.execute("""SELECT COUNT(*) FROM teams WHERE name_cn IS NULL OR name_cn=''""").fetchone()[0]
print(f"3. 缺中文名球队: {no_cn_teams:,}个")

alias_cnt = c.execute("SELECT COUNT(*) FROM team_aliases").fetchone()[0]
print(f"4. team_aliases 别名映射: {alias_cnt}条")
print(f"   同一真实球队多个ID: 如South Korea(841)/Korea Republic(1036)")

print("\n=== 核心问题总结 ===")
print("1. 多数据源(apifootball/oddsfe/sportmonks)写入同一matches表, match_id前缀不同")
print("2. 同一球队在不同源有不同team_id, 导致同一场比赛出现多条记录")
print("3. time_type不统一: utc/beijing/local混杂, 同一联赛的记录time_type不一致")
print("4. 联赛标记错误: 世界杯热身赛被apifootball标为Friendly(league_id=17)")
print("5. 大量比赛缺开球时间, 需从其他源补充或估算")
print("6. 垃圾联赛(联赛XXX)来自apifootball的league_id映射错误")

c.close()
