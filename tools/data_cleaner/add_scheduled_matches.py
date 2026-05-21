"""
添加五大联赛未开赛的比赛
北京时间 -> 当地时间
英超: -7小时 (UTC+1 夏令时)
意甲: -6小时 (UTC+2 夏令时)
西甲: -6小时 (UTC+2 夏令时)
"""
import csv
from pathlib import Path
import sys

if sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')

# 球队名映射
PREMIER_LEAGUE_TEAMS = {
    '阿森纳': 'Arsenal', '伯恩利': 'Burnley', '伯恩茅斯': 'Bournemouth',
    '曼城': 'Man City', '切尔西': 'Chelsea', '热刺': 'Tottenham',
    '布莱顿': 'Brighton', '曼联': 'Man United', '狼队': 'Wolves',
    '水晶宫': 'Crystal Palace', '富勒姆': 'Fulham', '纽卡斯尔': 'Newcastle',
    '利物浦': 'Liverpool', '布伦特': 'Brentford', '维拉': 'Aston Villa',
    '诺丁汉森林': 'Nottm Forest', '桑德兰': 'Sunderland',
    '埃弗顿': 'Everton', '西汉姆': 'West Ham', '利兹联': 'Leeds',
}

SERIE_A_TEAMS = {
    '博洛尼亚': 'Bologna', '国际米兰': 'Inter', '克雷莫纳': 'Cremonese',
    '科莫': 'Como', '佛罗伦萨': 'Fiorentina', '亚特兰大': 'Atalanta',
    '拉齐奥': 'Lazio', '比萨': 'Pisa', '莱切': 'Lecce', '热那亚': 'Genoa',
    'AC米兰': 'Milan', '卡利亚里': 'Cagliari', '那不勒斯': 'Napoli',
    '乌迪内斯': 'Udinese', '帕尔马': 'Parma', '萨索洛': 'Sassuolo',
    '维罗纳': 'Verona', '罗马': 'Roma', '都灵': 'Torino', '尤文': 'Juventus',
}

LA_LIGA_TEAMS = {
    '阿拉维斯': 'Alaves', '巴列卡诺': 'Rayo Vallecano', '贝蒂斯': 'Betis',
    '莱万特': 'Levante', '塞尔塔': 'Celta', '塞维利亚': 'Sevilla',
    '西班牙人': 'Espanyol', '皇家社会': 'Real Sociedad', '赫塔费': 'Getafe',
    '奥萨苏纳': 'Osasuna', '马洛卡': 'Mallorca', '奥维耶多': 'Oviedo',
    '皇马': 'Real Madrid', '毕尔巴鄂': 'Ath Bilbao', '巴伦西亚': 'Valencia',
    '巴萨': 'Barcelona', '赫罗纳': 'Girona', '埃尔切': 'Elche',
    '比利亚雷': 'Villarreal', '马竞': 'Ath Madrid',
}

# 未开赛比赛 (北京时间)
PREMIER_LEAGUE_MATCHES = [
    # (北京时间月-日, 北京时间, 轮次, 主队, 客队, 主胜赔率, 平局赔率, 客胜赔率)
    ('05-19', '03:00', 37, '阿森纳', '伯恩利', 1.13, 8.49, 17.50),
    ('05-20', '02:30', 37, '伯恩茅斯', '曼城', 4.34, 4.23, 1.68),
    ('05-20', '03:15', 37, '切尔西', '热刺', 1.99, 3.73, 3.34),
    ('05-24', '23:00', 38, '布莱顿', '曼联', 2.21, 3.66, 2.96),
    ('05-24', '23:00', 38, '伯恩利', '狼队', 2.39, 3.41, 2.81),
    ('05-24', '23:00', 38, '水晶宫', '阿森纳', 6.70, 4.14, 1.50),
    ('05-24', '23:00', 38, '富勒姆', '纽卡斯尔', 2.52, 3.64, 2.51),
    ('05-24', '23:00', 38, '利物浦', '布伦特', 1.58, 4.36, 5.19),
    ('05-24', '23:00', 38, '曼城', '维拉', 1.36, 5.27, 7.08),
    ('05-24', '23:00', 38, '诺丁汉森林', '伯恩茅斯', 2.50, 3.58, 2.64),
    ('05-24', '23:00', 38, '桑德兰', '切尔西', 3.72, 3.64, 1.94),
    ('05-24', '23:00', 38, '热刺', '埃弗顿', None, None, None),
    ('05-24', '23:00', 38, '西汉姆', '利兹联', None, None, None),
]

SERIE_A_MATCHES = [
    ('05-24', '21:00', 38, '博洛尼亚', '国际米兰', 4.37, 4.00, 1.70),
    ('05-24', '21:00', 38, '克雷莫纳', '科莫', 5.71, 4.14, 1.54),
    ('05-24', '21:00', 38, '佛罗伦萨', '亚特兰大', 2.96, 3.46, 2.28),
    ('05-24', '21:00', 38, '拉齐奥', '比萨', 1.48, 4.27, 6.57),
    ('05-24', '21:00', 38, '莱切', '热那亚', 1.80, 3.49, 4.54),
    ('05-24', '21:00', 38, 'AC米兰', '卡利亚里', 1.37, 4.49, 8.57),
    ('05-24', '21:00', 38, '那不勒斯', '乌迪内斯', 1.49, 4.18, 6.56),
    ('05-24', '21:00', 38, '帕尔马', '萨索洛', 2.79, 3.23, 2.52),
    ('05-24', '21:00', 38, '维罗纳', '罗马', 7.29, 4.41, 1.46),
    ('05-24', '21:00', 38, '都灵', '尤文', 6.14, 4.22, 1.49),
]

LA_LIGA_MATCHES = [
    ('05-24', '03:00', 38, '阿拉维斯', '巴列卡诺', 2.48, 3.12, 2.93),
    ('05-24', '03:00', 38, '贝蒂斯', '莱万特', 1.88, 3.92, 3.65),
    ('05-24', '03:00', 38, '塞尔塔', '塞维利亚', 2.05, 3.44, 3.50),
    ('05-24', '03:00', 38, '西班牙人', '皇家社会', 2.31, 3.38, 3.01),
    ('05-24', '03:00', 38, '赫塔费', '奥萨苏纳', 2.37, 2.80, 3.52),
    ('05-24', '03:00', 38, '马洛卡', '奥维耶多', 1.54, 4.00, 6.07),
    ('05-24', '03:00', 38, '皇马', '毕尔巴鄂', 1.46, 4.60, 6.14),
    ('05-24', '03:00', 38, '巴伦西亚', '巴萨', 3.89, 4.09, 1.78),
    ('05-24', '03:00', 38, '赫罗纳', '埃尔切', 1.82, 3.77, 3.98),
    ('05-25', '03:00', 38, '比利亚雷', '马竞', 2.47, 3.90, 2.53),
]


def convert_to_local(bj_date, bj_time, offset_hours=6):
    """北京时间转当地时间"""
    bj_hour = int(bj_time.split(':')[0])
    bj_minute = int(bj_time.split(':')[1])

    local_hour = bj_hour - offset_hours
    local_date = bj_date

    if local_hour < 0:
        local_hour += 24
        month = int(bj_date.split('-')[0])
        day = int(bj_date.split('-')[1])
        day -= 1
        if day < 1:
            month -= 1
            if month < 1:
                month = 12
            day = 31
        local_date = f'{month:02d}-{day:02d}'

    local_time = f'{local_hour:02d}:{bj_minute:02d}'
    return f'2026-{local_date}', local_time


def add_matches(league_name, team_mapping, matches, offset_hours=6):
    """添加比赛"""
    file_path = Path(f'D:/football_tools/new_data/leagues/{league_name}/{league_name}_2025-2026.csv')

    rows = []
    with open(file_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        headers = reader.fieldnames
        for row in reader:
            rows.append(row)

    print(f'\n{league_name}:')

    for bj_date, bj_time, round_num, home_cn, away_cn, odds_h, odds_d, odds_a in matches:
        home_en = team_mapping.get(home_cn, home_cn)
        away_en = team_mapping.get(away_cn, away_cn)

        local_date, local_time = convert_to_local(bj_date, bj_time, offset_hours)

        # 检查是否已存在
        exists = any(r.get('home_team') == home_en and r.get('away_team') == away_en for r in rows)
        if exists:
            print(f'  已存在: {home_en} vs {away_en}')
            continue

        # 添加新比赛
        new_row = {h: 'null' for h in headers}
        new_row['season'] = '2025-2026'
        new_row['match_date'] = local_date
        new_row['match_time'] = local_time
        new_row['round_num'] = str(round_num)
        new_row['home_team'] = home_en
        new_row['away_team'] = away_en
        new_row['status'] = 'Scheduled'

        if odds_h:
            new_row['b365_home'] = str(odds_h)
        if odds_d:
            new_row['b365_draw'] = str(odds_d)
        if odds_a:
            new_row['b365_away'] = str(odds_a)

        rows.append(new_row)
        print(f'  添加: {local_date} {local_time} | {home_en} vs {away_en} (第{round_num}轮)')

    with open(file_path, 'w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=headers, extrasaction='ignore')
        writer.writeheader()
        writer.writerows(rows)

    finished = sum(1 for r in rows if r.get('status') == 'Finished')
    scheduled = sum(1 for r in rows if r.get('status') == 'Scheduled')
    print(f'  总计: {len(rows)} 场 (Finished={finished}, Scheduled={scheduled})')


if __name__ == '__main__':
    print('='*60)
    print('添加未开赛比赛')
    print('='*60)

    # 英超 -7小时
    add_matches('premier_league', PREMIER_LEAGUE_TEAMS, PREMIER_LEAGUE_MATCHES, offset_hours=7)
    # 意甲 -6小时
    add_matches('serie_a', SERIE_A_TEAMS, SERIE_A_MATCHES, offset_hours=6)
    # 西甲 -6小时
    add_matches('la_liga', LA_LIGA_TEAMS, LA_LIGA_MATCHES, offset_hours=6)

    print('\n完成!')
