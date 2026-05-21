"""
正确更新比赛结果 - 按球队名匹配，北京时间转当地时间
"""
import csv
from pathlib import Path
import sys

if sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')

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
}

# 法甲比赛数据 (北京时间)
# 格式: (北京时间月-日, 北京时间, 主队中文, 比分, 客队中文, 主胜赔率, 平局赔率, 客胜赔率)
LIGUE_1_MATCHES = [
    # 第33轮 (北京时间 05-11 03:00 -> 当地 05-10 21:00)
    ('05-11', '03:00', '巴黎圣曼', '1-0', '布雷斯特', 1.16, 7.69, 14.47),
    ('05-11', '03:00', '勒阿弗尔', '0-1', '马赛', 4.39, 4.00, 1.69),
    ('05-11', '03:00', '图卢兹', '2-1', '里昂', 3.52, 3.53, 2.00),
    ('05-11', '03:00', '欧塞尔', '2-1', '尼斯', 2.36, 3.34, 2.88),
    ('05-11', '03:00', '雷恩', '2-1', '巴黎FC', 1.54, 4.35, 5.25),
    ('05-11', '03:00', '梅斯', '0-4', '洛里昂', 2.93, 3.45, 2.28),
    ('05-11', '03:00', '昂热', '1-1', '斯特拉斯', 3.81, 3.49, 1.91),
    ('05-11', '03:00', '摩纳哥', '0-1', '里尔', 2.23, 3.71, 2.83),
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


def update_ligue_1():
    file_path = Path('D:/football_tools/new_data/leagues/ligue_1/ligue_1_2025-2026.csv')

    rows = []
    with open(file_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        headers = reader.fieldnames
        for row in reader:
            rows.append(row)

    print(f'法甲 2025-2026:')
    print(f'  现有比赛数: {len(rows)}')

    updated = 0

    for match in LIGUE_1_MATCHES:
        bj_date, bj_time, home_cn, score, away_cn, odds_h, odds_d, odds_a = match

        home_en = LIGUE_1_TEAMS.get(home_cn, home_cn)
        away_en = LIGUE_1_TEAMS.get(away_cn, away_cn)

        home_goals, away_goals, result = parse_score(score)

        # 按球队名查找比赛
        found = False
        for row in rows:
            if row.get('home_team') == home_en and row.get('away_team') == away_en:
                if home_goals is not None:
                    # 更新比分
                    old_hg = row.get('home_goals', '')
                    old_ag = row.get('away_goals', '')

                    row['home_goals'] = str(home_goals)
                    row['away_goals'] = str(away_goals)
                    row['result'] = result
                    row['status'] = 'Finished'

                    # 更新赔率
                    if odds_h:
                        row['b365_home'] = str(odds_h)
                    if odds_d:
                        row['b365_draw'] = str(odds_d)
                    if odds_a:
                        row['b365_away'] = str(odds_a)

                    updated += 1
                    print(f'  更新: {row.get("match_date")} | {home_en} {score} {away_en} (原比分: {old_hg}-{old_ag})')

                found = True
                break

        if not found:
            print(f'  未找到: {home_en} vs {away_en}')

    # 写回文件
    with open(file_path, 'w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=headers, extrasaction='ignore')
        writer.writeheader()
        writer.writerows(rows)

    finished = sum(1 for r in rows if r.get('status') == 'Finished')
    scheduled = sum(1 for r in rows if r.get('status') == 'Scheduled')
    print(f'  更新: {updated} 场')
    print(f'  最终: Finished={finished}, Scheduled={scheduled}, 总计={len(rows)}')


if __name__ == '__main__':
    print('='*60)
    print('正确更新法甲比赛结果')
    print('='*60)
    update_ligue_1()