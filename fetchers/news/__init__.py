"""
足球新闻获取工具

支持渠道: 直播吧(zhibo8)
提供: 伤病情报、转会动态、教练更替、赛前分析
"""

from fetchers.news.get_news import (
    get_zhibo8_news, classify_news_type,
    filter_by_type, filter_by_team,
    get_zhibo8_today_matches, get_zhibo8_match_preview
)