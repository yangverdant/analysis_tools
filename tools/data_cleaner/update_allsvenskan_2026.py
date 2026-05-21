"""
更新瑞典超2026赛季数据
"""
import csv
from pathlib import Path
import sys

sys.stdout.reconfigure(encoding='utf-8')

DATA_FILE = Path("D:/football_tools/data/raw/allsvenskan_2026.txt")
OUTPUT_FILE = Path("D:/football_tools/new_data/leagues/allsvenskan/allsvenskan_2025-26.csv")

TEAM_MAPPING = {
    '哈马比': 'Hammarby',
    '米亚尔比': 'Mjallby',
    '代格福什': 'Degerfors',
    '天狼星': 'Sirius',
    '索尔纳': 'AIK',
    '哈尔姆斯塔德': 'Halmstad',
    '卡尔马': 'Kalmar',
    '韦斯特罗斯': 'Vasteras SK',
    '厄尔格里特': 'Orebro',
    '马尔默': 'Malmo FF',
    '赫根': 'Hacken',
    '布鲁马波卡纳': 'Brommapojkarna',
    '埃尔夫斯堡': 'Elfsborg',
    '哥德堡': 'IFK Goteborg',
    '哥德堡盖斯': 'GAIS',
    '佐加顿斯': 'Djurgarden',
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

def parse_data(data_text):
    rows = []
    for line in data_text.strip().split('\n'):
        if not line.strip():
            continue
        parts = line.split('\t')
        if len(parts) < 7:
            continue

        # 格式: 日期 时间 轮次 主队 比分 客队 赔率1 赔率2 赔率3
        date_str = parts[0]
        time_str = parts[1]
        round_num = parts[2]
        home_team_cn = parts[3]
        score = parts[4]
        away_team_cn = parts[5]

        if 'VS' in score or '-' not in score:
            continue

        score_parts = score.split('-')
        if len(score_parts) != 2:
            continue
        home_goals = score_parts[0]
        away_goals = score_parts[1]

        b365_home = parts[6] if len(parts) > 6 else 'null'
        b365_draw = parts[7] if len(parts) > 7 else 'null'
        b365_away = parts[8] if len(parts) > 8 else 'null'

        month, day = date_str.split('-')
        match_date = f'2026-{int(month):02d}-{int(day):02d}'

        home_team = TEAM_MAPPING.get(home_team_cn, home_team_cn)
        away_team = TEAM_MAPPING.get(away_team_cn, away_team_cn)

        hg = int(home_goals)
        ag = int(away_goals)
        if hg > ag:
            result = 'H'
        elif hg < ag:
            result = 'A'
        else:
            result = 'D'

        row = {f: 'null' for f in STANDARD_FIELDS}
        row['season'] = '2025-26'
        row['match_date'] = match_date
        row['match_time'] = time_str
        row['round_num'] = round_num
        row['division'] = 'Allsvenskan'
        row['home_team'] = home_team
        row['away_team'] = away_team
        row['home_goals'] = home_goals
        row['away_goals'] = away_goals
        row['result'] = result
        row['status'] = 'Finished'
        row['b365_home'] = b365_home
        row['b365_draw'] = b365_draw
        row['b365_away'] = b365_away

        rows.append(row)

    return rows

if __name__ == '__main__':
    if DATA_FILE.exists():
        with open(DATA_FILE, 'r', encoding='utf-8') as f:
            data_text = f.read()
    else:
        print('请将数据保存到 data/raw/allsvenskan_2026.txt')
        sys.exit(1)

    rows = parse_data(data_text)
    print(f'解析到 {len(rows)} 场比赛')

    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_FILE, 'w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=STANDARD_FIELDS, extrasaction='ignore')
        writer.writeheader()
        writer.writerows(rows)

    print(f'已写入: {OUTPUT_FILE}')