"""赛前情报采集模块

5大维度:
1. 雇佣关系 — 友谊赛谁花钱请谁
2. 球迷效应 — 客场球迷数量影响
3. 动机需求 — 球队当前需要什么结果
4. 疲劳临界 — 球员级赛季负荷+球星缺阵
5. 场地特殊 — 高原/气候/时差

使用:
    from fetchers.pre_match import PreMatchCollector
    intel = collector.collect('France', 'Ivory Coast', '2026-06-05', 'friendly')
"""

from fetchers.pre_match.collector import PreMatchCollector, PreMatchIntel, MatchContext
from fetchers.pre_match.context_builder import MatchContextBuilder
from fetchers.pre_match.news_scanner import PreMatchNewsScanner
from fetchers.pre_match.fatigue_tracker import PlayerFatigueTracker