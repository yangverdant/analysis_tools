#!/usr/bin/env python3
"""
完善数据库数据：
1. 更新联赛中文名和配置
2. 添加球队中文名
3. 添加联赛规则
"""

import sqlite3

DB_PATH = 'd:/football_tools/data/football_v2.db'

# 完整联赛配置
LEAGUES_UPDATE = {
    # 英格兰
    'premier_league': {'name_cn': '英超', 'country_cn': '英格兰', 'tier': 1, 'cl_spots': 4, 'el_spots': 2, 'conf_spots': 1, 'relegation': 3},
    'championship': {'name_cn': '英冠', 'country_cn': '英格兰', 'tier': 2, 'promotion': 3, 'relegation': 3},
    'scotland_premiership': {'name_cn': '苏超', 'country_cn': '苏格兰', 'tier': 1, 'cl_spots': 1, 'el_spots': 2},
    'scotland_championship': {'name_cn': '苏冠', 'country_cn': '苏格兰', 'tier': 2},
    'scotland_league_one': {'name_cn': '苏甲', 'country_cn': '苏格兰', 'tier': 3},
    'scotland_league_two': {'name_cn': '苏乙', 'country_cn': '苏格兰', 'tier': 4},

    # 西班牙
    'la_liga': {'name_cn': '西甲', 'country_cn': '西班牙', 'tier': 1, 'cl_spots': 4, 'el_spots': 2, 'conf_spots': 1, 'relegation': 3},
    'segunda_division': {'name_cn': '西乙', 'country_cn': '西班牙', 'tier': 2, 'promotion': 3, 'relegation': 4},

    # 德国
    'bundesliga': {'name_cn': '德甲', 'country_cn': '德国', 'tier': 1, 'cl_spots': 4, 'el_spots': 2, 'conf_spots': 1, 'relegation': 2, 'playoff': 1},
    'bundesliga_2': {'name_cn': '德乙', 'country_cn': '德国', 'tier': 2, 'promotion': 2, 'playoff': 1, 'relegation': 2},

    # 意大利
    'serie_a': {'name_cn': '意甲', 'country_cn': '意大利', 'tier': 1, 'cl_spots': 4, 'el_spots': 2, 'conf_spots': 1, 'relegation': 3},
    'serie_b': {'name_cn': '意乙', 'country_cn': '意大利', 'tier': 2, 'promotion': 3, 'relegation': 3},

    # 法国
    'ligue_1': {'name_cn': '法甲', 'country_cn': '法国', 'tier': 1, 'cl_spots': 3, 'el_spots': 2, 'conf_spots': 1, 'relegation': 2, 'playoff': 1},
    'ligue_2': {'name_cn': '法乙', 'country_cn': '法国', 'tier': 2, 'promotion': 2, 'playoff': 1, 'relegation': 2},

    # 荷兰
    'eredivisie': {'name_cn': '荷甲', 'country_cn': '荷兰', 'tier': 1, 'cl_spots': 2, 'el_spots': 2, 'relegation': 1, 'playoff': 1},

    # 葡萄牙
    'primeira_liga': {'name_cn': '葡超', 'country_cn': '葡萄牙', 'tier': 1, 'cl_spots': 2, 'el_spots': 2, 'relegation': 2},

    # 比利时
    'jupiler_league': {'name_cn': '比甲', 'country_cn': '比利时', 'tier': 1, 'cl_spots': 2, 'el_spots': 2},

    # 其他欧洲联赛
    'austrian_bundesliga': {'name_cn': '奥超', 'country_cn': '奥地利', 'tier': 1},
    'danish_superliga': {'name_cn': '丹超', 'country_cn': '丹麦', 'tier': 1},
    'greek_superleague': {'name_cn': '希腊超', 'country_cn': '希腊', 'tier': 1},
    'norwegian_eliteserien': {'name_cn': '挪超', 'country_cn': '挪威', 'tier': 1},
    'polish_ekstraklasa': {'name_cn': '波兰超', 'country_cn': '波兰', 'tier': 1},
    'swiss_super_league': {'name_cn': '瑞士超', 'country_cn': '瑞士', 'tier': 1},
    'turkish_super_lig': {'name_cn': '土超', 'country_cn': '土耳其', 'tier': 1},
    'allsvenskan': {'name_cn': '瑞典超', 'country_cn': '瑞典', 'tier': 1},
    'finland_veikkausliiga': {'name_cn': '芬超', 'country_cn': '芬兰', 'tier': 1},
    'romanian_liga_1': {'name_cn': '罗甲', 'country_cn': '罗马尼亚', 'tier': 1},
    'russian_premier_league': {'name_cn': '俄超', 'country_cn': '俄罗斯', 'tier': 1},

    # 非欧洲联赛
    'a_league': {'name_cn': '澳超', 'country_cn': '澳大利亚', 'tier': 1},
    'mls': {'name_cn': '美职联', 'country_cn': '美国', 'tier': 1},

    # 国家队赛事
    'world_cup': {'name_cn': '世界杯', 'country_cn': '世界', 'is_international': 1},
    'euro': {'name_cn': '欧洲杯', 'country_cn': '欧洲', 'is_international': 1},
    'copa_america': {'name_cn': '美洲杯', 'country_cn': '南美洲', 'is_international': 1},
    'africa_cup': {'name_cn': '非洲杯', 'country_cn': '非洲', 'is_international': 1},
    'asian_cup': {'name_cn': '亚洲杯', 'country_cn': '亚洲', 'is_international': 1},
    'friendly': {'name_cn': '国际友谊赛', 'country_cn': '世界', 'is_international': 1},
}

# 球队中文名映射（主要球队）
TEAM_CN = {
    # 英超
    'Manchester City': '曼城', 'Arsenal': '阿森纳', 'Liverpool': '利物浦', 'Manchester United': '曼联',
    'Chelsea': '切尔西', 'Tottenham': '热刺', 'Newcastle': '纽卡斯尔', 'Aston Villa': '阿斯顿维拉',
    'Brighton': '布莱顿', 'West Ham': '西汉姆', 'Brentford': '布伦特福德', 'Fulham': '富勒姆',
    'Crystal Palace': '水晶宫', 'Wolves': '狼队', 'Everton': '埃弗顿', 'Nottingham Forest': '诺丁汉森林',
    'Bournemouth': '伯恩茅斯', 'Leicester': '莱斯特城', 'Leeds': '利兹联', 'Southampton': '南安普顿',
    'Ipswich': '伊普斯维奇', 'Burnley': '伯恩利', 'Sheffield United': '谢菲尔德联',

    # 西甲
    'Real Madrid': '皇马', 'Barcelona': '巴萨', 'Atletico Madrid': '马竞', 'Athletic Bilbao': '毕尔巴鄂',
    'Real Sociedad': '皇家社会', 'Villarreal': '比利亚雷亚尔', 'Real Betis': '贝蒂斯', 'Sevilla': '塞维利亚',
    'Valencia': '瓦伦西亚', 'Getafe': '赫塔费', 'Osasuna': '奥萨苏纳', 'Celta Vigo': '塞尔塔',
    'Girona': '赫罗纳', 'Alaves': '阿拉维斯', 'Rayo Vallecano': '巴列卡诺', 'Mallorca': '马洛卡',
    'Las Palmas': '拉斯帕尔马斯', 'Leganes': '莱加内斯', 'Espanyol': '西班牙人', 'Valladolid': '巴利亚多利德',

    # 德甲
    'Bayern Munich': '拜仁', 'Borussia Dortmund': '多特', 'RB Leipzig': '莱比锡', 'Leverkusen': '勒沃库森',
    'Freiburg': '弗赖堡', 'Eintracht Frankfurt': '法兰克福', 'Wolfsburg': '沃尔夫斯堡', 'Mainz': '美因茨',
    'Borussia M\'gladbach': '门兴', 'Union Berlin': '柏林联合', 'Werder Bremen': '不来梅', 'Stuttgart': '斯图加特',
    'Hoffenheim': '霍芬海姆', 'Augsburg': '奥格斯堡', 'Bochum': '波鸿', 'Heidenheim': '海登海姆',
    'Holstein Kiel': '基尔', 'St. Pauli': '圣保利',

    # 意甲
    'Inter': '国际米兰', 'Milan': 'AC米兰', 'Juventus': '尤文图斯', 'Napoli': '那不勒斯',
    'Roma': '罗马', 'Lazio': '拉齐奥', 'Atalanta': '亚特兰大', 'Fiorentina': '佛罗伦萨',
    'Bologna': '博洛尼亚', 'Torino': '都灵', 'Monza': '蒙扎', 'Udinese': '乌迪内斯',
    'Sassuolo': '萨索洛', 'Empoli': '恩波利', 'Salernitana': '萨勒尼塔纳', 'Lecce': '莱切',
    'Cagliari': '卡利亚里', 'Genoa': '热那亚', 'Verona': '维罗纳', 'Frosinone': '弗罗西诺内',
    'Parma': '帕尔马', 'Como': '科莫', 'Venezia': '威尼斯',

    # 法甲
    'Paris SG': '巴黎圣日耳曼', 'Marseille': '马赛', 'Lyon': '里昂', 'Monaco': '摩纳哥',
    'Lille': '里尔', 'Nice': '尼斯', 'Lens': '朗斯', 'Rennes': '雷恩', 'Strasbourg': '斯特拉斯堡',
    'Toulouse': '图卢兹', 'Nantes': '南特', 'Montpellier': '蒙彼利埃', 'Brest': '布雷斯特',
    'Reims': '兰斯', 'Lorient': '洛里昂', 'Le Havre': '勒阿弗尔', 'Metz': '梅斯', 'Auxerre': '欧塞尔',
    'Saint-Etienne': '圣埃蒂安', 'Angers': '昂热',

    # 国家队
    'Argentina': '阿根廷', 'Brazil': '巴西', 'France': '法国', 'England': '英格兰',
    'Spain': '西班牙', 'Germany': '德国', 'Italy': '意大利', 'Portugal': '葡萄牙',
    'Netherlands': '荷兰', 'Belgium': '比利时', 'Croatia': '克罗地亚', 'Uruguay': '乌拉圭',
    'Colombia': '哥伦比亚', 'Mexico': '墨西哥', 'USA': '美国', 'Japan': '日本',
    'South Korea': '韩国', 'Australia': '澳大利亚', 'Senegal': '塞内加尔', 'Morocco': '摩洛哥',
    'Egypt': '埃及', 'Nigeria': '尼日利亚', 'Cameroon': '喀麦隆', 'Ghana': '加纳',
    'Tunisia': '突尼斯', 'Algeria': '阿尔及利亚', 'Saudi Arabia': '沙特', 'Iran': '伊朗',
    'Qatar': '卡塔尔', 'China': '中国', 'Canada': '加拿大', 'Costa Rica': '哥斯达黎加',
    'Panama': '巴拿马', 'Ecuador': '厄瓜多尔', 'Peru': '秘鲁', 'Chile': '智利',
    'Venezuela': '委内瑞拉', 'Paraguay': '巴拉圭', 'Bolivia': '玻利维亚',
    'Poland': '波兰', 'Ukraine': '乌克兰', 'Switzerland': '瑞士', 'Austria': '奥地利',
    'Czech Republic': '捷克', 'Denmark': '丹麦', 'Sweden': '瑞典', 'Norway': '挪威',
    'Finland': '芬兰', 'Ireland': '爱尔兰', 'Scotland': '苏格兰', 'Wales': '威尔士',
    'Serbia': '塞尔维亚', 'Slovenia': '斯洛文尼亚', 'Slovakia': '斯洛伐克', 'Hungary': '匈牙利',
    'Romania': '罗马尼亚', 'Greece': '希腊', 'Turkey': '土耳其', 'Russia': '俄罗斯',
    'Iceland': '冰岛', 'North Macedonia': '北马其顿', 'Albania': '阿尔巴尼亚', 'Georgia': '格鲁吉亚',
}


def update_data():
    print("=" * 70)
    print("完善数据库数据")
    print("=" * 70)

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # 1. 更新联赛信息
    print("\n[1/3] 更新联赛中文名和配置...")
    updated = 0
    for league_code, info in LEAGUES_UPDATE.items():
        cursor.execute('''
            UPDATE leagues SET
                name_cn = ?,
                country_cn = ?,
                tier = ?,
                is_international = ?
            WHERE league_code = ?
        ''', (
            info.get('name_cn', ''),
            info.get('country_cn', ''),
            info.get('tier', 1),
            info.get('is_international', 0),
            league_code
        ))
        if cursor.rowcount > 0:
            updated += 1
    conn.commit()
    print(f"  更新 {updated} 个联赛")

    # 2. 更新球队中文名
    print("\n[2/3] 更新球队中文名...")
    updated = 0
    for team_name, name_cn in TEAM_CN.items():
        cursor.execute('''
            UPDATE teams SET name_cn = ? WHERE name_en = ?
        ''', (name_cn, team_name))
        if cursor.rowcount > 0:
            updated += 1
    conn.commit()
    print(f"  更新 {updated} 支球队")

    # 3. 添加联赛规则
    print("\n[3/3] 添加联赛规则...")
    rules_added = 0
    for league_code, info in LEAGUES_UPDATE.items():
        if 'cl_spots' in info or 'promotion' in info:
            cursor.execute('SELECT league_id FROM leagues WHERE league_code = ?', (league_code,))
            row = cursor.fetchone()
            if row:
                league_id = row[0]
                cursor.execute('''
                    INSERT OR REPLACE INTO league_rules
                    (league_id, season, teams_count, champions_league_spots, europa_league_spots,
                     conference_league_spots, promotion_spots, relegation_spots, playoff_spots)
                    VALUES (?, '2024-25', 18, ?, ?, ?, ?, ?, ?)
                ''', (
                    league_id,
                    info.get('cl_spots'),
                    info.get('el_spots'),
                    info.get('conf_spots'),
                    info.get('promotion'),
                    info.get('relegation'),
                    info.get('playoff')
                ))
                rules_added += 1
    conn.commit()
    print(f"  添加 {rules_added} 条联赛规则")

    # 打印统计
    print("\n" + "=" * 70)
    print("数据统计：")
    print("=" * 70)

    cursor.execute("SELECT COUNT(*) FROM leagues WHERE name_cn IS NOT NULL AND name_cn != ''")
    print(f"  有中文名的联赛: {cursor.fetchone()[0]}")

    cursor.execute("SELECT COUNT(*) FROM teams WHERE name_cn IS NOT NULL AND name_cn != ''")
    print(f"  有中文名的球队: {cursor.fetchone()[0]}")

    cursor.execute("SELECT COUNT(*) FROM league_rules")
    print(f"  联赛规则: {cursor.fetchone()[0]} 条")

    # 显示联赛列表
    print("\n联赛列表：")
    cursor.execute('''
        SELECT league_code, name_cn, competition_type, participant_type
        FROM leagues ORDER BY competition_type, league_code
    ''')
    current_type = None
    for row in cursor.fetchall():
        if row[2] != current_type:
            current_type = row[2]
            print(f"\n  [{current_type}]")
        print(f"    {row[0]}: {row[1]} ({row[3]})")

    conn.close()
    print("\n完成！")


if __name__ == '__main__':
    update_data()
