#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""导入用户提供的比赛数据"""

import csv
import sqlite3
import os
import re

DATABASE_PATH = 'data/football_unified.db'

# 联赛名称映射
LEAGUE_MAPPING = {
    '意甲': ('I1', 'Serie A', 'Italy', -7),
    '意乙': ('I2', 'Serie B', 'Italy', -7),
    '英超': ('E0', 'Premier League', 'England', -7),
    '英冠': ('E1', 'Championship', 'England', -7),
    '西甲': ('SP1', 'La Liga', 'Spain', -7),
    '西乙': ('SP2', 'Segunda Division', 'Spain', -7),
    '法甲': ('F1', 'Ligue 1', 'France', -7),
    '法乙': ('F2', 'Ligue 2', 'France', -7),
    '德甲': ('D1', 'Bundesliga', 'Germany', -7),
    '德乙': ('D2', 'Bundesliga 2', 'Germany', -7),
    '葡甲': ('P1', 'Primeira Liga', 'Portugal', -8),
    '比甲': ('B1', 'Jupiler League', 'Belgium', -7),
    '丹超': ('DK1', 'Eliteserien', 'Denmark', -7),
    '瑞典超': ('SWE', 'Allsvenskan', 'Sweden', -7),
    '瑞典甲': ('SWE1', 'Superettan', 'Sweden', -7),
    '芬超': ('FIN', 'Veikkausliiga', 'Finland', -6),
    '芬甲': ('FIN1', 'Ykkonen', 'Finland', -6),
    '冰岛超': ('IS', 'Urvalsdeild', 'Iceland', -8),
    '挪超': ('N1', 'Eliteserien', 'Norway', -7),
    '土超': ('TR1', 'Super Lig', 'Turkey', -6),
    '希腊超': ('GR1', 'Super League', 'Greece', -6),
    '塞尔超': ('SR1', 'Super Liga', 'Serbia', -7),
    '克罗甲': ('HR1', '1. HNL', 'Croatia', -7),
    '罗甲': ('RO1', 'Liga I', 'Romania', -6),
    '波甲': ('PO1', 'Ekstraklasa', 'Poland', -7),
    '波兰甲': ('PO1', 'Ekstraklasa', 'Poland', -7),
    '乌克超': ('UA1', 'Premier League', 'Ukraine', -6),
    '俄超': ('RU1', 'Premier League', 'Russia', -5),
    '以超': ('IL1', 'Premier League', 'Israel', -6),
    '沙特联': ('SA1', 'Saudi Pro League', 'Saudi Arabia', -5),
    '美职': ('MLS', 'MLS', 'USA', -12),
    '墨联': ('MX1', 'Liga MX', 'Mexico', -14),
    '巴西甲': ('BR1', 'Serie A', 'Brazil', -11),
    '巴西乙': ('BR2', 'Serie B', 'Brazil', -11),
    '智利甲': ('CL1', 'Primera Division', 'Chile', -12),
    '厄瓜甲': ('EC1', 'Serie A', 'Ecuador', -13),
    '阿甲': ('AR1', 'Primera Division', 'Argentina', -11),
    '阿乙': ('AR2', 'Primera B Nacional', 'Argentina', -11),
    '拉脱超': ('LV1', 'Virsliga', 'Latvia', -6),
    '新加联': ('SG1', 'S.League', 'Singapore', 0),
    '印度超': ('IN1', 'Indian Super League', 'India', -2.5),
    '中超': ('CN1', 'Chinese Super League', 'China', 0),
    '爱超': ('IE1', 'Premier Division', 'Ireland', -8),
}

# 球队名称映射（中文到英文）
TEAM_MAPPING = {
    # 意甲
    '亚特兰大': 'Atalanta', '博洛尼亚': 'Bologna', '卡利亚里': 'Cagliari', '都灵': 'Torino',
    '萨索洛': 'Sassuolo', '莱切': 'Lecce', '乌迪内斯': 'Udinese', '克雷莫纳': 'Cremonese',
    # 英超
    '纽卡斯尔': 'Newcastle', '西汉姆': 'West Ham', '阿森纳': 'Arsenal', '伯恩利': 'Burnley',
    # 西甲
    '毕尔巴鄂': 'Athletic Bilbao', '塞尔塔': 'Celta Vigo', '马竞': 'Atletico Madrid',
    '赫罗纳': 'Girona', '埃尔切': 'Elche', '赫塔费': 'Getafe', '莱万特': 'Levante',
    '马洛卡': 'Mallorca', '巴列卡诺': 'Rayo Vallecano', '比利亚雷': 'Villarreal',
    '皇家社会': 'Real Sociedad', '巴伦西亚': 'Valencia', '奥维耶多': 'Oviedo',
    '阿拉维斯': 'Alaves', '奥萨苏纳': 'Osasuna', '西班牙人': 'Espanyol',
    '塞维利亚': 'Sevilla', '皇马': 'Real Madrid', '巴萨': 'Barcelona', '贝蒂斯': 'Real Betis',
    # 法甲
    '洛里昂': 'Lorient', '勒阿弗尔': 'Le Havre', '南特': 'Nantes', '图卢兹': 'Toulouse',
    '里尔': 'Lille', '欧塞尔': 'Auxerre', '尼斯': 'Nice', '梅斯': 'Metz',
    '布雷斯特': 'Brest', '昂热': 'Angers', '巴黎FC': 'Paris FC', '巴黎圣曼': 'Paris SG',
    '马赛': 'Marseille', '雷恩': 'Rennes', '斯特拉斯': 'Strasbourg', '摩纳哥': 'Monaco',
    '里昂': 'Lyon', '朗斯': 'Lens',
    # 德甲/德乙
    '达姆施塔特': 'Darmstadt', '帕德博恩': 'Paderborn',
    # 其他
    '索尔': 'Thorr', 'IA阿克拉内斯': 'IA Akranes', '利耶帕亚': 'Liepaja', '道加瓦': 'Daugava',
    '奥胡斯': 'Aarhus', '维堡': 'Viborg', '中日德兰': 'Midtjylland', '布隆德比': 'Brondby',
    '桑德捷斯基': 'Sandefjord', '北西兰': 'Nordsjaelland', '瓦奇巴托': 'Huachipato', '卡拉雷': 'Cobreloa',
    '雅典AEK': 'AEK Athens', '奥林匹亚科斯': 'Olympiacos', '帕纳辛纳科斯': 'Panathinaikos',
    '塞萨洛尼基': 'PAOK', '布鲁日': 'Club Brugge', '圣吉罗斯': 'Union SG',
    '苏杜利察': 'Suduca', '贝尔格莱德红星': 'Crvena Zvezda', '伊斯特拉': 'Istra', '里耶卡': 'Rijeka',
    '费内巴切': 'Fenerbahce', '埃伊乌斯堡': 'Istanbulspor', '卡斯帕萨': 'Kasimpasa',
    '加拉塔萨雷': 'Galatasaray', '特拉布宗': 'Trabzonspor', '根克勒比利吉': 'Genclerbirligi',
    '安塔利亚': 'Antalyaspor', '科贾埃利体育': 'Kocaelispor', '雷克斯欧斯': 'Vila Real',
    '卢西塔尼亚': 'Lusitania', '哈夫纳夫约杜尔': 'FH Hafnarfjordur', 'KA阿克雷里': 'KA Akureyri',
    '凯夫拉维克': 'Keflavik', '斯塔尔南': 'Stjarnan', '克拉约瓦': 'Craiova', '克鲁日大学': 'U Cluj',
    '卡坦萨罗': 'Catanzaro', '巴勒莫': 'Palermo', '马德林': 'Madryn', '西部铁路': 'Trenque Lauquen',
    'OFK贝尔格莱德': 'OFK Beograd', '沃伊沃迪纳': 'Vojvodina', '利雅青年': 'Al Raed',
    '吉达联合': 'Al Ittihad', '瓦路尔': 'Valur', '贝雷达': 'Breidablik',
    '雷克雅未克': 'KR Reykjavik', '弗拉姆': 'Fram', '胡胡伊体操击剑': 'Gimnasia Jujuy',
    'CA坦波利': 'Talleres Cordoba', '阿尔马格罗': 'Almagro', '圣胡安圣马丁': 'San Martin SJ',
    '博塔弗戈': 'Botafogo', '科林蒂安': 'Corinthians', '巴伊亚': 'Bahia', '格雷米奥': 'Gremio',
    '帕特罗纳图': 'Patronato', '查卡瑞塔青年': 'Chacarita Juniors', '科布雷萨尔': 'Cobreloa',
    '智利大学': 'U de Chile', '德雷竞技': 'Operario', '尤文图德': 'Juventude',
    '萨拉戈萨': 'Zaragoza', '希洪竞技': 'Sporting Gijon', '费雷拉': 'Pacos Ferreira',
    '佩纳菲耶尔': 'Penafiel', '波尔蒂芒斯': 'Portimonense', '法伦斯': 'Farense',
    '阿根廷青年人': 'Argentinos Juniors', '贝尔格拉诺': 'Belgrano', '迈普': 'Maique',
    '新芝加哥': 'Nueva Chicago', '基尔梅斯': 'Quilmes', '苏亚雷斯': 'Luis Suarez',
    '萨尔塔体操和射击': 'Gimnasia Salta', '图库曼圣马丁': 'San Martin Tucuman',
    '维拉诺瓦': 'Vila Nova', '阿瓦伊': 'Avai', '布拉干蒂诺': 'Bragantino', '维多利亚': 'Vitoria',
    '沙佩科恩斯': 'Chapecoense', '瑞模': 'Remo', '科洛科洛': 'Colo Colo', '纽布伦斯': 'Nublense',
    '塞阿拉': 'Ceara', '福塔雷萨': 'Fortaleza', '克里西乌马': 'Criciuma', '戈亚尼亚竞技': 'Goiania',
    '迈阿密国际': 'Inter Miami', '波特兰伐木工': 'Portland Timbers', '巴拉纳竞技': 'Paranaense',
    '弗拉门戈': 'Flamengo', '曼塔FC': 'Manta', '埃梅莱克': 'Emelec', '累西腓体育': 'Sport Recife',
    'CR巴西': 'CR Brasil', '迪康塞普森体育': 'Deportes Concepcion', '维尼亚德尔马': 'Vina del Mar',
    '纳什维尔': 'Nashville', '洛杉矶FC': 'LAFC', '美洲狮': 'Pumas', '帕丘卡': 'Pachuca',
    '卢甘斯克黎明': 'Zorya', '波利西亚': 'Polissya', '丹戎巴葛': 'Tanjong Pagar', '后港联': 'Hougang',
    '喀拉拉邦': 'Kerala Blasters', '果阿': 'Goa', '拉赫蒂': 'Lahti', '瓦萨': 'VPS',
    '哈卡': 'Haka', '克鲁比04': 'Klubi 04', '阿尔卡': 'Arka', '尼切萨': 'Nieciecza',
    '松兹瓦尔': 'Sundsvall', '兰斯克鲁纳': 'Landskrona', '佐加顿斯': 'Djurgarden', '天狼星': 'Sirius',
    '厄尔格里特': 'Orgryte', '哥德堡': 'IFK Goteborg', '谢莫夏普尔': 'Hapoel Shmona',
    '阿什杜德': 'Ashdod', '海法夏普尔': 'Hapoel Haifa', '比尼萨赫宁': 'Bnei Sakhnin',
    '贝内雷讷马卡比': 'Maccabi Bnei Reineh', '内坦马卡比': 'Maccabi Netanya',
    '耶路夏普尔': 'Hapoel Jerusalem', '伊罗尼太巴列': 'Ironi Kiryat Shmona',
    '奥迪沃特': 'Odevall', '厄勒布鲁': 'Orebro', '法鲁尔': 'Farul', '梅塔洛': 'Metaloglobus',
    '普洛耶什蒂': 'Ploiesti', '加拉茨钢铁': 'Otelul Galati', '尤尼史洛波西亚': 'Unirea Slobozia',
    '阿拉德联合': 'UTA Arad', '赫曼施塔特': 'Hermannstadt', '布加勒斯特星': 'Steaua Bucuresti',
    '莱加内斯': 'Leganes', '韦斯卡': 'Huesca', '贝尔格拉诺守卫者': 'Guillermo Brown',
    '查科永久': 'Chaco For Ever', '沃特福德联队': 'Waterford', '德罗赫达联': 'Drogheda',
    '庞特普雷塔': 'Ponte Preta', '隆迪那': 'Londrina', '全男孩竞技': 'All Boys', '玛伦': 'Maron',
    '瓜亚基尔城': 'Delfin', '奥伦斯': 'Aucas', '东北联队': 'NorthEast United',
    'Mohammedan SC': 'Mohammedan SC', '天津津门虎': 'Tianjin', '河南俱乐部': 'Henan',
    '深圳新鹏城': 'Shenzhen', '大连英博': 'Dalian', '青岛西海岸': 'Qingdao West Coast',
    '北京国安': 'Beijing Guoan', '成都蓉城': 'Chengdu', '上海海港': 'Shanghai Port',
}

def parse_team_name(name):
    """解析球队名称，去掉排名标记"""
    # 去掉 [数字] 前缀
    name = re.sub(r'^\[\d+\]\s*', '', name)
    return name.strip()

def convert_time(beijing_time, offset):
    """北京时间转当地时间"""
    try:
        hours, minutes = map(int, beijing_time.split(':'))
        total_minutes = hours * 60 + minutes + int(offset * 60)
        if total_minutes < 0:
            total_minutes += 24 * 60
        elif total_minutes >= 24 * 60:
            total_minutes -= 24 * 60
        return f"{total_minutes // 60:02d}:{total_minutes % 60:02d}"
    except:
        return beijing_time

def main():
    # 比赛数据（从用户输入解析）
    matches_data = """
英超,05-18 00:30,[13] 纽卡斯尔,[18] 西汉姆,2.17,3.80,3.03
意甲,05-18 00:00,[7] 亚特兰大,[8] 博洛尼亚,1.73,3.97,4.44
西甲,05-18 01:00,[9] 毕尔巴鄂,[6] 塞尔塔,2.21,3.20,3.46
西甲,05-18 01:00,[4] 马竞,[15] 赫罗纳,1.74,3.96,4.43
西甲,05-18 01:00,[17] 埃尔切,[7] 赫塔费,2.30,2.94,3.57
西甲,05-18 01:00,[19] 莱万特,[18] 马洛卡,2.10,3.43,3.49
西甲,05-18 01:00,[10] 巴列卡诺,[3] 比利亚雷,2.03,3.60,3.51
西甲,05-18 01:00,[8] 皇家社会,[11] 巴伦西亚,2.24,3.36,3.21
西甲,05-18 01:00,[20] 奥维耶多,[16] 阿拉维斯,3.91,3.33,2.00
西甲,05-18 01:00,[13] 奥萨苏纳,[14] 西班牙人,2.17,2.90,4.02
西甲,05-18 01:00,[12] 塞维利亚,[2] 皇马,3.20,3.52,2.19
西甲,05-18 03:15,[1] 巴萨,[5] 贝蒂斯,1.33,5.83,7.72
意甲,05-18 02:45,[16] 卡利亚里,[12] 都灵,2.31,3.06,3.38
意甲,05-18 02:45,[11] 萨索洛,[17] 莱切,2.67,3.20,2.72
意甲,05-18 02:45,[10] 乌迪内斯,[18] 克雷莫纳,2.45,3.20,2.99
法甲,05-18 03:00,[9] 洛里昂,[14] 勒阿弗尔,2.61,3.45,2.61
法甲,05-18 03:00,[17] 南特,[10] 图卢兹,2.58,3.49,2.60
法甲,05-18 03:00,[3] 里尔,[15] 欧塞尔,1.39,4.82,7.84
法甲,05-18 03:00,[16] 尼斯,[18] 梅斯,1.31,5.57,8.84
法甲,05-18 03:00,[12] 布雷斯特,[13] 昂热,1.83,3.70,4.19
法甲,05-18 03:00,[11] 巴黎FC,[1] 巴黎圣曼,4.84,4.55,1.59
法甲,05-18 03:00,[6] 马赛,[5] 雷恩,2.00,3.96,3.28
法甲,05-18 03:00,[8] 斯特拉斯,[7] 摩纳哥,3.05,4.02,2.08
法甲,05-18 03:00,[4] 里昂,[2] 朗斯,1.68,4.20,4.43
英超,05-19 03:00,[1] 阿森纳,[19] 伯恩利,1.08,11.47,25.39
美职,05-18 08:00,[3] 纳什维尔,[11] 洛杉矶FC,2.18,3.40,3.11
芬超,05-18 23:00,[8] 拉赫蒂,[6] 瓦萨,2.24,3.15,3.08
瑞典超,05-19 01:00,[4] 佐加顿斯,[1] 天狼星,2.20,3.61,2.85
瑞典超,05-19 01:00,[14] 厄尔格里特,[16] 哥德堡,3.75,3.67,1.84
"""

    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()

    # 获取联赛ID
    cursor.execute("SELECT league_id, name, country FROM leagues")
    leagues_db = {row[1]: {'id': row[0], 'country': row[2]} for row in cursor.fetchall()}

    # 获取球队ID
    cursor.execute("SELECT team_id, canonical_name FROM teams")
    teams_db = {row[1]: row[0] for row in cursor.fetchall()}

    added = 0
    for line in matches_data.strip().split('\n'):
        parts = line.split(',')
        if len(parts) < 6:
            continue

        league_cn = parts[0]
        date_time = parts[1]
        home_cn = parse_team_name(parts[2])
        away_cn = parse_team_name(parts[3])
        home_odds = float(parts[4]) if parts[4] else None
        draw_odds = float(parts[5]) if parts[5] else None
        away_odds = float(parts[6]) if len(parts) > 6 and parts[6] else None

        # 解析日期和时间
        date_parts = date_time.split()
        if len(date_parts) != 2:
            continue
        match_date = f"2026-{date_parts[0]}"
        match_time = date_parts[1]

        # 获取联赛信息
        league_info = LEAGUE_MAPPING.get(league_cn)
        if not league_info:
            print(f"Unknown league: {league_cn}")
            continue

        league_code, league_name, country, offset = league_info

        # 转换时间
        local_time = convert_time(match_time, offset)

        # 转换球队名称
        home_en = TEAM_MAPPING.get(home_cn, home_cn)
        away_en = TEAM_MAPPING.get(away_cn, away_cn)

        # 获取联赛ID
        league_data = leagues_db.get(league_name)
        if not league_data:
            print(f"League not in DB: {league_name}")
            continue
        league_id = league_data['id']

        # 获取球队ID
        home_team_id = teams_db.get(home_en)
        away_team_id = teams_db.get(away_en)

        if not home_team_id or not away_team_id:
            print(f"Team not found: {home_en} ({home_team_id}) vs {away_en} ({away_team_id})")
            continue

        # 检查是否已存在
        cursor.execute('''
            SELECT match_id FROM matches
            WHERE league_id = ? AND match_date = ?
            AND home_team_id = ? AND away_team_id = ?
        ''', (league_id, match_date, home_team_id, away_team_id))

        if cursor.fetchone():
            print(f"Already exists: {match_date} {home_en} vs {away_en}")
            continue

        # 插入比赛
        cursor.execute('''
            INSERT INTO matches (
                league_id, match_date, match_time,
                home_team_id, away_team_id,
                home_odds, draw_odds, away_odds,
                original_home_team, original_away_team,
                status
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'Scheduled')
        ''', (
            league_id, match_date, local_time,
            home_team_id, away_team_id,
            home_odds, draw_odds, away_odds,
            home_en, away_en
        ))
        added += 1
        print(f"Added: {match_date} {local_time} {home_en} vs {away_en} ({league_name})")

    conn.commit()
    conn.close()
    print(f"\nTotal added: {added} matches")

if __name__ == '__main__':
    main()
