"""
DeepSeek AI数据源配置

数据源: api.deepseek.com (OpenAI兼容API)
特色: AI分析/翻译/球员中文名/联赛中文名
模型: deepseek-chat / deepseek-v4-pro
"""

# 从api_config.json读取的Key
API_KEY = "sk-0Uj687veHGqP4f6dvTflFtfhAn52hOXuQUJ6A9Zb94DAayT1"  # spanagent.xyz代理
BASE_URL = "https://spanagent.xyz/v1"       # 代理endpoint
DIRECT_URL = "https://api.deepseek.com/v1"  # 官方endpoint
MODEL = "deepseek-chat"
REQUEST_TIMEOUT = 30
REQUEST_INTERVAL = 1