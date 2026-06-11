"""
足球新闻获取配置

支持渠道: 直播吧(zhibo8)
备用域名: zhibo8.cc, zhibo8.com, zhibo8.tv
提供: 伤病情报、转会动态、教练更替、赛前分析
"""

# 直播吧域名列表 (按优先级)
Zhibo8_DOMAINS = [
    "https://www.zhibo8.cc",
    "https://www.zhibo8.com",
    "https://www.zhibo8.tv",
]

REQUEST_TIMEOUT = 15
REQUEST_INTERVAL = 2