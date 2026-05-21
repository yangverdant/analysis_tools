"""
修正意甲、西甲、德甲的时间 - 北京时间转当地时间
意甲/西甲: -6小时 (UTC+2 夏令时)
德甲: -6小时 (UTC+2 夏令时)
"""
import csv
from pathlib import Path
import sys

if sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')

def convert_to_local(bj_date, bj_time, offset_hours=6):
    """北京时间转当地时间"""
    bj_hour = int(bj_time.split(':')[0])
    bj_minute = int(bj_time.split(':')[1])

    local_hour = bj_hour - offset_hours
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
            day = 31
        local_date = f'{month:02d}-{day:02d}'

    local_time = f'{local_hour:02d}:{bj_minute:02d}'
    return f'2026-{local_date}', local_time

def fix_league_times(league_name, round_nums):
    """修正联赛时间"""
    file_path = Path(f'D:/football_tools/new_data/leagues/{league_name}/{league_name}_2025-2026.csv')

    rows = []
    with open(file_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        headers = reader.fieldnames
        for row in reader:
            rows.append(row)

    print(f'\n{league_name}:')
    updated = 0

    for row in rows:
        if row['round_num'] in round_nums and row['status'] == 'Finished':
            old_date = row['match_date']
            old_time = row['match_time']

            # 提取月-日
            date_parts = old_date.split('-')
            bj_date = f'{date_parts[1]}-{date_parts[2]}'
            bj_time = old_time

            local_date, local_time = convert_to_local(bj_date, bj_time)

            row['match_date'] = local_date
            row['match_time'] = local_time

            print(f"  {row['round_num']}轮 | {old_date} {old_time} -> {local_date} {local_time} | {row['home_team']} vs {row['away_team']}")
            updated += 1

    with open(file_path, 'w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=headers, extrasaction='ignore')
        writer.writeheader()
        writer.writerows(rows)

    print(f'  修正: {updated} 场')

if __name__ == '__main__':
    print('='*60)
    print('修正意甲、西甲、德甲时间 (北京时间 -> 当地时间)')
    print('='*60)

    fix_league_times('serie_a', ['36', '37'])
    fix_league_times('la_liga', ['36', '37'])
    fix_league_times('bundesliga', ['33', '34'])

    print('\n完成!')
