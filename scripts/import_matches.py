#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""导入比赛数据到CSV文件"""

import csv
import os
import re

# 比赛数据
matches_data = """
2026-05-17 星期日
001	J联赛	05-17 14:00	完	[4]大阪樱花	6 - 1	[1]名古屋鲸	3-1	晴	2.373.252.50	3		析
002	K联赛	05-17 15:40	完	[3]全北现代	0 - 0	[10]金泉尚武	0-0	晴	1.583.604.58	1		析
2026-05-16 星期六 完
001	J联赛	05-16 13:00	完	[7]水户蜀葵	0 - 1	[4]东京绿茵	0-0	晴	2.202.753.22	0		析
002	J联赛	05-16 15:00	完	[5]浦和红钻	0 - 0	[2]东京FC	0-0	晴	2.862.802.37	1		析
003	K联赛	05-16 15:30	完	[9]大田市民	1 - 2	[1]首尔FC	0-1	 	2.923.152.13	0		析
004	J联赛	05-16 16:00	完	[8]横滨水手	0 - 1	[9]柏太阳神	0-1	晴	2.903.202.12	0		析
005	澳超	05-16 17:40	点球完	紐卡斯托	1 - 1	悉尼FC	0-0	多云	2.083.332.87	1		析
006	K联赛	05-16 18:00	完	[6]仁川联	4 - 0	[12]光州FC	2-0	 	1.423.556.95	3		析
007	芬超	05-16 19:00	完	1[5]赫尔辛	2 - 2	[9]坦山猫	1-1	阵雨	1.543.854.55	1		析
008	挪超	05-16 20:00	完	[8]布兰	2 - 1	1[12]KFUM奥斯陆	2-0	小雨	1.414.405.20	3		析
009	瑞典超	05-16 21:00	完	[16]哈尔姆斯塔德	1 - 1	[3]埃尔夫斯堡	1-0	多云	3.853.201.80	1		析
010	瑞典超	05-16 21:00	完	[8]哥德堡盖斯	1 - 1	[11]代格福什	1-0	多云	1.553.604.85	1		析
011	德甲	05-16 21:30	完	[6]勒沃库森	1 - 1	[11]汉堡	0-0	多云	1.166.708.50	1		析
012	德甲	05-16 21:30	完	[1]拜仁	5 - 1	[14]科隆	3-1	多云		3		析
013	德甲	05-16 21:30	完	[17]海登海姆	0 - 2	[10]美因茨	0-2	多云	1.744.053.25	0		析
014	德甲	05-16 21:30	完	[18]圣保利	1 - 3	[16]沃尔夫斯堡	0-1	多云	2.463.522.28	0		析
015	德甲	05-16 21:30	完	[12]柏林联合	4 - 0	[9]奥格斯堡	2-0	阵雨	2.503.522.25	3		析
016	德甲	05-16 21:30	完	[8]法兰克福	2 - 2	[4]斯图加特	0-2	多云	3.324.301.68	1		析
017	德甲	05-16 21:30	完	[15]不来梅	0 - 2	[2]多特蒙德	0-0	多云	3.064.001.81	0		析
018	德甲	05-16 21:30	完	[13]门兴	4 - 0	1[5]霍芬海姆	2-0	多云	4.304.551.48	3		析
019	德甲	05-16 21:30	完	[7]弗赖堡	4 - 1	[3]莱比锡	2-1	多云	2.223.802.41	3		析
020	足总杯	05-16 22:00	完	[9]英超切尔西	0 - 1	英超[2]曼城	0-0	多云	4.253.721.60	0		析
2026-05-17 星期日 完
021	挪超	05-17 00:00	完	[5]博德闪耀	5 - 0	1[1]特罗姆瑟	1-0	 	1.294.906.70	3		析
022	芬超	05-17 00:00	完	[10]赫尔火花	5 - 0	[11]雅罗	1-0	阵雨	2.152.853.19	3		析
023	芬超	05-17 00:00	完	1[2]AC奥卢	1 - 0	[4]TPS土尔库	0-0	多云	1.513.655.20	3		析
024	葡超	05-17 01:00	完	[4]布拉加	2 - 2	1[15]阿马多拉	1-1	多云	1.573.704.50	1		析
025	亚冠乙	05-17 01:45	完	[1]沙联利雅得胜利	0 - 1	J联[3]大阪钢巴	0-1	多云	1.304.507.25	0		析
026	沙特联	05-17 02:00	完	[3]吉达国民	3 - 0	[13]拉斯永恒	3-0	多云	1.156.1010.50	3		析
027	葡超	05-17 03:30	完	[2]里斯本	3 - 0	[6]吉维森特	2-0	多云		3		析
028	葡超	05-17 03:30	完	[9]埃斯托里	1 - 3	[3]本菲卡	0-3	多云	9.505.701.18	0		析
029	美职	05-17 07:30	完	[14]纽约红牛	1 - 1	[13]纽约城	1-0	多云	2.553.462.23	1		析
030	美职	05-17 07:30	完	[7]新英格兰革命	2 - 1	[9]明尼苏达联	1-1	多云	2.163.202.83	3		析
"""

# 球队名称映射（中文到英文）
team_name_mapping = {
    '大阪樱花': 'Cerezo Osaka',
    '名古屋鲸': 'Nagoya Grampus',
    '全北现代': 'Jeonbuk Hyundai',
    '金泉尚武': 'Gimcheon Sangmu',
    '水户蜀葵': 'Mito HollyHock',
    '东京绿茵': 'Tokyo Verdy',
    '浦和红钻': 'Urawa Reds',
    '东京FC': 'FC Tokyo',
    '大田市民': 'Daejeon Citizen',
    '首尔FC': 'FC Seoul',
    '横滨水手': 'Yokohama F. Marinos',
    '柏太阳神': 'Kashiwa Reysol',
    '纽卡斯托': 'Newcastle Jets',
    '悉尼FC': 'Sydney FC',
    '仁川联': 'Incheon United',
    '光州FC': 'Gwangju FC',
    '赫尔辛': 'HJK Helsinki',
    '坦山猫': 'Tampere United',
    '布兰': 'Brann',
    'KFUM奥斯陆': 'KFUM Oslo',
    '哈尔姆斯塔德': 'Halmstads BK',
    '埃尔夫斯堡': 'IF Elfsborg',
    '哥德堡盖斯': 'GAIS',
    '代格福什': 'Degerfors IF',
    '勒沃库森': 'Leverkusen',
    '汉堡': 'Hamburger SV',
    '拜仁': 'Bayern Munich',
    '科隆': 'FC Koln',
    '海登海姆': 'Heidenheim',
    '美因茨': 'Mainz',
    '圣保利': 'St. Pauli',
    '沃尔夫斯堡': 'Wolfsburg',
    '柏林联合': 'Union Berlin',
    '奥格斯堡': 'Augsburg',
    '法兰克福': 'Frankfurt',
    '斯图加特': 'Stuttgart',
    '不来梅': 'Werder Bremen',
    '多特蒙德': 'Dortmund',
    '门兴': "M'gladbach",
    '霍芬海姆': 'Hoffenheim',
    '弗赖堡': 'Freiburg',
    '莱比锡': 'RB Leipzig',
    '切尔西': 'Chelsea',
    '曼城': 'Man City',
    '博德闪耀': 'Bodo/Glimt',
    '特罗姆瑟': 'Tromso',
    '赫尔火花': 'HIFK',
    '雅罗': 'Jaro',
    'AC奥卢': 'AC Oulu',
    'TPS土尔库': 'TPS Turku',
    '布拉加': 'Braga',
    '阿马多拉': 'Amadora',
    '利雅得胜利': 'Al-Nassr',
    '大阪钢巴': 'Gamba Osaka',
    '吉达国民': 'Al-Ahli',
    '拉斯永恒': 'Al-Ettifaq',
    '里斯本': 'Sporting CP',
    '吉维森特': 'Gil Vicente',
    '埃斯托里': 'Estoril',
    '本菲卡': 'Benfica',
    '纽约红牛': 'NY Red Bulls',
    '纽约城': 'NYCFC',
    '新英格兰革命': 'New England',
    '明尼苏达联': 'Minnesota United',
}

# 联赛代码映射
league_code_mapping = {
    'J联赛': 'J1',
    'K联赛': 'K1',
    '澳超': 'AUS',
    '芬超': 'FIN',
    '挪超': 'NOR',
    '瑞典超': 'SWE',
    '德甲': 'D1',
    '足总杯': 'FA_CUP',
    '葡超': 'P1',
    '亚冠乙': 'ACL2',
    '沙特联': 'SAU',
    '美职': 'MLS',
}

# 解析比赛数据
lines = matches_data.strip().split('\n')
parsed_matches = []
current_date = None

for line in lines:
    line = line.strip()
    if not line:
        continue

    # 检查是否是日期行
    date_match = re.match(r'(\d{4}-\d{2}-\d{2})', line)
    if date_match:
        current_date = date_match.group(1)
        continue

    # 解析比赛行
    parts = line.split('\t')
    if len(parts) >= 7:
        try:
            league = parts[1].strip()
            time_str = parts[2].strip()
            status = parts[3].strip()
            home_team_raw = parts[4].strip()
            score = parts[5].strip()
            away_team_raw = parts[6].strip()

            # 提取比分
            score_parts = score.split(' - ')
            if len(score_parts) == 2:
                home_goals = int(score_parts[0].strip())
                away_goals = int(score_parts[1].strip())
            else:
                continue

            # 清理球队名称（移除排名等）
            home_team = re.sub(r'\[\d+\]|1\[|\d+\[|英超|J联|沙联', '', home_team_raw).strip()
            away_team = re.sub(r'\[\d+\]|1\[|\d+\[|英超|J联|沙联', '', away_team_raw).strip()

            # 提取半场比分
            half_score = parts[7].strip() if len(parts) > 7 else ''
            half_parts = half_score.split('-')
            if len(half_parts) == 2:
                try:
                    home_half_goals = int(half_parts[0].strip())
                    away_half_goals = int(half_parts[1].strip())
                except:
                    home_half_goals = None
                    away_half_goals = None
            else:
                home_half_goals = None
                away_half_goals = None

            # 提取赔率
            odds_str = parts[8].strip() if len(parts) > 8 else ''
            odds_match = re.findall(r'(\d+\.\d+)', odds_str)
            home_odds = float(odds_match[0]) if len(odds_match) > 0 else None
            draw_odds = float(odds_match[1]) if len(odds_match) > 1 else None
            away_odds = float(odds_match[2]) if len(odds_match) > 2 else None

            # 转换球队名称
            home_team_en = team_name_mapping.get(home_team, home_team)
            away_team_en = team_name_mapping.get(away_team, away_team)

            # 计算结果
            if home_goals > away_goals:
                ftr = 'H'
            elif home_goals < away_goals:
                ftr = 'A'
            else:
                ftr = 'D'

            parsed_matches.append({
                'date': current_date,
                'time': time_str,
                'league': league,
                'league_code': league_code_mapping.get(league, league),
                'home_team': home_team_en,
                'away_team': away_team_en,
                'home_goals': home_goals,
                'away_goals': away_goals,
                'home_half_goals': home_half_goals,
                'away_half_goals': away_half_goals,
                'home_odds': home_odds,
                'draw_odds': draw_odds,
                'away_odds': away_odds,
                'ftr': ftr,
                'status': 'Finished' if status in ['完', '点球完'] else status,
            })
        except Exception as e:
            print(f"Error parsing line: {line}")
            print(f"Error: {e}")

print(f"Parsed {len(parsed_matches)} matches")

# 按联赛分组
matches_by_league = {}
for match in parsed_matches:
    league = match['league']
    if league not in matches_by_league:
        matches_by_league[league] = []
    matches_by_league[league].append(match)

# 输出解析结果
for league, matches in matches_by_league.items():
    print(f"\n{league}: {len(matches)} matches")
    for m in matches:
        print(f"  {m['date']} {m['time']} | {m['home_team']} {m['home_goals']}-{m['away_goals']} {m['away_team']}")

# 写入CSV文件
data_dir = 'd:/football_tools/data'

for league, matches in matches_by_league.items():
    # 确定CSV文件路径（这里简化处理，实际需要根据联赛确定）
    print(f"\n准备写入 {league} 的 {len(matches)} 场比赛到CSV")
    for m in matches:
        # CSV格式: Div,Date,Time,HomeTeam,AwayTeam,FTHG,FTAG,FTR,HTHG,HTAG,B365H,B365D,B365A,Status
        csv_row = {
            'Div': m['league_code'],
            'Date': m['date'],
            'Time': m['time'],
            'HomeTeam': m['home_team'],
            'AwayTeam': m['away_team'],
            'FTHG': m['home_goals'],
            'FTAG': m['away_goals'],
            'FTR': m['ftr'],
            'HTHG': m['home_half_goals'] if m['home_half_goals'] else '',
            'HTAG': m['away_half_goals'] if m['away_half_goals'] else '',
            'B365H': m['home_odds'] if m['home_odds'] else '',
            'B365D': m['draw_odds'] if m['draw_odds'] else '',
            'B365A': m['away_odds'] if m['away_odds'] else '',
            'Status': m['status'],
        }
        print(f"  {csv_row['Div']},{csv_row['Date']},{csv_row['Time']},{csv_row['HomeTeam']},{csv_row['AwayTeam']},{csv_row['FTHG']},{csv_row['FTAG']},{csv_row['FTR']}")
