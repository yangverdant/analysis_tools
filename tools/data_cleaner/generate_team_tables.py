"""
生成球队表 - 从清洗后的数据中提取球队信息
"""
import csv
import os
from pathlib import Path
from collections import defaultdict
from datetime import datetime
import sys

if sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')

NEW_DATA_DIR = Path('D:/football_tools/new_data/leagues')
OUTPUT_DIR = Path('D:/football_tools/new_data/teams')

# 联赛中文名映射
LEAGUE_NAMES = {
    'premier_league': '英超',
    'la_liga': '西甲',
    'bundesliga': '德甲',
    'serie_a': '意甲',
    'ligue_1': '法甲',
    'championship': '英冠',
    'league_one': '英甲',
    'league_two': '英乙',
    'eredivisie': '荷甲',
    'primeira_liga': '葡超',
    'segunda_division': '西乙',
    'serie_b': '意乙',
    'ligue_2': '法乙',
    'jupiler_league': '比甲',
    'super_lig': '土超',
    'superleague': '希腊超',
    'bundesliga_2': '德乙',
    'bundesliga_3': '德丙',
    'scotland_premier': '苏超',
    'scotland_div1': '苏甲',
    'scotland_div2': '苏乙',
    'scotland_div3': '苏丙',
    'nb1': '匈甲',
    'gambrinus_liga': '捷甲',
    'super_league_swiss': '瑞士超',
    'swiss_2': '瑞士甲',
    'premier_league_russia': '俄超',
    'russia_2': '俄甲',
    'turkey_2': '土甲',
    'bundesliga_austria': '奥甲',
    'austria_2': '奥乙',
    'allsvenskan': '瑞典超',
    'veikkausliiga': '芬兰超',
}

# 球队中文名映射 (常见球队)
TEAM_CN_NAMES = {
    # 英超
    'Arsenal': '阿森纳',
    'Aston Villa': '阿斯顿维拉',
    'Bournemouth': '伯恩茅斯',
    'Brighton': '布莱顿',
    'Burnley': '伯恩利',
    'Chelsea': '切尔西',
    'Crystal Palace': '水晶宫',
    'Everton': '埃弗顿',
    'Fulham': '富勒姆',
    'Liverpool': '利物浦',
    'Man City': '曼城',
    'Man United': '曼联',
    'Newcastle': '纽卡斯尔',
    'Nottingham Forest': '诺丁汉森林',
    'Sheffield United': '谢菲尔德联',
    'Tottenham': '热刺',
    'West Ham': '西汉姆联',
    'Wolves': '狼队',
    'Birmingham': '伯明翰',
    'Blackburn': '布莱克本',
    'Blackpool': '布莱克浦',
    'Bolton': '博尔顿',
    'Bradford': '布拉德福德',
    'Brentford': '布伦特福德',
    'Cardiff': '加的夫城',
    'Charlton': '查尔顿',
    'Coventry': '考文垂',
    'Derby': '德比郡',
    'Huddersfield': '哈德斯菲尔德',
    'Hull': '赫尔城',
    'Ipswich': '伊普斯维奇',
    'Leeds': '利兹联',
    'Leicester': '莱斯特城',
    'Luton': '卢顿',
    'Middlesbrough': '米德尔斯堡',
    'Norwich': '诺维奇',
    'Portsmouth': '朴茨茅斯',
    'QPR': '女王公园巡游者',
    'Reading': '雷丁',
    'Southampton': '南安普顿',
    'Stoke': '斯托克城',
    'Sunderland': '桑德兰',
    'Swansea': '斯旺西',
    'Watford': '沃特福德',
    'Wigan': '维冈竞技',
    'West Brom': '西布朗',
    'Nottm Forest': '诺丁汉森林',
    "Nott'm Forest": '诺丁汉森林',
    'Tottenham Hotspur': '热刺',
    'Manchester City': '曼城',
    'Manchester United': '曼联',
    'Newcastle United': '纽卡斯尔',

    # 西甲
    'Ath Bilbao': '毕尔巴鄂竞技',
    'Athletic Bilbao': '毕尔巴鄂竞技',
    'Ath Madrid': '马德里竞技',
    'Atletico Madrid': '马德里竞技',
    'Alaves': '阿拉维斯',
    'Almeria': '阿尔梅里亚',
    'Barcelona': '巴塞罗那',
    'Betis': '皇家贝蒂斯',
    'Real Betis': '皇家贝蒂斯',
    'Cadiz': '加的斯',
    'Celta': '塞尔塔',
    'Celta Vigo': '塞尔塔',
    'Eibar': '埃瓦尔',
    'Elche': '埃尔切',
    'Espanol': '西班牙人',
    'Espanyol': '西班牙人',
    'Getafe': '赫塔费',
    'Girona': '赫罗纳',
    'Granada': '格拉纳达',
    'Huesca': '韦斯卡',
    'Las Palmas': '拉斯帕尔马斯',
    'Leganes': '莱加内斯',
    'Levante': '莱万特',
    'Mallorca': '马洛卡',
    'Osasuna': '奥萨苏纳',
    'Racing': '桑坦德竞技',
    'Santander': '桑坦德竞技',
    'Rayo Vallecano': '巴列卡诺',
    'Vallecano': '巴列卡诺',
    'Real Madrid': '皇家马德里',
    'Real Sociedad': '皇家社会',
    'Sevilla': '塞维利亚',
    'Sociedad': '皇家社会',
    'Sp Gijon': '希洪竞技',
    'Tenerife': '特内里费',
    'Valencia': '瓦伦西亚',
    'Valladolid': '巴利亚多利德',
    'Villarreal': '比利亚雷亚尔',
    'Xerez': '赫雷斯',
    'Albacete': '阿尔巴塞特',
    'Numancia': '努曼西亚',
    'Recreativo': '维尔瓦',
    'Dep La Coruna': '拉科鲁尼亚',
    'La Coruna': '拉科鲁尼亚',
    'Malaga': '马拉加',
    'Vigo': '维戈塞尔塔',
    'Cordoba': '科尔多瓦',
    'Gimnastic': '塔拉戈纳体操',
    'Hercules': '大力神',
    'Murcia': '穆尔西亚',
    'Oviedo': '奥维耶多',
    'Zaragoza': '萨拉戈萨',

    # 德甲
    'Augsburg': '奥格斯堡',
    'Bayern Munich': '拜仁慕尼黑',
    'Bayern': '拜仁慕尼黑',
    'Bochum': '波鸿',
    'Darmstadt': '达姆施塔特',
    'Dortmund': '多特蒙德',
    'Dresden': '德累斯顿',
    'Dusseldorf': '杜塞尔多夫',
    'Fortuna Dusseldorf': '杜塞尔多夫',
    'Ein Frankfurt': '法兰克福',
    'Frankfurt': '法兰克福',
    'Freiburg': '弗赖堡',
    'Greuther Furth': '菲尔特',
    'Hamburg': '汉堡',
    'Hamburger SV': '汉堡',
    'Hannover': '汉诺威96',
    'Hannover 96': '汉诺威96',
    'Heidenheim': '海登海姆',
    'Hertha': '柏林赫塔',
    'Hoffenheim': '霍芬海姆',
    'Kaiserslautern': '凯泽斯劳滕',
    'Koln': '科隆',
    'FC Koln': '科隆',
    'Leverkusen': '勒沃库森',
    "M'gladbach": '门兴格拉德巴赫',
    'Monchengladbach': '门兴格拉德巴赫',
    'B. Monchengladbach': '门兴格拉德巴赫',
    'Mainz': '美因茨',
    'Nurnberg': '纽伦堡',
    'Paderborn': '帕德博恩',
    'RB Leipzig': '莱比锡红牛',
    'RB莱比锡': '莱比锡红牛',
    'Schalke 04': '沙尔克04',
    'Schalke': '沙尔克04',
    'Stuttgart': '斯图加特',
    'Union Berlin': '柏林联合',
    'Werder Bremen': '云达不来梅',
    'Bremen': '云达不来梅',
    '不来梅': '云达不来梅',
    'Wolfsburg': '沃尔夫斯堡',
    'Bielefeld': '比勒费尔德',
    'Cottbus': '科特布斯',
    'Karlsruhe': '卡尔斯鲁厄',
    'Rostock': '罗斯托克',
    'Hansa Rostock': '罗斯托克',
    'Unterhaching': '翁特哈兴',
    'Aachen': '亚琛',
    'Duisburg': '杜伊斯堡',
    'Munich 1860': '慕尼黑1860',
    'Eintracht Frankfurt': '法兰克福',
    'Holstein Kiel': '基尔',
    'St Pauli': '圣保利',
    'St. Pauli': '圣保利',
    'Ingolstadt': '因戈尔施塔特',
    'Braunschweig': '布伦瑞克',

    # 意甲
    'Atalanta': '亚特兰大',
    'Bari': '巴里',
    'Bologna': '博洛尼亚',
    'Brescia': '布雷西亚',
    'Cagliari': '卡利亚里',
    'Catania': '卡塔尼亚',
    'Catanzaro': '卡坦扎罗',
    'Chievo': '切沃',
    'Como': '科莫',
    'Cremonese': '克雷莫内塞',
    'Crotone': '克罗托内',
    'Empoli': '恩波利',
    'Fiorentina': '佛罗伦萨',
    'Frosinone': '弗罗西诺内',
    'Genoa': '热那亚',
    'Hellas Verona': '维罗纳',
    'Inter': '国际米兰',
    'Inter Milan': '国际米兰',
    'Juventus': '尤文图斯',
    'Lazio': '拉齐奥',
    'Lecce': '莱切',
    'Livorno': '利沃诺',
    'Messina': '梅西纳',
    'Milan': 'AC米兰',
    'AC Milan': 'AC米兰',
    'Modena': '摩德纳',
    'Monza': '蒙扎',
    'Napoli': '那不勒斯',
    'Palermo': '巴勒莫',
    'Parma': '帕尔马',
    'Pescara': '佩斯卡拉',
    'Piacenza': '皮亚琴察',
    'Reggina': '雷吉纳',
    'Reggiana': '雷吉亚纳',
    'Roma': '罗马',
    'Salernitana': '萨勒尼塔纳',
    'Sampdoria': '桑普多利亚',
    'Sassuolo': '萨索洛',
    'Siena': '锡耶纳',
    'Spezia': '斯佩齐亚',
    'Torino': '都灵',
    'Trento': '特伦托',
    'Treviso': '特雷维索',
    'Udinese': '乌迪内斯',
    'Venezia': '威尼斯',
    'Vicenza': '维琴察',
    'Verona': '维罗纳',
    'Ascoli': '阿斯科利',
    'Perugia': '佩鲁贾',
    'Ancona': '安科纳',
    'Avellino': '阿韦利诺',
    'Benevento': '贝内文托',
    'Carpi': '卡尔皮',
    'Foggia': '福贾',
    'Novara': '诺瓦拉',
    'Portogruaro': '波尔托格鲁阿罗',
    'Ravenna': '拉文纳',
    'Sudtirol': '南蒂罗尔',
    'Triestina': '的里雅斯特',
    'Cesena': '切塞纳',
    'Pisa': '比萨',
    'Spal': '斯帕尔',

    # 法甲
    'Ajaccio': '阿雅克肖',
    'Ajaccio GFCO': '阿雅克肖GFCO',
    'Amiens': '亚眠',
    'Angers': '昂热',
    'Auxerre': '欧塞尔',
    'Bastia': '巴斯蒂亚',
    'Bordeaux': '波尔多',
    'Boulogne': '布洛涅',
    'Brest': '布雷斯特',
    'Caen': '卡昂',
    'Clermont': '克莱蒙',
    'Dijon': '第戎',
    'Dunkerque': '敦刻尔克',
    'Evian Thonon Gaillard': '依云',
    'Grenoble': '格勒诺布尔',
    'Guingamp': '甘冈',
    'Istres': '伊斯特尔',
    'Le Havre': '勒阿弗尔',
    'Le Mans': '勒芒',
    'Lens': '朗斯',
    'Lille': '里尔',
    'Lorient': '洛里昂',
    'Lyon': '里昂',
    'Marseille': '马赛',
    'Metz': '梅斯',
    'Monaco': '摩纳哥',
    'Montpellier': '蒙彼利埃',
    'Nancy': '南锡',
    'Nantes': '南特',
    'Nice': '尼斯',
    'Nimes': '尼姆',
    'Paris SG': '巴黎圣日耳曼',
    'PSG': '巴黎圣日耳曼',
    'Reims': '兰斯',
    'Rennes': '雷恩',
    'Rodez': '罗德兹',
    'Saint Etienne': '圣埃蒂安',
    'St Etienne': '圣埃蒂安',
    'Saint-Etienne': '圣埃蒂安',
    'Sochaux': '索肖',
    'Strasbourg': '斯特拉斯堡',
    'Toulouse': '图卢兹',
    'Troyes': '特鲁瓦',
    'Valenciennes': '瓦朗谢讷',
    'Tours': '图尔',
    'Sedan': '色当',
    'Chateauroux': '沙托鲁',
    'Niort': '尼奥尔',
    'Quevilly': '克维伊',
    'Pau': '波城',
    'Paris FC': '巴黎FC',
    'Vannes': '瓦讷',
    'Arles': '阿尔勒',
    'Evian': '依云',
}


def extract_teams():
    """从清洗后的数据中提取球队信息"""
    teams_by_league = defaultdict(lambda: defaultdict(set))  # league -> season -> teams

    for league_dir in NEW_DATA_DIR.iterdir():
        if not league_dir.is_dir():
            continue

        league = league_dir.name
        if league not in LEAGUE_NAMES:
            continue

        for csv_file in league_dir.glob('*.csv'):
            season = csv_file.stem.split('_')[-1]

            with open(csv_file, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    home_team = row.get('home_team', '').strip()
                    away_team = row.get('away_team', '').strip()

                    # 过滤空值和 null
                    if home_team and home_team != 'null':
                        teams_by_league[league][season].add(home_team)
                    if away_team and away_team != 'null':
                        teams_by_league[league][season].add(away_team)

    return teams_by_league


def generate_team_tables(teams_by_league):
    """生成球队表"""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    for league, seasons in teams_by_league.items():
        league_cn = LEAGUE_NAMES.get(league, league)

        # 收集所有球队及其首次出现的赛季
        team_info = {}  # team_name -> {first_season, last_season, seasons}

        for season, teams in sorted(seasons.items()):
            for team in teams:
                if team not in team_info:
                    team_info[team] = {
                        'first_season': season,
                        'last_season': season,
                        'seasons': [season]
                    }
                else:
                    team_info[team]['last_season'] = season
                    team_info[team]['seasons'].append(season)

        # 写入球队表
        output_file = OUTPUT_DIR / f'{league}_teams.csv'

        with open(output_file, 'w', encoding='utf-8', newline='') as f:
            writer = csv.writer(f)
            # 只输出5个字段: 赛季, 联赛英文名, 联赛中文名, 英文球队名, 中文球队名
            writer.writerow(['赛季', '联赛英文名', '联赛中文名', '英文球队名', '中文球队名'])

            for team_name in sorted(team_info.keys()):
                info = team_info[team_name]
                cn_name = TEAM_CN_NAMES.get(team_name, '')

                # 为每个赛季写一行
                for season in sorted(set(info['seasons'])):
                    writer.writerow([
                        season,
                        league,
                        league_cn,
                        team_name,
                        cn_name
                    ])

        print(f'{league_cn} ({league}): {len(team_info)} 支球队 -> {output_file.name}')

    # 生成合并表
    all_teams_file = OUTPUT_DIR / 'all_teams.csv'

    with open(all_teams_file, 'w', encoding='utf-8', newline='') as f:
        writer = csv.writer(f)
        # 只输出5个字段: 赛季, 联赛英文名, 联赛中文名, 英文球队名, 中文球队名
        writer.writerow(['赛季', '联赛英文名', '联赛中文名', '英文球队名', '中文球队名'])

        for league in sorted(LEAGUE_NAMES.keys()):
            if league not in teams_by_league:
                continue

            league_cn = LEAGUE_NAMES[league]
            seasons = teams_by_league[league]

            # 收集每个赛季的球队
            for season in sorted(seasons.keys()):
                teams = seasons[season]
                for team_name in sorted(teams):
                    cn_name = TEAM_CN_NAMES.get(team_name, '')
                    writer.writerow([
                        season,
                        league,
                        league_cn,
                        team_name,
                        cn_name
                    ])

    print(f'\n合并球队表: {all_teams_file.name}')


def main():
    print("=" * 60)
    print("生成球队表")
    print("=" * 60)

    teams_by_league = extract_teams()

    print(f"\n从清洗数据中提取球队信息...")
    print(f"联赛数: {len(teams_by_league)}")

    for league in LEAGUE_NAMES:
        if league in teams_by_league:
            all_teams = set()
            for season_teams in teams_by_league[league].values():
                all_teams.update(season_teams)
            print(f"  {LEAGUE_NAMES[league]}: {len(all_teams)} 支球队")

    print(f"\n生成球队表...")
    generate_team_tables(teams_by_league)

    print("\n" + "=" * 60)
    print("完成!")
    print("=" * 60)


if __name__ == '__main__':
    main()