"""
中间商适配器 — 将各fetcher的原始输出翻译为统一格式

核心原则：
- 不修改fetcher代码
- 每个fetcher函数有一张字段映射表：原始字段名 → 统一字段名
- 值标准化由normalizer模块处理
- match_key自动计算

使用示例:
    from fetchers.adapter import adapt

    raw = get_livescores()  # apifootball返回原始字段
    unified = adapt("apifootball", "get_livescores", raw)
    # unified[0] 含: home_team, away_team, date, match_key 等统一字段
"""

from fetchers.adapter.adapter import adapt, adapt_one
from fetchers.adapter.normalizer import normalize_record
from fetchers.adapter.merger import merge_records

__all__ = ['adapt', 'adapt_one', 'normalize_record', 'merge_records']