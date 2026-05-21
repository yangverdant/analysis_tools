#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""转换CSV文件中的北京时间到当地时间"""

import csv
import os
from datetime import datetime, timedelta

# 联赛时区偏移（北京时间UTC+8 到当地时间的偏移）
# 值为负数表示北京时间减去该值得到当地时间
TIMEZONE_OFFSETS = {
    # 欧洲联赛（夏令时期间）
    'D1': -6,  # 德甲 德国 UTC+1/+2
    'D2': -6,  # 德乙
    'E0': -7,  # 英超 英国 UTC+0/+1
    'E1': -7,  # 英冠
    'E2': -7,  # 英甲
    'E3': -7,  # 英乙
    'E4': -7,  # 英非联
    'SP1': -6, # 西甲 西班牙 UTC+1/+2
    'SP2': -6, # 西乙
    'I1': -6,  # 意甲 意大利 UTC+1/+2
    'I2': -6,  # 意乙
    'F1': -6,  # 法甲 法国 UTC+1/+2
    'FRA2': -6, # 法乙
    'FRA3': -6, # 法丙
    'NED': -6, # 荷甲 荷兰 UTC+1/+2
    'P1': -7,  # 葡超 葡萄牙 UTC+0/+1
    'P2': -7,  # 葡甲
    'TUR': -5, # 土超 土耳其 UTC+3
    'BEL': -6, # 比甲 比利时 UTC+1/+2
    'SWI': -6, # 瑞士超 UTC+1/+2
    'AUT': -6, # 奥甲 奥地利 UTC+1/+2
    'GRE': -5, # 希腊超 UTC+2/+3
    'CRO': -6, # 克罗甲 UTC+1/+2
    'SRB': -5, # 塞尔超 UTC+1/+2
    'CZE': -6, # 捷甲 UTC+1/+2
    'POL': -6, # 波兰甲 UTC+1/+2
    'DEN': -6, # 丹超 UTC+1/+2
    'NOR': -6, # 挪超 UTC+1/+2
    'SWE': -6, # 瑞超 UTC+1/+2
    'FIN': -5, # 芬超 UTC+2/+3
    'RUS': -4, # 俄超 UTC+3/+4
    'SCO': -7, # 苏超 UTC+0/+1
    'ROU': -5, # 罗甲 UTC+2/+3

    # 亚洲联赛
    'J1': -1,  # J联赛 日本 UTC+9
    'J2': -1,  # J2联赛
    'K1': -1,  # K联赛 韩国 UTC+9
    'K2': -1,  # K2联赛
    'CHN': 0,  # 中超 中国 UTC+8
    'SAU': -5, # 沙特联 UTC+3
    'THA': -1, # 泰超 UTC+7

    # 南美联赛
    'BRA1': -11, # 巴西甲 巴西东部 UTC-3
    'BRA2': -11, # 巴西乙
    'ARG': -11,  # 阿甲 阿根廷 UTC-3
    'URU': -11,  # 乌拉甲 UTC-3
    'ECU': -13,  # 厄瓜甲 UTC-5
    'BOL': -12,  # 玻利甲 UTC-4

    # 北美联赛
    'MLS': -12, # 美职联 东部时间 UTC-4/-5 (简化处理)
    'MEX': -14, # 墨联 UTC-6

    # 其他
    'FA_CUP': -7, # 足总杯 英国
    'ACL2': -1,   # 亚冠
}

# CSV文件路径映射
CSV_PATHS = {
    'D1': 'd:/football_tools/data/01_europe_leagues/bundesliga/bundesliga_2024-2025.csv',
    'E0': 'd:/football_tools/data/01_europe_leagues/premier_league/premier_league_2024-2025.csv',
    'SP1': 'd:/football_tools/data/01_europe_leagues/la_liga/la_liga_2024-2025.csv',
    'I1': 'd:/football_tools/data/01_europe_leagues/serie_a/serie_a_2024-2025.csv',
    'F1': 'd:/football_tools/data/01_europe_leagues/ligue_1/ligue_1_2024-2025.csv',
    'NED': 'd:/football_tools/data/01_europe_leagues/eredivisie/eredivisie_2024-2025.csv',
    'P1': 'd:/football_tools/data/01_europe_leagues/primeira_liga/primeira_liga_2024-2025.csv',
    'TUR': 'd:/football_tools/data/01_europe_leagues/super_lig/super_lig_2024-2025.csv',
    'BEL': 'd:/football_tools/data/01_europe_leagues/jupiler_league/jupiler_league_2024-2025.csv',
    'NOR': 'd:/football_tools/data/01_europe_leagues/eliteserien/eliteserien_2024-2025.csv',
    'SWE': 'd:/football_tools/data/01_europe_leagues/allsvenskan/allsvenskan_2024-2025.csv',
    'J1': 'd:/football_tools/data/05_asia_leagues/j1_league/j1_league_2025.csv',
    'K1': 'd:/football_tools/data/05_asia_leagues/k1_league/k1_league_2025-26.csv',
    'CHN': 'd:/football_tools/data/05_asia_leagues/csl/csl_2025.csv',
    'SAU': 'd:/football_tools/data/05_asia_leagues/saudi_pro/saudi_pro_2025-26.csv',
    'MLS': 'd:/football_tools/data/07_north_america/mls/mls_2025.csv',
    'BRA1': 'd:/football_tools/data/06_south_america/serie_a_brazil/serie_a_brazil_2025-2026.csv',
    'ARG': 'd:/football_tools/data/06_south_america/primera_division_argentina/primera_division_argentina_2025.csv',
    'FA_CUP': 'd:/football_tools/data/02_europe_cups/fa_cup/fa_cup_2024-2025.csv',
}

def convert_time(beijing_time_str, offset):
    """将北京时间转换为当地时间"""
    try:
        # 解析北京时间 HH:MM
        hours, minutes = map(int, beijing_time_str.split(':'))
        beijing_total_minutes = hours * 60 + minutes

        # 应用偏移
        local_total_minutes = beijing_total_minutes + offset * 60

        # 处理跨日情况
        if local_total_minutes < 0:
            local_total_minutes += 24 * 60
        elif local_total_minutes >= 24 * 60:
            local_total_minutes -= 24 * 60

        local_hours = local_total_minutes // 60
        local_minutes = local_total_minutes % 60

        return f"{local_hours:02d}:{local_minutes:02d}"
    except:
        return beijing_time_str

def fix_csv_times(csv_path, league_code):
    """修复CSV文件中的时间"""
    if not os.path.exists(csv_path):
        print(f"CSV not found: {csv_path}")
        return 0

    offset = TIMEZONE_OFFSETS.get(league_code, 0)
    if offset == 0:
        print(f"{league_code}: No timezone offset needed (offset=0)")
        return 0

    # 读取CSV
    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.reader(f)
        header = next(reader)
        rows = list(reader)

    # 查找时间列索引
    time_idx = 2  # Time列通常在索引2

    # 查找2026年5月的比赛（刚导入的比赛）
    fixed = 0
    for row in rows:
        if len(row) <= time_idx:
            continue

        date = row[1]
        time_str = row[time_idx]

        # 只处理2026年5月的比赛
        if date.startswith('2026-05'):
            # 检查时间是否是北京时间（通常是晚上时间如21:30, 03:00等）
            try:
                hours = int(time_str.split(':')[0])
                # 北京时间通常在晚上（18-24）或凌晨（00-08）
                # 如果时间是典型的北京时间范围，进行转换
                original_time = time_str
                new_time = convert_time(time_str, offset)

                if new_time != original_time:
                    row[time_idx] = new_time
                    fixed += 1
                    print(f"  {date} {original_time} -> {new_time} (offset={offset})")
            except:
                continue

    # 写回文件
    if fixed > 0:
        with open(csv_path, 'w', encoding='utf-8', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(header)
            writer.writerows(rows)

    return fixed

def main():
    """主函数"""
    print("Converting Beijing time to local time in CSV files...")
    print()

    total_fixed = 0
    for league_code, csv_path in CSV_PATHS.items():
        fixed = fix_csv_times(csv_path, league_code)
        if fixed > 0:
            print(f"{league_code}: Fixed {fixed} matches")
            total_fixed += fixed

    print(f"\nTotal fixed: {total_fixed} matches")

if __name__ == '__main__':
    main()