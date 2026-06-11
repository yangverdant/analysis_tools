#!/usr/bin/env python3
"""
批量添加球队中文名称映射
"""
import json
import os

# 文件路径
TEAM_NAMES_FILE = 'data/linkage/team_chinese_names.json'

# 加载现有映射
def load_existing_names():
    if os.path.exists(TEAM_NAMES_FILE):
        with open(TEAM_NAMES_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}

# 保存映射
def save_names(names):
    with open(TEAM_NAMES_FILE, 'w', encoding='utf-8') as f:
        json.dump(names, f, ensure_ascii=False, indent=2)

# 新增的球队中文名称映射
NEW_TEAM_NAMES = {
    # 美职联
    'Austin FC': '奥斯汀FC',
    'Sporting Kansas City': '堪萨斯城竞技',
    'Houston Dynamo': '休斯顿迪纳摩',
    'Vancouver Whitecaps': '温哥华白帽',
    'Seattle Sounders': '西雅图海湾人',
    'Real Salt Lake': '皇家盐湖城',
    'Colorado Rapids': '科罗拉多急流',
    'San Diego FC': '圣迭戈FC',
    'FC Cincinnati': '辛辛那提',
    'San Jose Earthquakes': '圣何塞地震',
    'FC Dallas': '达拉斯FC',
    'Nashville SC': '纳什维尔',
    'Los Angeles FC': '洛杉矶FC',
    'LAFC': '洛杉矶FC',
    'Portland Timbers': '波特兰伐木者',
    'Inter Miami': '迈阿密国际',
    'Minnesota United': '明尼苏达联',

    # 墨联
    'Pumas UNAM': '美洲狮',
    'Pachuca': '帕丘卡',
    'Chivas Guadalajara': '瓜达拉哈拉',

    # J联赛
    'V-Varen Nagasaki': '长崎航海',
    'Vissel Kobe': '神户胜利船',
    'Fagiano Okayama': '冈山绿雉',
    'Shimizu S-Pulse': '清水鼓动',
    'JEF United Chiba': '千叶市原',
    'Blaublitz Akita': '秋田蓝色闪电',
    'Thespa Gunma': '群马温泉',
    'Tochigi SC': '枥木SC',
    'Iwaki FC': '磐城FC',
    'Matsumoto Yamaga': '松本山雅',
    'Omiya Ardija': '大宫松鼠',
    'AC Nagano Parceiro': '长野帕塞罗',
    'Kataller Toyama': '富山胜利',
    'Tokushima Vortis': '德岛漩涡',
    'Zweigen Kanazawa': '金泽赛维根',
    'FC Imabari': 'FC今治',
    'Kamatamare Sanuki': '赞岐釜玉海',
    'Kochi United SC': '高知联合SC',
    'Ehime FC': '爱媛FC',
    'Kagoshima United': '鹿儿岛联',
    'Roasso Kumamoto': '熊本深红',
    'Oita Trinita': '大分三神',
    'Kyoto Sanga': '京都不死鸟',
    'Sanfrecce Hiroshima': '广岛三箭',
    'Nagoya Grampus': '名古屋鲸',
    'Thespakusatsu Gunma': '草津紫湖',
    'Giravanz Kitakyushu': '北九州向日葵',
    'Kawasaki Frontale': '川崎前锋',
    'FC Machida Zelvia': '町田泽维亚',

    # K联赛
    'Jeju United': '济州联',
    'FC Anyang': '安养FC',
    'Seongnam FC': '城南一和',
    'Gyeongnam FC': '庆南FC',
    'Hwaseong FC': '华城FC',
    'Busan IPark': '釜山偶像',
    'Jeonbuk Hyundai': '全北现代',
    'Gimcheon Sangmu': '金泉尚武',
    'Bucheon FC': '富川FC',
    'Gangwon FC': '江原FC',
    'Ulsan Hyundai': '蔚山现代',
    'Chungnam Asan': '忠清南道',

    # 意甲
    'Como 1907': '科莫',

    # 西甲
    'Real Oviedo': '奥维耶多',

    # 法甲
    'Paris FC': '巴黎FC',

    # 德乙
    'SV Elversberg': '艾禾斯堡',
    'Preussen Munster': '明斯特',
    '1. FC Magdeburg': '马格德堡',
    '1. FC Kaiserslautern': '凯泽斯劳滕',
    'Karlsruher SC': '卡尔斯鲁厄',
    'SV Darmstadt 98': '达姆施塔特',
    'SC Paderborn': '帕德博恩',
    'SpVgg Greuther Furth': '菲尔特',
    'Fortuna Dusseldorf': '杜塞尔多夫',
    'Eintracht Braunschweig': '不伦瑞克',
    'Arminia Bielefeld': '比勒菲尔德',
    'Dynamo Dresden': '德累斯顿',
    'Holstein Kiel': '基尔',

    # 荷甲
    'Sparta Rotterdam': '鹿特丹斯巴达',
    'Excelsior Rotterdam': 'SBV精英',
    'Heracles Almelo': '赫拉克勒斯',
    'FC Groningen': '格罗宁根',
    'NEC Nijmegen': '奈梅亨',
    'Go Ahead Eagles': '前进之鹰',
    'FC Volendam': '福伦丹',
    'PEC Zwolle': '兹沃勒',
    'FC Utrecht': '乌得勒支',
    'Fortuna Sittard': '福图纳',
    'SC Heerenveen': '海伦芬',
    'FC Twente': '特温特',
    'AZ Alkmaar': '阿尔克马尔',
    'NAC Breda': '布雷达',

    # 瑞典超
    'Hammarby IF': '哈马比',
    'Malmo FF': '马尔默',
    'IK Brommapojkarna': '布鲁马波卡纳',
    'Kalmar FF': '卡尔马',
    'Mjallby AIF': '米亚尔比',
    'BK Hacken': '赫根',
    'Vasteras SK': '韦斯特罗斯',
    'AIK Stockholm': '索尔纳',
    'Djurgardens IF': '佐加顿斯',
    'IK Sirius': '天狼星',
    'IFK Goteborg': '哥德堡',

    # 丹麦超
    'FC Copenhagen': '哥本哈根',
    'Randers FC': '兰纳斯',
    'FC Fredericia': '腓特烈西亚',
    'Silkeborg IF': '锡尔克堡',
    'Odense BK': '欧登塞',
    'Vejle BK': '瓦埃勒',
    'AGF Aarhus': '奥胡斯',
    'Viborg FF': '维堡',
    'FC Midtjylland': '中日德兰',
    'Brondby IF': '布隆德比',
    'Sonderjyske': '桑德捷斯基',
    'FC Nordsjaelland': '北西兰',

    # 奥甲
    'Red Bull Salzburg': '萨尔茨堡红牛',
    'TSV Hartberg': '哈特堡格',
    'FK Austria Wien': '奥地利维也纳',
    'LASK Linz': '林茨',
    'SK Sturm Graz': '格拉茨风暴',
    'SK Rapid Wien': '维也纳快速',

    # 瑞士超
    'BSC Young Boys': '年轻人',
    'FC Sion': '锡永',
    'FC Lugano': '卢加诺',
    'FC Basel': '巴塞尔',
    'FC St. Gallen': '圣加仑',
    'FC Thun': '图恩',

    # 俄超
    'FC Rostov': '罗斯托夫',
    'FC Zenit': '泽尼特',
    'Krylya Sovetov Samara': '苏维埃之翼',
    'CSKA Moscow': '莫斯科中央陆军',
    'Lokomotiv Moscow': '莫斯科火车头',
    'Rubin Kazan': '喀山红宝石',
    'FC Nizhny Novgorod': '诺夫哥罗德',
    'FC Baltika': '巴提卡',
    'Dynamo Moscow': '莫斯科迪纳摩',
    'FC Sochi': '索契',
    'Akhmat Grozny': '格罗兹尼',
    'FC Krasnodar': '克拉斯诺达尔',

    # 比甲
    'RSC Anderlecht': '安德莱赫特',
    'KV Mechelen': '梅赫伦',
    'SK Lommel': '洛默尔',
    'KMSK Deinze': '登德',
    'Club Brugge KV': '布鲁日',
    'Union Saint-Gilloise': '圣吉罗斯',

    # 土超
    'Kayserispor': '开塞利体育',
    'Konyaspor': '科尼亚体育',
    'Eyupspor': '埃伊乌斯堡',
    'Kasimpasa': '卡斯帕萨',
    'Genclerbirligi': '根克勒比利吉',
    'Antalyaspor': '安塔利亚',
    'Kocaelispor': '科贾埃利体育',

    # 希腊超
    'Aris Thessaloniki': '阿里斯',
    'OFI Crete': '克里特',
    'Volos FC': '沃洛斯',
    'AEK Athens': '雅典AEK',
    'Panathinaikos': '帕纳辛纳科斯',
    'PAOK Thessaloniki': '塞萨洛尼基',

    # 捷甲
    'FK Hradec Kralove': '赫拉德茨',
    'Slavia Prague': '布拉格斯拉维亚',
    'Slovan Liberec': '利贝雷茨',
    'Sparta Prague': '布拉格斯巴达',
    'Viktoria Plzen': '比尔森',
    'FK Jablonec': '亚布洛内茨',

    # 塞尔维亚超
    'FK Cukaricki': '库卡里基',
    'OFK Beograd': 'OFK贝尔格莱德',
    'FK Vojvodina': '沃伊沃迪纳',
    'FK BASK': 'BASK贝尔格莱德',
    'FK Radnicki 1923': '潘切沃工人',
    'FK Sudulica': '苏杜利察',
    'Crvena Zvezda': '贝尔格莱德红星',

    # 克罗地亚甲
    'NK Slaven Belupo': '斯拉文',
    'NK Istra 1961': '伊斯特拉',
    'NK Rijeka': '里耶卡',

    # 罗马尼亚甲
    'CS Universitatea Craiova': '克拉约瓦',
    'FCU Cluj': '克鲁日大学',
    'SCM Gloria Buzau': '梅塔洛',
    'FC Hermannstadt': '赫曼施塔特',
    'FCSB': '布加勒斯特星',

    # 波兰甲
    'Piast Gliwice': '皮亚斯特',
    'Rakow Czestochowa': '琴斯托霍瓦',
    'GKS Katowice': '卡托华斯',
    'Jagiellonia Bialystok': '比亚韦',
    'Arka Gdynia': '阿尔卡',
    'Legia Warsaw': '华沙军团',

    # 巴西甲
    'Coritiba': '科里蒂巴',
    'Esporte Clube Bahia': '巴伊亚',
    'Red Bull Bragantino': '布拉干蒂诺',
    'Vitoria': '维多利亚',
    'Chapecoense': '沙佩科恩斯',
    'Clube do Remo': '瑞模',
    'Atletico Paranaense': '巴拉纳竞技',

    # 巴西乙
    'Ponte Preta': '庞特普雷塔',
    'Londrina': '隆迪那',
    'Vila Nova': '维拉诺瓦',
    'Avaí': '阿瓦伊',
    'Ceara': '塞阿拉',
    'Criciuma': '克里西乌马',
    'Atletico Goianiense': '戈亚尼亚竞技',
    'Sport Recife': '累西腓体育',
    'EC Juventude': '尤文图德',

    # 阿甲
    'Argentinos Juniors': '阿根廷青年人',
    'Gimnasia La Plata': '拉普拉塔体操',

    # 阿乙
    'CA Temperley': 'CA坦波利',
    'Gimnasia y Tiro': '萨尔塔体操和射击',
    'All Boys': '全男孩竞技',

    # 智利甲
    'Huachipato': '瓦奇巴托',
    'Cobreloa': '卡拉雷',
    'Colo Colo': '科洛科洛',
    'Nublense': '纽布伦斯',
    'Cobre Sal': '科布雷萨尔',
    'Universidad de Chile': '智利大学',
    'Deportes Concepcion': '迪康塞普森体育',
    'Everton de Vina': '维尼亚德尔马',

    # 厄瓜甲
    'Manta FC': '曼塔FC',
    'Emelec': '埃梅莱克',
    'Guayaquil City': '瓜亚基尔城',
    'Orense SC': '奥伦斯',

    # 哈萨超
    'FC Astana': '阿斯塔纳',
    'FC Kairat': '阿拉木图凯拉特',
    'FC Aktobe': '阿克托比',
    'FC Atyrau': '阿特雷约',
    'FC Kaisar': '卡萨尔',
    'FC Tobol': '托博尔',
    'FC Ordabasy': '奥达巴斯',
    'FC Zhetysu': '泽泰苏',

    # 阿塞超
    'Zira FK': '济拉',
    'Sumqayit FK': '苏姆盖特',
    'Shamakhi FK': '沙巴巴库',
    'Neftchi Baku': '尼菲治',

    # 乌克超
    'FK Kolos Kovalivka': '科瓦立夫卡',
    'FC Obolon': '奥布隆',
    'FC Lviv': '利沃夫',
    'FC Veres': '维利斯罗夫',
    'Zorya Luhansk': '卢甘斯克黎明',
    'Polissya Zhytomyr': '波利西亚',
    'FC Kryvbas': '卡夫巴斯',
    'FK Oleksandriya': '亚历山德里亚',

    # 乌克甲
    'FC Poltava': '波尔塔瓦',
    'FC Metalist 1925': '米塔利斯特',

    # 葡甲
    'UD Oliveirense': '奥利韦伦斯',
    'AD Fafe': '费古拉斯',
    'UD Leiria': '莱里亚',
    'SC Farense': '费伦斯',
    'Vila Real': '雷克斯欧斯',
    'Lusitania FC': '卢西塔尼亚',
    'FC Penafiel': '佩纳菲耶尔',
    'Portimonense': '波尔蒂芒斯',

    # 冰岛超
    'Vestri': '韦斯特',
    'Vikingur Reykjavik': '维京人',
    'Thor Akureyri': '索尔',
    'IA Akranes': 'IA阿克拉内斯',
    'FH Hafnarfjordur': '哈夫纳夫约杜尔',
    'KA Akureyri': 'KA阿克雷里',
    'Keflavik IF': '凯夫拉维克',
    'Stjarnan': '斯塔尔南',
    'Valur': '瓦路尔',
    'Breidablik': '贝雷达',
    'KR Reykjavik': '雷克雅未克',
    'Fram Reykjavik': '弗拉姆',

    # 爱沙甲
    'FC Flora': '弗洛拉',
    'FCI Levadia': '塔林利瓦迪亚',
    'FC Kuressaare': '库雷萨雷',
    'Nomme Kalju': '诺梅卡尔尤',

    # 拉脱超
    'FK Odari': '奥达里加',
    'Riga FC': '列加斯',
    'FK Liepaja': '利耶帕亚',
    'FK Daugava': '道加瓦',

    # 加纳超
    'Beck United': '贝克联合',
    'Asante Kotoko': '阿桑特琴子',
    'Medeama SC': '梅德玛',
    'Hearts of Oak': '狮子之心',

    # 新加联
    'Tampines Rovers': '淡滨尼流浪',
    'Lion City Sailors': '狮城水手',
    'Tanjong Pagar United': '丹戎巴葛',
    'Hougang United': '后港联',

    # 印度超
    'ATK Mohun Bagan': 'ATK莫亨巴根',
    'East Bengal': '东孟加拉',
    'Kerala Blasters': '喀拉拉邦',
    'FC Goa': '果阿',

    # 芬兰
    'FC Lahti': '拉赫蒂',
    'VPS Vaasa': '瓦萨',
    'FC Haka': '哈卡',
    'KTP Kotka': '克鲁比04',
    'IFK Ekenas': '埃克纳斯',
    'SJK Academy': 'SJK学院',
    'Kapa': '卡帕',
    'PK-35 Vantaa': 'Pk-35万塔',
    'MP Mikkeli': 'MP 米克力',
    'KTP': '吉波',

    # 瑞典甲
    'Ostersunds FK': '厄斯特松德',
    'IFK Sandviken': '桑德维肯斯',
    'Osters IF': '厄斯特什',
    'Jonkopings Sodra': '永斯基',
    'Motala AIF': '慕达拉',
    'Falkenbergs FF': '法尔肯堡',
    'IFK Varnamo': '韦纳穆',
    'IFK Norby': '诺尔比',
    'GIF Sundsvall': '松兹瓦尔',
    'Landskrona BoIS': '兰斯克鲁纳',
    'Orebro SK': '厄勒布鲁',
    'Avedo AIK': '奥迪沃特',

    # 安道超
    'CE Escaldes': '艾斯卡迪斯',
    'FC Engordany': '佩亚恩卡那达',

    # 西乙
    'Deportivo La Coruna': '拉科',
    'FC Andorra': '安道尔CF',
    'CD Leganes': '莱加内斯',
    'SD Huesca': '韦斯卡',
    'Real Zaragoza': '萨拉戈萨',
    'Sporting Gijon': '希洪竞技',

    # 意乙
    'US Catanzaro': '卡坦萨罗',

    # 沙特联
    'Al Shabab': '利雅青年',

    # 爱超
    'Waterford FC': '沃特福德联队',
    'Drogheda United': '德罗赫达联',

    # 以超
    'Hapoel Shmona': '谢莫夏普尔',
    'FC Ashdod': '阿什杜德',
    'Hapoel Haifa': '海法夏普尔',
    'Bnei Sakhnin': '比尼萨赫宁',
    'Bnei Yehuda': '贝内雷讷马卡比',
    'Maccabi Netanya': '内坦马卡比',
    'Hapoel Jerusalem': '耶路夏普尔',
    'Ironi Tiberias': '伊罗尼太巴列',

    # 芬超
    'FC Lahti': '拉赫蒂',
}

def main():
    # 加载现有映射
    existing_names = load_existing_names()
    print(f'现有映射数量: {len(existing_names)}')

    # 合并新映射
    existing_names.update(NEW_TEAM_NAMES)
    print(f'合并后映射数量: {len(existing_names)}')

    # 保存
    save_names(existing_names)
    print(f'已保存到 {TEAM_NAMES_FILE}')

if __name__ == '__main__':
    main()
