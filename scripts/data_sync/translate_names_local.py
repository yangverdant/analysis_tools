#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
翻译中文名 - 使用本地词典
"""

import os
import sys
import sqlite3
from pathlib import Path

if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

PROJECT_ROOT = Path(__file__).parent.parent
DATABASE_PATH = PROJECT_ROOT / 'data' / 'football_v2.db'

# 常见球队中文名词典
TEAM_NAMES = {
    # 英超
    'Arsenal FC': '阿森纳',
    'Chelsea FC': '切尔西',
    'Liverpool FC': '利物浦',
    'Manchester City FC': '曼城',
    'Manchester United FC': '曼联',
    'Tottenham Hotspur FC': '热刺',
    'Newcastle United FC': '纽卡斯尔',
    'Aston Villa FC': '阿斯顿维拉',
    'Brighton & Hove Albion FC': '布莱顿',
    'West Ham United FC': '西汉姆联',
    'Crystal Palace FC': '水晶宫',
    'Everton FC': '埃弗顿',
    'Fulham FC': '富勒姆',
    'Brentford FC': '布伦特福德',
    'Wolverhampton Wanderers FC': '狼队',
    'AFC Bournemouth': '伯恩茅斯',
    'Nottingham Forest FC': '诺丁汉森林',
    'Leicester City FC': '莱斯特城',
    'Southampton FC': '南安普顿',
    'Leeds United FC': '利兹联',
    'Burnley FC': '伯恩利',
    'Sunderland AFC': '桑德兰',

    # 西甲
    'FC Barcelona': '巴塞罗那',
    'Real Madrid CF': '皇家马德里',
    'Club Atlético de Madrid': '马德里竞技',
    'Athletic Club': '毕尔巴鄂竞技',
    'Real Sociedad de Fútbol': '皇家社会',
    'Sevilla FC': '塞维利亚',
    'Villarreal CF': '比利亚雷亚尔',
    'Real Betis Balompié': '皇家贝蒂斯',
    'Valencia CF': '瓦伦西亚',
    'Getafe CF': '赫塔费',
    'RC Celta de Vigo': '塞尔塔',
    'RCD Mallorca': '马洛卡',
    'CA Osasuna': '奥萨苏纳',
    'Deportivo Alavés': '阿拉维斯',
    'Girona FC': '赫罗纳',
    'Rayo Vallecano de Madrid': '巴列卡诺',

    # 德甲
    'FC Bayern München': '拜仁慕尼黑',
    'Borussia Dortmund': '多特蒙德',
    'RB Leipzig': '莱比锡红牛',
    'Bayer 04 Leverkusen': '勒沃库森',
    'Borussia Mönchengladbach': '门兴格拉德巴赫',
    'VfL Wolfsburg': '沃尔夫斯堡',
    'Eintracht Frankfurt': '法兰克福',
    'TSG 1899 Hoffenheim': '霍芬海姆',
    'SC Freiburg': '弗赖堡',
    '1. FC Union Berlin': '柏林联合',
    'VfB Stuttgart': '斯图加特',
    'FC Augsburg': '奥格斯堡',
    '1. FSV Mainz 05': '美因茨',
    'SV Werder Bremen': '云达不来梅',
    '1. FC Köln': '科隆',
    'Hamburger SV': '汉堡',

    # 意甲
    'Juventus FC': '尤文图斯',
    'FC Internazionale Milano': '国际米兰',
    'AC Milan': 'AC米兰',
    'SSC Napoli': '那不勒斯',
    'AS Roma': '罗马',
    'SS Lazio': '拉齐奥',
    'Atalanta BC': '亚特兰大',
    'ACF Fiorentina': '佛罗伦萨',
    'Bologna FC 1909': '博洛尼亚',
    'Torino FC': '都灵',
    'Udinese Calcio': '乌迪内斯',
    'Cagliari Calcio': '卡利亚里',
    'Genoa CFC': '热那亚',
    'US Sassuolo Calcio': '萨索洛',
    'Hellas Verona FC': '维罗纳',
    'US Lecce': '莱切',

    # 法甲
    'Paris Saint-Germain FC': '巴黎圣日耳曼',
    'Olympique de Marseille': '马赛',
    'Olympique Lyonnais': '里昂',
    'Lille OSC': '里尔',
    'AS Monaco FC': '摩纳哥',
    'OGC Nice': '尼斯',
    'Stade Rennais FC 1901': '雷恩',
    'RC Strasbourg Alsace': '斯特拉斯堡',
    'FC Nantes': '南特',
    'Toulouse FC': '图卢兹',
    'Racing Club de Lens': '朗斯',
    'Stade Brestois 29': '布雷斯特',
    'FC Lorient': '洛里昂',
    'Montpellier HSC': '蒙彼利埃',
    'Angers SCO': '昂热',

    # 欧冠球队
    'Sporting Clube de Portugal': '葡萄牙体育',
    'FC Porto': '波尔图',
    'Sport Lisboa e Benfica': '本菲卡',
    'AFC Ajax': '阿贾克斯',
    'PSV': '埃因霍温',
    'Feyenoord Rotterdam': '费耶诺德',
    'Club Brugge KV': '布鲁日',
    'Galatasaray SK': '加拉塔萨雷',
    'SK Slavia Praha': '布拉格斯拉维亚',
    'FC København': '哥本哈根',
    'PAE Olympiakos SFP': '奥林匹亚科斯',
    'FK Bodø/Glimt': '博德闪耀',

    # 荷甲
    'FC Twente \'65': '特温特',
    'FC Utrecht': '乌得勒支',
    'AZ': '阿尔克马尔',
    'Heracles Almelo': '海伦芬',
    'SC Heerenveen': '海伦芬',
    'FC Groningen': '格罗宁根',
    'NEC': '奈梅亨',
    'PEC Zwolle': '兹沃勒',
    'Go Ahead Eagles': '前进之鹰',
    'Fortuna Sittard': '锡塔德幸运',
    'Sparta Rotterdam': '鹿特丹斯巴达',

    # 英冠
    'Blackburn Rovers FC': '布莱克本',
    'Norwich City FC': '诺维奇',
    'Queens Park Rangers FC': '女王公园巡游者',
    'Stoke City FC': '斯托克城',
    'Swansea City AFC': '斯旺西',
    'West Bromwich Albion FC': '西布朗',
    'Hull City AFC': '赫尔城',
    'Portsmouth FC': '朴茨茅斯',
    'Birmingham City FC': '伯明翰',
    'Derby County FC': '德比郡',
    'Middlesbrough FC': '米德尔斯堡',
    'Sheffield Wednesday FC': '谢菲尔德星期三',
    'Sheffield United FC': '谢菲尔德联',
    'Watford FC': '沃特福德',
    'Charlton Athletic FC': '查尔顿',
    'Ipswich Town FC': '伊普斯维奇',
    'Millwall FC': '米尔沃尔',
    'Bristol City FC': '布里斯托尔城',
    'Coventry City FC': '考文垂',
    'Preston North End FC': '普雷斯顿',
    'Wrexham AFC': '雷克瑟姆',
    'Oxford United FC': '牛津联',
}


def translate_teams():
    """翻译球队名"""
    print("=" * 60)
    print("Translating Team Names")
    print("=" * 60)

    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()

    translated = 0

    for en_name, cn_name in TEAM_NAMES.items():
        cursor.execute(
            "UPDATE teams SET name_cn = ?, updated_at = datetime('now') WHERE name_en = ? AND name_cn IS NULL",
            (cn_name, en_name)
        )
        if cursor.rowcount > 0:
            translated += 1
            print(f"  {en_name} -> {cn_name}")

    conn.commit()
    conn.close()

    print(f"\nTotal translated: {translated}")
    return translated


def translate_players():
    """翻译球员名 - 使用常见球员词典"""
    print("\n" + "=" * 60)
    print("Translating Player Names")
    print("=" * 60)

    # 常见球员中文名
    PLAYER_NAMES = {
        'Mohamed Salah': '萨拉赫',
        'Erling Haaland': '哈兰德',
        'Kevin De Bruyne': '德布劳内',
        'Vinicius Junior': '维尼修斯',
        'Kylian Mbappe': '姆巴佩',
        'Jude Bellingham': '贝林厄姆',
        'Harry Kane': '凯恩',
        'Lionel Messi': '梅西',
        'Cristiano Ronaldo': 'C罗',
        'Robert Lewandowski': '莱万多夫斯基',
        'Karim Benzema': '本泽马',
        'Sadio Mane': '马内',
        'Virgil van Dijk': '范戴克',
        'Mohamed Elneny': '埃尔内尼',
        'Bukayo Saka': '萨卡',
        'Martin Odegaard': '厄德高',
        'Gabriel Jesus': '热苏斯',
        'Emile Smith Rowe': '史密斯-罗',
        'Raheem Sterling': '斯特林',
        'Phil Foden': '福登',
        'Bernardo Silva': '贝尔纳多·席尔瓦',
        'Ruben Dias': '鲁本·迪亚斯',
        'Rodri': '罗德里',
        'Jack Grealish': '格拉利什',
        'Marcus Rashford': '拉什福德',
        'Bruno Fernandes': '布鲁诺·费尔南德斯',
        'Casemiro': '卡塞米罗',
        'Raphael Varane': '瓦拉内',
        'Luke Shaw': '卢克·肖',
        'Paul Pogba': '博格巴',
        'Eden Hazard': '阿扎尔',
        'Luka Modric': '莫德里奇',
        'Toni Kroos': '克罗斯',
        'David Alaba': '阿拉巴',
        'Thibaut Courtois': '库尔图瓦',
        'Jan Oblak': '奥布拉克',
        'Marc-Andre ter Stegen': '特尔施特根',
        'Manuel Neuer': '诺伊尔',
        'Alisson Becker': '阿利松',
        'Ederson': '埃德森',
        'Kepa Arrizabalaga': '凯帕',
        'Pierre-Emerick Aubameyang': '奥巴梅扬',
        'Alexandre Lacazette': '拉卡泽特',
        'Nicolas Pepe': '佩佩',
        'Thomas Partey': '帕尔特伊',
        'Granit Xhaka': '扎卡',
        'Hector Bellerin': '贝莱林',
        'Kieran Tierney': '蒂尔尼',
        'Takehiro Tomiyasu': '富安健洋',
        'Ben White': '本·怀特',
    }

    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()

    translated = 0

    for en_name, cn_name in PLAYER_NAMES.items():
        cursor.execute(
            "UPDATE players SET name_cn = ?, updated_at = datetime('now') WHERE name_en = ? AND name_cn IS NULL",
            (cn_name, en_name)
        )
        if cursor.rowcount > 0:
            translated += 1
            print(f"  {en_name} -> {cn_name}")

    conn.commit()
    conn.close()

    print(f"\nTotal translated: {translated}")
    return translated


def main():
    teams = translate_teams()
    players = translate_players()

    print("\n" + "=" * 60)
    print(f"Summary: Teams={teams}, Players={players}")
    print("=" * 60)


if __name__ == '__main__':
    main()