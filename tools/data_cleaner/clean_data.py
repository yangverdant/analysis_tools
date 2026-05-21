"""
数据清洗脚本 - 将原始CSV数据转换为标准格式
"""
import os
import csv
import re
from pathlib import Path
from datetime import datetime
from collections import defaultdict
import sys

# 确保输出编码正确
if sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')

# 目录配置
DATA_DIR = Path("D:/football_tools/data/01_europe_leagues")
OUTPUT_DIR = Path("D:/football_tools/new_data/leagues")

# 中文球队名 -> 英文标准名映射 (用于统一球队名)
TEAM_NAME_CN_TO_EN = {
    '勒沃库森': 'Leverkusen',
    '多特蒙德': 'Dortmund',
    '奥格斯堡': 'Augsburg',
    '斯图加特': 'Stuttgart',
    '法兰克福': 'Frankfurt',
    '门兴': 'M\'gladbach',
    '霍芬海姆': 'Hoffenheim',
    '不来梅': 'Werder Bremen',
    '圣保利': 'St Pauli',
    'RB莱比锡': 'RB Leipzig',
}

# 标准字段映射 (原字段 -> 标准字段)
FIELD_MAPPING = {
    # 核心比赛信息
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

    # 半场数据
    'HTHG': 'home_goals_ht',
    'HTAG': 'away_goals_ht',
    'HTR': 'result_ht',

    # 比赛统计
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

    # 其他信息
    'Referee': 'referee',
    'Attendance': 'attendance',

    # 开场赔率 - Bet365
    'B365H': 'b365_home',
    'B365D': 'b365_draw',
    'B365A': 'b365_away',

    # 开场赔率 - Betway
    'BWH': 'bw_home',
    'BWD': 'bw_draw',
    'BWA': 'bw_away',

    # 开场赔率 - Pinnacle
    'PSH': 'ps_home',
    'PSD': 'ps_draw',
    'PSA': 'ps_away',

    # 开场赔率 - William Hill
    'WHH': 'wh_home',
    'WHD': 'wh_draw',
    'WHA': 'wh_away',

    # 开场赔率 - Interwetten
    'IWH': 'iw_home',
    'IWD': 'iw_draw',
    'IWA': 'iw_away',

    # 开场赔率 - Ladbrokes
    'LBH': 'lb_home',
    'LBD': 'lb_draw',
    'LBA': 'lb_away',

    # 开场赔率 - VC Bet
    'VCH': 'vc_home',
    'VCD': 'vc_draw',
    'VCA': 'vc_away',

    # 开场赔率 - Gamebookers
    'GBH': 'gb_home',
    'GBD': 'gb_draw',
    'GBA': 'gb_away',

    # 开场赔率 - Sportingbet
    'SBH': 'sb_home',
    'SBD': 'sb_draw',
    'SBA': 'sb_away',

    # 开场赔率 - Stan James
    'SJH': 'sj_home',
    'SJD': 'sj_draw',
    'SJA': 'sj_away',

    # 开场赔率 - Blue Square
    'BSH': 'bs_home',
    'BSD': 'bs_draw',
    'BSA': 'bs_away',

    # 开场赔率 - Betfair
    'BFH': 'bf_home',
    'BFD': 'bf_draw',
    'BFA': 'bf_away',

    # 开场赔率 - Betfair Exchange
    'BFEH': 'bfe_home',
    'BFED': 'bfe_draw',
    'BFEA': 'bfe_away',

    # 开场赔率 - Betfair Exchange (欧洲)
    'BFDH': 'bfd_home',
    'BFDD': 'bfd_draw',
    'BFDA': 'bfd_away',

    # 开场赔率 - BetMGM
    'BMGMH': 'bmgm_home',
    'BMGMD': 'bmgm_draw',
    'BMGMA': 'bmgm_away',

    # 开场赔率 - Bwin
    'BVH': 'bv_home',
    'BVD': 'bv_draw',
    'BVA': 'bv_away',

    # 开场赔率 - CloudBet
    'CLH': 'cl_home',
    'CLD': 'cl_draw',
    'CLA': 'cl_away',

    # 开场赔率 - 1xBet
    '1XBH': 'x1b_home',
    '1XBD': 'x1b_draw',
    '1XBA': 'x1b_away',

    # 开场赔率 - Sporting Odds
    'SOH': 'so_home',
    'SOD': 'so_draw',
    'SOA': 'so_away',
    'SYH': 'sy_home',
    'SYD': 'sy_draw',
    'SYA': 'sy_away',

    # 最高/平均赔率
    'MaxH': 'max_home',
    'MaxD': 'max_draw',
    'MaxA': 'max_away',
    'AvgH': 'avg_home',
    'AvgD': 'avg_draw',
    'AvgA': 'avg_away',

    # 大小球赔率
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

    # 亚盘赔率
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

    # 收盘赔率 - Bet365
    'B365CH': 'b365_c_home',
    'B365CD': 'b365_c_draw',
    'B365CA': 'b365_c_away',

    # 收盘赔率 - Betway
    'BWCH': 'bw_c_home',
    'BWCD': 'bw_c_draw',
    'BWCA': 'bw_c_away',

    # 收盘赔率 - Pinnacle
    'PSCH': 'ps_c_home',
    'PSCD': 'ps_c_draw',
    'PSCA': 'ps_c_away',

    # 收盘赔率 - William Hill
    'WHCH': 'wh_c_home',
    'WHCD': 'wh_c_draw',
    'WHCA': 'wh_c_away',

    # 收盘赔率 - Interwetten
    'IWCH': 'iw_c_home',
    'IWCD': 'iw_c_draw',
    'IWCA': 'iw_c_away',

    # 收盘赔率 - VC Bet
    'VCCH': 'vc_c_home',
    'VCCD': 'vc_c_draw',
    'VCCA': 'vc_c_away',

    # 收盘赔率 - Ladbrokes
    'LBCH': 'lb_c_home',
    'LBCD': 'lb_c_draw',
    'LBCA': 'lb_c_away',

    # 收盘赔率 - Betfair
    'BFCH': 'bf_c_home',
    'BFCD': 'bf_c_draw',
    'BFCA': 'bf_c_away',

    # 收盘赔率 - Betfair Exchange
    'BFECH': 'bfe_c_home',
    'BFECD': 'bfe_c_draw',
    'BFECA': 'bfe_c_away',

    # 收盘赔率 - Betfair Exchange (欧洲)
    'BFDCH': 'bfd_c_home',
    'BFDCD': 'bfd_c_draw',
    'BFDCA': 'bfd_c_away',

    # 收盘赔率 - BetMGM
    'BMGMCH': 'bmgm_c_home',
    'BMGMCD': 'bmgm_c_draw',
    'BMGMCA': 'bmgm_c_away',

    # 收盘赔率 - Bwin
    'BVCH': 'bv_c_home',
    'BVCD': 'bv_c_draw',
    'BVCA': 'bv_c_away',

    # 收盘赔率 - CloudBet
    'CLCH': 'cl_c_home',
    'CLCD': 'cl_c_draw',
    'CLCA': 'cl_c_away',

    # 收盘赔率 - 1xBet
    '1XBCH': 'x1b_c_home',
    '1XBCD': 'x1b_c_draw',
    '1XBCA': 'x1b_c_away',

    # 收盘最高/平均赔率
    'MaxCH': 'max_c_home',
    'MaxCD': 'max_c_draw',
    'MaxCA': 'max_c_away',
    'AvgCH': 'avg_c_home',
    'AvgCD': 'avg_c_draw',
    'AvgCA': 'avg_c_away',

    # 收盘大小球
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

    # 收盘亚盘
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

    # Bookball 统计
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

# 标准字段列表 (按顺序)
STANDARD_FIELDS = [
    # 核心信息
    'season', 'match_date', 'match_time', 'round_num',
    'division', 'home_team', 'away_team',
    'home_goals', 'away_goals', 'result',
    'status',

    # 半场
    'home_goals_ht', 'away_goals_ht', 'result_ht',

    # 统计
    'home_shots', 'away_shots',
    'home_shots_target', 'away_shots_target',
    'home_hit_woodwork', 'away_hit_woodwork',
    'home_corners', 'away_corners',
    'home_fouls', 'away_fouls',
    'home_offside', 'away_offside',
    'home_yellow', 'away_yellow',
    'home_red', 'away_red',
    'home_booking_points', 'away_booking_points',

    # 其他
    'referee', 'attendance',

    # 开场赔率 - 各博彩公司
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

    # 大小球赔率
    'b365_over_2_5', 'b365_under_2_5',
    'ps_over_2_5', 'ps_under_2_5',
    'max_over_2_5', 'max_under_2_5',
    'avg_over_2_5', 'avg_under_2_5',
    'bfe_over_2_5', 'bfe_under_2_5',

    # 亚盘赔率
    'asian_handicap',
    'b365_ah_home', 'b365_ah_away',
    'ps_ah_home', 'ps_ah_away',
    'max_ah_home', 'max_ah_away',
    'avg_ah_home', 'avg_ah_away',
    'bfe_ah_home', 'bfe_ah_away',
    'gb_ah_home', 'gb_ah_away',
    'gb_ah_handicap',

    # 收盘赔率 - 各博彩公司
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

    # 收盘大小球
    'b365_c_over_2_5', 'b365_c_under_2_5',
    'ps_c_over_2_5', 'ps_c_under_2_5',
    'max_c_over_2_5', 'max_c_under_2_5',
    'avg_c_over_2_5', 'avg_c_under_2_5',
    'bfe_c_over_2_5', 'bfe_c_under_2_5',

    # 收盘亚盘
    'asian_handicap_c',
    'b365_c_ah_home', 'b365_c_ah_away',
    'ps_c_ah_home', 'ps_c_ah_away',
    'max_c_ah_home', 'max_c_ah_away',
    'avg_c_ah_home', 'avg_c_ah_away',
    'bfe_c_ah_home', 'bfe_c_ah_away',

    # Bookball 统计
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


def parse_date(date_str, season):
    """解析日期字符串"""
    if not date_str:
        return None

    # 处理不同日期格式
    # 格式1: DD/MM/YYYY 或 DD-MM-YYYY
    # 格式2: YYYY-MM-DD
    # 格式3: YY-MM-DD (需要结合season推断年份)

    try:
        # 尝试 YYYY-MM-DD 格式
        if len(date_str) == 10 and '-' in date_str:
            return datetime.strptime(date_str, '%Y-%m-%d').strftime('%Y-%m-%d')

        # 尝试 YY-MM-DD 格式 (如 00-08-19, 15-08-07)
        if len(date_str) == 8 and '-' in date_str:
            parts = date_str.split('-')
            yy = int(parts[0])
            # YY 表示年份的后两位，直接加 2000
            # 如 00 -> 2000, 15 -> 2015, 24 -> 2024
            if yy < 100:
                year = 2000 + yy
            else:
                year = yy
            return f"{year}-{parts[1]}-{parts[2]}"

        # 尝试 DD/MM/YYYY 格式
        if '/' in date_str:
            parts = date_str.split('/')
            if len(parts) == 3:
                day, month, year = parts
                if len(year) == 2:
                    year = '20' + year if int(year) < 50 else '19' + year
                return f"{year}-{month}-{day}"

        return date_str
    except:
        return date_str


def calculate_round(matches, league_name):
    """根据日期计算轮次 - 每轮比赛数量由联赛球队数决定"""
    # 不同联赛每轮比赛数量 (球队数 / 2)
    # 英超: 20支球队, 每轮10场
    # 西甲: 20支球队, 每轮10场
    # 德甲: 18支球队, 每轮9场
    # 意甲: 20支球队, 每轮10场 (部分赛季18队, 9场)
    # 法甲: 18支球队, 每轮9场 (部分赛季20队, 10场)

    matches_per_round = {
        'premier_league': 10,
        'la_liga': 10,
        'bundesliga': 9,
        'serie_a': 10,
        'ligue_1': 9,
        'championship': 12,
        'league_one': 12,
        'league_two': 12,
        'eredivisie': 9,
        'primeira_liga': 9,
        'segunda_division': 11,
        'serie_b': 10,
        'ligue_2': 9,
        'jupiler_league': 11,
        'super_lig': 10,
        'superleague': 10,
        'bundesliga_2': 9,
        'bundesliga_3': 10,
        'scotland_premier': 6,
        'scotland_div1': 5,
        'scotland_div2': 5,
        'scotland_div3': 5,
        'nb1': 8,
        'gambrinus_liga': 8,
        'super_league_swiss': 10,
        'swiss_2': 10,
        'premier_league_russia': 8,
        'russia_2': 9,
        'turkey_2': 9,
        'bundesliga_austria': 6,
        'austria_2': 6,
        'allsvenskan': 8,
        'veikkausliiga': 6,
        # 亚洲联赛
        'j1_league': 9,   # 日本J1: 18队
        'j2_league': 11,  # 日本J2: 22队
        'k1_league': 6,   # 韩国K1: 12队
        'k2_league': 6,   # 韩国K2: 12队
        'csl': 8,         # 中超: 16队
        'a_league': 6,    # 澳超: 12队
        'saudi_pro': 8,   # 沙特超: 16队
    }

    target_per_round = matches_per_round.get(league_name, 10)

    # 按日期统计比赛数量
    date_counts = {}
    for m in matches:
        date = m.get('match_date')
        if date and date != 'null':
            if date not in date_counts:
                date_counts[date] = 0
            date_counts[date] += 1

    # 按日期排序
    sorted_dates = sorted(date_counts.keys())

    # 计算轮次 - 累计比赛数达到每轮目标时进入下一轮
    rounds = {}
    round_num = 1
    current_round_matches = 0

    for date in sorted_dates:
        rounds[date] = round_num
        current_round_matches += date_counts[date]

        # 当累计比赛数达到每轮目标时，进入下一轮
        if current_round_matches >= target_per_round:
            round_num += 1
            current_round_matches = 0

    return rounds


def extract_season_from_filename(filename):
    """从文件名提取赛季"""
    name = filename.replace('.csv', '')

    # 跳过 _all 文件
    if name.endswith('_all'):
        return None

    # 提取赛季 (最后部分)
    parts = name.split('_')
    if len(parts) >= 1:
        season = parts[-1]
        if '-' in season:  # 格式如 2024-2025
            return season

    return None


def clean_csv_file(input_path, output_path, league_name):
    """清洗单个CSV文件"""
    season_from_file = extract_season_from_filename(input_path.name)

    rows = []

    try:
        with open(input_path, 'r', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)
            original_headers = reader.fieldnames or []

            for row in reader:
                new_row = {}

                # 映射字段
                for old_key, value in row.items():
                    # 处理空键名
                    if old_key is None:
                        continue
                    old_key_clean = old_key.strip().replace('﻿', '') if old_key else ''

                    # 跳过 Unnamed 字段或空字段名
                    if not old_key_clean or old_key_clean.startswith('Unnamed'):
                        continue

                    if old_key_clean in FIELD_MAPPING:
                        new_key = FIELD_MAPPING[old_key_clean]

                        # 处理空值 - 用 'null' 字符串替代
                        if value == '' or value is None:
                            new_row[new_key] = 'null'
                        else:
                            # 处理球队名 - 将中文队名转换为英文标准名
                            if new_key in ('home_team', 'away_team') and value in TEAM_NAME_CN_TO_EN:
                                new_row[new_key] = TEAM_NAME_CN_TO_EN[value]
                            else:
                                new_row[new_key] = value

                # 处理赛季
                if 'season' not in new_row or new_row['season'] is None:
                    new_row['season'] = season_from_file

                # 处理日期
                if 'match_date' in new_row and new_row['match_date']:
                    new_row['match_date'] = parse_date(new_row['match_date'], new_row['season'])

                rows.append(new_row)

        # 计算轮次 - 根据实际球队数量动态计算
        rounds = calculate_round(rows, league_name)
        for row in rows:
            if row.get('match_date') and row['match_date'] != 'null':
                row['round_num'] = rounds.get(row['match_date'], None)
            else:
                row['round_num'] = None

        # 推断比赛状态 - 如果 status 为空，根据比分判断
        for row in rows:
            status = row.get('status', '').strip()
            if not status or status == 'null':
                # 根据比分判断状态
                home_goals = row.get('home_goals', '')
                away_goals = row.get('away_goals', '')
                result = row.get('result', '')

                if home_goals and home_goals != 'null' and away_goals and away_goals != 'null':
                    row['status'] = 'Finished'
                else:
                    row['status'] = 'Scheduled'

        # 写入清洗后的文件
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with open(output_path, 'w', encoding='utf-8', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=STANDARD_FIELDS, extrasaction='ignore')
            writer.writeheader()
            writer.writerows(rows)

        return {
            'input': str(input_path),
            'output': str(output_path),
            'rows': len(rows),
            'season': season_from_file
        }

    except Exception as e:
        return {
            'input': str(input_path),
            'error': str(e)
        }


def process_league(league_name):
    """处理单个联赛的所有文件"""
    league_path = DATA_DIR / league_name
    output_path = OUTPUT_DIR / league_name

    if not league_path.exists():
        print(f"联赛目录不存在: {league_name}")
        return []

    csv_files = list(league_path.glob('*.csv'))

    # 跳过 _all 文件，只处理单赛季文件
    single_season_files = [f for f in csv_files if not f.name.endswith('_all.csv')]

    print(f"\n处理 {league_name}:")
    print(f"  文件数: {len(single_season_files)}")
    print("-" * 60)

    results = []
    success = 0
    errors = 0

    for i, file_path in enumerate(sorted(single_season_files), 1):
        output_file = output_path / file_path.name
        result = clean_csv_file(file_path, output_file, league_name)

        if 'error' in result:
            print(f"  [{i:2}/{len(single_season_files)}] X {file_path.name} - {result['error']}")
            errors += 1
        else:
            print(f"  [{i:2}/{len(single_season_files)}] OK {file_path.name} - {result['rows']} rows, season: {result['season']}")
            success += 1

        results.append(result)

    print(f"  完成: 成功 {success}, 错误 {errors}")

    return results


def process_big_five():
    """处理五大联赛"""
    big_five = [
        'premier_league',    # 英超
        'la_liga',           # 西甲
        'bundesliga',        # 德甲
        'serie_a',           # 意甲
        'ligue_1',           # 法甲
    ]

    print("=" * 60)
    print("清洗五大联赛数据")
    print("=" * 60)

    all_results = {}

    for league in big_five:
        results = process_league(league)
        all_results[league] = results

    print("\n" + "=" * 60)
    print("全部完成!")
    print("=" * 60)

    return all_results


def process_all_leagues():
    """处理所有联赛"""
    all_leagues = [d.name for d in DATA_DIR.iterdir() if d.is_dir()]
    all_leagues.sort()

    print("=" * 60)
    print(f"清洗所有联赛数据 (共 {len(all_leagues)} 个)")
    print("=" * 60)

    all_results = {}

    for league in all_leagues:
        league_path = DATA_DIR / league
        csv_files = list(league_path.glob('*.csv'))
        if len(csv_files) > 0:
            results = process_league(league)
            all_results[league] = results

    print("\n" + "=" * 60)
    print("全部完成!")
    print("=" * 60)

    return all_results


if __name__ == '__main__':
    import sys

    if len(sys.argv) > 1:
        cmd = sys.argv[1]
        if cmd == 'all':
            process_big_five()
        elif cmd == 'all_leagues':
            process_all_leagues()
        elif cmd == 'one':
            if len(sys.argv) > 2:
                process_league(sys.argv[2])
            else:
                print("请指定联赛名称")
        elif cmd == 'test':
            # 测试单个文件
            test_file = DATA_DIR / 'premier_league' / 'premier_league_2024-2025.csv'
            test_output = OUTPUT_DIR / 'premier_league' / 'test.csv'
            result = clean_csv_file(test_file, test_output, 'premier_league')
            print(f"测试结果: {result}")
        else:
            print(f"未知命令: {cmd}")
    else:
        print("\n数据清洗工具")
        print("=" * 40)
        print("用法:")
        print("  python clean_data.py all      - 清洗五大联赛")
        print("  python clean_data.py one <联赛名> - 清洗单个联赛")
        print("  python clean_data.py test     - 测试单个文件")
        print("=" * 40)