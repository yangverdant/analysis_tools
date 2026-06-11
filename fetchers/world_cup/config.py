"""World Cup historical data configuration.

Data sources:
- StatsBomb open data (local): xG, lineups, formations, match statistics
- Flashscore (scraped): 1X2 closing odds
"""
import os

# 本fetcher自带数据目录
_MODULE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(_MODULE_DIR, 'data')

# StatsBomb open data (本地原始数据)
SB_DATA_DIR = os.path.join('data', 'open-data-master', 'data')

SUPPORTED_YEARS = [2018, 2022]

# StatsBomb competition/season IDs
STATSBOMB_COMPETITION_ID = 43
STATSBOMB_SEASON_IDS = {
    2018: '3',
    2022: '106',
}

# League info for adapter
LEAGUE_NAME = 'World Cup'
LEAGUE_ID = 'wc'
