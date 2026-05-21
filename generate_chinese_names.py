#!/usr/bin/env python3
"""
为数据库中所有球队生成中文名称
"""
import sqlite3
import json
import re
import os

DATABASE_PATH = 'd:/football_tools/data/football_unified.db'
OUTPUT_PATH = 'd:/football_tools/data/linkage'

# 核心球队中文名称映射（基础版）
BASE_TEAM_NAMES = {
    # 英超
    'Manchester City': '曼城', 'Manchester United': '曼联',
    'Arsenal': '阿森纳', 'Liverpool': '利物浦',
    'Chelsea': '切尔西', 'Tottenham': '热刺',
    'Newcastle': '纽卡斯尔', 'Newcastle United': '纽卡斯尔',
    'Brighton': '布莱顿', 'Aston Villa': '阿斯顿维拉',
    'West Ham': '西汉姆', 'West Ham United': '西汉姆',
    'Crystal Palace': '水晶宫', 'Wolves': '狼队',
    'Wolverhampton': '狼队', 'Wolverhampton Wanderers': '狼队',
    'Leicester': '莱斯特城', 'Leicester City': '莱斯特城',
    'Everton': '埃弗顿', 'Leeds': '利兹联', 'Leeds United': '利兹联',
    'Southampton': '南安普顿', 'Burnley': '伯恩利',
    'Norwich': '诺维奇', 'Norwich City': '诺维奇',
    'Watford': '沃特福德', 'Bournemouth': '伯恩茅斯',
    'Fulham': '富勒姆', 'Brentford': '布伦特福德',
    'Nottingham Forest': '诺丁汉森林', 'Luton': '卢顿',
    'Luton Town': '卢顿', 'Sheffield United': '谢菲尔德联',
    'Ipswich': '伊普斯维奇', 'Ipswich Town': '伊普斯维奇',
    'Wolves': '狼队', 'Bournemouth': '伯恩茅斯',

    # 德甲
    'Bayern Munich': '拜仁慕尼黑', 'Bayern': '拜仁慕尼黑',
    'Dortmund': '多特蒙德', 'Borussia Dortmund': '多特蒙德',
    'Leverkusen': '勒沃库森', 'Bayer Leverkusen': '勒沃库森',
    'RB Leipzig': '莱比锡红牛', 'Leipzig': '莱比锡红牛',
    'Wolfsburg': '沃尔夫斯堡', 'VfL Wolfsburg': '沃尔夫斯堡',
    'Monchengladbach': '门兴', 'Borussia Monchengladbach': '门兴',
    "M'gladbach": '门兴', "Mgladbach": '门兴',
    'Frankfurt': '法兰克福', 'Eintracht Frankfurt': '法兰克福',
    'Freiburg': '弗赖堡', 'SC Freiburg': '弗赖堡',
    'Hoffenheim': '霍芬海姆', 'TSG Hoffenheim': '霍芬海姆',
    'Mainz': '美因茨', 'Mainz 05': '美因茨',
    'Union Berlin': '柏林联合', 'Stuttgart': '斯图加特',
    'VfB Stuttgart': '斯图加特', 'Werder Bremen': '云达不莱梅',
    'Bremen': '不莱梅', 'Hertha': '柏林赫塔',
    'Hertha Berlin': '柏林赫塔', 'Schalke': '沙尔克04',
    'Schalke 04': '沙尔克04', 'Koln': '科隆', 'FC Koln': '科隆',
    'Cologne': '科隆', 'Augsburg': '奥格斯堡',
    'Bochum': '波鸿', 'VfL Bochum': '波鸿',
    'Darmstadt': '达姆施塔特', 'Heidenheim': '海登海姆',

    # 西甲
    'Real Madrid': '皇家马德里', 'Barcelona': '巴塞罗那',
    'Atletico Madrid': '马德里竞技', 'Atletico': '马德里竞技',
    'Sevilla': '塞维利亚', 'Real Sociedad': '皇家社会',
    'Real Betis': '皇家贝蒂斯', 'Betis': '贝蒂斯',
    'Villarreal': '比利亚雷亚尔', 'Athletic': '毕尔巴鄂竞技',
    'Athletic Bilbao': '毕尔巴鄂竞技', 'Valencia': '瓦伦西亚',
    'Getafe': '赫塔费', 'Celta': '塞尔塔', 'Celta Vigo': '塞尔塔',
    'Osasuna': '奥萨苏纳', 'Mallorca': '马洛卡',
    'Rayo Vallecano': '巴列卡诺', 'Cadiz': '加的斯',
    'Alaves': '阿拉维斯', 'Girona': '赫罗纳',
    'Las Palmas': '拉斯帕尔马斯', 'Almeria': '阿尔梅里亚',
    'Granada': '格拉纳达', 'Espanyol': '西班牙人',

    # 意甲
    'Juventus': '尤文图斯', 'Inter': '国际米兰',
    'Inter Milan': '国际米兰', 'AC Milan': 'AC米兰',
    'Milan': 'AC米兰', 'Napoli': '那不勒斯',
    'Roma': '罗马', 'AS Roma': '罗马',
    'Lazio': '拉齐奥', 'Atalanta': '亚特兰大',
    'Fiorentina': '佛罗伦萨', 'Bologna': '博洛尼亚',
    'Torino': '都灵', 'Sassuolo': '萨索洛',
    'Udinese': '乌迪内斯', 'Genoa': '热那亚',
    'Verona': '维罗纳', 'Hellas Verona': '维罗纳',
    'Cagliari': '卡利亚里', 'Lecce': '莱切',
    'Empoli': '恩波利', 'Monza': '蒙扎',
    'Frosinone': '弗罗西诺内', 'Salernitana': '萨勒尼塔纳',
    'Parma': '帕尔马', 'Brescia': '布雷西亚',
    'Sampdoria': '桑普多利亚',

    # 法甲
    'Paris SG': '巴黎圣日耳曼', 'Paris Saint-Germain': '巴黎圣日耳曼',
    'PSG': '巴黎圣日耳曼', 'Marseille': '马赛',
    'Lyon': '里昂', 'Monaco': '摩纳哥',
    'Lille': '里尔', 'Nice': '尼斯',
    'Rennes': '雷恩', 'Lens': '朗斯',
    'Montpellier': '蒙彼利埃', 'Nantes': '南特',
    'Strasbourg': '斯特拉斯堡', 'Toulouse': '图卢兹',
    'Bordeaux': '波尔多', 'Reims': '兰斯',
    'Metz': '梅斯', 'Le Havre': '勒阿弗尔',
    'Lorient': '洛里昂', 'Clermont': '克莱蒙',
    'Brest': '布雷斯特', 'Angers': '昂热',
    'Saint-Etienne': '圣埃蒂安',

    # 荷甲
    'Ajax': '阿贾克斯', 'Ajax Amsterdam': '阿贾克斯',
    'PSV': '埃因霍温', 'PSV Eindhoven': '埃因霍温',
    'Feyenoord': '费耶诺德', 'AZ Alkmaar': '阿尔克马尔',
    'AZ': '阿尔克马尔', 'Vitesse': '维特斯',
    'FC Twente': '特温特', 'Twente': '特温特',
    'FC Utrecht': '乌得勒支', 'Utrecht': '乌得勒支',
    'FC Groningen': '格罗宁根', 'Groningen': '格罗宁根',
    'Heerenveen': '海伦芬',

    # 葡超
    'Benfica': '本菲卡', 'Porto': '波尔图',
    'FC Porto': '波尔图', 'Sporting': '葡萄牙体育',
    'Sporting Lisbon': '葡萄牙体育', 'Sporting CP': '葡萄牙体育',
    'Braga': '布拉加',

    # 土超
    'Galatasaray': '加拉塔萨雷', 'Fenerbahce': '费内巴切',
    'Besiktas': '贝西克塔斯', 'Trabzonspor': '特拉布宗体育',

    # 苏超
    'Celtic': '凯尔特人', 'Rangers': '流浪者',
    'Aberdeen': '阿伯丁', 'Hearts': '哈茨',
    'Hibernian': '希伯尼安', 'Dundee United': '邓迪联',
    'Dundee Utd': '邓迪联',

    # 比甲
    'Club Brugge': '布鲁日', 'Anderlecht': '安德莱赫特',
    'Genk': '亨克', 'Gent': '根特',
    'Standard': '标准列日', 'Standard Liege': '标准列日',

    # 奥地利
    'Salzburg': '萨尔茨堡红牛', 'Red Bull Salzburg': '萨尔茨堡红牛',
    'RB Salzburg': '萨尔茨堡红牛', 'Rapid Vienna': '维也纳快速',
    'Austria Vienna': '维也纳奥地利',

    # 瑞士
    'Young Boys': '年轻人', 'Basel': '巴塞尔',
    'Zurich': '苏黎世', 'FC Zurich': '苏黎世',

    # 俄超
    'Zenit': '圣彼得堡泽尼特', 'Zenit St Petersburg': '圣彼得堡泽尼特',
    'CSKA Moscow': '莫斯科中央陆军', 'Spartak Moscow': '莫斯科斯巴达',
    'Lokomotiv Moscow': '莫斯科火车头',

    # 乌超
    'Shakhtar': '顿涅茨克矿工', 'Shakhtar Donetsk': '顿涅茨克矿工',
    'Dynamo Kyiv': '基辅迪纳摩', 'Dynamo Kiev': '基辅迪纳摩',

    # 巴甲
    'Flamengo': '弗拉门戈', 'Palmeiras': '帕尔梅拉斯',
    'Santos': '桑托斯', 'Sao Paulo': '圣保罗',
    'Corinthians': '科林蒂安', 'Gremio': '格雷米奥',
    'Internacional': '国际体育会', 'Atletico Mineiro': '米内罗竞技',
    'Fluminense': '弗鲁米嫩塞', 'Vasco': '瓦斯科达伽马',
    'Vasco da Gama': '瓦斯科达伽马', 'Botafogo': '博塔弗戈',
    'Cruzeiro': '克鲁塞罗',

    # 阿甲
    'Boca Juniors': '博卡青年', 'River Plate': '河床',
    'River': '河床', 'Racing Club': '竞技俱乐部',
    'Independiente': '独立队', 'San Lorenzo': '圣洛伦索',

    # 墨超
    'Club America': '美洲俱乐部', 'America': '美洲俱乐部',
    'Chivas': '瓜达拉哈拉', 'Guadalajara': '瓜达拉哈拉',
    'Cruz Azul': '蓝十字', 'Monterrey': '蒙特雷',
    'Tigres': '老虎大学', 'Tigres UANL': '老虎大学',

    # 美职联
    'LA Galaxy': '洛杉矶银河', 'Seattle Sounders': '西雅图海湾人',
    'Atlanta United': '亚特兰大联', 'NYCFC': '纽约城',
    'New York City': '纽约城', 'New York City FC': '纽约城',
    'Toronto FC': '多伦多FC', 'LAFC': '洛杉矶FC',
    'Los Angeles FC': '洛杉矶FC', 'Inter Miami': '迈阿密国际',
    'Columbus Crew': '哥伦布机员', 'Philadelphia Union': '费城联合',
    'New England': '新英格兰革命', 'New England Revolution': '新英格兰革命',
    'Sporting KC': '堪萨斯城竞技', 'Sporting Kansas City': '堪萨斯城竞技',
    'Portland Timbers': '波特兰伐木者', 'Vancouver Whitecaps': '温哥华白帽',
    'Real Salt Lake': '皇家盐湖城', 'FC Dallas': '达拉斯FC',
    'Houston Dynamo': '休斯顿迪纳摩', 'San Jose Earthquakes': '圣何塞地震',
    'Colorado Rapids': '科罗拉多急流', 'Minnesota United': '明尼苏达联',
    'Minnesota United FC': '明尼苏达联', 'Orlando City': '奥兰多城',
    'DC United': '华盛顿联', 'D.C. United': '华盛顿联',
    'Chicago Fire': '芝加哥火焰', 'CF Montreal': '蒙特利尔',
    'Montreal': '蒙特利尔', 'Charlotte FC': '夏洛特FC',
    'Austin FC': '奥斯汀FC', 'St Louis City': '圣路易斯城',
    'St. Louis City SC': '圣路易斯城',

    # 日职联
    'Urawa Reds': '浦和红钻', 'Urawa Red Diamonds': '浦和红钻',
    'Kashima Antlers': '鹿岛鹿角', 'Yokohama F. Marinos': '横滨水手',
    'Yokohama Marinos': '横滨水手', 'Kawasaki Frontale': '川崎前锋',
    'Gamba Osaka': '大阪钢巴', 'Cerezo Osaka': '大阪樱花',
    'FC Tokyo': 'FC东京',

    # 韩K联
    'Jeonbuk': '全北现代', 'Jeonbuk Hyundai': '全北现代',
    'Suwon': '水原三星', 'Suwon Samsung': '水原三星',
    'FC Seoul': 'FC首尔', 'Seoul': 'FC首尔',
    'Pohang': '浦项制铁', 'Pohang Steelers': '浦项制铁',

    # 沙特
    'Al Hilal': '利雅得新月', 'Al Nassr': '利雅得胜利',
    'Al Ahli': '吉达联合', 'Al Ittihad': '吉达国民',

    # 中超
    'Guangzhou': '广州队', 'Guangzhou Evergrande': '广州恒大',
    'Shanghai SIPG': '上海海港', 'Shanghai Port': '上海海港',
    'Beijing Guoan': '北京国安', 'Shandong': '山东泰山',
    'Shandong Taishan': '山东泰山', 'Shanghai Shenhua': '上海申花',
    'Shenzhen Peng City': '深圳新鹏城',

    # 澳超
    'Sydney FC': '悉尼FC', 'Melbourne City': '墨尔本城',
    'Melbourne Victory': '墨尔本胜利', 'Western Sydney': '西悉尼流浪者',
    'Western Sydney Wanderers': '西悉尼流浪者', 'Adelaide United': '阿德莱德联',
    'Central Coast': '中央海岸水手', 'Central Coast Mariners': '中央海岸水手',
    'Perth Glory': '珀斯光荣', 'Wellington': '惠灵顿凤凰',
    'Wellington Phoenix': '惠灵顿凤凰',

    # 非洲
    'Al Ahly': '开罗国民', 'Zamalek': '扎马雷克',
    'Esperance': '突尼斯希望', 'Esperance Tunis': '突尼斯希望',
    'Wydad': '卡萨布兰卡维达德', 'Wydad Casablanca': '卡萨布兰卡维达德',
    'Mamelodi': '马梅洛迪日落', 'Mamelodi Sundowns': '马梅洛迪日落',
    'Kaizer Chiefs': '凯泽酋长', 'Orlando Pirates': '奥兰多海盗',

    # 其他英格兰球队
    'Birmingham': '伯明翰', 'Birmingham City': '伯明翰',
    'Bristol City': '布里斯托尔城', 'Cardiff': '卡迪夫城',
    'Cardiff City': '卡迪夫城', 'Coventry': '考文垂',
    'Coventry City': '考文垂', 'Huddersfield': '哈德斯菲尔德',
    'Huddersfield Town': '哈德斯菲尔德', 'Hull': '赫尔城',
    'Hull City': '赫尔城', 'Middlesbrough': '米德尔斯堡',
    'Millwall': '米尔沃尔', 'Preston': '普雷斯顿',
    'Preston NE': '普雷斯顿', 'QPR': '女王公园巡游者',
    'Queens Park Rangers': '女王公园巡游者', 'Reading': '雷丁',
    'Rotherham': '罗瑟勒姆', 'Sheffield Wed': '谢菲尔德星期三',
    'Stoke': '斯托克城', 'Stoke City': '斯托克城',
    'Swansea': '斯旺西', 'Swansea City': '斯旺西',
    'Blackburn': '布莱克本', 'Blackburn Rovers': '布莱克本',
    'Blackpool': '布莱克浦', 'Charlton': '查尔顿',
    'Derby': '德比郡', 'Derby County': '德比郡',
    'Oxford': '牛津联', 'Oxford City': '牛津城',
    'Cambridge': '剑桥联', 'Cambridge Utd': '剑桥联',
    'Shrewsbury': '什鲁斯伯里', 'Wycombe': '韦康比流浪者',
    'Burton': '伯顿', 'Fleetwood': '弗利特伍德',
    'Accrington': '阿克灵顿', 'Accrington Stanley': '阿克灵顿',
    'Lincoln': '林肯城', 'Lincoln City': '林肯城',
    'Doncaster': '唐卡斯特', 'Doncaster Rovers': '唐卡斯特',
    'Portsmouth': '朴茨茅斯', 'Sunderland': '桑德兰',
    'Wigan': '维冈竞技', 'Wigan Athletic': '维冈竞技',
    'Plymouth': '普利茅斯', 'Plymouth Argyle': '普利茅斯',
    'Barnsley': '巴恩斯利', 'Peterborough': '彼得伯勒联',
    'Peterborough Utd': '彼得伯勒联', 'Northampton': '北安普顿',
    'Northampton Town': '北安普顿', 'Exeter': '埃克塞特',
    'Exeter City': '埃克塞特', 'Stevenage': '斯蒂夫尼奇',
    'Burton Albion': '伯顿', 'Cheltenham': '切尔滕纳姆',
    'Cheltenham Town': '切尔滕纳姆', 'Shrewsbury Town': '什鲁斯伯里',
    'Morecambe': '莫克姆', 'Forest Green': '森林绿流浪者',
    'Forest Green Rovers': '森林绿流浪者', 'Grimsby': '格里姆斯比',
    'Grimsby Town': '格里姆斯比', 'Newport': '纽波特郡',
    'Newport County': '纽波特郡', 'Salford': '索尔福德城',
    'Salford City': '索尔福德城', 'Barrow': '巴罗',
    'Bradford': '布拉德福德城', 'Bradford City': '布拉德福德城',
    'Colchester': '科尔切斯特联', 'Colchester Utd': '科尔切斯特联',
    'Crawley': '克劳利镇', 'Crawley Town': '克劳利镇',
    'Crewe': '克鲁', 'Crewe Alexandra': '克鲁',
    'Harrogate': '哈罗盖特镇', 'Harrogate Town': '哈罗盖特镇',
    'Leyton Orient': '莱顿东方', 'Mansfield': '曼斯菲尔德镇',
    'Mansfield Town': '曼斯菲尔德镇', 'Oldham': '奥尔德姆竞技',
    'Oldham Athletic': '奥尔德姆竞技', 'Scunthorpe': '斯肯索普联',
    'Scunthorpe Utd': '斯肯索普联', 'Swindon': '斯文登镇',
    'Swindon Town': '斯文登镇', 'Tranmere': '特兰米尔流浪者',
    'Tranmere Rovers': '特兰米尔流浪者', 'Walsall': '沃尔索尔',
    'Carlisle': '卡莱尔联', 'Carlisle Utd': '卡莱尔联',
    'Hartlepool': '哈特尔浦联', 'Hartlepool Utd': '哈特尔浦联',
    'Rochdale': '罗奇代尔', 'Gillingham': '吉林汉姆',
    'AFC Wimbledon': 'AFC温布尔登', 'Sutton': '萨顿联',
    'Sutton Utd': '萨顿联', 'Crawley Town': '克劳利镇',
    'Wimbledon': '温布尔登',
}

# 国家队名称
NATIONAL_TEAM_NAMES = {
    'Argentina': '阿根廷', 'France': '法国', 'Spain': '西班牙',
    'England': '英格兰', 'Brazil': '巴西', 'Netherlands': '荷兰',
    'Portugal': '葡萄牙', 'Germany': '德国', 'Colombia': '哥伦比亚',
    'Belgium': '比利时', 'Italy': '意大利', 'Croatia': '克罗地亚',
    'Uruguay': '乌拉圭', 'Mexico': '墨西哥', 'Switzerland': '瑞士',
    'USA': '美国', 'United States': '美国', 'Denmark': '丹麦',
    'Senegal': '塞内加尔', 'Morocco': '摩洛哥', 'Japan': '日本',
    'South Korea': '韩国', 'Korea Republic': '韩国',
    'Australia': '澳大利亚', 'Iran': '伊朗', 'Saudi Arabia': '沙特阿拉伯',
    'China': '中国', 'Russia': '俄罗斯', 'Ukraine': '乌克兰',
    'Poland': '波兰', 'Sweden': '瑞典', 'Norway': '挪威',
    'Austria': '奥地利', 'Czech Republic': '捷克', 'Turkey': '土耳其',
    'Greece': '希腊', 'Scotland': '苏格兰', 'Wales': '威尔士',
    'Ireland': '爱尔兰', 'Romania': '罗马尼亚', 'Hungary': '匈牙利',
    'Serbia': '塞尔维亚', 'Slovakia': '斯洛伐克', 'Slovenia': '斯洛文尼亚',
    'Finland': '芬兰', 'Iceland': '冰岛', 'North Macedonia': '北马其顿',
    'Montenegro': '黑山', 'Albania': '阿尔巴尼亚', 'Bosnia': '波黑',
    'Bulgaria': '保加利亚', 'Israel': '以色列', 'Cyprus': '塞浦路斯',
    'Luxembourg': '卢森堡', 'Kazakhstan': '哈萨克斯坦',
    'Azerbaijan': '阿塞拜疆', 'Armenia': '亚美尼亚', 'Georgia': '格鲁吉亚',
    'Belarus': '白俄罗斯', 'Moldova': '摩尔多瓦', 'Lithuania': '立陶宛',
    'Latvia': '拉脱维亚', 'Estonia': '爱沙尼亚', 'Malta': '马耳他',
    'Andorra': '安道尔', 'Faroe Islands': '法罗群岛',
    'Gibraltar': '直布罗陀', 'San Marino': '圣马力诺',
    'Liechtenstein': '列支敦士登', 'Kosovo': '科索沃',
    'Chile': '智利', 'Peru': '秘鲁', 'Ecuador': '厄瓜多尔',
    'Paraguay': '巴拉圭', 'Venezuela': '委内瑞拉', 'Bolivia': '玻利维亚',
    'Canada': '加拿大', 'Costa Rica': '哥斯达黎加', 'Panama': '巴拿马',
    'Jamaica': '牙买加', 'Honduras': '洪都拉斯', 'El Salvador': '萨尔瓦多',
    'Trinidad': '特立尼达和多巴哥', 'Trinidad and Tobago': '特立尼达和多巴哥',
    'Guatemala': '危地马拉', 'Haiti': '海地', 'Cuba': '古巴',
    'Nicaragua': '尼加拉瓜', 'Egypt': '埃及', 'Tunisia': '突尼斯',
    'Algeria': '阿尔及利亚', 'Nigeria': '尼日利亚', 'Cameroon': '喀麦隆',
    'Ghana': '加纳', 'Ivory Coast': '科特迪瓦', "Cote d'Ivoire": '科特迪瓦',
    'South Africa': '南非', 'Mali': '马里', 'Congo': '刚果',
    'Guinea': '几内亚', 'Zambia': '赞比亚', 'Angola': '安哥拉',
    'Kenya': '肯尼亚', 'Uganda': '乌干达', 'Tanzania': '坦桑尼亚',
    'Zimbabwe': '津巴布韦', 'Mozambique': '莫桑比克', 'Gabon': '加蓬',
    'Burkina Faso': '布基纳法索', 'Niger': '尼日尔', 'Cape Verde': '佛得角',
    'Mauritania': '毛里塔尼亚', 'Libya': '利比亚', 'Sudan': '苏丹',
    'Togo': '多哥', 'Benin': '贝宁', 'Rwanda': '卢旺达',
    'Ethiopia': '埃塞俄比亚', 'Madagascar': '马达加斯加', 'Comoros': '科摩罗',
    'New Zealand': '新西兰', 'Fiji': '斐济',
    'Papua New Guinea': '巴布亚新几内亚', 'Solomon Islands': '所罗门群岛',
    'Vanuatu': '瓦努阿图', 'North Korea': '朝鲜', 'Korea DPR': '朝鲜',
    'Lebanon': '黎巴嫩', 'Palestine': '巴勒斯坦', 'Yemen': '也门',
    'Tajikistan': '塔吉克斯坦', 'Kyrgyzstan': '吉尔吉斯斯坦',
    'Myanmar': '缅甸', 'Singapore': '新加坡', 'Hong Kong': '香港',
    'Taiwan': '台湾', 'Chinese Taipei': '中华台北',
    'Thailand': '泰国', 'Vietnam': '越南', 'Indonesia': '印度尼西亚',
    'Malaysia': '马来西亚', 'Philippines': '菲律宾', 'India': '印度',
    'Qatar': '卡塔尔', 'UAE': '阿联酋', 'United Arab Emirates': '阿联酋',
    'Oman': '阿曼', 'Bahrain': '巴林', 'Kuwait': '科威特',
    'Jordan': '约旦', 'Syria': '叙利亚', 'Iraq': '伊拉克',
    'Uzbekistan': '乌兹别克斯坦', 'Afghanistan': '阿富汗',
    'Pakistan': '巴基斯坦', 'Bangladesh': '孟加拉国',
    'Nepal': '尼泊尔', 'Sri Lanka': '斯里兰卡', 'Maldives': '马尔代夫',
    'Cambodia': '柬埔寨', 'Laos': '老挝', 'Brunei': '文莱',
    'Timor-Leste': '东帝汶', 'Mongolia': '蒙古',
}


def normalize_name(name):
    """标准化名称，去除后缀"""
    # 去除常见的后缀
    suffixes = [
        ' (ENG)', ' (GER)', ' (ESP)', ' (ITA)', ' (FRA)', ' (NED)',
        ' (POR)', ' (TUR)', ' (SCO)', ' (BEL)', ' (AUT)', ' (SUI)',
        ' (RUS)', ' (UKR)', ' (POL)', ' (GRE)', ' (NOR)', ' (SWE)',
        ' (DEN)', ' (FIN)', ' (CZE)', ' (ROU)', ' (HUN)', ' (SRB)',
        ' FC (ENG)', ' FC', ' AFC', ' SC', ' CF', ' RC', ' AC',
        ' United', ' City', ' Town', ' Athletic', ' Albion',
        ' Rovers', ' Wanderers', ' Rangers', ' County',
    ]

    normalized = name
    for suffix in suffixes:
        if normalized.endswith(suffix):
            normalized = normalized[:-len(suffix)]
            break

    return normalized.strip()


def get_chinese_name(name, team_type='club'):
    """获取中文名称"""
    # 直接匹配
    if name in BASE_TEAM_NAMES:
        return BASE_TEAM_NAMES[name]

    if name in NATIONAL_TEAM_NAMES:
        return NATIONAL_TEAM_NAMES[name]

    # 标准化后匹配
    normalized = normalize_name(name)
    if normalized in BASE_TEAM_NAMES:
        return BASE_TEAM_NAMES[normalized]

    if normalized in NATIONAL_TEAM_NAMES:
        return NATIONAL_TEAM_NAMES[normalized]

    # 模糊匹配 - 检查是否包含关键词
    for eng, cn in {**BASE_TEAM_NAMES, **NATIONAL_TEAM_NAMES}.items():
        # 如果英文名是中文名的子串
        if eng in name or name in eng:
            return cn

    return name  # 返回原名


def generate_all_mappings():
    """为数据库中所有球队生成中文名称"""
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()

    # 获取所有球队
    cursor.execute('SELECT team_id, canonical_name, team_type, country FROM teams')
    teams = cursor.fetchall()

    team_chinese = {}

    for team_id, name, team_type, country in teams:
        cn_name = get_chinese_name(name, team_type)
        if cn_name != name:  # 只有翻译成功才添加
            team_chinese[name] = cn_name

    conn.close()

    # 合并基础映射
    all_team_names = {**BASE_TEAM_NAMES, **NATIONAL_TEAM_NAMES, **team_chinese}

    # 保存
    with open(f'{OUTPUT_PATH}/team_chinese_names.json', 'w', encoding='utf-8') as f:
        json.dump(all_team_names, f, ensure_ascii=False, indent=2)

    print(f"生成 {len(all_team_names)} 个球队中文名称映射")

    return all_team_names


if __name__ == '__main__':
    generate_all_mappings()
