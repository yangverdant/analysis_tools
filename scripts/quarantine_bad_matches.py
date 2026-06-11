"""清理错配比赛 - 备份到matches_quarantine表"""
import sqlite3

conn = sqlite3.connect("/opt/football_tools/data/football_v2.db")
cur = conn.cursor()

# 创建备份表
cur.execute("CREATE TABLE IF NOT EXISTS matches_quarantine AS SELECT * FROM matches WHERE 1=0")
cur.execute("DELETE FROM matches_quarantine")

# K联赛真正的韩国队
korean_teams = [
    'Jeonbuk Hyundai', 'Suwon Bluewings', 'Pohang Steelers', 'Daegu FC',
    'Ulsan Hyundai', 'Incheon United', 'Jeju United', 'Gangwon FC',
    'FC Seoul', 'Sangju Sangmu', 'Seongnam FC', 'Gwangju FC',
    'Suwon FC', 'Daejeon Hana Citizen', 'Anyang', 'Cheonan City',
    'Chungnam Asan', 'Gimpo FC', 'Busan IPark', 'Bucheon FC 1995',
    'Gyeongnam FC', 'Ansan Greeners', 'Seoul E-Land', 'Cheongju FC',
    'Kimcheon Sangmu', 'Jeonnam Dragons'
]

# 巴甲真正的巴西队
brazilian_teams = [
    'Flamengo', 'Palmeiras', 'Atletico Mineiro', 'Fortaleza', 'Sao Paulo',
    'Fluminense', 'Internacional', 'Corinthians', 'Gremio', 'Bahia',
    'Botafogo', 'Santos', 'Bragantino', 'Athletico Paranaense', 'Cuiaba',
    'Goias', 'Coritiba', 'America Mineiro', 'Vitoria', 'Cruzeiro', 'Ceara',
    'Chapecoense', 'Clube do Remo', 'Paysandu', 'Vila Nova', 'Operario PR',
    'Amazonas', 'Criciuma', 'Mirassol', 'Atletico Goianiense', 'Avai', 'Juventude'
]

# 瑞典超真正的瑞典队
swedish_teams = [
    'Malmo FF', 'Hammarby', 'Djurgardens IF', 'AIK', 'IFK Goteborg',
    'IF Elfsborg', 'Mjallby AIF', 'BK Hacken', 'Degerfors IF', 'Kalmar FF',
    'IK Sirius', 'Osters IF', 'Halmstads BK', 'IFK Varnamo', 'Vasteras SK',
    'GAIS', 'Brommapojkarna', 'Helsingborgs IF', 'Norrkoping', 'Orebro SK',
    'IK Brage', 'Sandvikens IF', 'Ostersunds FK', 'Landskrona BoIS',
    'Jonkopings Sodra IF', 'Linkopings FC', 'Varbergs BoIS FC',
    'Sirius', 'Djurgarden', 'Hacken', 'Elfsborg', 'Goteborg',
    'Halmstad', 'Varnamo', 'Vasteras', 'Oster', 'Kalmar', 'Mjallby'
]

def move_to_quarantine(desc, where_clause, params=()):
    cur.execute(f"SELECT COUNT(*) FROM matches WHERE {where_clause}", params)
    count = cur.fetchone()[0]
    if count == 0:
        print(f"  {desc}: 0条, 跳过")
        return 0
    cur.execute(f"INSERT INTO matches_quarantine SELECT * FROM matches WHERE {where_clause}", params)
    cur.execute(f"DELETE FROM matches WHERE {where_clause}", params)
    print(f"  {desc}: 备份并移除{cur.rowcount}条")
    return cur.rowcount

total = 0

# 1. K联赛错配
for lid in [20, 7436]:
    placeholders = ','.join(['?' for _ in korean_teams])
    n = move_to_quarantine(
        f"K联赛(id={lid})非韩国队",
        f"league_id = ? AND match_date >= '2026-06-10' AND status = 'scheduled' AND home_team_id NOT IN (SELECT team_id FROM teams WHERE name_en IN ({placeholders}))",
        [lid] + korean_teams
    )
    total += n

# 2. 巴甲错配
placeholders = ','.join(['?' for _ in brazilian_teams])
n = move_to_quarantine(
    "巴甲非巴西队",
    f"league_id = 6 AND match_date >= '2026-06-10' AND status = 'scheduled' AND home_team_id NOT IN (SELECT team_id FROM teams WHERE name_en IN ({placeholders}))",
    brazilian_teams
)
total += n

# 3. 瑞典超错配
placeholders = ','.join(['?' for _ in swedish_teams])
n = move_to_quarantine(
    "瑞典超非瑞典队",
    f"league_id = 3 AND match_date >= '2026-06-10' AND status = 'scheduled' AND home_team_id NOT IN (SELECT team_id FROM teams WHERE name_en IN ({placeholders}))",
    swedish_teams
)
total += n

# 4. 越南友谊赛
n = move_to_quarantine(
    "越南联赛",
    "match_date >= '2026-06-10' AND status = 'scheduled' AND home_team_id IN (SELECT team_id FROM teams WHERE name_en = 'Phu Dong Ninh Binh')"
)
total += n

# 5. 世界杯占位符(B1 vs E3等)
n = move_to_quarantine(
    "世界杯占位符",
    "league_id = 40 AND match_date >= '2026-06-29'"
)
total += n

# 6. 联赛名缺失
n = move_to_quarantine(
    "联赛名缺失",
    "match_date >= '2026-06-10' AND status = 'scheduled' AND league_id IN (SELECT league_id FROM leagues WHERE name_en LIKE 'League%' OR name_en LIKE 'liga%')"
)
total += n

print(f"\n总计移除 {total} 条脏数据到 matches_quarantine 表")

cur.execute("SELECT COUNT(*) FROM matches_quarantine")
print(f"备份表共 {cur.fetchone()[0]} 条")

conn.commit()
conn.close()
