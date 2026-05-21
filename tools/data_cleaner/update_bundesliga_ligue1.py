"""
更新比赛结果 - 德甲和法甲
"""
import csv
from pathlib import Path
import sys

if sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')

# 德甲球队名映射
BUNDESLIGA_TEAMS = {
    '多特蒙德': 'Dortmund',
    '法兰克福': 'Frankfurt',
    '莱比锡': 'RB Leipzig',
    '圣保利': 'St Pauli',
    '斯图加特': 'Stuttgart',
    '勒沃库森': 'Leverkusen',
    '奥格斯堡': 'Augsburg',
    '门兴': "M'gladbach",
    '霍芬海姆': 'Hoffenheim',
    '不来梅': 'Werder Bremen',
    '沃尔夫斯堡': 'Wolfsburg',
    '拜仁': 'Bayern Munich',
    '汉堡': 'Hamburg',
    '弗赖堡': 'Freiburg',
    '科隆': 'FC Koln',
    '海登海姆': 'Heidenheim',
    '美因茨': 'Mainz',
    '柏林联合': 'Union Berlin',
}

# 法甲球队名映射
LIGUE_1_TEAMS = {
    '朗斯': 'Lens',
    '南特': 'Nantes',
    '巴黎圣曼': 'Paris SG',
    '布雷斯特': 'Brest',
    '勒阿弗尔': 'Le Havre',
    '马赛': 'Marseille',
    '图卢兹': 'Toulouse',
    '里昂': 'Lyon',
    '欧塞尔': 'Auxerre',
    '尼斯': 'Nice',
    '雷恩': 'Rennes',
    '巴黎FC': 'Paris FC',
    '梅斯': 'Metz',
    '洛里昂': 'Lorient',
    '昂热': 'Angers',
    '斯特拉斯': 'Strasbourg',
    '摩纳哥': 'Monaco',
    '里尔': 'Lille',
    '圣埃蒂安': 'St Etienne',
    '圣旺红星': 'Red Star',
    '罗德兹': 'Rodez',
}

# 德甲比赛数据
BUNDESLIGA_MATCHES = [
    # 第33轮
    ('05-09', '02:30', 33, '多特蒙德', '3-2', '法兰克福', 1.52, 4.61, 5.08),
    ('05-09', '21:30', 33, '莱比锡', '2-1', '圣保利', 1.41, 4.76, 6.67),
    ('05-09', '21:30', 33, '斯图加特', '3-1', '勒沃库森', 2.07, 3.89, 3.01),
    ('05-09', '21:30', 33, '奥格斯堡', '3-1', '门兴', 2.26, 3.51, 2.90),
    ('05-09', '21:30', 33, '霍芬海姆', '1-0', '不来梅', 1.56, 4.54, 4.83),
    ('05-10', '00:30', 33, '沃尔夫斯堡', '0-1', '拜仁', 5.01, 5.00, 1.49),
    ('05-10', '21:30', 33, '汉堡', '3-2', '弗赖堡', 2.69, 3.56, 2.39),
    ('05-10', '23:30', 33, '科隆', '1-3', '海登海姆', 1.71, 4.05, 4.21),
    ('05-11', '01:30', 33, '美因茨', '1-3', '柏林联合', 1.81, 3.67, 4.04),
    # 第34轮
    ('05-16', '21:30', 34, '拜仁', '5-1', '科隆', 1.22, 7.03, 9.67),
    ('05-16', '21:30', 34, '勒沃库森', '1-1', '汉堡', 1.40, 5.43, 6.14),
    ('05-16', '21:30', 34, '法兰克福', '2-2', '斯图加特', 3.04, 4.07, 2.04),
    ('05-16', '21:30', 34, '弗赖堡', '4-1', '莱比锡', 3.20, 3.83, 2.04),
    ('05-16', '21:30', 34, '不来梅', '0-2', '多特蒙德', 3.61, 3.98, 1.87),
    ('05-16', '21:30', 34, '门兴', '4-0', '霍芬海姆', 2.96, 3.86, 2.14),
    ('05-16', '21:30', 34, '柏林联合', '4-0', '奥格斯堡', 2.36, 3.93, 2.59),
    ('05-16', '21:30', 34, '圣保利', '1-3', '沃尔夫斯堡', 2.48, 3.50, 2.67),
    ('05-16', '21:30', 34, '海登海姆', '0-2', '美因茨', 2.71, 4.05, 2.23),
]

# 法甲比赛数据
LIGUE_1_MATCHES = [
    # 第33轮
    ('05-09', '02:45', 33, '朗斯', '1-0', '南特', 1.29, 5.44, 9.19),
    ('05-11', '03:00', 33, '巴黎圣曼', '1-0', '布雷斯特', 1.16, 7.69, 14.47),
    ('05-11', '03:00', 33, '勒阿弗尔', '0-1', '马赛', 4.39, 4.00, 1.69),
    ('05-11', '03:00', 33, '图卢兹', '2-1', '里昂', 3.52, 3.53, 2.00),
    ('05-11', '03:00', 33, '欧塞尔', '2-1', '尼斯', 2.36, 3.34, 2.88),
    ('05-11', '03:00', 33, '雷恩', '2-1', '巴黎FC', 1.54, 4.35, 5.25),
    ('05-11', '03:00', 33, '梅斯', '0-4', '洛里昂', 2.93, 3.45, 2.28),
    ('05-11', '03:00', 33, '昂热', '1-1', '斯特拉斯', 3.81, 3.49, 1.91),
    ('05-11', '03:00', 33, '摩纳哥', '0-1', '里尔', 2.23, 3.71, 2.83),
    # 第34轮
    ('05-18', '03:00', 34, '洛里昂', '0-2', '勒阿弗尔', 1.97, 3.70, 3.47),
    ('05-18', '03:00', 34, '南特', None, '图卢兹', 2.64, 3.26, 2.63),
    ('05-18', '03:00', 34, '里尔', '0-2', '欧塞尔', 1.29, 5.10, 10.65),
    ('05-18', '03:00', 34, '尼斯', '0-0', '梅斯', 1.41, 4.33, 8.13),
    ('05-18', '03:00', 34, '布雷斯特', '1-1', '昂热', 1.77, 3.50, 4.68),
    ('05-18', '03:00', 34, '巴黎FC', '2-1', '巴黎圣曼', 7.84, 5.29, 1.34),
    ('05-18', '03:00', 34, '马赛', '3-1', '雷恩', 1.68, 3.69, 4.98),
    ('05-18', '03:00', 34, '斯特拉斯', '5-4', '摩纳哥', 2.60, 3.63, 2.47),
    ('05-18', '03:00', 34, '里昂', '0-4', '朗斯', 2.58, 3.51, 2.55),
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
    print('更新德甲和法甲 2025-2026 赛季比赛结果')
    print('='*60)

    update_league('bundesliga', BUNDESLIGA_TEAMS, BUNDESLIGA_MATCHES)
    update_league('ligue_1', LIGUE_1_TEAMS, LIGUE_1_MATCHES)

    print('\n完成!')