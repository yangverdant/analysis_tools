#!/usr/bin/env python3
"""
批量更新球队中文名
"""

import sqlite3

DB_PATH = 'd:/football_tools/data/football_v2.db'

# 更多球队中文名
TEAM_CN_EXTENDED = {
    # 英冠/英甲/英乙球队
    'Portsmouth': '朴茨茅斯', 'Millwall': '米尔沃尔', 'Middlesbrough': '米德尔斯堡',
    'West Brom': '西布朗', 'Watford': '沃特福德', 'Swansea': '斯旺西', 'Stoke': '斯托克城',
    'Reading': '雷丁', 'QPR': '女王公园巡游者', 'Norwich': '诺维奇', 'Charlton': '查尔顿',
    'Bristol City': '布里斯托尔城', 'Blackpool': '布莱克浦', 'Blackburn': '布莱克本',
    'Wigan': '维冈', 'Sunderland': '桑德兰', 'Preston': '普雷斯顿', 'Plymouth': '普利茅斯',
    'Oxford Utd': '牛津联', 'Luton': '卢顿', 'Huddersfield': '哈德斯菲尔德',
    'Hull': '赫尔城', 'Derby': '德比郡', 'Coventry': '考文垂', 'Cardiff': '卡迪夫城',
    'Birmingham': '伯明翰', 'Sheffield Weds': '谢菲尔德星期三', 'Rotherham': '罗瑟勒姆',
    'Ipswich': '伊普斯维奇', 'Leicester': '莱斯特城', 'Leeds': '利兹联',
    'Southampton': '南安普顿', 'Burnley': '伯恩利', 'Sheffield United': '谢菲尔德联',
    'Bournemouth': '伯恩茅斯', 'Fulham': '富勒姆', 'Brentford': '布伦特福德',
    'Brighton': '布莱顿', 'Crystal Palace': '水晶宫', 'Wolves': '狼队',
    'Everton': '埃弗顿', 'Nottingham Forest': '诺丁汉森林', 'Aston Villa': '阿斯顿维拉',
    'Newcastle': '纽卡斯尔', 'Tottenham': '热刺', 'West Ham': '西汉姆联',
    'Chelsea': '切尔西', 'Liverpool': '利物浦', 'Arsenal': '阿森纳',
    'Manchester City': '曼城', 'Manchester United': '曼联', 'Real Madrid': '皇马',
    'Barcelona': '巴萨', 'Atletico Madrid': '马竞', 'Bayern Munich': '拜仁',
    'Borussia Dortmund': '多特蒙德', 'Leverkusen': '勒沃库森', 'RB Leipzig': '莱比锡',
    'Inter': '国际米兰', 'Milan': 'AC米兰', 'Juventus': '尤文图斯', 'Napoli': '那不勒斯',
    'Roma': '罗马', 'Lazio': '拉齐奥', 'Atalanta': '亚特兰大', 'Fiorentina': '佛罗伦萨',
    'Paris SG': '巴黎圣日耳曼', 'Marseille': '马赛', 'Lyon': '里昂', 'Monaco': '摩纳哥',
    'Lille': '里尔', 'Nice': '尼斯', 'Lens': '朗斯', 'Rennes': '雷恩',

    # 德甲球队
    'Freiburg': '弗赖堡', 'Eintracht Frankfurt': '法兰克福', 'Wolfsburg': '沃尔夫斯堡',
    'Mainz': '美因茨', 'Borussia M\'gladbach': '门兴', 'Union Berlin': '柏林联合',
    'Werder Bremen': '不来梅', 'Stuttgart': '斯图加特', 'Hoffenheim': '霍芬海姆',
    'Augsburg': '奥格斯堡', 'Bochum': '波鸿', 'Heidenheim': '海登海姆',
    'Holstein Kiel': '基尔', 'St. Pauli': '圣保利',

    # 西甲球队
    'Athletic Bilbao': '毕尔巴鄂竞技', 'Real Sociedad': '皇家社会', 'Villarreal': '比利亚雷亚尔',
    'Real Betis': '贝蒂斯', 'Sevilla': '塞维利亚', 'Valencia': '瓦伦西亚', 'Getafe': '赫塔费',
    'Osasuna': '奥萨苏纳', 'Celta Vigo': '塞尔塔', 'Girona': '赫罗纳', 'Alaves': '阿拉维斯',
    'Rayo Vallecano': '巴列卡诺', 'Mallorca': '马洛卡', 'Las Palmas': '拉斯帕尔马斯',
    'Leganes': '莱加内斯', 'Espanyol': '西班牙人', 'Valladolid': '巴利亚多利德',

    # 意甲球队
    'Bologna': '博洛尼亚', 'Torino': '都灵', 'Monza': '蒙扎', 'Udinese': '乌迪内斯',
    'Sassuolo': '萨索洛', 'Empoli': '恩波利', 'Lecce': '莱切', 'Cagliari': '卡利亚里',
    'Genoa': '热那亚', 'Verona': '维罗纳', 'Parma': '帕尔马', 'Como': '科莫', 'Venezia': '威尼斯',

    # 法甲球队
    'Toulouse': '图卢兹', 'Nantes': '南特', 'Montpellier': '蒙彼利埃', 'Brest': '布雷斯特',
    'Reims': '兰斯', 'Le Havre': '勒阿弗尔', 'Auxerre': '欧塞尔', 'Saint-Etienne': '圣埃蒂安',
    'Angers': '昂热', 'Strasbourg': '斯特拉斯堡',

    # 荷甲球队
    'Ajax': '阿贾克斯', 'PSV Eindhoven': '埃因霍温', 'Feyenoord': '费耶诺德',
    'AZ Alkmaar': '阿尔克马尔', 'Twente': '特温特', 'Utrecht': '乌得勒支',
    'Vitesse': '维特斯', 'Groningen': '格罗宁根', 'Heerenveen': '海伦芬',
    'NEC Nijmegen': '奈梅亨', 'Sparta Rotterdam': '鹿特丹斯巴达', 'RKC Waalwijk': '瓦尔韦克',

    # 葡超球队
    'Benfica': '本菲卡', 'Porto': '波尔图', 'Sporting Lisbon': '里斯本竞技',
    'Braga': '布拉加', 'Guimaraes': '吉马良斯', 'Famalicao': '法马利康',
    'Rio Ave': '里奥阿维', 'Boavista': '博阿维斯塔', 'Gil Vicente': '吉尔维森特',

    # 比甲球队
    'Genk': '亨克', 'Anderlecht': '安德莱赫特', 'Club Brugge': '布鲁日',
    'Antwerp': '安特卫普', 'Gent': '根特', 'Standard Liege': '标准列日',
    'Mechelen': '梅赫伦', 'Charleroi': '沙勒罗瓦', 'Kortrijk': '科特赖克',

    # 苏超球队
    'Celtic': '凯尔特人', 'Rangers': '流浪者', 'Aberdeen': '阿伯丁',
    'Hearts': '哈茨', 'Hibernian': '希伯尼安', 'Dundee Utd': '邓迪联', 'Ross County': '罗斯郡',

    # 奥超球队
    'Salzburg': '萨尔茨堡红牛', 'Rapid Vienna': '维也纳快速', 'Austria Vienna': '奥地利维也纳',
    'Sturm Graz': '格拉茨风暴', 'LASK': '林茨',

    # 丹超球队
    'Copenhagen': '哥本哈根', 'Midtjylland': '中日德兰', 'Brondby': '布隆德比',
    'AGF Aarhus': '奥胡斯',

    # 其他欧洲球队
    'Galatasaray': '加拉塔萨雷', 'Fenerbahce': '费内巴切', 'Besiktas': '贝西克塔斯',
    'Olympiacos': '奥林匹亚科斯', 'Panathinaikos': '帕纳辛奈科斯', 'PAOK': '帕奥克',
    'Basel': '巴塞尔', 'Young Boys': '年轻人', 'Zurich': '苏黎世',
    'Legia Warsaw': '华沙莱吉亚', 'Slavia Prague': '布拉格斯拉维亚', 'Sparta Prague': '布拉格斯巴达',

    # 澳超球队
    'Melbourne City': '墨尔本城', 'Melbourne Victory': '墨尔本胜利', 'Sydney FC': '悉尼FC',
    'Adelaide United': '阿德莱德联', 'Central Coast Mariners': '中央海岸水手',
    'Perth Glory': '珀斯光荣', 'Wellington Phoenix': '惠灵顿凤凰', 'Brisbane Roar': '布里斯班狮吼',
    'Western Sydney Wanderers': '西悉尼流浪者', 'Western United': '西部联',
    'Newcastle Jets': '纽卡斯尔喷气机', 'Macarthur FC': '麦克阿瑟FC', 'Auckland FC': '奥克兰FC',

    # 美职联球队
    'LA Galaxy': '洛杉矶银河', 'LAFC': '洛杉矶FC', 'Seattle Sounders': '西雅图海湾人',
    'Portland Timbers': '波特兰伐木者', 'Atlanta United': '亚特兰大联', 'Inter Miami': '迈阿密国际',
    'New York City FC': '纽约城', 'New York Red Bulls': '纽约红牛', 'Toronto FC': '多伦多FC',
    'Columbus Crew': '哥伦布机员', 'FC Dallas': '达拉斯FC', 'Sporting Kansas City': '堪萨斯城竞技',
    'Minnesota United': '明尼苏达联', 'Nashville SC': '纳什维尔', 'Austin FC': '奥斯汀FC',
    'Charlotte FC': '夏洛特FC', 'St. Louis City': '圣路易斯城', 'Vancouver Whitecaps': '温哥华白帽',
    'Real Salt Lake': '皇家盐湖城', 'Houston Dynamo': '休斯敦迪纳摩', 'CF Montreal': '蒙特利尔',
    'New England': '新英格兰革命', 'DC United': '华盛顿联', 'Chicago Fire': '芝加哥火焰',
    'FC Cincinnati': '辛辛那提FC', 'Orlando City': '奥兰多城', 'Philadelphia Union': '费城联合',
    'Colorado Rapids': '科罗拉多急流', 'San Jose Earthquakes': '圣何塞地震',

    # 瑞典超球队
    'Malmo FF': '马尔默', 'Hammarby': '哈马比', 'Djurgarden': '尤尔加登',
    'AIK Stockholm': 'AIK索尔纳', 'IFK Goteborg': '哥德堡', 'Elfsborg': '埃尔夫斯堡',
    'Hacken': '赫根', 'Sirius': '天狼星', 'Norrkoping': '北雪平', 'Kalmar': '卡尔马',

    # 挪超球队
    'Molde': '莫尔德', 'Rosenborg': '罗森博格', 'Brann': '布兰', 'Viking': '维京',
    'Lillestrom': '利勒斯特罗姆', 'Bodo/Glimt': '博德闪耀', 'Strmsgodset': '斯托姆加斯特',
    'Sarpsborg': '萨尔普斯堡', 'Odd': '奥德', 'Tromso': '特罗姆瑟',

    # 芬超球队
    'HJK Helsinki': '赫尔辛基', 'KuPS': '库奥皮奥', 'Ilves': '伊尔韦斯',
    'Honka': '洪卡', 'Lahti': '拉赫蒂', 'Inter Turku': '图尔库国际',

    # 波兰超球队
    'Lech Poznan': '波兹南莱赫', 'Wisla Krakow': '克拉科夫维斯瓦',
    'Jagiellonia': '雅盖隆', 'Pogon Szczecin': '什切青波贡',

    # 瑞士超球队
    'Lugano': '卢加诺', 'Luzern': '卢塞恩', 'Servette': '塞尔维特',
    'St. Gallen': '圣加伦', 'Winterthur': '温特图尔', 'Yverdon': '伊韦尔东',

    # 土超球队
    'Trabzonspor': '特拉布宗体育', 'Basaksehir': '伊斯坦布尔', 'Konyaspor': '科尼亚体育',
    'Antalyaspor': '安塔利亚体育', 'Sivasspor': '锡瓦斯体育', 'Alanyaspor': '阿兰亚体育',
    'Caykur Rizespor': '里泽体育', 'Kasimpasa': '卡斯帕萨', 'Fatih Karagumruk': '卡拉古姆鲁克',
    'Hatayspor': '哈塔伊体育', 'Gaziantep': '加济安泰普', 'Pendikspor': '彭迪克体育',

    # 希腊超球队
    'AEK Athens': '雅典AEK', 'PAOK Salonika': '塞萨洛尼基PAOK', 'Aris': '阿里斯',
    'Volos': '沃洛斯', 'OFI Crete': 'OFI克里特', 'Atromitos': '阿特罗米托斯',

    # 俄超球队
    'Zenit St Petersburg': '圣彼得堡泽尼特', 'CSKA Moscow': '莫斯科中央陆军',
    'Spartak Moscow': '莫斯科斯巴达', 'Lokomotiv Moscow': '莫斯科火车头',
    'Krasnodar': '克拉斯诺达尔', 'Dinamo Moscow': '莫斯科迪纳摩', 'Sochi': '索契',
    'Rostov': '罗斯托夫', 'Rubin Kazan': '喀山红宝石',

    # 罗甲球队
    'FCSB': '布加勒斯特星', 'CFR Cluj': '克卢日', 'Universitatea Craiova': '克拉约瓦大学',
    'Dinamo Bucuresti': '布加勒斯特迪纳摩', 'UTA Arad': '阿拉德UTA',

    # 奥乙球队
    'Lustenau': '卢斯特瑙', 'Ried': '里德', 'Blau Weiss Linz': '蓝白林茨',
    'Stripfing': '施特里普芬', 'Admira': '阿德米拉', 'Amstetten': '阿姆施泰滕',
    'St. Polten': '圣珀尔滕', 'Kapfenberg': '卡芬堡', 'Stripfing': '施特里普芬',
    'Schwarz Weiss Bregenz': '布雷根茨黑白', ' Lafnitz': '拉夫尼茨', 'Voitsberg': '福伊茨贝格',

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
    'Bosnia': '波黑', 'Montenegro': '黑山', 'Cyprus': '塞浦路斯', 'Luxembourg': '卢森堡',
    'Kazakhstan': '哈萨克斯坦', 'Azerbaijan': '阿塞拜疆', 'Israel': '以色列',
    'South Africa': '南非', 'Mali': '马里', 'Ivory Coast': '科特迪瓦', 'Congo DR': '刚果民主共和国',
    'Guinea': '几内亚', 'Burkina Faso': '布基纳法索', 'Zambia': '赞比亚', 'Gabon': '加蓬',
    'Congo': '刚果', 'Cape Verde': '佛得角', 'Mauritania': '毛里塔尼亚', 'Sudan': '苏丹',
    'Togo': '多哥', 'Benin': '贝宁', 'Malawi': '马拉维', 'Zimbabwe': '津巴布韦',
    'Kenya': '肯尼亚', 'Uganda': '乌干达', 'Tanzania': '坦桑尼亚', 'Mozambique': '莫桑比克',
    'Angola': '安哥拉', 'Libya': '利比亚', 'Niger': '尼日尔', 'Central African Rep.': '中非共和国',
    'Madagascar': '马达加斯加', 'Comoros': '科摩罗', 'Namibia': '纳米比亚', 'Botswana': '博茨瓦纳',
    'Lesotho': '莱索托', 'Eswatini': '斯威士兰', 'Maldives': '马尔代夫', 'Guam': '关岛',
    'Singapore': '新加坡', 'Thailand': '泰国', 'Vietnam': '越南', 'Malaysia': '马来西亚',
    'Indonesia': '印度尼西亚', 'Philippines': '菲律宾', 'Myanmar': '缅甸', 'Laos': '老挝',
    'Cambodia': '柬埔寨', 'Brunei': '文莱', 'Timor-Leste': '东帝汶',
    'Uzbekistan': '乌兹别克斯坦', 'Tajikistan': '塔吉克斯坦', 'Kyrgyzstan': '吉尔吉斯斯坦',
    'Turkmenistan': '土库曼斯坦', 'Afghanistan': '阿富汗', 'Pakistan': '巴基斯坦',
    'Bangladesh': '孟加拉国', 'India': '印度', 'Nepal': '尼泊尔', 'Bhutan': '不丹',
    'Sri Lanka': '斯里兰卡', 'Maldives': '马尔代夫',
    'Jordan': '约旦', 'Iraq': '伊拉克', 'Syria': '叙利亚', 'Lebanon': '黎巴嫩',
    'Palestine': '巴勒斯坦', 'Kuwait': '科威特', 'Bahrain': '巴林', 'Oman': '阿曼',
    'Yemen': '也门', 'United Arab Emirates': '阿联酋',
    'New Zealand': '新西兰', 'Fiji': '斐济', 'Papua New Guinea': '巴布亚新几内亚',
    'Solomon Islands': '所罗门群岛', 'Vanuatu': '瓦努阿图', 'New Caledonia': '新喀里多尼亚',
    'Tahiti': '塔希提', 'Samoa': '萨摩亚', 'Tonga': '汤加',
    'Honduras': '洪都拉斯', 'El Salvador': '萨尔瓦多', 'Guatemala': '危地马拉',
    'Belize': '伯利兹', 'Nicaragua': '尼加拉agua', 'Jamaica': '牙买加',
    'Trinidad and Tobago': '特立尼达和多巴哥', 'Haiti': '海地', 'Cuba': '古巴',
    'Dominican Republic': '多米尼加共和国', 'Puerto Rico': '波多黎各',
    'Guadeloupe': '瓜德罗普', 'Martinique': '马提尼克', 'French Guiana': '法属圭亚那',
    'Suriname': '苏里南', 'Guyana': '圭亚那', 'Bermuda': '百慕大',
    'Bahamas': '巴哈马', 'Barbados': '巴巴多斯', 'St. Kitts and Nevis': '圣基茨和尼维斯',
    'St. Lucia': '圣卢西亚', 'Grenada': '格林纳达', 'St. Vincent Grenadines': '圣文森特和格林纳丁斯',
    'Dominica': '多米尼克', 'Antigua and Barbuda': '安提瓜和巴布达',
    'Curacao': '库拉索', 'Aruba': '阿鲁巴', 'Bonaire': '博内尔',
}


def update_teams():
    print("更新球队中文名...")
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    updated = 0
    for team_name, name_cn in TEAM_CN_EXTENDED.items():
        cursor.execute('''
            UPDATE teams SET name_cn = ? WHERE name_en = ?
        ''', (name_cn, team_name))
        if cursor.rowcount > 0:
            updated += 1

    conn.commit()

    cursor.execute("SELECT COUNT(*) FROM teams WHERE name_cn IS NOT NULL AND name_cn != ''")
    total = cursor.fetchone()[0]

    print(f"  更新 {updated} 支球队")
    print(f"  当前有中文名的球队: {total}")

    conn.close()


if __name__ == '__main__':
    update_teams()
