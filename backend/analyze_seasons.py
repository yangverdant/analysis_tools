import sqlite3
import sys
sys.stdout.reconfigure(encoding='utf-8')

conn = sqlite3.connect('data/football_v2.db')
conn.row_factory = sqlite3.Row
cursor = conn.cursor()

# 先查看seasons表结构
cursor.execute("PRAGMA table_info(seasons)")
print('seasons表字段:', [col[1] for col in cursor.fetchall()])

# 查看matches中的赛季分布
cursor.execute('''
    SELECT DISTINCT l.league_id, l.name_en, l.name_cn, l.country,
           m.season_id, substr(m.match_id, 1, 30) as match_id_sample
    FROM matches m
    LEFT JOIN leagues l ON m.league_id = l.league_id
    ORDER BY l.country, l.name_en
''')
rows = cursor.fetchall()

# 按联赛分组，提取赛季信息
from collections import defaultdict
league_seasons = defaultdict(set)

for row in rows:
    key = f"{row['country']}|{row['name_en']}"
    # 从match_id提取赛季
    match_id = row['match_id_sample'] or ''
    parts = match_id.split('_')
    if len(parts) >= 2:
        season_part = parts[1]
        league_seasons[key].add(season_part)

print('\n联赛赛季命名分析')
print('=' * 80)

# 需要跨年命名的联赛（欧洲主流）
cross_year_leagues = ['premier_league', 'la_liga', 'bundesliga', 'serie_a', 'ligue_1',
                      'eredivisie', 'primeira_liga', 'jupiler_pro_league', 'scottish_premiership']

# 不跨年命名的联赛（北欧、南美、亚洲）
same_year_leagues = ['allsvenskan', 'eliteserien', 'danish_superliga', 'veikkausliiga',
                     'brasileirao', 'argentina_primera', 'mls', 'j_league', 'k_league', 'csl']

for key, seasons in sorted(league_seasons.items()):
    country, league = key.split('|')
    print(f'\n【{country}】{league}')
    print(f'  当前赛季命名: {sorted(seasons)}')

    # 检查是否正确
    league_lower = league.lower().replace(' ', '_')
    is_cross_year = any(cy in league_lower for cy in ['premier', 'la_liga', 'bundesliga', 'serie', 'ligue', 'eredivisie', 'primeira', 'jupiler', 'scottish'])
    is_same_year = any(sy in league_lower for sy in ['allsvenskan', 'eliteserien', 'danish', 'veikkaus', 'brasileirao', 'argentina', 'mls', 'j_league', 'k_league', 'csl', 'swedish', 'norwegian', 'finnish'])

    # 或者按国家判断
    is_cross_year_country = country in ['England', 'Spain', 'Germany', 'Italy', 'France', 'Netherlands', 'Portugal', 'Belgium', 'Scotland', 'Turkey', 'Greece', 'Austria', 'Switzerland', 'Poland', 'Czech Republic', 'Russia']
    is_same_year_country = country in ['Sweden', 'Norway', 'Denmark', 'Finland', 'Brazil', 'Argentina', 'USA', 'China', 'Japan', 'South Korea', 'Chile', 'Colombia', 'Mexico', 'Iceland']

    if is_cross_year_country:
        expected_format = '跨年格式(如2025-2026)'
        for s in seasons:
            if '-' not in s:
                print(f'  ⚠️ {s} 应该用跨年格式')
    elif is_same_year_country:
        expected_format = '单年格式(如2025)'
        for s in seasons:
            if '-' in s:
                print(f'  ⚠️ {s} 应该用单年格式')
    else:
        expected_format = '需确认'

conn.close()