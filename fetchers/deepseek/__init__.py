"""
DeepSeek AI数据获取工具

数据源: api.deepseek.com (需API Key)
提供: AI分析/翻译/聊天补全
"""

from fetchers.deepseek.chat import (
    chat_completion, analyze_match,
    translate_players, translate_leagues
)