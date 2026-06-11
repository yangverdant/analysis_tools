#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""导入比赛数据到CSV文件"""

import csv
import os

# 要添加的比赛数据（按联赛分组）
matches_to_add = {
    'bundesliga': [
        ['D1', '2026-05-16', '21:30', 'Leverkusen', 'Hamburger SV', 1, 1, 'D', 0, 0, 1.16, 6.70, 8.50, 'Finished'],
        ['D1', '2026-05-16', '21:30', 'Bayern Munich', 'FC Koln', 5, 1, 'H', 3, 1, '', '', '', 'Finished'],
        ['D1', '2026-05-16', '21:30', 'Heidenheim', 'Mainz', 0, 2, 'A', 0, 2, 1.74, 4.05, 3.25, 'Finished'],
        ['D1', '2026-05-16', '21:30', 'St. Pauli', 'Wolfsburg', 1, 3, 'A', 0, 1, 2.46, 3.52, 2.28, 'Finished'],
        ['D1', '2026-05-16', '21:30', 'Union Berlin', 'Augsburg', 4, 0, 'H', 2, 0, 2.50, 3.52, 2.25, 'Finished'],
        ['D1', '2026-05-16', '21:30', 'Frankfurt', 'Stuttgart', 2, 2, 'D', 0, 2, 3.32, 4.30, 1.68, 'Finished'],
        ['D1', '2026-05-16', '21:30', 'Werder Bremen', 'Dortmund', 0, 2, 'A', 0, 0, 3.06, 4.00, 1.81, 'Finished'],
        ['D1', '2026-05-16', '21:30', "M'gladbach", 'Hoffenheim', 4, 0, 'H', 2, 0, 4.30, 4.55, 1.48, 'Finished'],
        ['D1', '2026-05-16', '21:30', 'Freiburg', 'RB Leipzig', 4, 1, 'H', 2, 1, 2.22, 3.80, 2.41, 'Finished'],
    ],
    'j1_league': [
        ['J1', '2026-05-17', '14:00', 'Cerezo Osaka', 'Nagoya Grampus', 6, 1, 'H', 3, 1, 2.37, 3.25, 2.50, 'Finished'],
        ['J1', '2026-05-16', '13:00', 'Mito HollyHock', 'Tokyo Verdy', 0, 1, 'A', 0, 0, 2.20, 2.75, 3.22, 'Finished'],
        ['J1', '2026-05-16', '15:00', 'Urawa Reds', 'FC Tokyo', 0, 0, 'D', 0, 0, 2.86, 2.80, 2.37, 'Finished'],
        ['J1', '2026-05-16', '16:00', 'Yokohama F. Marinos', 'Kashiwa Reysol', 0, 1, 'A', 0, 1, 2.90, 3.20, 2.12, 'Finished'],
    ],
    'k1_league': [
        ['K1', '2026-05-17', '15:40', 'Jeonbuk Hyundai', 'Gimcheon Sangmu', 0, 0, 'D', 0, 0, 1.58, 3.60, 4.58, 'Finished'],
        ['K1', '2026-05-16', '15:30', 'Daejeon Citizen', 'FC Seoul', 1, 2, 'A', 0, 1, 2.92, 3.15, 2.13, 'Finished'],
        ['K1', '2026-05-16', '18:00', 'Incheon United', 'Gwangju FC', 4, 0, 'H', 2, 0, 1.42, 3.55, 6.95, 'Finished'],
    ],
    'fa_cup': [
        ['FA_CUP', '2026-05-16', '22:00', 'Chelsea', 'Man City', 0, 1, 'A', 0, 0, 4.25, 3.72, 1.60, 'Finished'],
    ],
    'primeira_liga': [
        ['P1', '2026-05-17', '01:00', 'Braga', 'Amadora', 2, 2, 'D', 1, 1, 1.57, 3.70, 4.50, 'Finished'],
        ['P1', '2026-05-17', '03:30', 'Sporting CP', 'Gil Vicente', 3, 0, 'H', 2, 0, '', '', '', 'Finished'],
        ['P1', '2026-05-17', '03:30', 'Estoril', 'Benfica', 1, 3, 'A', 0, 3, 9.50, 5.70, 1.18, 'Finished'],
    ],
    'eliteserien': [
        ['NOR', '2026-05-16', '20:00', 'Brann', 'KFUM Oslo', 2, 1, 'H', 2, 0, 1.41, 4.40, 5.20, 'Finished'],
        ['NOR', '2026-05-17', '00:00', 'Bodo/Glimt', 'Tromso', 5, 0, 'H', 1, 0, 1.29, 4.90, 6.70, 'Finished'],
    ],
    'sweden': [
        ['SWE', '2026-05-16', '21:00', 'Halmstads BK', 'IF Elfsborg', 1, 1, 'D', 1, 0, 3.85, 3.20, 1.80, 'Finished'],
        ['SWE', '2026-05-16', '21:00', 'GAIS', 'Degerfors IF', 1, 1, 'D', 1, 0, 1.55, 3.60, 4.85, 'Finished'],
    ],
    'mls': [
        ['MLS', '2026-05-17', '07:30', 'NY Red Bulls', 'NYCFC', 1, 1, 'D', 1, 0, 2.55, 3.46, 2.23, 'Finished'],
        ['MLS', '2026-05-17', '07:30', 'New England', 'Minnesota United', 2, 1, 'H', 1, 1, 2.16, 3.20, 2.83, 'Finished'],
    ],
}

# CSV文件路径映射
csv_paths = {
    'bundesliga': 'd:/football_tools/data/01_europe_leagues/bundesliga/bundesliga_2024-2025.csv',
    'j1_league': 'd:/football_tools/data/05_asia_leagues/j1_league/j1_league_2025.csv',
    'k1_league': 'd:/football_tools/data/05_asia_leagues/k1_league/k1_league_2025-26.csv',
    'fa_cup': 'd:/football_tools/data/02_europe_cups/fa_cup/fa_cup_2024-2025.csv',
    'primeira_liga': 'd:/football_tools/data/01_europe_leagues/primeira_liga/primeira_liga_2024-2025.csv',
    'eliteserien': 'd:/football_tools/data/01_europe_leagues/eliteserien/eliteserien_2025-2026.csv',
    'sweden': 'd:/football_tools/data/01_europe_leagues/allsvenskan/allsvenskan_2025-26.csv',
    'mls': 'd:/football_tools/data/07_north_america/mls/mls_2025.csv',
}

# 写入CSV文件
for league_key, matches in matches_to_add.items():
    csv_path = csv_paths.get(league_key)
    if not csv_path:
        print(f"No CSV path for {league_key}")
        continue

    # 检查文件是否存在
    if not os.path.exists(csv_path):
        print(f"CSV file not found: {csv_path}")
        continue

    # 读取现有数据
    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.reader(f)
        header = next(reader)
        rows = list(reader)

    # 检查是否已存在相同比赛
    existing_keys = set()
    for row in rows:
        if len(row) >= 5:
            key = (row[1], row[3], row[4])  # Date, HomeTeam, AwayTeam
            existing_keys.add(key)

    # 添加新比赛
    added = 0
    for match in matches:
        key = (match[1], match[3], match[4])  # Date, HomeTeam, AwayTeam
        if key not in existing_keys:
            # 构建完整的行（填充空值）
            full_row = [''] * len(header)
            full_row[0] = match[0]   # Div
            full_row[1] = match[1]   # Date
            full_row[2] = match[2]   # Time
            full_row[3] = match[3]   # HomeTeam
            full_row[4] = match[4]   # AwayTeam
            full_row[5] = str(match[5])   # FTHG
            full_row[6] = str(match[6])   # FTAG
            full_row[7] = match[7]   # FTR
            if len(header) > 8:
                full_row[8] = str(match[8]) if match[8] is not None else ''   # HTHG
            if len(header) > 9:
                full_row[9] = str(match[9]) if match[9] is not None else ''   # HTAG
            if len(header) > 23:
                full_row[23] = str(match[10]) if match[10] else ''  # B365H
            if len(header) > 24:
                full_row[24] = str(match[11]) if match[11] else ''  # B365D
            if len(header) > 25:
                full_row[25] = str(match[12]) if match[12] else ''  # B365A
            if len(header) > 66:
                full_row[66] = match[13]  # Status

            rows.append(full_row)
            added += 1

    # 写回文件
    with open(csv_path, 'w', encoding='utf-8', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(header)
        writer.writerows(rows)

    print(f"{league_key}: Added {added} matches to {csv_path}")

print("\nDone!")
