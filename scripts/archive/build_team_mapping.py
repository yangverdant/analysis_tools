#!/usr/bin/env python3
"""
足球数据实体识别与标准化脚本
目标：从所有CSV中提取唯一球队名称，建立标准化映射表
"""

import os
import pandas as pd
import json
import re
from collections import defaultdict
from fuzzywuzzy import fuzz, process
import warnings
warnings.filterwarnings('ignore')

# 数据目录
DATA_DIR = 'd:/football_tools/data'
OUTPUT_DIR = 'd:/football_tools/data/linkage'

# 创建输出目录
os.makedirs(OUTPUT_DIR, exist_ok=True)

def extract_all_team_names():
    """从所有CSV文件中提取球队名称"""
    all_teams = set()
    team_sources = defaultdict(list)

    csv_files = []
    for root, dirs, files in os.walk(DATA_DIR):
        for f in files:
            if f.endswith('.csv'):
                csv_files.append(os.path.join(root, f))

    print(f"找到 {len(csv_files)} 个CSV文件")

    for i, filepath in enumerate(csv_files):
        try:
            df = pd.read_csv(filepath, encoding='utf-8', nrows=100)
        except:
            try:
                df = pd.read_csv(filepath, encoding='latin-1', nrows=100)
            except:
                continue

        # 检查可能的球队列名
        team_columns = ['HomeTeam', 'AwayTeam', 'Home', 'Away',
                       'home_team', 'away_team', 'Team', 'team',
                       'home_team_name', 'away_team_name']

        for col in team_columns:
            if col in df.columns:
                teams = df[col].dropna().unique()
                for team in teams:
                    team_name = str(team).strip()
                    if team_name and team_name not in ['', 'nan', 'NaN']:
                        all_teams.add(team_name)
                        team_sources[team_name].append(os.path.basename(filepath))

        if (i + 1) % 100 == 0:
            print(f"已处理 {i + 1}/{len(csv_files)} 个文件，发现 {len(all_teams)} 个唯一球队名")

    return all_teams, team_sources


def categorize_teams(all_teams):
    """将球队分类为国家队和俱乐部"""
    national_teams = set()
    club_teams = set()

    # 国家队关键词（排除常见的俱乐部名称）
    national_keywords = [
        'U21', 'U20', 'U19', 'U18', 'U17', 'U16',  # 青年队
    ]

    # 已知的国家队名称
    known_national = [
        # 欧洲
        'Germany', 'France', 'Spain', 'England', 'Italy', 'Portugal', 'Netherlands',
        'Belgium', 'Croatia', 'Denmark', 'Sweden', 'Norway', 'Poland', 'Austria',
        'Switzerland', 'Czech Republic', 'Russia', 'Ukraine', 'Turkey', 'Greece',
        'Scotland', 'Wales', 'Ireland', 'Romania', 'Hungary', 'Serbia', 'Slovakia',
        'Slovenia', 'Finland', 'Iceland', 'North Macedonia', 'Montenegro', 'Albania',
        'Bosnia', 'Bulgaria', 'Israel', 'Cyprus', 'Luxembourg', 'Kazakhstan',
        'Azerbaijan', 'Armenia', 'Georgia', 'Belarus', 'Moldova', 'Lithuania',
        'Latvia', 'Estonia', 'Malta', 'Andorra', 'Faroe Islands', 'Gibraltar',
        'San Marino', 'Liechtenstein', 'Kosovo',

        # 南美洲
        'Brazil', 'Argentina', 'Uruguay', 'Colombia', 'Chile', 'Peru', 'Ecuador',
        'Paraguay', 'Venezuela', 'Bolivia',

        # 中北美
        'USA', 'Mexico', 'Canada', 'Costa Rica', 'Panama', 'Jamaica', 'Honduras',
        'El Salvador', 'Trinidad', 'Guatemala', 'Haiti', 'Cuba', 'Nicaragua',

        # 亚洲
        'Japan', 'South Korea', 'Australia', 'Iran', 'Saudi Arabia', 'Qatar',
        'UAE', 'China', 'Uzbekistan', 'Iraq', 'Syria', 'Jordan', 'Oman', 'Bahrain',
        'Kuwait', 'Thailand', 'Vietnam', 'Indonesia', 'Malaysia', 'Philippines',
        'India', 'North Korea', 'Lebanon', 'Palestine', 'Yemen', 'Tajikistan',
        'Kyrgyzstan', 'Myanmar', 'Singapore', 'Hong Kong', 'Chinese Taipei',

        # 非洲
        'Senegal', 'Morocco', 'Tunisia', 'Algeria', 'Egypt', 'Nigeria', 'Cameroon',
        'Ghana', 'Ivory Coast', 'South Africa', 'Mali', 'Congo', 'Guinea', 'Zambia',
        'Angola', 'Kenya', 'Uganda', 'Tanzania', 'Zimbabwe', 'Mozambique', 'Gabon',
        'Burkina Faso', 'Niger', 'Cape Verde', 'Mauritania', 'Libya', 'Sudan',
        'Togo', 'Benin', 'Rwanda', 'Ethiopia', 'Madagascar', 'Comoros',

        # 大洋洲
        'New Zealand', 'Fiji', 'Papua New Guinea', 'Solomon Islands', 'Vanuatu',

        # 历史名称
        'West Germany', 'East Germany', 'USSR', 'Soviet Union', 'Czechoslovakia',
        'Yugoslavia', 'Serbia and Montenegro', 'Germany FR', 'Russia FR',
    ]

    for team in all_teams:
        is_national = False

        # 检查是否在已知国家队列表中
        for national in known_national:
            if national.lower() in team.lower() or team.lower() in national.lower():
                is_national = True
                break

        # 检查是否包含国家队关键词但不是俱乐部
        if not is_national:
            for kw in national_keywords:
                if kw in team:
                    # 检查是否是俱乐部的青年队（如 "Arsenal U21"）
                    club_indicators = ['FC', 'AFC', 'United', 'City', 'Arsenal', 'Chelsea',
                                      'Liverpool', 'Tottenham', 'Real', 'Barcelona', 'Bayern']
                    is_club_youth = any(ind.lower() in team.lower() for ind in club_indicators)
                    if not is_club_youth:
                        is_national = True
                    break

        if is_national:
            national_teams.add(team)
        else:
            club_teams.add(team)

    return national_teams, club_teams


def create_team_mapping(club_teams, national_teams):
    """创建球队名称映射表"""
    mapping = {}

    # 俱乐部映射规则
    club_mappings = {
        # 英格兰
        'Man United': 'Manchester United',
        'Man Utd': 'Manchester United',
        'Manchester Utd': 'Manchester United',
        'Man City': 'Manchester City',
        'Tottenham': 'Tottenham Hotspur',
        'Spurs': 'Tottenham Hotspur',
        'Newcastle': 'Newcastle United',
        'Newcastle Utd': 'Newcastle United',
        'Leicester': 'Leicester City',
        'Brighton': 'Brighton & Hove Albion',
        'Brighton and Hove': 'Brighton & Hove Albion',
        'Wolves': 'Wolverhampton Wanderers',
        'Wolverhampton': 'Wolverhampton Wanderers',
        'West Ham': 'West Ham United',
        'Crystal Palace': 'Crystal Palace',
        'Aston Villa': 'Aston Villa',
        'Leeds': 'Leeds United',
        'Everton': 'Everton',
        'Southampton': 'Southampton',
        'Norwich': 'Norwich City',
        'Watford': 'Watford',
        'Burnley': 'Burnley',
        'Sheffield Utd': 'Sheffield United',
        'Sheffield United': 'Sheffield United',
        'Fulham': 'Fulham',
        'Brentford': 'Brentford',
        'Bournemouth': 'Bournemouth',
        'Nottm Forest': 'Nottingham Forest',
        'Nottingham': 'Nottingham Forest',
        'Luton': 'Luton Town',

        # 德国
        'Bayern Munich': 'Bayern Munich',
        'Bayern Munchen': 'Bayern Munich',
        'Bayern': 'Bayern Munich',
        'Dortmund': 'Borussia Dortmund',
        'Borussia Dortmund': 'Borussia Dortmund',
        'B. Dortmund': 'Borussia Dortmund',
        'Leverkusen': 'Bayer Leverkusen',
        'Bayer 04 Leverkusen': 'Bayer Leverkusen',
        'RB Leipzig': 'RB Leipzig',
        'Leipzig': 'RB Leipzig',
        'Wolfsburg': 'VfL Wolfsburg',
        'Monchengladbach': 'Borussia Monchengladbach',
        "M'gladbach": 'Borussia Monchengladbach',
        'Borussia M.Gladbach': 'Borussia Monchengladbach',
        'Frankfurt': 'Eintracht Frankfurt',
        'Eintracht Frankfurt': 'Eintracht Frankfurt',
        'Freiburg': 'SC Freiburg',
        'Hoffenheim': 'TSG Hoffenheim',
        'Mainz': 'Mainz 05',
        'Union Berlin': 'Union Berlin',
        'Stuttgart': 'VfB Stuttgart',
        'Werder Bremen': 'Werder Bremen',
        'Bremen': 'Werder Bremen',
        'Hertha': 'Hertha Berlin',
        'Hertha Berlin': 'Hertha Berlin',
        'Schalke': 'Schalke 04',
        'Schalke 04': 'Schalke 04',
        'Koln': 'FC Koln',
        'Cologne': 'FC Koln',
        'FC Koln': 'FC Koln',
        'Augsburg': 'FC Augsburg',
        'Bochum': 'VfL Bochum',
        'Darmstadt': 'Darmstadt 98',
        'Heidenheim': 'Heidenheim',

        # 西班牙
        'Real Madrid': 'Real Madrid',
        'Barcelona': 'Barcelona',
        'Barca': 'Barcelona',
        'Atletico Madrid': 'Atletico Madrid',
        'Atletico': 'Atletico Madrid',
        'Sevilla': 'Sevilla',
        'Seville': 'Sevilla',
        'Real Sociedad': 'Real Sociedad',
        'Real Betis': 'Real Betis',
        'Betis': 'Real Betis',
        'Villarreal': 'Villarreal',
        'Athletic': 'Athletic Bilbao',
        'Athletic Bilbao': 'Athletic Bilbao',
        'Valencia': 'Valencia',
        'Getafe': 'Getafe',
        'Celta': 'Celta Vigo',
        'Celta Vigo': 'Celta Vigo',
        'Osasuna': 'Osasuna',
        'Mallorca': 'Mallorca',
        'Rayo Vallecano': 'Rayo Vallecano',
        'Cadiz': 'Cadiz',
        'Alaves': 'Alaves',
        'Girona': 'Girona',
        'Las Palmas': 'Las Palmas',
        'Almeria': 'Almeria',
        'Granada': 'Granada',

        # 意大利
        'Juventus': 'Juventus',
        'Juventus Turin': 'Juventus',
        'Inter': 'Inter Milan',
        'Inter Milan': 'Inter Milan',
        'AC Milan': 'AC Milan',
        'Milan': 'AC Milan',
        'Napoli': 'Napoli',
        'Naples': 'Napoli',
        'Roma': 'Roma',
        'AS Roma': 'Roma',
        'Lazio': 'Lazio',
        'Atalanta': 'Atalanta',
        'Fiorentina': 'Fiorentina',
        'Bologna': 'Bologna',
        'Torino': 'Torino',
        'Turin': 'Torino',
        'Sassuolo': 'Sassuolo',
        'Udinese': 'Udinese',
        'Genoa': 'Genoa',
        'Verona': 'Hellas Verona',
        'Hellas Verona': 'Hellas Verona',
        'Cagliari': 'Cagliari',
        'Lecce': 'Lecce',
        'Empoli': 'Empoli',
        'Monza': 'Monza',
        'Frosinone': 'Frosinone',
        'Salernitana': 'Salernitana',

        # 法国
        'Paris SG': 'Paris Saint-Germain',
        'Paris Saint Germain': 'Paris Saint-Germain',
        'PSG': 'Paris Saint-Germain',
        'Marseille': 'Marseille',
        'Lyon': 'Lyon',
        'Monaco': 'Monaco',
        'Lille': 'Lille',
        'Nice': 'Nice',
        'Rennes': 'Rennes',
        'Lens': 'Lens',
        'Montpellier': 'Montpellier',
        'Nantes': 'Nantes',
        'Strasbourg': 'Strasbourg',
        'Toulouse': 'Toulouse',
        'Bordeaux': 'Bordeaux',
        'Reims': 'Reims',
        'Metz': 'Metz',
        'Le Havre': 'Le Havre',
        'Lorient': 'Lorient',
        'Clermont': 'Clermont',
        'Brest': 'Brest',

        # 荷兰
        'Ajax': 'Ajax',
        'Ajax Amsterdam': 'Ajax',
        'PSV': 'PSV Eindhoven',
        'PSV Eindhoven': 'PSV Eindhoven',
        'Feyenoord': 'Feyenoord',
        'AZ Alkmaar': 'AZ Alkmaar',
        'AZ': 'AZ Alkmaar',
        'Vitesse': 'Vitesse',
        'Twente': 'FC Twente',
        'FC Twente': 'FC Twente',
        'Utrecht': 'FC Utrecht',
        'FC Utrecht': 'FC Utrecht',
        'Groningen': 'FC Groningen',
        'Heerenveen': 'Heerenveen',

        # 葡萄牙
        'Benfica': 'Benfica',
        'Porto': 'Porto',
        'FC Porto': 'Porto',
        'Sporting': 'Sporting Lisbon',
        'Sporting Lisbon': 'Sporting Lisbon',
        'Sporting CP': 'Sporting Lisbon',
        'Braga': 'Braga',

        # 土耳其
        'Galatasaray': 'Galatasaray',
        'Fenerbahce': 'Fenerbahce',
        'Besiktas': 'Besiktas',
        'Trabzonspor': 'Trabzonspor',

        # 苏格兰
        'Celtic': 'Celtic',
        'Rangers': 'Rangers',
        'Aberdeen': 'Aberdeen',
        'Hearts': 'Hearts',
        'Hibernian': 'Hibernian',
        'Dundee Utd': 'Dundee United',
        'Dundee United': 'Dundee United',

        # 希腊
        'Olympiacos': 'Olympiacos',
        'Panathinaikos': 'Panathinaikos',
        'PAOK': 'PAOK',
        'AEK Athens': 'AEK Athens',

        # 比利时
        'Club Brugge': 'Club Brugge',
        'Anderlecht': 'Anderlecht',
        'Genk': 'Genk',
        'Gent': 'Gent',
        'Standard': 'Standard Liege',
        'Standard Liege': 'Standard Liege',

        # 奥地利
        'Salzburg': 'Red Bull Salzburg',
        'Red Bull Salzburg': 'Red Bull Salzburg',
        'RB Salzburg': 'Red Bull Salzburg',
        'Rapid Vienna': 'Rapid Vienna',
        'Austria Vienna': 'Austria Vienna',

        # 瑞士
        'Young Boys': 'Young Boys',
        'Basel': 'Basel',
        'Zurich': 'FC Zurich',

        # 俄罗斯
        'Zenit': 'Zenit St Petersburg',
        'Zenit St Petersburg': 'Zenit St Petersburg',
        'CSKA Moscow': 'CSKA Moscow',
        'Spartak Moscow': 'Spartak Moscow',
        'Lokomotiv Moscow': 'Lokomotiv Moscow',

        # 乌克兰
        'Shakhtar': 'Shakhtar Donetsk',
        'Shakhtar Donetsk': 'Shakhtar Donetsk',
        'Dynamo Kyiv': 'Dynamo Kyiv',
        'Dynamo Kiev': 'Dynamo Kyiv',

        # 巴西
        'Flamengo': 'Flamengo',
        'Palmeiras': 'Palmeiras',
        'Santos': 'Santos',
        'Sao Paulo': 'Sao Paulo',
        'Corinthians': 'Corinthians',
        'Gremio': 'Gremio',
        'Internacional': 'Internacional',
        'Atletico Mineiro': 'Atletico Mineiro',
        'Fluminense': 'Fluminense',
        'Vasco': 'Vasco da Gama',
        'Vasco da Gama': 'Vasco da Gama',
        'Botafogo': 'Botafogo',
        'Cruzeiro': 'Cruzeiro',

        # 阿根廷
        'Boca Juniors': 'Boca Juniors',
        'River Plate': 'River Plate',
        'River': 'River Plate',
        'Racing Club': 'Racing Club',
        'Independiente': 'Independiente',
        'San Lorenzo': 'San Lorenzo',

        # 墨西哥
        'Club America': 'Club America',
        'America': 'Club America',
        'Chivas': 'Guadalajara',
        'Guadalajara': 'Guadalajara',
        'Cruz Azul': 'Cruz Azul',
        'Monterrey': 'Monterrey',
        'Tigres': 'Tigres UANL',
        'Tigres UANL': 'Tigres UANL',

        # 美国
        'LA Galaxy': 'LA Galaxy',
        'Seattle Sounders': 'Seattle Sounders',
        'Atlanta United': 'Atlanta United',
        'NYCFC': 'New York City FC',
        'New York City': 'New York City FC',
        'Toronto FC': 'Toronto FC',
        'LAFC': 'Los Angeles FC',
        'Los Angeles FC': 'Los Angeles FC',
        'Inter Miami': 'Inter Miami',
        'Columbus Crew': 'Columbus Crew',
        'Philadelphia Union': 'Philadelphia Union',
        'New England': 'New England Revolution',
        'Sporting KC': 'Sporting Kansas City',
        'Portland Timbers': 'Portland Timbers',
        'Vancouver Whitecaps': 'Vancouver Whitecaps',
        'Real Salt Lake': 'Real Salt Lake',
        'FC Dallas': 'FC Dallas',
        'Houston Dynamo': 'Houston Dynamo',
        'San Jose Earthquakes': 'San Jose Earthquakes',
        'Colorado Rapids': 'Colorado Rapids',
        'Minnesota United': 'Minnesota United',
        'Orlando City': 'Orlando City',
        'DC United': 'DC United',
        'Chicago Fire': 'Chicago Fire',
        'CF Montreal': 'CF Montreal',
        'Montreal': 'CF Montreal',
        'Charlotte FC': 'Charlotte FC',
        'Austin FC': 'Austin FC',
        'St Louis City': 'St Louis City',

        # 亚洲
        'Urawa Reds': 'Urawa Red Diamonds',
        'Kashima Antlers': 'Kashima Antlers',
        'Yokohama F. Marinos': 'Yokohama F. Marinos',
        'Yokohama Marinos': 'Yokohama F. Marinos',
        'Kawasaki Frontale': 'Kawasaki Frontale',
        'Gamba Osaka': 'Gamba Osaka',
        'Cerezo Osaka': 'Cerezo Osaka',
        'Tokyo': 'FC Tokyo',
        'FC Tokyo': 'FC Tokyo',
        'Jeonbuk': 'Jeonbuk Hyundai',
        'Jeonbuk Hyundai': 'Jeonbuk Hyundai',
        'Suwon': 'Suwon Samsung',
        'Suwon Samsung': 'Suwon Samsung',
        'Seoul': 'FC Seoul',
        'FC Seoul': 'FC Seoul',
        'Pohang': 'Pohang Steelers',
        'Pohang Steelers': 'Pohang Steelers',
        'Al Hilal': 'Al Hilal',
        'Al Nassr': 'Al Nassr',
        'Al Ahli': 'Al Ahli',
        'Al Ittihad': 'Al Ittihad',

        # 中国
        'Guangzhou': 'Guangzhou Evergrande',
        'Guangzhou Evergrande': 'Guangzhou Evergrande',
        'Shanghai SIPG': 'Shanghai Port',
        'Shanghai Port': 'Shanghai Port',
        'Beijing Guoan': 'Beijing Guoan',
        'Shandong': 'Shandong Taishan',
        'Shandong Taishan': 'Shandong Taishan',
        'Shanghai Shenhua': 'Shanghai Shenhua',

        # 澳大利亚
        'Sydney FC': 'Sydney FC',
        'Melbourne City': 'Melbourne City',
        'Melbourne Victory': 'Melbourne Victory',
        'Western Sydney': 'Western Sydney Wanderers',
        'Western Sydney Wanderers': 'Western Sydney Wanderers',
        'Adelaide United': 'Adelaide United',
        'Central Coast': 'Central Coast Mariners',
        'Central Coast Mariners': 'Central Coast Mariners',
        'Perth Glory': 'Perth Glory',
        'Wellington': 'Wellington Phoenix',
        'Wellington Phoenix': 'Wellington Phoenix',

        # 非洲
        'Al Ahly': 'Al Ahly',
        'Zamalek': 'Zamalek',
        'Esperance': 'Esperance Tunis',
        'Wydad': 'Wydad Casablanca',
        'Wydad Casablanca': 'Wydad Casablanca',
        'Mamelodi': 'Mamelodi Sundowns',
        'Mamelodi Sundowns': 'Mamelodi Sundowns',
        'Kaizer Chiefs': 'Kaizer Chiefs',
        'Orlando Pirates': 'Orlando Pirates',
    }

    # 国家队映射规则
    national_mappings = {
        'Germany FR': 'Germany',
        'West Germany': 'Germany',
        'East Germany': 'Germany',
        'USSR': 'Russia',
        'Soviet Union': 'Russia',
        'Czechoslovakia': 'Czech Republic',
        'Yugoslavia': 'Serbia',
        'Serbia and Montenegro': 'Serbia',
        'Macedonia': 'North Macedonia',
        'Macedonia FYR': 'North Macedonia',
        "Cote d'Ivoire": 'Ivory Coast',
        'Cote d Ivoire': 'Ivory Coast',
        'Cabo Verde': 'Cape Verde',
        'Turkiye': 'Turkey',
        'Türkiye': 'Turkey',
        'Korea Republic': 'South Korea',
        'Korea DPR': 'North Korea',
        'Korea Republic': 'South Korea',
        'IR Iran': 'Iran',
        'Islamic Republic of Iran': 'Iran',
        'China PR': 'China',
        'Chinese Taipei': 'Taiwan',
        'USA': 'United States',
        'United States': 'United States',
        'Holland': 'Netherlands',
        'Curacao': 'Curacao',
        'Curaçao': 'Curacao',
        'Bosnia and Herzegovina': 'Bosnia',
        'Bosnia-Herzegovina': 'Bosnia',
        'Congo DR': 'DR Congo',
        'Congo Democratic': 'DR Congo',
        'Democratic Republic of Congo': 'DR Congo',
        'St. Kitts and Nevis': 'Saint Kitts and Nevis',
        'St. Vincent and the Grenadines': 'Saint Vincent and the Grenadines',
        'Trinidad and Tobago': 'Trinidad and Tobago',
        'Papua New Guinea': 'Papua New Guinea',
        'Solomon Islands': 'Solomon Islands',
        'New Caledonia': 'New Caledonia',
        'French Guiana': 'French Guiana',
        'Guinea-Bissau': 'Guinea-Bissau',
        'Equatorial Guinea': 'Equatorial Guinea',
        'South Sudan': 'South Sudan',
    }

    return club_mappings, national_mappings


def apply_fuzzy_matching(teams, known_mappings, threshold=85):
    """对未映射的球队名称应用模糊匹配"""
    canonical_names = list(set(known_mappings.values()))
    mapping = {}

    for team in teams:
        if team in known_mappings:
            mapping[team] = known_mappings[team]
        else:
            # 尝试模糊匹配
            result = process.extractOne(
                team,
                canonical_names,
                scorer=fuzz.token_sort_ratio
            )
            if result and result[1] >= threshold:
                mapping[team] = result[0]
            else:
                # 保持原名
                mapping[team] = team

    return mapping


def create_master_team_table(all_teams, club_teams, national_teams, club_mappings, national_mappings):
    """创建主球队表"""
    master_data = []
    team_id = 1

    # 处理俱乐部
    processed = set()
    for team in club_teams:
        canonical = club_mappings.get(team, team)
        if canonical not in processed:
            master_data.append({
                'team_id': team_id,
                'canonical_name': canonical,
                'team_type': 'club',
                'country': None,  # 后续填充
                'fifa_code': None
            })
            processed.add(canonical)
            team_id += 1

    # 处理国家队
    for team in national_teams:
        canonical = national_mappings.get(team, team)
        if canonical not in processed:
            master_data.append({
                'team_id': team_id,
                'canonical_name': canonical,
                'team_type': 'national',
                'country': canonical,  # 国家队名称即国家名
                'fifa_code': None
            })
            processed.add(canonical)
            team_id += 1

    return pd.DataFrame(master_data)


def create_name_mapping_table(all_teams, club_mappings, national_mappings):
    """创建名称映射表"""
    mapping_data = []

    for team in all_teams:
        # 判断是国家队还是俱乐部
        is_national = team in national_teams

        if is_national:
            canonical = national_mappings.get(team, team)
        else:
            canonical = club_mappings.get(team, team)

        mapping_data.append({
            'original_name': team,
            'canonical_name': canonical,
            'team_type': 'national' if is_national else 'club'
        })

    return pd.DataFrame(mapping_data)


def main():
    print("=" * 60)
    print("足球数据实体识别与标准化")
    print("=" * 60)

    # 1. 提取所有球队名称
    print("\n[步骤1] 提取所有球队名称...")
    global national_teams  # 用于后续判断
    all_teams, team_sources = extract_all_team_names()
    print(f"发现 {len(all_teams)} 个唯一球队名称")

    # 2. 分类球队
    print("\n[步骤2] 分类国家队和俱乐部...")
    national_teams, club_teams = categorize_teams(all_teams)
    print(f"国家队: {len(national_teams)} 个")
    print(f"俱乐部: {len(club_teams)} 个")

    # 3. 创建映射规则
    print("\n[步骤3] 创建名称映射规则...")
    club_mappings, national_mappings = create_team_mapping(club_teams, national_teams)
    print(f"俱乐部映射规则: {len(club_mappings)} 条")
    print(f"国家队映射规则: {len(national_mappings)} 条")

    # 4. 创建映射表
    print("\n[步骤4] 创建名称映射表...")
    mapping_df = create_name_mapping_table(all_teams, club_mappings, national_mappings)

    # 5. 创建主球队表
    print("\n[步骤5] 创建主球队表...")
    master_df = create_master_team_table(all_teams, club_teams, national_teams,
                                          club_mappings, national_mappings)

    # 6. 保存结果
    print("\n[步骤6] 保存结果...")

    # 保存主球队表
    master_df.to_csv(f'{OUTPUT_DIR}/teams_master.csv', index=False, encoding='utf-8-sig')
    print(f"  - teams_master.csv: {len(master_df)} 条记录")

    # 保存名称映射表
    mapping_df.to_csv(f'{OUTPUT_DIR}/team_name_mapping.csv', index=False, encoding='utf-8-sig')
    print(f"  - team_name_mapping.csv: {len(mapping_df)} 条记录")

    # 保存JSON格式映射（便于程序使用）
    mapping_dict = dict(zip(mapping_df['original_name'], mapping_df['canonical_name']))
    with open(f'{OUTPUT_DIR}/team_name_mapping.json', 'w', encoding='utf-8') as f:
        json.dump(mapping_dict, f, ensure_ascii=False, indent=2)
    print(f"  - team_name_mapping.json")

    # 保存球队来源信息
    with open(f'{OUTPUT_DIR}/team_sources.json', 'w', encoding='utf-8') as f:
        json.dump(dict(team_sources), f, ensure_ascii=False, indent=2)
    print(f"  - team_sources.json")

    # 7. 统计报告
    print("\n" + "=" * 60)
    print("统计报告")
    print("=" * 60)
    print(f"总球队数: {len(all_teams)}")
    print(f"国家队数: {len(national_teams)}")
    print(f"俱乐部数: {len(club_teams)}")
    print(f"标准化后唯一球队数: {len(master_df)}")

    # 显示一些示例
    print("\n示例映射:")
    sample_mappings = list(mapping_dict.items())[:10]
    for orig, canonical in sample_mappings:
        if orig != canonical:
            print(f"  {orig} -> {canonical}")

    print("\n完成！")
    return master_df, mapping_df


if __name__ == '__main__':
    main()
