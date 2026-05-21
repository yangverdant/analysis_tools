"""
重新清洗J联赛数据 - 使用完整字段映射，保持中文队名，添加英文队名映射
"""
import csv
from pathlib import Path
import sys

if sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')

DATA_DIR = Path("D:/football_tools/data/05_asia_leagues")
OUTPUT_DIR = Path("D:/football_tools/new_data/leagues")

# J联赛球队名映射 (繁体中文 -> 英文标准名)
J_TEAM_MAPPING = {
    '名古屋八鯨': 'Nagoya Grampus',
    '浦和紅鑽': 'Urawa Reds',
    '大阪飛腳': 'Gamba Osaka',
    '清水心跳': 'Shimizu S-Pulse',
    '大分三神': 'Oita Trinita',
    '橫濱水手': 'Yokohama F. Marinos',
    'FC東京': 'FC Tokyo',
    '神戶勝利船': 'Vissel Kobe',
    '柏雷素爾': 'Kashiwa Reysol',
    '千葉市原': 'JEF United Chiba',
    '鹿島鹿角': 'Kashima Antlers',
    '川崎前鋒': 'Kawasaki Frontale',
    '東京綠茵': 'Tokyo Verdy',
    '札幌岡薩多': 'Consadole Sapporo',
    '廣島三箭': 'Sanfrecce Hiroshima',
    '新潟天鵝': 'Albirex Niigata',
    '大宮松鼠': 'Omiya Ardija',
    '甲府風林': 'Ventforet Kofu',
    '福岡黃蜂': 'Avispa Fukuoka',
    '山形山神': 'Montedio Yamagata',
    '仙台維加泰': 'Vegalta Sendai',
    '鳥栖砂岩': 'Sagan Tosu',
    '湘南比馬': 'Shonan Bellmare',
    '磐田喜悅': 'Júbilo Iwata',
    '京都不死鳥': 'Kyoto Sanga',
    '大阪櫻花': 'Cerezo Osaka',
    '橫濱FC': 'Yokohama FC',
    '長崎成功丸': 'V-Varen Nagasaki',
    '熊本深紅': 'Roasso Kumamoto',
    '愛媛FC': 'Ehime FC',
    '岡山雉雞': 'Fagiano Okayama',
    '讚岐釜玉海': 'Kamatamare Sanuki',
    '德島漩渦': 'Tokushima Vortis',
    '琉球FC': 'FC Ryukyu',
    '北九州向日葵': 'Giravanz Kitakyushu',
    '群馬草津溫泉': 'Thespakusatsu Gunma',
    '松本山雅': 'Matsumoto Yamaga',
    '金澤薩維根': 'Kataller Toyama',
    '秋田藍閃電': 'Blaublitz Akita',
    '岩手盛岡仙鹤': 'Iwate Grulla Morioka',
    '水戶蜀葵': 'Mito HollyHock',
    '藤枝MYFC': 'Azul Claro Numazu',
    # 简体中文映射
    '名古屋鲸鱼': 'Nagoya Grampus',
    '浦和红钻': 'Urawa Reds',
    '大阪飞脚': 'Gamba Osaka',
    '清水鼓动': 'Shimizu S-Pulse',
    '横滨水手': 'Yokohama F. Marinos',
    'FC东京': 'FC Tokyo',
    '神户胜利船': 'Vissel Kobe',
    '鹿岛鹿角': 'Kashima Antlers',
    '川崎前锋': 'Kawasaki Frontale',
    '东京绿茵': 'Tokyo Verdy',
    '札幌冈萨多': 'Consadole Sapporo',
    '广岛三箭': 'Sanfrecce Hiroshima',
    '新潟天鹅': 'Albirex Niigata',
    '大宫松鼠': 'Omiya Ardija',
    '甲府风林': 'Ventforet Kofu',
    '福冈黄蜂': 'Avispa Fukuoka',
    '山形山神': 'Montedio Yamagata',
    '仙台维加泰': 'Vegalta Sendai',
    '鸟栖砂岩': 'Sagan Tosu',
    '湘南比马': 'Shonan Bellmare',
    '磐田喜悦': 'Júbilo Iwata',
    '京都不死鸟': 'Kyoto Sanga',
    '大阪樱花': 'Cerezo Osaka',
    '横滨FC': 'Yokohama FC',
    '长崎成功丸': 'V-Varen Nagasaki',
    '熊本深红': 'Roasso Kumamoto',
    '爱媛FC': 'Ehime FC',
    '冈山雉鸡': 'Fagiano Okayama',
    '赞岐釜玉海': 'Kamatamare Sanuki',
    '德岛漩涡': 'Tokushima Vortis',
    '琉球FC': 'FC Ryukyu',
    '北九州向日葵': 'Giravanz Kitakyushu',
    '群马草津温泉': 'Thespakusatsu Gunma',
    '松本山雅': 'Matsumoto Yamaga',
    '金泽萨维根': 'Kataller Toyama',
    '秋田蓝闪电': 'Blaublitz Akita',
    '岩手盛冈仙鹤': 'Iwate Grulla Morioka',
    '水户蜀葵': 'Mito HollyHock',
    '藤枝MYFC': 'Azul Claro Numazu',
    # 英文名直接映射
    'Albirex Niigata': 'Albirex Niigata',
    'Avispa Fukuoka': 'Avispa Fukuoka',
    'Cerezo Osaka': 'Cerezo Osaka',
    'FC Machida Zelvia': 'FC Machida Zelvia',
    'FC Tokyo': 'FC Tokyo',
    'Fagiano Okayama': 'Fagiano Okayama',
    'Gamba Osaka': 'Gamba Osaka',
    'Hokkaido Consadole Sapporo': 'Consadole Sapporo',
    'Júbilo Iwata': 'Júbilo Iwata',
    'Jubilo Iwata': 'Júbilo Iwata',
    'Kashima Antlers': 'Kashima Antlers',
    'Kashiwa Reysol': 'Kashiwa Reysol',
    'Kawasaki Frontale': 'Kawasaki Frontale',
    'Kyoto Sanga': 'Kyoto Sanga',
    'Kyoto Sanga FC': 'Kyoto Sanga',
    'Matsumoto Yamaga': 'Matsumoto Yamaga',
    'Mito HollyHock': 'Mito HollyHock',
    'Nagoya Grampus': 'Nagoya Grampus',
    'Oita Trinita': 'Oita Trinita',
    'Sagan Tosu': 'Sagan Tosu',
    'Sanfrecce Hiroshima': 'Sanfrecce Hiroshima',
    'Shimizu S-Pulse': 'Shimizu S-Pulse',
    'Shonan Bellmare': 'Shonan Bellmare',
    'Tokyo Verdy': 'Tokyo Verdy',
    'Urawa Red Diamonds': 'Urawa Reds',
    'Urawa Reds': 'Urawa Reds',
    'Vegalta Sendai': 'Vegalta Sendai',
    'Vissel Kobe': 'Vissel Kobe',
    'Yokohama F. Marinos': 'Yokohama F. Marinos',
    'Yokohama FC': 'Yokohama FC',
    'V-Varen Nagasaki': 'V-Varen Nagasaki',
    'Roasso Kumamoto': 'Roasso Kumamoto',
    'Ehime FC': 'Ehime FC',
    'Kamatamare Sanuki': 'Kamatamare Sanuki',
    'Tokushima Vortis': 'Tokushima Vortis',
    'FC Ryukyu': 'FC Ryukyu',
    'Giravanz Kitakyushu': 'Giravanz Kitakyushu',
    'Thespakusatsu Gunma': 'Thespakusatsu Gunma',
    'Kataller Toyama': 'Kataller Toyama',
    'Blaublitz Akita': 'Blaublitz Akita',
    'Iwate Grulla Morioka': 'Iwate Grulla Morioka',
    'Azul Claro Numazu': 'Azul Claro Numazu',
    'SC Sagamihara': 'SC Sagamihara',
    'Nara Club': 'Nara Club',
    'Omiya Ardija': 'Omiya Ardija',
    'Ventforet Kofu': 'Ventforet Kofu',
    'Montedio Yamagata': 'Montedio Yamagata',
    'Consadole Sapporo': 'Consadole Sapporo',
}

# 完整字段映射 (和欧洲联赛一致)
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

# 标准字段列表 (和欧洲联赛完全一致)
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

def parse_date(date_str):
    if not date_str:
        return None
    try:
        if len(date_str) == 10 and '-' in date_str:
            return date_str
        if len(date_str) == 8 and '-' in date_str:
            parts = date_str.split('-')
            yy = int(parts[0])
            year = 2000 + yy if yy < 100 else yy
            return f'{year}-{parts[1]}-{parts[2]}'
        if '/' in date_str:
            parts = date_str.split('/')
            if len(parts) == 3:
                day, month, year = parts
                if len(year) == 2:
                    year = '20' + year if int(year) < 50 else '19' + year
                return f'{year}-{month}-{day}'
        return date_str
    except:
        return date_str

def calculate_round(matches, matches_per_round=9):
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

def clean_csv_file(input_path, output_path, season, matches_per_round=9):
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

                # 将中文队名转换为英文标准名
                home_team = new_row.get('home_team', '')
                away_team = new_row.get('away_team', '')
                if home_team in J_TEAM_MAPPING:
                    new_row['home_team'] = J_TEAM_MAPPING[home_team]
                if away_team in J_TEAM_MAPPING:
                    new_row['away_team'] = J_TEAM_MAPPING[away_team]

                rows.append(new_row)

        rounds = calculate_round(rows, matches_per_round)
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

def process_j_league(league_name, matches_per_round=9):
    league_path = DATA_DIR / league_name
    output_path = OUTPUT_DIR / league_name

    if not league_path.exists():
        print(f'联赛目录不存在: {league_name}')
        return 0

    all_csv_files = list(league_path.glob('*.csv'))
    csv_files = []
    for f in all_csv_files:
        if f.name.endswith('_all.csv'):
            continue
        if f.name.endswith('_history.csv'):
            continue
        if f.name == 'results.csv':
            continue
        if league_name == 'j1_league' and f.name.startswith('j2_league_'):
            continue
        csv_files.append(f)

    print(f'\n{league_name}:')

    total_rows = 0
    for csv_file in sorted(csv_files):
        name = csv_file.stem
        parts = name.split('_')
        if len(parts) >= 2:
            season = parts[-1]
            if '-' not in season:
                year = int(season)
                season = f'{year}-{str(year+1)[-2:]}'
        else:
            season = name

        output_file = output_path / f'{league_name}_{season}.csv'
        rows = clean_csv_file(csv_file, output_file, season, matches_per_round)
        if rows > 0:
            print(f'  {csv_file.name} -> {season}: {rows}场')
            total_rows += rows

    print(f'  总计: {total_rows}场')
    return total_rows

if __name__ == '__main__':
    print('='*60)
    print('重新清洗J联赛数据 (统一格式)')
    print('='*60)

    process_j_league('j1_league', matches_per_round=9)  # J1: 18队
    process_j_league('j2_league', matches_per_round=11)  # J2: 22队

    print('\n完成!')
