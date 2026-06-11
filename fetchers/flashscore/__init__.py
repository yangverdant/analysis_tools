"""
FlashScore数据获取工具

数据源: flashscore.com (爬虫, 需绕反爬)
提供: 实时比分/比赛统计 (JS渲染, 建议使用其他源)
"""

from fetchers.flashscore.get_live import get_livescores, get_match_detail