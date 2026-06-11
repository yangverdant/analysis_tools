"""
搜索API数据源配置

数据源: Tavily API / Brave Search API
特色: 搜索互联网获取最新足球资讯/数据
用途: 辅助搜索, 获取无法从固定API获取的信息
"""

# Tavily
TAVILY_API_KEY = ""  # 需要填入
TAVILY_URL = "https://api.tavily.com/search"

# Brave Search
BRAVE_API_KEY = ""  # 需要填入
BRAVE_URL = "https://api.search.brave.com/res/v1/web/search"

REQUEST_TIMEOUT = 15