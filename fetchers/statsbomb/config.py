"""
StatsBomb本地xG数据配置

数据源: StatsBomb Open Data (本地JSON文件)
特色: 高级xG模型/比赛事件/球员动作
数据仓库: https://github.com/statsbomb/open-data
"""

# 本地数据目录 (需先下载数据)
DATA_DIR = "data/statsbomb"

# StatsBomb Open Data仓库
GITHUB_REPO = "https://raw.githubusercontent.com/statsbomb/open-data/master/data"

# 竞赛ID映射
COMPETITION_IDS = {
    "premier_league": 2,
    "la_liga": 11,
    "champions_league": 16,
    "world_cup": 43,
    "euro": 55,
    "womens_world_cup": 72,
}

COMPETITION_CN = {
    "英超": "premier_league", "西甲": "la_liga",
    "欧冠": "champions_league", "世界杯": "world_cup",
    "欧洲杯": "euro", "女足世界杯": "womens_world_cup",
}