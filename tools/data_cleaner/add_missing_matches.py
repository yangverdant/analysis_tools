"""
添加缺失的比赛到五大联赛数据
"""
import csv
from pathlib import Path
import sys

if sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')

# 球队名映射
PREMIER_LEAGUE_TEAMS = {
    '利物浦': 'Liverpool',
    '阿森纳': 'Arsenal',
    '诺丁汉': 'Nottm Forest',
    '曼城': 'Man City',
    '纽卡斯尔': 'Newcastle',
    '切尔西': 'Chelsea',
    '阿斯顿维': 'Aston Villa',
    '伯恩茅斯': 'Bournemouth',
    '富勒姆': 'Fulham',
    '热刺': 'Tottenham',
    '布赖顿': 'Brighton',
    '水晶宫': 'Crystal Palace',
    '布伦特福': 'Brentford',
    '西汉姆': 'West Ham',
    '曼联': 'Man United',
    '埃弗顿': 'Everton',
    '狼队': 'Wolves',
    '莱斯特城': 'Leicester',
    '伊普斯维': 'Ipswich',
    '南安普顿': 'Southampton',
}

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
}

# 缺失的比赛数据 (北京时间)
# 格式: (北京时间月-日, 北京时间, 主队中文, 比分, 客队中文, 主胜赔率, 平局赔率, 客胜赔率)
MISSING_PREMIER_LEAGUE = [
    # 第37轮 - Everton vs Southampton
    ('05-10', '22:00', '埃弗顿', '0-2', '南安普顿', 2.50, 3.30, 2.90),
]

MISSING_LIGUE_1 = [
    # 第34轮 (北京时间 05-18 03:00 -> 当地 05-17 21:00)
    ('05-18', '03:00', '洛里昂', '0-2', '勒阿弗尔', 1.97, 3.70, 3.47),
    ('05-18', '03:00', '南特', None, '图卢兹', 2.64, 3.26, 2.63),
    ('05-18', '03:00', '里尔', '0-2', '欧塞尔', 1.29, 5.10, 10.65),
    ('05-18', '03:00', '尼斯', '0-0', '梅斯', 1.41, 4.33, 8.13),
    ('05-18', '03:00', '布雷斯特', '1-1', '昂热', 1.77, 3.50, 4.68),
    ('05-18', '03:00', '巴黎FC', '2-1', '巴黎圣曼', 7.84, 5.29, 1.34),
    ('05-18', '03:00', '马赛', '3-1', '雷恩', 1.68, 3.69, 4.98),
    ('05-18', '03:00', '斯特拉斯', '5-4', '摩纳哥', 2.60, 3.63, 2.47),
    ('05-18', '03:00', '里昂', '0-4', '朗斯', 2.58, 3.51, 2.55),
]


def parse_score(score_str):
    if not score_str:
        return None, None, None
    try:
        parts = score_str.split('-')
        home = int(parts[0])
        away = int(parts[1])
        result = 'H' if home > away else ('A' if home < away else 'D')
        return home, away, result
    except:
        return None, None, None


def add_missing_matches(league_name, team_mapping, matches):
    """添加缺失的比赛"""
    file_path = Path(f'D:/football_tools/new_data/leagues/{league_name}/{league_name}_2025-2026.csv')

    rows = []
    with open(file_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        headers = reader.fieldnames
        for row in reader:
            rows.append(row)

    print(f'\n{league_name}:')
    print(f'  现有比赛数: {len(rows)}')

    # 找到最大轮次
    max_round = max(int(r.get('round_num', 0)) for r in rows if r.get('round_num') and r['round_num'] != 'null')
    print(f'  当前最大轮次: {max_round}')

    added = 0
    for match in matches:
        bj_date, bj_time, home_cn, score, away_cn, odds_h, odds_d, odds_a = match

        home_en = team_mapping.get(home_cn, home_cn)
        away_en = team_mapping.get(away_cn, away_cn)

        # 北京时间转当地时间
        # 法甲: 北京时间 -6小时 (夏季) / -7小时 (冬季)
        # 05-18 03:00 北京 -> 05-17 21:00 当地
        import datetime
        bj_hour = int(bj_time.split(':')[0])
        bj_minute = int(bj_time.split(':')[1])

        # 计算当地时间 (减6小时)
        local_hour = bj_hour - 6
        local_date = bj_date
        if local_hour < 0:
            local_hour += 24
            # 日期减1天
            month = int(bj_date.split('-')[0])
            day = int(bj_date.split('-')[1])
            day -= 1
            if day < 1:
                month -= 1
                if month < 1:
                    month = 12
                # 简化处理，假设每月31天
                day = 31
            local_date = f'{month:02d}-{day:02d}'

        local_time = f'{local_hour:02d}:{bj_minute:02d}'

        home_goals, away_goals, result = parse_score(score)
        status = 'Finished' if home_goals is not None else 'Scheduled'

        # 检查是否已存在
        exists = False
        for row in rows:
            if row.get('home_team') == home_en and row.get('away_team') == away_en:
                exists = True
                break

        if not exists:
            # 添加新比赛
            new_row = {h: 'null' for h in headers}
            new_row['season'] = '2025-2026'
            new_row['match_date'] = f'2026-{local_date}'
            new_row['match_time'] = local_time
            new_row['round_num'] = str(max_round + 1)
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
            if score:
                print(f'  添加: {home_en} {score} {away_en} (第{max_round + 1}轮)')
            else:
                print(f'  添加: {home_en} vs {away_en} (未开赛, 第{max_round + 1}轮)')
        else:
            print(f'  已存在: {home_en} vs {away_en}')

    # 写回文件
    with open(file_path, 'w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=headers, extrasaction='ignore')
        writer.writeheader()
        writer.writerows(rows)

    finished = sum(1 for r in rows if r.get('status') == 'Finished')
    scheduled = sum(1 for r in rows if r.get('status') == 'Scheduled')
    print(f'  新增: {added} 场')
    print(f'  最终: Finished={finished}, Scheduled={scheduled}, 总计={len(rows)}')


if __name__ == '__main__':
    print('='*60)
    print('添加缺失的比赛')
    print('='*60)

    add_missing_matches('premier_league', PREMIER_LEAGUE_TEAMS, MISSING_PREMIER_LEAGUE)
    add_missing_matches('ligue_1', LIGUE_1_TEAMS, MISSING_LIGUE_1)

    print('\n完成!')