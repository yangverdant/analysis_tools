"""
football-data.co.uk 数据源配置

免费、无需API Key，直接下载CSV
提供五大联赛历史比赛数据 + 赔率数据 (1993年起)
"""

# ==================== 请求配置 ====================
BASE_URL = "https://www.football-data.co.uk"
# CSV下载不需要认证
REQUEST_TIMEOUT = 30

# ==================== 联赛映射 ====================
# key: 中文名
# value: dict with league_code (URL路径中的代码), country (国家代码)
#
# CSV URL格式: https://www.football-data.co.uk/mmz4281/{season}/{league_code}.csv
# season格式: 2425 = 2024-25赛季, 2324 = 2023-24赛季

LEAGUES = {
    "英超": {
        "league_code": "E0",
        "country": "england",
        "total_teams": 20,
        "rounds": 38,
        "name_en": "Premier League",
    },
    "英冠": {
        "league_code": "E1",
        "country": "england",
        "total_teams": 24,
        "rounds": 46,
        "name_en": "Championship",
    },
    "英甲": {
        "league_code": "E2",
        "country": "england",
        "total_teams": 24,
        "rounds": 46,
        "name_en": "League One",
    },
    "英乙": {
        "league_code": "E3",
        "country": "england",
        "total_teams": 24,
        "rounds": 46,
        "name_en": "League Two",
    },
    "西甲": {
        "league_code": "SP1",
        "country": "spain",
        "total_teams": 20,
        "rounds": 38,
        "name_en": "La Liga",
    },
    "西乙": {
        "league_code": "SP2",
        "country": "spain",
        "total_teams": 22,
        "rounds": 42,
        "name_en": "Segunda Division",
    },
    "德甲": {
        "league_code": "D1",
        "country": "germany",
        "total_teams": 18,
        "rounds": 34,
        "name_en": "Bundesliga",
    },
    "德乙": {
        "league_code": "D2",
        "country": "germany",
        "total_teams": 18,
        "rounds": 34,
        "name_en": "2. Bundesliga",
    },
    "意甲": {
        "league_code": "I1",
        "country": "italy",
        "total_teams": 20,
        "rounds": 38,
        "name_en": "Serie A",
    },
    "意乙": {
        "league_code": "I2",
        "country": "italy",
        "total_teams": 20,
        "rounds": 38,
        "name_en": "Serie B",
    },
    "法甲": {
        "league_code": "F1",
        "country": "france",
        "total_teams": 18,
        "rounds": 34,
        "name_en": "Ligue 1",
    },
    "法乙": {
        "league_code": "F2",
        "country": "france",
        "total_teams": 18,
        "rounds": 34,
        "name_en": "Ligue 2",
    },
    "荷甲": {
        "league_code": "N1",
        "country": "netherlands",
        "total_teams": 18,
        "rounds": 34,
        "name_en": "Eredivisie",
    },
    "葡超": {
        "league_code": "P1",
        "country": "portugal",
        "total_teams": 18,
        "rounds": 34,
        "name_en": "Primeira Liga",
    },
    "土超": {
        "league_code": "T1",
        "country": "turkey",
        "total_teams": 20,
        "rounds": 38,
        "name_en": "Super Lig",
    },
    "比甲": {
        "league_code": "B1",
        "country": "belgium",
        "total_teams": 18,
        "rounds": 34,
        "name_en": "Jupiler League",
    },
    "苏超": {
        "league_code": "SC0",
        "country": "scotland",
        "total_teams": 12,
        "rounds": 38,
        "name_en": "Premiership",
    },
    "希腊超": {
        "league_code": "G1",
        "country": "greece",
        "total_teams": 14,
        "rounds": 36,
        "name_en": "Super League",
    },
}

# ==================== 赛季代码 ====================
# season_code: "2425" 表示2024-25赛季
# 可用赛季: 9394 ~ 当前赛季
CURRENT_SEASON = "2425"

# ==================== CSV列名映射 ====================
# football-data.co.uk CSV标准列名 -> 中文含义
CSV_COLUMNS = {
    # 基本信息
    "Div":         "联赛代码",
    "Date":        "日期",
    "HomeTeam":    "主队",
    "AwayTeam":    "客队",
    "FTHG":        "主队全场进球",
    "FTAG":        "客队全场进球",
    "FTR":         "全场结果",      # H=主胜 D=平 A=客胜
    "HTHG":        "主队半场进球",
    "HTAG":        "客队半场进球",
    "HTR":         "半场结果",
    # 赔率 - B365
    "B365H":       "B365主胜",
    "B365D":       "B365平",
    "B365A":       "B365客胜",
    # 赔率 - 威廉希尔
    "BWH":         "WH主胜",
    "BWD":         "WH平",
    "BWA":         "WH客胜",
    # 赔率 - Interwetten
    "IWH":         "IW主胜",
    "IWD":         "IW平",
    "IWA":         "IW客胜",
    # 赔率 - Pinnacle
    "PSH":         "PIN主胜",
    "PSD":         "PIN平",
    "PSA":         "PIN客胜",
    # 赔率 - 其他
    "WHH":         "WH_主胜",
    "WHD":         "WH_平",
    "WHA":         "WH_客胜",
    "VCH":         "VC主胜",
    "VCD":         "VC平",
    "VCA":         "VC客胜",
    "MaxH":        "最高主胜",
    "MaxD":        "最高平",
    "MaxA":        "最高客胜",
    "AvgH":        "平均主胜",
    "AvgD":        "平均平",
    "AvgA":        "平均客胜",
    # 亚盘
    "B365AHH":     "B365亚盘主",
    "B365AHA":     "B365亚盘客",
    "PAHH":        "PIN亚盘主",
    "PAHA":        "PIN亚盘客",
    # 大小球
    "B365>2.5":    "B365大2.5",
    "B365<2.5":    "B365小2.5",
    "P>2.5":       "PIN大2.5",
    "P<2.5":       "PIN小2.5",
    "Max>2.5":     "最大2.5",
    "Max<2.5":     "最小2.5",
    "Avg>2.5":     "平均大2.5",
    "Avg<2.5":     "平均小2.5",
    # 射门统计
    "HS":          "主队射门",
    "AS":          "客队射门",
    "HST":         "主队射正",
    "AST":         "客队射正",
    "HF":          "主队犯规",
    "AF":          "客队犯规",
    "HC":          "主队角球",
    "AC":          "客队角球",
    "HY":          "主队黄牌",
    "AY":          "客队黄牌",
    "HR":          "主队红牌",
    "AR":          "客队红牌",
    # 亚盘盘口
    "AHh":         "亚盘让球数",
    "B365AH":      "B365亚盘",
}

# ==================== URL模板 ====================
# CSV下载URL
URL_CSV = BASE_URL + "/mmz4281/{season}/{league_code}.csv"

# 历史数据归档页(含更早赛季)
URL_ARCHIVE = BASE_URL + "/downloadm.php"
