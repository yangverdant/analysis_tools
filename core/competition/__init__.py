"""
赛事规则引擎 — 8种赛事类型 + 俱乐部/国家队分线
"""
from .engine import (
    CompetitionRuleEngine,
    CompetitionType,
    MatchPhase,
    MatchProfile,
    ParticipantType,
    classify_match,
)

__all__ = [
    "CompetitionRuleEngine",
    "CompetitionType",
    "MatchPhase",
    "MatchProfile",
    "ParticipantType",
    "classify_match",
]
