"""
生成球队统计文件 - 瑞典超、芬兰超、挪威超
格式: 赛季,联赛英文名,联赛中文名,英文球队名,中文球队名
"""
import csv
from pathlib import Path
from collections import defaultdict

# 瑞典超球队中文名映射
ALLSVENSKAN_CN = {
    'AIK': '索尔纳',
    'Malmo FF': '马尔默',
    'Hammarby': '哈马比',
    'Djurgarden': '佐加顿斯',
    'Elfsborg': '埃尔夫斯堡',
    'Hacken': '赫根',
    'Goteborg': '哥德堡',
    'GAIS': '哥德堡盖斯',
    'Mjallby': '米亚尔比',
    'Sirius': '天狼星',
    'Kalmar': '卡尔马',
    'Halmstad': '哈尔姆斯塔德',
    'Degerfors': '代格福什',
    'Vasteras SK': '韦斯特罗斯',
    'Orgryte': '厄尔格里特',
    'Brommapojkarna': '布鲁马波卡纳',
    'Norrkoping': '北雪平',
    'Orebro': '厄勒布鲁',
    'Varberg': '瓦尔贝里',
    'Ostersunds': '厄斯特松德',
    'AFC Eskilstuna': 'AFC埃斯基尔斯蒂纳',
    'Atvidabergs': '奥特维达贝里',
    'Brage': '布赖格',
    'Dalkurd': '达尔库尔德',
    'Falkenbergs': '法尔肯贝里',
    'Gefle': '耶夫勒',
    'Helsingborg': '赫尔辛堡',
    'Jonkopings': '延雪平',
    'Landskrona': '兰茨克鲁纳',
    'Ljungskile': '永斯基莱',
    'Oster': '奥斯特',
    'Osters': '奥斯特斯',
    'Sundsvall': '松兹瓦尔',
    'Syrianska': '叙利亚人',
    'Trelleborgs': '特雷勒堡',
    'Varnamo': '韦纳穆',
}

# 芬兰超球队中文名映射
VEIKKAUSLIIGA_CN = {
    'HJK': '赫尔辛基',
    'KuPS': '库奥皮奥',
    'Inter Turku': '图尔库国际',
    'Honka': '洪卡',
    'Lahti': '拉赫蒂',
    'Haka': '哈卡',
    'Ilves': '伊尔韦斯',
    'SJK': '塞伊奈约基',
    'Rovaniemi': '罗瓦涅米',
    'Mariehamn': '玛丽港',
    'VPS': '瓦萨',
    'TPS': '图尔库TPS',
    'MyPa': '迈帕',
    'Jaro': '雅罗',
    'AC Oulu': '奥卢',
    'HIFK': 'HIFK赫尔辛基',
    'Gnistan': '格尼斯坦',
    'Ekenas': '埃克奈斯',
    'KTP': '科特卡',
    'KPV Kokkola': '科科拉',
    'JJK Jyvaskyla': 'JJK于韦斯屈莱',
    'PK-35 Vantaa': 'PK-35万塔',
    'PS Kemi': '凯米',
}

# 挪威超球队中文名映射
ELITESERIEN_CN = {
    'Molde': '莫尔德',
    'Rosenborg': '罗森博格',
    'Bodo/Glimt': '博德闪耀',
    'Viking': '维京',
    'Brann': '布兰',
    'Lillestrom': '利勒斯特罗姆',
    'Valerenga': '瓦勒伦加',
    'Tromso': '特罗姆瑟',
    'Odd': '奥德',
    'Haugesund': '海于格松',
    'Sarpsborg 08': '萨尔普斯堡08',
    'Stromsgodset': '斯托姆加斯特',
    'Sandefjord': '桑德菲尤尔',
    'Aalesund': '奥勒松',
    'Kristiansund': '克里斯蒂安松',
    'Sogndal': '松达尔',
    'Stabaek': '斯塔贝克',
    'Start': '斯达',
    'Honefoss': '内弗oss',
    'Fredrikstad': '腓特烈斯塔',
    'Ham-Kam': '哈姆卡姆',
    'HamKam': '哈姆卡姆',
    'Mjondalen': '米约恩达伦',
    'Jerv': '耶尔夫',
    'Sandnes': '桑内斯',
    'Ranheim': '兰海姆',
    'Bryne': '布吕讷',
    'Moss': '莫斯',
    'Kongsvinger': '孔斯温格',
    'Ull/Kisa': '乌尔/基萨',
    'KFUM Oslo': 'KFUM奥斯陆',
}

def extract_teams(league_path, league_en, league_cn, team_cn_map):
    """从CSV文件中提取球队和赛季信息"""
    teams_by_season = defaultdict(set)
    path = Path(league_path)

    for csv_file in sorted(path.glob('*.csv')):
        # 从文件名提取赛季
        season = csv_file.stem.replace(league_en + '_', '')

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

    return len(rows)

if __name__ == '__main__':
    output_dir = Path('D:/football_tools/new_data/teams')

    # 瑞典超
    print('处理瑞典超...')
    teams = extract_teams(
        'D:/football_tools/new_data/leagues/allsvenskan',
        'allsvenskan', '瑞典超', ALLSVENSKAN_CN
    )
    count = write_teams_file(
        output_dir / 'allsvenskan_teams.csv',
        teams, 'allsvenskan', '瑞典超', ALLSVENSKAN_CN
    )
    print(f'  瑞典超: {count}条记录')

    # 芬兰超
    print('处理芬兰超...')
    teams = extract_teams(
        'D:/football_tools/new_data/leagues/veikkausliiga',
        'veikkausliiga', '芬兰超', VEIKKAUSLIIGA_CN
    )
    count = write_teams_file(
        output_dir / 'veikkausliiga_teams.csv',
        teams, 'veikkausliiga', '芬兰超', VEIKKAUSLIIGA_CN
    )
    print(f'  芬兰超: {count}条记录')

    # 挪威超
    print('处理挪威超...')
    teams = extract_teams(
        'D:/football_tools/new_data/leagues/eliteserien',
        'eliteserien', '挪威超', ELITESERIEN_CN
    )
    count = write_teams_file(
        output_dir / 'eliteserien_teams.csv',
        teams, 'eliteserien', '挪威超', ELITESERIEN_CN
    )
    print(f'  挪威超: {count}条记录')

    print('\n完成!')
