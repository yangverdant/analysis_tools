"""
生成亚洲联赛球队统计文件
"""
import csv
from pathlib import Path
from collections import defaultdict

# J1联赛球队中文名映射
J1_LEAGUE_CN = {
    'Kashima Antlers': '鹿岛鹿角',
    'Yokohama F. Marinos': '横滨水手',
    'Urawa Red Diamonds': '浦和红钻',
    'Urawa Reds': '浦和红钻',
    'Kawasaki Frontale': '川崎前锋',
    'Gamba Osaka': '大阪钢巴',
    'Nagoya Grampus': '名古屋鲸鱼',
    'Nagoya Grampus Eight': '名古屋鲸八',
    'FC Tokyo': 'FC东京',
    'Shimizu S-Pulse': '清水心跳',
    'Jubilo Iwata': '磐田喜悦',
    'Júbilo Iwata': '磐田喜悦',
    '磐田山葉': '磐田喜悦',
    'Cerezo Osaka': '大阪樱花',
    'Sanfrecce Hiroshima': '广岛三箭',
    'Vissel Kobe': '神户胜利船',
    'Sagan Tosu': '鸟栖砂岩',
    '鳥棲砂岩': '鸟栖砂岩',
    'Kashiwa Reysol': '柏太阳神',
    'Oita Trinita': '大分三神',
    'Shonan Bellmare': '湘南比马',
    'Ventforet Kofu': '甲府风林',
    'Yokohama FC': '横滨FC',
    'FC橫濱': '横滨FC',
    'Avispa Fukuoka': '福冈黄蜂',
    'Hokkaido Consadole Sapporo': '札幌冈萨多',
    'Consadole Sapporo': '札幌冈萨多',
    'Vegalta Sendai': '仙台维加泰',
    'Matsumoto Yamaga': '松本山雅',
    'Albirex Niigata': '新泻天鹅',
    'Tokyo Verdy': '东京绿茵',
    'JEF United Chiba': '杰夫联千叶',
    'Omiya Ardija': '大宫松鼠',
    'Yamagata Montedio': '山形山神',
    'Montedio Yamagata': '山形山神',
    'Kyoto Sanga': '京都桑加',
    'FC Machida Zelvia': '町田泽维亚',
    'Tokushima Vortis': '德岛漩涡',
    'Fagiano Okayama': '冈山雉鸡',
    'Mito HollyHock': '水户蜀葵',
}

# J2联赛球队中文名映射
J2_LEAGUE_CN = {
    'JEF United Chiba': '杰夫联千叶',
    'Ventforet Kofu': '甲府风林',
    'Omiya Ardija': '大宫松鼠',
    'Yamagata Montedio': '山形山神',
    'Montedio Yamagata': '山形山神',
    'V-Varen Nagasaki': '长崎成功丸',
    'Avispa Fukuoka': '福冈黄蜂',
    'Oita Trinita': '大分三神',
    'Matsumoto Yamaga': '松本山雅',
    'Albirex Niigata': '新泻天鹅',
    'Tokushima Vortis': '德岛漩涡',
    'Roasso Kumamoto': '熊本深红',
    'Zweigen Kanazawa': '金泽共进',
    'Renofa Yamaguchi': '雷法山口',
    'Mito HollyHock': '水户蜀葵',
    'Tochigi SC': '枥木SC',
    'Thespa Kusatsu': '草津温泉',
    'Thespakusatsu Gunma': '草津温泉群马',
    'Ehime FC': '爱媛FC',
    'Fagiano Okayama': '冈山雉鸡',
    'Kataller Toyama': '卡塔勒富山',
    'Giravanz Kitakyushu': '北九州向日葵',
    'Blaublitz Akita': '秋田蓝色闪电',
    'FC Ryukyu': '琉球FC',
    'Kagoshima United': '鹿儿岛联',
    'FC Gifu': 'FC岐阜',
    'Tokyo Verdy': '东京绿茵',
    'Yokohama FC': '横滨FC',
    'Kyoto Sanga': '京都桑加',
    'Nagasaki': '长崎成功丸',
    'Kumamoto': '熊本深红',
    'Okayama': '冈山雉鸡',
    'Akita': '秋田蓝色闪电',
    'Kanazawa': '金泽共进',
    'Yamaguchi': '雷法山口',
    'Mito': '水户蜀葵',
    'Tochigi': '枥木SC',
    'Ehime': '爱媛FC',
    'Toyama': '卡塔勒富山',
    'Kitakyushu': '北九州向日葵',
    'Kofu': '甲府风林',
    'Chiba': '杰夫联千叶',
    'Kusatsu': '草津温泉',
    'Ryukyu': '琉球FC',
    'Gifu': 'FC岐阜',
    'Kagoshima': '鹿儿岛联',
    'Hachinohe': '八户云罗里',
    'Iwaki': '岩城',
    'Iwaki FC': '岩城FC',
    'FC大阪': '大阪FC',
    '大阪FC': '大阪FC',
    'Nara Club': '奈良俱乐部',
    'SP Kyoto': 'SP京都',
    'Reilac Shiga': '雷拉克滋贺',
    'Honda Lock': '本田洛克',
    'Honda FC': '本田FC',
    'Cerezo Osaka': '大阪樱花',
    'Consadole Sapporo': '札幌冈萨多',
    'FC Tokyo': 'FC东京',
    'Gamba Osaka': '大阪钢巴',
    'Kashiwa Reysol': '柏太阳神',
    'Sanfrecce Hiroshima': '广岛三箭',
    'Shonan Bellmare': '湘南比马',
    'Sagan Tosu': '鸟栖砂岩',
    'Vissel Kobe': '神户胜利船',
    'Kashima Antlers': '鹿岛鹿角',
    'Kawasaki Frontale': '川崎前锋',
    'Nagoya Grampus': '名古屋鲸鱼',
    'Shimizu S-Pulse': '清水心跳',
    'Júbilo Iwata': '磐田喜悦',
    'Jubilo Iwata': '磐田喜悦',
    '磐田山葉': '磐田喜悦',
    '鳥棲砂岩': '鸟栖砂岩',
    'Vegalta Sendai': '仙台维加泰',
    'FC岐阜': 'FC岐阜',
    'FC今治': 'FC今治',
    'FC琉球': '琉球FC',
    '秋田蓝色闪电': '秋田蓝色闪电',
    '山形山神': '山形山神',
    '水戸蜀葵': '水户蜀葵',
    '栃木SC': '枥木SC',
    '群馬草津温泉': '草津温泉群马',
    '大分三神': '大分三神',
    '徳島漩渦': '德岛漩涡',
    '長崎成功丸': '长崎成功丸',
    '熊本深紅': '熊本深红',
    '愛媛FC': '爱媛FC',
    '讚岐高松': '赞岐高松',
    '宮崎棒牛': '宫崎棒牛',
    '沖繩FC': '冲绳FC',
    '北海道札幌岡薩多': '札幌冈萨多',
    'FC橫濱': '横滨FC',
    'FC愛媛': '爱媛FC',
    '熊本羅亞素': '熊本深红',
    '富山勝利': '卡塔勒富山',
    '岡山綠雉': '冈山雉鸡',
    '櫪木葡萄': '枥木SC',
    '鳥取飛翔': '鸟取飞翔',
    '讚岐卡馬達馬尼': '赞岐卡马达马尼',
    '長野帕塞羅': '长野帕塞罗',
    '町田澤維亞': '町田泽维亚',
}

# K1联赛球队中文名映射
K1_LEAGUE_CN = {
    'Jeonbuk Hyundai Motors': '全北现代',
    'Jeonbuk Hyundai': '全北现代',
    'Ulsan Hyundai': '蔚山现代',
    'Pohang Steelers': '浦项制铁',
    'Seoul FC': '首尔FC',
    'FC Seoul': '首尔FC',
    'Suwon Samsung Bluewings': '水原三星',
    'Incheon United': '仁川联',
    'Daegu FC': '大邱FC',
    'Jeju United': '济州联',
    'Gwangju FC': '光州FC',
    'Sangju Sangmu': '尚州尚武',
    'Gimcheon Sangmu': '金泉尚武',
    'Gangwon FC': '江原FC',
    'Seongnam FC': '城南FC',
    'Busan IPark': '釜山IPark',
    'Suwon FC': '水原FC',
    'Chuncheon': '春川',
    'Jeonnam Dragons': '全南天龙',
    'Anyang': '安阳',
    'Anyang FC': '安阳FC',
    'Gyeongnam': '庆南',
    'Changwon': '昌原',
    'Mokpo': '木浦',
    'Daejeon Citizen': '大田市民',
    'Daejeon Hana Citizen': '大田韩亚市民',
    'Bucheon FC': '富川FC',
    'Bucheon FC 1995': '富川FC1995',
}

# K2联赛球队中文名映射
K2_LEAGUE_CN = {
    'Ansan Greeners': '安山小绿人',
    'Asan Mugunghwa': '牙山木槿花',
    'Chungbuk Cheongju': '忠北清州',
    'Daejeon Citizen': '大田市民',
    'Gangwon FC': '江原FC',
    'Gyeongnam FC': '庆南FC',
    'Jeonnam Dragons': '全南天龙',
    'Pyeongtaek FC': '平泽FC',
    'Seoul E-Land': '首尔衣恋',
    'Suwon FC': '水原FC',
    'Busan IPark': '釜山IPark',
    'Anyang FC': '安阳FC',
    'Chungju': '忠州',
    'Gimpo': '金浦',
    'Hwaseong': '华城',
    'Yangju': '杨州',
    'Yangpyeong': '杨平',
}

# 澳超球队中文名映射
A_LEAGUE_CN = {
    'Sydney FC': '悉尼FC',
    'Melbourne Victory': '墨尔本胜利',
    'Melbourne City': '墨尔本城',
    'Melbourne City FC': '墨尔本城',
    'Adelaide United': '阿德莱德联',
    'Western Sydney Wanderers': '西悉尼流浪者',
    'Perth Glory': '珀斯光荣',
    'Wellington Phoenix': '惠灵顿凤凰',
    'Central Coast Mariners': '中央海岸水手',
    'Brisbane Roar': '布里斯班狮吼',
    'Newcastle Jets': '纽卡斯尔喷气机',
    'Newcastle United Jets': '纽卡斯尔喷气机',
    'Western United': '西部联',
    'Macarthur FC': '麦克阿瑟FC',
    'Gold Coast United': '黄金海岸联',
    'North Queensland Fury': '北昆士兰狂怒',
    'Auckland FC': '奥克兰FC',
    'N.N.': '未知',
    'Sieger EF': '西格EF',
}

# 中超球队中文名映射
CSL_CN = {
    'Shanghai Port': '上海海港',
    'Shanghai Port FC': '上海海港',
    'Shanghai SIPG': '上海上港',
    'Shanghai Shenhua': '上海申花',
    'Shandong Taishan': '山东泰山',
    'Shandong Luneng': '山东鲁能',
    'Beijing Guoan': '北京国安',
    'Guangzhou FC': '广州队',
    'Guangzhou Evergrande': '广州恒大',
    'Guangzhou Evergrande Taobao': '广州恒大淘宝',
    'Jiangsu Suning': '江苏苏宁',
    'Jiangsu苏宁': '江苏苏宁',
    'Tianjin Jinmen Tiger': '天津津门虎',
    'Tianjin TEDA': '天津泰达',
    'Tianjin Teda': '天津泰达',
    'Tianjin Tianhai': '天津天海',
    'Henan FC': '河南FC',
    'Henan Jianye': '河南建业',
    'Wuhan Three Towns': '武汉三镇',
    'Wuhan Zall FC': '武汉卓尔',
    'Chengdu Better City': '成都蓉城',
    'Chengdu Rongcheng': '成都蓉城',
    'Zhejiang FC': '浙江队',
    'Zhejiang': '浙江队',
    'Zhejiang Professional': '浙江职业',
    'Changchun Yatai': '长春亚泰',
    'Shenzhen FC': '深圳队',
    'Shenzhen Peng City': '深圳鹏城',
    'Dalian Pro': '大连人',
    'Dalian Aerbin': '大连阿尔滨',
    'Dalian Yifang FC': '大连一方',
    'Dalian Yingbo': '大连英博',
    'Qingdao Hainiu': '青岛海牛',
    'Qingdao FC': '青岛队',
    'Qingdao Huanghai': '青岛黄海',
    'Qingdao West Coast': '青岛西海岸',
    'Nantong Zhiyun': '南通支云',
    'Cangzhou Mighty Lions': '沧州雄狮',
    'Meizhou Hakka': '梅州客家',
    'Hebei FC': '河北队',
    'Hebei China Fortune': '华夏幸福',
    'Chongqing Liangjiang': '重庆两江竞技',
    'Chongqing Lifan': '重庆力帆',
    'Wuhan FC': '武汉队',
    'Guangzhou City': '广州城',
    'Guangzhou R&F': '广州富力',
    'Beijing Renhe FC': '北京人和',
    'Guizhou Hengfeng': '贵州恒丰',
    'Shanghai Shenxin': '上海申鑫',
    'Liaoning Tieren': '辽宁铁人',
    'Liaoning Whowin': '辽足',
    'Yunnan Yukun': '云南玉昆',
    'Shijiazhuang Ever Bright': '石家庄永昌',
    'Tianjin Quanjian': '天津权健',
    'Yanbian Funde': '延边富德',
    'Jiangsu苏宁': '江苏苏宁',
    'Jiāngsū Sūnìng': '江苏苏宁',
    'Jiāngsū Sūníng': '江苏苏宁',
}

# 沙特超球队中文名映射
SAUDI_PRO_CN = {
    'Al-Hilal': '利雅得新月',
    'Al-Nassr': '利雅得胜利',
    'Al-Ittihad': '吉达联合',
    'Al-Ahli': '吉达国民',
    'Al-Shabab': '利雅得青年',
    'Al-Fayha': '费哈',
    'Al-Taawoun': '塔伊夫',
    'Al-Taawon': '塔伊夫',
    'Al-Raed': '拉艾德',
    'Al-Fateh': '法特赫',
    'Al-Khaleej': '卡利杰',
    'Damac': '达马克',
    'Al-Hazm': '哈兹姆',
    'Al-Riyadh': '利雅得',
    'Al-Okhdood': '奥赫杜德',
    'Al-Wehda': '麦加团结',
    'Al-Qadsiah': '卡迪西亚',
    'Al-Batin': '巴廷',
    'Al-Faisaly': '费萨利',
    'Najran': '纳季兰',
    'Al-Tai': '塔伊',
    'Al-Ettifaq': '伊蒂法克',
    'Neom': '新未来城',
    'Al-Khaleej': '卡利杰',
}

# 亚冠球队中文名映射
AFC_CHAMPIONS_LEAGUE_CN = {
    'Ulsan Hyundai': '蔚山现代',
    'Pohang Steelers': '浦项制铁',
    'Jeonbuk Hyundai Motors': '全北现代',
    'Daegu FC': '大邱FC',
    'Daegu FC': '大邱FC',
    'Suwon Samsung Bluewings': '水原三星',
    'Seoul FC': '首尔FC',
    'Incheon United': '仁川联',
    'Gwangju FC': '光州FC',
    'Yokohama F. Marinos': '横滨水手',
    'Kawasaki Frontale': '川崎前锋',
    'Urawa Red Diamonds': '浦和红钻',
    'Vissel Kobe': '神户胜利船',
    'Sanfrecce Hiroshima': '广岛三箭',
    'Kashima Antlers': '鹿岛鹿角',
    'Gamba Osaka': '大阪钢巴',
    'Cerezo Osaka': '大阪樱花',
    'FC Tokyo': 'FC东京',
    'Nagoya Grampus': '名古屋鲸鱼',
    'Shandong Taishan': '山东泰山',
    'Shanghai Port': '上海海港',
    'Shanghai Shenhua': '上海申花',
    'Beijing Guoan': '北京国安',
    'Guangzhou FC': '广州队',
    'Zhejiang FC': '浙江队',
    'Wuhan Three Towns': '武汉三镇',
    'Al-Hilal': '利雅得新月',
    'Al-Nassr': '利雅得胜利',
    'Al-Ittihad': '吉达联合',
    'Al-Ahli': '吉达国民',
    'Al-Fayha': '费哈',
    'Al-Shabab': '利雅得青年',
    'Al-Rayyan': '赖扬',
    'Al-Sadd': '萨德',
    'Al-Duhail': '杜海勒',
    'Al-Wakrah': '沃克拉',
    'Persepolis': '波斯波利斯',
    'Esteghlal': '埃斯特格拉尔',
    'Sepahan': '塞帕汉',
    'Tractor': '拖拉机',
    'Al-Wahda': '阿布扎比统一',
    'Al-Ain': '艾因',
    'Al-Jazira': '贾兹拉',
    'Shabab Al-Ahli': '迪拜青年国民',
    'Al-Hilal Omdurman': '恩图曼新月',
    'Pakhtakor': '帕克塔科',
    'Lokomotiv Tashkent': '塔什干火车头',
    'Nasaf': '纳萨夫',
    'AGMK': 'AGMK',
    'Al-Quwa Al-Jawiya': '空军俱乐部',
    'Al-Zawraa': '祖拉',
    'Al-Shorta': '警察',
    'Persebaya Surabaya': '泗水帕尔斯巴亚',
    'Persib Bandung': '万隆',
    'Bali United': '巴厘联',
    'PSM Makassar': '望加锡',
    'Buriram United': '武里南联',
    'Bangkok United': '曼谷联',
    'Chiangrai United': '清莱联',
    'Pathum United': '巴吞联',
    'Melbourne Victory': '墨尔本胜利',
    'Sydney FC': '悉尼FC',
    'Central Coast Mariners': '中央海岸水手',
    'Wellington Phoenix': '惠灵顿凤凰',
    'Jeonnam Dragons': '全南天龙',
    'Gangwon FC': '江原FC',
    'Suwon FC': '水原FC',
    'Sagan Tosu': '鸟栖砂岩',
    'Avispa Fukuoka': '福冈黄蜂',
    'Kyoto Sanga': '京都桑加',
    'Yokohama FC': '横滨FC',
    'Jubilo Iwata': '磐田喜悦',
    'Shonan Bellmare': '湘南比马',
    'Hokkaido Consadole Sapporo': '札幌冈萨多',
    'Vegalta Sendai': '仙台维加泰',
    'Oita Trinita': '大分三神',
    'Matsumoto Yamaga': '松本山雅',
    'Albirex Niigata': '新泻天鹅',
    'Tokushima Vortis': '德岛漩涡',
    'Ventforet Kofu': '甲府风林',
    'JEF United Chiba': '杰夫联千叶',
    'Omiya Ardija': '大宫松鼠',
    'Yamagata Montedio': '山形山神',
}

def extract_teams(league_path, league_en):
    """从CSV文件中提取球队和赛季信息"""
    teams_by_season = defaultdict(set)
    path = Path(league_path)

    if not path.exists():
        return teams_by_season

    for csv_file in sorted(path.glob('*.csv')):
        season = csv_file.stem.replace(league_en + '_', '').replace(league_en + '-', '')

        with open(csv_file, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                home = row.get('home_team', '')
                away = row.get('away_team', '')
                if home and home != 'null':
                    teams_by_season[season].add(home)
                if away and away != 'null':
                    teams_by_season[season].add(away)

    return teams_by_season

def write_teams_file(output_path, teams_by_season, league_en, league_cn, team_cn_map):
    """写入球队统计文件"""
    rows = []
    for season in sorted(teams_by_season.keys()):
        for team in sorted(teams_by_season[season]):
            cn_name = team_cn_map.get(team, '')
            rows.append({
                'season': season,
                'league_en': league_en,
                'league_cn': league_cn,
                'team_en': team,
                'team_cn': cn_name
            })

    with open(output_path, 'w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=['season', 'league_en', 'league_cn', 'team_en', 'team_cn'])
        writer.writeheader()
        writer.writerows(rows)

    return len(rows), len(set([r['team_en'] for r in rows]))

if __name__ == '__main__':
    output_dir = Path('D:/football_tools/new_data/teams')
    base_dir = Path('D:/football_tools/new_data/leagues')

    leagues = [
        ('j1_league', 'J1联赛', J1_LEAGUE_CN),
        ('j2_league', 'J2联赛', J2_LEAGUE_CN),
        ('k1_league', 'K1联赛', K1_LEAGUE_CN),
        ('k2_league', 'K2联赛', K2_LEAGUE_CN),
        ('a_league', '澳超', A_LEAGUE_CN),
        ('csl', '中超', CSL_CN),
        ('saudi_pro', '沙特超', SAUDI_PRO_CN),
        ('afc_champions_league', '亚冠', AFC_CHAMPIONS_LEAGUE_CN),
    ]

    print('='*60)
    print('亚洲联赛球队统计')
    print('='*60)

    total_missing = 0
    for league_en, league_cn, team_cn_map in leagues:
        league_path = base_dir / league_en
        teams_by_season = extract_teams(league_path, league_en)

        if teams_by_season:
            output_file = output_dir / f'{league_en}_teams.csv'
            record_count, team_count = write_teams_file(output_file, teams_by_season, league_en, league_cn, team_cn_map)

            # 统计缺失中文名
            all_teams = set()
            for teams in teams_by_season.values():
                all_teams.update(teams)

            missing_cn = [t for t in all_teams if t not in team_cn_map]
            total_missing += len(missing_cn)

            print(f'\n{league_cn} ({league_en}):')
            print(f'  球队数: {team_count}')
            print(f'  记录数: {record_count}')
            print(f'  有中文名: {team_count - len(missing_cn)}')
            print(f'  缺中文名: {len(missing_cn)}')

            if missing_cn:
                print(f'  缺失中文:')
                for t in sorted(missing_cn)[:10]:
                    print(f'    {t}')
                if len(missing_cn) > 10:
                    print(f'    ... 还有{len(missing_cn)-10}个')
        else:
            print(f'\n{league_cn}: 无数据')

    print(f'\n总计缺失中文名: {total_missing}')
