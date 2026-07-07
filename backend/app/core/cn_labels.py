"""Centralized CN label maps for enum fields that leak into the analysis report.

Why: comprehensive.py / analyze.py serialize raw English enums (away_win,
medium, friendly_intl, historical_pattern_gate, ...) directly into the JSON
report. The frontend renders some of these (RL map, confCN map) but not all,
so users see English like "predicted_result: away_win" and
"reason: historical_pattern_gate" mixed into Chinese sentences.

This module gives one place to translate every enum that appears in the
user-facing report. Callers keep the original English key (downstream logic
depends on it) and add a `*_cn` sibling.
"""
from __future__ import annotations

PREDICTED_RESULT_CN = {
    "home_win": "主胜",
    "draw": "平局",
    "away_win": "客胜",
    "3": "主胜",
    "1": "平局",
    "0": "客胜",
}

CONFIDENCE_LEVEL_CN = {
    "high": "强烈推荐",
    "medium": "谨慎推荐",
    "low": "仅供参考",
    "avoid": "建议回避",
}

CONFIDENCE_TIER_CN = CONFIDENCE_LEVEL_CN

ADVANTAGE_CN = {
    "home": "主队",
    "away": "客队",
    "team1": "主队",
    "team2": "客队",
    "balanced": "两队均衡",
    "neutral": "中性",
}

LEVEL_CN = {
    "neutral": "中性",
    "slight": "轻微",
    "moderate": "中等",
    "significant": "明显",
    "strong": "显著",
    "very_strong": "压倒性",
    "unknown": "未知",
}

MOTIVATION_TYPE_CN = {
    "friendly": "友谊赛",
    "league": "联赛",
    "cup": "杯赛",
    "qualifier": "预选赛",
    "nations_league": "欧国联",
    "world_cup": "世界杯",
    "continental_cup": "洲际杯赛",
    "champions_league": "欧冠",
    "europa_league": "欧联",
    "conference_league": "欧协联",
    "domestic_cup": "国内杯赛",
    "relegation": "保级战",
    "title_decider": "争冠战",
}

MOTIVATION_LEVEL_CN = {
    "high": "高",
    "medium": "中",
    "low": "低",
    "very_high": "极高",
    "very_low": "极低",
    "unknown": "未知",
}

COMPETITION_TYPE_CN = {
    "friendly_intl": "国际友谊赛",
    "friendly_club": "俱乐部友谊赛",
    "league": "联赛",
    "cup": "杯赛",
    "international_cup": "国际杯赛",
    "qualifier": "预选赛",
    "nations_league": "欧国联",
    "world_cup": "世界杯",
    "continental_cup": "洲际杯赛",
    "champions_league": "欧冠",
    "europa_league": "欧联",
    "conference_league": "欧协联",
    "domestic_cup": "国内杯赛",
}

PARTICIPANT_TYPE_CN = {
    "national": "国家队",
    "club": "俱乐部",
    "youth": "青年队",
    "women": "女足",
}

MATCH_PHASE_CN = {
    "league_phase": "联赛阶段",
    "group_stage": "小组赛",
    "round_of_16": "十六强",
    "quarter_final": "四分之一决赛",
    "semi_final": "半决赛",
    "final": "决赛",
    "knockout": "淘汰赛",
    "qualifying": "预选赛阶段",
    "regular_season": "常规赛季",
}

GATE_REASON_CN = {
    "historical_pattern_gate": "历史规律校准",
    "risk_profile_watch_only": "风险侧栏建议观望",
    "goal_axis_risk_gate": "进球轴风险校准",
    "goal_axis_thin_edge": "进球轴边际过薄",
    "handicap_boundary_gate": "让球边界校准",
    "no_historical_support_for_strong": "无历史强推支持",
    "default": "默认",
    "manual_override": "人工干预",
}

SCENARIO_TYPE_CN = COMPETITION_TYPE_CN


def cn(value: str | None, mapping: dict, default: str | None = None) -> str:
    """Translate an enum value via mapping; returns default or the raw value if unknown."""
    if value is None:
        return default or ""
    return mapping.get(str(value), default or str(value))


def predicted_result_cn(value: str | None) -> str:
    return cn(value, PREDICTED_RESULT_CN)


def confidence_level_cn(value: str | None) -> str:
    return cn(value, CONFIDENCE_LEVEL_CN)


def advantage_cn(value: str | None) -> str:
    return cn(value, ADVANTAGE_CN)


def level_cn(value: str | None) -> str:
    return cn(value, LEVEL_CN)


def motivation_type_cn(value: str | None) -> str:
    return cn(value, MOTIVATION_TYPE_CN)


def motivation_level_cn(value: str | None) -> str:
    return cn(value, MOTIVATION_LEVEL_CN)


def competition_type_cn(value: str | None) -> str:
    return cn(value, COMPETITION_TYPE_CN)


def participant_type_cn(value: str | None) -> str:
    return cn(value, PARTICIPANT_TYPE_CN)


def match_phase_cn(value: str | None) -> str:
    return cn(value, MATCH_PHASE_CN)


def gate_reason_cn(value: str | None) -> str:
    return cn(value, GATE_REASON_CN)


def scenario_type_cn(value: str | None) -> str:
    return cn(value, SCENARIO_TYPE_CN)
