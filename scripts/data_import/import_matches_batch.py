#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""导入比赛数据到CSV文件 - 批量处理"""

import csv
import os
import re

# 球队名称映射（中文到英文）
team_name_mapping = {
    # 意甲
    '拉齐奥': 'Lazio', '国际米兰': 'Inter', '莱切': 'Lecce', '尤文': 'Juventus',
    '克雷莫纳': 'Cremonese', '佛罗伦萨': 'Fiorentina', '热那亚': 'Genoa',
    '维罗纳': 'Verona', '科莫': 'Como', '帕尔马': 'Parma', '罗马': 'Roma',
    '那不勒斯': 'Napoli', '博洛尼亚': 'Bologna', 'AC米兰': 'AC Milan', '亚特兰大': 'Atalanta',

    # 英超
    '曼城': 'Man City', '布伦特': 'Brentford', '伯恩利': 'Burnley', '维拉': 'Aston Villa',
    '水晶宫': 'Crystal Palace', '埃弗顿': 'Everton', '诺丁汉森林': 'Nottingham Forest',
    '纽卡斯尔': 'Newcastle', '西汉姆': 'West Ham', '阿森纳': 'Arsenal', '热刺': 'Tottenham',
    '利兹联': 'Leeds',

    # 德甲
    '沃尔夫斯堡': 'Wolfsburg', '拜仁': 'Bayern Munich', '汉堡': 'Hamburger SV',
    '弗赖堡': 'Freiburg', '科隆': 'FC Koln', '海登海姆': 'Heidenheim', '美因茨': 'Mainz',
    '柏林联合': 'Union Berlin',

    # 西甲
    '马竞': 'Atletico Madrid', '塞尔塔': 'Celta Vigo', '皇家社会': 'Real Sociedad',
    '贝蒂斯': 'Real Betis', '马洛卡': 'Mallorca', '比利亚雷': 'Villarreal',
    '毕尔巴鄂': 'Athletic Bilbao', '巴伦西亚': 'Valencia', '巴萨': 'Barcelona',
    '皇马': 'Real Madrid', '巴列卡诺': 'Rayo Vallecano', '赫罗纳': 'Girona',
    '奥维耶多': 'Oviedo', '赫塔费': 'Getafe',

    # 西乙
    '巴拉多利德': 'Valladolid', '萨拉戈萨': 'Zaragoza', '马拉加': 'Malaga',
    '希洪竞技': 'Sporting Gijon', '莱加内斯': 'Leganes', '桑坦德竞技': 'Racing Santander',
    '安道尔CF': 'FC Andorra', '拉斯马斯': 'Las Palmas', '科尔多瓦': 'Cordoba',
    '格拉纳达': 'Granada', '米兰德斯': 'Mirandes', '埃瓦尔': 'Eibar', '韦斯卡': 'Huesca',
    '皇家社会B队': 'Real Sociedad B',

    # 法甲
    '巴黎圣曼': 'PSG', '布雷斯特': 'Brest', '勒阿弗尔': 'Le Havre', '马赛': 'Marseille',
    '图卢兹': 'Toulouse', '里昂': 'Lyon', '欧塞尔': 'Auxerre', '尼斯': 'Nice',
    '雷恩': 'Rennes', '巴黎FC': 'Paris FC', '梅斯': 'Metz', '洛里昂': 'Lorient',
    '昂热': 'Angers', '斯特拉斯': 'Strasbourg', '摩纳哥': 'Monaco', '里尔': 'Lille',

    # 法乙
    '圣埃蒂安': 'Saint-Etienne', '亚眠': 'Amiens', '兰斯': 'Reims', '波城': 'Pau',
    '圣旺红星': 'Red Star', '蒙彼利埃': 'Montpellier', '巴斯蒂亚': 'Bastia', '勒芒': 'Le Mans',
    '克莱蒙': 'Clermont', '甘冈': 'Guingamp', '格勒诺布尔': 'Grenoble', '特鲁瓦': 'Troyes',
    '南锡': 'Nancy', '敦刻尔克': 'Dunkerque', '阿纳西': 'Annecy', '罗德兹': 'Rodez',
    '拉瓦勒': 'Laval', '布洛涅': 'Boulogne', '沙托鲁': 'Chateauroux', '索肖': 'Sochaux',
    '布尔格': 'Bourg', '瓦朗谢讷': 'Valenciennes', '鲁昂': 'Rouen', '凡尔赛78': 'Versailles',
    '欧巴涅': 'Aubagne', '巴黎13马竞': 'Paris 13 Atletico', '孔卡诺': 'Concarneau',
    '克维伊': 'Quevilly', '圣布里厄': 'Saint-Brieuc', '奥尔良': 'Orleans', '弗勒里': 'Fleury',

    # 荷甲
    '格拉夫夏普': 'De Graafschap', '阿尔梅勒': 'Almere City', 'SBV精英': 'Excelsior',
    '福伦丹': 'Volendam', '福图纳': 'Fortuna Sittard', '兹沃勒': 'PEC Zwolle',
    '格罗宁根': 'Groningen', '奈梅亨': 'NEC', '前进之鹰': 'Go Ahead Eagles',
    '埃因霍温': 'PSV', '阿贾克斯': 'Ajax', '乌德勒支': 'Utrecht', '特温特': 'Twente',
    '鹿特丹': 'Sparta Rotterdam', '布雷达': 'NAC Breda', '特尔斯达': 'Telstar',
    '赫拉克勒斯': 'Heracles', '费耶诺德': 'Feyenoord', '阿尔克马': 'AZ Alkmaar',
    '海伦芬': 'Heerenveen',

    # 葡超
    '布拉加': 'Braga', '阿马多拉': 'Amadora', '里斯本': 'Sporting CP', '吉维森特': 'Gil Vicente',
    '埃斯托里': 'Estoril', '本菲卡': 'Benfica', '艾华卡': 'Arouca', '波尔图': 'Porto',
    '吉马良斯': 'Vitoria Guimaraes', '卡萨皮亚': 'Casa Pia', '通德拉': 'Tondela',
    '摩雷伦斯': 'Moreirense', '里奥阿维': 'Rio Ave', '圣克拉拉': 'Santa Clara',
    '葡萄牙国民': 'Nacional', '法马利康': 'Famalicao', '阿罗卡': 'Arouca',

    # 土超
    '埃伊乌斯堡': 'Eyupspor', '里泽体育': 'Rizespor', '根克勒比利吉': 'Genclerbirligi',
    '卡斯帕萨': 'Kasimpasa', '加拉塔萨雷': 'Galatasaray', '安塔利亚': 'Antalyaspor',
    '贝西克塔斯': 'Besiktas', '特拉布宗': 'Trabzonspor', '伊斯坦布尔': 'Basaksehir',
    '萨姆松': 'Samsunspor', '科贾埃利体育': 'Kocaelispor', '卡拉古姆克': 'Fatih Karagumruk',
    '戈兹特普': 'Goztepe', '加济安泰普': 'Gaziantep', '科尼亚体育': 'Konyaspor',
    '费内巴切': 'Fenerbahce', '阿拉尼亚': 'Alanyaspor', '开塞利体育': 'Kayserispor',

    # 比甲
    '比尔肖特': 'Beerschot', '洛默尔': 'Lommel', '根特': 'Gent', '安德莱赫特': 'Anderlecht',
    '安特卫普': 'Antwerp', '沙勒罗瓦': 'Charleroi', '布鲁日': 'Club Brugge',
    '圣图尔登': 'Sint-Truiden', '圣吉罗斯': 'Union Saint-Gilloise', '梅赫伦': 'Mechelen',
    '亨克': 'Genk', '韦斯特鲁': 'Westerlo',

    # 瑞士超
    '温特图尔': 'Winterthur', '洛桑': 'Lausanne', '苏黎世': 'Zurich', '草蜢': 'Grasshopper',
    '卢塞恩': 'Luzern', '塞尔维特': 'Servette', '卢加诺': 'Lugano', '圣加仑': 'St. Gallen',
    '锡永': 'Sion', '图恩': 'Thun', '年轻人': 'Young Boys', '巴塞尔': 'Basel',

    # 奥甲
    '林茨': 'LASK', '萨尔茨堡': 'Salzburg', '哈特堡格': 'Hartberg', '格拉茨风暴': 'Sturm Graz',
    '维快速': 'Rapid Vienna', '奥地利维也纳': 'Austria Vienna',

    # 俄超
    '加索维卡': 'Gazovik', '苏维埃之翼': 'Krylya Sovetov', '泽尼特': 'Zenit',
    '索契': 'Sochi', '格罗兹尼': 'Akhmat', '马哈奇卡': 'Makhachkala', '莫火车头': 'Lokomotiv',
    '巴提卡': 'Baltika', '陶里亚蒂阿克隆': 'Akron', '罗斯托夫': 'Rostov',
    '诺夫哥罗德': 'Nizhny Novgorod', '莫陆军': 'CSKA Moscow', '莫斯巴达': 'Spartak Moscow',
    '喀山红宝石': 'Rubin Kazan', '莫迪纳摩': 'Dynamo Moscow', '克拉斯': 'Krasnodar',

    # 希腊超
    '阿特罗米托斯': 'Atromitos', '帕纳多里科斯': 'Panetolikos', '阿里斯': 'Aris',
    '克里特': 'OFI', '沃洛斯': 'Volos', '利瓦迪亚科斯': 'Levadiakos', '雅典AEK': 'AEK Athens',
    '帕纳辛纳科斯': 'Panathinaikos', '奥林匹亚科斯': 'Olympiacos', '塞萨洛尼基': 'PAOK',

    # 克罗甲
    '瓦拉兹丁': 'Varazdin', '萨格勒布火车头': 'Lokomotiva', '奥西耶克': 'Osijek',
    '伊斯特拉': 'Istra', '斯拉文': 'Slaven Belupo', 'NK哥里卡': 'Gorica',

    # 塞尔超
    '贝尔格莱德红星': 'Crvena Zvezda', 'BASK贝尔格莱德': 'BASK', '贝尔格莱德游击': 'Partizan',
    'OFK贝尔格莱德': 'OFK Beograd', '新贝尔格莱德': 'Novi Beograd', '舒马迪亚': 'Sumadija',
    '托波拉': 'TSC', '嘉沃伊万基卡': 'Javor', '拉德尼基': 'Radnicki', '卢卡尼': 'Mladost Lucani',
    '兹拉蒂博尔': 'Zlatibor', '纳普雷达克': 'Napredak',

    # 捷甲
    '布拉格斯拉维亚': 'Slavia Prague', '布斯巴达': 'Sparta Prague', '帕尔杜比采': 'Pardubice',
    '卡尔维纳': 'Karvina', '奥洛穆茨': 'Olomouc', '波希米亚1905': 'Bohemians',
    '亚布洛内茨': 'Jablonec', '赫拉德茨': 'Hradec', '博莱斯拉夫': 'Mlada Boleslav',
    '杜克拉布拉格': 'Dukla Prague', '兹林': 'Zlin', '特普利斯': 'Teplice',
    '斯洛瓦克': 'Slovacko', '俄斯特拉发': 'Banik Ostrava',

    # 波兰甲
    '扎布热矿工': 'Gornik Zabrze', '卢宾扎格勒比': 'Zaglebie Lubin', '皮亚斯特': 'Piast',
    '卡托华斯': 'Katowice', '普沃茨克': 'Wisla Plock', '摩托鲁宾': 'Motor Lublin',
    '尼切萨': 'Nieciecza', '华沙军团': 'Legia Warsaw', '克拉科维亚': 'Cracovia',
    '拉多米亚克': 'Radomiak',

    # 丹超
    '北西兰': 'Nordsjaelland', '中日德兰': 'Midtjylland', '瓦埃勒': 'Vejle',
    '腓特烈西亚': 'Fredericia', '布隆德比': 'Brondby', '奥胡斯': 'AGF',
    '锡尔克堡': 'Silkeborg', '哥本哈根': 'Copenhagen', '兰纳斯': 'Randers', '欧登塞': 'Odense',

    # 挪超
    '博德闪耀': 'Bodo/Glimt', '布兰': 'Brann', '罗森博格': 'Rosenborg', '利勒斯特': 'Lillestrom',
    'KFUM奥斯陆': 'KFUM Oslo', '维京': 'Viking', '桑纳菲尤尔': 'Sandefjord',
    '克里斯蒂安松': 'Kristiansund', '特罗姆瑟': 'Tromso', '莫尔德': 'Molde',
    '奥勒松': 'Aalesund', '斯达': 'Start',

    # 瑞典超
    '索尔纳': 'AIK', '佐加顿斯': 'Djurgarden', '卡尔马': 'Kalmar', '哈尔姆斯塔德': 'Halmstads',
    '赫根': 'Hacken', '马尔默': 'Malmo', '天狼星': 'Sirius', '厄尔格里特': 'Orgryte',

    # 芬超
    '拉赫蒂': 'Lahti', '玛丽港': 'Mariehamn', '塞伊奈': 'SJK',

    # J联赛
    '清水鼓动': 'Shimizu S-Pulse', '福冈黄蜂': 'Avispa Fukuoka', '神户胜利': 'Vissel Kobe',
    '冈山绿雉': 'Fagiano Okayama', '横滨水手': 'Yokohama F. Marinos', '鹿岛鹿角': 'Kashima Antlers',
    '大阪钢巴': 'Gamba Osaka', '广岛三箭': 'Sanfrecce Hiroshima', '东京FC': 'FC Tokyo',
    '东京绿茵': 'Tokyo Verdy', '名古屋鲸': 'Nagoya Grampus', '京都不死鸟': 'Kyoto Sanga',
    '柏太阳神': 'Kashiwa Reysol', '川崎前锋': 'Kawasaki Frontale', '千叶市原': 'JEF United Chiba',
    '町田泽维亚': 'Machida Zelvia',

    # J2联赛
    '金泽赛维根': 'Zweigen Kanazawa', '新泻天鹅': 'Albirex Niigata', '八户南源': 'Vanraure Hachinohe',
    '仙台七夕': 'Vegalta Sendai', '山形山神': 'Montedio Yamagata', '相模原': 'SC Sagamihara',
    '枥木SC': 'Tochigi SC', '秋田蓝色闪电': 'Blaublitz Akita', '湘南海洋': 'Shonan Bellmare',
    '横滨FC': 'Yokohama FC', '福岛联': 'FC Fukushima', '磐田喜悦': 'Jubilo Iwata',
    '松本山雅': 'Matsumoto Yamaga', '藤枝MYFC': 'Fujieda MYFC', '赞岐釜玉海': 'Kamatamare Sanuki',
    '高知联合SC': 'Kochi United', '德岛漩涡': 'Tokushima Vortis', '奈良': 'Nara Club',
    '草津紫湖': 'Thespa Gunma', '鹿儿岛联': 'Kagoshima United', '鸟取希望': 'Gainare Tottori',
    '北九州向日葵': 'Giravanz Kitakyushu', '熊本深红': 'Roasso Kumamoto', '琉球FC': 'FC Ryukyu',
    '大分三神': 'Oita Trinita', '鸟栖沙岩': 'Sagan Tosu', '爱媛FC': 'Ehime FC', '富山胜利': 'Kataller Toyama',

    # K联赛
    '蔚山现代': 'Ulsan Hyundai', '富川FC': 'Bucheon FC', '安养FC': 'Anyang',
    '全北现代': 'Jeonbuk Hyundai', '江原FC': 'Gangwon FC', '大田市民': 'Daejeon Citizen',
    '光州FC': 'Gwangju FC', '首尔FC': 'FC Seoul', '仁川联': 'Incheon United',
    '浦项制铁': 'Pohang Steelers',

    # K2联赛
    '城南一和': 'Seongnam', '全南天龙': 'Jeonnam Dragons', '安山小绿人': 'Ansan Greeners',
    '龙仁': 'Yongin', '釜山偶像': 'Busan IPark', '天安城': 'Chungnam Asan',
    '庆南FC': 'Gyeongnam', '金海': 'Gimhae',

    # 中超
    '青岛西海岸': 'Qingdao West Coast', '武汉三镇': 'Wuhan Three Towns',
    '深圳新鹏城': 'Shenzhen Peng City', '山东泰山': 'Shandong Taishan',
    '辽宁铁人': 'Liaoning Tieren', '云南玉昆': 'Yunnan Yukun', '浙江队': 'Zhejiang',
    '天津津门虎': 'Tianjin Jinmen Tiger', '北京国安': 'Beijing Guoan', '上海海港': 'Shanghai Port',
    '青岛海牛': 'Qingdao Hainiu', '大连英博': 'Dalian Yingbo',

    # 沙特联
    '欧奈纳伊': 'Al-Okhdood', '拉斯决心': 'Al-Ettifaq', '迈季宽广': 'Al-Khaleej',
    '胡巴卡德': 'Al-Qadsiah', '利雅得': 'Al-Riyadh', '穆拜征服': 'Al-Fayha',
    '吉达联合': 'Al-Ittihad', '达马克': 'Damac', '新未来城': 'Al-Qadsiah', '利雅青年': 'Al-Shabab',
    '布赖合作': 'Al-Taawon', '吉达国民': 'Al-Ahli',

    # 美职
    '多伦多FC': 'Toronto FC', '迈阿密国际': 'Inter Miami', '芝加哥火焰': 'Chicago Fire',
    '纽约红牛': 'NY Red Bulls', '蒙特利尔': 'CF Montreal', '奥兰多城': 'Orlando City',
    '亚特兰大联': 'Atlanta United', '洛杉矶银河': 'LA Galaxy', '夏洛特FC': 'Charlotte FC',
    '辛辛那提': 'Cincinnati', '新英格兰革命': 'New England', '费城联合': 'Philadelphia',
    '达拉斯FC': 'FC Dallas', '皇家盐湖城': 'Real Salt Lake', '纳什维尔': 'Nashville',
    '华盛顿联': 'DC United', '科罗拉多急流': 'Colorado Rapids', '圣路易斯市': 'St. Louis City',
    '波特兰伐木工': 'Portland Timbers', '堪萨斯城': 'Sporting KC', '圣何塞地震': 'San Jose',
    '温哥华白帽': 'Vancouver', '西雅图海湾人': 'Seattle Sounders', '圣迭戈FC': 'San Diego FC',
    '洛杉矶FC': 'LAFC', '明尼苏达联': 'Minnesota United', '奥斯汀FC': 'Austin FC',
    '休斯顿迪纳摩': 'Houston Dynamo', '纽约城': 'NYCFC', '哥伦布机员': 'Columbus Crew',

    # 墨联
    '瓜达拉哈拉': 'Chivas', '老虎大学': 'Tigres', '蓝十字': 'Cruz Azul', '阿特拉斯': 'Atlas',
    '帕丘卡': 'Pachuca', '托卢卡': 'Toluca', '美洲狮': 'Pumas', '墨西哥美洲': 'Club America',

    # 巴西甲
    '科里蒂巴': 'Coritiba', '巴西国际': 'Internacional', '弗鲁米嫩塞': 'Fluminense',
    '维多利亚': 'Vitoria', '米内罗竞技': 'Atletico Mineiro', '博塔弗戈': 'Botafogo',
    '巴伊亚': 'Bahia', '克鲁塞罗': 'Cruzeiro', '桑托斯': 'Santos', '布拉干蒂诺': 'Bragantino',
    '科林蒂安': 'Corinthians', '圣保罗': 'Sao Paulo', '迈拉索尔': 'Mirassol',
    '沙佩科恩斯': 'Chapecoense', '格雷米奥': 'Gremio', '弗拉门戈': 'Flamengo',
    '瓦斯科达伽马': 'Vasco da Gama', '巴拉纳竞技': 'Athletico Paranaense', '瑞模': 'Remo',
    '帕尔梅拉斯': 'Palmeiras',

    # 巴西乙
    '戈亚斯': 'Goias', '维拉诺瓦': 'Vila Nova', '德雷竞技': 'LDU', '奎尔巴': 'Ceara',
    '庞特普雷塔': 'Ponte Preta', '累西腓体育': 'Sport Recife', '塞阿拉': 'Ceara',
    '戈亚尼亚竞技': 'Goiania', 'CR巴西': 'CSA', '奥佩拉里奥': 'Operario',
    '尤文图德': 'Juventude', '克里西乌马': 'Criciuma', '隆迪那': 'Londrina',
    '圣贝尔纳多': 'Sao Bernardo', '累西腓航海': 'Nautico', '米内罗美洲': 'America Mineiro',
    '阿瓦伊': 'Avaí', '福塔雷萨': 'Fortaleza', '诺瓦里': 'Novorizontino', '博塔弗戈SP': 'Botafogo SP',

    # 阿甲
    '博卡青年': 'Boca Juniors', '飓风': 'Huracan', '门多萨独立': 'Independiente Rivadavia',
    '圣菲联合': 'Union Santa Fe', '阿根廷青年人': 'Argentinos Juniors', '拉努斯': 'Lanus',
    '罗萨里奥': 'Rosario Central', '阿根廷独立': 'Independiente', '拉普大学': 'Estudiantes',
    '竞技俱乐部': 'Racing Club', '河床': 'River Plate', '圣洛伦索': 'San Lorenzo',
    '萨斯菲尔德': 'Velez Sarsfield', '拉普拉塔体操': 'Gimnasia La Plata',
    '铁路工场': 'Talleres', '贝尔格拉诺': 'Belgrano',

    # 阿乙
    '玛伦': 'Mitre', '安第斯': 'Andes', '圣特尔莫': 'San Telmo', '米特雷': 'Mitre',
    'CA坦波利': 'Temperley', '迈普': 'Maipu', '图库曼圣马丁': 'San Martin Tucuman',
    '胡胡伊体操击剑': 'Gimnasia Jujuy', '新芝加哥': 'Nueva Chicago', '阿尔马格罗': 'Almagro',
    '阿卡苏索': 'Acassuso', '布朗海军上将': 'Brown', '查卡瑞塔青年': 'Chacarita Juniors',
    '科勒吉莱斯': 'Colegiales', '阿戈罗佩': 'Agropecuario', '亚特兰大竞技': 'Atletico Atlanta',
    '格梅斯竞技': 'Victoriano Arenas', '基尔梅斯': 'Quilmes', '戈多伊克鲁斯': 'Godoy Cruz',
    '科尔多巴竞技': 'Atletico Cordoba', '查科永久': 'Chaco For Ever', '玻利瓦尔城': 'Bolivar',
    '北萨尔塔中央': 'Central Norte', '马德林': 'Madryn', '科隆竞技': 'Colon',
    '全男孩竞技': 'All Boys', '西部铁路': 'Ferro', '贝尔格拉诺守卫者': 'Defensores de Belgrano',

    # 乌拉甲
    '达努比奥': 'Danubio', '阿尔比恩': 'Albion', '西班牙中心': 'Centro Espanol',
    '蒙特维多竞技': 'Atletico Montevideo', '捍卫者竞技': 'Defensor', '拉斯彼德拉斯': 'Las Piedras',
    '力矩': 'Torque', '普罗雷索': 'Progreso', '马尔多纳多': 'Maldonado', '波士顿河': 'Boston River',
    '塞罗拉尔戈': 'Cerro Largo', '佩纳罗尔': 'Penarol', '乌拉圭民族': 'Nacional', '切洛': 'Cerro',

    # 厄瓜甲
    '理工大学竞技': 'Universidad Catolica', '迪尔芬': 'Delfin', '瓜亚基尔城': 'Guayaquil City',
    '昆卡竞技': 'Cuenca', '奥卡斯': 'Aucas', '基多天主大学': 'Universidad Catolica',
    '德尔瓦耶独立': 'Independiente del Valle', '瓜亚基尔': 'Barcelona SC', '埃梅莱克': 'Emelec',
    '利伯塔德洛哈': 'Libertad', '曼塔FC': 'Manta', '马卡拉': 'Macara', '穆苏克鲁纳': 'Mushuc Runa',
    '基多大学': 'LDU Quito',

    # 玻利甲
    '瓜比拉': 'Guabira', 'GV圣何塞': 'San Jose', '皇家托马亚波': 'Tomasino',
    '圣安东尼奥': 'San Antonio', '石油独立': 'Petrolero', '时刻准备着': 'Always Ready',
    '最强者': 'The Strongest', '皇家波托西': 'Real Potosi', '国民波托西': 'Nacional Potosi',
    '科恰班巴极光': 'Aurora', '布鲁明': 'Blooming', '玻利瓦尔': 'Bolivar',

    # 其他联赛
    '托尔斯港B36': 'B36 Torshavn', '克拉克斯维克': 'Klaksvik', '比尔肖特': 'Beerschot',
    '欧奈纳伊': 'Al-Okhdood', '拉斯决心': 'Al-Ettifaq', '迈季宽广': 'Al-Khaleej',
    '胡巴卡德': 'Al-Qadsiah', '利雅得': 'Al-Riyadh', '穆拜征服': 'Al-Fayha',
    '新未来城': 'Neom', '利雅青年': 'Al-Shabab', '布赖合作': 'Al-Taawon',
    '博德闪耀': 'Bodo/Glimt', '挪超博德闪耀': 'Bodo/Glimt', '挪超布兰': 'Brann',
    '普里耶多尔': 'Borac', '萨拉热窝': 'Sarajevo', '拉德尼克': 'Radnik',
    '辛连斯基': 'Sloga', '埃斯比约': 'Esbjerg', '科尔丁IF': 'Kolding IF',
    '贝内雷讷马卡比': 'Bnei Sakhnin', '谢莫夏普尔': 'Hapoel Shmona',
    '海法马卡比': 'Maccabi Haifa', '耶路贝塔': 'Beitar Jerusalem', '特拉夏普尔': 'Hapoel Tel Aviv',
    '特拉马卡比': 'Maccabi Tel Aviv', '彼达迪华夏普尔': 'Hapoel Petah Tikva',
    '贝谢夏普尔': 'Hapoel Be\'er Sheva', '马格斯': 'Maritzburg', '奥兰多海盗': 'Orlando Pirates',
    '玛伦': 'Mitre', '安第斯': 'Andes', '圣特尔莫': 'San Telmo', '米特雷': 'Mitre',
    '蒂瓦特': 'Buducnost', '苏基斯卡': 'Sutjeska', '克鲁日大学': 'Universitatea Cluj',
    '布加勒斯特快速': 'Rapid Bucuresti', '博托沙尼': 'Botosani', '普洛耶什蒂': 'Ploiesti',
    '布加勒斯特迪纳摩': 'Dinamo Bucuresti', '阿尔杰什': 'Arges', '梅塔洛': 'Metaloglobus',
    '赫曼施塔特': 'Hermannstadt', '尤尼史洛波西亚': 'Unirea Slobozia',
    '布加勒斯特星': 'FCSB', '亚历山德里亚': 'Oleksandriya', '卢甘斯克黎明': 'Zorya',
    '杜纳伊夫齐': 'Dnipro', '波利西亚': 'Polissya', '维利斯罗夫': 'Veres',
    '卡夫巴斯': 'Kryvbas', '梅塔利斯特': 'Metalist', '利沃夫': 'Lviv',
    '塞伊奈': 'SJK', '拉宾兰塔': 'Lahden Reipas', '萨布塔洛': 'Saburtalo',
    '古泰斯拖比度': 'Guria', '巴统迪纳摩': 'Dinamo Batumi', '萨古拉利': 'Saguramo',
    '鲁斯塔维': 'Rustavi', '第比利斯迪纳摩': 'Dinamo Tbilisi', '艾拉华特': 'Ararat',
    '班南特斯': 'Banants', '亚美尼亚亚拉腊': 'Ararat Yerevan', '诺亚': 'Noah',
    '橡树之心': 'Hearts of Oak', '阿杜瓦纳斯明星': 'Medeama', '突尼斯希望': 'Esperance',
    '艾菲里肯': 'African', '施特拉森': 'Strassen', '埃斯克年青人': 'Esch',
    '莫尔纳': 'Mornar', '博凯列': 'Bokelj', '帕内韦日斯': 'Panevezys', '斯帕尼斯': 'Spyris',
    '苏杜瓦': 'Suduva', '扎尔吉里斯': 'Zalgiris', '斯卡拉': 'Skala', '阿吉尔': 'AB',
    '斯特梅尔': 'Stjarnan', '维京人': 'Vikingur', '诺米联合JK': 'Nomme Kalju',
    '弗罗拉': 'Flora', '诺梅卡尔尤': 'Nomme Kalju', 'KA阿克雷里': 'KA Akureyri',
    '韦斯特': 'Vestri', '格洛比纳': 'Globina', '叶尔加瓦': 'Jelgava',
    '地拉拿柏迪辛尼': 'Partizani', '地拉纳迪纳摩': 'Dinamo Tirana',
    '维拉斯尼亚': 'Vllaznia', '法兰姆达利': 'Flamurtari', '潘德夫学院': 'Pandev Academy',
    '列伯尼基': 'Rabotnicki', '马克顿尼亚': 'Makedonija', '卡瓦达尔奇': 'Kavadartsi',
    '萨普里萨': 'Saprissa', '阿吉拉斯': 'Aguilas', '埃雷迪亚': 'Heredia', '卡塔戈尼斯': 'Cartago',
    '东北联队': 'NorthEast United', '城南': 'Chengdu', '喀拉拉邦': 'Kerala Blasters',
    'Mohammedan SC': 'Mohammedan', '东孟加拉': 'East Bengal', '米勒瓦学院': 'Mohammedan',
    '后港联': 'Hougang United', '淡滨尼流浪': 'Tampines Rovers', '狮城水手': 'Lion City Sailors',
    '新泻天鹅乙队': 'Albirex Niigata Singapore', '萨连斯基': 'Sloga', '华拉莫斯塔': 'Velez',
    '萨拉热窝铁路工人': 'Zeljeznicar', '索尔加多波': 'Sloga', '尼菲治': 'Neftchi',
    '国际巴库': 'Inter Baku', '海法夏普尔': 'Hapoel Haifa', '阿什杜德': 'Ashdod',
    '耶路夏普尔': 'Hapoel Jerusalem', '比尼萨赫宁': 'Bnei Sakhnin', '伊罗尼太巴列': 'Hapoel Tiberias',
    '内坦马卡比': 'Maccabi Netanya', '莫斯': 'Moss', '布莱尼': 'Bryne', '赖于福斯': 'Raufoss',
    '利恩': 'Lyn', '桑内斯': 'Sandnes', '斯塔贝克': 'Stabekk', '松达尔': 'Sogndal',
    '海于格松': 'Haugesund', '斯特勒门': 'Strommen', '赫德': 'Hodd', '奥桑内': 'Osane',
    '斯特罗姆': 'Stromsgodset', '安格森德': 'Aalesund 2', '奥德': 'Odd',
    '拉赫蒂': 'Lahti', '塞伊奈': 'SJK', '加菲卡': 'Zemun', '杜博奇察': 'Dubocica',
    '斯梅德拉沃': 'Smederevo', '博拉奇': 'Borac', '格林斯比': 'Grimsby', '索尔福德城': 'Salford',
    '切斯特菲尔德': 'Chesterfield', '诺茨郡': 'Notts County', '米尔沃尔': 'Millwall',
    '赫尔城': 'Hull City', '博尔顿': 'Bolton', '布拉德福德': 'Bradford City',
    '马瑟韦尔': 'Motherwell', '哈茨': 'Hearts', '凯尔特人': 'Celtic', '流浪者': 'Rangers',
    '本菲卡B队': 'Benfica B', '维塞乌': 'Viseu', '维兹拉': 'Vizela', '莱里亚': 'Leiria',
    '卢西塔尼亚': 'Lusitania', '杜连斯': 'Dumiense', '瓦杜兹': 'Vaduz', '阿劳': 'Aarau',
    '尼奈斯': 'Nyon', '洛桑乌契': 'Lausanne', '纳沙泰尔': 'Neuchatel', '艾托雷': 'Etoile',
    '贝林佐纳': 'Bellinzona', '韦尔': 'Wohlen', '伊韦尔东': 'Yverdon', '拉珀斯维尔': 'Rapperswil',
    '力矩': 'Torque', '捍卫者竞技': 'Defensor', '拉斯彼德拉斯': 'Las Piedras',
    '圣达哥林玛': 'Santa Coloma', 'FC Ordino': 'Ordino', '埃斯卡尔德斯国际': 'Inter Escaldes',
    '艾斯卡迪斯': 'Escaldes', '素可泰FC': 'Sukhothai', '蒙通联': 'Muangthong United',
}

# 联赛代码映射
league_code_mapping = {
    '意甲': 'I1', '法罗超': 'FRO', '瑞士超': 'SWI', '塞尔超': 'SRB', '挪威杯': 'NOR_CUP',
    '比甲': 'BEL', '沙特联': 'SAU', '英超': 'E0', '德甲': 'D1', '西甲': 'SP1',
    '西乙': 'SP2', '波黑超': 'BIH', '希腊超': 'GRE', '克罗甲': 'CRO', '土超': 'TUR',
    '美职': 'MLS', '丹甲': 'DEN2', '捷甲': 'CZE', '以超': 'ISR', '法丙': 'FRA3',
    '法乙': 'FRA2', '南非超': 'RSA', '阿乙': 'ARG2', '黑山甲': 'MNE', '罗甲': 'ROU',
    '波兰甲': 'POL', '德乙': 'D2', '厄瓜甲': 'ECU', '乌拉甲': 'URU', '英甲': 'E3',
    '巴西甲': 'BRA1', '巴西乙': 'BRA2', '苏超': 'SCO', '阿甲': 'ARG', '葡甲': 'P2',
    '玻利甲': 'BOL', '墨联': 'MEX', 'J联赛': 'J1', 'J2联赛': 'J2', 'K联赛': 'K1',
    'K2联赛': 'K2', '安道超': 'AND', '俄超': 'RUS', '中超': 'CHN', '泰超': 'THA',
    '立陶甲': 'LTU', '新加联': 'SGP', '爱沙甲': 'EST', '印度超': 'IND', '荷甲': 'NED',
    '加纳超': 'GHA', '挪超': 'NOR', '挪甲': 'NOR2', '突尼甲': 'TUN', '奥甲': 'AUT',
    '拉脱超': 'LVA', '塞尔甲': 'SRB2', '格鲁超': 'GEO', '亚美超': 'ARM',
    '马其甲': 'MKD', '阿尔巴超': 'ALB', '丹超': 'DEN', '瑞典超': 'SWE', '芬超': 'FIN',
    '芬兰杯': 'FIN_CUP', '冰岛超': 'ISL', '卢森甲': 'LUX', '哥斯甲': 'CRC',
    '哈萨超': 'KAZ', '阿塞超': 'AZE', '乌克超': 'UKR', '葡超': 'P1', '英乙': 'E4',
    '法甲': 'F1', '亚冠乙': 'ACL2', '足总杯': 'FA_CUP',
}

# CSV文件路径映射
csv_paths = {
    'I1': 'd:/football_tools/data/01_europe_leagues/serie_a/serie_a_2024-2025.csv',
    'E0': 'd:/football_tools/data/01_europe_leagues/premier_league/premier_league_2024-2025.csv',
    'D1': 'd:/football_tools/data/01_europe_leagues/bundesliga/bundesliga_2024-2025.csv',
    'D2': 'd:/football_tools/data/01_europe_leagues/bundesliga_2/bundesliga_2_2024-2025.csv',
    'SP1': 'd:/football_tools/data/01_europe_leagues/la_liga/la_liga_2024-2025.csv',
    'SP2': 'd:/football_tools/data/01_europe_leagues/segunda_division/segunda_division_2024-2025.csv',
    'F1': 'd:/football_tools/data/01_europe_leagues/ligue_1/ligue_1_2024-2025.csv',
    'FRA2': 'd:/football_tools/data/01_europe_leagues/ligue_2/ligue_2_2024-2025.csv',
    'NED': 'd:/football_tools/data/01_europe_leagues/eredivisie/eredivisie_2024-2025.csv',
    'P1': 'd:/football_tools/data/01_europe_leagues/primeira_liga/primeira_liga_2024-2025.csv',
    'TUR': 'd:/football_tools/data/01_europe_leagues/super_lig/super_lig_2024-2025.csv',
    'BEL': 'd:/football_tools/data/01_europe_leagues/jupiler_league/jupiler_league_2024-2025.csv',
    'SWI': 'd:/football_tools/data/01_europe_leagues/switzerland/switzerland_2024-2025.csv',
    'AUT': 'd:/football_tools/data/01_europe_leagues/austria/austria_2024-2025.csv',
    'GRE': 'd:/football_tools/data/01_europe_leagues/superleague/superleague_2024-2025.csv',
    'CRO': 'd:/football_tools/data/01_europe_leagues/croatia/croatia_2024-2025.csv',
    'SRB': 'd:/football_tools/data/01_europe_leagues/serbia/serbia_2024-2025.csv',
    'CZE': 'd:/football_tools/data/01_europe_leagues/czech/czech_2024-2025.csv',
    'POL': 'd:/football_tools/data/01_europe_leagues/ekstraklasa/ekstraklasa_2024-2025.csv',
    'DEN': 'd:/football_tools/data/01_europe_leagues/denmark/denmark_2024-2025.csv',
    'NOR': 'd:/football_tools/data/01_europe_leagues/eliteserien/eliteserien_2024-2025.csv',
    'SWE': 'd:/football_tools/data/01_europe_leagues/allsvenskan/allsvenskan_2024-2025.csv',
    'FIN': 'd:/football_tools/data/01_europe_leagues/finland/finland_2025.csv',
    'RUS': 'd:/football_tools/data/01_europe_leagues/russia/russia_2024-2025.csv',
    'SCO': 'd:/football_tools/data/01_europe_leagues/scotland_premier/scotland_premier_2024-2025.csv',
    'ROU': 'd:/football_tools/data/01_europe_leagues/romania/romania_2024-2025.csv',
    'J1': 'd:/football_tools/data/05_asia_leagues/j1_league/j1_league_2025.csv',
    'J2': 'd:/football_tools/data/05_asia_leagues/j2_league/j2_league_2025.csv',
    'K1': 'd:/football_tools/data/05_asia_leagues/k1_league/k1_league_2025-26.csv',
    'K2': 'd:/football_tools/data/05_asia_leagues/k2_league/k2_league_2025-26.csv',
    'CHN': 'd:/football_tools/data/05_asia_leagues/csl/csl_2025.csv',
    'SAU': 'd:/football_tools/data/05_asia_leagues/saudi_pro/saudi_pro_2025-26.csv',
    'MLS': 'd:/football_tools/data/07_north_america/mls/mls_2025.csv',
    'MEX': 'd:/football_tools/data/07_north_america/liga_mx/liga_mx_2024-2025.csv',
    'BRA1': 'd:/football_tools/data/06_south_america/serie_a_brazil/serie_a_brazil_2025-2026.csv',
    'BRA2': 'd:/football_tools/data/06_south_america/serie_b_brazil/serie_b_brazil_2025.csv',
    'ARG': 'd:/football_tools/data/06_south_america/primera_division_argentina/primera_division_argentina_2025.csv',
    'ARG2': 'd:/football_tools/data/06_south_america/primera_b_nacional/primera_b_nacional_2025.csv',
    'URU': 'd:/football_tools/data/06_south_america/uruguay/uruguay_2025.csv',
    'ECU': 'd:/football_tools/data/06_south_america/ecuador/ecuador_2025.csv',
    'BOL': 'd:/football_tools/data/06_south_america/bolivia/bolivia_2025.csv',
    'FA_CUP': 'd:/football_tools/data/02_europe_cups/fa_cup/fa_cup_2024-2025.csv',
}

def parse_match_data(raw_data):
    """解析比赛数据"""
    matches = []
    current_date = None

    lines = raw_data.strip().split('\n')
    for line in lines:
        line = line.strip()
        if not line:
            continue

        # 检查日期行
        date_match = re.match(r'(\d{4}-\d{2}-\d{2})', line)
        if date_match:
            current_date = date_match.group(1)
            continue

        # 跳过标题行
        if '选(序)' in line or '赛事' in line:
            continue

        # 解析比赛行
        parts = line.split('\t')
        if len(parts) >= 7:
            try:
                league = parts[1].strip()
                time_str = parts[2].strip()
                status = parts[3].strip()
                home_team_raw = parts[4].strip()
                score = parts[5].strip()
                away_team_raw = parts[6].strip()

                # 提取比分
                score_parts = score.split(' - ')
                if len(score_parts) == 2:
                    try:
                        home_goals = int(score_parts[0].strip())
                        away_goals = int(score_parts[1].strip())
                    except:
                        continue
                else:
                    continue

                # 清理球队名称
                home_team = re.sub(r'\[\d+\]|1\[|\d+\[|挪超|英超|J联|沙联|芬超|芬甲', '', home_team_raw).strip()
                away_team = re.sub(r'\[\d+\]|1\[|\d+\[|挪超|英超|J联|沙联|芬超|芬甲', '', away_team_raw).strip()

                # 提取半场比分
                half_score = parts[7].strip() if len(parts) > 7 else ''
                half_parts = half_score.split('-')
                if len(half_parts) == 2:
                    try:
                        home_half_goals = int(half_parts[0].strip())
                        away_half_goals = int(half_parts[1].strip())
                    except:
                        home_half_goals = None
                        away_half_goals = None
                else:
                    home_half_goals = None
                    away_half_goals = None

                # 提取赔率
                odds_str = parts[9].strip() if len(parts) > 9 else ''
                odds_match = re.findall(r'(\d+\.\d+)', odds_str)
                home_odds = float(odds_match[0]) if len(odds_match) > 0 else None
                draw_odds = float(odds_match[1]) if len(odds_match) > 1 else None
                away_odds = float(odds_match[2]) if len(odds_match) > 2 else None

                # 转换球队名称
                home_team_en = team_name_mapping.get(home_team, home_team)
                away_team_en = team_name_mapping.get(away_team, away_team)

                # 计算结果
                if home_goals > away_goals:
                    ftr = 'H'
                elif home_goals < away_goals:
                    ftr = 'A'
                else:
                    ftr = 'D'

                # 确定状态
                if status in ['完', '点球完', '加时完']:
                    match_status = 'Finished'
                elif status == '延期':
                    match_status = 'Postponed'
                elif status == '取消':
                    match_status = 'Cancelled'
                elif status == '腰斩':
                    match_status = 'Abandoned'
                else:
                    match_status = status

                league_code = league_code_mapping.get(league, league)

                matches.append({
                    'date': current_date,
                    'time': time_str,
                    'league': league,
                    'league_code': league_code,
                    'home_team': home_team_en,
                    'away_team': away_team_en,
                    'home_goals': home_goals,
                    'away_goals': away_goals,
                    'home_half_goals': home_half_goals,
                    'away_half_goals': away_half_goals,
                    'home_odds': home_odds,
                    'draw_odds': draw_odds,
                    'away_odds': away_odds,
                    'ftr': ftr,
                    'status': match_status,
                })
            except Exception as e:
                pass

    return matches

def add_matches_to_csv(matches):
    """添加比赛到CSV文件"""
    # 按联赛分组
    matches_by_league = {}
    for match in matches:
        code = match['league_code']
        if code not in matches_by_league:
            matches_by_league[code] = []
        matches_by_league[code].append(match)

    total_added = 0
    for code, league_matches in matches_by_league.items():
        csv_path = csv_paths.get(code)
        if not csv_path:
            print(f"No CSV path for league code: {code}")
            continue

        if not os.path.exists(csv_path):
            print(f"CSV file not found: {csv_path}")
            continue

        # 读取现有数据
        with open(csv_path, 'r', encoding='utf-8') as f:
            reader = csv.reader(f)
            header = next(reader)
            rows = list(reader)

        # 检查已存在的比赛
        existing_keys = set()
        for row in rows:
            if len(row) >= 5:
                key = (row[1], row[3], row[4])  # Date, HomeTeam, AwayTeam
                existing_keys.add(key)

        # 添加新比赛
        added = 0
        for match in league_matches:
            key = (match['date'], match['home_team'], match['away_team'])
            if key not in existing_keys:
                # 构建完整的行
                full_row = [''] * len(header)
                full_row[0] = match['league_code']
                full_row[1] = match['date']
                full_row[2] = match['time']
                full_row[3] = match['home_team']
                full_row[4] = match['away_team']
                full_row[5] = str(match['home_goals'])
                full_row[6] = str(match['away_goals'])
                full_row[7] = match['ftr']
                if len(header) > 8 and match['home_half_goals'] is not None:
                    full_row[8] = str(match['home_half_goals'])
                if len(header) > 9 and match['away_half_goals'] is not None:
                    full_row[9] = str(match['away_half_goals'])
                if len(header) > 23 and match['home_odds']:
                    full_row[23] = str(match['home_odds'])
                if len(header) > 24 and match['draw_odds']:
                    full_row[24] = str(match['draw_odds'])
                if len(header) > 25 and match['away_odds']:
                    full_row[25] = str(match['away_odds'])
                if len(header) > 66:
                    full_row[66] = match['status']

                rows.append(full_row)
                added += 1

        # 写回文件
        with open(csv_path, 'w', encoding='utf-8', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(header)
            writer.writerows(rows)

        print(f"{code}: Added {added} matches")
        total_added += added

    return total_added

if __name__ == '__main__':
    # 读取比赛数据文件
    data_file = 'd:/football_tools/scripts/match_data.txt'
    if os.path.exists(data_file):
        with open(data_file, 'r', encoding='utf-8') as f:
            raw_data = f.read()
    else:
        print("Data file not found, using inline data")
        raw_data = ""

    matches = parse_match_data(raw_data)
    print(f"Parsed {len(matches)} matches")

    added = add_matches_to_csv(matches)
    print(f"\nTotal added: {added} matches")
