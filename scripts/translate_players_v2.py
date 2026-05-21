#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
扩展球员中文名词典 V2 - 更多球员
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

# 更多球员中文名词典
PLAYER_NAMES = {
    # 英超球员 - 阿森纳
    'Gabriel Martinelli': '马丁内利',
    'Kieran Tierney': '蒂尔尼',
    'Thomas Partey': '帕尔特伊',
    'Granit Xhaka': '扎卡',
    'Emile Smith Rowe': '史密斯-罗',
    'Takehiro Tomiyasu': '富安健洋',
    'Oleksandr Zinchenko': '津琴科',
    'Jorginho': '若日尼奥',

    # 英超球员 - 切尔西
    'Moises Caicedo': '凯塞多',
    'Romeo Lavia': '拉维亚',
    'Christopher Nkunku': '恩昆库',
    'Nicolas Jackson': '杰克逊',
    'Armando Broja': '布罗亚',
    'Conor Gallagher': '加拉格尔',
    'Levi Colwill': '科尔维尔',
    'Robert Sanchez': '罗伯特·桑切斯',

    # 英超球员 - 利物浦
    'Dominik Szoboszlai': '索博斯洛伊',
    'Alexis Mac Allister': '麦卡利斯特',
    'Wataru Endo': '远藤航',
    'Ryan Gravenberch': '赫拉芬贝赫',
    'Curtis Jones': '柯蒂斯·琼斯',
    'Harvey Elliott': '埃利奥特',
    'Stefan Bajcetic': '巴伊切蒂奇',
    'Joe Gomez': '戈麦斯',
    'Ibrahima Konate': '科纳特',
    'Andrew Robertson': '罗伯逊',
    'Kostas Tsimikas': '齐米卡斯',
    'Caoimhin Kelleher': '凯莱赫',

    # 英超球员 - 曼城
    'Jeremy Doku': '多库',
    'Mateo Kovacic': '科瓦契奇',
    'Matheus Nunes': '努内斯',
    'Kalvin Phillips': '菲利普斯',
    'Nathan Ake': '阿克',
    'Manuel Akanji': '阿坎吉',
    'Josko Gvardiol': '格瓦迪奥尔',
    'Sergio Gomez': '塞尔吉奥·戈麦斯',

    # 英超球员 - 曼联
    'Lisandro Martinez': '利桑德罗·马丁内斯',
    'Victor Lindelof': '林德洛夫',
    'Tyrell Malacia': '马拉西亚',
    'Sofyan Amrabat': '阿姆拉巴特',
    'Christian Eriksen': '埃里克森',
    'Scott McTominay': '麦克托米奈',
    'Facundo Pellistri': '佩利斯特里',
    'Amad Diallo': '阿马德·迪亚洛',
    'Anthony Elanga': '埃兰加',

    # 英超球员 - 热刺
    'Yves Bissouma': '比苏马',
    'Pape Matar Sarr': '萨尔',
    'Oliver Skipp': '斯基普',
    'Rodrigo Bentancur': '本坦库尔',
    'Yves Bissouma': '比苏马',
    'Emerson Royal': '埃默松',
    'Ben Davies': '本·戴维斯',

    # 英超球员 - 纽卡斯尔
    'Alexander Isak': '伊萨克',
    'Anthony Gordon': '安东尼·戈登',
    'Sandro Tonali': '托纳利',
    'Bruno Guimaraes': '吉马良斯',
    'Joelinton': '乔林顿',
    'Callum Wilson': '威尔逊',
    'Kieran Trippier': '特里皮尔',
    'Sven Botman': '博特曼',
    'Nick Pope': '波普',

    # 英超球员 - 阿斯顿维拉
    'Ollie Watkins': '沃特金斯',
    'John McGinn': '麦金',
    'Douglas Luiz': '道格拉斯·路易斯',
    'Jacob Ramsey': '拉姆齐',
    'Leon Bailey': '利昂·贝利',
    'Moussa Diaby': '迪亚比',
    'Pau Torres': '保·托雷斯',
    'Emiliano Martinez': '埃米利亚诺·马丁内斯',
    'Ezri Konsa': '康萨',
    'Matty Cash': '卡什',

    # 英超球员 - 布莱顿
    'Kaoru Mitoma': '三笘薰',
    'Alexis Mac Allister': '麦卡利斯特',
    'Moises Caicedo': '凯塞多',
    'Solly March': '马奇',
    'Pascal Gross': '格罗斯',
    'Danny Welbeck': '维尔贝克',
    'Evan Ferguson': '弗格森',
    'Lewis Dunk': '邓克',
    'Jason Steele': '斯蒂尔',

    # 英超球员 - 西汉姆
    'Jarrod Bowen': '鲍恩',
    'Mohammed Kudus': '库杜斯',
    'James Ward-Prowse': '沃德-普劳斯',
    'Lucas Paqueta': '帕奎塔',
    'Michail Antonio': '安东尼奥',
    'Tomas Soucek': '绍切克',
    'Declan Rice': '赖斯',
    'Kurt Zouma': '祖马',
    'Vladimir Coufal': '曹法尔',
    'Alphonse Areola': '阿雷奥拉',

    # 西甲球员 - 皇马
    'Eder Militao': '米利唐',
    'Antonio Rudiger': '吕迪格',
    'Nacho Fernandez': '纳乔',
    'Dani Carvajal': '卡瓦哈尔',
    'Ferland Mendy': '费兰·门迪',
    'Lucas Vazquez': '巴斯克斯',
    'Dani Ceballos': '塞瓦略斯',
    'Eduardo Camavinga': '卡马文加',
    'Aurelien Tchouameni': '楚阿梅尼',
    'Federico Valverde': '巴尔韦德',
    'Arda Guler': '阿尔达·居莱尔',
    'Joselu': '何塞卢',
    'Andriy Lunin': '卢宁',

    # 西甲球员 - 巴萨
    'Ronald Araujo': '阿劳霍',
    'Jules Kounde': '孔德',
    'Andreas Christensen': '克里斯滕森',
    'Alejandro Balde': '巴尔德',
    'Sergi Roberto': '塞尔吉·罗贝托',
    'Franck Kessie': '凯西',
    'Ilkay Gundogan': '京多安',
    'Oriol Romeu': '奥里奥尔·罗梅乌',
    'Ferran Torres': '费兰·托雷斯',
    'Lamine Yamal': '亚马尔',
    'Joao Felix': '若昂·菲利克斯',
    'Joao Cancelo': '坎塞洛',
    'Robert Lewandowski': '莱万多夫斯基',

    # 西甲球员 - 马竞
    'Antoine Griezmann': '格列兹曼',
    'Alvaro Morata': '莫拉塔',
    'Memphis Depay': '德佩',
    'Angel Correa': '科雷亚',
    'Yannick Carrasco': '卡拉斯科',
    'Rodrigo De Paul': '德保罗',
    'Koke': '科克',
    'Saul Niguez': '萨乌尔',
    'Jose Gimenez': '希门尼斯',
    'Stefan Savic': '萨维奇',
    'Reinildo Mandava': '赖因尔多',
    'Jan Oblak': '奥布拉克',

    # 德甲球员 - 拜仁
    'Manuel Neuer': '诺伊尔',
    'Sven Ulreich': '乌尔赖希',
    'Min-jae Kim': '金玟哉',
    'Dayot Upamecano': '于帕梅卡诺',
    'Matthijs de Ligt': '德里赫特',
    'Noussair Mazraoui': '马兹拉维',
    'Alphonso Davies': '阿方索·戴维斯',
    'Konrad Laimer': '莱默尔',
    'Leon Goretzka': '格雷茨卡',
    'Jamal Musiala': '穆西亚拉',
    'Leroy Sane': '萨内',
    'Serge Gnabry': '格纳布里',
    'Kingsley Coman': '科曼',
    'Thomas Muller': '穆勒',
    'Harry Kane': '凯恩',
    'Eric Maxim Choupo-Moting': '舒波-莫廷',
    'Mathys Tel': '特尔',

    # 德甲球员 - 多特
    'Gregor Kobel': '科贝尔',
    'Mats Hummels': '胡梅尔斯',
    'Niklas Sule': '聚勒',
    'Nico Schlotterbeck': '施洛特贝克',
    'Raphael Guerreiro': '格雷罗',
    'Julian Ryerson': '赖尔森',
    'Emre Can': '埃姆雷·詹',
    'Salih Ozcan': '厄兹詹',
    'Jude Bellingham': '贝林厄姆',
    'Julian Brandt': '布兰特',
    'Marco Reus': '罗伊斯',
    'Giovanni Reyna': '雷纳',
    'Jamie Bynoe-Gittens': '拜诺-吉滕斯',
    'Donyell Malen': '马伦',
    'Sebastien Haller': '阿莱',
    'Karim Adeyemi': '阿德耶米',
    'Youssoufa Moukoko': '穆科科',

    # 德甲球员 - 勒沃库森
    'Florian Wirtz': '维尔茨',
    'Jonathan Tah': '塔',
    'Piero Hincapie': '因卡皮耶',
    'Edmond Tapsoba': '塔普索巴',
    'Exequiel Palacios': '帕拉西奥斯',
    'Robert Andrich': '安德利希',
    'Granit Xhaka': '扎卡',
    'Jonas Hofmann': '霍夫曼',
    'Amine Adli': '阿德利',
    'Victor Boniface': '博尼法斯',
    'Patrik Schick': '希克',

    # 意甲球员 - 尤文
    'Wojciech Szczesny': '什琴斯尼',
    'Mattia Perin': '佩林',
    'Gleison Bremer': '布雷默',
    'Danilo': '达尼洛',
    'Alex Sandro': '阿莱士·桑德罗',
    'Federico Gatti': '加蒂',
    'Manuel Locatelli': '洛卡特利',
    'Adrien Rabiot': '拉比奥特',
    'Weston McKennie': '麦肯尼',
    'Nicolo Fagioli': '法乔利',
    'Federico Chiesa': '基耶萨',
    'Dusan Vlahovic': '弗拉霍维奇',
    'Moise Kean': '基恩',
    'Arkadiusz Milik': '米利克',

    # 意甲球员 - 国米
    'Yann Sommer': '索默',
    'Milan Skriniar': '什克里尼亚尔',
    'Alessandro Bastoni': '巴斯托尼',
    'Francesco Acerbi': '阿切尔比',
    'Matteo Darmian': '达尔米安',
    'Denzel Dumfries': '邓弗里斯',
    'Nicolò Barella': '巴雷拉',
    'Marcelo Brozovic': '布罗佐维奇',
    'Hakan Calhanoglu': '恰尔汗奥卢',
    'Henrikh Mkhitaryan': '姆希塔良',
    'Lautaro Martinez': '劳塔罗·马丁内斯',
    'Marcus Thuram': '图拉姆',
    'Joaquin Correa': '科雷亚',
    'Marko Arnautovic': '阿瑙托维奇',

    # 意甲球员 - AC米兰
    'Mike Maignan': '迈尼昂',
    'Fikayo Tomori': '托莫里',
    'Theo Hernandez': '特奥·埃尔南德斯',
    'Simon Kjaer': '克亚尔',
    'Davide Calabria': '卡拉布里亚',
    'Pierre Kalulu': '卡卢卢',
    'Sandro Tonali': '托纳利',
    'Ismael Bennacer': '本纳塞尔',
    'Rade Krunic': '克鲁尼奇',
    'Yacine Adli': '阿德利',
    'Rafael Leao': '莱奥',
    'Olivier Giroud': '吉鲁',
    'Christian Pulisic': '普利西奇',
    'Samuel Chukwueze': '丘库埃泽',
    'Noah Okafor': '奥卡福',
    'Luka Jovic': '约维奇',

    # 意甲球员 - 那不勒斯
    'Alex Meret': '梅雷特',
    'Kim Min-jae': '金玟哉',
    'Giovanni Di Lorenzo': '迪洛伦佐',
    'Mario Rui': '马里奥·鲁伊',
    'Mathias Olivera': '奥利韦拉',
    'Andre-Frank Zambo Anguissa': '安古伊萨',
    'Stanislav Lobotka': '洛博特卡',
    'Piotr Zielinski': '泽林斯基',
    'Khvicha Kvaratskhelia': '克瓦拉茨赫利亚',
    'Victor Osimhen': '奥斯梅恩',
    'Giacomo Raspadori': '拉斯帕多里',
    'Giovanni Simeone': '西蒙尼',

    # 法甲球员 - 巴黎
    'Gianluigi Donnarumma': '多纳鲁马',
    'Keylor Navas': '纳瓦斯',
    'Marquinhos': '马尔基尼奥斯',
    'Presnel Kimpembe': '金彭贝',
    'Achraf Hakimi': '阿什拉夫',
    'Nuno Mendes': '努诺·门德斯',
    'Juan Bernat': '贝尔纳特',
    'Danilo Pereira': '达尼洛·佩雷拉',
    'Idrissa Gueye': '盖耶',
    'Vitinha': '维蒂尼亚',
    'Fabian Ruiz': '法比安·鲁伊斯',
    'Marco Asensio': '阿森西奥',
    'Warren Zaire-Emery': '扎伊尔-埃梅里',
    'Randal Kolo Muani': '科洛·穆阿尼',
    'Goncalo Ramos': '贡萨洛·拉莫斯',
    'Ousmane Dembele': '登贝莱',
    'Kylian Mbappe': '姆巴佩',
    'Neymar': '内马尔',
    'Lionel Messi': '梅西',

    # 法甲球员 - 马赛
    'Pau Lopez': '保·洛佩斯',
    'Chancel Mbemba': '姆班巴',
    'Leonardo Balerdi': '巴莱尔迪',
    'Jonathan Clauss': '克劳斯',
    'Valentin Rongier': '隆吉耶',
    'Mattéo Guendouzi': '贡多齐',
    'Jordan Veretout': '韦勒图',
    'Alexis Sanchez': '阿莱克西斯·桑切斯',
    'Cengiz Under': '云代尔',
    'Amine Harit': '哈里特',
    'Pierre-Emerick Aubameyang': '奥巴梅扬',

    # 法甲球员 - 里昂
    'Anthony Lopes': '洛佩斯',
    'Castello Lukeba': '卢克巴',
    'Sinaly Diomande': '迪奥曼德',
    'Nicolas Tagliafico': '塔利亚菲科',
    'Corentin Tolisso': '托利索',
    'Maxence Caqueret': '卡克雷',
    'Houssem Aouar': '奥亚尔',
    'Lucas Paqueta': '帕奎塔',
    'Bradley Barcola': '巴尔科拉',
    'Alexandre Lacazette': '拉卡泽特',
    'Moussa Dembele': '穆萨·登贝莱',

    # 荷甲球员 - 阿贾克斯
    'Gerónimo Rulli': '鲁利',
    'Daley Blind': '布林德',
    'Jurrien Timber': '廷伯',
    'Edson Alvarez': '阿尔瓦雷斯',
    'Ryan Gravenberch': '赫拉芬贝赫',
    'Donny van de Beek': '范德贝克',
    'Steven Berghuis': '贝赫伊斯',
    'Dusan Tadic': '塔迪奇',
    'Antony': '安东尼',
    'Brian Brobbey': '布罗贝',
    'Mohamed Kudus': '库杜斯',
    'Steven Bergwijn': '贝格温',

    # 葡超球员 - 本菲卡
    'Odysseas Vlachodimos': '弗拉霍迪莫斯',
    'Nicolas Otamendi': '奥塔门迪',
    'Jan Vertonghen': '维尔通亨',
    'Alex Grimaldo': '格里马尔多',
    'Rafa Silva': '拉法·席尔瓦',
    'Joao Mario': '若昂·马里奥',
    'Enzo Fernandez': '恩佐·费尔南德斯',
    'Goncalo Ramos': '贡萨洛·拉莫斯',
    'Petar Musa': '穆萨',

    # 葡超球员 - 波尔图
    'Diogo Costa': '迪奥戈·科斯塔',
    'Pepe': '佩佩',
    'Vitinha': '维蒂尼亚',
    'Otavio': '奥塔维奥',
    'Mateus Uribe': '乌里韦',
    'Mehdi Taremi': '塔雷米',
    'Evanilson': '埃万尼尔松',
    'Luis Diaz': '迪亚斯',

    # 欧冠其他球队
    'Manuel Akanji': '阿坎吉',
    'Erling Haaland': '哈兰德',
    'Kevin De Bruyne': '德布劳内',
    'Phil Foden': '福登',
    'Bernardo Silva': '贝尔纳多·席尔瓦',
    'Ruben Dias': '鲁本·迪亚斯',
    'Rodri': '罗德里',
    'Jack Grealish': '格拉利什',
    'Vinicius Junior': '维尼修斯',
    'Jude Bellingham': '贝林厄姆',
    'Luka Modric': '莫德里奇',
    'Toni Kroos': '克罗斯',
    'David Alaba': '阿拉巴',
    'Thibaut Courtois': '库尔图瓦',
    'Pedri': '佩德里',
    'Gavi': '加维',
    'Marc-Andre ter Stegen': '特尔施特根',
}


def translate_players():
    """翻译球员名"""
    print("=" * 60)
    print("Translating Player Names (Extended V2)")
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
