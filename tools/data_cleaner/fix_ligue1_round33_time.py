"""
修正法甲第33轮比赛的日期时间和比分
北京时间 -> 当地时间 (减6小时)
"""
import csv
from pathlib import Path
import sys

if sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')

# 第33轮比赛 (北京时间)
# 北京时间 05-09 02:45 -> 当地 05-08 20:45
# 北京时间 05-11 03:00 -> 当地 05-10 21:00
MATCHES_ROUND_33 = [
    # (北京时间月-日, 北京时间, 主队, 比分, 客队)
    ('05-09', '02:45', 'Lens', '1-0', 'Nantes'),           # -> 当地 05-08 20:45
    ('05-11', '03:00', 'Paris SG', '1-0', 'Brest'),        # -> 当地 05-10 21:00
    ('05-11', '03:00', 'Le Havre', '0-1', 'Marseille'),    # -> 当地 05-10 21:00
    ('05-11', '03:00', 'Toulouse', '2-1', 'Lyon'),         # -> 当地 05-10 21:00
    ('05-11', '03:00', 'Auxerre', '2-1', 'Nice'),          # -> 当地 05-10 21:00
    ('05-11', '03:00', 'Rennes', '2-1', 'Paris FC'),       # -> 当地 05-10 21:00
    ('05-11', '03:00', 'Metz', '0-4', 'Lorient'),          # -> 当地 05-10 21:00
    ('05-11', '03:00', 'Angers', '1-1', 'Strasbourg'),     # -> 当地 05-10 21:00
    ('05-11', '03:00', 'Monaco', '0-1', 'Lille'),          # -> 当地 05-10 21:00
]

def convert_to_local(bj_date, bj_time):
    """北京时间转当地时间 (减6小时)"""
    bj_hour = int(bj_time.split(':')[0])
    bj_minute = int(bj_time.split(':')[1])

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
            day = 31  # 简化
        local_date = f'{month:02d}-{day:02d}'

    local_time = f'{local_hour:02d}:{bj_minute:02d}'
    return f'2026-{local_date}', local_time

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

def main():
    file_path = Path('D:/football_tools/new_data/leagues/ligue_1/ligue_1_2025-2026.csv')

    rows = []
    with open(file_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        headers = reader.fieldnames
        for row in reader:
            rows.append(row)

    print('修正法甲第33轮比赛日期时间:')
    print()

    updated = 0
    for bj_date, bj_time, home, score, away in MATCHES_ROUND_33:
        local_date, local_time = convert_to_local(bj_date, bj_time)
        home_goals, away_goals, result = parse_score(score)

        for row in rows:
            if row.get('home_team') == home and row.get('away_team') == away:
                old_date = row.get('match_date')
                old_time = row.get('match_time')

                # 更新日期时间
                row['match_date'] = local_date
                row['match_time'] = local_time

                # 更新比分
                if home_goals is not None:
                    row['home_goals'] = str(home_goals)
                    row['away_goals'] = str(away_goals)
                    row['result'] = result
                    row['status'] = 'Finished'

                print(f'  {home} {score} {away}')
                print(f'    北京时间: {bj_date} {bj_time}')
                print(f'    当地时间: {local_date} {local_time}')
                print(f'    原日期: {old_date} {old_time}')
                updated += 1
                break

    # 写回文件
    with open(file_path, 'w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=headers, extrasaction='ignore')
        writer.writeheader()
        writer.writerows(rows)

    print(f'\n修正: {updated} 场')

if __name__ == '__main__':
    main()
