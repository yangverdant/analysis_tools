"""
补充欧战球队详细信息
"""

import sqlite3
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent
DATABASE_PATH = PROJECT_ROOT / "data" / "football_v2.db"

# 主要欧战球队详细信息
UEFA_TEAMS = {
    # 英超球队
    'Manchester City': {'name_cn': '曼城', 'city': 'Manchester', 'city_cn': '曼彻斯特', 'stadium': 'Etihad Stadium', 'stadium_capacity': 53500},
    'Liverpool': {'name_cn': '利物浦', 'city': 'Liverpool', 'city_cn': '利物浦', 'stadium': 'Anfield', 'stadium_capacity': 61276},
    'Chelsea': {'name_cn': '切尔西', 'city': 'London', 'city_cn': '伦敦', 'stadium': 'Stamford Bridge', 'stadium_capacity': 41841},
    'Arsenal': {'name_cn': '阿森纳', 'city': 'London', 'city_cn': '伦敦', 'stadium': 'Emirates Stadium', 'stadium_capacity': 60704},
    'Tottenham': {'name_cn': '热刺', 'city': 'London', 'city_cn': '伦敦', 'stadium': 'Tottenham Hotspur Stadium', 'stadium_capacity': 62850},
    'Manchester United': {'name_cn': '曼联', 'city': 'Manchester', 'city_cn': '曼彻斯特', 'stadium': 'Old Trafford', 'stadium_capacity': 74310},
    'Newcastle': {'name_cn': '纽卡斯尔', 'city': 'Newcastle', 'city_cn': '纽卡斯尔', 'stadium': 'St James Park', 'stadium_capacity': 52305},
    'West Ham': {'name_cn': '西汉姆联', 'city': 'London', 'city_cn': '伦敦', 'stadium': 'London Stadium', 'stadium_capacity': 60000},
    'Aston Villa': {'name_cn': '阿斯顿维拉', 'city': 'Birmingham', 'city_cn': '伯明翰', 'stadium': 'Villa Park', 'stadium_capacity': 42682},
    'Brighton': {'name_cn': '布莱顿', 'city': 'Brighton', 'city_cn': '布莱顿', 'stadium': 'Amex Stadium', 'stadium_capacity': 30750},
    'Leicester': {'name_cn': '莱斯特城', 'city': 'Leicester', 'city_cn': '莱斯特', 'stadium': 'King Power Stadium', 'stadium_capacity': 32262},
    'Everton': {'name_cn': '埃弗顿', 'city': 'Liverpool', 'city_cn': '利物浦', 'stadium': 'Goodison Park', 'stadium_capacity': 39572},
    'Fulham': {'name_cn': '富勒姆', 'city': 'London', 'city_cn': '伦敦', 'stadium': 'Craven Cottage', 'stadium_capacity': 25700},
    'Crystal Palace': {'name_cn': '水晶宫', 'city': 'London', 'city_cn': '伦敦', 'stadium': 'Selhurst Park', 'stadium_capacity': 25486},
    'Brentford': {'name_cn': '布伦特福德', 'city': 'London', 'city_cn': '伦敦', 'stadium': 'Brentford Community Stadium', 'stadium_capacity': 17250},
    'Wolves': {'name_cn': '狼队', 'city': 'Wolverhampton', 'city_cn': '伍尔弗汉普顿', 'stadium': 'Molineux Stadium', 'stadium_capacity': 32110},

    # 西甲球队
    'Real Madrid': {'name_cn': '皇家马德里', 'city': 'Madrid', 'city_cn': '马德里', 'stadium': 'Santiago Bernabeu', 'stadium_capacity': 83186},
    'Barcelona': {'name_cn': '巴塞罗那', 'city': 'Barcelona', 'city_cn': '巴塞罗那', 'stadium': 'Camp Nou', 'stadium_capacity': 99274},
    'Atletico Madrid': {'name_cn': '马德里竞技', 'city': 'Madrid', 'city_cn': '马德里', 'stadium': 'Metropolitano', 'stadium_capacity': 70460},
    'Sevilla': {'name_cn': '塞维利亚', 'city': 'Seville', 'city_cn': '塞维利亚', 'stadium': 'Ramon Sanchez Pizjuan', 'stadium_capacity': 42883},
    'Valencia': {'name_cn': '瓦伦西亚', 'city': 'Valencia', 'city_cn': '瓦伦西亚', 'stadium': 'Mestalla', 'stadium_capacity': 49430},
    'Villarreal': {'name_cn': '比利亚雷亚尔', 'city': 'Villarreal', 'city_cn': '比利亚雷亚尔', 'stadium': 'Estadio de la Ceramica', 'stadium_capacity': 23500},
    'Real Sociedad': {'name_cn': '皇家社会', 'city': 'San Sebastian', 'city_cn': '圣塞巴斯蒂安', 'stadium': 'Reale Arena', 'stadium_capacity': 40000},
    'Athletic Bilbao': {'name_cn': '毕尔巴鄂竞技', 'city': 'Bilbao', 'city_cn': '毕尔巴鄂', 'stadium': 'San Mames', 'stadium_capacity': 53289},
    'Real Betis': {'name_cn': '皇家贝蒂斯', 'city': 'Seville', 'city_cn': '塞维利亚', 'stadium': 'Benito Villamarin', 'stadium_capacity': 60720},
    'Girona': {'name_cn': '赫罗纳', 'city': 'Girona', 'city_cn': '赫罗纳', 'stadium': 'Municipal Montilivi', 'stadium_capacity': 14624},

    # 德甲球队
    'Bayern Munich': {'name_cn': '拜仁慕尼黑', 'city': 'Munich', 'city_cn': '慕尼黑', 'stadium': 'Allianz Arena', 'stadium_capacity': 75024},
    'Borussia Dortmund': {'name_cn': '多特蒙德', 'city': 'Dortmund', 'city_cn': '多特蒙德', 'stadium': 'Signal Iduna Park', 'stadium_capacity': 81365},
    'RB Leipzig': {'name_cn': '莱比锡红牛', 'city': 'Leipzig', 'city_cn': '莱比锡', 'stadium': 'Red Bull Arena', 'stadium_capacity': 47069},
    'Bayer Leverkusen': {'name_cn': '勒沃库森', 'city': 'Leverkusen', 'city_cn': '勒沃库森', 'stadium': 'BayArena', 'stadium_capacity': 30210},
    'Eintracht Frankfurt': {'name_cn': '法兰克福', 'city': 'Frankfurt', 'city_cn': '法兰克福', 'stadium': 'Deutsche Bank Park', 'stadium_capacity': 51500},
    'VfB Stuttgart': {'name_cn': '斯图加特', 'city': 'Stuttgart', 'city_cn': '斯图加特', 'stadium': 'MHPArena', 'stadium_capacity': 60449},
    'Borussia M\'gladbach': {'name_cn': '门兴格拉德巴赫', 'city': 'Monchengladbach', 'city_cn': '门兴格拉德巴赫', 'stadium': 'Borussia Park', 'stadium_capacity': 54057},
    'VfL Wolfsburg': {'name_cn': '沃尔夫斯堡', 'city': 'Wolfsburg', 'city_cn': '沃尔夫斯堡', 'stadium': 'Volkswagen Arena', 'stadium_capacity': 30000},
    'SC Freiburg': {'name_cn': '弗赖堡', 'city': 'Freiburg', 'city_cn': '弗赖堡', 'stadium': 'Europa-Park Stadion', 'stadium_capacity': 34700},
    'TSG Hoffenheim': {'name_cn': '霍芬海姆', 'city': 'Sinsheim', 'city_cn': '辛斯海姆', 'stadium': 'Rhein-Neckar-Arena', 'stadium_capacity': 30164},
    '1. FC Union Berlin': {'name_cn': '柏林联合', 'city': 'Berlin', 'city_cn': '柏林', 'stadium': 'Stadion An der Alten Forsterei', 'stadium_capacity': 22012},

    # 意甲球队
    'Inter Milan': {'name_cn': '国际米兰', 'city': 'Milan', 'city_cn': '米兰', 'stadium': 'San Siro', 'stadium_capacity': 75923},
    'AC Milan': {'name_cn': 'AC米兰', 'city': 'Milan', 'city_cn': '米兰', 'stadium': 'San Siro', 'stadium_capacity': 75923},
    'Juventus': {'name_cn': '尤文图斯', 'city': 'Turin', 'city_cn': '都灵', 'stadium': 'Allianz Stadium', 'stadium_capacity': 41507},
    'Napoli': {'name_cn': '那不勒斯', 'city': 'Naples', 'city_cn': '那不勒斯', 'stadium': 'Stadio Diego Armando Maradona', 'stadium_capacity': 54726},
    'AS Roma': {'name_cn': '罗马', 'city': 'Rome', 'city_cn': '罗马', 'stadium': 'Stadio Olimpico', 'stadium_capacity': 70634},
    'Lazio': {'name_cn': '拉齐奥', 'city': 'Rome', 'city_cn': '罗马', 'stadium': 'Stadio Olimpico', 'stadium_capacity': 70634},
    'Atalanta': {'name_cn': '亚特兰大', 'city': 'Bergamo', 'city_cn': '贝加莫', 'stadium': 'Gewiss Stadium', 'stadium_capacity': 24000},
    'Fiorentina': {'name_cn': '佛罗伦萨', 'city': 'Florence', 'city_cn': '佛罗伦萨', 'stadium': 'Stadio Artemio Franchi', 'stadium_capacity': 43147},
    'Bologna': {'name_cn': '博洛尼亚', 'city': 'Bologna', 'city_cn': '博洛尼亚', 'stadium': 'Stadio Renato Dall Ara', 'stadium_capacity': 38279},
    'Torino': {'name_cn': '都灵', 'city': 'Turin', 'city_cn': '都灵', 'stadium': 'Stadio Olimpico Grande Torino', 'stadium_capacity': 27582},

    # 法甲球队
    'Paris Saint Germain': {'name_cn': '巴黎圣日耳曼', 'city': 'Paris', 'city_cn': '巴黎', 'stadium': 'Parc des Princes', 'stadium_capacity': 47929},
    'AS Monaco FC': {'name_cn': '摩纳哥', 'city': 'Monaco', 'city_cn': '摩纳哥', 'stadium': 'Stade Louis II', 'stadium_capacity': 18523},
    'Marseille': {'name_cn': '马赛', 'city': 'Marseille', 'city_cn': '马赛', 'stadium': 'Orange Velodrome', 'stadium_capacity': 67000},
    'Lyon': {'name_cn': '里昂', 'city': 'Lyon', 'city_cn': '里昂', 'stadium': 'Groupama Stadium', 'stadium_capacity': 59186},
    'Lille': {'name_cn': '里尔', 'city': 'Lille', 'city_cn': '里尔', 'stadium': 'Stade Pierre-Mauroy', 'stadium_capacity': 50186},
    'Nice': {'name_cn': '尼斯', 'city': 'Nice', 'city_cn': '尼斯', 'stadium': 'Allianz Riviera', 'stadium_capacity': 35624},
    'Lens': {'name_cn': '朗斯', 'city': 'Lens', 'city_cn': '朗斯', 'stadium': 'Stade Bollaert-Delelis', 'stadium_capacity': 38223},
    'Rennes': {'name_cn': '雷恩', 'city': 'Rennes', 'city_cn': '雷恩', 'stadium': 'Roazhon Park', 'stadium_capacity': 29197},

    # 葡超球队
    'Benfica': {'name_cn': '本菲卡', 'city': 'Lisbon', 'city_cn': '里斯本', 'stadium': 'Estadio da Luz', 'stadium_capacity': 65647},
    'Porto': {'name_cn': '波尔图', 'city': 'Porto', 'city_cn': '波尔图', 'stadium': 'Estadio do Dragao', 'stadium_capacity': 50399},
    'Sporting CP': {'name_cn': '葡萄牙体育', 'city': 'Lisbon', 'city_cn': '里斯本', 'stadium': 'Estadio Jose Alvalade', 'stadium_capacity': 50095},
    'Braga': {'name_cn': '布拉加', 'city': 'Braga', 'city_cn': '布拉加', 'stadium': 'Estadio Municipal de Braga', 'stadium_capacity': 30046},

    # 荷甲球队
    'Ajax': {'name_cn': '阿贾克斯', 'city': 'Amsterdam', 'city_cn': '阿姆斯特丹', 'stadium': 'Johan Cruijff Arena', 'stadium_capacity': 55500},
    'PSV Eindhoven': {'name_cn': '埃因霍温', 'city': 'Eindhoven', 'city_cn': '埃因霍温', 'stadium': 'Philips Stadion', 'stadium_capacity': 35000},
    'Feyenoord': {'name_cn': '费耶诺德', 'city': 'Rotterdam', 'city_cn': '鹿特丹', 'stadium': 'Stadion Feijenoord', 'stadium_capacity': 51577},

    # 苏超球队
    'Celtic': {'name_cn': '凯尔特人', 'city': 'Glasgow', 'city_cn': '格拉斯哥', 'stadium': 'Celtic Park', 'stadium_capacity': 60832},
    'Rangers': {'name_cn': '流浪者', 'city': 'Glasgow', 'city_cn': '格拉斯哥', 'stadium': 'Ibrox Stadium', 'stadium_capacity': 50817},

    # 奥地利球队
    'Red Bull Salzburg': {'name_cn': '萨尔茨堡红牛', 'city': 'Salzburg', 'city_cn': '萨尔茨堡', 'stadium': 'Red Bull Arena', 'stadium_capacity': 31198},
    'Rapid Vienna': {'name_cn': '维也纳快速', 'city': 'Vienna', 'city_cn': '维也纳', 'stadium': 'Allianz Stadion', 'stadium_capacity': 28100},
    'Austria Vienna': {'name_cn': '奥地利维也纳', 'city': 'Vienna', 'city_cn': '维也纳', 'stadium': 'Franz Horr Stadium', 'stadium_capacity': 17500},

    # 比利时球队
    'Club Brugge': {'name_cn': '布鲁日', 'city': 'Bruges', 'city_cn': '布鲁日', 'stadium': 'Jan Breydel Stadium', 'stadium_capacity': 29062},
    'Anderlecht': {'name_cn': '安德莱赫特', 'city': 'Brussels', 'city_cn': '布鲁塞尔', 'stadium': 'Constant Vanden Stock Stadium', 'stadium_capacity': 50093},
    'Genk': {'name_cn': '亨克', 'city': 'Genk', 'city_cn': '亨克', 'stadium': 'Cegeka Arena', 'stadium_capacity': 24596},
    'Gent': {'name_cn': '根特', 'city': 'Ghent', 'city_cn': '根特', 'stadium': 'Ghelamco Arena', 'stadium_capacity': 19968},
    'Royal Antwerp': {'name_cn': '安特卫普', 'city': 'Antwerp', 'city_cn': '安特卫普', 'stadium': 'Bosuilstadion', 'stadium_capacity': 12420},

    # 土耳其球队
    'Galatasaray': {'name_cn': '加拉塔萨雷', 'city': 'Istanbul', 'city_cn': '伊斯坦布尔', 'stadium': 'Nef Stadium', 'stadium_capacity': 52280},
    'Fenerbahce': {'name_cn': '费内巴切', 'city': 'Istanbul', 'city_cn': '伊斯坦布尔', 'stadium': 'Ulker Stadium', 'stadium_capacity': 50509},
    'Besiktas': {'name_cn': '贝西克塔斯', 'city': 'Istanbul', 'city_cn': '伊斯坦布尔', 'stadium': 'Tupras Stadium', 'stadium_capacity': 42390},

    # 希腊球队
    'Olympiakos': {'name_cn': '奥林匹亚科斯', 'city': 'Piraeus', 'city_cn': '比雷埃夫斯', 'stadium': 'Karaiskakis Stadium', 'stadium_capacity': 32115},
    'Panathinaikos': {'name_cn': '帕纳辛奈科斯', 'city': 'Athens', 'city_cn': '雅典', 'stadium': 'Apostolos Nikolaidis', 'stadium_capacity': 16003},
    'PAOK': {'name_cn': 'PAOK', 'city': 'Thessaloniki', 'city_cn': '塞萨洛尼基', 'stadium': 'Toumba Stadium', 'stadium_capacity': 29580},
    'AEK Athens': {'name_cn': 'AEK雅典', 'city': 'Athens', 'city_cn': '雅典', 'stadium': 'Agia Sophia Stadium', 'stadium_capacity': 32250},

    # 乌克兰球队
    'Shakhtar Donetsk': {'name_cn': '顿涅茨克矿工', 'city': 'Donetsk', 'city_cn': '顿涅茨克', 'stadium': 'Donbass Arena', 'stadium_capacity': 52519},
    'Dynamo Kyiv': {'name_cn': '基辅迪纳摩', 'city': 'Kyiv', 'city_cn': '基辅', 'stadium': 'Valeriy Lobanovskiy Stadium', 'stadium_capacity': 16573},

    # 俄罗斯球队
    'Zenit St Petersburg': {'name_cn': '泽尼特', 'city': 'St Petersburg', 'city_cn': '圣彼得堡', 'stadium': 'Krestovsky Stadium', 'stadium_capacity': 67234},
    'CSKA Moscow': {'name_cn': '莫斯科中央陆军', 'city': 'Moscow', 'city_cn': '莫斯科', 'stadium': 'VEB Arena', 'stadium_capacity': 26160},
    'Spartak Moscow': {'name_cn': '莫斯科斯巴达', 'city': 'Moscow', 'city_cn': '莫斯科', 'stadium': 'Otkritie Arena', 'stadium_capacity': 45360},
    'Lokomotiv Moscow': {'name_cn': '莫斯科火车头', 'city': 'Moscow', 'city_cn': '莫斯科', 'stadium': 'RZD Arena', 'stadium_capacity': 27320},

    # 捷克球队
    'Slavia Praha': {'name_cn': '布拉格斯拉维亚', 'city': 'Prague', 'city_cn': '布拉格', 'stadium': 'Fortuna Arena', 'stadium_capacity': 20374},
    'Sparta Praha': {'name_cn': '布拉格斯巴达', 'city': 'Prague', 'city_cn': '布拉格', 'stadium': 'Generali Arena', 'stadium_capacity': 18987},
    'AC Sparta Praha': {'name_cn': '布拉格斯巴达', 'city': 'Prague', 'city_cn': '布拉格', 'stadium': 'Generali Arena', 'stadium_capacity': 18987},

    # 波兰球队
    'Legia Warsaw': {'name_cn': '华沙莱吉亚', 'city': 'Warsaw', 'city_cn': '华沙', 'stadium': 'Polish Army Stadium', 'stadium_capacity': 31107},
    'Lech Poznan': {'name_cn': '波兹南莱赫', 'city': 'Poznan', 'city_cn': '波兹南', 'stadium': 'INEA Stadion', 'stadium_capacity': 42837},

    # 塞尔维亚球队
    'Red Star Belgrade': {'name_cn': '贝尔格莱德红星', 'city': 'Belgrade', 'city_cn': '贝尔格莱德', 'stadium': 'Rajko Mitic Stadium', 'stadium_capacity': 55838},
    'Partizan': {'name_cn': '贝尔格莱德游击', 'city': 'Belgrade', 'city_cn': '贝尔格莱德', 'stadium': 'Partizan Stadium', 'stadium_capacity': 32510},

    # 瑞士球队
    'Young Boys': {'name_cn': '年轻人', 'city': 'Bern', 'city_cn': '伯尔尼', 'stadium': 'Stade de Suisse', 'stadium_capacity': 31360},
    'Basel': {'name_cn': '巴塞尔', 'city': 'Basel', 'city_cn': '巴塞尔', 'stadium': 'St Jakob-Park', 'stadium_capacity': 38505},

    # 丹麦球队
    'FC Copenhagen': {'name_cn': '哥本哈根', 'city': 'Copenhagen', 'city_cn': '哥本哈根', 'stadium': 'Parken', 'stadium_capacity': 38065},
    'Midtjylland': {'name_cn': '中日德兰', 'city': 'Herning', 'city_cn': '海宁', 'stadium': 'MCH Arena', 'stadium_capacity': 11576},

    # 挪威球队
    'Molde': {'name_cn': '莫尔德', 'city': 'Molde', 'city_cn': '莫尔德', 'stadium': 'Aker Stadion', 'stadium_capacity': 11300},
    'Rosenborg': {'name_cn': '罗森博格', 'city': 'Trondheim', 'city_cn': '特隆赫姆', 'stadium': 'Lerkendal Stadion', 'stadium_capacity': 21405},

    # 瑞典球队
    'Malmo FF': {'name_cn': '马尔默', 'city': 'Malmo', 'city_cn': '马尔默', 'stadium': 'Eleda Stadion', 'stadium_capacity': 22180},

    # 以色列球队
    'Maccabi Haifa': {'name_cn': '海法马卡比', 'city': 'Haifa', 'city_cn': '海法', 'stadium': 'Sammy Ofer Stadium', 'stadium_capacity': 30780},
    'Maccabi Tel Aviv': {'name_cn': '特拉维夫马卡比', 'city': 'Tel Aviv', 'city_cn': '特拉维夫', 'stadium': 'Bloomfield Stadium', 'stadium_capacity': 14410},

    # 匈牙利球队
    'Ferencvaros': {'name_cn': '费伦茨瓦罗斯', 'city': 'Budapest', 'city_cn': '布达佩斯', 'stadium': 'Groupama Arena', 'stadium_capacity': 22148},

    # 克罗地亚球队
    'Dinamo Zagreb': {'name_cn': '萨格勒布迪纳摩', 'city': 'Zagreb', 'city_cn': '萨格勒布', 'stadium': 'Stadion Maksimir', 'stadium_capacity': 35000},
    'Hajduk Split': {'name_cn': '哈伊杜克', 'city': 'Split', 'city_cn': '斯普利特', 'stadium': 'Stadion Poljud', 'stadium_capacity': 34984},

    # 罗马尼亚球队
    'FCSB': {'name_cn': 'FCSB', 'city': 'Bucharest', 'city_cn': '布加勒斯特', 'stadium': 'Arena Nationala', 'stadium_capacity': 55634},
    'CFR Cluj': {'name_cn': '克卢日', 'city': 'Cluj-Napoca', 'city_cn': '克卢日', 'stadium': 'Dr Constantin Radulescu', 'stadium_capacity': 23198},

    # 保加利亚球队
    'Ludogorets': {'name_cn': '卢多戈雷茨', 'city': 'Razgrad', 'city_cn': '拉兹格勒', 'stadium': 'Huvepharma Arena', 'stadium_capacity': 10300},

    # 塞浦路斯球队
    'APOEL': {'name_cn': 'APOEL', 'city': 'Nicosia', 'city_cn': '尼科西亚', 'stadium': 'GSP Stadium', 'stadium_capacity': 22859},
    'Omonia': {'name_cn': '奥莫尼亚', 'city': 'Nicosia', 'city_cn': '尼科西亚', 'stadium': 'GSP Stadium', 'stadium_capacity': 22859},
    'Anorthosis': {'name_cn': '阿诺托西斯', 'city': 'Famagusta', 'city_cn': '法马古斯塔', 'stadium': 'Antonis Papadopoulos', 'stadium_capacity': 11000},

    # 斯洛文尼亚球队
    'Maribor': {'name_cn': '马里博尔', 'city': 'Maribor', 'city_cn': '马里博尔', 'stadium': 'Ljudski vrt', 'stadium_capacity': 12570},

    # 斯洛伐克球队
    'Slovan Bratislava': {'name_cn': '布拉迪斯拉发', 'city': 'Bratislava', 'city_cn': '布拉迪斯拉发', 'stadium': 'Tehelne pole', 'stadium_capacity': 22500},

    # 摩尔多瓦球队
    'Sheriff Tiraspol': {'name_cn': '蒂拉斯波尔警长', 'city': 'Tiraspol', 'city_cn': '蒂拉斯波尔', 'stadium': 'Sheriff Stadium', 'stadium_capacity': 13000},

    # 哈萨克斯坦球队
    'Kairat': {'name_cn': '凯拉特', 'city': 'Almaty', 'city_cn': '阿拉木图', 'stadium': 'Almaty Central Stadium', 'stadium_capacity': 23804},
    'Astana': {'name_cn': '阿斯塔纳', 'city': 'Astana', 'city_cn': '阿斯塔纳', 'stadium': 'Astana Arena', 'stadium_capacity': 30000},

    # 阿塞拜疆球队
    'Qarabag': {'name_cn': '卡拉巴赫', 'city': 'Baku', 'city_cn': '巴库', 'stadium': 'Azersun Arena', 'stadium_capacity': 11500},

    # 格鲁吉亚球队
    'Dinamo Tbilisi': {'name_cn': '第比利斯迪纳摩', 'city': 'Tbilisi', 'city_cn': '第比利斯', 'stadium': 'Boris Paichadze Stadium', 'stadium_capacity': 55600},

    # 白俄罗斯球队
    'BATE Borisov': {'name_cn': '鲍里索夫BATE', 'city': 'Borisov', 'city_cn': '鲍里索夫', 'stadium': 'Borisov Arena', 'stadium_capacity': 12215},

    # 冰岛球队
    'KR Reykjavik': {'name_cn': '雷克雅未克KR', 'city': 'Reykjavik', 'city_cn': '雷克雅未克', 'stadium': 'KR-vollur', 'stadium_capacity': 2700},

    # 芬兰球队
    'HJK Helsinki': {'name_cn': '赫尔辛基HJK', 'city': 'Helsinki', 'city_cn': '赫尔辛基', 'stadium': 'Bolt Arena', 'stadium_capacity': 10770},

    # 拉脱维亚球队
    'RFS': {'name_cn': 'RFS', 'city': 'Riga', 'city_cn': '里加', 'stadium': 'LNK Sporta Parks', 'stadium_capacity': 1050},

    # 立陶宛球队
    'Zalgiris': {'name_cn': '萨尔吉里斯', 'city': 'Vilnius', 'city_cn': '维尔纽斯', 'stadium': 'LFF Stadium', 'stadium_capacity': 5167},

    # 爱沙尼亚球队
    'Flora': {'name_cn': '弗洛拉', 'city': 'Tallinn', 'city_cn': '塔林', 'stadium': 'A Le Coq Arena', 'stadium_capacity': 9300},

    # 北马其顿球队
    'Vardar': {'name_cn': '瓦尔达尔', 'city': 'Skopje', 'city_cn': '斯科普里', 'stadium': 'Toce Proeski Arena', 'stadium_capacity': 33460},

    # 黑山球队
    'Buducnost': {'name_cn': '布杜奇诺斯特', 'city': 'Podgorica', 'city_cn': '波德戈里察', 'stadium': 'Stadion pod Goricom', 'stadium_capacity': 15000},

    # 波黑球队
    'Zrinjski': {'name_cn': '兹林斯基', 'city': 'Mostar', 'city_cn': '莫斯塔尔', 'stadium': 'Stadion pod Bijelim Brijegom', 'stadium_capacity': 9000},

    # 阿尔巴尼亚球队
    'Tirana': {'name_cn': '地拉那', 'city': 'Tirana', 'city_cn': '地拉那', 'stadium': 'Arena Kombetare', 'stadium_capacity': 22500},

    # 卢森堡球队
    'F91 Dudelange': {'name_cn': '迪德朗日F91', 'city': 'Dudelange', 'city_cn': '迪德朗日', 'stadium': 'Stade Jos Nosbaum', 'stadium_capacity': 2050},

    # 马耳他球队
    'Valletta': {'name_cn': '瓦莱塔', 'city': 'Valletta', 'city_cn': '瓦莱塔', 'stadium': 'National Stadium', 'stadium_capacity': 17000},

    # 威尔士球队
    'The New Saints': {'name_cn': '新圣徒', 'city': 'Oswestry', 'city_cn': '奥斯韦斯特里', 'stadium': 'Park Hall', 'stadium_capacity': 2000},

    # 北爱尔兰球队
    'Linfield': {'name_cn': '林菲尔德', 'city': 'Belfast', 'city_cn': '贝尔法斯特', 'stadium': 'Windsor Park', 'stadium_capacity': 18549},

    # 爱尔兰球队
    'Shamrock Rovers': {'name_cn': '沙姆洛克流浪', 'city': 'Dublin', 'city_cn': '都柏林', 'stadium': 'Tallaght Stadium', 'stadium_capacity': 9500},

    # 法罗群岛球队
    'Klaksvik': {'name_cn': '克拉克斯维克', 'city': 'Klaksvik', 'city_cn': '克拉克斯维克', 'stadium': 'Djupumargur Stadium', 'stadium_capacity': 2500},

    # 直布罗陀球队
    'Lincoln Red Imps': {'name_cn': '林肯红魔', 'city': 'Gibraltar', 'city_cn': '直布罗陀', 'stadium': 'Victoria Stadium', 'stadium_capacity': 2000},

    # 安道尔球队
    'Sant Julia': {'name_cn': '圣胡利亚', 'city': 'Andorra la Vella', 'city_cn': '安道尔城', 'stadium': 'Estadi Comunal d Andorra la Vella', 'stadium_capacity': 1300},

    # 圣马力诺球队
    'La Fiorita': {'name_cn': '拉菲奥里塔', 'city': 'San Marino', 'city_cn': '圣马力诺', 'stadium': 'Stadio Olimpico Serravalle', 'stadium_capacity': 6915},
}


def get_db():
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def update_team_details():
    """Update team details"""
    print("=" * 60)
    print("Updating UEFA team details...")
    print("=" * 60)

    conn = get_db()
    cursor = conn.cursor()

    updated = 0
    for team_name, details in UEFA_TEAMS.items():
        # Try exact match first
        cursor.execute('''
            SELECT team_id, name_en FROM teams
            WHERE name_en = ? OR name_en LIKE ? OR name_cn = ?
        ''', (team_name, f'%{team_name}%', details.get('name_cn', '')))

        row = cursor.fetchone()
        if row:
            team_id = row[0]

            cursor.execute("PRAGMA table_info(teams)")
            columns = [r[1] for r in cursor.fetchall()]

            if 'city' in columns:
                cursor.execute('''
                    UPDATE teams SET
                        city = COALESCE(?, city),
                        stadium = COALESCE(?, stadium),
                        stadium_capacity = COALESCE(?, stadium_capacity),
                        name_cn = COALESCE(?, name_cn)
                    WHERE team_id = ?
                ''', (details.get('city'), details.get('stadium'),
                      details.get('stadium_capacity'), details.get('name_cn'), team_id))
            else:
                cursor.execute('''
                    UPDATE teams SET
                        stadium = COALESCE(?, stadium),
                        stadium_capacity = COALESCE(?, stadium_capacity),
                        name_cn = COALESCE(?, name_cn)
                    WHERE team_id = ?
                ''', (details.get('stadium'), details.get('stadium_capacity'),
                      details.get('name_cn'), team_id))

            conn.commit()
            updated += 1
            print(f"  Updated: {team_name}")

    conn.close()
    print(f"\nUpdated {updated} teams")
    return updated


def show_stats():
    """Show statistics"""
    print("\n" + "=" * 60)
    print("UEFA Teams Statistics After Update")
    print("=" * 60)

    conn = get_db()
    cursor = conn.cursor()

    cursor.execute('''
        SELECT
            COUNT(*) as total,
            SUM(CASE WHEN stadium IS NOT NULL AND stadium != '' THEN 1 ELSE 0 END) as has_stadium,
            SUM(CASE WHEN stadium_capacity IS NOT NULL THEN 1 ELSE 0 END) as has_capacity,
            SUM(CASE WHEN name_cn IS NOT NULL AND name_cn != '' THEN 1 ELSE 0 END) as has_cn,
            SUM(CASE WHEN city IS NOT NULL AND city != '' THEN 1 ELSE 0 END) as has_city
        FROM teams
        WHERE team_id IN (
            SELECT DISTINCT home_team_id FROM matches WHERE league_id IN (10, 7511, 7512)
            UNION
            SELECT DISTINCT away_team_id FROM matches WHERE league_id IN (10, 7511, 7512)
        )
    ''')

    r = cursor.fetchone()
    print(f"UEFA teams: {r[0]}")
    print(f"  With Chinese name: {r[3]}")
    print(f"  With stadium: {r[1]}")
    print(f"  With capacity: {r[2]}")
    print(f"  With city: {r[4]}")

    conn.close()


if __name__ == "__main__":
    update_team_details()
    show_stats()
    print("\nDone!")