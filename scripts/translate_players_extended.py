#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
扩展球员中文名词典
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

# 扩展球员中文名词典
PLAYER_NAMES = {
    # 英超球员
    'Mohamed Salah': '萨拉赫',
    'Erling Haaland': '哈兰德',
    'Kevin De Bruyne': '德布劳内',
    'Bukayo Saka': '萨卡',
    'Martin Odegaard': '厄德高',
    'Gabriel Jesus': '热苏斯',
    'Gabriel Magalhaes': '加布里埃尔',
    'William Saliba': '萨利巴',
    'Ben White': '本·怀特',
    'Aaron Ramsdale': '拉姆斯代尔',
    'Takehiro Tomiyasu': '富安健洋',
    'Kieran Tierney': '蒂尔尼',
    'Granit Xhaka': '扎卡',
    'Thomas Partey': '帕尔特伊',
    'Emile Smith Rowe': '史密斯-罗',
    'Reiss Nelson': '纳尔逊',
    'Eddie Nketiah': '恩凯蒂亚',
    'Leandro Trossard': '特罗萨德',
    'Kai Havertz': '哈弗茨',
    'Declan Rice': '赖斯',
    'Jurrien Timber': '廷伯',

    # 曼城球员
    'Phil Foden': '福登',
    'Bernardo Silva': '贝尔纳多·席尔瓦',
    'Rodri': '罗德里',
    'Jack Grealish': '格拉利什',
    'Ruben Dias': '鲁本·迪亚斯',
    'John Stones': '斯通斯',
    'Kyle Walker': '沃克',
    'Ederson': '埃德森',
    'Aymeric Laporte': '拉波尔特',
    'Ilkay Gundogan': '京多安',
    'Riyad Mahrez': '马赫雷斯',
    'Raheem Sterling': '斯特林',
    'Joao Cancelo': '坎塞洛',

    # 曼联球员
    'Marcus Rashford': '拉什福德',
    'Bruno Fernandes': '布鲁诺·费尔南德斯',
    'Casemiro': '卡塞米罗',
    'Raphael Varane': '瓦拉内',
    'Luke Shaw': '卢克·肖',
    'Harry Maguire': '马奎尔',
    'Aaron Wan-Bissaka': '万-比萨卡',
    'Diogo Dalot': '达洛特',
    'Jadon Sancho': '桑乔',
    'Anthony Martial': '马夏尔',
    'Antony': '安东尼',
    'Alejandro Garnacho': '加纳乔',
    'Mason Mount': '芒特',
    'Rasmus Hojlund': '霍伊伦',
    'Andre Onana': '奥纳纳',

    # 利物浦球员
    'Virgil van Dijk': '范戴克',
    'Alisson Becker': '阿利松',
    'Trent Alexander-Arnold': '阿诺德',
    'Andrew Robertson': '罗伯逊',
    'Darwin Nunez': '努涅斯',
    'Luis Diaz': '迪亚斯',
    'Cody Gakpo': '加克波',
    'Mohamed Elneny': '埃尔内尼',
    'Thiago Alcantara': '蒂亚戈',
    'Fabinho': '法比尼奥',
    'Jordan Henderson': '亨德森',
    'Sadio Mane': '马内',
    'Roberto Firmino': '菲尔米诺',

    # 切尔西球员
    'Enzo Fernandez': '恩佐·费尔南德斯',
    'Mykhailo Mudryk': '穆德里克',
    'Noni Madueke': '马杜埃凯',
    'Raheem Sterling': '斯特林',
    'Nicolas Jackson': '杰克逊',
    'Cole Palmer': '帕尔默',
    'Reece James': '里斯·詹姆斯',
    'Ben Chilwell': '奇尔韦尔',
    'Wesley Fofana': '福法纳',
    'Kepa Arrizabalaga': '凯帕',
    'Mason Mount': '芒特',
    'Kai Havertz': '哈弗茨',
    'Christian Pulisic': '普利西奇',
    'Pierre-Emerick Aubameyang': '奥巴梅扬',
    'Alexandre Lacazette': '拉卡泽特',

    # 热刺球员
    'Harry Kane': '凯恩',
    'Son Heung-min': '孙兴慜',
    'Dejan Kulusevski': '库卢塞夫斯基',
    'Richarlison': '理查利森',
    'James Maddison': '麦迪逊',
    'Brennan Johnson': '布伦南·约翰逊',
    'Cristian Romero': '罗梅罗',
    'Micky van de Ven': '范德芬',
    'Pedro Porro': '波罗',
    'Destiny Udogie': '乌多吉',
    'Guglielmo Vicario': '维卡里奥',

    # 皇马球员
    'Vinicius Junior': '维尼修斯',
    'Kylian Mbappe': '姆巴佩',
    'Jude Bellingham': '贝林厄姆',
    'Rodrygo': '罗德里戈',
    'Luka Modric': '莫德里奇',
    'Toni Kroos': '克罗斯',
    'David Alaba': '阿拉巴',
    'Antonio Rudiger': '吕迪格',
    'Thibaut Courtois': '库尔图瓦',
    'Eder Militao': '米利唐',
    'Federico Valverde': '巴尔韦德',
    'Aurelien Tchouameni': '楚阿梅尼',
    'Eduardo Camavinga': '卡马文加',

    # 巴萨球员
    'Robert Lewandowski': '莱万多夫斯基',
    'Pedri': '佩德里',
    'Gavi': '加维',
    'Ilkay Gundogan': '京多安',
    'Frenkie de Jong': '德容',
    'Ronald Araujo': '阿劳霍',
    'Jules Kounde': '孔德',
    'Marc-Andre ter Stegen': '特尔施特根',
    'Raphinha': '拉菲尼亚',
    'Ferran Torres': '费兰·托雷斯',
    'Ansu Fati': '法蒂',
    'Lamine Yamal': '亚马尔',

    # 拜仁球员
    'Manuel Neuer': '诺伊尔',
    'Joshua Kimmich': '基米希',
    'Leon Goretzka': '格雷茨卡',
    'Thomas Muller': '穆勒',
    'Leroy Sane': '萨内',
    'Kingsley Coman': '科曼',
    'Serge Gnabry': '格纳布里',
    'Jamal Musiala': '穆西亚拉',
    'Matthijs de Ligt': '德里赫特',
    'Dayot Upamecano': '于帕梅卡诺',
    'Kim Min-jae': '金玟哉',
    'Harry Kane': '凯恩',

    # 多特球员
    'Marco Reus': '罗伊斯',
    'Jude Bellingham': '贝林厄姆',
    'Erling Haaland': '哈兰德',
    'Mats Hummels': '胡梅尔斯',
    'Niklas Sule': '聚勒',
    'Sebastien Haller': '阿莱',
    'Donyell Malen': '马伦',
    'Karim Adeyemi': '阿德耶米',

    # 尤文球员
    'Federico Chiesa': '基耶萨',
    'Dusan Vlahovic': '弗拉霍维奇',
    'Weston McKennie': '麦肯尼',
    'Manuel Locatelli': '洛卡特利',
    'Adrien Rabiot': '拉比奥特',
    'Gleison Bremer': '布雷默',
    'Danilo': '达尼洛',
    'Wojciech Szczesny': '什琴斯尼',

    # 国米球员
    'Lautaro Martinez': '劳塔罗·马丁内斯',
    'Romelu Lukaku': '卢卡库',
    'Nicolò Barella': '巴雷拉',
    'Marcelo Brozovic': '布罗佐维奇',
    'Milan Skriniar': '什克里尼亚尔',
    'Alessandro Bastoni': '巴斯托尼',
    'Hakan Calhanoglu': '恰尔汗奥卢',
    'Andre Onana': '奥纳纳',

    # AC米兰球员
    'Rafael Leao': '莱奥',
    'Olivier Giroud': '吉鲁',
    'Theo Hernandez': '特奥·埃尔南德斯',
    'Sandro Tonali': '托纳利',
    'Ismael Bennacer': '本纳塞尔',
    'Mike Maignan': '迈尼昂',
    'Christian Pulisic': '普利西奇',

    # 巴黎球员
    'Lionel Messi': '梅西',
    'Neymar': '内马尔',
    'Kylian Mbappe': '姆巴佩',
    'Marco Asensio': '阿森西奥',
    'Gianluigi Donnarumma': '多纳鲁马',
    'Marquinhos': '马尔基尼奥斯',
    'Achraf Hakimi': '阿什拉夫',
    'Vitinha': '维蒂尼亚',
    'Warren Zaire-Emery': '扎伊尔-埃梅里',

    # 其他球星
    'Cristiano Ronaldo': 'C罗',
    'Karim Benzema': '本泽马',
    'Eden Hazard': '阿扎尔',
    'Jan Oblak': '奥布拉克',
    'Paul Pogba': '博格巴',
    'Antoine Griezmann': '格列兹曼',
    'Diego Costa': '迭戈·科斯塔',
    'Sergio Aguero': '阿圭罗',
    'David Silva': '大卫·席尔瓦',
    'Yaya Toure': '亚亚·图雷',
    'Carlos Tevez': '特维斯',
    'Wayne Rooney': '鲁尼',
    'Robin van Persie': '范佩西',
    'Thierry Henry': '亨利',
    'Dennis Bergkamp': '博格坎普',
    'Zinedine Zidane': '齐达内',
    'Ronaldinho': '罗纳尔迪尼奥',
    'Ronaldo': '罗纳尔多',
    'Kaka': '卡卡',
    'Andrea Pirlo': '皮尔洛',
    'Francesco Totti': '托蒂',
    'Alessandro Del Piero': '德尔·皮耶罗',
    'Paolo Maldini': '马尔蒂尼',
    'Gianluigi Buffon': '布冯',
    'Iker Casillas': '卡西利亚斯',
    'Xavi': '哈维',
    'Andres Iniesta': '伊涅斯塔',
    'Sergio Ramos': '拉莫斯',
    'Gerard Pique': '皮克',
    'Carles Puyol': '普约尔',
}


def translate_players():
    """翻译球员名"""
    print("=" * 60)
    print("Translating Player Names (Extended)")
    print("=" * 60)

    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()

    translated = 0
    not_found = 0

    for en_name, cn_name in PLAYER_NAMES.items():
        cursor.execute(
            "UPDATE players SET name_cn = ?, updated_at = datetime('now') WHERE name_en = ? AND name_cn IS NULL",
            (cn_name, en_name)
        )
        if cursor.rowcount > 0:
            translated += 1
            print(f"  {en_name} -> {cn_name}")
        else:
            not_found += 1

    conn.commit()

    # 统计
    cursor.execute("SELECT COUNT(*) FROM players WHERE name_cn IS NOT NULL")
    total_cn = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM players")
    total = cursor.fetchone()[0]

    conn.close()

    print(f"\nTranslated: {translated}")
    print(f"Not found in DB: {not_found}")
    print(f"Total with Chinese: {total_cn}/{total} ({total_cn/total*100:.1f}%)")


if __name__ == '__main__':
    translate_players()