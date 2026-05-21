"""
处理欧冠数据 - 标准化格式
"""
import csv
from pathlib import Path
from collections import defaultdict
from datetime import datetime

# 欧冠球队中文名映射
CHAMPIONS_LEAGUE_TEAMS_CN = {
    # 英超
    'Manchester City': '曼城',
    'Manchester City FC (ENG)': '曼城',
    'Liverpool': '利物浦',
    'Liverpool FC (ENG)': '利物浦',
    'Chelsea': '切尔西',
    'Chelsea FC (ENG)': '切尔西',
    'Arsenal': '阿森纳',
    'Arsenal FC (ENG)': '阿森纳',
    'Manchester United': '曼联',
    'Manchester United (ENG)': '曼联',
    'Tottenham': '热刺',
    'Tottenham Hotspur (ENG)': '热刺',
    'Leicester City': '莱斯特城',
    'Leicester City FC (ENG)': '莱斯特城',
    'Newcastle United': '纽卡斯尔',
    'Aston Villa': '阿斯顿维拉',
    'Aston Villa FC (ENG)': '阿斯顿维拉',
    'West Ham United': '西汉姆联',

    # 西甲
    'Real Madrid': '皇家马德里',
    'Real Madrid CF (ESP)': '皇家马德里',
    'FC Barcelona': '巴塞罗那',
    'FC Barcelona (ESP)': '巴塞罗那',
    'Atletico Madrid': '马德里竞技',
    'Club Atlético de Madrid (ESP)': '马德里竞技',
    'Atlético Madrid (ESP)': '马德里竞技',
    'Sevilla': '塞维利亚',
    'Sevilla FC (ESP)': '塞维利亚',
    'Valencia': '瓦伦西亚',
    'Valencia CF (ESP)': '瓦伦西亚',
    'Villarreal': '比利亚雷亚尔',
    'Villarreal CF (ESP)': '比利亚雷亚尔',
    'Real Sociedad': '皇家社会',
    'Real Betis': '皇家贝蒂斯',
    'Athletic Bilbao': '毕尔巴鄂竞技',
    'Girona': '赫罗纳',
    'Girona FC (ESP)': '赫罗纳',

    # 德甲
    'Bayern Munich': '拜仁慕尼黑',
    'Bayern München (GER)': '拜仁慕尼黑',
    'FC Bayern München (GER)': '拜仁慕尼黑',
    'Borussia Dortmund': '多特蒙德',
    'Borussia Dortmund (GER)': '多特蒙德',
    'RB Leipzig': '莱比锡红牛',
    'RB Leipzig (GER)': '莱比锡红牛',
    'Bayer Leverkusen': '勒沃库森',
    'Bayer 04 Leverkusen (GER)': '勒沃库森',
    'Borussia M\'gladbach': '门兴格拉德巴赫',
    'VfL Wolfsburg': '沃尔夫斯堡',
    'Eintracht Frankfurt': '法兰克福',
    'VfB Stuttgart': '斯图加特',
    'Union Berlin': '柏林联合',
    'SC Freiburg': '弗赖堡',

    # 意甲
    'Juventus': '尤文图斯',
    'Juventus FC (ITA)': '尤文图斯',
    'AC Milan': 'AC米兰',
    'AC Milan (ITA)': 'AC米兰',
    'Inter': '国际米兰',
    'FC Internazionale Milano (ITA)': '国际米兰',
    'Inter (ITA)': '国际米兰',
    'Napoli': '那不勒斯',
    'SSC Napoli (ITA)': '那不勒斯',
    'Roma': '罗马',
    'AS Roma (ITA)': '罗马',
    'Lazio': '拉齐奥',
    'SS Lazio (ITA)': '拉齐奥',
    'Atalanta': '亚特兰大',
    'Atalanta BC (ITA)': '亚特兰大',
    'Fiorentina': '佛罗伦萨',
    'Bologna': '博洛尼亚',
    'Bologna FC 1909 (ITA)': '博洛尼亚',

    # 法甲
    'Paris Saint-Germain': '巴黎圣日耳曼',
    'Paris Saint-Germain FC (FRA)': '巴黎圣日耳曼',
    'Marseille': '马赛',
    'Olympique de Marseille (FRA)': '马赛',
    'Lyon': '里昂',
    'Olympique Lyonnais (FRA)': '里昂',
    'Monaco': '摩纳哥',
    'AS Monaco FC (MCO)': '摩纳哥',
    'Lille': '里尔',
    'Lille OSC (FRA)': '里尔',
    'Nice': '尼斯',
    'Lens': '朗斯',
    'Rennes': '雷恩',
    'Brest': '布雷斯特',
    'Stade Brestois 29 (FRA)': '布雷斯特',

    # 葡超
    'Benfica': '本菲卡',
    'SL Benfica (POR)': '本菲卡',
    'Sport Lisboa e Benfica (POR)': '本菲卡',
    'Porto': '波尔图',
    'FC Porto (POR)': '波尔图',
    'Sporting CP': '葡萄牙体育',
    'Sporting Clube de Portugal (POR)': '葡萄牙体育',
    'Braga': '布拉加',

    # 荷甲
    'Ajax': '阿贾克斯',
    'AFC Ajax (NED)': '阿贾克斯',
    'PSV': '埃因霍温',
    'PSV (NED)': '埃因霍温',
    'PSV Eindhoven': '埃因霍温',
    'Feyenoord': '费耶诺德',
    'Feyenoord Rotterdam (NED)': '费耶诺德',

    # 比甲
    'Club Brugge': '布鲁日',
    'Club Brugge KV (BEL)': '布鲁日',
    'Anderlecht': '安德莱赫特',
    'RSC Anderlecht (BEL)': '安德莱赫特',
    'Genk': '亨克',
    'KRC Genk (BEL)': '亨克',
    'Antwerp': '安特卫普',

    # 奥地利
    'RB Salzburg': '萨尔茨堡红牛',
    'RB Salzburg (AUT)': '萨尔茨堡红牛',
    'FC Red Bull Salzburg (AUT)': '萨尔茨堡红牛',
    'Sturm Graz': '格拉茨风暴',
    'SK Sturm Graz (AUT)': '格拉茨风暴',

    # 苏超
    'Celtic': '凯尔特人',
    'Celtic FC (SCO)': '凯尔特人',
    'Rangers': '流浪者',
    'Rangers FC (SCO)': '流浪者',

    # 土超
    'Galatasaray': '加拉塔萨雷',
    'Galatasaray (TUR)': '加拉塔萨雷',
    'Fenerbahce': '费内巴切',
    'Besiktas': '贝西克塔斯',

    # 乌克兰
    'Shakhtar Donetsk': '顿涅茨克矿工',
    'Shakhtar Donetsk (UKR)': '顿涅茨克矿工',
    'FK Shakhtar Donetsk (UKR)': '顿涅茨克矿工',
    'Dynamo Kyiv': '基辅迪纳摩',

    # 俄罗斯
    'Zenit': '泽尼特',
    'Zenit St. Petersburg (RUS)': '泽尼特',
    'Lokomotiv Moscow': '莫斯科火车头',
    'Lokomotiv Moskva (RUS)': '莫斯科火车头',
    'CSKA Moscow': '莫斯科中央陆军',
    'CSKA Moskva (RUS)': '莫斯科中央陆军',
    'Spartak Moscow': '莫斯科斯巴达',

    # 希腊
    'Olympiacos': '奥林匹亚科斯',
    'Olympiakos Piraeus (GRE)': '奥林匹亚科斯',
    'Panathinaikos': '帕纳辛奈科斯',
    'PAOK': 'PAOK',

    # 塞尔维亚
    'Crvena Zvezda': '贝尔格莱德红星',
    'Crvena Zvezda (SRB)': '贝尔格莱德红星',
    'FK Crvena Zvezda (SRB)': '贝尔格莱德红星',
    'Partizan': '贝尔格莱德游击队',

    # 克罗地亚
    'Dinamo Zagreb': '萨格勒布迪纳摩',
    'Dinamo Zagreb (CRO)': '萨格勒布迪纳摩',
    'GNK Dinamo Zagreb (CRO)': '萨格勒布迪纳摩',

    # 捷克
    'Slavia Praha': '布拉格斯拉维亚',
    'Slavia Praha (CZE)': '布拉格斯拉维亚',
    'Sparta Praha': '布拉格斯巴达',
    'AC Sparta Praha (CZE)': '布拉格斯巴达',
    'Viktoria Plzeň': '比尔森胜利',
    'Viktoria Plzen (CZE)': '比尔森胜利',

    # 瑞士
    'Young Boys': '年轻人',
    'BSC Young Boys (SUI)': '年轻人',
    'Basel': '巴塞尔',
    'FC Basel 1893 (SUI)': '巴塞尔',

    # 波兰
    'Legia Warsaw': '华沙莱吉亚',

    # 匈牙利
    'Ferencvaros': '费伦茨瓦罗斯',

    # 以色列
    'Maccabi Haifa': '海法马卡比',
    'Maccabi Tel Aviv': '特拉维夫马卡比',

    # 丹麦
    'Copenhagen': '哥本哈根',
    'FC Copenhagen (DEN)': '哥本哈根',
    'Midtjylland': '中日德兰',

    # 瑞典
    'Malmo': '马尔默',
    'Malmö FF (SWE)': '马尔默',

    # 挪威
    'Molde': '莫尔德',

    # 芬兰
    'HJK Helsinki': '赫尔辛基',

    # 罗马尼亚
    'CFR Cluj': '克卢日',

    # 保加利亚
    'Ludogorets': '卢多戈雷茨',

    # 塞浦路斯
    'APOEL': '希腊人竞技',
    'APOEL Nikosia (CYP)': '希腊人竞技',
    'Apoel Nicosia': '希腊人竞技',

    # 其他
    'Salzburg': '萨尔茨堡红牛',
    'BATE Borisov': '鲍里索夫',
    'BATE Borisov (BLR)': '鲍里索夫',
    'Astana': '阿斯塔纳',
    'Qarabag': '卡拉巴赫',
    'Qarabağ FK (AZE)': '卡拉巴赫',
    'Sheriff Tiraspol': '蒂拉斯波尔警长',
    'Oţelul Galaţi': '加拉茨钢铁',
    'Otelul Galati': '加拉茨钢铁',
    'Trabzonspor': '特拉布宗体育',
    'Trabzonspor (TUR)': '特拉布宗体育',
    'Olympique Marseille': '马赛',
    'AC Omonia': '奥莫尼亚',
    'Dinamo Zagreb (CRO)': '萨格勒布迪纳摩',
    'KRC Genk (BEL)': '亨克',
    'Olympiakos Piraeus (GRE)': '奥林匹亚科斯',
    'Inter (ITA)': '国际米兰',
    'SSC Napoli (ITA)': '那不勒斯',
    'AFC Ajax (NED)': '阿贾克斯',
    'Lille OSC (FRA)': '里尔',
    'Viktoria Plzeň (CZE)': '比尔森胜利',
    'BATE Borisov (BLR)': '鲍里索夫',
    'Oţelul Galaţi (ROU)': '加拉茨钢铁',
    'APOEL Nikosia (CYP)': '希腊人竞技',
    'Zenit St. Petersburg (RUS)': '泽尼特',
    'Shakhtar Donetsk (UKR)': '顿涅茨克矿工',
    'CSKA Moskva (RUS)': '莫斯科中央陆军',
    'FK Crvena Zvezda (SRB)': '贝尔格莱德红星',
    'GNK Dinamo Zagreb (CRO)': '萨格勒布迪纳摩',
    'FK Shakhtar Donetsk (UKR)': '顿涅茨克矿工',
    'AC Sparta Praha (CZE)': '布拉格斯巴达',
    'FC Red Bull Salzburg (AUT)': '萨尔茨堡红牛',
    'BSC Young Boys (SUI)': '年轻人',
    'SK Slovan Bratislava (SVK)': '布拉迪斯拉发斯拉夫人',
    'Slovan Bratislava': '布拉迪斯拉发斯拉夫人',

    # 缺失的球队
    '1899 Hoffenheim': '霍芬海姆',
    '1899 Hoffenheim (GER)': '霍芬海姆',
    'TSG Hoffenheim': '霍芬海姆',
    'AEK Athen': '雅典AEK',
    'AEK Athen (GRE)': '雅典AEK',
    'AEK Athens': '雅典AEK',
    'Athletic Club': '毕尔巴鄂竞技',
    'Athletic Club (ESP)': '毕尔巴鄂竞技',
    'Austria Wien': '维也纳奥地利',
    'Austria Wien (AUT)': '维也纳奥地利',
    'FK Austria Wien': '维也纳奥地利',
    'İstanbul Başakşehir': '伊斯坦布尔',
    'İstanbul Başakşehir (TUR)': '伊斯坦布尔',
    'Istanbul Basaksehir': '伊斯坦布尔',
    'Başakşehir FK': '伊斯坦布尔',
    'Malmö FF': '马尔默',
    'Malmö FF (SWE)': '马尔默',
    'Dinamo Kiev': '基辅迪纳摩',
    'Dynamo Kyiv (UKR)': '基辅迪纳摩',
    'FC Dynamo Kyiv': '基辅迪纳摩',
    'FC København': '哥本哈根',
    'FC Copenhagen (DEN)': '哥本哈根',
    'Copenhagen (DEN)': '哥本哈根',
    'København': '哥本哈根',
    'KRC Genk': '亨克',
    'PAOK Saloniki': 'PAOK塞萨洛尼基',
    'PAOK Thessaloniki': 'PAOK塞萨洛尼基',
    'PAOK FC': 'PAOK塞萨洛尼基',
    'RSC Anderlecht': '安德莱赫特',
    'RSC Anderlecht (BEL)': '安德莱赫特',
    'Shakhtar': '顿涅茨克矿工',
    'Shakhtar Donetsk (UKR)': '顿涅茨克矿工',
    'Slavia Praha (CZE)': '布拉格斯拉维亚',
    'Slavia Prague': '布拉格斯拉维亚',
    'SK Slavia Praha': '布拉格斯拉维亚',
    'Olympiacos Piraeus': '奥林匹亚科斯',
    'Olympiacos FC': '奥林匹亚科斯',
    'FC Porto (POR)': '波尔图',
    'FC Porto': '波尔图',
    'FC Salzburg': '萨尔茨堡红牛',
    'Red Bull Salzburg': '萨尔茨堡红牛',
    'FC Basel': '巴塞尔',
    'FC Basel 1893': '巴塞尔',
    'Basel (SUI)': '巴塞尔',
    'Young Boys (SUI)': '年轻人',
    'BSC Young Boys': '年轻人',
    'Club Brugge (BEL)': '布鲁日',
    'Club Brugge KV': '布鲁日',
    'Galatasaray (TUR)': '加拉塔萨雷',
    'Galatasaray SK': '加拉塔萨雷',
    'Crvena Zvezda (SRB)': '贝尔格莱德红星',
    'Red Star Belgrade': '贝尔格莱德红星',
    'FK Crvena zvezda': '贝尔格莱德红星',
    'Dinamo Zagreb (CRO)': '萨格勒布迪纳摩',
    'GNK Dinamo Zagreb': '萨格勒布迪纳摩',
    'NK Dinamo Zagreb': '萨格勒布迪纳摩',
    'Olympiakos (GRE)': '奥林匹亚科斯',
    'Olympiacos Piraeus (GRE)': '奥林匹亚科斯',
    'APOEL Nicosia': '希腊人竞技',
    'APOEL FC': '希腊人竞技',
    'APOEL Nikosia': '希腊人竞技',
    'Viktoria Plzen': '比尔森胜利',
    'FC Viktoria Plzeň': '比尔森胜利',
    'Viktoria Plzeň (CZE)': '比尔森胜利',
    'BATE (BLR)': '鲍里索夫',
    'FC BATE Borisov': '鲍里索夫',
    'BATE Borisov': '鲍里索夫',
    'Lokomotiv Moskva': '莫斯科火车头',
    'FC Lokomotiv Moscow': '莫斯科火车头',
    'Lokomotiv Moscow': '莫斯科火车头',
    'CSKA Moscow': '莫斯科中央陆军',
    'PFC CSKA Moscow': '莫斯科中央陆军',
    'CSKA (RUS)': '莫斯科中央陆军',
    'Zenit (RUS)': '泽尼特',
    'FC Zenit': '泽尼特',
    'Zenit Saint Petersburg': '泽尼特',
    'Shakhtar (UKR)': '顿涅茨克矿工',
    'FC Shakhtar Donetsk': '顿涅茨克矿工',
    'Dinamo Zagreb': '萨格勒布迪纳摩',
    'NK Dinamo': '萨格勒布迪纳摩',
    'Atalanta (ITA)': '亚特兰大',
    'Atalanta BC': '亚特兰大',
    'Atalanta Bergamo': '亚特兰大',
    'Valencia CF (ESP)': '瓦伦西亚',
    'Valencia CF': '瓦伦西亚',
    'Valencia (ESP)': '瓦伦西亚',
    'SSC Napoli (ITA)': '那不勒斯',
    'SSC Napoli': '那不勒斯',
    'Napoli (ITA)': '那不勒斯',
    'FC Barcelona (ESP)': '巴塞罗那',
    'FC Barcelona': '巴塞罗那',
    'Barcelona (ESP)': '巴塞罗那',
    'Chelsea FC (ENG)': '切尔西',
    'Chelsea FC': '切尔西',
    'Chelsea (ENG)': '切尔西',
    'Liverpool FC (ENG)': '利物浦',
    'Liverpool FC': '利物浦',
    'Liverpool (ENG)': '利物浦',
    'Manchester City (ENG)': '曼城',
    'Manchester City FC': '曼城',
    'Man City': '曼城',
    'Tottenham Hotspur (ENG)': '热刺',
    'Tottenham Hotspur': '热刺',
    'Spurs': '热刺',
    'RB Leipzig (GER)': '莱比锡红牛',
    'RB Leipzig': '莱比锡红牛',
    'RasenBallsport Leipzig': '莱比锡红牛',
    'Borussia Dortmund (GER)': '多特蒙德',
    'Borussia Dortmund': '多特蒙德',
    'BVB': '多特蒙德',
    'Bayern München (GER)': '拜仁慕尼黑',
    'FC Bayern München': '拜仁慕尼黑',
    'Bayern Munich': '拜仁慕尼黑',
    'Bayern': '拜仁慕尼黑',
    'Real Madrid CF (ESP)': '皇家马德里',
    'Real Madrid CF': '皇家马德里',
    'Real Madrid (ESP)': '皇家马德里',
    'Paris Saint-Germain FC (FRA)': '巴黎圣日耳曼',
    'Paris Saint-Germain': '巴黎圣日耳曼',
    'PSG': '巴黎圣日耳曼',
    'Paris SG': '巴黎圣日耳曼',
    'Juventus FC (ITA)': '尤文图斯',
    'Juventus FC': '尤文图斯',
    'Juventus (ITA)': '尤文图斯',
    'Juve': '尤文图斯',
    'Olympique Lyonnais (FRA)': '里昂',
    'Olympique Lyonnais': '里昂',
    'Lyon (FRA)': '里昂',
    'OL': '里昂',
    'Olympique Marseille (FRA)': '马赛',
    'Olympique de Marseille': '马赛',
    'Marseille (FRA)': '马赛',
    'OM': '马赛',
    'Lille OSC (FRA)': '里尔',
    'Lille OSC': '里尔',
    'Lille (FRA)': '里尔',
    'LOSC': '里尔',
    'Atlético Madrid (ESP)': '马德里竞技',
    'Atlético Madrid': '马德里竞技',
    'Atletico Madrid (ESP)': '马德里竞技',
    'Atleti': '马德里竞技',
    'SL Benfica (POR)': '本菲卡',
    'SL Benfica': '本菲卡',
    'Benfica (POR)': '本菲卡',
    'Sporting Clube de Portugal (POR)': '葡萄牙体育',
    'Sporting CP (POR)': '葡萄牙体育',
    'Sporting CP': '葡萄牙体育',
    'Sporting Lisbon': '葡萄牙体育',
    'AFC Ajax (NED)': '阿贾克斯',
    'AFC Ajax': '阿贾克斯',
    'Ajax (NED)': '阿贾克斯',
    'Ajax Amsterdam': '阿贾克斯',
    'Feyenoord Rotterdam (NED)': '费耶诺德',
    'Feyenoord': '费耶诺德',
    'Feyenoord (NED)': '费耶诺德',
    'PSV (NED)': '埃因霍温',
    'PSV Eindhoven': '埃因霍温',
    'PSV': '埃因霍温',
    'Philips Sport Vereniging': '埃因霍温',
    'Inter (ITA)': '国际米兰',
    'FC Internazionale Milano': '国际米兰',
    'Internazionale': '国际米兰',
    'Inter Milan': '国际米兰',
    'Arsenal FC (ENG)': '阿森纳',
    'Arsenal FC': '阿森纳',
    'Arsenal (ENG)': '阿森纳',
    'The Gunners': '阿森纳',
    'Manchester United (ENG)': '曼联',
    'Manchester United FC': '曼联',
    'Man United': '曼联',
    'Man Utd': '曼联',
    'Leicester City FC (ENG)': '莱斯特城',
    'Leicester City': '莱斯特城',
    'Leicester (ENG)': '莱斯特城',
    'The Foxes': '莱斯特城',
    'Sevilla FC (ESP)': '塞维利亚',
    'Sevilla FC': '塞维利亚',
    'Sevilla (ESP)': '塞维利亚',
    'Seville': '塞维利亚',
    'Villarreal CF (ESP)': '比利亚雷亚尔',
    'Villarreal CF': '比利亚雷亚尔',
    'Villarreal (ESP)': '比利亚雷亚尔',
    'The Yellow Submarine': '比利亚雷亚尔',
    'Real Sociedad (ESP)': '皇家社会',
    'Real Sociedad': '皇家社会',
    'La Real': '皇家社会',
    'Real Betis (ESP)': '皇家贝蒂斯',
    'Real Betis': '皇家贝蒂斯',
    'Betis': '皇家贝蒂斯',
    'Athletic Club (ESP)': '毕尔巴鄂竞技',
    'Athletic Club': '毕尔巴鄂竞技',
    'Athletic Bilbao': '毕尔巴鄂竞技',
    'The Lions': '毕尔巴鄂竞技',
    'Bayer 04 Leverkusen (GER)': '勒沃库森',
    'Bayer Leverkusen': '勒沃库森',
    'Leverkusen': '勒沃库森',
    'Bayer 04': '勒沃库森',
    'Borussia Mönchengladbach': '门兴格拉德巴赫',
    'Borussia M\'gladbach': '门兴格拉德巴赫',
    'Borussia Monchengladbach': '门兴格拉德巴赫',
    'Gladbach': '门兴格拉德巴赫',
    'VfL Wolfsburg': '沃尔夫斯堡',
    'Wolfsburg': '沃尔夫斯堡',
    'Die Wölfe': '沃尔夫斯堡',
    'Eintracht Frankfurt': '法兰克福',
    'Frankfurt': '法兰克福',
    'SGE': '法兰克福',
    'VfB Stuttgart': '斯图加特',
    'Stuttgart': '斯图加特',
    'Die Roten': '斯图加特',
    'SC Freiburg': '弗赖堡',
    'Freiburg': '弗赖堡',
    'Union Berlin': '柏林联合',
    '1. FC Union Berlin': '柏林联合',
    'RB Salzburg (AUT)': '萨尔茨堡红牛',
    'Red Bull Salzburg (AUT)': '萨尔茨堡红牛',
    'FC Red Bull Salzburg': '萨尔茨堡红牛',
    'Salzburg (AUT)': '萨尔茨堡红牛',
    'SK Sturm Graz (AUT)': '格拉茨风暴',
    'Sturm Graz': '格拉茨风暴',
    'SK Sturm': '格拉茨风暴',
    'Austria Wien (AUT)': '维也纳奥地利',
    'FK Austria Wien': '维也纳奥地利',
    'Austria Vienna': '维也纳奥地利',
    'Celtic FC (SCO)': '凯尔特人',
    'Celtic FC': '凯尔特人',
    'Celtic (SCO)': '凯尔特人',
    'The Bhoys': '凯尔特人',
    'Rangers FC (SCO)': '流浪者',
    'Rangers FC': '流浪者',
    'Rangers (SCO)': '流浪者',
    'Glasgow Rangers': '流浪者',
    'Club Brugge KV (BEL)': '布鲁日',
    'Club Brugge': '布鲁日',
    'Brugge': '布鲁日',
    'Blauw-Zwart': '布鲁日',
    'KRC Genk (BEL)': '亨克',
    'KRC Genk': '亨克',
    'Genk': '亨克',
    'RSC Anderlecht (BEL)': '安德莱赫特',
    'RSC Anderlecht': '安德莱赫特',
    'Anderlecht': '安德莱赫特',
    'Royal Sporting Club Anderlecht': '安德莱赫特',
    'Royal Antwerp FC': '安特卫普',
    'Antwerp': '安特卫普',
    'The Great Old': '安特卫普',
    'Galatasaray (TUR)': '加拉塔萨雷',
    'Galatasaray SK': '加拉塔萨雷',
    'Galatasaray Istanbul': '加拉塔萨雷',
    'Cim Bom': '加拉塔萨雷',
    'Fenerbahçe': '费内巴切',
    'Fenerbahce': '费内巴切',
    'Fenerbahçe SK': '费内巴切',
    'Yellow Canaries': '费内巴切',
    'Beşiktaş': '贝西克塔斯',
    'Besiktas': '贝西克塔斯',
    'Beşiktaş JK': '贝西克塔斯',
    'Black Eagles': '贝西克塔斯',
    'İstanbul Başakşehir (TUR)': '伊斯坦布尔',
    'Istanbul Basaksehir': '伊斯坦布尔',
    'Başakşehir FK': '伊斯坦布尔',
    'Medipol Basaksehir': '伊斯坦布尔',
    'Olympiacos FC (GRE)': '奥林匹亚科斯',
    'Olympiacos Piraeus': '奥林匹亚科斯',
    'Olympiacos (GRE)': '奥林匹亚科斯',
    'Thrylos': '奥林匹亚科斯',
    'PAOK FC (GRE)': 'PAOK塞萨洛尼基',
    'PAOK Thessaloniki': 'PAOK塞萨洛尼基',
    'PAOK (GRE)': 'PAOK塞萨洛尼基',
    'Panathinaikos FC': '帕纳辛奈科斯',
    'Panathinaikos': '帕纳辛奈科斯',
    'Pana': '帕纳辛奈科斯',
    'AEK Athens FC': '雅典AEK',
    'AEK Athens': '雅典AEK',
    'AEK (GRE)': '雅典AEK',
    'Crvena Zvezda (SRB)': '贝尔格莱德红星',
    'FK Crvena Zvezda': '贝尔格莱德红星',
    'Red Star Belgrade': '贝尔格莱德红星',
    'Red Star': '贝尔格莱德红星',
    'Partizan Belgrade': '贝尔格莱德游击队',
    'FK Partizan': '贝尔格莱德游击队',
    'Partizan': '贝尔格莱德游击队',
    'Dinamo Zagreb (CRO)': '萨格勒布迪纳摩',
    'GNK Dinamo Zagreb': '萨格勒布迪纳摩',
    'NK Dinamo Zagreb': '萨格勒布迪纳摩',
    'Dinamo': '萨格勒布迪纳摩',
    'Shakhtar Donetsk (UKR)': '顿涅茨克矿工',
    'FC Shakhtar Donetsk': '顿涅茨克矿工',
    'Shakhtar': '顿涅茨克矿工',
    'The Miners': '顿涅茨克矿工',
    'Dynamo Kyiv (UKR)': '基辅迪纳摩',
    'FC Dynamo Kyiv': '基辅迪纳摩',
    'Dynamo Kiev': '基辅迪纳摩',
    'Zenit St. Petersburg (RUS)': '泽尼特',
    'FC Zenit Saint Petersburg': '泽尼特',
    'Zenit Saint Petersburg': '泽尼特',
    'Zenit': '泽尼特',
    'CSKA Moskva (RUS)': '莫斯科中央陆军',
    'PFC CSKA Moscow': '莫斯科中央陆军',
    'CSKA Moscow': '莫斯科中央陆军',
    'CSKA': '莫斯科中央陆军',
    'Lokomotiv Moskva (RUS)': '莫斯科火车头',
    'FC Lokomotiv Moscow': '莫斯科火车头',
    'Lokomotiv Moscow': '莫斯科火车头',
    'Loko': '莫斯科火车头',
    'Spartak Moscow': '莫斯科斯巴达',
    'FC Spartak Moscow': '莫斯科斯巴达',
    'Spartak': '莫斯科斯巴达',
    'APOEL FC (CYP)': '希腊人竞技',
    'APOEL Nicosia': '希腊人竞技',
    'APOEL': '希腊人竞技',
    'APOEL Nikosia (CYP)': '希腊人竞技',
    'AC Omonia (CYP)': '奥莫尼亚',
    'Omonia Nicosia': '奥莫尼亚',
    'Omonia': '奥莫尼亚',
    'BATE Borisov (BLR)': '鲍里索夫',
    'FC BATE Borisov': '鲍里索夫',
    'BATE': '鲍里索夫',
    'Dinamo Brest': '布雷斯特迪纳摩',
    'FC Dinamo Brest': '布雷斯特迪纳摩',
    'Sheriff Tiraspol': '蒂拉斯波尔警长',
    'FC Sheriff': '蒂拉斯波尔警长',
    'Sheriff': '蒂拉斯波尔警长',
    'Qarabağ FK (AZE)': '卡拉巴赫',
    'Qarabag FK': '卡拉巴赫',
    'Qarabag': '卡拉巴赫',
    'The Horsemen': '卡拉巴赫',
    'Astana FC': '阿斯塔纳',
    'FC Astana': '阿斯塔纳',
    'Astana': '阿斯塔纳',
    'Malmö FF (SWE)': '马尔默',
    'Malmö FF': '马尔默',
    'Malmo FF': '马尔默',
    'Di Blåe': '马尔默',
    'AIK': 'AIK索尔纳',
    'AIK Fotboll': 'AIK索尔纳',
    'Djurgårdens IF': '尤尔加登',
    'Djurgardens IF': '尤尔加登',
    'Rosenborg BK': '罗森博格',
    'Rosenborg': '罗森博格',
    'Molde FK': '莫尔德',
    'Molde': '莫尔德',
    'FC København (DEN)': '哥本哈根',
    'FC Copenhagen': '哥本哈根',
    'Copenhagen': '哥本哈根',
    'FCK': '哥本哈根',
    'FC Midtjylland': '中日德兰',
    'Midtjylland': '中日德兰',
    'FCM': '中日德兰',
    'Brøndby IF': '布隆德比',
    'Brondby IF': '布隆德比',
    'Brondby': '布隆德比',
    'Legia Warsaw': '华沙莱吉亚',
    'Legia Warszawa': '华沙莱吉亚',
    'Legia': '华沙莱吉亚',
    'Lech Poznań': '波兹南莱赫',
    'Lech Poznan': '波兹南莱赫',
    'Lech': '波兹南莱赫',
    'Slavia Praha (CZE)': '布拉格斯拉维亚',
    'SK Slavia Prague': '布拉格斯拉维亚',
    'Slavia Prague': '布拉格斯拉维亚',
    'Sešívaní': '布拉格斯拉维亚',
    'Sparta Praha (CZE)': '布拉格斯巴达',
    'AC Sparta Prague': '布拉格斯巴达',
    'Sparta Prague': '布拉格斯巴达',
    'Viktoria Plzeň (CZE)': '比尔森胜利',
    'FC Viktoria Plzen': '比尔森胜利',
    'Viktoria Plzen': '比尔森胜利',
    'Viktoria': '比尔森胜利',
    'Baník Ostrava': '俄斯特拉发矿工',
    'Banik Ostrava': '俄斯特拉发矿工',
    'Ferencvárosi TC': '费伦茨瓦罗斯',
    'Ferencvaros': '费伦茨瓦罗斯',
    'FTC': '费伦茨瓦罗斯',
    'MOL Fehérvár FC': '费赫尔瓦尔',
    'Fehervar': '费赫尔瓦尔',
    'Videoton': '费赫尔瓦尔',
    'BSC Young Boys (SUI)': '年轻人',
    'Young Boys': '年轻人',
    'YB': '年轻人',
    'FC Basel 1893 (SUI)': '巴塞尔',
    'FC Basel': '巴塞尔',
    'Basel': '巴塞尔',
    'FCB': '巴塞尔',
    'FC Zürich': '苏黎世',
    'FC Zurich': '苏黎世',
    'Zurich': '苏黎世',
    'FC Luzern': '卢塞恩',
    'Luzern': '卢塞恩',
    'Servette FC': '塞尔维特',
    'Servette': '塞尔维特',
    'CFR Cluj': '克卢日',
    'CFR Cluj-Napoca': '克卢日',
    'Universitatea Craiova': '克拉约瓦大学',
    'Craiova': '克拉约瓦大学',
    'FCSB': '布加勒斯特星',
    'Steaua Bucuresti': '布加勒斯特星',
    'Steaua': '布加勒斯特星',
    'Dinamo Bucuresti': '布加勒斯特迪纳摩',
    'Dinamo Bucharest': '布加勒斯特迪纳摩',
    'Ludogorets Razgrad': '卢多戈雷茨',
    'Ludogorets': '卢多戈雷茨',
    'The Eagles': '卢多戈雷茨',
    'CSKA Sofia': '索菲亚中央陆军',
    'CSKA-Sofia': '索菲亚中央陆军',
    'Levski Sofia': '索菲亚列夫斯基',
    'Levski': '索菲亚列夫斯基',
    'Maccabi Haifa FC': '海法马卡比',
    'Maccabi Haifa': '海法马卡比',
    'Maccabi Tel Aviv FC': '特拉维夫马卡比',
    'Maccabi Tel Aviv': '特拉维夫马卡比',
    'Hapoel Tel Aviv': '特拉维夫工人',
    'Hapoel Be\'er Sheva': '贝尔谢巴工人',
    'Be\'er Sheva': '贝尔谢巴工人',
    'Maccabi Netanya': '内坦亚马卡比',
    'Beitar Jerusalem': '耶路撒冷贝塔',
    'HJK Helsinki': '赫尔辛基',
    'HJK': '赫尔辛基',
    'KuPS': '库奥皮奥',
    'Inter Turku': '图尔库国际',
    'FC Inter Turku': '图尔库国际',
    'ŠK Slovan Bratislava': '布拉迪斯拉发斯拉夫人',
    'SK Slovan Bratislava': '布拉迪斯拉发斯拉夫人',
    'Slovan Bratislava': '布拉迪斯拉发斯拉夫人',
    'Slovan Bratislava (SVK)': '布拉迪斯拉发斯拉夫人',

    # 补充缺失的球队
    'Bor. Mönchengladbach': '门兴格拉德巴赫',
    'Borussia Mönchengladbach (GER)': '门兴格拉德巴赫',
    'Borussia Monchengladbach': '门兴格拉德巴赫',
    'Borussia M\'gladbach': '门兴格拉德巴赫',
    'FC Nordsjælland': '北西兰',
    'FC Nordsjaelland': '北西兰',
    'Nordsjaelland': '北西兰',
    'Nordsjælland': '北西兰',
    'FC Schalke 04': '沙尔克04',
    'Schalke 04': '沙尔克04',
    'Schalke': '沙尔克04',
    'FC Steaua Bucureşti': '布加勒斯特星',
    'Steaua Bucuresti': '布加勒斯特星',
    'Steaua Bucureşti': '布加勒斯特星',
    'FK Astana': '阿斯塔纳',
    'Astana FK': '阿斯塔纳',
    'FK Rostov': '罗斯托夫',
    'FC Rostov': '罗斯托夫',
    'Rostov': '罗斯托夫',
    'KAA Gent': '根特',
    'Gent': '根特',
    'AA Gent': '根特',
    'Montpellier HSC': '蒙彼利埃',
    'Montpellier': '蒙彼利埃',
    'MHSC': '蒙彼利埃',
    'Málaga CF': '马拉加',
    'Malaga CF': '马拉加',
    'Malaga': '马拉加',
    'NK Maribor': '马里博尔',
    'Maribor': '马里博尔',
    'PFC Ludogorets Razgrad': '卢多戈雷茨',
    'Ludogorets Razgrad': '卢多戈雷茨',
    'Ludogorets': '卢多戈雷茨',
    'Sporting Braga': '布拉加',
    'SC Braga': '布拉加',
    'Braga': '布拉加',
}

# 阶段映射
STAGE_MAPPING = {
    'group': 'group',
    'group_stage': 'group',
    'league_phase': 'league_phase',
    'round_of_16': 'round_of_16',
    'round_of_32': 'round_of_32',
    'quarterfinal': 'quarterfinal',
    'semifinal': 'semifinal',
    'final': 'final',
    'qualifying': 'qualifying',
    'playoff': 'playoff',
}

STAGE_ORDER = {
    'qualifying': 1,
    'playoff': 2,
    'group': 3,
    'league_phase': 3,
    'round_of_32': 4,
    'round_of_16': 5,
    'quarterfinal': 6,
    'semifinal': 7,
    'final': 8,
}

PHASE_MAPPING = {
    'qualifying': 'qualifying',
    'playoff': 'qualifying',
    'group': 'main',
    'league_phase': 'main',
    'round_of_32': 'main',
    'round_of_16': 'main',
    'quarterfinal': 'main',
    'semifinal': 'main',
    'final': 'main',
}

def clean_team_name(team_name):
    """清理球队名称，移除国家后缀"""
    if not team_name:
        return ''
    # 移除类似 (ENG), (ESP) 的国家后缀
    import re
    cleaned = re.sub(r'\s*\([A-Z]{3}\)\s*$', '', team_name)
    return cleaned.strip()

def get_team_cn(team_name):
    """获取球队中文名"""
    if not team_name:
        return ''

    # 先尝试完整匹配
    if team_name in CHAMPIONS_LEAGUE_TEAMS_CN:
        return CHAMPIONS_LEAGUE_TEAMS_CN[team_name]

    # 清理后匹配
    cleaned = clean_team_name(team_name)
    if cleaned in CHAMPIONS_LEAGUE_TEAMS_CN:
        return CHAMPIONS_LEAGUE_TEAMS_CN[cleaned]

    # 尝试不带FC等后缀
    for key, value in CHAMPIONS_LEAGUE_TEAMS_CN.items():
        if key.startswith(cleaned) or cleaned.startswith(key):
            return value

    return ''

def infer_stage_from_date(date_str, season, match_index, total_matches):
    """根据日期和比赛位置推断阶段"""
    try:
        date = datetime.strptime(date_str, '%Y-%m-%d')
        year = date.year
        month = date.month
        day = date.day

        # 欧冠赛季结构 (传统赛制):
        # 小组赛: 9月-12月 (6轮, 每组12场, 共96场)
        # 16强: 2月-3月 (首回合+次回合, 共16场)
        # 八强: 4月 (首回合+次回合, 共8场)
        # 半决赛: 4月-5月 (首回合+次回合, 共4场)
        # 决赛: 5月-6月 (1场)

        # 2024-25新赛制 (联赛阶段):
        # 联赛阶段: 9月-1月 (每队8场)
        # 淘汰赛附加赛: 2月
        # 16强: 3月
        # 八强: 4月
        # 半决赛: 4月-5月
        # 决赛: 5月-6月

        if season >= '2024-25':
            # 新赛制
            if month >= 9 or month == 1:
                return 'league_phase'
            elif month == 2:
                return 'playoff'
            elif month == 3:
                return 'round_of_16'
            elif month == 4:
                return 'quarterfinal'
            elif month == 5:
                # 决赛通常在5月底或6月初
                if day >= 28:
                    return 'final'
                return 'semifinal'
            elif month == 6:
                return 'final'
            else:
                return 'league_phase'
        else:
            # 传统赛制
            if month >= 9 and month <= 12:
                return 'group'
            elif month == 2:
                return 'round_of_16'
            elif month == 3:
                return 'round_of_16'
            elif month == 4:
                # 需要区分八强和半决赛
                return 'quarterfinal'
            elif month == 5:
                # 决赛通常在5月底
                if day >= 28:
                    return 'final'
                return 'semifinal'
            elif month == 6:
                return 'final'
            elif month == 8:
                # 2020年因疫情延期
                # 8月7-8日是16强次回合
                # 8月12-19日是八强
                # 8月23日是决赛
                if day >= 23:
                    return 'final'
                elif day >= 12:
                    return 'quarterfinal'
                else:
                    return 'round_of_16'
            else:
                return 'group'
    except:
        return 'group'

def process_champions_league():
    """处理欧冠数据"""
    input_dir = Path('D:/football_tools/data/03_european_competitions/champions_league')
    output_dir = Path('D:/football_tools/new_data/cups/champions_league')
    output_dir.mkdir(parents=True, exist_ok=True)

    # 标准化字段
    fieldnames = [
        'competition', 'competition_cn', 'season', 'phase', 'stage', 'stage_order',
        'group_name', 'group_round', 'leg',
        'match_date', 'match_time',
        'home_team', 'home_team_cn', 'away_team', 'away_team_cn',
        'home_goals', 'away_goals', 'home_goals_ht', 'away_goals_ht',
        'home_goals_et', 'away_goals_et', 'home_penalties', 'away_penalties', 'result',
        'venue', 'attendance', 'referee', 'status'
    ]

    total_matches = 0
    total_missing_cn = set()

    for csv_file in sorted(input_dir.glob('*.csv')):
        if csv_file.name == 'champions_league_all.csv':
            continue

        season = csv_file.stem.replace('champions_league_', '')
        matches = []

        with open(csv_file, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                home_team = row.get('HomeTeam', '').strip()
                away_team = row.get('AwayTeam', '').strip()
                date = row.get('Date', '').strip()

                if not home_team or not away_team:
                    continue

                # 获取中文名
                home_cn = get_team_cn(home_team)
                away_cn = get_team_cn(away_team)

                if not home_cn:
                    total_missing_cn.add(home_team)
                if not away_cn:
                    total_missing_cn.add(away_team)

                # 推断阶段
                stage = infer_stage_from_date(date, season, 0, 0)

                match = {
                    'competition': 'champions_league',
                    'competition_cn': '欧冠',
                    'season': season,
                    'phase': PHASE_MAPPING.get(stage, 'main'),
                    'stage': stage,
                    'stage_order': STAGE_ORDER.get(stage, 3),
                    'group_name': '',  # 需要外部数据填充
                    'group_round': '',
                    'leg': '',
                    'match_date': date,
                    'match_time': row.get('Time', '').strip(),
                    'home_team': clean_team_name(home_team),
                    'home_team_cn': home_cn,
                    'away_team': clean_team_name(away_team),
                    'away_team_cn': away_cn,
                    'home_goals': row.get('FTHG', ''),
                    'away_goals': row.get('FTAG', ''),
                    'home_goals_ht': row.get('HTHG', ''),
                    'away_goals_ht': row.get('HTAG', ''),
                    'home_goals_et': '',
                    'away_goals_et': '',
                    'home_penalties': '',
                    'away_penalties': '',
                    'result': row.get('FTR', ''),
                    'venue': '',
                    'attendance': row.get('Attendance', ''),
                    'referee': row.get('Referee', ''),
                    'status': row.get('Status', 'Finished') or 'Finished'
                }
                matches.append(match)

        if matches:
            output_file = output_dir / f'champions_league_{season}.csv'
            with open(output_file, 'w', encoding='utf-8', newline='') as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(matches)

            print(f'{season}: {len(matches)} 场比赛')
            total_matches += len(matches)

    print(f'\n总计: {total_matches} 场比赛')
    print(f'缺失中文名球队: {len(total_missing_cn)}')
    if total_missing_cn:
        print('缺失列表:')
        for team in sorted(total_missing_cn)[:20]:
            print(f'  {team}')
        if len(total_missing_cn) > 20:
            print(f'  ... 还有 {len(total_missing_cn) - 20} 个')

if __name__ == '__main__':
    process_champions_league()
