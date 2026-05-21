"""
清洗新采集的瑞典超数据
"""
import csv
from pathlib import Path
import sys

sys.stdout.reconfigure(encoding='utf-8')

DATA_DIR = Path("D:/football_tools/data/01_leagues/sweden")
OUTPUT_DIR = Path("D:/football_tools/new_data/leagues/allsvenskan")

# 完整字段映射
FIELD_MAPPING = {
    'Div': 'division',
    'Date': 'match_date',
    'Time': 'match_time',
    'HomeTeam': 'home_team',
    'AwayTeam': 'away_team',
    'FTHG': 'home_goals',
    'FTAG': 'away_goals',
    'FTR': 'result',
    'Season': 'season',
    'Status': 'status',
    'HTHG': 'home_goals_ht',
    'HTAG': 'away_goals_ht',
    'HTR': 'result_ht',
    'HS': 'home_shots',
    'AS': 'away_shots',
    'HST': 'home_shots_target',
    'AST': 'away_shots_target',
    'HHW': 'home_hit_woodwork',
    'AHW': 'away_hit_woodwork',
    'HC': 'home_corners',
    'AC': 'away_corners',
    'HF': 'home_fouls',
    'AF': 'away_fouls',
    'HO': 'home_offside',
    'AO': 'away_offside',
    'HY': 'home_yellow',
    'AY': 'away_yellow',
    'HR': 'home_red',
    'AR': 'away_red',
    'HBP': 'home_booking_points',
    'ABP': 'away_booking_points',
    'Referee': 'referee',
    'Attendance': 'attendance',
    'B365H': 'b365_home',
    'B365D': 'b365_draw',
    'B365A': 'b365_away',
    'BWH': 'bw_home',
    'BWD': 'bw_draw',
    'BWA': 'bw_away',
    'PSH': 'ps_home',
    'PSD': 'ps_draw',
    'PSA': 'ps_away',
    'WHH': 'wh_home',
    'WHD': 'wh_draw',
    'WHA': 'wh_away',
    'IWH': 'iw_home',
    'IWD': 'iw_draw',
    'IWA': 'iw_away',
    'LBH': 'lb_home',
    'LBD': 'lb_draw',
    'LBA': 'lb_away',
    'VCH': 'vc_home',
    'VCD': 'vc_draw',
    'VCA': 'vc_away',
    'GBH': 'gb_home',
    'GBD': 'gb_draw',
    'GBA': 'gb_away',
    'SBH': 'sb_home',
    'SBD': 'sb_draw',
    'SBA': 'sb_away',
    'SJH': 'sj_home',
    'SJD': 'sj_draw',
    'SJA': 'sj_away',
    'BSH': 'bs_home',
    'BSD': 'bs_draw',
    'BSA': 'bs_away',
    'BFH': 'bf_home',
    'BFD': 'bf_draw',
    'BFA': 'bf_away',
    'BFEH': 'bfe_home',
    'BFED': 'bfe_draw',
    'BFEA': 'bfe_away',
    'BFDH': 'bfd_home',
    'BFDD': 'bfd_draw',
    'BFDA': 'bfd_away',
    'BMGMH': 'bmgm_home',
    'BMGMD': 'bmgm_draw',
    'BMGMA': 'bmgm_away',
    'BVH': 'bv_home',
    'BVD': 'bv_draw',
    'BVA': 'bv_away',
    'CLH': 'cl_home',
    'CLD': 'cl_draw',
    'CLA': 'cl_away',
    '1XBH': 'x1b_home',
    '1XBD': 'x1b_draw',
    '1XBA': 'x1b_away',
    'SOH': 'so_home',
    'SOD': 'so_draw',
    'SOA': 'so_away',
    'SYH': 'sy_home',
    'SYD': 'sy_draw',
    'SYA': 'sy_away',
    'MaxH': 'max_home',
    'MaxD': 'max_draw',
    'MaxA': 'max_away',
    'AvgH': 'avg_home',
    'AvgD': 'avg_draw',
    'AvgA': 'avg_away',
    'B365>2.5': 'b365_over_2_5',
    'B365<2.5': 'b365_under_2_5',
    'P>2.5': 'ps_over_2_5',
    'P<2.5': 'ps_under_2_5',
    'Max>2.5': 'max_over_2_5',
    'Max<2.5': 'max_under_2_5',
    'Avg>2.5': 'avg_over_2_5',
    'Avg<2.5': 'avg_under_2_5',
    'BFE>2.5': 'bfe_over_2_5',
    'BFE<2.5': 'bfe_under_2_5',
    'AHh': 'asian_handicap',
    'B365AHH': 'b365_ah_home',
    'B365AHA': 'b365_ah_away',
    'PAHH': 'ps_ah_home',
    'PAHA': 'ps_ah_away',
    'MaxAHH': 'max_ah_home',
    'MaxAHA': 'max_ah_away',
    'AvgAHH': 'avg_ah_home',
    'AvgAHA': 'avg_ah_away',
    'BFEAHH': 'bfe_ah_home',
    'BFEAHA': 'bfe_ah_away',
    'GBAHH': 'gb_ah_home',
    'GBAHA': 'gb_ah_away',
    'GBAH': 'gb_ah_handicap',
    'B365CH': 'b365_c_home',
    'B365CD': 'b365_c_draw',
    'B365CA': 'b365_c_away',
    'BWCH': 'bw_c_home',
    'BWCD': 'bw_c_draw',
    'BWCA': 'bw_c_away',
    'PSCH': 'ps_c_home',
    'PSCD': 'ps_c_draw',
    'PSCA': 'ps_c_away',
    'WHCH': 'wh_c_home',
    'WHCD': 'wh_c_draw',
    'WHCA': 'wh_c_away',
    'IWCH': 'iw_c_home',
    'IWCD': 'iw_c_draw',
    'IWCA': 'iw_c_away',
    'VCCH': 'vc_c_home',
    'VCCD': 'vc_c_draw',
    'VCCA': 'vc_c_away',
    'LBCH': 'lb_c_home',
    'LBCD': 'lb_c_draw',
    'LBCA': 'lb_c_away',
    'BFCH': 'bf_c_home',
    'BFCD': 'bf_c_draw',
    'BFCA': 'bf_c_away',
    'BFECH': 'bfe_c_home',
    'BFECD': 'bfe_c_draw',
    'BFECA': 'bfe_c_away',
    'BFDCH': 'bfd_c_home',
    'BFDCD': 'bfd_c_draw',
    'BFDCA': 'bfd_c_away',
    'BMGMCH': 'bmgm_c_home',
    'BMGMCD': 'bmgm_c_draw',
    'BMGMCA': 'bmgm_c_away',
    'BVCH': 'bv_c_home',
    'BVCD': 'bv_c_draw',
    'BVCA': 'bv_c_away',
    'CLCH': 'cl_c_home',
    'CLCD': 'cl_c_draw',
    'CLCA': 'cl_c_away',
    '1XBCH': 'x1b_c_home',
    '1XBCD': 'x1b_c_draw',
    '1XBCA': 'x1b_c_away',
    'MaxCH': 'max_c_home',
    'MaxCD': 'max_c_draw',
    'MaxCA': 'max_c_away',
    'AvgCH': 'avg_c_home',
    'AvgCD': 'avg_c_draw',
    'AvgCA': 'avg_c_away',
    'B365C>2.5': 'b365_c_over_2_5',
    'B365C<2.5': 'b365_c_under_2_5',
    'PC>2.5': 'ps_c_over_2_5',
    'PC<2.5': 'ps_c_under_2_5',
    'MaxC>2.5': 'max_c_over_2_5',
    'MaxC<2.5': 'max_c_under_2_5',
    'AvgC>2.5': 'avg_c_over_2_5',
    'AvgC<2.5': 'avg_c_under_2_5',
    'BFEC>2.5': 'bfe_c_over_2_5',
    'BFEC<2.5': 'bfe_c_under_2_5',
    'AHCh': 'asian_handicap_c',
    'B365CAHH': 'b365_c_ah_home',
    'B365CAHA': 'b365_c_ah_away',
    'PCAHH': 'ps_c_ah_home',
    'PCAHA': 'ps_c_ah_away',
    'MaxCAHH': 'max_c_ah_home',
    'MaxCAHA': 'max_c_ah_away',
    'AvgCAHH': 'avg_c_ah_home',
    'AvgCAHA': 'avg_c_ah_away',
    'BFECAHH': 'bfe_c_ah_home',
    'BFECAHA': 'bfe_c_ah_away',
    'Bb1X2': 'bb_1x2_count',
    'BbMxH': 'bb_max_home',
    'BbAvH': 'bb_avg_home',
    'BbMxD': 'bb_max_draw',
    'BbAvD': 'bb_avg_draw',
    'BbMxA': 'bb_max_away',
    'BbAvA': 'bb_avg_away',
    'BbOU': 'bb_ou_count',
    'BbMx>2.5': 'bb_max_over_2_5',
    'BbAv>2.5': 'bb_avg_over_2_5',
    'BbMx<2.5': 'bb_max_under_2_5',
    'BbAv<2.5': 'bb_avg_under_2_5',
    'BbAH': 'bb_ah_count',
    'BbAHh': 'bb_ah_handicap',
    'BbMxAHH': 'bb_max_ah_home',
    'BbAvAHH': 'bb_avg_ah_home',
    'BbMxAHA': 'bb_max_ah_away',
    'BbAvAHA': 'bb_avg_ah_away',
}

STANDARD_FIELDS = [
    'season', 'match_date', 'match_time', 'round_num',
    'division', 'home_team', 'away_team',
    'home_goals', 'away_goals', 'result',
    'status',
    'home_goals_ht', 'away_goals_ht', 'result_ht',
    'home_shots', 'away_shots',
    'home_shots_target', 'away_shots_target',
    'home_hit_woodwork', 'away_hit_woodwork',
    'home_corners', 'away_corners',
    'home_fouls', 'away_fouls',
    'home_offside', 'away_offside',
    'home_yellow', 'away_yellow',
    'home_red', 'away_red',
    'home_booking_points', 'away_booking_points',
    'referee', 'attendance',
    'b365_home', 'b365_draw', 'b365_away',
    'bw_home', 'bw_draw', 'bw_away',
    'ps_home', 'ps_draw', 'ps_away',
    'wh_home', 'wh_draw', 'wh_away',
    'iw_home', 'iw_draw', 'iw_away',
    'lb_home', 'lb_draw', 'lb_away',
    'vc_home', 'vc_draw', 'vc_away',
    'gb_home', 'gb_draw', 'gb_away',
    'sb_home', 'sb_draw', 'sb_away',
    'sj_home', 'sj_draw', 'sj_away',
    'bs_home', 'bs_draw', 'bs_away',
    'bf_home', 'bf_draw', 'bf_away',
    'bfe_home', 'bfe_draw', 'bfe_away',
    'bfd_home', 'bfd_draw', 'bfd_away',
    'bmgm_home', 'bmgm_draw', 'bmgm_away',
    'bv_home', 'bv_draw', 'bv_away',
    'cl_home', 'cl_draw', 'cl_away',
    'x1b_home', 'x1b_draw', 'x1b_away',
    'so_home', 'so_draw', 'so_away',
    'sy_home', 'sy_draw', 'sy_away',
    'max_home', 'max_draw', 'max_away',
    'avg_home', 'avg_draw', 'avg_away',
    'b365_over_2_5', 'b365_under_2_5',
    'ps_over_2_5', 'ps_under_2_5',
    'max_over_2_5', 'max_under_2_5',
    'avg_over_2_5', 'avg_under_2_5',
    'bfe_over_2_5', 'bfe_under_2_5',
    'asian_handicap',
    'b365_ah_home', 'b365_ah_away',
    'ps_ah_home', 'ps_ah_away',
    'max_ah_home', 'max_ah_away',
    'avg_ah_home', 'avg_ah_away',
    'bfe_ah_home', 'bfe_ah_away',
    'gb_ah_home', 'gb_ah_away',
    'gb_ah_handicap',
    'b365_c_home', 'b365_c_draw', 'b365_c_away',
    'bw_c_home', 'bw_c_draw', 'bw_c_away',
    'ps_c_home', 'ps_c_draw', 'ps_c_away',
    'wh_c_home', 'wh_c_draw', 'wh_c_away',
    'iw_c_home', 'iw_c_draw', 'iw_c_away',
    'vc_c_home', 'vc_c_draw', 'vc_c_away',
    'lb_c_home', 'lb_c_draw', 'lb_c_away',
    'bf_c_home', 'bf_c_draw', 'bf_c_away',
    'bfe_c_home', 'bfe_c_draw', 'bfe_c_away',
    'bfd_c_home', 'bfd_c_draw', 'bfd_c_away',
    'bmgm_c_home', 'bmgm_c_draw', 'bmgm_c_away',
    'bv_c_home', 'bv_c_draw', 'bv_c_away',
    'cl_c_home', 'cl_c_draw', 'cl_c_away',
    'x1b_c_home', 'x1b_c_draw', 'x1b_c_away',
    'max_c_home', 'max_c_draw', 'max_c_away',
    'avg_c_home', 'avg_c_draw', 'avg_c_away',
    'b365_c_over_2_5', 'b365_c_under_2_5',
    'ps_c_over_2_5', 'ps_c_under_2_5',
    'max_c_over_2_5', 'max_c_under_2_5',
    'avg_c_over_2_5', 'avg_c_under_2_5',
    'bfe_c_over_2_5', 'bfe_c_under_2_5',
    'asian_handicap_c',
    'b365_c_ah_home', 'b365_c_ah_away',
    'ps_c_ah_home', 'ps_c_ah_away',
    'max_c_ah_home', 'max_c_ah_away',
    'avg_c_ah_home', 'avg_c_ah_away',
    'bfe_c_ah_home', 'bfe_c_ah_away',
    'bb_1x2_count',
    'bb_max_home', 'bb_avg_home',
    'bb_max_draw', 'bb_avg_draw',
    'bb_max_away', 'bb_avg_away',
    'bb_ou_count',
    'bb_max_over_2_5', 'bb_avg_over_2_5',
    'bb_max_under_2_5', 'bb_avg_under_2_5',
    'bb_ah_count', 'bb_ah_handicap',
    'bb_max_ah_home', 'bb_avg_ah_home',
    'bb_max_ah_away', 'bb_avg_ah_away',
]

def parse_date(date_str):
    if not date_str:
        return None
    try:
        if '/' in date_str:
            parts = date_str.split('/')
            if len(parts) == 3:
                day, month, year = parts
                if len(year) == 2:
                    year = '20' + year if int(year) < 50 else '19' + year
                return f'{year}-{month}-{day}'
        if len(date_str) == 10 and '-' in date_str:
            return date_str
        return date_str
    except:
        return date_str

def calculate_round(matches, matches_per_round=8):
    date_counts = {}
    for m in matches:
        date = m.get('match_date')
        if date and date != 'null':
            if date not in date_counts:
                date_counts[date] = 0
            date_counts[date] += 1
    sorted_dates = sorted(date_counts.keys())
    rounds = {}
    round_num = 1
    current_round_matches = 0
    for date in sorted_dates:
        rounds[date] = round_num
        current_round_matches += date_counts[date]
        if current_round_matches >= matches_per_round:
            round_num += 1
            current_round_matches = 0
    return rounds

def clean_file(input_path, output_path, season):
    rows = []
    try:
        with open(input_path, 'r', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)
            for row in reader:
                new_row = {}
                for old_key, value in row.items():
                    if old_key is None:
                        continue
                    old_key_clean = old_key.strip().replace('﻿', '') if old_key else ''
                    if not old_key_clean or old_key_clean.startswith('Unnamed'):
                        continue
                    if old_key_clean in FIELD_MAPPING:
                        new_key = FIELD_MAPPING[old_key_clean]
                        if value == '' or value is None:
                            new_row[new_key] = 'null'
                        else:
                            new_row[new_key] = value

                new_row['season'] = season
                if 'match_date' in new_row and new_row['match_date']:
                    new_row['match_date'] = parse_date(new_row['match_date'])
                rows.append(new_row)

        rounds = calculate_round(rows)
        for row in rows:
            if row.get('match_date') and row['match_date'] != 'null':
                row['round_num'] = rounds.get(row['match_date'], None)
            else:
                row['round_num'] = None

        for row in rows:
            status = row.get('status', '').strip()
            if not status or status == 'null':
                home_goals = row.get('home_goals', '')
                away_goals = row.get('away_goals', '')
                if home_goals and home_goals != 'null' and away_goals and away_goals != 'null':
                    row['status'] = 'Finished'
                else:
                    row['status'] = 'Scheduled'

        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, 'w', encoding='utf-8', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=STANDARD_FIELDS, extrasaction='ignore')
            writer.writeheader()
            writer.writerows(rows)
        return len(rows)
    except Exception as e:
        print(f'  错误: {e}')
        return 0

if __name__ == '__main__':
    print('='*60)
    print('清洗瑞典超数据')
    print('='*60)

    csv_files = sorted(DATA_DIR.glob('allsvenskan_*.csv'))
    total = 0

    for csv_file in csv_files:
        if csv_file.name == 'allsvenskan_raw.csv':
            continue

        # 从文件名提取年份
        year = csv_file.stem.replace('allsvenskan_', '')
        if year.isdigit():
            year_int = int(year)
            season = f'{year_int}-{str(year_int+1)[-2:]}'
        else:
            season = year

        output_file = OUTPUT_DIR / f'allsvenskan_{season}.csv'
        count = clean_file(csv_file, output_file, season)
        if count > 0:
            print(f'  {csv_file.name} -> {season}: {count}场')
            total += count

    print(f'\n总计: {total}场')
