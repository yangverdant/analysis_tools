"""World Cup historical data fetcher.

Data sources: StatsBomb open data (xG/lineups/stats) + Flashscore (odds)
"""

from fetchers.world_cup.get_data import (
    get_matches, get_odds, get_lineups, get_statistics, get_full_data
)
