"""
ESPN Soccer数据获取工具

数据源: espn.com/soccer (免费爬虫 + API)
提供: 实时比分, 赛后阵容, 伤病
"""

from fetchers.espn.get_scores import get_livescores
from fetchers.espn.get_lineups import get_match_lineup, get_league_scoreboard, get_league_injuries