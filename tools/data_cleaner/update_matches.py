"""
更新比赛结果 - 意甲和西甲
"""
import csv
from pathlib import Path
import sys

if sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')

# 意甲球队名映射
SERIE_A_TEAMS = {
    '都灵': 'Torino',
    '萨索洛': 'Sassuolo',
    '卡利亚里': 'Cagliari',
    '乌迪内斯': 'Udinese',
    '拉齐奥': 'Lazio',
    '国际米兰': 'Inter',
    '莱切': 'Lecce',
    '尤文': 'Juventus',
    '维罗纳': 'Verona',
    '科莫': 'Como',
    '克雷莫纳': 'Cremonese',
    '比萨': 'Pisa',
    '佛罗伦萨': 'Fiorentina',
    '热那亚': 'Genoa',
    '帕尔马': 'Parma',
    '罗马': 'Roma',
    'AC米兰': 'Milan',
    '亚特兰大': 'Atalanta',
    '那不勒斯': 'Napoli',
    '博洛尼亚': 'Bologna',
}

# 西甲球队名映射
LA_LIGA_TEAMS = {
    '塞尔塔': 'Celta',
    '莱万特': 'Levante',
    '贝蒂斯': 'Betis',
    '埃尔切': 'Elche',
    '奥萨苏纳': 'Osasuna',
    '马竞': 'Ath Madrid',
    '西班牙人': 'Espanyol',
    '毕尔巴鄂': 'Ath Bilbao',
    '比利亚雷': 'Villarreal',
    '塞维利亚': 'Sevilla',
    '阿拉维斯': 'Alaves',
    '巴萨': 'Barcelona',
    '赫塔费': 'Getafe',
    '马洛卡': 'Mallorca',
    '巴伦西亚': 'Valencia',
    '巴列卡诺': 'Rayo Vallecano',
    '赫罗纳': 'Girona',
    '皇家社会': 'Real Sociedad',
    '皇马': 'Real Madrid',
    '奥维耶多': 'Oviedo',
}

# 意甲比赛数据
SERIE_A_MATCHES = [
    # 第36轮
    ('05-09', '02:45', 36, '都灵', '2-1', '萨索洛', 2.25, 3.06, 3.36),
    ('05-09', '21:00', 36, '卡利亚里', '0-2', '乌迪内斯', 2.42, 3.08, 3.01),
    ('05-10', '00:00', 36, '拉齐奥', '0-3', '国际米兰', 4.51, 3.71, 1.74),
    ('05-10', '02:45', 36, '莱切', '0-1', '尤文', 6.05, 4.33, 1.49),
    ('05-10', '18:30', 36, '维罗纳', '0-1', '科莫', 6.16, 4.38, 1.49),
    ('05-10', '21:00', 36, '克雷莫纳', '3-0', '比萨', 2.05, 3.22, 3.71),
    ('05-10', '21:00', 36, '佛罗伦萨', '0-0', '热那亚', 2.00, 3.30, 3.77),
    ('05-11', '00:00', 36, '帕尔马', '2-3', '罗马', 4.39, 3.62, 1.77),
    ('05-11', '02:45', 36, 'AC米兰', '2-3', '亚特兰大', 2.03, 3.37, 3.60),
    ('05-12', '02:45', 36, '那不勒斯', '2-3', '博洛尼亚', 1.59, 3.92, 5.45),
    # 第37轮
    ('05-17', '18:00', 37, '科莫', '1-0', '帕尔马', 1.32, 5.06, 8.85),
    ('05-17', '18:00', 37, '热那亚', '1-2', 'AC米兰', 4.26, 3.63, 1.78),
    ('05-17', '18:00', 37, '尤文', '0-2', '佛罗伦萨', 1.40, 4.75, 6.90),
    ('05-17', '18:00', 37, '比萨', '0-3', '那不勒斯', 6.79, 4.47, 1.43),
    ('05-17', '18:00', 37, '罗马', '2-0', '拉齐奥', 1.65, 3.77, 4.97),
    ('05-17', '21:00', 37, '国际米兰', '1-1', '维罗纳', 1.17, 6.84, 14.83),
    ('05-18', '00:00', 37, '亚特兰大', '0-1', '博洛尼亚', 1.65, 4.05, 4.65),
    ('05-18', '02:45', 37, '卡利亚里', '2-1', '都灵', 2.57, 2.79, 3.10),
    ('05-18', '02:45', 37, '萨索洛', '2-3', '莱切', 2.26, 3.16, 3.19),
    ('05-18', '02:45', 37, '乌迪内斯', '0-1', '克雷莫纳', 1.94, 3.43, 3.82),
    # 第38轮
    ('05-24', '21:00', 38, '博洛尼亚', None, '国际米兰', 4.37, 4.00, 1.70),
    ('05-24', '21:00', 38, '克雷莫纳', None, '科莫', 5.71, 4.14, 1.54),
    ('05-24', '21:00', 38, '佛罗伦萨', None, '亚特兰大', 2.96, 3.46, 2.28),
    ('05-24', '21:00', 38, '拉齐奥', None, '比萨', 1.48, 4.27, 6.57),
    ('05-24', '21:00', 38, '莱切', None, '热那亚', 1.80, 3.49, 4.54),
    ('05-24', '21:00', 38, 'AC米兰', None, '卡利亚里', 1.37, 4.49, 8.57),
    ('05-24', '21:00', 38, '那不勒斯', None, '乌迪内斯', 1.49, 4.18, 6.56),
    ('05-24', '21:00', 38, '帕尔马', None, '萨索洛', 2.79, 3.23, 2.52),
    ('05-24', '21:00', 38, '维罗纳', None, '罗马', 7.29, 4.41, 1.46),
    ('05-24', '21:00', 38, '都灵', None, '尤文', 6.14, 4.22, 1.49),
]

# 西甲比赛数据
LA_LIGA_MATCHES = [
    # 第36轮
    ('05-13', '01:00', 36, '塞尔塔', '2-3', '莱万特', 1.70, 3.87, 4.47),
    ('05-13', '02:00', 36, '贝蒂斯', '2-1', '埃尔切', 1.63, 3.98, 4.85),
    ('05-13', '03:30', 36, '奥萨苏纳', '1-2', '马竞', 2.61, 3.48, 2.50),
    ('05-14', '01:00', 36, '西班牙人', '2-0', '毕尔巴鄂', 2.82, 3.31, 2.42),
    ('05-14', '01:00', 36, '比利亚雷', '2-3', '塞维利亚', 1.84, 3.56, 4.14),
    ('05-14', '03:30', 36, '阿拉维斯', '1-0', '巴萨', 4.46, 3.95, 1.69),
    ('05-14', '03:30', 36, '赫塔费', '3-1', '马洛卡', 2.06, 2.95, 4.07),
    ('05-15', '01:00', 36, '巴伦西亚', '1-1', '巴列卡诺', 2.13, 3.26, 3.37),
    ('05-15', '02:00', 36, '赫罗纳', '1-1', '皇家社会', 2.24, 3.56, 2.91),
    ('05-15', '03:30', 36, '皇马', '2-0', '奥维耶多', 1.21, 6.45, 11.21),
    # 第37轮
    ('05-18', '01:00', 37, '毕尔巴鄂', '1-1', '塞尔塔', 1.79, 3.65, 4.26),
    ('05-18', '01:00', 37, '马竞', '1-0', '赫罗纳', 1.52, 4.43, 5.21),
    ('05-18', '01:00', 37, '埃尔切', '1-0', '赫塔费', 2.24, 3.09, 3.27),
    ('05-18', '01:00', 37, '莱万特', '2-0', '马洛卡', 2.19, 3.33, 3.21),
    ('05-18', '01:00', 37, '巴列卡诺', '2-0', '比利亚雷', 2.32, 3.53, 2.82),
    ('05-18', '01:00', 37, '皇家社会', '3-4', '巴伦西亚', 1.95, 3.54, 3.65),
    ('05-18', '01:00', 37, '奥维耶多', '0-1', '阿拉维斯', 2.50, 3.27, 2.70),
    ('05-18', '01:00', 37, '奥萨苏纳', '1-2', '西班牙人', 1.94, 3.44, 3.82),
    ('05-18', '01:00', 37, '塞维利亚', '0-1', '皇马', 3.96, 4.07, 1.73),
    ('05-18', '03:15', 37, '巴萨', '3-1', '贝蒂斯', 1.30, 5.82, 7.49),
    # 第38轮
    ('05-24', '03:00', 38, '阿拉维斯', None, '巴列卡诺', 2.48, 3.12, 2.93),
    ('05-24', '03:00', 38, '贝蒂斯', None, '莱万特', 1.88, 3.92, 3.65),
    ('05-24', '03:00', 38, '塞尔塔', None, '塞维利亚', 2.05, 3.44, 3.50),
    ('05-24', '03:00', 38, '西班牙人', None, '皇家社会', 2.31, 3.38, 3.01),
    ('05-24', '03:00', 38, '赫塔费', None, '奥萨苏纳', 2.37, 2.80, 3.52),
    ('05-24', '03:00', 38, '马洛卡', None, '奥维耶多', 1.54, 4.00, 6.07),
    ('05-24', '03:00', 38, '皇马', None, '毕尔巴鄂', 1.46, 4.60, 6.14),
    ('05-24', '03:00', 38, '巴伦西亚', None, '巴萨', 3.89, 4.09, 1.78),
    ('05-24', '03:00', 38, '赫罗纳', None, '埃尔切', 1.82, 3.77, 3.98),
    ('05-25', '03:00', 38, '比利亚雷', None, '马竞', 2.47, 3.90, 2.53),
]


def parse_score(score_str):
    """解析比分"""
    if not score_str or score_str.strip() == '':
        return None, None, None
    try:
        parts = score_str.split('-')
        home = int(parts[0])
        away = int(parts[1])
        if home > away:
            result = 'H'
        elif home < away:
            result = 'A'
        else:
            result = 'D'
        return home, away, result
    except:
        return None, None, None


def update_league(league_name, team_mapping, matches):
    """更新联赛数据"""
    file_path = Path(f'D:/football_tools/new_data/leagues/{league_name}/{league_name}_2025-2026.csv')

    rows = []
    with open(file_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        headers = reader.fieldnames
        for row in reader:
            rows.append(row)

    print(f'\n{league_name}:')
    print(f'  现有比赛数: {len(rows)}')

    updated = 0
    added = 0

    for match in matches:
        month_day, time, round_num, home_cn, score, away_cn, odds_h, odds_d, odds_a = match

        home_en = team_mapping.get(home_cn, home_cn)
        away_en = team_mapping.get(away_cn, away_cn)
        date_str = f'2026-{month_day}'

        home_goals, away_goals, result = parse_score(score)
        status = 'Finished' if home_goals is not None else 'Scheduled'

        found = False
        for row in rows:
            if (row.get('home_team') == home_en and
                row.get('away_team') == away_en and
                row.get('round_num') == str(round_num)):

                if home_goals is not None:
                    row['home_goals'] = str(home_goals)
                    row['away_goals'] = str(away_goals)
                    row['result'] = result
                row['status'] = status
                row['match_date'] = date_str
                row['match_time'] = time

                if odds_h:
                    row['b365_home'] = str(odds_h)
                if odds_d:
                    row['b365_draw'] = str(odds_d)
                if odds_a:
                    row['b365_away'] = str(odds_a)

                found = True
                updated += 1
                break

        if not found:
            new_row = {h: 'null' for h in headers}
            new_row['season'] = '2025-2026'
            new_row['match_date'] = date_str
            new_row['match_time'] = time
            new_row['round_num'] = str(round_num)
            new_row['home_team'] = home_en
            new_row['away_team'] = away_en
            new_row['status'] = status

            if home_goals is not None:
                new_row['home_goals'] = str(home_goals)
                new_row['away_goals'] = str(away_goals)
                new_row['result'] = result

            if odds_h:
                new_row['b365_home'] = str(odds_h)
            if odds_d:
                new_row['b365_draw'] = str(odds_d)
            if odds_a:
                new_row['b365_away'] = str(odds_a)

            rows.append(new_row)
            added += 1

    with open(file_path, 'w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=headers, extrasaction='ignore')
        writer.writeheader()
        writer.writerows(rows)

    finished = sum(1 for r in rows if r.get('status') == 'Finished')
    scheduled = sum(1 for r in rows if r.get('status') == 'Scheduled')
    print(f'  更新: {updated} 场, 新增: {added} 场')
    print(f'  最终: Finished={finished}, Scheduled={scheduled}, 总计={len(rows)}')


if __name__ == '__main__':
    print('='*60)
    print('更新意甲和西甲 2025-2026 赛季比赛结果')
    print('='*60)

    update_league('serie_a', SERIE_A_TEAMS, SERIE_A_MATCHES)
    update_league('la_liga', LA_LIGA_TEAMS, LA_LIGA_MATCHES)

    print('\n完成!')