"""9:00 分析 — MatchProfile驱动分析路由

路由逻辑:
- LEAGUE/SUPER_CUP/PLAYOFF → ComprehensiveAnalyzer (标准)
- CUP → ComprehensiveAnalyzer + cup权重+upset_risk
- FRIENDLY_INTL → ComprehensiveAnalyzer + draw_boost + rotation_risk + 5维度修正
- WC_QUALIFIER/NATIONS_LEAGUE/TOURNAMENT_INTL → ComprehensiveAnalyzer + FIFA/Elo国家队评估
"""

import json
import logging
import os
import sqlite3
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional

from .time_utils import today_beijing, tomorrow_beijing
from .cn_labels import (
    predicted_result_cn, confidence_level_cn, advantage_cn, level_cn,
    motivation_type_cn, motivation_level_cn, competition_type_cn,
    participant_type_cn, match_phase_cn, gate_reason_cn, scenario_type_cn,
)

logger = logging.getLogger(__name__)


def _stable_json(value: Any) -> str:
    try:
        return json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)
    except Exception:
        return str(value)


def _strip_volatile_report_fields(value: Any) -> Any:
    volatile_keys = {
        'retrieved_at',
        'fetched_at',
        'generated_at',
        'updated_at',
        'last_updated',
        'update_time',
        'created_at',
        'snapshot_time',
        'context_generated_at',
        'analysis_time',
        'context_selection_note',
    }
    if isinstance(value, dict):
        return {
            key: _strip_volatile_report_fields(item)
            for key, item in value.items()
            if key not in volatile_keys
        }
    if isinstance(value, list):
        return [_strip_volatile_report_fields(item) for item in value]
    return value


def _round_number(value: Any, digits: int = 3) -> Any:
    if isinstance(value, (int, float)):
        return round(float(value), digits)
    return value


def _safe_float(value: Any) -> Optional[float]:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _compact_probabilities(value: Any, digits: int = 3) -> Any:
    if not isinstance(value, dict):
        return value
    return {key: _round_number(item, digits) for key, item in sorted(value.items())}


def _compact_goal_axis(value: Any) -> dict:
    if not isinstance(value, dict):
        return {}
    sensitivity = value.get('sensitivity') if isinstance(value.get('sensitivity'), dict) else {}
    similarity = value.get('historical_similarity_signal') if isinstance(value.get('historical_similarity_signal'), dict) else {}
    return {
        key: val
        for key, val in {
            'side': value.get('side'),
            'confidence_level': value.get('confidence_level'),
            'risk_level': value.get('risk_level'),
            'recommended_usage': value.get('recommended_usage'),
            'line': _round_number(value.get('line'), 2),
            'expected_total': _round_number(value.get('expected_total'), 2),
            'selected_probability': _round_number(value.get('selected_probability'), 3),
            'probability_gap': _round_number(value.get('probability_gap'), 3),
            'market_alignment': value.get('market_alignment'),
            'sensitivity_level': sensitivity.get('level'),
            'similarity_sample_size': similarity.get('sample_size'),
            'similarity_hit_rate': _round_number(similarity.get('same_prediction_hit_rate') or similarity.get('hit_rate'), 3),
            'similarity_support_side': similarity.get('support_side'),
            'support_count': len(value.get('supporting_evidence') or []),
            'warning_count': len(value.get('warnings') or []),
        }.items()
        if val not in (None, '', {})
    }


def _compact_play_predictions(plays: Any) -> dict:
    if not isinstance(plays, dict):
        return {}
    compact = {}
    for play_type, play in plays.items():
        if play_type == 'top3_scores' and isinstance(play, list):
            compact[play_type] = [
                {
                    'score': item.get('score'),
                    'probability': _round_number(item.get('probability'), 1),
                }
                for item in play[:3]
                if isinstance(item, dict)
            ]
            continue
        if not isinstance(play, dict):
            continue
        item = {
            'direction': play.get('direction'),
            'recommendation': play.get('recommendation'),
            'recommendation_cn': play.get('recommendation_cn'),
            'handicap': _round_number(play.get('handicap'), 2),
            'goal_line': _round_number(play.get('goal_line'), 2),
            'goal_line_label': play.get('goal_line_label'),
            'margin_requirement': play.get('margin_requirement'),
            'line': _round_number(play.get('line') or play.get('best_line'), 2),
            'confidence_level': play.get('confidence_level'),
            'confidence_tier': play.get('confidence_tier'),
        }
        gate = play.get('recommendation_gate') if isinstance(play.get('recommendation_gate'), dict) else {}
        if gate:
            item['recommendation_gate'] = {
                key: gate.get(key)
                for key in (
                    'tier',
                    'base_tier',
                    'reason',
                    'selected_probability',
                    'historical_accuracy',
                    'historical_sample_size',
                    'historical_scope',
                )
                if gate.get(key) not in (None, '', {})
            }
        if play_type in {'spf', 'rqspf', 'ou'}:
            item['probabilities'] = _compact_probabilities(play.get('probabilities'), 2)
        if play_type == 'rqspf':
            axis = play.get('axis_projection') if isinstance(play.get('axis_projection'), dict) else {}
            item.update({
                'display_source': play.get('display_source'),
                'unconditional_direction': play.get('unconditional_direction'),
                'axis_direction': axis.get('direction'),
                'axis_basis': axis.get('basis'),
                'axis_probabilities': _compact_probabilities(axis.get('probabilities'), 2),
            })
        if play_type == 'ou':
            item['recommendation_basis'] = play.get('recommendation_basis')
            item['best_line_probs'] = _compact_probabilities(play.get('best_line_probs'), 3)
            item['raw_best_line_probs'] = _compact_probabilities(play.get('raw_best_line_probs'), 3)
            goal_axis = _compact_goal_axis(play.get('goal_axis'))
            if goal_axis:
                item['goal_axis'] = goal_axis
        compact[play_type] = {key: value for key, value in item.items() if value not in (None, '', {})}
    return compact


def _compact_final_prediction(final_prediction: Any) -> dict:
    if not isinstance(final_prediction, dict):
        return {}
    return {
        'predicted_result': final_prediction.get('predicted_result'),
        'confidence_level': final_prediction.get('confidence_level'),
        'confidence_tier': final_prediction.get('confidence_tier'),
        'probabilities': _compact_probabilities(final_prediction.get('probabilities'), 3),
        'expected_score': _compact_probabilities(final_prediction.get('expected_score'), 2),
        'most_likely_scores': [
            {
                'score': item.get('score'),
                'probability': _round_number(item.get('probability'), 1),
            }
            for item in (final_prediction.get('most_likely_scores') or [])[:3]
            if isinstance(item, dict)
        ],
    }


def _compact_standings(rows: Any) -> list:
    if not isinstance(rows, list):
        return []
    compact = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        compact.append({
            'group': row.get('group'),
            'position': row.get('position'),
            'team_name_cn': row.get('team_name_cn') or row.get('team_name'),
            'played': row.get('played'),
            'points': row.get('points'),
            'goal_diff': row.get('goal_diff'),
            'goals_for': row.get('goals_for'),
            'qualification': row.get('qualification'),
        })
    return compact


def _compact_world_cup_context(context: Any) -> dict:
    if not isinstance(context, dict):
        return {}
    group = context.get('group') if isinstance(context.get('group'), dict) else {}
    teams = context.get('teams') if isinstance(context.get('teams'), dict) else {}
    path = context.get('knockout_path_context') if isinstance(context.get('knockout_path_context'), dict) else {}
    slots = []
    for slot in path.get('potential_round_of_32_slots') or []:
        if not isinstance(slot, dict):
            continue
        slots.append({
            'finish': slot.get('finish') or slot.get('finish_label') or slot.get('slot_type'),
            'match_no': slot.get('match_no') or slot.get('match_number'),
            'opponent_slot': slot.get('opponent_slot') or slot.get('opponent'),
            'venue': slot.get('venue'),
        })
    return {
        'context_freshness': context.get('context_freshness'),
        'group': {
            'group': group.get('group'),
            'matches_finished': group.get('matches_finished'),
            'matches_total': group.get('matches_total'),
            'standings': _compact_standings(group.get('standings')),
        },
        'teams': {
            side: {
                'team_name_cn': item.get('team_name_cn') or item.get('team_name'),
                'position': item.get('position'),
                'played': item.get('played'),
                'points': item.get('points'),
                'goal_diff': item.get('goal_diff'),
                'qualification': item.get('qualification'),
                'pressure_level': item.get('pressure_level'),
            }
            for side, item in teams.items()
            if isinstance(item, dict)
        } if isinstance(teams, dict) else {},
        'round': context.get('round') or context.get('group_round'),
        'knockout_slots': slots,
    }


def _compact_competition_context(context: Any) -> dict:
    if not isinstance(context, dict):
        return {}
    compact = {}
    if 'world_cup_2026' in context:
        compact['world_cup_2026'] = _compact_world_cup_context(context.get('world_cup_2026'))
    for key in ('competition_type', 'type', 'stage_type', 'group_name', 'round_num',
                'motivation_weight', 'draw_boost', 'rotation_risk', 'upset_risk',
                'is_neutral_venue', 'has_two_legs'):
        if key in context:
            compact[key] = context.get(key)
    return compact


_COMPETITION_TYPE_CONTEXTS = {
    'league': {
        'description': '联赛：长期攻防状态+主客场+积分/排名压力',
        'motivation_weight': 0.4,
        'draw_boost': 0.0,
        'rotation_risk': 0.0,
        'upset_risk': 0.15,
        'key_factors': ['home_away', 'form', 'elo', 'h2h', 'odds'],
    },
    'cup': {
        'description': '杯赛：淘汰赛动机+轮换风险+赛制',
        'motivation_weight': 0.6,
        'draw_boost': -0.05,
        'rotation_risk': 0.25,
        'upset_risk': 0.30,
        'key_factors': ['motivation', 'rotation_risk', 'odds', 'h2h'],
    },
    'super_cup': {
        'description': '超级杯：单场决赛+动机高+轮换少',
        'motivation_weight': 0.5,
        'draw_boost': -0.03,
        'rotation_risk': 0.10,
        'upset_risk': 0.20,
        'key_factors': ['motivation', 'elo', 'odds', 'form'],
    },
    'playoff': {
        'description': '升降级附加赛/淘汰赛末段：高压+积分形势',
        'motivation_weight': 0.7,
        'draw_boost': -0.08,
        'rotation_risk': 0.05,
        'upset_risk': 0.25,
        'key_factors': ['motivation', 'form', 'home_away', 'odds'],
    },
    'wc_qualifier': {
        'description': '世预赛：积分压力+主客旅行+阵容征召',
        'motivation_weight': 0.6,
        'draw_boost': 0.02,
        'rotation_risk': 0.15,
        'upset_risk': 0.25,
        'key_factors': ['motivation', 'elo', 'odds', 'travel_rest'],
    },
    'nations_league': {
        'description': '欧国联/亚国联：联赛阶段+积分+升降级',
        'motivation_weight': 0.5,
        'draw_boost': 0.01,
        'rotation_risk': 0.20,
        'upset_risk': 0.20,
        'key_factors': ['motivation', 'elo', 'form', 'odds'],
    },
    'friendly_intl': {
        'description': '国际友谊赛：轮换+试阵+动机不稳定',
        'motivation_weight': 0.2,
        'draw_boost': 0.10,
        'rotation_risk': 0.40,
        'upset_risk': 0.35,
        'key_factors': ['rotation_risk', 'odds', 'friendly_context'],
    },
    'tournament_intl': {
        'description': '大赛正赛(世界杯/欧洲杯)：小组形势+晋级压力',
        'motivation_weight': 0.5,
        'draw_boost': 0.0,
        'rotation_risk': 0.10,
        'upset_risk': 0.20,
        'key_factors': ['motivation', 'elo', 'form', 'odds', 'tournament_context'],
    },
}


def _build_type_context(ct: str, profile, match: dict, db_path: str) -> dict:
    """Build competition context based on type, enriching from profile and DB."""
    base = _COMPETITION_TYPE_CONTEXTS.get(ct, _COMPETITION_TYPE_CONTEXTS['league']).copy()
    context = {
        'type': ct,
        'description': base.get('description', ''),
        'motivation_weight': base.get('motivation_weight', 0.4),
        'draw_boost': base.get('draw_boost', 0.0),
        'rotation_risk': base.get('rotation_risk', 0.0),
        'upset_risk': base.get('upset_risk', 0.15),
        'key_factors': base.get('key_factors', []),
    }
    # Enrich from MatchProfile
    if profile and hasattr(profile, 'is_neutral_venue'):
        context['is_neutral_venue'] = profile.is_neutral_venue
    if profile and hasattr(profile, 'has_two_legs'):
        context['has_two_legs'] = profile.has_two_legs
    if profile and hasattr(profile, 'match_phase'):
        mp = profile.match_phase
        context['stage_type'] = mp.value if hasattr(mp, 'value') else str(mp)
    return context


def _compact_evidence_state(report: Any) -> dict:
    if not isinstance(report, dict):
        return {}
    guard = report.get('analysis_guard') if isinstance(report.get('analysis_guard'), dict) else {}
    evidence = guard.get('evidence') if isinstance(guard.get('evidence'), dict) else {}
    intelligence = report.get('intelligence_adjustment') if isinstance(report.get('intelligence_adjustment'), dict) else {}
    status_by_key = evidence.get('status_by_key') if isinstance(evidence.get('status_by_key'), dict) else {}
    compact_status = {}
    for key, item in sorted(status_by_key.items()):
        if not isinstance(item, dict):
            continue
        compact_status[key] = {
            'status': item.get('status'),
            'confidence': _round_number(item.get('confidence'), 3),
            'source': item.get('source'),
            'mode': item.get('mode'),
        }
    low_conf = []
    for item in evidence.get('low_confidence_critical') or []:
        if not isinstance(item, dict):
            continue
        low_conf.append({
            'key': item.get('key'),
            'confidence': _round_number(item.get('confidence'), 3),
            'threshold': _round_number(item.get('threshold'), 3),
            'reason': item.get('reason'),
        })
    return {
        'guard_applied': guard.get('applied'),
        'guard_reason': guard.get('reason'),
        'package_status': evidence.get('package_status') or intelligence.get('package_status'),
        'strict_completeness': _round_number(
            evidence.get('strict_completeness', intelligence.get('strict_completeness')),
            2,
        ),
        'required_fallback': evidence.get('required_fallback', intelligence.get('required_fallback')),
        'average_confidence': _round_number(
            evidence.get('average_confidence', intelligence.get('average_confidence')),
            3,
        ),
        'missing_required': evidence.get('missing_required') or [],
        'missing_critical': evidence.get('missing_critical') or [],
        'low_confidence_critical': low_conf,
        'status_by_key': compact_status,
        'package_updated_at': intelligence.get('package_updated_at'),
    }


def _report_quality(report: dict) -> int:
    if not isinstance(report, dict):
        return 0
    plays = report.get('play_predictions') if isinstance(report.get('play_predictions'), dict) else {}
    bqc = plays.get('bqc') if isinstance(plays.get('bqc'), dict) else {}
    ou = plays.get('ou') if isinstance(plays.get('ou'), dict) else {}
    context = report.get('world_cup_context') if isinstance(report.get('world_cup_context'), dict) else {}
    guard = report.get('analysis_guard') if isinstance(report.get('analysis_guard'), dict) else {}
    guard_evidence = guard.get('evidence') if isinstance(guard.get('evidence'), dict) else {}
    intelligence = report.get('intelligence_adjustment') if isinstance(report.get('intelligence_adjustment'), dict) else {}
    quality = 0
    if report.get('odds_baseline'):
        quality += 10
    if report.get('model_vs_odds'):
        quality += 5
    if bqc.get('phase_profile'):
        quality += 30
    if bqc.get('derivation'):
        quality += 10
    if bqc.get('risk_profile'):
        quality += 5
    if ou.get('diagnostics') or ou.get('line_profile'):
        quality += 15
    if context:
        quality += 10
        status = context.get('data_status') if isinstance(context.get('data_status'), dict) else {}
        if status.get('mode') == 'live_api':
            quality += 10
        group = context.get('group') if isinstance(context.get('group'), dict) else {}
        quality += int(group.get('matches_finished') or 0)
    if report.get('intelligence_summary'):
        quality += 10
    if guard:
        quality += 8
        if guard_evidence.get('strict_completeness') is not None:
            quality += 8
        if guard_evidence.get('required_fallback') is not None:
            quality += 4
        low_conf = guard_evidence.get('low_confidence_critical')
        if isinstance(low_conf, list):
            quality += min(8, len(low_conf) * 2)
    if intelligence.get('strict_completeness') is not None:
        quality += 5
    if intelligence.get('required_fallback') is not None:
        quality += 3
    return quality


def _report_signature(report: dict) -> str:
    """Stable content signature for deciding whether to write a new report row."""
    if not isinstance(report, dict):
        return ''
    payload = {
        'final_prediction': _compact_final_prediction(report.get('final_prediction')),
        'play_predictions': _compact_play_predictions(report.get('play_predictions')),
        'odds_baseline': report.get('odds_baseline'),
        'model_vs_odds': report.get('model_vs_odds'),
        'world_cup_context': _compact_world_cup_context(report.get('world_cup_context')),
        'competition_context': _compact_competition_context(report.get('competition_context')),
        'intelligence_summary': report.get('intelligence_summary'),
        'evidence_state': _compact_evidence_state(report),
        'data_quality': report.get('data_quality'),
    }
    return _stable_json(_strip_volatile_report_fields(payload))


def _load_latest_active_report(cursor, match_key: str) -> Optional[dict]:
    try:
        row = cursor.execute(
            """
            SELECT report_id, report_data, created_at
            FROM lottery_analysis_reports
            WHERE lottery_match_id = ?
              AND report_type = 'prediction'
              AND COALESCE(is_stale, 0) = 0
            ORDER BY datetime(created_at) DESC, report_id DESC
            LIMIT 1
            """,
            (match_key,),
        ).fetchone()
        if not row:
            return None
        data = json.loads(row[1]) if isinstance(row[1], str) else row[1]
        return {'report_id': row[0], 'report_data': data or {}, 'created_at': row[2]}
    except Exception:
        return None


def analyze(state, db_path: str) -> dict:
    """执行分析 — 覆盖所有比赛(体彩+全量)

    数据源:
    1. lottery_matches — 体彩开售的比赛(有体彩赔率)
    2. matches表 — 全量比赛(世界杯/友谊赛/联赛等, 有oddsfe赔率)

    范围: 北京时间窗口(今天+明天) + 未来7天的世界杯/重要赛事
    """
    today = today_beijing()
    tomorrow = tomorrow_beijing()
    logger.info('=== 9:00 分析 (%s ~ %s + 未来赛事) ===', today, tomorrow)

    # 1. 体彩比赛(今天+明天窗口)
    lottery_matches = _get_pending_lottery(db_path, today, tomorrow)
    # 2. 全量比赛 - 今天+明天窗口的国家队比赛
    near_matches = _get_pending_from_matches(db_path, today, tomorrow)
    # 3. 未来7天的重要赛事(世界杯/洲际杯赛)
    future_matches = _get_pending_future(db_path, 7)

    total_pending = len(lottery_matches) + len(near_matches) + len(future_matches)
    logger.info('待分析: 体彩%d + 近期%d + 未来%d = %d场',
                len(lottery_matches), len(near_matches), len(future_matches), total_pending)

    if total_pending == 0:
        return {'route': 'normal', 'analyzed': 0}

    analyzed = 0
    # 优先分析体彩比赛
    for match in lottery_matches[:30]:
        try:
            result = _analyze_single(db_path, match)
            if result:
                analyzed += 1
        except Exception as e:
            logger.error('分析失败 %s: %s', match.get('lottery_match_id') or match.get('match_id'), e)

    # 然后近期国家队比赛
    for match in near_matches[:30]:
        try:
            result = _analyze_single(db_path, match)
            if result:
                analyzed += 1
        except Exception as e:
            logger.error('分析失败 %s: %s', match.get('match_id'), e)

    # 最后未来重要赛事
    for match in future_matches[:30]:
        try:
            result = _analyze_single(db_path, match)
            if result:
                analyzed += 1
        except Exception as e:
            logger.error('分析失败 %s: %s', match.get('match_id'), e)

    logger.info('分析完成: %d场', analyzed)
    return {'route': 'normal', 'analyzed': analyzed}


def _get_pending_lottery(db_path: str, today: str, tomorrow: str) -> List[dict]:
    """获取待分析的体彩比赛 — 北京时间窗口"""
    try:
        conn = sqlite3.connect(db_path, timeout=10)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("""
            SELECT lm.*,
                   ht.team_type AS home_team_type,
                   at.team_type AS away_team_type
            FROM lottery_matches lm
            LEFT JOIN teams ht ON lm.home_team_id = ht.team_id
            LEFT JOIN teams at ON lm.away_team_id = at.team_id
            WHERE (
                lm.match_date = ?
                OR (lm.match_date = ? AND substr(lm.match_time, 1, 2) < '12')
            )
            AND lm.lottery_match_id NOT IN (
                SELECT DISTINCT lottery_match_id FROM lottery_analysis_reports
                WHERE report_type = 'prediction'
            )
            AND lm.home_team_id IS NOT NULL
            AND lm.away_team_id IS NOT NULL
            ORDER BY lm.match_date, lm.match_time
        """, (today, tomorrow))
        return [dict(row) for row in cursor.fetchall()]
    except Exception as e:
        logger.error('获取体彩待分析失败: %s', e)
        return []


def _get_pending_from_matches(db_path: str, today: str, tomorrow: str) -> List[dict]:
    """获取待分析的全量比赛(matches表) — 排除已有预测和体彩已覆盖的

    优先级: 世界杯 > 友谊赛(国家队) > 联赛 > 其他
    """
    try:
        conn = sqlite3.connect(db_path, timeout=10)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        # 已有预测的match_id
        cursor.execute("""
            SELECT DISTINCT lottery_match_id FROM lottery_analysis_reports
            WHERE report_type = 'prediction'
        """)
        reported_keys = set(r[0] for r in cursor.fetchall())

        # 体彩已覆盖的match_id
        cursor.execute("""
            SELECT DISTINCT oddsfe_event_id FROM lottery_matches
            WHERE oddsfe_event_id IS NOT NULL AND oddsfe_event_id != ''
        """)
        lottery_event_ids = set(r[0] for r in cursor.fetchall())

        # 查询matches表 — 北京时间窗口
        cursor.execute("""
            SELECT m.match_id, m.match_date, m.match_time,
                   m.home_team_id, m.away_team_id, m.league_id,
                   l.name_en AS league_name_en, l.name_cn AS league_name_cn,
                   l.competition_type, l.participant_type,
                   ht.name_en AS home_team_name, ht.team_type AS home_team_type,
                   at.name_en AS away_team_name, at.team_type AS away_team_type
            FROM matches m
            JOIN leagues l ON m.league_id = l.league_id
            JOIN teams ht ON m.home_team_id = ht.team_id
            JOIN teams at ON m.away_team_id = at.team_id
            WHERE (
                m.match_date = ?
                OR (m.match_date = ? AND substr(m.match_time, 1, 2) < '12')
            )
            AND m.home_team_id IS NOT NULL
            AND m.away_team_id IS NOT NULL
            AND ht.team_type = 'national'
            AND at.team_type = 'national'
            ORDER BY
                CASE WHEN l.name_en LIKE '%World Cup%' THEN 0
                     WHEN l.name_en LIKE '%riendly%' THEN 1
                     WHEN l.competition_type = 'international' THEN 2
                     ELSE 3 END,
                m.match_date, m.match_time
        """, (today, tomorrow))
        rows = [dict(r) for r in cursor.fetchall()]
        conn.close()

        # 过滤已有预测和体彩已覆盖的
        pending = []
        for r in rows:
            mid = r['match_id']
            if mid in reported_keys:
                continue
            # 检查体彩是否已覆盖(通过team_id+date判断)
            key = "{}_{}".format(r['home_team_id'], r['away_team_id'])
            if key in reported_keys:
                continue
            pending.append(r)

        return pending
    except Exception as e:
        logger.error('获取全量待分析失败: %s', e)
        return []


def _get_pending_future(db_path: str, days: int = 7) -> List[dict]:
    """获取未来N天的重要赛事(World Cup/洲际杯/国家队比赛)

    只取国家队比赛, 因为俱乐部联赛太多且体彩不一定开售。
    """
    try:
        from datetime import timedelta
        from .time_utils import today_beijing

        start_date = tomorrow_beijing()
        end_date = (datetime.strptime(today_beijing(), '%Y-%m-%d').date() + timedelta(days=days)).strftime('%Y-%m-%d')

        conn = sqlite3.connect(db_path, timeout=10)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        # 已有预测的
        cursor.execute("""
            SELECT DISTINCT lottery_match_id FROM lottery_analysis_reports
            WHERE report_type = 'prediction'
        """)
        reported_keys = set(r[0] for r in cursor.fetchall())

        # 查未来赛事
        cursor.execute("""
            SELECT m.match_id, m.match_date, m.match_time,
                   m.home_team_id, m.away_team_id, m.league_id,
                   l.name_en AS league_name_en, l.name_cn AS league_name_cn,
                   l.competition_type, l.participant_type,
                   ht.name_en AS home_team_name, ht.team_type AS home_team_type,
                   at.name_en AS away_team_name, at.team_type AS away_team_type
            FROM matches m
            JOIN leagues l ON m.league_id = l.league_id
            JOIN teams ht ON m.home_team_id = ht.team_id
            JOIN teams at ON m.away_team_id = at.team_id
            WHERE m.match_date >= ? AND m.match_date <= ?
            AND m.home_team_id IS NOT NULL
            AND m.away_team_id IS NOT NULL
            AND ht.team_type = 'national' AND at.team_type = 'national'
            AND (l.name_en LIKE '%World Cup%' OR l.name_en LIKE '%riendly%'
                 OR l.competition_type = 'international')
            ORDER BY
                CASE WHEN l.name_en LIKE '%World Cup%' THEN 0
                     WHEN l.competition_type = 'international' THEN 1
                     ELSE 2 END,
                m.match_date, m.match_time
        """, (start_date, end_date))
        rows = [dict(r) for r in cursor.fetchall()]
        conn.close()

        # 过滤已有预测的 + 按team_id去重(不同数据源可能有同一比赛)
        pending = []
        seen_pairs = set()
        for r in rows:
            if r['match_id'] in reported_keys:
                continue
            # 跳过占位队名(W50/W100等)
            home_name = r.get('home_team_name', '')
            away_name = r.get('away_team_name', '')
            if home_name.startswith('W') and len(home_name) <= 4:
                continue
            if away_name.startswith('W') and len(away_name) <= 4:
                continue
            # 按(home_id, away_id, date)去重
            pair_key = (r['home_team_id'], r['away_team_id'], r['match_date'])
            if pair_key in seen_pairs:
                continue
            seen_pairs.add(pair_key)
            pending.append(r)

        return pending
    except Exception as e:
        logger.error('获取未来赛事失败: %s', e)
        return []


def analyze_single(db_path: str, lottery_match_id: str) -> Optional[dict]:
    """Public entry point: analyze a single match by lottery_match_id.

    Used by API endpoints and analysis_service to delegate to the unified pipeline.
    Returns the full result dict or None on failure.
    """
    try:
        conn = sqlite3.connect(db_path, timeout=10)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("""
            SELECT lm.lottery_match_id, lm.home_team_id, lm.away_team_id,
                   lm.home_team_cn, lm.away_team_cn, lm.match_date, lm.match_time,
                   lm.league_name_cn, lm.handicap_line, lm.oddsfe_event_id,
                   lm.play_types, lm.beijing_time
            FROM lottery_matches lm
            WHERE lm.lottery_match_id = ?
        """, (lottery_match_id,))
        row = cursor.fetchone()
        conn.close()

        if not row:
            logger.warning('analyze_single: match not found: %s', lottery_match_id)
            return None

        match = dict(row)
        return _analyze_single(db_path, match)
    except Exception as e:
        logger.error('analyze_single failed for %s: %s', lottery_match_id, e)
        return None


def _analyze_single(db_path: str, match: dict) -> dict:
    """分析单场比赛 — MatchProfile驱动，兼容lottery_matches和matches表

    当ComprehensiveAnalyzer返回None(数据不足)时, 用赔率基线生成简化预测。
    """
    try:
        from backend.app.analytics.comprehensive import ComprehensiveAnalyzer
        from backend.app.core.competition.engine import CompetitionRuleEngine, MatchProfile

        analyzer = ComprehensiveAnalyzer(db_path)
        home_id = match.get('home_team_id')
        away_id = match.get('away_team_id')

        if not home_id or not away_id:
            mid = match.get('lottery_match_id') or match.get('match_id')
            logger.debug('无team_id, 跳过: %s', mid)
            return None

        # 1. 加载MatchProfile(从classify步骤保存的分类报告)
        profile = _load_match_profile(db_path, match)

        # 2. 如果没有分类报告, 实时生成
        if profile is None:
            profile = _build_profile_on_the_fly(db_path, match)

        # 3. 执行分析(传入match_profile)
        result = analyzer.comprehensive_prediction(
            home_team_id=home_id,
            away_team_id=away_id,
            league_id=match.get('league_id'),
            match_date=match.get('match_date'),
            match_profile=profile,
        )

        # 4. 如果完整分析失败, 尝试赔率基线兜底
        if result is None or not result.get('final_prediction'):
            result = _odds_only_prediction(db_path, match, profile)
            if result is None:
                logger.debug('赔率兜底也失败: %s vs %s',
                             match.get('home_team_name') or home_id,
                             match.get('away_team_name') or away_id)
                return None

        # 4. 添加赔率基线(体彩赔率优先, oddsfe赔率备选)
        match_key = match.get('lottery_match_id') or match.get('match_id')
        odds_baseline = _get_match_odds_baseline(db_path, match.get('lottery_match_id'))
        if not odds_baseline:
            odds_baseline = _get_oddsfe_odds_baseline(db_path, home_id, away_id,
                                                        match.get('match_date'))
        if odds_baseline:
            result['odds_baseline'] = odds_baseline
            result['model_vs_odds'] = _compute_model_vs_odds(
                result['final_prediction']['probabilities'], odds_baseline
            )

        # 5. 模型-赔率分歧增强
        _apply_disagreement_boost(result)

        # 6. 因子分解
        result['factor_breakdown'] = _build_factor_breakdown(result, profile, db_path, match)

        # 7. 赔率区间draw校准
        _calibrate_draw(result, db_path)

        # 8. 用校准数据调整置信度
        _calibrate_confidence(result, db_path)

        # 9. 记录使用的权重
        result['weights_used'] = _get_weights_used(profile)

        world_cup_context = _load_world_cup_context(db_path, match)
        if world_cup_context:
            result.setdefault('competition_context', {})['world_cup_2026'] = world_cup_context
            result['world_cup_context'] = world_cup_context

        # 9b. Universal competition context — every match gets a type
        ct = 'league'
        if profile and hasattr(profile, 'competition_type'):
            ct = profile.competition_type.value if hasattr(profile.competition_type, 'value') else str(profile.competition_type)
        result.setdefault('competition_context', {})['type'] = ct
        result['competition_context'].update(_build_type_context(ct, profile, match, db_path))

        # 10. 情报包因子小幅调整：只使用已采集的真实证据，调整前后完整留痕
        _apply_intelligence_adjustment(db_path, match, result)

        # 10b. Use only pre-match team facts to nudge the goal matrix. SPF
        # stays on its calibrated axis; O/U, RQSPF, BQC and score candidates
        # then share the same attack/defense/tempo evidence.
        _apply_goal_profile_adjustment(db_path, match, result)
        _apply_prematch_evidence_guard(db_path, match, result)

        # 11. 大小球 — 使用统一ou_calculator(Pinnacle→TTG→Poisson)
        from backend.app.lottery.services.ou_calculator import compute_ou_analysis
        _sm_raw = result.get('base_prediction', {}).get('poisson', {}).get('score_matrix', None)
        _sm, _projection_meta = _prepare_joint_score_matrix(result, _sm_raw)
        if _projection_meta:
            result['joint_projection'] = _projection_meta
        ou_result = compute_ou_analysis(
            db_path=db_path,
            match=match,
            score_matrix=_sm,
            lottery_match_id=match.get('lottery_match_id'),
        )
        if isinstance(ou_result, dict):
            ou_result['line_profile'] = _load_ou_line_profile(db_path, match, ou_result)
            similarity_signal = _load_ou_similarity_signal(db_path, match, ou_result)
            if similarity_signal:
                ou_result['similarity_signal'] = similarity_signal
            _refine_ou_recommendation(ou_result, result, _sm, db_path=db_path, match=match)

        # 12. 6项玩法推算(比分/胜平负/让球/大小球/半全场)
        result['play_predictions'] = _compute_all_plays(result, match, ou_result, db_path)
        _apply_selective_recommendation_guard(db_path, match, result)
        _sync_final_prediction_scores(result)

        # 12b. 概率校准 — 用历史验证数据校准各玩法confidence, 直接提升命中率
        try:
            from backend.app.core.probability_calibration import apply_calibration_to_play
            plays = result.get('play_predictions', {})
            if isinstance(plays, dict):
                cal_applied = 0
                for ptype, play in plays.items():
                    if isinstance(play, dict) and ptype != 'top3_scores':
                        if apply_calibration_to_play(db_path, ptype, play):
                            cal_applied += 1
                if cal_applied:
                    result['calibration_applied'] = cal_applied
                    logger.debug('概率校准: 应用%d个玩法', cal_applied)
        except Exception as exc:
            logger.debug('概率校准应用失败: %s', exc)

        # 13. 比赛脚本 + 模型基线
        try:
            from backend.app.core.match_script import build_match_script
            result['match_script'] = build_match_script(result['play_predictions'], result, match)
        except Exception as exc:
            logger.debug('match_script build failed: %s', exc)

        try:
            from backend.app.core.model_baselines import compute_all_baselines, save_baselines
            _odds_bl = result.get('odds_baseline') or {}
            _elo_pred = None
            bp = result.get('base_prediction', {})
            if isinstance(bp.get('elo'), dict):
                _elo_pred = bp['elo']
            # Try to get elo from comprehensive result
            if not _elo_pred and isinstance(result.get('elo_prediction'), dict):
                _elo_pred = result['elo_prediction']
            baselines = compute_all_baselines(
                result,
                odds_baseline=_odds_bl,
                elo_prediction=_elo_pred,
                poisson_prediction=bp.get('poisson'),
                form_comparison=result.get('form_comparison'),
            )
            result['model_baselines'] = baselines
            # Persist baselines to DB
            try:
                _bl_conn = sqlite3.connect(db_path, timeout=15)
                save_baselines(
                    _bl_conn,
                    lottery_match_id=match_key,
                    baselines=baselines,
                    actual_results=None,  # no result yet at analysis time
                    handicap=_safe_float((result.get('play_predictions', {}).get('rqspf') or {}).get('handicap')),
                    ou_line=_safe_float((result.get('play_predictions', {}).get('ou') or {}).get('best_line')),
                )
                _bl_conn.close()
            except Exception as bl_exc:
                logger.debug('baseline save failed: %s', bl_exc)
        except Exception as exc:
            logger.debug('model_baselines compute failed: %s', exc)

        # 14. 保存报告
        report_id = _save_report(db_path, match, result)
        _save_foundation_snapshots(db_path, match, result, profile, report_id)

        # 15. 保存各玩法预测
        _save_play_predictions(db_path, match, result)

        return result

    except Exception as e:
        logger.error('分析异常: %s', e)
        import traceback
        logger.debug(traceback.format_exc())
        return None


def _odds_only_prediction(db_path: str, match: dict, profile) -> Optional[dict]:
    """赔率基线兜底预测 — 当ComprehensiveAnalyzer返回None时使用

    仅用赔率隐含概率生成预测, 标记confidence='odds_only'。
    如果也没有赔率, 返回None。
    """
    home_id = match.get('home_team_id')
    away_id = match.get('away_team_id')

    # 尝试获取赔率基线
    odds_baseline = _get_match_odds_baseline(db_path, match.get('lottery_match_id'))
    if not odds_baseline:
        odds_baseline = _get_oddsfe_odds_baseline(db_path, home_id, away_id,
                                                    match.get('match_date'))
    if not odds_baseline:
        return None

    probs = {
        'home_win': odds_baseline.get('home_win', 0),
        'draw': odds_baseline.get('draw', 0),
        'away_win': odds_baseline.get('away_win', 0),
    }
    rec = max(probs, key=probs.get)

    # 友谊赛/国家队比赛draw boost
    if profile and hasattr(profile, 'draw_boost') and profile.draw_boost > 0:
        draw_boost = profile.draw_boost
        probs['draw'] = min(probs['draw'] + draw_boost, 0.45)
        reduction = draw_boost
        total_non_draw = probs['home_win'] + probs['away_win']
        if total_non_draw > 0:
            probs['home_win'] = max(probs['home_win'] - reduction * (probs['home_win'] / total_non_draw), 0.05)
            probs['away_win'] = max(probs['away_win'] - reduction * (probs['away_win'] / total_non_draw), 0.05)
        # renormalize
        total = sum(probs.values())
        if total > 0:
            probs = {k: round(v / total, 4) for k, v in probs.items()}
        rec = max(probs, key=probs.get)

    # 从赔率推算xG(简化: 用隐含概率→平均进球)
    # home_win概率高→home_xg高, draw概率高→xg接近
    home_xg = 1.0 + probs['home_win'] * 1.5
    away_xg = 0.8 + probs['away_win'] * 1.2
    # 友谊赛进球偏少
    if profile and hasattr(profile, 'competition_type'):
        ct = profile.competition_type.value if hasattr(profile.competition_type, 'value') else str(profile.competition_type)
        if 'friendly' in ct:
            home_xg *= 0.85
            away_xg *= 0.85

    import math
    # 生成简化Poisson比分矩阵
    max_g = 6
    score_matrix = []
    for i in range(max_g):
        row = []
        for j in range(max_g):
            p = (math.exp(-home_xg) * home_xg**i / math.factorial(i) *
                 math.exp(-away_xg) * away_xg**j / math.factorial(j))
            row.append(round(p * 100, 2))
        score_matrix.append(row)

    return {
        'final_prediction': {
            'probabilities': probs,
            'predicted_result': rec,
            'confidence_level': 'odds_only',
            'expected_score': {'home': round(home_xg, 2), 'away': round(away_xg, 2)},
        },
        'base_prediction': {
            'poisson': {
                'score_matrix': score_matrix,
                'expected_score': {'home': round(home_xg, 2), 'away': round(away_xg, 2)},
            }
        },
        'odds_baseline': odds_baseline,
        'model_vs_odds': {
            'model_rec': rec,
            'odds_rec': rec,
            'agreement': True,
        },
        'factor_breakdown': {
            'factors': {'odds': {k: round(v, 4) for k, v in odds_baseline.items() if k in ('home_win', 'draw', 'away_win')}},
            'weights': {'odds': 1.0},
            'final': probs,
        },
        'weights_used': {'source': 'odds_only', 'weights': {'odds': 1.0}},
        'prediction_mode': 'odds_only',
    }


# ── MatchProfile加载 ──

def _load_match_profile(db_path: str, match: dict):
    """从lottery_analysis_reports加载分类报告"""
    try:
        conn = sqlite3.connect(db_path, timeout=10)
        cursor = conn.cursor()
        cursor.execute("""
            SELECT report_data FROM lottery_analysis_reports
            WHERE lottery_match_id = ? AND report_type = 'classification'
            ORDER BY created_at DESC LIMIT 1
        """, (match.get('lottery_match_id'),))
        row = cursor.fetchone()
        conn.close()

        if row:
            from backend.app.core.competition.engine import (
                CompetitionRuleEngine, CompetitionType, MatchProfile,
                MatchPhase, ParticipantType,
            )
            data = json.loads(row[0]) if isinstance(row[0], str) else row[0]
            # 从dict重建MatchProfile
            return _dict_to_profile(data)
    except Exception as e:
        logger.debug('加载分类报告失败: %s', e)
    return None


def _build_profile_on_the_fly(db_path: str, match: dict):
    """实时构建MatchProfile(当分类报告不存在时)"""
    from backend.app.core.competition.engine import CompetitionRuleEngine

    engine = CompetitionRuleEngine()

    # 优先使用matches表自带的信息
    competition_type_db = match.get('competition_type')
    participant_type_db = match.get('participant_type')
    league_name = match.get('league_name_en') or match.get('league_name_cn', '')

    # 如果matches表信息不全, 从leagues表补充
    if not competition_type_db or not participant_type_db:
        try:
            conn = sqlite3.connect(db_path, timeout=10)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("""
                SELECT l.name_en, l.competition_type, l.participant_type
                FROM leagues l
                WHERE l.league_id = ? OR l.name_cn = ? OR l.name_en = ?
                LIMIT 1
            """, (match.get('league_id'), match.get('league_name_cn', ''),
                  match.get('league_name_en', '')))
            league_row = cursor.fetchone()
            conn.close()
            if league_row:
                league_name = league_row['name_en'] or league_name
                if not competition_type_db:
                    competition_type_db = league_row['competition_type']
                if not participant_type_db:
                    participant_type_db = league_row['participant_type']
        except Exception:
            pass

    return engine.classify(
        league_name=league_name or match.get('league_name_cn', ''),
        competition_type_db=competition_type_db,
        participant_type_db=participant_type_db,
        home_team_type=match.get('home_team_type'),
        away_team_type=match.get('away_team_type'),
    )


def _dict_to_profile(data: dict):
    """从序列化的dict重建MatchProfile"""
    from backend.app.core.competition.engine import CompetitionType, MatchPhase, MatchProfile, ParticipantType

    ct = data.get('competition_type', 'league')
    pt = data.get('participant_type', 'club')
    mp = data.get('match_phase', 'league_phase')

    try:
        comp_type = CompetitionType(ct)
    except ValueError:
        comp_type = CompetitionType.LEAGUE

    try:
        part_type = ParticipantType(pt)
    except ValueError:
        part_type = ParticipantType.CLUB

    try:
        match_phase = MatchPhase(mp)
    except ValueError:
        match_phase = MatchPhase.LEAGUE_PHASE

    return MatchProfile(
        competition_type=comp_type,
        participant_type=part_type,
        match_phase=match_phase,
        is_national=part_type.value == 'national',
        is_club=part_type.value == 'club',
        is_neutral_venue=data.get('is_neutral_venue', False),
        draw_boost=data.get('draw_boost', 0.0),
        upset_risk=data.get('upset_risk', 0.0),
        rotation_risk=data.get('rotation_risk', 0.0),
        motivation_weight=data.get('motivation_weight', 0.5),
        league_name=data.get('league_name', ''),
        tags=data.get('tags', []),
    )


# ── 赔率基线 ──

def _parse_lottery_datetime(value: Any) -> Optional[datetime]:
    text = str(value or '').strip().replace('T', ' ')
    if not text:
        return None
    for fmt, width in (
        ('%Y-%m-%d %H:%M:%S', 19),
        ('%Y-%m-%d %H:%M', 16),
        ('%Y-%m-%d', 10),
    ):
        try:
            return datetime.strptime(text[:width], fmt)
        except ValueError:
            continue
    return None


def _get_lottery_kickoff(cursor, lottery_match_id: str) -> Optional[datetime]:
    try:
        cursor.execute(
            """
            SELECT beijing_time, match_date, match_time
            FROM lottery_matches
            WHERE lottery_match_id = ?
            """,
            (lottery_match_id,),
        )
        row = cursor.fetchone()
        if not row:
            return None
        beijing_time = row['beijing_time'] if isinstance(row, sqlite3.Row) else row[0]
        match_date = row['match_date'] if isinstance(row, sqlite3.Row) else row[1]
        match_time = row['match_time'] if isinstance(row, sqlite3.Row) else row[2]
        parsed = _parse_lottery_datetime(beijing_time)
        if parsed:
            return parsed
        return _parse_lottery_datetime('%s %s' % (str(match_date or '')[:10], match_time or ''))
    except Exception:
        return None


def _odds_row_captured_at(row: sqlite3.Row) -> Optional[datetime]:
    for key in ('update_time', 'created_at', 'updated_at'):
        if key in row.keys():
            parsed = _parse_lottery_datetime(row[key])
            if parsed:
                return parsed
    return None


def _select_prematch_lottery_odds_row(
    cursor,
    lottery_match_id: str,
    play_type: str,
    preferred_snapshots: Optional[List[Optional[str]]] = None,
    kickoff_grace_minutes: int = 5,
) -> Optional[sqlite3.Row]:
    snapshots = preferred_snapshots or ['opening', 'latest', 'midday', 'current', None]
    priority = {snapshot: index for index, snapshot in enumerate(snapshots)}
    cursor.execute(
        """
        SELECT odds_data, snapshot_type, update_time, created_at
        FROM lottery_odds
        WHERE lottery_match_id = ? AND play_type = ?
        ORDER BY created_at ASC
        """,
        (lottery_match_id, play_type),
    )
    rows = cursor.fetchall()
    if not rows:
        return None

    kickoff = _get_lottery_kickoff(cursor, lottery_match_id)
    allowed_until = kickoff + timedelta(minutes=kickoff_grace_minutes) if kickoff else None
    safe_rows = []
    rejected_rows = []
    for row in rows:
        snapshot = row['snapshot_type']
        if snapshot not in priority:
            continue
        captured_at = _odds_row_captured_at(row)
        sort_key = (priority.get(snapshot, len(priority)), captured_at or datetime.min)
        if allowed_until is None or captured_at is None or captured_at <= allowed_until:
            safe_rows.append((sort_key, row))
        else:
            rejected_rows.append((sort_key, row, captured_at, allowed_until))

    if safe_rows:
        safe_rows.sort(key=lambda item: item[0])
        return safe_rows[0][1]

    if rejected_rows:
        first = sorted(rejected_rows, key=lambda item: item[0])[0]
        logger.debug(
            'Skip post-kickoff %s odds for %s: snapshot=%s captured_at=%s cutoff=%s',
            play_type,
            lottery_match_id,
            first[1]['snapshot_type'],
            first[2],
            first[3],
        )
    return None


def _get_pinnacle_ou_baseline(db_path: str, match: dict) -> Optional[Dict]:
    """从oddsfe获取Pinnacle O/U赔率作为大小球基线

    返回与_get_ttg_odds_baseline()相同格式，供_compute_over_under()使用。
    """
    try:
        from backend.app.lottery.services.pinnacle_ou import get_pinnacle_ou_odds
        from fetchers.common.team_names import normalize_team_name

        # 获取队名
        home_en = ''
        away_en = ''
        match_date = match.get('match_date', '')

        # 尝试从team_id获取英文名
        home_id = match.get('home_team_id')
        away_id = match.get('away_team_id')
        if home_id and away_id:
            try:
                conn = sqlite3.connect(db_path, timeout=10)
                cursor = conn.cursor()
                cursor.execute("SELECT name_en FROM teams WHERE team_id = ?", (home_id,))
                row = cursor.fetchone()
                if row:
                    home_en = row[0]
                cursor.execute("SELECT name_en FROM teams WHERE team_id = ?", (away_id,))
                row = cursor.fetchone()
                if row:
                    away_en = row[0]
                conn.close()
            except Exception:
                pass

        # Fallback: normalize from Chinese names
        if not home_en:
            home_en = normalize_team_name(match.get('home_team_cn', '') or match.get('home_team', '') or '')
        if not away_en:
            away_en = normalize_team_name(match.get('away_team_cn', '') or match.get('away_team', '') or '')

        if not home_en or not away_en or not match_date:
            return None

        result = get_pinnacle_ou_odds(home_en, away_en, match_date, db_path)
        if not result:
            return None

        # Convert to _compute_over_under compatible format
        over_prob = result['over_prob']
        under_prob = result['under_prob']
        line = result['line']

        # Derive standard format
        ou_baseline = {
            'best_line': line,
            'best_line_over': round(over_prob, 4),
            'best_line_under': round(under_prob, 4),
            'source': f"pinnacle_ou_{result.get('source', 'unknown')}",
        }

        # Derive over_2_5 / under_2_5 from all_lines if available
        all_lines = result.get('all_lines', {})
        for line_str, line_odds in all_lines.items():
            try:
                lv = float(line_str)
                ov = line_odds.get('over', 0)
                un = line_odds.get('under', 0)
                if ov > 1 and un > 1:
                    p_over = (1/ov) / (1/ov + 1/un)
                    p_under = 1 - p_over
                    if abs(lv - 2.5) < 0.01:
                        ou_baseline['over_2_5'] = round(p_over, 4)
                        ou_baseline['under_2_5'] = round(p_under, 4)
                    elif abs(lv - 3.5) < 0.01:
                        ou_baseline['over_3_5'] = round(p_over, 4)
                        ou_baseline['under_3_5'] = round(p_under, 4)
            except (ValueError, KeyError):
                pass

        return ou_baseline

    except Exception as e:
        logger.debug(f'Pinnacle O/U baseline获取失败: {e}')
        return None


def _get_oddsfe_odds_baseline(db_path: str, home_team_id: int, away_team_id: int,
                              match_date: str) -> Optional[Dict]:
    """从oddsfe历史赔率获取赔率基线(matches表比赛)

    通过team_id匹配oddsfe球队, 获取Pinnacle收盘赔率
    """
    try:
        conn = sqlite3.connect(db_path, timeout=10)
        cursor = conn.cursor()

        # 通过team_id查队名
        cursor.execute("SELECT name_en FROM teams WHERE team_id = ?", (home_team_id,))
        home_name = cursor.fetchone()
        cursor.execute("SELECT name_en FROM teams WHERE team_id = ?", (away_team_id,))
        away_name = cursor.fetchone()

        if not home_name or not away_name:
            conn.close()
            return None

        # 查oddsfe赔率表(oddsfe_pinnacle_odds或其他赔率存储)
        # 先检查有没有oddsfe表
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name LIKE '%oddsfe%'")
        oddsfe_tables = [r[0] for r in cursor.fetchall()]
        conn.close()

        if not oddsfe_tables:
            return None

        # 尝试从oddsfe数据查找赔率
        # 这里用简单方法: 查最近的同名比赛赔率
        from fetchers.common.team_names import normalize_team_name
        home_norm = normalize_team_name(home_name[0])
        away_norm = normalize_team_name(away_name[0])

        conn = sqlite3.connect(db_path, timeout=10)
        cursor = conn.cursor()

        # 查CSV赔率表(football-data.co.uk的Pinnacle赔率)
        for table in oddsfe_tables:
            try:
                cursor.execute("PRAGMA table_info({})".format(table))
                cols = [r[1] for r in cursor.fetchall()]
                if 'home_team' in cols and 'away_team' in cols and 'psh' in cols:
                    cursor.execute("""
                        SELECT psh, psd, psa FROM {}
                        WHERE home_team = ? AND away_team = ? AND date = ?
                        LIMIT 1
                    """.format(table), (home_norm, away_norm, match_date))
                    row = cursor.fetchone()
                    if row and row[0] and row[1] and row[2]:
                        h, d, a = float(row[0]), float(row[1]), float(row[2])
                        if h > 1 and d > 1 and a > 1:
                            total = 1/h + 1/d + 1/a
                            conn.close()
                            return {
                                'home_win': round((1/h) / total, 4),
                                'draw': round((1/d) / total, 4),
                                'away_win': round((1/a) / total, 4),
                                'source': 'oddsfe_pinnacle',
                            }
            except Exception:
                continue

        conn.close()
        return None
    except Exception as e:
        logger.debug('oddsfe赔率基线获取失败: %s', e)
        return None


def _compute_model_vs_odds(model_probs: Dict, odds_baseline: Dict) -> Dict:
    """计算模型 vs 赔率对比"""
    # 只比较概率键，排除source等元数据
    prob_keys = ['home_win', 'draw', 'away_win']
    prob_only = {k: odds_baseline[k] for k in prob_keys if k in odds_baseline}
    model_rec = max(model_probs, key=model_probs.get)
    odds_rec = max(prob_only, key=prob_only.get) if prob_only else 'unknown'

    # 概率差异(模型-赔率)
    edge = {
        'home_win': round(model_probs.get('home_win', 0) - odds_baseline.get('home_win', 0), 4),
        'draw': round(model_probs.get('draw', 0) - odds_baseline.get('draw', 0), 4),
        'away_win': round(model_probs.get('away_win', 0) - odds_baseline.get('away_win', 0), 4),
    }

    return {
        'model_rec': model_rec,
        'odds_rec': odds_rec,
        'agreement': model_rec == odds_rec,
        'edge': edge,
    }


def _apply_disagreement_boost(result: dict):
    """模型-赔率分歧处理

    数据回测(76场): 模型与赔率一致时70%准确, 分歧时模型仅38.5%而赔率50%.
    策略: 不再boost模型方向, 而是将概率向赔率方向靠拢(blend 30%赔率).
    如果模型方向概率显著高于赔率(>=0.40且>赔率+5pp), 保留模型方向但降置信度.
    """
    mvo = result.get('model_vs_odds')
    if not mvo or mvo.get('agreement') is not False:
        return

    fp = result.get('final_prediction', {})
    probs = fp.get('probabilities', {})
    if not probs:
        return

    model_rec = mvo.get('model_rec', '')
    odds_rec = mvo.get('odds_rec', '')
    if not model_rec or not odds_rec:
        return

    key_map = {'home_win': 'home_win', 'draw': 'draw', 'away_win': 'away_win'}
    model_key = key_map.get(model_rec, model_rec)
    odds_key = key_map.get(odds_rec, odds_rec)
    model_prob = probs.get(model_key, 0)

    if _apply_spf_market_anchor(result, probs, model_key, model_prob):
        return

    # Blend towards market: 30% market weight when disagreeing
    odds_baseline = result.get('odds_baseline') if isinstance(result.get('odds_baseline'), dict) else {}
    market_probs = {
        k: _to_float(odds_baseline.get(k), 0.0) or 0.0
        for k in ('home_win', 'draw', 'away_win')
    }
    market_total = sum(market_probs.values())
    if market_total <= 0:
        return
    market_probs = {k: v / market_total for k, v in market_probs.items()}

    # If model is very confident (>=0.40 AND > market+5pp), keep model but lower confidence
    market_model_dir_prob = market_probs.get(model_key, 0)
    if model_prob >= 0.40 and model_prob > market_model_dir_prob + 0.05:
        # Model has conviction — keep direction but reduce confidence
        if fp.get('confidence_level') == 'high':
            fp['confidence_level'] = 'medium'
        elif fp.get('confidence_level') == 'medium':
            fp['confidence_level'] = 'low'
        mvo['disagreement_handling'] = {
            'action': 'keep_model_lower_confidence',
            'model_key': model_key,
            'model_prob': round(model_prob, 3),
            'market_prob': round(market_model_dir_prob, 3),
        }
        return

    # Default: blend 30% market into model probabilities
    blend_weight = 0.30
    before = {k: _to_float(probs.get(k), 0.0) or 0.0 for k in ('home_win', 'draw', 'away_win')}
    after = {
        k: before.get(k, 0) * (1 - blend_weight) + market_probs.get(k, 0) * blend_weight
        for k in ('home_win', 'draw', 'away_win')
    }
    total = sum(after.values())
    if total > 0:
        after = {k: round(v / total, 4) for k, v in after.items()}

    probs.clear()
    probs.update(after)
    fp['probabilities'] = probs
    fp['predicted_result'] = max(after, key=after.get)
    fp['confidence'] = round(max(after.values()), 4)
    fp['confidence_level'] = _confidence_level_from_probability(fp['confidence'])

    # Refresh model_vs_odds
    refreshed = _compute_model_vs_odds(after, odds_baseline)
    result['model_vs_odds'] = refreshed

    mvo['disagreement_handling'] = {
        'action': 'blend_towards_market',
        'blend_weight': blend_weight,
        'model_key_before': model_key,
        'odds_key': odds_key,
        'before_probabilities': {k: round(before.get(k, 0), 3) for k in ('home_win', 'draw', 'away_win')},
        'after_probabilities': after,
    }


def _apply_spf_market_anchor(result: dict, probs: dict, model_key: str, model_prob: float) -> bool:
    """Respect a strong prematch SPF market when the model edge is thin.

    The previous disagreement boost always rewarded the model side when model
    and odds disagreed. That is too aggressive for cases where the market has a
    clear favorite and the model is only weakly separated from its second choice.
    """
    if _env_float('FOOTBALL_SPF_MARKET_ANCHOR_ENABLED', 1.0, 0.0, 1.0) < 1.0:
        return False

    odds_baseline = result.get('odds_baseline') if isinstance(result.get('odds_baseline'), dict) else {}
    mvo = result.get('model_vs_odds') if isinstance(result.get('model_vs_odds'), dict) else {}
    fp = result.get('final_prediction') if isinstance(result.get('final_prediction'), dict) else {}
    prob_keys = ('home_win', 'draw', 'away_win')
    market_probs = {
        key: _to_float(odds_baseline.get(key), 0.0) or 0.0
        for key in prob_keys
    }
    if sum(market_probs.values()) <= 0:
        return False

    market_probs = _normalize_probs(market_probs)
    market_rec = max(market_probs, key=market_probs.get)
    if model_key == 'draw' or market_rec == model_key or market_rec == 'draw':
        return False

    source_quality = str(odds_baseline.get('source_quality') or '').strip()
    source = str(odds_baseline.get('source') or '').strip()
    if source_quality and source_quality not in {'prematch', 'market_unknown'}:
        return False
    if not source_quality and source not in {'current', 'opening', 'latest', 'midday'}:
        return False

    market_values = sorted(market_probs.values(), reverse=True)
    market_top = market_values[0]
    market_gap = market_values[0] - market_values[1] if len(market_values) > 1 else market_values[0]
    model_values = sorted((_to_float(probs.get(key), 0.0) or 0.0 for key in prob_keys), reverse=True)
    model_gap = model_values[0] - model_values[1] if len(model_values) > 1 else model_values[0]

    if market_top < _env_float('FOOTBALL_SPF_MARKET_ANCHOR_MIN', 0.55, 0.0, 1.0):
        return False
    if market_gap < _env_float('FOOTBALL_SPF_MARKET_ANCHOR_GAP', 0.12, 0.0, 1.0):
        return False
    if model_prob > _env_float('FOOTBALL_SPF_MARKET_ANCHOR_MAX_MODEL_PROB', 0.52, 0.0, 1.0):
        return False
    if model_gap > _env_float('FOOTBALL_SPF_MARKET_ANCHOR_MAX_MODEL_GAP', 0.12, 0.0, 1.0):
        return False

    market_weight = _env_float('FOOTBALL_SPF_MARKET_ANCHOR_WEIGHT', 0.62, 0.0, 1.0)
    before = {key: _to_float(probs.get(key), 0.0) or 0.0 for key in prob_keys}
    before = _normalize_probs(before)
    draw_close_gap = _env_float('FOOTBALL_SPF_MARKET_ANCHOR_DRAW_CLOSE_GAP', 0.015, 0.0, 1.0)
    draw_close_min = _env_float('FOOTBALL_SPF_MARKET_ANCHOR_DRAW_CLOSE_MIN', 0.30, 0.0, 1.0)
    if (
        model_key != 'draw'
        and before.get('draw', 0.0) >= draw_close_min
        and before.get(model_key, 0.0) - before.get('draw', 0.0) <= draw_close_gap
    ):
        return False
    after = {
        key: (before.get(key, 0.0) * (1.0 - market_weight)) + (market_probs.get(key, 0.0) * market_weight)
        for key in prob_keys
    }
    after = _normalize_probs(after)

    probs.clear()
    probs.update(after)
    fp['probabilities'] = probs
    fp['predicted_result'] = max(after, key=after.get)
    fp['confidence'] = round(max(after.values()), 4)
    fp['confidence_level'] = _confidence_level_from_probability(fp['confidence'])

    mvo['market_anchor'] = {
        'applied': True,
        'reason': 'strong_prematch_market_low_model_edge',
        'market_rec': market_rec,
        'model_rec_before': model_key,
        'market_top_probability': round(market_top, 4),
        'market_gap': round(market_gap, 4),
        'model_probability': round(float(model_prob or 0.0), 4),
        'model_gap': round(model_gap, 4),
        'market_weight': round(market_weight, 4),
        'before_probabilities': {key: round(before.get(key, 0.0), 4) for key in prob_keys},
        'after_probabilities': after,
    }
    refreshed = _compute_model_vs_odds(after, odds_baseline)
    refreshed['market_anchor'] = mvo['market_anchor']
    result['model_vs_odds'] = refreshed
    return True


def _calibrate_draw(result: dict, db_path: str):
    """用warmup校准数据调整draw概率 — 基于赔率区间的历史平局率

    核心逻辑: 如果某赔率区间历史平局率>模型预测draw概率,
    则提升draw概率至历史水平(保守: 取70%的差距注入)
    """
    try:
        conn = sqlite3.connect(db_path, timeout=10)
        cursor = conn.cursor()
        cursor.execute("""
            SELECT cal_data FROM odds_calibration
            WHERE cal_key = 'odds_bucket_accuracy'
        """)
        row = cursor.fetchone()
        conn.close()

        if not row:
            return

        cal = json.loads(row[0]) if isinstance(row[0], str) else row[0]

        # Get home odds from odds_baseline
        ob = result.get('odds_baseline')
        if not ob:
            return

        home_prob = ob.get('home_win', 0)
        if home_prob <= 0:
            return
        home_odds = 1.0 / home_prob

        # Find bucket
        bucket = None
        for name, lo, hi in [('<1.30', 0, 1.30), ('1.30-1.60', 1.30, 1.60),
                              ('1.60-2.00', 1.60, 2.00), ('2.00-3.00', 2.00, 3.00),
                              ('>3.00', 3.00, 999)]:
            if lo <= home_odds < hi:
                bucket = name
                break

        if not bucket or bucket not in cal:
            return

        historical_draw_rate = cal[bucket].get('draw_rate', 0)
        if historical_draw_rate <= 0:
            return

        # Get current model draw probability
        fp = result.get('final_prediction', {})
        probs = fp.get('probabilities', {})
        model_draw = probs.get('draw', 0)

        if model_draw <= 0:
            return

        # If historical draw rate > model draw, inject boost
        # Conservative: inject 70% of the gap
        if historical_draw_rate > model_draw:
            gap = historical_draw_rate - model_draw
            boost = gap * 0.70

            new_draw = min(model_draw + boost, 0.45)  # cap at 45%
            # Redistribute: reduce home_win and away_win proportionally
            reduction = new_draw - model_draw
            total_non_draw = probs.get('home_win', 0) + probs.get('away_win', 0)
            if total_non_draw > 0:
                home_share = probs.get('home_win', 0) / total_non_draw
                away_share = probs.get('away_win', 0) / total_non_draw
                probs['draw'] = round(new_draw, 4)
                probs['home_win'] = round(max(probs.get('home_win', 0) - reduction * home_share, 0.05), 4)
                probs['away_win'] = round(max(probs.get('away_win', 0) - reduction * away_share, 0.05), 4)

                # Renormalize
                total = probs['home_win'] + probs['draw'] + probs['away_win']
                if total > 0:
                    probs['home_win'] = round(probs['home_win'] / total, 4)
                    probs['draw'] = round(probs['draw'] / total, 4)
                    probs['away_win'] = round(probs['away_win'] / total, 4)

                fp['draw_calibration'] = {
                    'bucket': bucket,
                    'historical_draw_rate': round(historical_draw_rate, 3),
                    'model_draw_before': round(model_draw, 3),
                    'model_draw_after': probs['draw'],
                    'boost_applied': round(boost, 3),
                }

    except Exception as e:
        logger.debug(f'Draw校准失败: {e}')


def _calibrate_confidence(result: dict, db_path: str):
    """用warmup校准数据调整置信度 — 基于赔率区间的历史准确率"""
    try:
        conn = sqlite3.connect(db_path, timeout=10)
        cursor = conn.cursor()
        cursor.execute("""
            SELECT cal_data FROM odds_calibration
            WHERE cal_key = 'odds_bucket_accuracy'
        """)
        row = cursor.fetchone()
        conn.close()

        if not row:
            return

        cal = json.loads(row[0]) if isinstance(row[0], str) else row[0]

        # Get home odds from odds_baseline
        ob = result.get('odds_baseline')
        if not ob:
            return

        # Convert implied prob to approximate odds
        home_prob = ob.get('home_win', 0)
        if home_prob <= 0:
            return
        home_odds = 1.0 / home_prob

        # Find bucket
        bucket = None
        for name, lo, hi in [('<1.30', 0, 1.30), ('1.30-1.60', 1.30, 1.60),
                              ('1.60-2.00', 1.60, 2.00), ('2.00-3.00', 2.00, 3.00),
                              ('>3.00', 3.00, 999)]:
            if lo <= home_odds < hi:
                bucket = name
                break

        if not bucket or bucket not in cal:
            return

        bucket_acc = cal[bucket].get('accuracy', 0.5)
        draw_rate = cal[bucket].get('draw_rate', 0.25)

        # Adjust confidence_level based on historical accuracy
        fp = result.get('final_prediction', {})
        current_conf = fp.get('confidence_level', 'medium')

        if bucket_acc >= 0.70:
            # Strong favorites zone — high confidence
            if current_conf in ('low', 'medium'):
                fp['confidence_level'] = 'high'
                fp['calibration_note'] = f'{bucket}区历史{bucket_acc:.0%}准确, 提升置信度'
        elif bucket_acc <= 0.45:
            # Hard zone — reduce confidence
            if current_conf in ('high', 'medium'):
                fp['confidence_level'] = 'low'
                fp['calibration_note'] = f'{bucket}区历史{bucket_acc:.0%}准确, 降低置信度'

        # If draw rate is high (>25%), note it
        if draw_rate > 0.25:
            fp['draw_risk_note'] = f'{bucket}区平局率{draw_rate:.0%}'

    except Exception as e:
        logger.debug(f'校准置信度失败: {e}')


def _build_factor_breakdown(result: dict, profile, db_path: str, match: dict) -> dict:
    """构建因子分解 — 每个分析器的概率贡献"""
    factors = {}
    prob_keys = ['home_win', 'draw', 'away_win']

    # Elo
    if 'elo_prediction' in result:
        ep = result['elo_prediction']
        probs = ep.get('probabilities', ep.get('elo_probabilities', {}))
        if probs:
            factors['elo'] = {k: round(probs.get(k, 0), 4) for k in prob_keys}

    # Poisson
    if 'poisson_prediction' in result:
        pp = result['poisson_prediction']
        probs = pp.get('probabilities', pp.get('match_probabilities', {}))
        if probs:
            factors['poisson'] = {k: round(probs.get(k, 0), 4) for k in prob_keys}

    # H2H
    if 'h2h_analysis' in result:
        h2h = result['h2h_analysis']
        probs = h2h.get('probabilities', h2h.get('win_probabilities', {}))
        if probs:
            # h2h可能用home/away/draw
            mapped = {}
            for k in prob_keys:
                mapped[k] = round(probs.get(k, probs.get('home' if k == 'home_win' else k, 0)), 4)
            factors['h2h'] = mapped

    # Form
    if 'form_comparison' in result:
        fc = result['form_comparison']
        probs = fc.get('probabilities', {})
        if probs:
            factors['form'] = {k: round(probs.get(k, 0), 4) for k in prob_keys}
        elif 'form_score' in fc:
            # 从form_score推导方向
            diff = fc.get('form_diff', fc.get('home_form', 0) - fc.get('away_form', 0))
            if diff > 0.1:
                factors['form'] = {'home_win': 0.45, 'draw': 0.28, 'away_win': 0.27}
            elif diff < -0.1:
                factors['form'] = {'home_win': 0.27, 'draw': 0.28, 'away_win': 0.45}
            else:
                factors['form'] = {'home_win': 0.35, 'draw': 0.32, 'away_win': 0.33}

    # Home/Away
    if 'home_away_analysis' in result:
        ha = result['home_away_analysis']
        probs = ha.get('probabilities', {})
        if probs:
            factors['home_away'] = {k: round(probs.get(k, 0), 4) for k in prob_keys}

    # Motivation
    if 'motivation_analysis' in result:
        ma = result['motivation_analysis']
        probs = ma.get('probabilities', {})
        if probs:
            factors['motivation'] = {k: round(probs.get(k, 0), 4) for k in prob_keys}

    # News
    if 'news_factors_analysis' in result:
        nf = result['news_factors_analysis']
        probs = nf.get('probabilities', {})
        if probs:
            factors['news'] = {k: round(probs.get(k, 0), 4) for k in prob_keys}

    # Odds baseline
    if 'odds_baseline' in result and result['odds_baseline']:
        ob = result['odds_baseline']
        factors['odds'] = {k: round(ob.get(k, 0), 4) for k in prob_keys}

    # Add weights
    weights_used = _get_weights_used(profile)
    weights = weights_used.get('weights', {})

    # Add provenance — evidence source for each factor
    provenance = _build_factor_provenance(result, db_path, match)

    return {
        'factors': factors,
        'weights': weights,
        'final': {k: round(result['final_prediction']['probabilities'].get(k, 0), 4) for k in prob_keys},
        'provenance': provenance,
    }


def _get_weights_used(profile) -> Dict:
    """获取使用的权重配置"""
    if profile is None:
        return {'source': 'default', 'weights': {}}

    ct = profile.competition_type.value if hasattr(profile, 'competition_type') else 'league'

    WEIGHT_PROFILES = {
        'league':         {'odds': 0.35, 'elo': 0.25, 'poisson': 0.25, 'form': 0.10, 'other': 0.05},
        'cup':            {'odds': 0.35, 'elo': 0.20, 'poisson': 0.20, 'form': 0.10, 'cup': 0.15},
        'super_cup':      {'odds': 0.35, 'elo': 0.25, 'poisson': 0.20, 'form': 0.10, 'other': 0.10},
        'playoff':        {'odds': 0.40, 'elo': 0.20, 'poisson': 0.20, 'form': 0.10, 'motivation': 0.10},
        'wc_qualifier':   {'odds': 0.40, 'elo': 0.20, 'poisson': 0.20, 'form': 0.10, 'motivation': 0.10},
        'nations_league': {'odds': 0.40, 'elo': 0.20, 'poisson': 0.20, 'form': 0.10, 'motivation': 0.10},
        'friendly_intl':  {'odds': 0.45, 'elo': 0.15, 'poisson': 0.15, 'form': 0.05, 'friendly': 0.20},
        'tournament_intl':{'odds': 0.35, 'elo': 0.25, 'poisson': 0.25, 'form': 0.10, 'motivation': 0.05},
    }

    weights = WEIGHT_PROFILES.get(ct, WEIGHT_PROFILES['league'])
    return {'source': 'match_profile', 'competition_type': ct, 'weights': weights}


# ── P3: 因子证据溯源 ──

# Maps factor_key → (default_source, intel_requirement_key)
_FACTOR_SOURCE_MAP = {
    'elo':       ('elo_history', 'elo_rating'),
    'poisson':   ('matches_history', 'goal_tempo_profile'),
    'h2h':       ('matches_history', 'base_info'),
    'form':      ('matches_history', 'recent_form'),
    'home_away': ('matches_history', 'home_away_profile'),
    'motivation':('classify_rules', 'standings_context'),
    'news':      ('intelligence', 'injuries_suspensions'),
    'odds':      ('lottery_odds', 'odds_1x2'),
}


def _build_factor_provenance(result: dict, db_path: str, match: dict) -> dict:
    """为每个因子标注证据来源、采集时间、置信度、是否fallback、是否过期"""
    provenance = {}
    match_key = match.get('lottery_match_id')

    # Base provenance from static mapping — no DB query needed
    for factor_key, (default_source, req_key) in _FACTOR_SOURCE_MAP.items():
        if factor_key not in (result.get('factor_breakdown', {}).get('factors', {})):
            continue
        provenance[factor_key] = {
            'source': default_source,
            'requirement_key': req_key,
            'captured_at': None,
            'confidence': None,
            'fallback': False,
            'stale': False,
        }

    # Enrich from intelligence_requirements + intelligence_artifacts
    if not match_key:
        return provenance

    try:
        conn = sqlite3.connect(db_path, timeout=10)
        conn.row_factory = sqlite3.Row
        has_reqs = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='intelligence_requirements'"
        ).fetchone()
        if not has_reqs:
            conn.close()
            return provenance

        # Get latest job for this match
        job_row = conn.execute(
            "SELECT job_id FROM intelligence_jobs WHERE lottery_match_id = ? ORDER BY updated_at DESC LIMIT 1",
            (match_key,),
        ).fetchone()
        if not job_row:
            conn.close()
            return provenance

        job_id = job_row['job_id']

        # Get requirements with artifact metadata
        rows = conn.execute("""
            SELECT ir.key, ir.status, ir.confidence, ir.artifact_id,
                   ia.source, ia.captured_at, ia.confidence AS artifact_confidence
            FROM intelligence_requirements ir
            LEFT JOIN intelligence_artifacts ia ON ir.artifact_id = ia.artifact_id
            WHERE ir.job_id = ?
        """, (job_id,)).fetchall()
        conn.close()

        # Build lookup: requirement_key → artifact info
        req_map = {}
        for r in rows:
            req_map[r['key']] = {
                'status': r['status'],
                'confidence': r['artifact_confidence'] or r['confidence'],
                'source': r['source'],
                'captured_at': r['captured_at'],
                'fallback': r['status'] == 'fallback_used',
                'stale': r['status'] == 'stale',
            }

        # Match requirement keys to factors
        for factor_key, prov in provenance.items():
            req_key = prov['requirement_key']
            if req_key in req_map:
                info = req_map[req_key]
                if info['source']:
                    prov['source'] = info['source']
                prov['captured_at'] = info['captured_at']
                prov['confidence'] = info['confidence']
                prov['fallback'] = info['fallback']
                prov['stale'] = info['stale']

        # Also check odds source specifically
        odds_prov = provenance.get('odds')
        if odds_prov and odds_prov['source'] == 'lottery_odds':
            # Check if odds came from sporttery or oddsfe
            odds_baseline = result.get('odds_baseline', {})
            if odds_baseline.get('source'):
                odds_prov['source'] = odds_baseline['source']

    except Exception as e:
        logger.debug('factor provenance lookup failed: %s', e)

    return provenance



def _save_report(db_path: str, match: dict, result: dict):
    """保存分析报告 — 兼容lottery_matches和matches表"""
    try:
        conn = sqlite3.connect(db_path, timeout=10)
        cursor = conn.cursor()
        report_json = json.dumps(result, ensure_ascii=False, default=str)

        # lottery_matches用lottery_match_id, matches表用match_id
        match_key = match.get('lottery_match_id') or match.get('match_id')
        if not match_key:
            return

        # 添加队名信息到report方便前端展示
        if 'home_team_name' not in result and match.get('home_team_name'):
            result['home_team_name'] = match['home_team_name']
            result['away_team_name'] = match['away_team_name']

        report_json = json.dumps(result, ensure_ascii=False, default=str)
        columns = {row[1] for row in cursor.execute("PRAGMA table_info(lottery_analysis_reports)").fetchall()}
        latest_active = _load_latest_active_report(cursor, match_key) if "is_stale" in columns else None
        if latest_active and _report_signature(latest_active.get('report_data') or {}) == _report_signature(result):
            existing_report_id = latest_active.get('report_id')
            existing_quality = _report_quality(latest_active.get('report_data') or {})
            new_quality = _report_quality(result)
            if existing_report_id and new_quality <= existing_quality:
                cursor.execute(
                    """
                    UPDATE lottery_analysis_reports
                    SET is_stale = CASE WHEN report_id = ? THEN 0 ELSE 1 END
                    WHERE lottery_match_id = ?
                      AND report_type IN ('prediction', 'full')
                    """,
                    (existing_report_id, match_key),
                )
                conn.commit()
                conn.close()
                return existing_report_id

        cursor.execute("""
            INSERT OR REPLACE INTO lottery_analysis_reports
            (lottery_match_id, report_type, report_data, created_at)
            VALUES (?, 'prediction', ?, datetime('now'))
        """, (match_key, report_json))
        report_id = cursor.lastrowid
        if "is_stale" in columns:
            cursor.execute(
                """
                UPDATE lottery_analysis_reports
                SET is_stale = CASE WHEN report_id = ? THEN 0 ELSE 1 END
                WHERE lottery_match_id = ?
                  AND report_type IN ('prediction', 'full')
                """,
                (report_id, match_key),
            )
        conn.commit()
        conn.close()
        return report_id
    except Exception as e:
        logger.debug('报告保存失败: %s', e)
        return None


def _save_foundation_snapshots(db_path: str, match: dict, result: dict, profile, report_id=None) -> None:
    """Persist durable match context and model feature snapshots."""
    try:
        from backend.app.data_access.foundation_dao import FoundationDAO

        match_key = match.get('lottery_match_id') or match.get('match_id')
        if not match_key:
            return

        intel_context = _load_intelligence_context(db_path, match)
        competition_context = {
            'match': _jsonable(match),
            'profile': _jsonable(profile),
        }
        competition_context.update(_jsonable(result.get('competition_context') or {}))
        odds_context = {
            'odds_baseline': result.get('odds_baseline', {}),
            'model_vs_odds': result.get('model_vs_odds', {}),
            'play_predictions': {
                'spf': result.get('play_predictions', {}).get('spf', {}),
                'rqspf': result.get('play_predictions', {}).get('rqspf', {}),
                'ou': result.get('play_predictions', {}).get('ou', {}),
            },
        }
        data_quality = {
            'has_team_mapping': bool(match.get('home_team_id') and match.get('away_team_id')),
            'has_odds': bool(result.get('odds_baseline')),
            'has_intelligence_package': bool(intel_context.get('package')),
            'has_rqspf': bool(result.get('play_predictions', {}).get('rqspf')),
            'has_ou': bool(result.get('play_predictions', {}).get('ou')),
            'has_world_cup_context': bool(result.get('competition_context', {}).get('world_cup_2026')),
            'competition_type': result.get('competition_context', {}).get('type', 'league'),
            'source_report_id': report_id,
        }

        features = {
            'final_prediction': result.get('final_prediction', {}),
            'play_predictions': result.get('play_predictions', {}),
            'factor_breakdown': result.get('factor_breakdown', {}),
            'weights_used': result.get('weights_used', {}),
            'model_vs_odds': result.get('model_vs_odds', {}),
            'base_prediction': result.get('base_prediction', {}),
            'intelligence_adjustment': result.get('intelligence_adjustment', {}),
        }
        model_version = (
            result.get('model_version')
            or result.get('weights_used', {}).get('source')
            or 'core_analyze'
        )

        dao = FoundationDAO(db_path)
        dao.save_context_snapshot(
            match_key=match_key,
            competition_context=competition_context,
            odds_context=odds_context,
            intel_context=intel_context,
            data_quality=data_quality,
        )
        dao.save_feature_snapshot(
            match_key=match_key,
            features=features,
            model_version=model_version,
            source_report_id=report_id,
        )
    except Exception as e:
        logger.debug('foundation snapshots skipped: %s', e)


def _world_cup_context_progress(context: Optional[dict]) -> int:
    if not isinstance(context, dict):
        return -1
    group_stage = context.get('group_stage_context') or {}
    group = context.get('group') or {}
    teams = context.get('teams') or {}
    home = teams.get('home') or {}
    away = teams.get('away') or {}
    values = [
        group_stage.get('group_matches_finished'),
        group.get('matches_finished'),
        home.get('played'),
        away.get('played'),
    ]
    score = 0
    for value in values:
        try:
            score += max(0, int(value or 0))
        except Exception:
            pass
    return score


def _load_existing_world_cup_context(db_path: str, match_key: Optional[str]) -> dict:
    if not match_key:
        return {}
    try:
        conn = sqlite3.connect(db_path, timeout=10)
        conn.row_factory = sqlite3.Row
        conn.row_factory = sqlite3.Row
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            """
            SELECT report_data
            FROM lottery_analysis_reports
            WHERE lottery_match_id = ?
              AND report_type IN ('prediction', 'full')
            ORDER BY created_at DESC, report_id DESC
            LIMIT 8
            """,
            (match_key,),
        ).fetchall()
        conn.close()
        best = {}
        best_score = -1
        for item in row:
            try:
                report = json.loads(item['report_data'])
            except Exception:
                continue
            context = report.get('world_cup_context') or (report.get('competition_context') or {}).get('world_cup_2026') or {}
            score = _world_cup_context_progress(context)
            if score > best_score:
                best = context
                best_score = score
        return best or {}
    except Exception as e:
        logger.debug('existing world cup context load failed: %s', e)
        return {}


def _prefer_world_cup_context(new_context: dict, old_context: dict) -> dict:
    if not old_context:
        return new_context or {}
    if not new_context:
        return old_context

    new_status = new_context.get('data_status') or {}
    new_progress = _world_cup_context_progress(new_context)
    old_progress = _world_cup_context_progress(old_context)
    new_is_offline = new_status.get('mode') == 'offline_fallback' or new_context.get('context_freshness') == 'offline_fallback'

    if new_progress < old_progress:
        chosen = dict(old_context)
        chosen['context_freshness'] = chosen.get('context_freshness') or 'cached_better_snapshot'
        chosen['context_selection_note'] = 'kept_existing_context_with_more_group_progress'
        return chosen
    if new_is_offline and old_progress > 0 and new_progress <= old_progress:
        chosen = dict(old_context)
        chosen['context_freshness'] = chosen.get('context_freshness') or 'cached_live_snapshot'
        chosen['context_selection_note'] = 'kept_existing_context_because_new_context_was_offline_fallback'
        return chosen
    return new_context


def _load_world_cup_context(db_path: str, match: dict) -> dict:
    """Attach 2026 World Cup group/knockout context when the match is in scope."""
    league_text = ' '.join(str(match.get(key) or '') for key in ('league_name_cn', 'league_name', 'competition', 'competition_name'))
    league_text_l = league_text.lower()
    if (
        '世界杯' not in league_text
        and 'world cup' not in league_text_l
        and 'fifa world cup' not in league_text_l
    ):
        return {}

    home_team = match.get('home_team_cn') or match.get('home_team_name') or match.get('home_team')
    away_team = match.get('away_team_cn') or match.get('away_team_name') or match.get('away_team')
    if not home_team or not away_team:
        return {}

    try:
        from backend.app.worldcup.service import WorldCupContextService

        service = WorldCupContextService()
        match_date = match.get('beijing_time') or match.get('match_date')
        match_key = match.get('lottery_match_id') or match.get('match_id')
        existing_context = _load_existing_world_cup_context(db_path, match_key)
        try:
            context = service.get_match_context_by_teams(
                home_team=home_team,
                away_team=away_team,
                match_date=match_date,
                live=True,
            )
            data_status = context.get('data_status') or {}
            context['context_freshness'] = 'live' if data_status.get('mode') == 'live_api' else 'offline_fallback'
            return _prefer_world_cup_context(context, existing_context)
        except Exception as live_exc:
            context = service.get_match_context_by_teams(
                home_team=home_team,
                away_team=away_team,
                match_date=match_date,
                live=False,
            )
            context['context_freshness'] = 'offline_fallback'
            context['live_error'] = str(live_exc)
            return _prefer_world_cup_context(context, existing_context)
    except Exception as e:
        logger.debug('world cup context skipped: %s', e)
        return {}


def _load_intelligence_context(db_path: str, match: dict) -> dict:
    match_key = match.get('lottery_match_id')
    match_id = match.get('match_id')
    try:
        conn = sqlite3.connect(db_path, timeout=10)
        conn.row_factory = sqlite3.Row
        exists = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='intelligence_packages'"
        ).fetchone()
        if not exists:
            conn.close()
            return {}

        # Pre-match leakage gate: only use intel captured before kickoff
        kickoff = _get_lottery_kickoff(conn, match_key) if match_key else None
        intel_cutoff = (kickoff + timedelta(minutes=15)).isoformat() if kickoff else None

        params = []
        clauses = []
        if match_key:
            clauses.append("ij.lottery_match_id = ?")
            params.append(match_key)
        if match_id:
            clauses.append("ij.match_id = ?")
            params.append(match_id)
        if not clauses:
            conn.close()
            return {}

        cutoff_clause = "AND ip.updated_at <= ?" if intel_cutoff else ""
        if intel_cutoff:
            params.append(intel_cutoff)

        row = conn.execute(
            f"""
            SELECT ip.package_json, ip.completeness, ip.missing_required_json,
                   ip.updated_at, ij.job_id, ij.status
            FROM intelligence_packages ip
            JOIN intelligence_jobs ij ON ip.job_id = ij.job_id
            WHERE {' OR '.join(clauses)} {cutoff_clause}
            ORDER BY ip.updated_at DESC
            LIMIT 1
            """,
            params,
        ).fetchone()
        conn.close()
        if not row:
            return {}
        package = _loads_json(row['package_json'], {})
        summary = package.get('summary') if isinstance(package, dict) else {}
        return {
            'job_id': row['job_id'],
            'status': row['status'],
            'completeness': row['completeness'],
            'strict_completeness': summary.get('strict_completeness'),
            'required_total': summary.get('required_total'),
            'required_collected': summary.get('required_collected'),
            'required_fallback': summary.get('required_fallback'),
            'average_confidence': summary.get('average_confidence'),
            'missing_required': _loads_json(row['missing_required_json'], []),
            'package': package,
            'updated_at': row['updated_at'],
        }
    except Exception as e:
        logger.debug('load intelligence context failed: %s', e)
        return {}


PROB_KEYS = ('home_win', 'draw', 'away_win')


def _apply_intelligence_adjustment(db_path: str, match: dict, result: dict) -> None:
    """Apply a bounded, explainable probability overlay from collected intelligence.

    This layer is intentionally conservative: it does not invent missing data and it
    never lets intelligence artifacts dominate the base model/odds prediction.
    """
    try:
        fp = result.get('final_prediction') or {}
        raw_probs = fp.get('probabilities') or {}
        if not all(k in raw_probs for k in PROB_KEYS):
            return

        intel_context = _load_intelligence_context(db_path, match)
        package = intel_context.get('package') or {}
        artifacts = package.get('artifacts') or {}
        if not artifacts:
            result['intelligence_adjustment'] = {
                'applied': False,
                'reason': 'no_intelligence_package',
            }
            return

        before = {k: _to_float(raw_probs.get(k), 0.0) for k in PROB_KEYS}
        before = _normalize_probs(before)
        deltas = {k: 0.0 for k in PROB_KEYS}
        factors: List[Dict[str, Any]] = []

        _add_market_movement_delta(artifacts.get('market_movement'), deltas, factors)
        _add_injury_delta(artifacts.get('injuries_suspensions'), deltas, factors)
        _add_lineup_delta(artifacts.get('expected_lineup'), deltas, factors)
        _add_travel_fatigue_delta(artifacts.get('travel_fatigue'), deltas, factors)
        _add_major_experience_delta(artifacts.get('major_tournament_experience'), deltas, factors)
        _add_tournament_context_delta(
            artifacts.get('tournament_context'),
            result.get('world_cup_context'),
            deltas,
            factors,
        )

        capped_deltas = _cap_total_delta(deltas, max_total_abs=0.10)
        applied = any(abs(v) >= 0.001 for v in capped_deltas.values())
        adjustment = {
            'applied': applied,
            'source_job_id': intel_context.get('job_id'),
            'package_status': intel_context.get('status'),
            'package_completeness': intel_context.get('completeness'),
            'strict_completeness': intel_context.get('strict_completeness'),
            'required_total': intel_context.get('required_total'),
            'required_collected': intel_context.get('required_collected'),
            'required_fallback': intel_context.get('required_fallback'),
            'average_confidence': intel_context.get('average_confidence'),
            'package_updated_at': intel_context.get('updated_at'),
            'before_probabilities': {k: round(before.get(k, 0.0), 4) for k in PROB_KEYS},
            'raw_probability_delta': {k: round(deltas.get(k, 0.0), 4) for k in PROB_KEYS},
            'probability_delta': {k: round(capped_deltas.get(k, 0.0), 4) for k in PROB_KEYS},
            'factors': factors,
            'cap': {
                'max_total_abs_delta': 0.10,
                'was_capped': capped_deltas != deltas,
            },
        }

        if not applied:
            adjustment['reason'] = 'no_directional_intelligence_delta'
            result['intelligence_adjustment'] = adjustment
            return

        after = _apply_probability_delta(before, capped_deltas)
        fp['probabilities'] = after
        fp['predicted_result_before_intelligence'] = fp.get('predicted_result')
        fp['predicted_result'] = max(after, key=after.get)
        fp['confidence'] = round(max(after.values()), 4)
        fp['confidence_level'] = _confidence_level_from_probability(fp['confidence'])
        fp['intelligence_adjusted'] = True

        adjustment['after_probabilities'] = after
        adjustment['direction_before'] = max(before, key=before.get)
        adjustment['direction_after'] = fp['predicted_result']
        adjustment['direction_changed'] = adjustment['direction_before'] != adjustment['direction_after']
        result['intelligence_adjustment'] = adjustment

        if result.get('odds_baseline'):
            previous_mvo = result.get('model_vs_odds') or {}
            result['model_vs_odds'] = _compute_model_vs_odds(after, result['odds_baseline'])
            result['model_vs_odds']['before_intelligence'] = previous_mvo

        _refresh_factor_breakdown_after_intelligence(result, after)
        _inject_intelligence_overlay_weights(result, factors)
        _append_intelligence_adjustment_note(result, adjustment)
    except Exception as e:
        logger.debug('intelligence adjustment skipped: %s', e)


def _add_market_movement_delta(artifact: Optional[dict], deltas: Dict[str, float], factors: List[dict]) -> None:
    payload = _artifact_payload(artifact)
    if not payload:
        return

    spf_summary = None
    for summary in payload.get('play_summaries') or []:
        if str(summary.get('play_type') or '').lower() == 'spf':
            spf_summary = summary
            break
    comparison = (spf_summary or {}).get('comparison') or {}
    movements = comparison.get('movements') or []
    if not comparison.get('comparable') or not movements:
        factors.append({
            'key': 'market_movement',
            'title': '盘口变化',
            'applied': False,
            'reason': 'spf_opening_latest_not_comparable',
            **_artifact_provenance(artifact),
        })
        return

    key_map = {'3': 'home_win', '1': 'draw', '0': 'away_win'}
    factor_delta = {k: 0.0 for k in PROB_KEYS}
    evidence = []
    for item in movements:
        prob_key = key_map.get(str(item.get('key')))
        prob_delta = _to_float(item.get('probability_delta'), None)
        if not prob_key or prob_delta is None:
            continue
        effect = _clamp(prob_delta * 0.35, -0.025, 0.025)
        factor_delta[prob_key] += effect
        evidence.append(_market_evidence_text(item))

    if not any(abs(v) >= 0.001 for v in factor_delta.values()):
        factors.append({
            'key': 'market_movement',
            'title': '盘口变化',
            'applied': False,
            'reason': 'spf_market_move_too_small',
            'evidence': evidence[:3],
            **_artifact_provenance(artifact),
        })
        return

    _merge_deltas(deltas, factor_delta)
    factors.append({
        'key': 'market_movement',
        'title': '盘口变化',
        'applied': True,
        'delta': _rounded_delta(factor_delta),
        'evidence': evidence[:3],
        'reason': 'spf_opening_latest_implied_probability_changed',
        **_artifact_provenance(artifact),
    })


def _add_injury_delta(artifact: Optional[dict], deltas: Dict[str, float], factors: List[dict]) -> None:
    """Adjust probabilities based on confirmed injuries/suspensions from intelligence."""
    payload = _artifact_payload(artifact)
    if not payload:
        return

    summary = payload.get('summary') or {}
    mode = summary.get('mode', '')
    if mode == 'no_confirmed_absence_found':
        factors.append({
            'key': 'injury',
            'title': '伤停情况',
            'applied': False,
            'reason': 'no_confirmed_absence',
            **_artifact_provenance(artifact),
        })
        return

    # Count absent players per side
    home_absent = summary.get('local_home_absent', 0) or 0
    away_absent = summary.get('local_away_absent', 0) or 0
    # Also check API-confirmed counts
    home_absent += summary.get('api_home_count', 0) or 0
    away_absent += summary.get('api_away_count', 0) or 0
    # Also check ESPN counts (free API, available during season)
    home_absent += summary.get('espn_home_count', 0) or 0
    away_absent += summary.get('espn_away_count', 0) or 0

    # Check for key player absences in local_player_status
    local_ps = payload.get('local_player_status') or {}
    home_key = (local_ps.get('summary', {}).get('home') or {}).get('key_absent', 0) or 0
    away_key = (local_ps.get('summary', {}).get('away') or {}).get('key_absent', 0) or 0

    # Confidence scaling: API-confirmed > ESPN-confirmed > local_fallback
    conf = _artifact_confidence(artifact, 0.3)
    scale = 1.0 if mode == 'api_confirmed' else 0.8 if mode == 'espn_confirmed' else 0.5

    factor_delta = {k: 0.0 for k in PROB_KEYS}
    evidence = []

    # Home team absences → reduce home_win, boost draw/away
    if home_absent > 0:
        magnitude = min(home_absent * 0.012, 0.05) * scale
        key_boost = min(home_key * 0.02, 0.03) * scale
        factor_delta['home_win'] -= (magnitude + key_boost)
        factor_delta['draw'] += (magnitude + key_boost) * 0.4
        factor_delta['away_win'] += (magnitude + key_boost) * 0.6
        evidence.append('主队缺席%d人(核心%d)' % (home_absent, home_key))

    # Away team absences → reduce away_win, boost home/draw
    if away_absent > 0:
        magnitude = min(away_absent * 0.012, 0.05) * scale
        key_boost = min(away_key * 0.02, 0.03) * scale
        factor_delta['away_win'] -= (magnitude + key_boost)
        factor_delta['draw'] += (magnitude + key_boost) * 0.4
        factor_delta['home_win'] += (magnitude + key_boost) * 0.6
        evidence.append('客队缺席%d人(核心%d)' % (away_absent, away_key))

    if not any(abs(v) >= 0.001 for v in factor_delta.values()):
        factors.append({
            'key': 'injury',
            'title': '伤停情况',
            'applied': False,
            'reason': 'absence_counts_zero_or_below_threshold',
            'evidence': evidence,
            **_artifact_provenance(artifact),
        })
        return

    _merge_deltas(deltas, factor_delta)
    factors.append({
        'key': 'injury',
        'title': '伤停情况',
        'applied': True,
        'delta': _rounded_delta(factor_delta),
        'evidence': evidence,
        'reason': 'absence_based_adjustment',
        'mode': mode,
        **_artifact_provenance(artifact),
    })


def _add_lineup_delta(artifact: Optional[dict], deltas: Dict[str, float], factors: List[dict]) -> None:
    """Adjust probabilities based on lineup confidence from intelligence.

    Low-confidence or missing lineup → increase draw probability and reduce
    confidence in the favored side, since the outcome is more uncertain.
    """
    payload = _artifact_payload(artifact)
    if not payload:
        return

    conf = _artifact_confidence(artifact, 0.3)
    mode = payload.get('mode', '')
    tier = payload.get('lineup_confidence_tier', '')

    factor_delta = {k: 0.0 for k in PROB_KEYS}
    evidence = []

    if conf >= 0.60:
        # Confirmed/expected lineup available — no uncertainty penalty
        factors.append({
            'key': 'lineup',
            'title': '阵容信息',
            'applied': False,
            'reason': 'lineup_confident_enough',
            'tier': tier,
            **_artifact_provenance(artifact),
        })
        return

    # Low confidence or fallback lineup → draw boost
    if conf <= 0.30:
        # No lineup data at all — significant uncertainty
        draw_boost = 0.015
        evidence.append('无阵容数据(conf=%.2f)' % conf)
    elif conf <= 0.45:
        # Squad-only or news-inferred
        draw_boost = 0.010
        evidence.append('阵容不完整(conf=%.2f, tier=%s)' % (conf, tier))
    else:
        # Expected lineup but not confirmed
        draw_boost = 0.005
        evidence.append('预计阵容未确认(conf=%.2f)' % conf)

    _shift_draw_probability(factor_delta, draw_boost)
    evidence_text = '; '.join(evidence) if evidence else 'low_lineup_confidence'

    _merge_deltas(deltas, factor_delta)
    factors.append({
        'key': 'lineup',
        'title': '阵容信息',
        'applied': True,
        'delta': _rounded_delta(factor_delta),
        'evidence': [evidence_text],
        'reason': 'lineup_uncertainty_draw_boost',
        'tier': tier,
        **_artifact_provenance(artifact),
    })


def _add_travel_fatigue_delta(artifact: Optional[dict], deltas: Dict[str, float], factors: List[dict]) -> None:
    payload = _artifact_payload(artifact)
    if not payload:
        return
    comparison = payload.get('comparison') or {}
    home = payload.get('home') or {}
    away = payload.get('away') or {}
    short_side = comparison.get('short_rest_side')
    rest_delta_hours = _to_float(comparison.get('rest_hours_delta_home_minus_away'), None)
    confidence = _artifact_confidence(artifact)
    factor_delta = {k: 0.0 for k in PROB_KEYS}

    if short_side == 'home':
        _shift_win_probability(factor_delta, 'away', 0.018 * confidence, draw_share=0.30)
    elif short_side == 'away':
        _shift_win_probability(factor_delta, 'home', 0.018 * confidence, draw_share=0.30)
    elif short_side == 'both':
        _shift_draw_probability(factor_delta, 0.006 * confidence)
    elif rest_delta_hours is not None and abs(rest_delta_hours) >= 36:
        side = 'home' if rest_delta_hours > 0 else 'away'
        amount = min(abs(rest_delta_hours) / 240.0 * 0.014, 0.014) * confidence
        _shift_win_probability(factor_delta, side, amount, draw_share=0.25)

    evidence = [
        '主队休息%s天' % _display_number(home.get('rest_days')),
        '客队休息%s天' % _display_number(away.get('rest_days')),
    ]
    if rest_delta_hours is not None:
        evidence.append('休息差%s小时' % _signed_number(rest_delta_hours))
    gaps = payload.get('gaps') or []
    if gaps:
        evidence.append('缺口: ' + '；'.join(str(x) for x in gaps[:2]))

    if not any(abs(v) >= 0.001 for v in factor_delta.values()):
        factors.append({
            'key': 'travel_fatigue',
            'title': '休息赛程',
            'applied': False,
            'reason': 'no_material_rest_or_short_turnaround_edge',
            'evidence': evidence,
            **_artifact_provenance(artifact),
        })
        return

    _merge_deltas(deltas, factor_delta)
    factors.append({
        'key': 'travel_fatigue',
        'title': '休息赛程',
        'applied': True,
        'delta': _rounded_delta(factor_delta),
        'evidence': evidence,
        'reason': 'real_schedule_rest_difference',
        **_artifact_provenance(artifact),
    })


def _add_major_experience_delta(artifact: Optional[dict], deltas: Dict[str, float], factors: List[dict]) -> None:
    payload = _artifact_payload(artifact)
    if not payload:
        return
    comparison = payload.get('comparison') or {}
    major_delta = _to_float(comparison.get('major_matches_delta_home_minus_away'), 0.0)
    wc_delta = _to_float(comparison.get('world_cup_matches_delta_home_minus_away'), 0.0)
    knockout_delta = _to_float(comparison.get('knockout_matches_delta_home_minus_away'), 0.0)
    confidence = _artifact_confidence(artifact)
    experience_score = major_delta + wc_delta * 3.0 + knockout_delta * 2.0
    factor_delta = {k: 0.0 for k in PROB_KEYS}

    if abs(experience_score) >= 8:
        side = 'home' if experience_score > 0 else 'away'
        amount = min(abs(experience_score) / 80.0 * 0.022, 0.022) * confidence
        _shift_win_probability(factor_delta, side, amount, draw_share=0.20)

    home_db = (payload.get('home') or {}).get('db') or {}
    away_db = (payload.get('away') or {}).get('db') or {}
    evidence = [
        '大赛场次 %s:%s' % (_display_number(home_db.get('major_matches'), 0), _display_number(away_db.get('major_matches'), 0)),
        '世界杯场次 %s:%s' % (_display_number(home_db.get('world_cup_matches'), 0), _display_number(away_db.get('world_cup_matches'), 0)),
    ]

    if not any(abs(v) >= 0.001 for v in factor_delta.values()):
        factors.append({
            'key': 'major_tournament_experience',
            'title': '大赛经验',
            'applied': False,
            'reason': 'experience_gap_too_small_or_unavailable',
            'evidence': evidence,
            **_artifact_provenance(artifact),
        })
        return

    _merge_deltas(deltas, factor_delta)
    factors.append({
        'key': 'major_tournament_experience',
        'title': '大赛经验',
        'applied': True,
        'delta': _rounded_delta(factor_delta),
        'evidence': evidence,
        'reason': 'validated_finished_major_tournament_history_gap',
        **_artifact_provenance(artifact),
    })


def _add_tournament_context_delta(
    artifact: Optional[dict],
    live_world_cup_context: Optional[dict],
    deltas: Dict[str, float],
    factors: List[dict],
) -> None:
    payload = _artifact_payload(artifact)
    wc_context = live_world_cup_context or payload.get('world_cup_context') or {}
    if not wc_context:
        return

    confidence = _artifact_confidence(artifact, 0.65)
    factor_delta = {k: 0.0 for k in PROB_KEYS}
    pressure = wc_context.get('pressure') or {}
    home_pressure = (pressure.get('home') or {})
    away_pressure = (pressure.get('away') or {})
    h_level = _pressure_level_score(home_pressure.get('level'))
    a_level = _pressure_level_score(away_pressure.get('level'))
    if h_level is not None and a_level is not None and h_level != a_level:
        side = 'home' if h_level > a_level else 'away'
        gap = abs(h_level - a_level)
        amount = (0.008 if gap >= 2 else 0.004) * confidence
        _shift_win_probability(factor_delta, side, amount, draw_share=0.20)

    teams = wc_context.get('teams') or {}
    group_stage = wc_context.get('group_stage_context') or {}
    home_team = teams.get('home') or {}
    away_team = teams.get('away') or {}
    matchday = _to_float(group_stage.get('matchday'), None)
    home_points = _to_float(home_team.get('points'), None)
    away_points = _to_float(away_team.get('points'), None)
    both_direct = (
        home_team.get('qualification') == 'direct_round_of_32'
        and away_team.get('qualification') == 'direct_round_of_32'
    )
    if (
        matchday is not None and matchday >= 2
        and home_points is not None and away_points is not None
        and home_points >= 3 and away_points >= 3
        and both_direct
    ):
        _shift_draw_probability(factor_delta, 0.006 * confidence)

    evidence = []
    if home_pressure or away_pressure:
        evidence.append('压力 %s:%s' % (home_pressure.get('level') or '-', away_pressure.get('level') or '-'))
    if matchday is not None:
        evidence.append('小组第%d轮' % int(matchday))
    if home_points is not None and away_points is not None:
        evidence.append('积分 %s:%s' % (_display_number(home_points, 0), _display_number(away_points, 0)))

    if not any(abs(v) >= 0.001 for v in factor_delta.values()):
        factors.append({
            'key': 'tournament_context',
            'title': '世界杯形势',
            'applied': False,
            'reason': 'no_directional_group_pressure_edge',
            'evidence': evidence,
            **_artifact_provenance(artifact),
        })
        return

    _merge_deltas(deltas, factor_delta)
    factors.append({
        'key': 'tournament_context',
        'title': '世界杯形势',
        'applied': True,
        'delta': _rounded_delta(factor_delta),
        'evidence': evidence,
        'reason': 'live_world_cup_group_pressure_context',
        **_artifact_provenance(artifact),
    })


def _artifact_payload(artifact: Optional[dict]) -> dict:
    if not isinstance(artifact, dict):
        return {}
    payload = artifact.get('payload')
    return payload if isinstance(payload, dict) else {}


def _artifact_confidence(artifact: Optional[dict], default: float = 0.5) -> float:
    if not isinstance(artifact, dict):
        return default
    return _clamp(_to_float(artifact.get('confidence'), default), 0.0, 1.0)


def _artifact_provenance(artifact: Optional[dict]) -> dict:
    """Extract evidence provenance fields from an intelligence artifact dict."""
    if not isinstance(artifact, dict):
        return {}
    return {
        'source': artifact.get('source'),
        'captured_at': artifact.get('captured_at'),
        'confidence': _artifact_confidence(artifact),
        'fallback': artifact.get('status') == 'fallback_used',
        'stale': artifact.get('status') == 'stale',
    }


def _merge_deltas(target: Dict[str, float], source: Dict[str, float]) -> None:
    for key in PROB_KEYS:
        target[key] = target.get(key, 0.0) + source.get(key, 0.0)


def _shift_win_probability(deltas: Dict[str, float], side: str, amount: float, draw_share: float = 0.20) -> None:
    amount = max(0.0, amount)
    draw_share = _clamp(draw_share, 0.0, 0.8)
    if side == 'home':
        deltas['home_win'] += amount
        deltas['draw'] -= amount * draw_share
        deltas['away_win'] -= amount * (1.0 - draw_share)
    elif side == 'away':
        deltas['away_win'] += amount
        deltas['draw'] -= amount * draw_share
        deltas['home_win'] -= amount * (1.0 - draw_share)


def _shift_draw_probability(deltas: Dict[str, float], amount: float) -> None:
    amount = max(0.0, amount)
    deltas['draw'] += amount
    deltas['home_win'] -= amount / 2.0
    deltas['away_win'] -= amount / 2.0


def _apply_probability_delta(before: Dict[str, float], deltas: Dict[str, float]) -> Dict[str, float]:
    adjusted = {
        key: max(0.01, before.get(key, 0.0) + deltas.get(key, 0.0))
        for key in PROB_KEYS
    }
    return {k: round(v, 4) for k, v in _normalize_probs(adjusted).items()}


def _normalize_probs(probs: Dict[str, float]) -> Dict[str, float]:
    total = sum(max(0.0, _to_float(probs.get(k), 0.0)) for k in PROB_KEYS)
    if total <= 0:
        return {'home_win': 0.34, 'draw': 0.32, 'away_win': 0.34}
    return {k: max(0.0, _to_float(probs.get(k), 0.0)) / total for k in PROB_KEYS}


def _cap_total_delta(deltas: Dict[str, float], max_total_abs: float) -> Dict[str, float]:
    total_abs = sum(abs(deltas.get(k, 0.0)) for k in PROB_KEYS)
    if total_abs <= max_total_abs or total_abs <= 0:
        return dict(deltas)
    scale = max_total_abs / total_abs
    return {k: deltas.get(k, 0.0) * scale for k in PROB_KEYS}


def _refresh_factor_breakdown_after_intelligence(result: dict, after_probs: Dict[str, float]) -> None:
    breakdown = result.get('factor_breakdown')
    if not isinstance(breakdown, dict):
        return
    breakdown['final'] = {k: round(after_probs.get(k, 0.0), 4) for k in PROB_KEYS}
    factors = breakdown.setdefault('factors', {})
    if isinstance(factors, dict):
        factors['intelligence_overlay'] = {k: round(after_probs.get(k, 0.0), 4) for k in PROB_KEYS}
    # Add intelligence overlay provenance
    intel_adj = result.get('intelligence_adjustment') or {}
    intel_factors = intel_adj.get('factors') or []
    if intel_factors:
        prov = breakdown.setdefault('provenance', {})
        for f in intel_factors:
            key = f.get('key')
            if key:
                prov[key] = {
                    'source': f.get('source'),
                    'captured_at': f.get('captured_at'),
                    'confidence': f.get('confidence'),
                    'fallback': f.get('fallback', False),
                    'stale': f.get('stale', False),
                    'applied': f.get('applied', False),
                }


def _inject_intelligence_overlay_weights(result: dict, factors: List[dict]) -> None:
    active = [f for f in factors if f.get('applied')]
    if not active:
        return
    overlay_by_key = {
        'market_movement': 0.030,
        'travel_fatigue': 0.020,
        'major_tournament_experience': 0.020,
        'tournament_context': 0.020,
    }
    overlay = {f['key']: overlay_by_key.get(f['key'], 0.015) for f in active if f.get('key')}
    overlay_total = min(sum(overlay.values()), 0.085)
    weights_used = result.setdefault('weights_used', {})
    weights = weights_used.setdefault('weights', {})
    if not isinstance(weights, dict):
        return
    existing = {k: _to_float(v, 0.0) for k, v in weights.items() if _to_float(v, 0.0) > 0}
    existing_total = sum(existing.values())
    if existing_total > 0:
        scaled = {k: round(v / existing_total * (1.0 - overlay_total), 4) for k, v in existing.items()}
    else:
        scaled = {}
    for key, value in overlay.items():
        scaled[key] = round(value, 4)
    weights_used['weights'] = scaled
    weights_used['intelligence_overlay'] = {
        'applied': True,
        'weight_total': round(overlay_total, 4),
        'active_factors': [f.get('key') for f in active],
        'note': '情报层是基于真实采集包的保守后置修正，已缩放原有权重保持总量接近1。',
    }
    if isinstance(result.get('factor_breakdown'), dict):
        result['factor_breakdown']['weights'] = scaled


def _append_intelligence_adjustment_note(result: dict, adjustment: dict) -> None:
    adjustments = result.setdefault('adjustments', [])
    if not isinstance(adjustments, list):
        return
    adjustments.append({
        'type': 'intelligence_overlay',
        'applied': adjustment.get('applied'),
        'source_job_id': adjustment.get('source_job_id'),
        'probability_delta': adjustment.get('probability_delta'),
        'direction_before': adjustment.get('direction_before'),
        'direction_after': adjustment.get('direction_after'),
        'factors': [
            {
                'key': f.get('key'),
                'title': f.get('title'),
                'applied': f.get('applied'),
                'delta': f.get('delta'),
                'reason': f.get('reason'),
            }
            for f in adjustment.get('factors', [])
        ],
    })


def _apply_prematch_evidence_guard(db_path: str, match: dict, result: dict) -> None:
    """Prevent confident pre-match picks when the evidence base is too thin.

    The model is allowed to disagree with the market only when it can point to
    enough collected evidence. If key inputs are missing, a strong market line
    becomes the conservative baseline and the report records exactly what must
    be collected next.
    """
    try:
        fp = result.get('final_prediction') if isinstance(result.get('final_prediction'), dict) else {}
        probs = fp.get('probabilities') if isinstance(fp.get('probabilities'), dict) else {}
        odds_baseline = result.get('odds_baseline') if isinstance(result.get('odds_baseline'), dict) else {}
        if not fp or not probs:
            return

        evidence = _prematch_evidence_state(db_path, match, result)
        missing = evidence.get('missing_critical') or []
        low_conf = evidence.get('low_confidence_critical') or []
        no_package = evidence.get('package_status') == 'missing'
        severe_gap = no_package or len(missing) >= 2 or ('goal_tempo_profile' in missing)
        has_gap = severe_gap or bool(missing or low_conf)
        guard = {
            'applied': False,
            'reason': 'evidence_sufficient',
            'evidence': evidence,
        }

        if not has_gap:
            result['analysis_guard'] = guard
            return

        market_probs = _market_probabilities_from_odds(odds_baseline)
        model_rec = max(probs, key=probs.get)
        market_rec = max(market_probs, key=market_probs.get) if market_probs else None
        market_values = sorted(market_probs.values(), reverse=True) if market_probs else []
        market_top = market_values[0] if market_values else 0.0
        market_gap = (market_values[0] - market_values[1]) if len(market_values) > 1 else market_top
        disagreement = bool(market_rec and market_rec != model_rec)

        if disagreement and market_top >= 0.62 and market_gap >= 0.12:
            before = _normalize_probs({key: _to_float(probs.get(key), 0.0) or 0.0 for key in PROB_KEYS})
            weight = 0.72 if severe_gap else 0.55
            after = _normalize_probs({
                key: before.get(key, 0.0) * (1.0 - weight) + market_probs.get(key, 0.0) * weight
                for key in PROB_KEYS
            })
            probs.clear()
            probs.update(after)
            fp['probabilities'] = probs
            fp['predicted_result_before_evidence_guard'] = model_rec
            fp['predicted_result'] = max(after, key=after.get)
            fp['confidence'] = round(max(after.values()), 4)
            fp['confidence_level'] = 'low' if severe_gap else min(
                _confidence_level_from_probability(fp['confidence']),
                'medium',
                key={'low': 0, 'medium': 1, 'high': 2}.get,
            )
            guard.update({
                'applied': True,
                'reason': 'strong_market_disagreement_with_insufficient_evidence',
                'action': 'market_anchor_and_confidence_cap',
                'market_rec': market_rec,
                'model_rec_before': model_rec,
                'market_top_probability': round(market_top, 4),
                'market_gap': round(market_gap, 4),
                'market_weight': round(weight, 4),
                'before_probabilities': {key: round(before.get(key, 0.0), 4) for key in PROB_KEYS},
                'after_probabilities': after,
            })
            if odds_baseline:
                result['model_vs_odds'] = _compute_model_vs_odds(after, odds_baseline)
                result['model_vs_odds']['evidence_guard'] = guard
        else:
            current_conf = _to_float(fp.get('confidence'), max(probs.values()) if probs else 0.0) or 0.0
            cap = 0.40 if severe_gap else 0.48
            fp['confidence'] = round(min(current_conf, cap), 4)
            fp['confidence_level'] = 'low' if severe_gap else 'medium'
            guard.update({
                'applied': True,
                'reason': 'insufficient_evidence_confidence_cap',
                'action': 'confidence_cap',
                'confidence_cap': cap,
            })

        result['analysis_guard'] = guard
        adjustments = result.setdefault('adjustments', [])
        if isinstance(adjustments, list):
            adjustments.append({
                'type': 'prematch_evidence_guard',
                'applied': guard.get('applied'),
                'reason': guard.get('reason'),
                'missing_critical': missing,
                'low_confidence_critical': low_conf,
                'action': guard.get('action'),
            })
    except Exception as exc:
        logger.debug('prematch evidence guard skipped: %s', exc)


def _prematch_evidence_state(db_path: str, match: dict, result: dict) -> dict:
    intel_context = _load_intelligence_context(db_path, match)
    package = intel_context.get('package') if isinstance(intel_context.get('package'), dict) else {}
    requirements = package.get('requirements') if isinstance(package.get('requirements'), list) else []
    req_by_key = {str(req.get('key')): req for req in requirements if req.get('key')}
    artifacts = package.get('artifacts') if isinstance(package.get('artifacts'), dict) else {}
    world_cup = bool(result.get('world_cup_context') or '世界杯' in str(match.get('league_name_cn') or match.get('league_name') or ''))
    critical = [
        'odds_1x2',
        'recent_form',
        'goal_tempo_profile',
        'injuries_suspensions',
        'expected_lineup',
        'data_quality',
    ]
    if world_cup:
        critical.extend(['tournament_context', 'fifa_ranking', 'elo_rating'])

    missing: List[str] = []
    low_conf: List[dict] = []
    status_map = {}
    for key in critical:
        req = req_by_key.get(key) or {}
        artifact = artifacts.get(key) if isinstance(artifacts.get(key), dict) else {}
        artifact_payload = artifact.get('payload') if isinstance(artifact.get('payload'), dict) else {}
        status = str(req.get('status') or ('collected' if artifact else 'missing'))
        confidence = _to_float(req.get('confidence'), None)
        if confidence is None and artifact:
            confidence = _to_float(artifact.get('confidence'), None)
        status_map[key] = {
            'status': status,
            'confidence': round(float(confidence), 3) if confidence is not None else None,
            'source': artifact.get('source') if artifact else None,
            'mode': artifact_payload.get('mode'),
        }
        if status not in {'collected', 'fallback_used'}:
            missing.append(key)
            continue
        threshold = 0.55 if key in {'injuries_suspensions', 'expected_lineup'} else 0.45
        if key == 'odds_1x2' and (
            artifact.get('source') == 'lottery_odds_rqspf_fallback'
            or artifact_payload.get('mode') == 'rqspf_fallback_no_spf'
        ):
            threshold = 0.70
            low_conf.append({
                'key': key,
                'confidence': round(float(confidence or 0.0), 3),
                'threshold': threshold,
                'reason': 'rqspf_fallback_no_spf',
            })
            continue
        if status == 'fallback_used' and key in {'injuries_suspensions', 'expected_lineup'}:
            low_conf.append({
                'key': key,
                'confidence': round(float(confidence or 0.0), 3),
                'threshold': threshold,
                'reason': f'{key}_fallback',
            })
            continue
        if confidence is not None and confidence < threshold:
            low_conf.append({'key': key, 'confidence': round(float(confidence), 3), 'threshold': threshold})

    if not artifacts and not requirements:
        package_status = 'missing'
    elif missing:
        package_status = 'partial'
    else:
        package_status = 'usable'
    return {
        'package_status': package_status,
        'source_job_id': intel_context.get('job_id'),
        'package_completeness': intel_context.get('completeness'),
        'strict_completeness': intel_context.get('strict_completeness'),
        'required_total': intel_context.get('required_total'),
        'required_collected': intel_context.get('required_collected'),
        'required_fallback': intel_context.get('required_fallback'),
        'average_confidence': intel_context.get('average_confidence'),
        'missing_required': intel_context.get('missing_required') or [],
        'critical_keys': critical,
        'missing_critical': missing,
        'low_confidence_critical': low_conf,
        'status_by_key': status_map,
        'goal_profile_adjustment': result.get('goal_profile_adjustment'),
    }


def _market_probabilities_from_odds(odds_baseline: dict) -> Dict[str, float]:
    probs = {
        key: _to_float(odds_baseline.get(key), 0.0) or 0.0
        for key in PROB_KEYS
    }
    if sum(probs.values()) <= 0:
        return {}
    return _normalize_probs(probs)


def _confidence_level_from_probability(confidence: float) -> str:
    if confidence >= 0.55:
        return 'high'
    if confidence >= 0.43:
        return 'medium'
    return 'low'


def _pressure_level_score(level: Any) -> Optional[int]:
    if level is None:
        return None
    text = str(level).lower()
    mapping = {
        'none': 0,
        'low': 0,
        'medium': 1,
        'mid': 1,
        'high': 2,
        'must_win': 3,
        'critical': 3,
    }
    return mapping.get(text)


def _market_evidence_text(item: dict) -> str:
    label = item.get('label') or item.get('key') or ''
    opening = _display_number(item.get('opening'))
    latest = _display_number(item.get('latest'))
    prob_delta = _to_float(item.get('probability_delta'), None)
    if prob_delta is None:
        return '%s %s->%s' % (label, opening, latest)
    return '%s %s->%s 隐含%s%%' % (
        label,
        opening,
        latest,
        _signed_number(prob_delta * 100.0, digits=1),
    )


def _rounded_delta(delta: Dict[str, float]) -> Dict[str, float]:
    return {k: round(delta.get(k, 0.0), 4) for k in PROB_KEYS}


def _to_float(value: Any, default: Optional[float] = 0.0) -> Optional[float]:
    try:
        if value is None or value == '':
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _env_float(name: str, default: float, low: Optional[float] = None, high: Optional[float] = None) -> float:
    value = _to_float(os.environ.get(name), default)
    if value is None:
        value = default
    if low is not None:
        value = max(low, value)
    if high is not None:
        value = min(high, value)
    return float(value)


def _env_int(name: str, default: int, low: Optional[int] = None, high: Optional[int] = None) -> int:
    value = _to_float(os.environ.get(name), float(default))
    try:
        number = int(value if value is not None else default)
    except (TypeError, ValueError):
        number = int(default)
    if low is not None:
        number = max(int(low), number)
    if high is not None:
        number = min(int(high), number)
    return number


def _safe_sql_identifier(value: Any, default: str = 'team_match_facts') -> str:
    text = str(value or '').strip() or default
    if not text:
        return default
    first = text[0]
    if not (first == '_' or 'A' <= first <= 'Z' or 'a' <= first <= 'z'):
        return default
    for char in text:
        if not (char == '_' or 'A' <= char <= 'Z' or 'a' <= char <= 'z' or '0' <= char <= '9'):
            return default
    return text


def _national_reference_fact_table() -> str:
    return _safe_sql_identifier(os.environ.get('FOOTBALL_NATIONAL_REFERENCE_FACT_TABLE'), 'team_match_facts')


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def _display_number(value: Any, digits: int = 1) -> str:
    number = _to_float(value, None)
    if number is None:
        return '--'
    if abs(number - round(number)) < 0.0001:
        return str(int(round(number)))
    return ('%%.%df' % digits) % number


def _signed_number(value: Any, digits: int = 0) -> str:
    number = _to_float(value, None)
    if number is None:
        return '--'
    fmt = ('%%+.%df' % digits)
    return fmt % number


def _loads_json(value, default):
    try:
        return json.loads(value) if isinstance(value, str) and value else default
    except Exception:
        return default


def _jsonable(value):
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, dict):
        return {str(k): _jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_jsonable(v) for v in value]
    if hasattr(value, 'value'):
        return value.value
    if hasattr(value, '__dict__'):
        return {k: _jsonable(v) for k, v in vars(value).items() if not k.startswith('_')}
    return str(value)



def _save_play_predictions(db_path: str, match: dict, result: dict):
    """Save multi-play predictions to lottery_predictions table"""
    try:
        match_key = match.get('lottery_match_id') or match.get('match_id')
        if not match_key:
            return

        play_predictions = result.get('play_predictions', {})
        if not play_predictions:
            return

        conn = sqlite3.connect(db_path, timeout=10)
        cursor = conn.cursor()

        # Delete existing predictions for this match
        cursor.execute("DELETE FROM lottery_predictions WHERE lottery_match_id = ?", (match_key,))

        fp = result.get('final_prediction', {})
        confidence = fp.get('confidence', 0)
        confidence_level = fp.get('confidence_level', 'medium')

        for play_type, pred in play_predictions.items():
            if play_type in {'derivation_axes'}:
                continue
            if not pred or not isinstance(pred, dict):
                continue

            # recommendation优先: ou/bqc用recommendation, spf/rqspf用direction
            rec = pred.get('recommendation', '') or pred.get('direction', '')
            probs = pred.get('probabilities', {})
            value_bets = pred.get('value_bets', [])
            play_confidence = pred.get('confidence')
            if play_confidence is None:
                play_confidence = confidence
            play_confidence_level = pred.get('confidence_level') or confidence_level

            cursor.execute("""
                INSERT OR REPLACE INTO lottery_predictions
                (lottery_match_id, play_type, predictions, recommendation,
                 confidence, confidence_level, has_value_bet, value_bets)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                match_key,
                play_type,
                json.dumps(pred, ensure_ascii=False, default=str),
                rec,
                play_confidence,
                play_confidence_level,
                1 if value_bets else 0,
                json.dumps(value_bets, ensure_ascii=False, default=str) if value_bets else None,
            ))

        # Also save match_id link if available
        match_id = match.get('match_id')
        if match_id:
            cursor.execute("""
                UPDATE lottery_predictions SET match_id = ?
                WHERE lottery_match_id = ? AND match_id IS NULL
            """, (match_id, match_key))

        conn.commit()
        conn.close()
    except Exception as e:
        logger.debug('Play predictions save failed: %s', e)


# ═══════════════════════════════════════
# 6项玩法推算
# ═══════════════════════════════════════

def _ensure_spf_recommendation_fields(plays: dict) -> None:
    if not isinstance(plays, dict):
        return
    spf = plays.get('spf')
    if not isinstance(spf, dict):
        return
    direction = spf.get('direction')
    if direction not in {'3', '1', '0'}:
        return
    cn = spf.get('direction_cn') or {
        '3': '\u4e3b\u80dc',
        '1': '\u5e73\u5c40',
        '0': '\u5ba2\u80dc',
    }.get(direction, '')
    spf['direction_cn'] = cn
    spf['recommendation'] = direction
    spf['recommendation_cn'] = cn


_TIER_ORDER = {'avoid': 0, 'low': 1, 'medium': 2, 'strong': 3}


def _worse_tier(left: str, right: str) -> str:
    left = left if left in _TIER_ORDER else 'low'
    right = right if right in _TIER_ORDER else 'low'
    return left if _TIER_ORDER[left] <= _TIER_ORDER[right] else right


def _tier_to_confidence_level(tier: str) -> str:
    if tier == 'strong':
        return 'high'
    if tier == 'medium':
        return 'medium'
    return 'low'


def _base_tier_from_probability(play_type: str, probability: Optional[float]) -> str:
    probability = _to_float(probability, None)
    if probability is None or probability <= 0:
        return 'avoid'
    if play_type in {'bf'}:
        return 'low' if probability >= 0.12 else 'avoid'
    if play_type in {'bqc'}:
        if probability >= 0.58:
            return 'medium'
        if probability >= 0.40:
            return 'low'
        return 'avoid'
    if probability >= 0.62:
        return 'strong'
    if probability >= 0.54:
        return 'medium'
    if probability >= 0.44:
        return 'low'
    return 'avoid'


def _analysis_scenario_type(match: dict, result: dict) -> str:
    context = (result or {}).get('competition_context') if isinstance((result or {}).get('competition_context'), dict) else {}
    context_type = str(context.get('type') or '').strip().lower()
    if context_type in {'friendly_intl', 'qualifier', 'nations_league'}:
        return context_type
    league_text = ' '.join(
        str((match or {}).get(key) or '')
        for key in ('league_name_cn', 'league_name_en', 'league_name', 'competition', 'competition_name')
    )
    league_text_l = league_text.lower()
    if any(token in league_text for token in ('\u53cb\u8c0a', '\u56fd\u9645\u8d5b')):
        return 'friendly_intl'
    if any(token in league_text for token in ('\u4e16\u9884', '\u6b27\u9884', '\u975e\u9884', '\u4e9a\u9884', '\u5357\u7f8e\u9884')):
        return 'qualifier'
    if '\u6b27\u56fd\u8054' in league_text:
        return 'nations_league'
    if (
        any(token in league_text for token in ('\u4e16\u754c\u676f', '\u6b27\u6d32\u676f', '\u4e9a\u6d32\u676f', '\u7f8e\u6d32\u676f', '\u975e\u6d32\u676f'))
        or 'world cup' in league_text_l
        or 'euro' in league_text_l
        or 'copa america' in league_text_l
    ):
        return 'international_cup'
    if any(token in league_text for token in ('\u6b27\u51a0', '\u6b27\u8054', '\u6b27\u534f', '\u89e3\u653e\u8005', '\u4e9a\u51a0')):
        return 'continental_cup'
    if '\u676f' in league_text:
        return 'domestic_cup'
    return 'league'


def _normalize_gate_prediction_key(play_type: str, prediction: Any) -> str:
    text = str(prediction or '').strip()
    if not text:
        return ''
    if play_type in {'spf', 'rqspf'}:
        mapping = {'home_win': '3', 'draw': '1', 'away_win': '0'}
        return mapping.get(text, text)
    if play_type == 'bqc':
        lower = text.lower()
        letter_map = {'h': '3', 'd': '1', 'a': '0'}
        if len(lower) == 2 and all(ch in letter_map for ch in lower):
            return ''.join(letter_map[ch] for ch in lower)
        return text
    if play_type == 'bf':
        return text.replace('-', ':').replace(' ', '')
    return text.replace(' ', '')


def _play_prediction_key(play_type: str, play: dict, result: dict, plays: dict) -> str:
    if play_type == 'spf':
        key = play.get('direction') or play.get('recommendation')
        if not key:
            final_prediction = (result or {}).get('final_prediction') or {}
            key = final_prediction.get('predicted_result')
        return _normalize_gate_prediction_key(play_type, key)
    if play_type == 'rqspf':
        return _normalize_gate_prediction_key(play_type, play.get('direction') or play.get('recommendation'))
    if play_type == 'ou':
        return _normalize_gate_prediction_key(play_type, play.get('recommendation'))
    if play_type == 'bqc':
        return _normalize_gate_prediction_key(play_type, play.get('recommendation') or play.get('direction'))
    if play_type == 'bf':
        top_scores = plays.get('top3_scores') if isinstance(plays, dict) else []
        scores = []
        if isinstance(top_scores, list):
            for item in top_scores[:3]:
                if isinstance(item, dict) and item.get('score'):
                    scores.append(_normalize_gate_prediction_key('bf', item.get('score')))
        return ' / '.join(score for score in scores if score)
    return ''


def _selected_play_probability(play_type: str, play: dict, result: dict, plays: dict) -> Optional[float]:
    if not isinstance(play, dict):
        return None
    if play_type == 'spf':
        fp = (result or {}).get('final_prediction') or {}
        probs = play.get('probabilities') if isinstance(play.get('probabilities'), dict) else {}
        direction = str(play.get('direction') or '')
        value = probs.get(direction)
        if value is None:
            value = fp.get('confidence')
        return _to_float(value, None)
    if play_type == 'rqspf':
        probs = play.get('probabilities') if isinstance(play.get('probabilities'), dict) else {}
        direction = str(play.get('direction') or '')
        return _to_float(play.get('confidence'), _to_float(probs.get(direction), None))
    if play_type == 'ou':
        side = _ou_side_from_recommendation(play.get('recommendation'))
        probs = play.get('best_line_probs') or play.get('probabilities') or {}
        if isinstance(probs, dict) and side in {'over', 'under'}:
            return _to_float(probs.get(side), _to_float(play.get('confidence'), None))
        return _to_float(play.get('confidence'), None)
    if play_type == 'bqc':
        rec = str(play.get('recommendation') or '')
        probs = play.get('probabilities') if isinstance(play.get('probabilities'), dict) else {}
        candidates = [rec]
        normalized = _normalize_gate_prediction_key('bqc', rec)
        reverse = {'33': 'hh', '31': 'hd', '30': 'ha', '13': 'dh', '11': 'dd', '10': 'da', '03': 'ah', '01': 'ad', '00': 'aa'}
        if normalized in reverse:
            candidates.append(reverse[normalized])
        for key in candidates:
            value = probs.get(key)
            if value is not None:
                return _to_float(value, None)
        return _to_float(play.get('confidence'), None)
    if play_type == 'bf':
        top_scores = plays.get('top3_scores') if isinstance(plays, dict) else []
        if not isinstance(top_scores, list):
            return None
        total = 0.0
        for item in top_scores[:3]:
            if not isinstance(item, dict):
                continue
            prob = _to_float(item.get('probability'), 0.0) or 0.0
            total += prob / 100.0 if prob > 1 else prob
        return total
    return _to_float(play.get('confidence'), None)


def _load_historical_play_quality(db_path: str, play_type: str, predicted_result: str, scenario_type: str) -> dict:
    if not db_path or not play_type or not predicted_result:
        return {}
    try:
        conn = sqlite3.connect(db_path, timeout=10)
        conn.row_factory = sqlite3.Row
        scopes = []
        if scenario_type:
            scopes.append(('scenario', scenario_type))
        scopes.append(('global', None))
        for scope, scenario in scopes:
            params = [play_type, predicted_result]
            scenario_filter = ''
            if scenario:
                scenario_filter = 'AND scenario_type = ?'
                params.append(scenario)
            row = conn.execute(
                f"""
                SELECT COUNT(*) AS sample_size,
                       COALESCE(SUM(CASE WHEN is_correct = 1 THEN 1 ELSE 0 END), 0) AS correct
                FROM lottery_validation
                WHERE play_type = ?
                  AND predicted_result = ?
                  AND actual_result IS NOT NULL
                  {scenario_filter}
                """,
                params,
            ).fetchone()
            sample_size = int(row['sample_size'] or 0) if row else 0
            correct = int(row['correct'] or 0) if row else 0
            min_sample = 5 if scope == 'scenario' else 8
            if sample_size >= min_sample:
                conn.close()
                accuracy = correct / sample_size if sample_size else 0.0
                return {
                    'scope': scope,
                    'scenario_type': scenario,
                    'sample_size': sample_size,
                    'correct': correct,
                    'accuracy': round(accuracy, 4),
                }
        conn.close()
    except Exception as exc:
        logger.debug('historical play quality load failed: %s', exc)
    return {}


def _tier_after_historical_quality(play_type: str, base_tier: str, probability: Optional[float], quality: dict) -> tuple:
    tier = base_tier if base_tier in _TIER_ORDER else 'low'
    reason = 'probability_gate'
    if play_type in {'bf'}:
        return _worse_tier(tier, 'low'), 'score_exact_high_variance'
    if play_type in {'bqc'}:
        tier = _worse_tier(tier, 'medium')

    probability = _to_float(probability, 0.0) or 0.0
    sample_size = int((quality or {}).get('sample_size') or 0)
    accuracy = _to_float((quality or {}).get('accuracy'), None)
    if sample_size and accuracy is not None:
        reason = 'historical_pattern_gate'
        if accuracy < 0.35:
            return 'avoid', reason
        if accuracy < 0.50:
            return _worse_tier(tier, 'low'), reason
        if accuracy < 0.62 and tier == 'strong':
            return 'medium', reason
        if accuracy < 0.72 and tier == 'strong':
            return 'medium', reason
        if accuracy >= 0.78 and probability >= 0.64 and play_type in {'spf', 'ou', 'rqspf'}:
            return 'strong', reason
        if tier == 'strong' and accuracy < 0.78:
            return 'medium', reason
    elif tier == 'strong' and probability < 0.68:
        return 'medium', 'no_historical_support_for_strong'
    return tier, reason


def _apply_selective_recommendation_guard(db_path: str, match: dict, result: dict) -> None:
    if not isinstance(result, dict):
        return
    plays = result.get('play_predictions') if isinstance(result.get('play_predictions'), dict) else {}
    if not plays:
        return
    scenario_type = _analysis_scenario_type(match or {}, result)
    summary = {
        'scenario_type': scenario_type,
        'applied': True,
        'plays': {},
    }

    for play_type in ('spf', 'ou', 'rqspf', 'bqc'):
        play = plays.get(play_type)
        if not isinstance(play, dict):
            continue
        prediction_key = _play_prediction_key(play_type, play, result, plays)
        probability = _selected_play_probability(play_type, play, result, plays)
        base_tier = _base_tier_from_probability(play_type, probability)
        quality = _load_historical_play_quality(db_path, play_type, prediction_key, scenario_type)
        tier, reason = _tier_after_historical_quality(play_type, base_tier, probability, quality)

        risk_profile = play.get('risk_profile') if isinstance(play.get('risk_profile'), dict) else {}
        if risk_profile.get('recommended_usage') == 'watch_only':
            tier = _worse_tier(tier, 'low')
            reason = 'risk_profile_watch_only'
        goal_axis = play.get('goal_axis') if isinstance(play.get('goal_axis'), dict) else {}
        if play_type == 'ou' and goal_axis:
            if goal_axis.get('recommended_usage') == 'watch_only' or goal_axis.get('risk_level') in {'very_high', 'high'}:
                tier = _worse_tier(tier, 'low')
                reason = 'goal_axis_risk_gate'
            selected = _to_float(goal_axis.get('selected_probability'), None)
            if selected is not None and selected < 0.54:
                tier = _worse_tier(tier, 'low')
                reason = 'goal_axis_thin_edge'
        boundary = play.get('boundary_profile') if isinstance(play.get('boundary_profile'), dict) else {}
        if play_type == 'rqspf' and boundary.get('is_boundary'):
            tier = _worse_tier(tier, 'low')
            reason = 'handicap_boundary_gate'

        play['confidence'] = round(probability, 4) if probability is not None else play.get('confidence')
        play['confidence_tier'] = tier
        play['confidence_level'] = _tier_to_confidence_level(tier)
        play['historical_quality'] = quality
        play['recommendation_gate'] = {
            'tier': tier,
            'tier_cn': confidence_level_cn(_tier_to_confidence_level(tier)),
            'base_tier': base_tier,
            'base_tier_cn': confidence_level_cn(_tier_to_confidence_level(base_tier)),
            'reason': reason,
            'reason_cn': gate_reason_cn(reason),
            'prediction_key': prediction_key,
            'selected_probability': round(probability, 4) if probability is not None else None,
            'historical_accuracy': quality.get('accuracy'),
            'historical_sample_size': quality.get('sample_size'),
            'historical_scope': quality.get('scope'),
            'scenario_type': scenario_type,
            'scenario_type_cn': scenario_type_cn(scenario_type),
        }
        summary['plays'][play_type] = play['recommendation_gate']

    bf_key = _play_prediction_key('bf', {}, result, plays)
    bf_prob = _selected_play_probability('bf', {}, result, plays)
    bf_quality = _load_historical_play_quality(db_path, 'bf', bf_key, scenario_type)
    bf_tier, bf_reason = _tier_after_historical_quality('bf', _base_tier_from_probability('bf', bf_prob), bf_prob, bf_quality)
    summary['plays']['bf'] = {
        'tier': bf_tier,
        'tier_cn': confidence_level_cn(_tier_to_confidence_level(bf_tier)),
        'base_tier': _base_tier_from_probability('bf', bf_prob),
        'base_tier_cn': confidence_level_cn(_tier_to_confidence_level(_base_tier_from_probability('bf', bf_prob))),
        'reason': bf_reason,
        'reason_cn': gate_reason_cn(bf_reason),
        'prediction_key': bf_key,
        'selected_probability': round(bf_prob, 4) if bf_prob is not None else None,
        'historical_accuracy': bf_quality.get('accuracy'),
        'historical_sample_size': bf_quality.get('sample_size'),
        'historical_scope': bf_quality.get('scope'),
        'scenario_type': scenario_type,
        'scenario_type_cn': scenario_type_cn(scenario_type),
    }
    top_scores = plays.get('top3_scores')
    if isinstance(top_scores, list):
        for item in top_scores:
            if isinstance(item, dict):
                item['confidence_tier'] = bf_tier
                item['recommendation_gate'] = summary['plays']['bf']

    spf_gate = summary['plays'].get('spf') or {}
    fp = result.get('final_prediction') if isinstance(result.get('final_prediction'), dict) else {}
    if fp and spf_gate:
        fp['confidence_tier'] = spf_gate.get('tier')
        fp['confidence_level'] = _tier_to_confidence_level(spf_gate.get('tier'))
        fp['recommendation_gate'] = spf_gate
    result['recommendation_gate'] = summary


def _compute_all_plays(result: dict, match: dict, ou_result: dict = None, db_path: str = None) -> dict:
    """从Poisson比分矩阵推算全部6项玩法

    输出:
    - spf: 胜平负方向 + 概率
    - rqspf: 让球胜平负方向 + 概率
    - top3_scores: TOP3比分 + 概率
    - ou: 大小球(2/2.5/3) + 概率 (来自ou_calculator)
    - bqc: 半全场 + 概率
    """
    fp = result.get('final_prediction', {})
    probs = fp.get('probabilities', {})
    bp = result.get('base_prediction', {})
    poisson = bp.get('poisson', {})

    # 获取Poisson比分矩阵，并校准到最终胜平负概率/预期进球。
    score_matrix = poisson.get('score_matrix')
    expected = fp.get('expected_score', poisson.get('expected_score', {}))
    score_matrix, projection_meta = _prepare_joint_score_matrix(result, score_matrix)
    if projection_meta:
        result['joint_projection'] = projection_meta

    # 如果没有score_matrix, 从expected_score重建
    if not score_matrix:
        # 用最终概率直接推算
        return _compute_plays_from_probs(probs, expected, match, db_path)

    home_xg = expected.get('home', 0)
    away_xg = expected.get('away', 0)

    plays = {}

    # 1. 胜平负(SPF) — 直接用final概率
    spf_rec = max(probs, key=probs.get) if probs else 'unknown'
    spf_map = {'home_win': '3', 'draw': '1', 'away_win': '0'}
    plays['spf'] = {
        'direction': spf_map.get(spf_rec, '?'),
        'direction_cn': {'3': '主胜', '1': '平局', '0': '客胜'}.get(spf_map.get(spf_rec, '?'), ''),
        'probabilities': {
            '3': round(probs.get('home_win', 0), 3),
            '1': round(probs.get('draw', 0), 3),
            '0': round(probs.get('away_win', 0), 3),
        },
    }

    # 2. 大小球 — 使用ou_calculator的结果。RQSPF needs the O/U axis too
    # because the card/detail UI presents these plays as one coherent view.
    spf_axis_context = _build_spf_axis_context(result, plays['spf'])
    plays['spf']['axis_context'] = spf_axis_context
    market_anchor = (result.get('model_vs_odds') or {}).get('market_anchor') if isinstance(result.get('model_vs_odds'), dict) else None
    if isinstance(market_anchor, dict) and market_anchor.get('applied'):
        plays['spf']['market_anchor'] = market_anchor
    visible_spf_axis = plays['spf'].get('direction')
    derived_full_time_axis = visible_spf_axis if visible_spf_axis in {'3', '1', '0'} else None

    if ou_result:
        plays['ou'] = ou_result
    else:
        plays['ou'] = _compute_over_under(score_matrix, None)

    # 3. TOP3比分 — 从同一套主轴/大小球约束后的score_matrix取候选
    plays['top3_scores'] = _get_top3_scores(
        score_matrix,
        spf_direction=plays['spf'].get('direction'),
        ou_prediction=plays.get('ou'),
    )

    # 4. 半全场(BQC)
    # BQC already has its own half-time phase profile. If the full-time goal
    # profile rebuilt the shared matrix, keep BQC on the raw SPF-aligned matrix
    # so the full-game tempo correction does not drown out half-time evidence.
    bqc_score_matrix = poisson.get('score_matrix') or score_matrix
    if (result.get('goal_profile_adjustment') or {}).get('applied') and poisson.get('score_matrix'):
        bqc_projection_meta = {
            'method': 'legacy_raw_poisson_matrix',
            'applied': False,
        }
        result['bqc_projection'] = {
            'method': 'raw_matrix_with_phase_profile',
            'spf_alignment': bqc_projection_meta,
            'reason': 'bqc_uses_legacy_raw_poisson_matrix_without_spf_alignment',
        }
    plays['bqc'] = _compute_bqc(
        bqc_score_matrix,
        match,
        db_path,
        full_time_axis=derived_full_time_axis,
        axis_context=spf_axis_context,
    )

    # 5. 让球胜平负(RQSPF) — keep the full-matrix result, but display the
    # projection conditioned on the full-time/BQC/O/U axes when the visible
    # analysis axis would otherwise conflict with the handicap result.
    handicap = _get_handicap(match, db_path)
    rqspf_odds_baseline = _get_rqspf_odds_baseline(db_path, match.get('lottery_match_id')) if db_path else None
    plays['rqspf'] = _compute_rqspf(
        score_matrix,
        handicap,
        full_time_axis=derived_full_time_axis,
        full_time_probabilities=plays['spf'].get('probabilities'),
        ou_prediction=plays.get('ou'),
        bqc_prediction=plays.get('bqc'),
        axis_context=spf_axis_context,
        rqspf_odds_baseline=rqspf_odds_baseline,
    )

    _apply_play_consistency(plays)
    if _refresh_bqc_after_spf_axis_shift(plays, bqc_score_matrix, match, db_path):
        _apply_play_consistency(plays)
    if _apply_bqc_stability_reuse(db_path, match, plays):
        _apply_rqspf_for_stable_bqc_axis(plays)
        if _env_float('FOOTBALL_BQC_STABLE_REUSE_POST_CONSISTENCY', 1.0, 0.0, 1.0) >= 1.0:
            _apply_play_consistency(plays)
    plays['top3_scores'] = _enhance_score_candidates(score_matrix, plays)
    _apply_national_ou_conflict_gate_to_play(plays, result, db_path, match, score_matrix)
    _apply_play_risk_profiles(plays, result, score_matrix)
    _apply_ou_display_probability_override(plays)
    _ensure_spf_recommendation_fields(plays)
    return plays


def _sync_final_prediction_scores(result: dict) -> None:
    """Keep final_prediction score display aligned with play_predictions."""
    if not isinstance(result, dict):
        return
    plays = result.get('play_predictions') if isinstance(result.get('play_predictions'), dict) else {}
    top_scores = plays.get('top3_scores') if isinstance(plays.get('top3_scores'), list) else []
    if not top_scores:
        return
    final_prediction = result.setdefault('final_prediction', {})
    if not isinstance(final_prediction, dict):
        return

    synced = []
    for item in top_scores[:5]:
        if not isinstance(item, dict) or not item.get('score'):
            continue
        probability = _to_float(item.get('probability'), None)
        if probability is not None and probability <= 1.0:
            probability *= 100.0
        synced.append({
            'score': item.get('score'),
            'home_goals': item.get('home_goals'),
            'away_goals': item.get('away_goals'),
            'probability': round(probability, 2) if probability is not None else item.get('probability'),
            'source': 'play_predictions_top3_scores',
        })
    if synced:
        final_prediction['most_likely_scores'] = synced


def _score_item_total_side(item: dict, line: Any) -> Optional[str]:
    if not isinstance(item, dict):
        return None
    try:
        line_value = float(line)
    except (TypeError, ValueError):
        return None
    try:
        home_goals = int(item.get('home_goals'))
        away_goals = int(item.get('away_goals'))
    except (TypeError, ValueError):
        score = str(item.get('score') or '')
        if '-' not in score:
            return None
        try:
            home_text, away_text = score.split('-', 1)
            home_goals = int(home_text)
            away_goals = int(away_text)
        except (TypeError, ValueError):
            return None
    total_goals = home_goals + away_goals
    if total_goals > line_value:
        return 'over'
    if total_goals < line_value:
        return 'under'
    return 'push'


def _build_national_ou_score_axis_note(side: str, line: Any, scores: list) -> str:
    try:
        line_value = float(line)
    except (TypeError, ValueError):
        line_value = None
    if side not in {'over', 'under'} or line_value is None:
        return ''
    top_sides = []
    for item in scores[:3]:
        score_side = _score_item_total_side(item, line_value)
        if score_side:
            top_sides.append(score_side)
    opposite = 'under' if side == 'over' else 'over'
    side_cn = '大球' if side == 'over' else '小球'
    if top_sides.count(opposite) >= 2:
        return (
            f'{side_cn}方向由国家队历史进失球样本校准；'
            '比分是单点落点，当前 Top3 仍偏向反侧，说明总进球风险更分散。'
        )
    return f'{side_cn}方向由国家队历史进失球样本校准；比分候选已按最终大小球方向重新排序。'


def _preview_national_ou_gate_scores(score_matrix, plays: dict, line: Any, target_side: str) -> dict:
    if not score_matrix or not isinstance(plays, dict) or target_side not in {'over', 'under'}:
        return {}
    try:
        line_value = float(line)
    except (TypeError, ValueError):
        return {}

    preview_plays = {
        **plays,
        'ou': dict(plays.get('ou') or {}),
    }
    preview_plays['ou']['recommendation'] = _format_ou_recommendation(target_side, line_value)
    preview_scores = _enhance_score_candidates(score_matrix, preview_plays)
    opposite = 'under' if target_side == 'over' else 'over'
    top_sides = [
        _score_item_total_side(item, line_value)
        for item in preview_scores[:3]
    ]
    top_sides = [side for side in top_sides if side]
    coherent_count = sum(1 for side in top_sides if side == target_side)
    opposite_count = sum(1 for side in top_sides if side == opposite)
    return {
        'scores': preview_scores,
        'top_score_sides': top_sides,
        'coherent_count': coherent_count,
        'opposite_count': opposite_count,
        'blocked': opposite_count >= 2,
    }


def _apply_national_ou_conflict_gate_to_play(plays: dict, result: dict, db_path: str, match: dict, score_matrix=None) -> None:
    """Apply national-team O/U calibration after cross-play derivation.

    The gate is intentionally O/U-only. It can correct the visible O/U side,
    but it must not rewrite RQSPF, BQC or score candidates until a separate
    protected backtest proves those downstream changes are positive too.
    """
    if _env_float('FOOTBALL_NATIONAL_OU_CONFLICT_GATE_ENABLED', 0.0, 0.0, 1.0) < 1.0:
        return
    if str(os.environ.get('FOOTBALL_NATIONAL_OU_CONFLICT_GATE_PHASE') or 'post').lower() != 'post':
        return
    if not isinstance(plays, dict):
        return
    ou = plays.get('ou') if isinstance(plays.get('ou'), dict) else {}
    if not ou:
        return

    line = ou.get('best_line') or ou.get('line') or 2.5
    current_side = _ou_side_from_recommendation(ou.get('recommendation'))
    if current_side not in {'over', 'under'}:
        current_side = _ou_side_from_recommendation(ou.get('model_recommendation'))
    if current_side not in {'over', 'under'}:
        probs = ou.get('best_line_probs') if isinstance(ou.get('best_line_probs'), dict) else {}
        over_prob = _to_float(probs.get('over'), None)
        under_prob = _to_float(probs.get('under'), None)
        if over_prob is not None and under_prob is not None:
            current_side = 'over' if over_prob >= under_prob else 'under'
    if current_side not in {'over', 'under'}:
        return

    national_signal = _national_ou_reference_signal(db_path, match or {}, line)
    if national_signal:
        ou['national_reference_signal'] = national_signal
    national_side = national_signal.get('side') if isinstance(national_signal, dict) else None
    if not (
        isinstance(national_signal, dict)
        and national_signal.get('eligible')
        and national_side in {'over', 'under'}
        and national_side != current_side
    ):
        return

    preview = _preview_national_ou_gate_scores(score_matrix, plays, line, national_side)
    if isinstance(preview, dict) and preview.get('blocked'):
        ou['national_gate_guard'] = {
            'blocked': True,
            'reason': 'score_axis_conflict_after_gate_preview',
            'target_side': national_side,
            'top_score_sides': preview.get('top_score_sides') or [],
            'preview_scores': [
                item.get('score')
                for item in (preview.get('scores') or [])[:3]
                if isinstance(item, dict) and item.get('score')
            ],
        }
        return

    probs = ou.get('best_line_probs') if isinstance(ou.get('best_line_probs'), dict) else {}
    over = _to_float(probs.get('over'), None)
    under = _to_float(probs.get('under'), None)
    if over is None or under is None:
        over = 0.5
        under = 0.5
    sample_bonus = min(
        0.035,
        max(
            0.0,
            (min(
                _to_float(national_signal.get('home_sample'), 0.0) or 0.0,
                _to_float(national_signal.get('away_sample'), 0.0) or 0.0,
            ) - _to_float(national_signal.get('min_sample_required'), 16.0)) * 0.003,
        ),
    )
    gap_bonus = min(0.055, abs(_to_float(national_signal.get('total_gap'), 0.0) or 0.0) * 0.055)
    national_selected = round(max(0.535, min(0.64, 0.535 + sample_bonus + gap_bonus)), 4)
    display_probs = {
        'over': national_selected if national_side == 'over' else round(1.0 - national_selected, 4),
        'under': national_selected if national_side == 'under' else round(1.0 - national_selected, 4),
        'source': 'national_reference_conflict_gate',
    }
    before = ou.get('recommendation') or _format_ou_recommendation(current_side, line)
    after = _format_ou_recommendation(national_side, line)
    previous_basis = ou.get('recommendation_basis')
    ou.setdefault('model_recommendation', _format_ou_recommendation(current_side, line))
    ou['pre_national_recommendation'] = before
    ou['recommendation'] = after
    ou['recommendation_basis'] = 'national_reference_conflict_gate'
    ou['confidence'] = round(national_selected, 3)
    ou['confidence_level'] = 'medium' if national_selected < 0.58 else 'high'
    ou['display_probability_override'] = {
        'raw_best_line_probs': {
            'over': round(over, 4),
            'under': round(under, 4),
            'source': 'pre_national_reference_gate',
        },
        'best_line_probs': display_probs,
    }
    ou['raw_best_line_probs'] = {
        'over': round(over, 4),
        'under': round(under, 4),
        'source': 'pre_national_reference_gate',
    }
    ou['best_line_probs'] = display_probs
    ou['recommendation_adjustment'] = {
        'from': before,
        'to': after,
        'reason': 'national_reference_conflict_gate',
        'previous_basis': previous_basis,
        'model_side': current_side,
        'national_reference_side': national_side,
        'national_reference_total_gap': national_signal.get('total_gap'),
        'national_reference_source_table': national_signal.get('source_table'),
    }
    if isinstance(preview, dict):
        preview_scores = preview.get('scores') if isinstance(preview.get('scores'), list) else []
        if preview_scores:
            plays['top3_scores'] = preview_scores
        ou['score_axis_note'] = _build_national_ou_score_axis_note(
            national_side,
            line,
            preview_scores,
        )
        ou['national_gate_guard'] = {
            'blocked': False,
            'reason': 'score_axis_refreshed_after_gate',
            'target_side': national_side,
            'top_score_sides': preview.get('top_score_sides') or [],
            'preview_scores': [
                item.get('score')
                for item in preview_scores[:3]
                if isinstance(item, dict) and item.get('score')
            ],
        }


def _apply_ou_display_probability_override(plays: dict) -> None:
    """Apply display-only O/U probability harmonization after all model axes.

    Some recommendations are intentionally chosen by a thin market tie-breaker
    or a matrix self-check. Internal model axes should still be calculated from
    the raw distribution; only the saved/displayed probability block is aligned
    with the final recommendation to avoid UI/audit contradictions.
    """
    if not isinstance(plays, dict):
        return
    ou = plays.get('ou') if isinstance(plays.get('ou'), dict) else {}
    override = ou.get('display_probability_override') if isinstance(ou.get('display_probability_override'), dict) else {}
    if not override:
        return
    raw_probs = override.get('raw_best_line_probs')
    display_probs = override.get('best_line_probs')
    if isinstance(raw_probs, dict):
        ou['raw_best_line_probs'] = raw_probs
    if isinstance(display_probs, dict):
        ou['best_line_probs'] = display_probs


def _refresh_bqc_after_spf_axis_shift(plays: dict, score_matrix, match: dict, db_path: str) -> bool:
    """Recompute BQC when SPF was arbitrated onto a new trusted full-time axis."""
    if not isinstance(plays, dict) or not score_matrix:
        return False
    spf = plays.get('spf') if isinstance(plays.get('spf'), dict) else {}
    bqc = plays.get('bqc') if isinstance(plays.get('bqc'), dict) else {}
    if not spf or not bqc:
        return False

    arbitration = spf.get('arbitration_adjustment') if isinstance(spf.get('arbitration_adjustment'), dict) else {}
    axis_context = spf.get('axis_context') if isinstance(spf.get('axis_context'), dict) else {}
    target_direction = str(spf.get('direction') or '')
    if target_direction not in {'3', '1', '0'}:
        return False
    if not arbitration and axis_context.get('reason') != 'rqspf_arbitrated_spf_axis':
        return False

    refreshed = _compute_bqc(
        score_matrix,
        match,
        db_path,
        full_time_axis=target_direction,
        axis_context=axis_context,
    )
    if not isinstance(refreshed, dict):
        return False

    previous_rec = str(bqc.get('recommendation') or '')
    refreshed_rec = str(refreshed.get('recommendation') or '')
    refreshed['axis_recompute'] = {
        'applied': True,
        'reason': 'spf_arbitration_recompute',
        'spf_direction': target_direction,
        'spf_direction_cn': {'3': '主胜', '1': '平局', '0': '客胜'}.get(target_direction, ''),
        'from': previous_rec,
        'from_cn': bqc.get('recommendation_cn'),
        'to': refreshed_rec,
        'to_cn': refreshed.get('recommendation_cn'),
        'arbitration': {
            key: arbitration.get(key)
            for key in (
                'from',
                'from_cn',
                'to',
                'to_cn',
                'reason',
                'rqspf_direction',
                'rqspf_probability',
                'rqspf_gap',
            )
            if arbitration.get(key) not in (None, '')
        },
    }
    plays['bqc'] = refreshed
    return True


def _bqc_stability_reuse_enabled() -> bool:
    if _env_float('FOOTBALL_BQC_STABLE_REUSE_ENABLED', 1.0, 0.0, 1.0) < 1.0:
        return False
    # When explicitly testing a new BQC path, evaluate it honestly instead of
    # hiding it behind the last accepted report.
    if _env_float('FOOTBALL_BQC_JOINT_PATH_ENABLED', 0.0, 0.0, 1.0) >= 1.0:
        return False
    return True


def _clone_jsonable(value: Any) -> Any:
    try:
        return json.loads(json.dumps(value, ensure_ascii=False, default=str))
    except Exception:
        return value.copy() if isinstance(value, dict) else value


def _load_previous_bqc_prediction(db_path: str, lottery_match_id: str) -> Optional[dict]:
    if not db_path or not lottery_match_id:
        return None
    try:
        conn = sqlite3.connect(db_path, timeout=10)
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            """
            SELECT report_id, report_data, created_at
            FROM lottery_analysis_reports
            WHERE lottery_match_id = ?
              AND report_type = 'prediction'
              AND COALESCE(is_stale, 0) = 0
            ORDER BY datetime(created_at) DESC, report_id DESC
            LIMIT 1
            """,
            (str(lottery_match_id),),
        ).fetchone()
        conn.close()
        if not row:
            return None
        report = json.loads(row['report_data']) if isinstance(row['report_data'], str) else row['report_data']
        plays = report.get('play_predictions') if isinstance(report, dict) else {}
        bqc = plays.get('bqc') if isinstance(plays, dict) else None
        if not isinstance(bqc, dict):
            return None
        return {
            'report_id': row['report_id'],
            'created_at': row['created_at'],
            'bqc': bqc,
        }
    except Exception as exc:
        logger.debug('load previous bqc prediction failed: %s', exc)
        return None


def _apply_bqc_stability_reuse(db_path: str, match: dict, plays: dict) -> bool:
    """Keep BQC on the last accepted layer unless a BQC experiment is enabled.

    SPF/RQSPF/O/U/score improvements should be able to pass their own gate
    without accidentally replacing BQC with an unaccepted experimental path.
    The reused value is still passed through consistency arbitration afterward.
    """
    if not _bqc_stability_reuse_enabled() or not isinstance(plays, dict):
        return False
    current = plays.get('bqc') if isinstance(plays.get('bqc'), dict) else {}
    current_rec = str(current.get('recommendation') or '')
    previous = _load_previous_bqc_prediction(db_path, str((match or {}).get('lottery_match_id') or ''))
    previous_bqc = previous.get('bqc') if isinstance(previous, dict) else None
    if not isinstance(previous_bqc, dict):
        return False
    previous_rec = str(previous_bqc.get('recommendation') or '')
    valid_codes = {'hh', 'hd', 'ha', 'dh', 'dd', 'da', 'ah', 'ad', 'aa'}
    if previous_rec not in valid_codes:
        return False
    if previous_rec == current_rec:
        return False
    current_structural = any(
        isinstance(current.get(key), dict) and current.get(key)
        for key in ('phase_axis_adjustment', 'soft_full_axis_adjustment', 'axis_recompute')
    )
    previous_structural = any(
        isinstance(previous_bqc.get(key), dict) and previous_bqc.get(key)
        for key in ('phase_axis_adjustment', 'soft_full_axis_adjustment', 'axis_recompute')
    )
    if current_structural and not previous_structural:
        current['stability_reuse_skipped'] = {
            'applied': False,
            'reason': 'current_bqc_has_structural_axis_adjustment',
            'current_candidate': current_rec,
            'current_candidate_cn': current.get('recommendation_cn'),
            'previous_candidate': previous_rec,
            'previous_candidate_cn': previous_bqc.get('recommendation_cn'),
            'source_report_id': previous.get('report_id'),
            'source_created_at': previous.get('created_at'),
        }
        return False

    preserved = _clone_jsonable(previous_bqc)
    if not isinstance(preserved, dict):
        return False
    preserved['stability_reuse'] = {
        'applied': True,
        'reason': 'reuse_last_accepted_bqc_until_bqc_gate_passes',
        'source_report_id': previous.get('report_id'),
        'source_created_at': previous.get('created_at'),
        'from_candidate': current_rec,
        'from_candidate_cn': current.get('recommendation_cn'),
        'to': previous_rec,
        'to_cn': previous_bqc.get('recommendation_cn'),
        'current_candidate': _clone_jsonable({
            key: current.get(key)
            for key in ('recommendation', 'recommendation_cn', 'probabilities', 'half_time', 'method', 'axis_constraint')
            if key in current
        }),
    }
    plays['bqc'] = preserved
    return True


def _apply_rqspf_for_stable_bqc_axis(plays: dict) -> bool:
    if not isinstance(plays, dict):
        return False
    bqc = plays.get('bqc') if isinstance(plays.get('bqc'), dict) else {}
    marker = bqc.get('stability_reuse') if isinstance(bqc.get('stability_reuse'), dict) else {}
    if not marker.get('applied'):
        return False
    rqspf = plays.get('rqspf') if isinstance(plays.get('rqspf'), dict) else {}
    if not rqspf:
        return False
    bqc_axis = _bqc_full_time_axis(bqc)
    direction = str(rqspf.get('direction') or '')
    if bqc_axis not in {'3', '1', '0'} or direction not in {'3', '1', '0'}:
        return False
    spf = plays.get('spf') if isinstance(plays.get('spf'), dict) else {}
    spf_axis = str(spf.get('direction') or '')
    spf_axis_context = spf.get('axis_context') if isinstance(spf.get('axis_context'), dict) else None
    if (
        spf_axis in {'3', '1', '0'}
        and _axis_context_is_trusted(spf_axis_context)
        and bqc_axis != spf_axis
    ):
        marker['skipped_rqspf_axis_adjustment'] = {
            'reason': 'stable_bqc_conflicts_with_trusted_spf_axis',
            'bqc_full_time_axis': bqc_axis,
            'spf_axis': spf_axis,
        }
        return False
    try:
        handicap = float(rqspf.get('handicap') or 0.0)
    except (TypeError, ValueError):
        handicap = 0.0
    if _rqspf_direction_possible_under_spf(handicap, direction, bqc_axis):
        return False

    probabilities = rqspf.get('probabilities') if isinstance(rqspf.get('probabilities'), dict) else {}
    candidates = [
        code for code in ('3', '1', '0')
        if _rqspf_direction_possible_under_spf(handicap, code, bqc_axis)
    ]
    if not candidates:
        return False
    selected = max(candidates, key=lambda code: float(probabilities.get(code) or 0.0))
    if selected == direction:
        return False

    rqspf_cn = {'3': '让胜', '1': '让平', '0': '让负'}
    spf_cn = {'3': '主胜', '1': '平局', '0': '客胜'}
    rqspf['direction'] = selected
    rqspf['recommendation'] = selected
    rqspf['recommendation_cn'] = rqspf_cn.get(selected, '')
    rqspf['direction_cn'] = {'3': 'home_win', '1': 'draw', '0': 'away_win'}.get(selected, '')
    rqspf['margin_requirement'] = _rqspf_margin_requirement(handicap, selected)
    rqspf['bqc_stability_axis_adjustment'] = {
        'from': direction,
        'from_cn': rqspf_cn.get(direction, ''),
        'to': selected,
        'to_cn': rqspf_cn.get(selected, ''),
        'reason': 'stable_bqc_full_time_axis',
        'bqc_full_time_axis': bqc_axis,
        'bqc_full_time_axis_cn': spf_cn.get(bqc_axis, ''),
        'selected_probability': round(float(probabilities.get(selected) or 0.0), 4),
        'original_probability': round(float(probabilities.get(direction) or 0.0), 4),
        'compatible_directions': candidates,
    }
    return True


def _compute_plays_from_probs(probs, expected, match, db_path: str = None) -> dict:
    """当没有score_matrix时, 从概率直接推算"""
    spf_map = {'home_win': '3', 'draw': '1', 'away_win': '0'}
    spf_rec = max(probs, key=probs.get) if probs else 'unknown'

    # 从expected_score推算最可能比分
    home_xg = expected.get('home', 0) if expected else 0
    away_xg = expected.get('away', 0) if expected else 0
    top3 = []
    if home_xg > 0 and away_xg > 0:
        # 从xG推算最可能的比分(简化)
        h_score = round(home_xg)
        a_score = round(away_xg)
        top3 = [
            {'score': '{}-{}'.format(h_score, a_score), 'probability': 0},
            {'score': '{}-{}'.format(h_score, a_score + 1 if probs.get('away_win', 0) > probs.get('home_win', 0) else h_score + 1, a_score), 'probability': 0},
            {'score': '1-1', 'probability': 0},
        ]

    # 让球胜平负 — 用概率直接推算
    handicap = _get_handicap(match, db_path)
    rqspf = {}
    if handicap != 0:
        # 简化: 让球后概率调整(不能用score_matrix精确计算)
        rqspf = {'direction': '?', 'handicap': handicap, 'probabilities': {}}

    # 大小球 — 从expected推算
    total_xg = home_xg + away_xg
    ou = {}
    if total_xg > 0:
        ou = {
            'recommendation': '大2.5' if total_xg > 2.5 else '小2.5',
            'most_likely_total': round(total_xg),
        }

    plays = {
        'spf': {
            'direction': spf_map.get(spf_rec, '?'),
            'direction_cn': {'3': '主胜', '1': '平局', '0': '客胜'}.get(spf_map.get(spf_rec, '?'), ''),
            'probabilities': {
                '3': round(probs.get('home_win', 0), 3),
                '1': round(probs.get('draw', 0), 3),
                '0': round(probs.get('away_win', 0), 3),
            },
        },
        'top3_scores': top3,
        'rqspf': rqspf or {'direction': '?', 'handicap': 0, 'probabilities': {}},
        'ou': ou,
        'bqc': {},
    }
    _apply_play_consistency(plays)
    _apply_play_risk_profiles(plays, {'final_prediction': {'probabilities': probs}}, None)
    _ensure_spf_recommendation_fields(plays)
    return plays


def _score_matrix_conditions(score_matrix, ou_line=None) -> dict:
    if not score_matrix:
        return {}
    norm = _normalize_matrix(score_matrix)
    home_by_margin = {'win_1': 0.0, 'win_2_plus': 0.0, 'draw': 0.0, 'away_win': 0.0}
    away_by_margin = {'win_1': 0.0, 'win_2_plus': 0.0}
    away_goal_prob = 0.0
    home_goal_prob = 0.0
    btts_prob = 0.0
    total_over_line = None
    total_under_line = None
    total_push_line = None
    if ou_line is not None:
        try:
            total_over_line = 0.0
            total_under_line = 0.0
            total_push_line = 0.0
            line = float(ou_line)
        except (TypeError, ValueError):
            total_over_line = None
            total_under_line = None
            total_push_line = None
            line = None
    else:
        line = None

    top_scores = []
    total_goals_prob = {}
    for home_goals, row in enumerate(norm):
        for away_goals, prob in enumerate(row):
            if prob <= 0:
                continue
            margin = home_goals - away_goals
            if margin == 1:
                home_by_margin['win_1'] += prob
            elif margin >= 2:
                home_by_margin['win_2_plus'] += prob
            elif margin == 0:
                home_by_margin['draw'] += prob
            else:
                home_by_margin['away_win'] += prob
                if margin == -1:
                    away_by_margin['win_1'] += prob
                elif margin <= -2:
                    away_by_margin['win_2_plus'] += prob
            if away_goals > 0:
                away_goal_prob += prob
            if home_goals > 0:
                home_goal_prob += prob
            if home_goals > 0 and away_goals > 0:
                btts_prob += prob
            if line is not None:
                total_goals = home_goals + away_goals
                total_goals_prob[total_goals] = total_goals_prob.get(total_goals, 0.0) + prob
            top_scores.append((prob, home_goals, away_goals))

    if line is not None:
        try:
            from backend.app.lottery.services.ou_calculator import asian_ou_line_probabilities

            ou_line_probs = asian_ou_line_probabilities(total_goals_prob, line)
            total_over_line = ou_line_probs.get('over')
            total_under_line = ou_line_probs.get('under')
            total_push_line = ou_line_probs.get('push')
        except Exception:
            total_over_line = sum(p for g, p in total_goals_prob.items() if g > line)
            total_under_line = sum(p for g, p in total_goals_prob.items() if g < line)
            total_push_line = sum(p for g, p in total_goals_prob.items() if g == line)

    top_scores.sort(reverse=True)
    return {
        'home_win_by_1_probability': round(home_by_margin['win_1'], 4),
        'home_win_by_2_plus_probability': round(home_by_margin['win_2_plus'], 4),
        'away_win_by_1_probability': round(away_by_margin['win_1'], 4),
        'away_win_by_2_plus_probability': round(away_by_margin['win_2_plus'], 4),
        'draw_probability_from_matrix': round(home_by_margin['draw'], 4),
        'away_win_probability_from_matrix': round(home_by_margin['away_win'], 4),
        'home_goal_probability': round(home_goal_prob, 4),
        'away_goal_probability': round(away_goal_prob, 4),
        'both_teams_score_probability': round(btts_prob, 4),
        'over_line_probability': round(total_over_line, 4) if total_over_line is not None else None,
        'under_line_probability': round(total_under_line, 4) if total_under_line is not None else None,
        'push_line_probability': round(total_push_line, 4) if total_push_line is not None else None,
        'top_score_cells': [
            {'score': f'{home}-{away}', 'probability': round(prob, 4)}
            for prob, home, away in top_scores[:5]
        ],
    }


def _play_top_probability(play_type: str, prediction: dict, result: dict) -> float:
    if not isinstance(prediction, dict):
        return 0.0
    if play_type == 'spf':
        probs = prediction.get('probabilities') or (result.get('final_prediction') or {}).get('probabilities') or {}
        values = [probs.get('3'), probs.get('1'), probs.get('0'), probs.get('home_win'), probs.get('draw'), probs.get('away_win')]
        numeric = [float(v) for v in values if isinstance(v, (int, float))]
        return max(numeric) if numeric else 0.0
    if play_type in {'rqspf', 'bqc'}:
        probs = prediction.get('probabilities') or prediction.get('adjusted_probs') or {}
        numeric = [float(v) for v in probs.values() if isinstance(v, (int, float))]
        return max(numeric) if numeric else 0.0
    if play_type == 'ou':
        best_line_probs = prediction.get('best_line_probs') or prediction.get('over_under_probs') or {}
        numeric = [float(v) for v in best_line_probs.values() if isinstance(v, (int, float))]
        if numeric:
            return max(numeric)
        candidates = [prediction.get('over_2_5'), prediction.get('under_2_5'), prediction.get('over_3_5')]
        numeric = [float(v) for v in candidates if isinstance(v, (int, float))]
        return max(numeric) if numeric else 0.0
    return 0.0


def _play_risk_profile(play_type: str, prediction: dict, result: dict) -> dict:
    top_prob = _play_top_probability(play_type, prediction, result)
    base = {
        'spf': ('primary_axis', '主判断轴', '胜平负是比赛方向主轴，后续玩法应与它相互校验。'),
        'ou': ('goal_axis', '进球区间轴', '大小球是总进球区间主轴，会约束比分、半全场和让球解释。'),
        'rqspf': ('conditional_projection', '条件推导', '让球胜平负是在方向主轴成立后，继续判断净胜球区间。'),
        'bqc': ('path_projection', '路径推导', '半全场是在全场方向和进球节奏成立后，推演半场路径。'),
    }
    category, label, note = base.get(play_type, ('conditional_projection', '条件推导', '该玩法由主轴条件派生，应看条件是否充分。'))
    if play_type == 'spf':
        level = 'low' if top_prob >= 0.55 else 'medium'
        usage = 'primary'
    elif play_type == 'ou':
        goal_axis = (prediction or {}).get('goal_axis') or {}
        if isinstance(goal_axis, dict) and goal_axis.get('risk_level'):
            axis_label = goal_axis.get('risk_label')
            return {
                'category': 'goal_axis',
                'risk_level': goal_axis.get('risk_level'),
                'risk_label': axis_label or label,
                'risk_note': note,
                'reference_label': axis_label or label,
                'reference_note': note,
                'top_probability': round(top_prob, 4) if top_prob else None,
                'recommended_usage': goal_axis.get('recommended_usage') or 'secondary',
            }
        source = str((prediction or {}).get('source') or '')
        diagnostics = (prediction or {}).get('diagnostics') or {}
        conflict = diagnostics.get('conflict_level')
        volatility = diagnostics.get('volatility_reasons') or []
        has_real_line = bool((prediction or {}).get('line_source') or source)
        if conflict == 'high':
            level = 'very_high'
            label = '分歧进球区间'
            usage = 'watch_only'
        elif conflict == 'medium' or volatility:
            level = 'high'
            label = '谨慎进球区间'
            usage = 'secondary'
        elif has_real_line and top_prob >= 0.58:
            level = 'medium'
            usage = 'secondary'
        else:
            level = 'high'
            usage = 'secondary'
    elif play_type == 'rqspf':
        level = 'medium' if top_prob >= 0.62 else 'high'
        usage = 'secondary'
    else:
        level = 'very_high'
        usage = 'watch_only'
    return {
        'category': category,
        'risk_level': level,
        'risk_label': label,
        'risk_note': note,
        'reference_label': label,
        'reference_note': note,
        'top_probability': round(top_prob, 4) if top_prob else None,
        'recommended_usage': usage,
    }


def _ou_side_from_recommendation(value: Any) -> Optional[str]:
    text = '' if value is None else str(value).strip().lower()
    if not text:
        return None
    if text.startswith('大') or text.startswith('over') or text.startswith('o'):
        return 'over'
    if text.startswith('小') or text.startswith('under') or text.startswith('u'):
        return 'under'
    return None


def _ou_side_label(side: Optional[str]) -> str:
    return {'over': '大球', 'under': '小球'}.get(side or '', '未定')


def _signal_level(value: Any, high: float = 0.70, medium: float = 0.56, low: float = 0.44) -> str:
    if not isinstance(value, (int, float)):
        return 'unknown'
    if value >= high:
        return 'high'
    if value >= medium:
        return 'medium'
    if value <= low:
        return 'low'
    return 'balanced'


def _goal_profile_from_phase(phase_profile: dict) -> dict:
    if not isinstance(phase_profile, dict) or not phase_profile:
        return {}
    home = phase_profile.get('home') if isinstance(phase_profile.get('home'), dict) else {}
    away = phase_profile.get('away') if isinstance(phase_profile.get('away'), dict) else {}

    home_signal = phase_profile.get('home_ft_score_signal')
    away_signal = phase_profile.get('away_ft_score_signal')
    home_suppression = None
    away_suppression = None
    if home and away:
        home_suppression = round(
            float(home.get('ft_clean_sheet_rate') or 0) * 0.55 + float(away.get('ft_blank_rate') or 0) * 0.45,
            4,
        )
        away_suppression = round(
            float(away.get('ft_clean_sheet_rate') or 0) * 0.55 + float(home.get('ft_blank_rate') or 0) * 0.45,
            4,
        )

    return {
        'source': phase_profile.get('source') or 'matches_recent_with_half_time',
        'sample_quality': phase_profile.get('sample_quality'),
        'home_sample_size': home.get('sample_size'),
        'away_sample_size': away.get('sample_size'),
        'home_score_signal': home_signal,
        'away_score_signal': away_signal,
        'home_score_level': _signal_level(home_signal),
        'away_score_level': _signal_level(away_signal),
        'home_suppression_signal': home_suppression,
        'away_suppression_signal': away_suppression,
        'home_recent': {
            'gf': home.get('ft_avg_for'),
            'ga': home.get('ft_avg_against'),
            'score_rate': home.get('ft_score_rate'),
            'concede_rate': home.get('ft_concede_rate'),
            'clean_sheet_rate': home.get('ft_clean_sheet_rate'),
            'blank_rate': home.get('ft_blank_rate'),
            'big_score_rate': home.get('big_score_rate'),
            'big_concede_rate': home.get('big_concede_rate'),
            'ht_zero_zero_rate': home.get('ht_zero_zero_rate'),
            'ht_under_1_5_rate': home.get('ht_under_1_5_rate'),
            'low_total_rate': home.get('low_total_rate'),
            'high_total_rate': home.get('high_total_rate'),
            'defense_collapse_rate': home.get('defense_collapse_rate'),
            'attack_spike_rate': home.get('attack_spike_rate'),
            'avg_shots_for': home.get('avg_shots_for'),
            'avg_shots_against': home.get('avg_shots_against'),
            'avg_sot_for': home.get('avg_sot_for'),
            'avg_sot_against': home.get('avg_sot_against'),
            'avg_xg_for': home.get('avg_xg_for'),
            'avg_xg_against': home.get('avg_xg_against'),
            'shot_sample_size': home.get('shot_sample_size'),
            'xg_sample_size': home.get('xg_sample_size'),
        } if home else {},
        'away_recent': {
            'gf': away.get('ft_avg_for'),
            'ga': away.get('ft_avg_against'),
            'score_rate': away.get('ft_score_rate'),
            'concede_rate': away.get('ft_concede_rate'),
            'clean_sheet_rate': away.get('ft_clean_sheet_rate'),
            'blank_rate': away.get('ft_blank_rate'),
            'big_score_rate': away.get('big_score_rate'),
            'big_concede_rate': away.get('big_concede_rate'),
            'ht_zero_zero_rate': away.get('ht_zero_zero_rate'),
            'ht_under_1_5_rate': away.get('ht_under_1_5_rate'),
            'low_total_rate': away.get('low_total_rate'),
            'high_total_rate': away.get('high_total_rate'),
            'defense_collapse_rate': away.get('defense_collapse_rate'),
            'attack_spike_rate': away.get('attack_spike_rate'),
            'avg_shots_for': away.get('avg_shots_for'),
            'avg_shots_against': away.get('avg_shots_against'),
            'avg_sot_for': away.get('avg_sot_for'),
            'avg_sot_against': away.get('avg_sot_against'),
            'avg_xg_for': away.get('avg_xg_for'),
            'avg_xg_against': away.get('avg_xg_against'),
            'shot_sample_size': away.get('shot_sample_size'),
            'xg_sample_size': away.get('xg_sample_size'),
        } if away else {},
    }


def _goal_axis_support(side: Optional[str], support_side: Optional[str]) -> int:
    if not side or not support_side or support_side == 'mixed':
        return 0
    return 1 if side == support_side else -1


def _opposite_ou_side(side: Optional[str]) -> Optional[str]:
    if side == 'over':
        return 'under'
    if side == 'under':
        return 'over'
    return None


def _format_ou_recommendation(side: Optional[str], line: Any) -> str:
    try:
        line_value = float(line)
    except (TypeError, ValueError):
        line_value = 2.5
    return f"{'大' if side == 'over' else '小'}{line_value:g}" if side in {'over', 'under'} else f'{line_value:g}球'


def _matrix_ou_probabilities(score_matrix, line: Any) -> dict:
    try:
        line_value = float(line)
    except (TypeError, ValueError):
        return {}
    if not score_matrix:
        return {}

    total_goals_prob = {}
    for home_goals, row in enumerate(_normalize_matrix(score_matrix)):
        for away_goals, raw_prob in enumerate(row):
            try:
                prob = float(raw_prob or 0)
            except (TypeError, ValueError):
                prob = 0.0
            if prob <= 0:
                continue
            total_goals = home_goals + away_goals
            total_goals_prob[total_goals] = total_goals_prob.get(total_goals, 0.0) + prob

    try:
        from backend.app.lottery.services.ou_calculator import asian_ou_line_probabilities

        ou_line_probs = asian_ou_line_probabilities(total_goals_prob, line_value)
        over = float(ou_line_probs.get('over') or 0)
        under = float(ou_line_probs.get('under') or 0)
        push = float(ou_line_probs.get('push') or 0)
    except Exception:
        over = sum(prob for total_goals, prob in total_goals_prob.items() if total_goals > line_value)
        under = sum(prob for total_goals, prob in total_goals_prob.items() if total_goals < line_value)
        push = sum(prob for total_goals, prob in total_goals_prob.items() if total_goals == line_value)

    decision_mass = over + under
    return {
        'line': line_value,
        'over_line_probability': round(over, 4),
        'under_line_probability': round(under, 4),
        'push_line_probability': round(push, 4),
        'decision_over_probability': round(over / decision_mass, 4) if decision_mass > 0 else None,
        'decision_under_probability': round(under / decision_mass, 4) if decision_mass > 0 else None,
    }


def _refine_ou_recommendation(ou: dict, result: dict, score_matrix=None, db_path: str = '', match: Optional[dict] = None) -> None:
    """Use the market only as a tie-breaker when the model O/U edge is thin.

    The model distribution remains stored in ``best_line_probs``; this function
    only avoids presenting a 50/50-ish O/U edge as a confident direction.
    """
    if not isinstance(ou, dict):
        return
    line = ou.get('best_line') or ou.get('line') or 2.5
    model_probs = ou.get('best_line_probs') if isinstance(ou.get('best_line_probs'), dict) else {}
    over = _to_float(model_probs.get('over'), None)
    under = _to_float(model_probs.get('under'), None)
    if over is None or under is None:
        return

    model_side = 'over' if over >= under else 'under'
    model_edge = abs(over - under)
    selected_probability = max(over, under)

    market_side = _ou_side_from_recommendation(ou.get('market_recommendation'))
    market_probs = ou.get('market_best_line_probs') if isinstance(ou.get('market_best_line_probs'), dict) else {}
    market_over = _to_float(market_probs.get('over'), None)
    market_under = _to_float(market_probs.get('under'), None)
    market_edge = abs(market_over - market_under) if market_over is not None and market_under is not None else 0.0
    market_selected = max(market_over or 0.0, market_under or 0.0)

    expected = ((result or {}).get('final_prediction') or {}).get('expected_score') or {}
    expected_total = None
    if isinstance(expected, dict):
        home = _to_float(expected.get('home'), None)
        away = _to_float(expected.get('away'), None)
        if home is not None and away is not None:
            expected_total = home + away
    strong_xg_side = None
    try:
        gap = float(expected_total) - float(line) if expected_total is not None else None
        if gap is not None and gap >= 0.45:
            strong_xg_side = 'over'
        elif gap is not None and gap <= -0.45:
            strong_xg_side = 'under'
    except (TypeError, ValueError):
        gap = None

    matrix_ou = _matrix_ou_probabilities(score_matrix, line)
    matrix_over = _to_float(matrix_ou.get('decision_over_probability'), None)
    matrix_under = _to_float(matrix_ou.get('decision_under_probability'), None)
    matrix_side = None
    matrix_selected = None
    if matrix_over is not None and matrix_under is not None:
        if matrix_over >= matrix_under and matrix_over >= 0.52:
            matrix_side = 'over'
            matrix_selected = matrix_over
        elif matrix_under > matrix_over and matrix_under >= 0.52:
            matrix_side = 'under'
            matrix_selected = matrix_under

    before = ou.get('recommendation') or _format_ou_recommendation(model_side, line)
    final_side = model_side
    basis = 'model_distribution'
    if (
        strong_xg_side in {'over', 'under'}
        and matrix_side == strong_xg_side
        and isinstance(matrix_selected, (int, float))
        and matrix_selected >= 0.54
        and abs(float(gap or 0)) >= 0.55
        and (model_side != strong_xg_side or selected_probability < 0.58)
    ):
        final_side = strong_xg_side
        basis = 'expected_total_matrix_self_check'
    if (
        market_side in {'over', 'under'}
        and market_side != model_side
        and model_edge <= 0.02
        and selected_probability < 0.515
        and market_edge >= 0.018
        and market_selected >= 0.512
        and market_edge >= model_edge + 0.012
        and strong_xg_side not in {'over', 'under'}
        and basis == 'model_distribution'
    ):
        final_side = market_side
        basis = 'market_tiebreaker_thin_model_edge'

    national_signal = {}
    national_selected = None
    if (
        _env_float('FOOTBALL_NATIONAL_OU_CONFLICT_GATE_ENABLED', 0.0, 0.0, 1.0) >= 1.0
        and str(os.environ.get('FOOTBALL_NATIONAL_OU_CONFLICT_GATE_PHASE') or 'post').lower() == 'pre'
    ):
        national_signal = _national_ou_reference_signal(db_path, match or {}, line)
        if national_signal:
            ou['national_reference_signal'] = national_signal
        national_side = national_signal.get('side') if isinstance(national_signal, dict) else None
        if (
            isinstance(national_signal, dict)
            and national_signal.get('eligible')
            and national_side in {'over', 'under'}
            and national_side != final_side
        ):
            final_side = national_side
            basis = 'national_reference_conflict_gate'
            sample_bonus = min(
                0.035,
                max(
                    0.0,
                    (min(
                        _to_float(national_signal.get('home_sample'), 0.0) or 0.0,
                        _to_float(national_signal.get('away_sample'), 0.0) or 0.0,
                    ) - _to_float(national_signal.get('min_sample_required'), 16.0)) * 0.003,
                ),
            )
            gap_bonus = min(0.055, abs(_to_float(national_signal.get('total_gap'), 0.0) or 0.0) * 0.055)
            national_selected = round(max(0.535, min(0.64, 0.535 + sample_bonus + gap_bonus)), 4)
            national_display_probs = {
                'over': national_selected if national_side == 'over' else round(1.0 - national_selected, 4),
                'under': national_selected if national_side == 'under' else round(1.0 - national_selected, 4),
                'source': 'national_reference_conflict_gate',
            }
            ou['display_probability_override'] = {
                'raw_best_line_probs': {
                    'over': round(over, 4),
                    'under': round(under, 4),
                    'source': 'pre_national_reference_gate',
                },
                'best_line_probs': national_display_probs,
            }
            ou['best_line_probs'] = national_display_probs

    if basis == 'expected_total_matrix_self_check' and matrix_over is not None and matrix_under is not None:
        ou['display_probability_override'] = {
            'raw_best_line_probs': {
                'over': round(over, 4),
                'under': round(under, 4),
                'source': 'pre_self_check',
            },
            'best_line_probs': {
                'over': round(matrix_over, 4),
                'under': round(matrix_under, 4),
                'source': 'score_matrix_self_check',
            },
        }
    elif basis == 'market_tiebreaker_thin_model_edge' and market_over is not None and market_under is not None:
        ou['display_probability_override'] = {
            'raw_best_line_probs': {
                'over': round(over, 4),
                'under': round(under, 4),
                'source': 'pre_market_tiebreaker',
            },
            'best_line_probs': {
                'over': round(market_over, 4),
                'under': round(market_under, 4),
                'source': 'market_tiebreaker',
            },
        }

    ou['model_recommendation'] = _format_ou_recommendation(model_side, line)
    ou['model_edge'] = round(model_edge, 4)

    # Low-confidence Under correction: data shows Under predictions at <0.60 confidence
    # have only 50.1% accuracy (essentially random), while Over at same confidence
    # has 56.2%. When Under confidence is low, default to Over (which matches the
    # 52.9% base rate of actual Over results).
    if final_side == 'under' and selected_probability < 0.56 and basis == 'model_distribution':
        final_side = 'over'
        basis = 'under_low_confidence_correction'
        ou['under_correction'] = {
            'original_side': 'under',
            'original_confidence': round(selected_probability, 3),
            'reason': 'Under<0.56 only 50.1% accurate in 1477-match validation; defaulting to Over',
        }

    if matrix_ou:
        ou['matrix_ou_self_check'] = {
            **matrix_ou,
            'side': matrix_side,
        }
    ou['recommendation_basis'] = basis
    ou['recommendation'] = _format_ou_recommendation(final_side, line)
    if basis == 'expected_total_matrix_self_check' and isinstance(matrix_selected, (int, float)):
        confidence_basis = max(matrix_selected, over if final_side == 'over' else under)
    elif basis == 'market_tiebreaker_thin_model_edge':
        confidence_basis = market_over if final_side == 'over' else market_under
        if confidence_basis is None:
            confidence_basis = max(market_over or 0, market_under or 0, over, under)
    elif basis == 'national_reference_conflict_gate' and isinstance(national_selected, (int, float)):
        confidence_basis = national_selected
    elif basis == 'model_distribution':
        confidence_basis = max(over, under)
    else:
        confidence_basis = max(market_over or 0, market_under or 0, over, under)
    ou['confidence'] = round(confidence_basis, 3)
    level_probability = confidence_basis if basis in {'expected_total_matrix_self_check', 'national_reference_conflict_gate'} else selected_probability
    if level_probability < 0.535 or (basis == 'model_distribution' and model_edge <= 0.04):
        ou['confidence_level'] = 'low'
    elif level_probability < 0.58:
        ou['confidence_level'] = 'medium'
    else:
        ou['confidence_level'] = 'high'
    if before != ou['recommendation']:
        ou['recommendation_adjustment'] = {
            'from': before,
            'to': ou['recommendation'],
            'reason': basis,
            'model_side': model_side,
            'model_edge': round(model_edge, 4),
            'market_side': market_side,
            'market_edge': round(market_edge, 4),
            'expected_total_minus_line': round(gap, 4) if isinstance(gap, (int, float)) else None,
            'national_reference_side': national_signal.get('side') if isinstance(national_signal, dict) else None,
            'national_reference_total_gap': national_signal.get('total_gap') if isinstance(national_signal, dict) else None,
            'national_reference_source_table': national_signal.get('source_table') if isinstance(national_signal, dict) else None,
        }


def _build_goal_axis(ou: dict, axes: dict, result: dict) -> dict:
    if not isinstance(ou, dict):
        return {}
    diagnostics = ou.get('diagnostics') if isinstance(ou.get('diagnostics'), dict) else {}
    conditions = axes.get('conditions') if isinstance(axes.get('conditions'), dict) else {}
    line = diagnostics.get('line') if diagnostics.get('line') is not None else axes.get('ou_line')
    expected_total = diagnostics.get('expected_total') if diagnostics.get('expected_total') is not None else axes.get('total_xg')
    model_side = diagnostics.get('model_side') or _ou_side_from_recommendation(ou.get('recommendation'))
    market_side = diagnostics.get('market_side')
    over_prob = diagnostics.get('decision_over_probability')
    under_prob = diagnostics.get('decision_under_probability')
    if not isinstance(over_prob, (int, float)):
        over_prob = diagnostics.get('over_line_probability')
    if not isinstance(under_prob, (int, float)):
        under_prob = diagnostics.get('under_line_probability')
    if not isinstance(under_prob, (int, float)) and isinstance(over_prob, (int, float)):
        under_prob = max(0.0, 1.0 - float(over_prob))

    selected_probability = None
    if model_side == 'over' and isinstance(over_prob, (int, float)):
        selected_probability = float(over_prob)
    elif model_side == 'under' and isinstance(under_prob, (int, float)):
        selected_probability = float(under_prob)
    elif isinstance(over_prob, (int, float)) and isinstance(under_prob, (int, float)):
        selected_probability = max(float(over_prob), float(under_prob))

    probability_gap = None
    if isinstance(over_prob, (int, float)) and isinstance(under_prob, (int, float)):
        probability_gap = abs(float(over_prob) - float(under_prob))

    supporting = []
    warnings = []
    components = {}

    def add_support(source: str, side: Optional[str], strength: str, detail: str, score: float) -> None:
        supporting.append({'source': source, 'side': side, 'strength': strength, 'detail': detail})
        components[source] = round(score, 4)

    def add_warning(code: str, detail: str, penalty: float) -> None:
        warnings.append({'code': code, 'detail': detail})
        components[f'warn:{code}'] = round(-abs(penalty), 4)

    if isinstance(selected_probability, (int, float)):
        if selected_probability >= 0.58:
            add_support('score_matrix', model_side, 'strong', f'比分矩阵{_ou_side_label(model_side)}概率{selected_probability * 100:.0f}%', 0.12)
        elif selected_probability >= 0.53:
            add_support('score_matrix', model_side, 'medium', f'比分矩阵{_ou_side_label(model_side)}概率{selected_probability * 100:.0f}%', 0.06)
        else:
            add_warning('thin_probability_edge', '大小球概率优势不足', 0.10)

    line_gap = None
    try:
        if expected_total is not None and line is not None:
            line_gap = float(expected_total) - float(line)
    except (TypeError, ValueError):
        line_gap = None
    if isinstance(line_gap, (int, float)):
        if line_gap >= 0.45:
            add_support('expected_total_vs_line', 'over', 'medium', f'预期总进球高于盘口{line_gap:.2f}', 0.06)
        elif line_gap <= -0.45:
            add_support('expected_total_vs_line', 'under', 'medium', f'预期总进球低于盘口{abs(line_gap):.2f}', 0.06)
        else:
            add_warning('near_market_line', '预期总进球贴近盘口', 0.08)

    if market_side and model_side:
        if market_side == model_side:
            add_support('market_alignment', model_side, 'medium', f'市场与模型同向：{_ou_side_label(model_side)}', 0.06)
            market_alignment = 'aligned'
        else:
            add_warning('market_model_divergence', f'市场倾向{_ou_side_label(market_side)}，模型倾向{_ou_side_label(model_side)}', 0.14)
            market_alignment = 'diverged'
    else:
        market_alignment = 'unknown'

    home_goal = conditions.get('home_goal_probability')
    away_goal = conditions.get('away_goal_probability')
    btts = conditions.get('both_teams_score_probability')
    if isinstance(home_goal, (int, float)) and isinstance(away_goal, (int, float)):
        if home_goal >= 0.72 and away_goal >= 0.58:
            add_support('both_team_goal_probability', 'over', 'medium', f'双方进球概率较高：主{home_goal * 100:.0f}% / 客{away_goal * 100:.0f}%', 0.06)
        elif home_goal < 0.55 and away_goal < 0.55:
            add_support('both_team_goal_probability', 'under', 'medium', f'双方进球把握都不高：主{home_goal * 100:.0f}% / 客{away_goal * 100:.0f}%', 0.06)
        elif min(home_goal, away_goal) < 0.46 and max(home_goal, away_goal) >= 0.72:
            add_support('one_sided_goal_profile', 'mixed', 'watch', f'单边进球形态明显：主{home_goal * 100:.0f}% / 客{away_goal * 100:.0f}%', 0.00)
    if isinstance(btts, (int, float)):
        if btts >= 0.58:
            add_support('btts_probability', 'over', 'medium', f'双方进球概率{btts * 100:.0f}%', 0.04)
        elif btts <= 0.38:
            add_support('btts_probability', 'under', 'medium', f'双方进球概率仅{btts * 100:.0f}%', 0.04)

    goal_profile = _goal_profile_from_phase(axes.get('phase_profile') or {})
    home_signal = goal_profile.get('home_score_signal')
    away_signal = goal_profile.get('away_score_signal')
    if isinstance(home_signal, (int, float)) and isinstance(away_signal, (int, float)):
        if home_signal >= 0.68 and away_signal >= 0.56:
            add_support('recent_attack_defense_profile', 'over', 'medium', f'近期攻防进球信号：主{home_signal * 100:.0f}% / 客{away_signal * 100:.0f}%', 0.05)
        elif home_signal <= 0.50 and away_signal <= 0.50:
            add_support('recent_attack_defense_profile', 'under', 'medium', f'近期攻防进球信号偏低：主{home_signal * 100:.0f}% / 客{away_signal * 100:.0f}%', 0.05)
        else:
            add_support('recent_attack_defense_profile', 'mixed', 'watch', f'近期攻防进球信号：主{home_signal * 100:.0f}% / 客{away_signal * 100:.0f}%', 0.00)
    home_recent = goal_profile.get('home_recent') if isinstance(goal_profile.get('home_recent'), dict) else {}
    away_recent = goal_profile.get('away_recent') if isinstance(goal_profile.get('away_recent'), dict) else {}
    home_tail = (
        float(home_recent.get('big_score_rate') or 0) * 0.58
        + float(away_recent.get('big_concede_rate') or 0) * 0.42
    ) if home_recent or away_recent else None
    away_tail = (
        float(away_recent.get('big_score_rate') or 0) * 0.58
        + float(home_recent.get('big_concede_rate') or 0) * 0.42
    ) if home_recent or away_recent else None
    if isinstance(home_tail, (int, float)) and isinstance(away_tail, (int, float)):
        tail_signal = max(home_tail, away_tail)
        if tail_signal >= 0.26:
            add_support(
                'recent_tail_goal_profile',
                'over',
                'light',
                f'近期存在大比分尾部风险：主{home_tail * 100:.0f}% / 客{away_tail * 100:.0f}%',
                0.04,
            )
            if model_side == 'under':
                add_warning('tail_risk_against_under', '近期大比分尾部风险与小球方向冲突', 0.06)
        elif tail_signal <= 0.08 and home_signal is not None and away_signal is not None:
            add_support(
                'recent_low_tail_profile',
                'under',
                'light',
                f'近期大比分尾部风险低：主{home_tail * 100:.0f}% / 客{away_tail * 100:.0f}%',
                0.03,
            )

    low_tempo_signal = None
    if home_recent or away_recent:
        home_low = float(home_recent.get('low_total_rate') or 0)
        away_low = float(away_recent.get('low_total_rate') or 0)
        home_ht00 = float(home_recent.get('ht_zero_zero_rate') or 0)
        away_ht00 = float(away_recent.get('ht_zero_zero_rate') or 0)
        home_ht_under = float(home_recent.get('ht_under_1_5_rate') or 0)
        away_ht_under = float(away_recent.get('ht_under_1_5_rate') or 0)
        low_tempo_signal = (
            ((home_low + away_low) / 2) * 0.55
            + ((home_ht00 + away_ht00) / 2) * 0.25
            + ((home_ht_under + away_ht_under) / 2) * 0.20
        )
        if low_tempo_signal >= 0.50:
            add_support(
                'recent_low_tempo_profile',
                'under',
                'medium',
                f'近期低节奏画像偏强：低总进球{((home_low + away_low) / 2) * 100:.0f}% / 半场0-0{((home_ht00 + away_ht00) / 2) * 100:.0f}%',
                0.05,
            )
            if model_side == 'over':
                add_warning('low_tempo_against_over', '近期低节奏画像与大球方向冲突', 0.05)
        elif low_tempo_signal <= 0.24 and max(float(home_recent.get('high_total_rate') or 0), float(away_recent.get('high_total_rate') or 0)) >= 0.24:
            add_support(
                'recent_open_tempo_profile',
                'over',
                'light',
                f'近期开放节奏画像：低节奏{low_tempo_signal * 100:.0f}%',
                0.03,
            )

    collapse_signal = None
    if home_recent or away_recent:
        home_collapse = (
            float(home_recent.get('attack_spike_rate') or 0) * 0.45
            + float(away_recent.get('defense_collapse_rate') or 0) * 0.55
        )
        away_collapse = (
            float(away_recent.get('attack_spike_rate') or 0) * 0.45
            + float(home_recent.get('defense_collapse_rate') or 0) * 0.55
        )
        collapse_signal = max(home_collapse, away_collapse)
        if collapse_signal >= 0.28:
            add_support(
                'recent_defensive_collapse_profile',
                'over',
                'light',
                f'近期防守崩盘/进攻爆点风险：主{home_collapse * 100:.0f}% / 客{away_collapse * 100:.0f}%',
                0.04,
            )
            if model_side == 'under':
                add_warning('collapse_risk_against_under', '近期防守崩盘风险与小球方向冲突', 0.05)
    if goal_profile.get('sample_quality') == 'low':
        add_warning('low_phase_profile_sample', '近期进失球画像样本偏少', 0.05)

    historical = diagnostics.get('historical_line_profile') or ou.get('line_profile') or {}
    historical_support = None
    if historical:
        sample_size = int(historical.get('sample_size') or 0)
        over_rate = historical.get('over_rate')
        under_rate = historical.get('under_rate')
        edge_rate = historical.get('edge_rate')
        if sample_size < 12:
            add_warning('thin_historical_line_sample', f'同类盘口历史样本仅{sample_size}场', 0.04)
        if isinstance(over_rate, (int, float)) and isinstance(under_rate, (int, float)) and sample_size >= 8:
            if over_rate - under_rate >= 0.18:
                historical_support = 'over'
                add_support('historical_line_profile', 'over', 'light', f'历史同类盘口大球率{over_rate * 100:.0f}%', 0.04)
            elif under_rate - over_rate >= 0.18:
                historical_support = 'under'
                add_support('historical_line_profile', 'under', 'light', f'历史同类盘口小球率{under_rate * 100:.0f}%', 0.04)
        if isinstance(edge_rate, (int, float)) and edge_rate >= 0.40 and sample_size >= 8:
            add_warning('high_line_edge_rate', f'历史同类盘口卡边率{edge_rate * 100:.0f}%', 0.05)

    similarity_signal = diagnostics.get('historical_similarity_signal') or ou.get('similarity_signal') or {}
    similarity_support = None
    if isinstance(similarity_signal, dict) and similarity_signal:
        sample_size = int(similarity_signal.get('sample_size') or 0)
        same_sample = int(similarity_signal.get('same_prediction_sample_size') or 0)
        same_hit_rate = similarity_signal.get('same_prediction_hit_rate')
        hit_rate = similarity_signal.get('hit_rate')
        similarity_support = similarity_signal.get('support_side')
        if sample_size < 3:
            add_warning('thin_ou_similarity_sample', f'相似大小球案例仅{sample_size}场', 0.04)
        if similarity_support in {'over', 'under'}:
            rate = same_hit_rate if isinstance(same_hit_rate, (int, float)) else hit_rate
            rate_text = f'{rate * 100:.0f}%' if isinstance(rate, (int, float)) else '--'
            sample_text = same_sample if same_sample else sample_size
            if model_side and similarity_support != model_side:
                add_warning(
                    'similar_cases_against_goal_axis',
                    f'相似大小球案例偏向{_ou_side_label(similarity_support)}，{sample_text}场命中率{rate_text}',
                    0.08,
                )
            else:
                add_support(
                    'historical_similarity_cases',
                    similarity_support,
                    'medium' if sample_size >= 5 else 'light',
                    f'相似大小球案例支持{_ou_side_label(similarity_support)}，{sample_text}场命中率{rate_text}',
                    0.06 if sample_size >= 5 else 0.03,
                )

    national_reference_signal = diagnostics.get('national_reference_signal') or ou.get('national_reference_signal') or {}
    national_reference_support = None
    if isinstance(national_reference_signal, dict) and national_reference_signal:
        national_reference_support = national_reference_signal.get('side')
        if national_reference_signal.get('eligible') and national_reference_support in {'over', 'under'}:
            detail = (
                f"national total signal {national_reference_signal.get('total_signal')} "
                f"vs line {national_reference_signal.get('line')} "
                f"(samples {national_reference_signal.get('home_sample')}/{national_reference_signal.get('away_sample')})"
            )
            if national_reference_support == model_side:
                add_support('national_goal_reference', national_reference_support, 'medium', detail, 0.07)
            else:
                add_warning('national_goal_reference_conflict', detail, 0.07)

    push_prob = diagnostics.get('push_line_probability')
    if isinstance(push_prob, (int, float)) and push_prob >= 0.12:
        add_warning('push_probability_high', f'走盘概率{push_prob * 100:.0f}%', 0.05)
    if diagnostics.get('score_cluster_near_line'):
        add_warning('score_cluster_near_line', '高概率比分集中在盘口附近', 0.06)

    side_support = sum(_goal_axis_support(model_side, item.get('side')) for item in supporting)
    warning_penalty = sum(abs(value) for key, value in components.items() if key.startswith('warn:'))
    base_score = 0.50
    if isinstance(selected_probability, (int, float)):
        base_score += max(-0.08, min(0.16, (selected_probability - 0.50) * 1.15))
    base_score += max(-0.12, min(0.12, side_support * 0.035))
    base_score -= min(0.22, warning_penalty)
    confidence_score = round(max(0.20, min(0.82, base_score)), 4)

    if diagnostics.get('conflict_level') == 'high' or confidence_score < 0.50:
        confidence_level = 'low'
        risk_level = 'very_high'
        risk_label = '分歧进球区间'
        usage = 'watch_only'
    elif confidence_score >= 0.62 and warning_penalty <= 0.08:
        confidence_level = 'high'
        risk_level = 'medium'
        risk_label = '进球区间轴'
        usage = 'secondary'
    elif confidence_score >= 0.54:
        confidence_level = 'medium'
        risk_level = 'high'
        risk_label = '谨慎进球区间'
        usage = 'secondary'
    else:
        confidence_level = 'low'
        risk_level = 'high'
        risk_label = '谨慎进球区间'
        usage = 'watch_only'

    sensitivity_reasons = [item['detail'] for item in warnings]
    sensitivity_level = 'high' if len(warnings) >= 3 or diagnostics.get('conflict_level') == 'high' else 'medium' if warnings else 'low'
    summary_bits = []
    if line is not None:
        summary_bits.append(f'盘口{float(line):g}' if isinstance(line, (int, float)) else f'盘口{line}')
    if expected_total is not None:
        summary_bits.append(f'预期{float(expected_total):.2f}')
    if model_side:
        prob_text = f'{selected_probability * 100:.0f}%' if isinstance(selected_probability, (int, float)) else '--'
        summary_bits.append(f'进球轴倾向{_ou_side_label(model_side)}{prob_text}')
    if market_alignment == 'diverged':
        summary_bits.append('市场分歧')
    if sensitivity_reasons:
        summary_bits.append('谨慎点：' + ' / '.join(sensitivity_reasons[:2]))

    return {
        'side': model_side,
        'side_cn': _ou_side_label(model_side),
        'line': line,
        'expected_total': expected_total,
        'line_gap': round(line_gap, 4) if isinstance(line_gap, (int, float)) else None,
        'selected_probability': round(selected_probability, 4) if isinstance(selected_probability, (int, float)) else None,
        'over_probability': round(float(over_prob), 4) if isinstance(over_prob, (int, float)) else None,
        'under_probability': round(float(under_prob), 4) if isinstance(under_prob, (int, float)) else None,
        'probability_gap': round(probability_gap, 4) if isinstance(probability_gap, (int, float)) else None,
        'confidence_score': confidence_score,
        'confidence_level': confidence_level,
        'risk_level': risk_level,
        'risk_label': risk_label,
        'recommended_usage': usage,
        'market_alignment': market_alignment,
        'market_side': market_side,
        'model_side': model_side,
        'attack_defense_profile': goal_profile,
        'historical_line_signal': {
            'support_side': historical_support,
            'sample_size': historical.get('sample_size'),
            'over_rate': historical.get('over_rate'),
            'under_rate': historical.get('under_rate'),
            'edge_rate': historical.get('edge_rate'),
            'scope': historical.get('scope'),
        } if historical else {},
        'historical_similarity_signal': {
            'support_side': similarity_support,
            'sample_size': similarity_signal.get('sample_size'),
            'hit_rate': similarity_signal.get('hit_rate'),
            'same_prediction_sample_size': similarity_signal.get('same_prediction_sample_size'),
            'same_prediction_hit_rate': similarity_signal.get('same_prediction_hit_rate'),
            'average_similarity': similarity_signal.get('average_similarity'),
        } if isinstance(similarity_signal, dict) and similarity_signal else {},
        'national_reference_signal': {
            'support_side': national_reference_support,
            'eligible': national_reference_signal.get('eligible'),
            'reason': national_reference_signal.get('reason'),
            'source_table': national_reference_signal.get('source_table'),
            'home_sample': national_reference_signal.get('home_sample'),
            'away_sample': national_reference_signal.get('away_sample'),
            'total_signal': national_reference_signal.get('total_signal'),
            'line': national_reference_signal.get('line'),
            'total_gap': national_reference_signal.get('total_gap'),
        } if isinstance(national_reference_signal, dict) and national_reference_signal else {},
        'sensitivity': {
            'level': sensitivity_level,
            'reasons': sensitivity_reasons,
        },
        'supporting_evidence': supporting,
        'warnings': warnings,
        'component_scores': components,
        'summary': '；'.join(summary_bits),
    }


def _load_ou_line_profile(db_path: str, match: dict, ou_result: dict) -> dict:
    """Load historical O/U line calibration built from post-match reviews.

    This intentionally does not infer that any line is "sensitive" by rule.
    It only returns persisted calibration rows created from finished matches.
    """
    if not db_path or not isinstance(ou_result, dict):
        return {}

    raw_line = ou_result.get('best_line') or ou_result.get('line')
    try:
        line = round(float(raw_line), 2)
    except (TypeError, ValueError):
        return {}

    league_name = (
        (match or {}).get('league_name_cn')
        or (match or {}).get('league_name')
        or (match or {}).get('competition')
        or ''
    )

    try:
        conn = sqlite3.connect(db_path, timeout=10)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='ou_line_calibration'"
        )
        if not cursor.fetchone():
            conn.close()
            return {}

        cursor.execute("PRAGMA table_info(ou_line_calibration)")
        columns = {row['name'] for row in cursor.fetchall()}
        required = {'line', 'sample_size', 'over_rate', 'under_rate', 'push_rate', 'edge_rate'}
        if not required.issubset(columns):
            conn.close()
            return {}

        select_columns = [
            'line',
            'sample_size',
            'over_rate',
            'under_rate',
            'push_rate',
            'edge_rate',
        ]
        for optional in (
            'league_name_cn',
            'scenario_type',
            'avg_total_goals',
            'median_total_goals',
            'prediction_hit_rate',
            'edge_definition',
            'updated_at',
            'source',
        ):
            if optional in columns:
                select_columns.append(optional)

        league_filter = ''
        params: List[Any] = [line]
        if 'league_name_cn' in columns:
            league_filter = """
                AND (
                    league_name_cn = ?
                    OR league_name_cn IS NULL
                    OR league_name_cn = ''
                    OR league_name_cn = '_global'
                )
            """
            params.append(league_name)

        order_by = """
            CASE
                WHEN league_name_cn = ? THEN 0
                WHEN league_name_cn = '_global' THEN 1
                WHEN league_name_cn IS NULL OR league_name_cn = '' THEN 2
                ELSE 3
            END,
            sample_size DESC
        """ if 'league_name_cn' in columns else "sample_size DESC"
        if 'league_name_cn' in columns:
            params.append(league_name)

        cursor.execute(f"""
            SELECT {', '.join(select_columns)}
            FROM ou_line_calibration
            WHERE ABS(line - ?) < 0.001
            {league_filter}
            ORDER BY {order_by}
            LIMIT 1
        """, params)
        row = cursor.fetchone()
        conn.close()
        if not row:
            return {}

        data = dict(row)
        for key in ('line', 'over_rate', 'under_rate', 'push_rate', 'edge_rate',
                    'avg_total_goals', 'median_total_goals', 'prediction_hit_rate'):
            if key in data and data[key] is not None:
                data[key] = round(float(data[key]), 4)
        if data.get('sample_size') is not None:
            data['sample_size'] = int(data['sample_size'])
        data['source'] = data.get('source') or 'ou_line_calibration'
        data['scope'] = 'league' if data.get('league_name_cn') == league_name and league_name else 'global'
        return data
    except Exception as exc:
        logger.debug('读取大小球盘口历史画像失败: %s', exc)
        return {}


def _safe_json_dict(value: Any) -> dict:
    if isinstance(value, dict):
        return value
    if not value:
        return {}
    try:
        loaded = json.loads(value)
        return loaded if isinstance(loaded, dict) else {}
    except Exception:
        return {}


def _load_ou_similarity_signal(db_path: str, match: dict, ou_result: dict, limit: int = 8) -> dict:
    if not db_path or not isinstance(match, dict) or not isinstance(ou_result, dict):
        return {}
    match_key = match.get('lottery_match_id') or match.get('match_id')
    if match_key is None:
        return {}

    model_side = _ou_side_from_recommendation(ou_result.get('recommendation'))
    try:
        conn = sqlite3.connect(db_path, timeout=10)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='similar_match_cases'")
        if not cursor.fetchone():
            conn.close()
            return {}
        columns = {row['name'] for row in cursor.execute("PRAGMA table_info(similar_match_cases)").fetchall()}
        play_type_select = 'play_type' if 'play_type' in columns else "NULL AS play_type"
        cursor.execute(
            f"""
            SELECT case_id, similar_match_key, similarity_score, {play_type_select},
                   similarity_json, outcome_json, created_at
            FROM similar_match_cases
            WHERE match_key = ?
            ORDER BY similarity_score DESC, created_at DESC
            LIMIT ?
            """,
            (str(match_key), max(limit * 3, limit)),
        )
        rows = cursor.fetchall()

        # Pre-match leakage gate: exclude similar cases from future matches
        current_kickoff = _get_lottery_kickoff(cursor, str(match_key))
        if current_kickoff:
            filtered = []
            for r in rows:
                sim_key = r['similar_match_key']
                sim_kickoff = _get_lottery_kickoff(cursor, str(sim_key))
                if sim_kickoff and sim_kickoff > current_kickoff:
                    continue
                filtered.append(r)
            rows = filtered

        conn.close()
    except Exception as exc:
        logger.debug('读取大小球相似案例失败: %s', exc)
        return {}

    cases = []
    known = 0
    correct = 0
    same_prediction_known = 0
    same_prediction_correct = 0
    actual_over = 0
    actual_under = 0
    for row in rows:
        similarity = _safe_json_dict(row['similarity_json'])
        outcome = _safe_json_dict(row['outcome_json'])
        row_play_type = row['play_type'] or outcome.get('play_type') or similarity.get('play_type')
        if row_play_type != 'ou':
            continue
        predicted_side = _ou_side_from_recommendation(outcome.get('predicted_result'))
        actual_side = _ou_side_from_recommendation(outcome.get('actual_result'))
        is_correct = outcome.get('is_correct')
        if is_correct is not None:
            known += 1
            correct += 1 if bool(is_correct) else 0
        if actual_side == 'over':
            actual_over += 1
        elif actual_side == 'under':
            actual_under += 1
        same_prediction = bool(model_side and predicted_side == model_side)
        if same_prediction and is_correct is not None:
            same_prediction_known += 1
            same_prediction_correct += 1 if bool(is_correct) else 0
        reasons = similarity.get('reasons') if isinstance(similarity.get('reasons'), dict) else {}
        cases.append({
            'similar_match_key': row['similar_match_key'],
            'similarity_score': round(float(row['similarity_score'] or 0), 4),
            'predicted_side': predicted_side,
            'actual_side': actual_side,
            'is_correct': None if is_correct is None else bool(is_correct),
            'same_prediction': same_prediction,
            'ou_line_gap': reasons.get('ou_line_gap'),
            'expected_total_gap': reasons.get('expected_total_gap'),
        })
        if len(cases) >= limit:
            break

    if not cases:
        return {}

    sample_size = len(cases)
    hit_rate = (correct / known) if known else None
    same_hit_rate = (same_prediction_correct / same_prediction_known) if same_prediction_known else None
    actual_over_rate = actual_over / sample_size
    actual_under_rate = actual_under / sample_size
    support_side = None
    if same_prediction_known >= 3 and isinstance(same_hit_rate, (int, float)):
        if same_hit_rate >= 0.58:
            support_side = model_side
        elif same_hit_rate <= 0.42:
            support_side = _opposite_ou_side(model_side)
    if support_side is None and sample_size >= 4:
        if actual_over_rate >= 0.62:
            support_side = 'over'
        elif actual_under_rate >= 0.62:
            support_side = 'under'

    return {
        'source': 'similar_match_cases',
        'sample_size': sample_size,
        'known_count': known,
        'hit_rate': round(hit_rate, 4) if isinstance(hit_rate, (int, float)) else None,
        'same_prediction_sample_size': same_prediction_known,
        'same_prediction_hit_rate': round(same_hit_rate, 4) if isinstance(same_hit_rate, (int, float)) else None,
        'actual_over_rate': round(actual_over_rate, 4),
        'actual_under_rate': round(actual_under_rate, 4),
        'support_side': support_side,
        'average_similarity': round(sum(item['similarity_score'] for item in cases) / sample_size, 4),
        'cases': cases[:5],
    }


def _build_ou_diagnostics(ou: dict, axes: dict) -> dict:
    if not isinstance(ou, dict):
        return {}
    line = axes.get('ou_line') or ou.get('best_line') or ou.get('line')
    total_xg = axes.get('total_xg')
    conditions = axes.get('conditions') or {}
    matrix_over_prob = conditions.get('over_line_probability')
    matrix_under_prob = conditions.get('under_line_probability')
    push_prob = conditions.get('push_line_probability')
    probs = ou.get('best_line_probs') or {}
    decision_over_prob = probs.get('over')
    decision_under_prob = probs.get('under')
    if not isinstance(decision_over_prob, (int, float)) and isinstance(matrix_over_prob, (int, float)) and isinstance(matrix_under_prob, (int, float)):
        decision_total = float(matrix_over_prob) + float(matrix_under_prob)
        if decision_total > 0:
            decision_over_prob = float(matrix_over_prob) / decision_total
            decision_under_prob = float(matrix_under_prob) / decision_total
    over_prob = decision_over_prob if isinstance(decision_over_prob, (int, float)) else matrix_over_prob
    under_prob = decision_under_prob if isinstance(decision_under_prob, (int, float)) else None
    if under_prob is None and isinstance(over_prob, (int, float)):
        under_prob = max(0.0, 1.0 - float(over_prob))
    final_side = _ou_side_from_recommendation(ou.get('recommendation'))
    model_side = _ou_side_from_recommendation(ou.get('model_recommendation')) or final_side
    if ou.get('recommendation_basis') == 'national_reference_conflict_gate' and final_side in {'over', 'under'}:
        model_side = final_side
    if not model_side and isinstance(over_prob, (int, float)):
        if over_prob >= 0.55:
            model_side = 'over'
        elif over_prob <= 0.45:
            model_side = 'under'
    market_side = _ou_side_from_recommendation(ou.get('market_recommendation'))
    market_probs = ou.get('market_best_line_probs') or {}
    market_over = market_probs.get('over')
    market_under = market_probs.get('under')
    historical_line_profile = ou.get('line_profile') or {}
    historical_similarity_signal = ou.get('similarity_signal') or {}
    national_reference_signal = ou.get('national_reference_signal') or {}

    flags = []
    volatility = []
    if isinstance(total_xg, (int, float)) and line is not None:
        try:
            gap = float(total_xg) - float(line)
            if gap >= 0.45:
                flags.append('预期总进球明显高于盘口')
            elif gap <= -0.45:
                flags.append('预期总进球明显低于盘口')
            else:
                flags.append('预期总进球贴近盘口')
                volatility.append('预期总进球贴近盘口')
        except (TypeError, ValueError):
            pass
    if market_side and model_side and market_side != model_side:
        flags.append('模型与市场方向分歧')
        volatility.append('市场与模型分歧')
    if isinstance(over_prob, (int, float)) and 0.45 < over_prob < 0.55:
        flags.append('盘口附近分布接近五五开')
        volatility.append('大小球概率接近五五开')
    if isinstance(push_prob, (int, float)) and push_prob >= 0.12:
        volatility.append('走盘概率偏高')
    if historical_line_profile:
        sample_size = historical_line_profile.get('sample_size') or 0
        edge_rate = historical_line_profile.get('edge_rate')
        if sample_size < 30:
            flags.append('历史同类盘口样本不足')
        elif isinstance(edge_rate, (int, float)):
            if edge_rate >= 0.45:
                volatility.append('历史同类盘口卡边率偏高')
            elif edge_rate <= 0.25:
                flags.append('历史同类盘口卡边率不高')
    if historical_similarity_signal:
        sample_size = historical_similarity_signal.get('sample_size') or 0
        support_side = historical_similarity_signal.get('support_side')
        if sample_size < 3:
            flags.append('相似大小球案例样本不足')
        elif support_side and model_side and support_side != model_side:
            volatility.append('相似大小球案例与模型方向分歧')
    away_goal = conditions.get('away_goal_probability')
    home_goal = conditions.get('home_goal_probability')
    btts = conditions.get('both_teams_score_probability')
    if isinstance(home_goal, (int, float)) and isinstance(away_goal, (int, float)):
        if home_goal >= 0.75 and away_goal >= 0.55:
            flags.append('双方都有较高进球可能')
        elif home_goal >= 0.75 and away_goal < 0.45:
            flags.append('主队进球强但客队进球弱')
        elif home_goal < 0.55 and away_goal < 0.55:
            flags.append('双方进球把握都不高')
    spf_prob = axes.get('spf_probability')
    if isinstance(spf_prob, (int, float)) and spf_prob < 0.48:
        volatility.append('胜平负主轴不够强')
    top_cells = conditions.get('top_score_cells') or []
    clustered_scores = []
    if top_cells:
        for cell in top_cells[:6]:
            score = cell.get('score')
            if not score or '-' not in score:
                continue
            try:
                h, a = [int(x) for x in score.split('-', 1)]
            except ValueError:
                continue
            total = h + a
            if line is None or abs(total - float(line)) <= 0.75:
                clustered_scores.append(score)
        if len(clustered_scores) >= 3:
            volatility.append('比分高概率点集中在盘口附近')
    conflict_level = 'none'
    if '模型与市场方向分歧' in flags:
        conflict_level = 'high'
    elif volatility:
        conflict_level = 'medium'

    summary_bits = []
    if line is not None:
        summary_bits.append(f'盘口{line:g}' if isinstance(line, (int, float)) else f'盘口{line}')
    if isinstance(total_xg, (int, float)):
        summary_bits.append(f'预期总进球{total_xg:g}')
    if isinstance(matrix_over_prob, (int, float)):
        summary_bits.append(f'大于盘口{matrix_over_prob * 100:.0f}%')
    if isinstance(over_prob, (int, float)) and isinstance(matrix_over_prob, (int, float)) and abs(over_prob - matrix_over_prob) >= 0.05:
        summary_bits.append(f'排除走盘后大球{over_prob * 100:.0f}%')
    summary_bits.append(f'模型倾向{_ou_side_label(model_side)}')
    if market_side:
        summary_bits.append(f'市场倾向{_ou_side_label(market_side)}')
    if historical_line_profile:
        sample_size = historical_line_profile.get('sample_size')
        scope_label = '同联赛' if historical_line_profile.get('scope') == 'league' else '全局'
        if sample_size:
            summary_bits.append(f'{scope_label}历史样本{int(sample_size)}场')
    if historical_similarity_signal:
        sample_size = historical_similarity_signal.get('sample_size')
        hit_rate = historical_similarity_signal.get('same_prediction_hit_rate') or historical_similarity_signal.get('hit_rate')
        if sample_size:
            if isinstance(hit_rate, (int, float)):
                summary_bits.append(f'相似大小球{int(sample_size)}场命中{hit_rate * 100:.0f}%')
            else:
                summary_bits.append(f'相似大小球{int(sample_size)}场')

    return {
        'line': line,
        'expected_total': total_xg,
        'model_side': model_side,
        'final_side': final_side,
        'market_side': market_side,
        'over_line_probability': round(float(matrix_over_prob), 4) if isinstance(matrix_over_prob, (int, float)) else None,
        'under_line_probability': round(float(matrix_under_prob), 4) if isinstance(matrix_under_prob, (int, float)) else None,
        'push_line_probability': round(float(push_prob), 4) if isinstance(push_prob, (int, float)) else None,
        'decision_over_probability': round(float(over_prob), 4) if isinstance(over_prob, (int, float)) else None,
        'decision_under_probability': round(float(under_prob), 4) if isinstance(under_prob, (int, float)) else None,
        'home_goal_probability': home_goal,
        'away_goal_probability': away_goal,
        'both_teams_score_probability': btts,
        'market_over_probability': market_over,
        'market_under_probability': market_under,
        'historical_line_profile': historical_line_profile,
        'historical_similarity_signal': historical_similarity_signal,
        'national_reference_signal': national_reference_signal,
        'conflict_level': conflict_level,
        'volatility_reasons': sorted(set(volatility)),
        'score_cluster_near_line': clustered_scores[:5],
        'flags': flags,
        'summary': '；'.join(summary_bits),
    }


def _primary_play_axes(plays: dict, result: dict, score_matrix=None) -> dict:
    fp = result.get('final_prediction') or {}
    spf = plays.get('spf') or {}
    ou = plays.get('ou') or {}
    bqc = plays.get('bqc') if isinstance(plays.get('bqc'), dict) else {}
    probs = spf.get('probabilities') or {}
    direction = spf.get('direction') or {'home_win': '3', 'draw': '1', 'away_win': '0'}.get(fp.get('predicted_result'))
    direction_cn = spf.get('direction_cn') or {'3': '主胜', '1': '平局', '0': '客胜'}.get(direction, '')
    ou_rec = ou.get('recommendation') or ''
    ou_line = ou.get('best_line') or ou.get('line')
    expected = fp.get('expected_score') or {}
    total_xg = None
    if isinstance(expected, dict) and expected.get('home') is not None and expected.get('away') is not None:
        try:
            total_xg = round(float(expected.get('home') or 0) + float(expected.get('away') or 0), 2)
        except (TypeError, ValueError):
            total_xg = None
    conditions = _score_matrix_conditions(score_matrix, ou_line)
    selected_score_cells = []
    for item in plays.get('top3_scores') or []:
        if not isinstance(item, dict) or not item.get('score'):
            continue
        selected_score_cells.append({
            'score': item.get('score'),
            'probability': item.get('probability'),
            'candidate_reasons': item.get('candidate_reasons') or [],
            'candidate_source': item.get('candidate_source'),
        })
    axes = {
        'spf_direction': direction,
        'spf_direction_cn': direction_cn,
        'spf_probability': max([v for v in probs.values() if isinstance(v, (int, float))], default=None),
        'ou_recommendation': ou_rec,
        'ou_line': ou_line,
        'total_xg': total_xg,
        'conditions': conditions,
        'phase_profile': bqc.get('phase_profile') if isinstance(bqc.get('phase_profile'), dict) else {},
        'selected_score_cells': selected_score_cells,
    }
    if conditions:
        axes.update(conditions)
    return axes


def _play_derivation(play_type: str, axes: dict, prediction: dict) -> dict:
    direction = axes.get('spf_direction_cn') or '胜平负方向'
    ou_text = axes.get('ou_recommendation') or (
        f"{axes.get('ou_line')}球盘口" if axes.get('ou_line') is not None else '进球区间'
    )
    total_xg = axes.get('total_xg')
    total_text = f"预期总进球{total_xg}" if total_xg is not None else '总进球分布'
    conditions = axes.get('conditions') or {}
    home_win_1 = conditions.get('home_win_by_1_probability')
    home_win_2p = conditions.get('home_win_by_2_plus_probability')
    away_goal = conditions.get('away_goal_probability')
    btts = conditions.get('both_teams_score_probability')
    over_line = conditions.get('over_line_probability')
    top_cells = conditions.get('top_score_cells') or []

    def pct(value):
        return f"{value * 100:.0f}%" if isinstance(value, (int, float)) else '--'

    if play_type == 'spf':
        return {
            'base_axes': ['胜平负概率主轴'],
            'formula': '赔率/ELO/Poisson/情报修正后的三项概率取最大方向',
            'summary': f'主轴方向：{direction}',
        }
    if play_type == 'ou':
        goal_axis = prediction.get('goal_axis') or {}
        diagnostics = prediction.get('diagnostics') or {}
        detail_bits = []
        if isinstance(goal_axis, dict) and goal_axis.get('summary'):
            detail_bits.append(goal_axis.get('summary'))
        if diagnostics.get('summary'):
            detail_bits.append(diagnostics.get('summary'))
        if diagnostics.get('flags'):
            detail_bits.append('；'.join(diagnostics.get('flags')[:3]))
        if diagnostics.get('volatility_reasons'):
            detail_bits.append('谨慎点：' + ' / '.join(diagnostics.get('volatility_reasons')[:3]))
        return {
            'base_axes': ['进球区间主轴', '大小球盘口'],
            'formula': '真实盘口线 + 比分矩阵总进球分布 + 双方进球概率 + 市场倾向交叉校验',
            'summary': '；'.join(detail_bits) if detail_bits else f'进球区间：{ou_text}，{total_text}',
            'conditions': diagnostics,
        }
    if play_type == 'rqspf':
        margin_bits = []
        axis = prediction.get('axis_projection') if isinstance(prediction.get('axis_projection'), dict) else {}
        display_source = prediction.get('display_source') or 'unconditional'
        global_probs = prediction.get('unconditional_probabilities') or prediction.get('probabilities') or {}
        axis_probs = axis.get('probabilities') or {}
        display_label = prediction.get('recommendation_cn') or {'3': '让胜', '1': '让平', '0': '让负'}.get(prediction.get('direction'), '')
        gate_adjustment = prediction.get('handicap_margin_gate_adjustment') if isinstance(prediction.get('handicap_margin_gate_adjustment'), dict) else {}
        goal_line_label = prediction.get('goal_line_label') or _format_goal_line(prediction.get('handicap', 0))
        margin_requirement = prediction.get('margin_requirement') or _rqspf_margin_requirement(
            prediction.get('handicap', 0),
            prediction.get('direction'),
        )
        if margin_requirement:
            margin_bits.append(margin_requirement)
        if axes.get('spf_direction') == '0':
            away_win_1 = conditions.get('away_win_by_1_probability')
            away_win_2p = conditions.get('away_win_by_2_plus_probability')
            if away_win_1 is not None:
                margin_bits.append(f"客胜1球{pct(away_win_1)}")
            if away_win_2p is not None:
                margin_bits.append(f"客胜2+球{pct(away_win_2p)}")
        else:
            if home_win_1 is not None:
                margin_bits.append(f"主胜1球{pct(home_win_1)}")
            if home_win_2p is not None:
                margin_bits.append(f"主胜2+球{pct(home_win_2p)}")
        if global_probs:
            margin_bits.append(
                "全局盘面 "
                f"让胜{pct(global_probs.get('3'))} / "
                f"让平{pct(global_probs.get('1'))} / "
                f"让负{pct(global_probs.get('0'))}"
            )
        if axis_probs:
            basis_map = {
                'spf_bqc_ou_axis': '胜平负+半全场+大小球主轴',
                'spf_ou_axis': '胜平负+大小球主轴',
                'spf_bqc_axis': '胜平负+半全场主轴',
                'spf_axis': '胜平负主轴',
            }
            basis_label = basis_map.get(axis.get('basis'), '主轴条件')
            axis_requirement = axis.get('margin_requirement') or _rqspf_margin_requirement(
                prediction.get('handicap', 0),
                axis.get('direction'),
            )
            margin_bits.append(
                f"{basis_label} "
                f"让胜{pct(axis_probs.get('3'))} / "
                f"让平{pct(axis_probs.get('1'))} / "
                f"让负{pct(axis_probs.get('0'))}"
            )
            if axis_requirement and axis_requirement != margin_requirement:
                margin_bits.append(f"主轴门槛：{axis_requirement}")
        if display_source != 'unconditional':
            margin_bits.append(f"卡片按主轴条件展示为{display_label}")
        if gate_adjustment:
            gate_bits = []
            if gate_adjustment.get('from') or gate_adjustment.get('to'):
                gate_bits.append(
                    f"{gate_adjustment.get('from') or '原方向'} -> {gate_adjustment.get('to') or display_label}"
                )
            reason_map = {
                'positive_tail_cover': '强队净胜尾部更集中',
                'negative_tail_cover': '受让方被穿盘风险更高',
                'exact_margin_weak': '正好赢盘边界支撑不足',
                'rqspf_margin_boundary': '让球边界回测',
            }
            gate_bits.append(reason_map.get(gate_adjustment.get('reason'), gate_adjustment.get('reason') or '让球边界回测'))
            selected_probability = gate_adjustment.get('selected_probability')
            if isinstance(selected_probability, (int, float)) and selected_probability > 0:
                gate_bits.append(f"覆盖概率{pct(selected_probability)}")
            gate_requirement = gate_adjustment.get('margin_requirement')
            if gate_requirement and gate_requirement != margin_requirement:
                gate_bits.append(str(gate_requirement))
            margin_bits.append('门禁覆盖：' + ' / '.join(gate_bits))
        return {
            'base_axes': ['胜平负方向', '净胜球分布', '让球盘口'],
            'formula': '比分矩阵先算全局让球分布，再按胜平负/大小球主轴做条件化校验',
            'summary': f'由{direction}方向叠加让球线{goal_line_label}推导；' + ' / '.join(margin_bits),
            'conditions': {
                'home_win_by_1_probability': home_win_1,
                'home_win_by_2_plus_probability': home_win_2p,
                'away_win_by_1_probability': conditions.get('away_win_by_1_probability'),
                'away_win_by_2_plus_probability': conditions.get('away_win_by_2_plus_probability'),
                'unconditional_probabilities': global_probs,
                'axis_projection': axis,
                'display_source': display_source,
                'margin_requirement': margin_requirement,
            },
        }
    if play_type == 'bqc':
        adjustment = prediction.get('consistency_adjustment') or {}
        phase_adjustment = prediction.get('phase_axis_adjustment') or {}
        adjustment_text = ''
        if adjustment:
            adjustment_text = (
                f"；已按{'让球条件' if adjustment.get('reason') == 'rqspf_condition' else '胜平负主轴'}"
                f"校正为{adjustment.get('to_cn') or adjustment.get('to')}"
            )
        if phase_adjustment:
            adjustment_text += (
                f"；上半场画像更支持{phase_adjustment.get('to_cn') or phase_adjustment.get('to')}"
            )
        phase = prediction.get('phase_profile') or {}
        phase_text = ''
        if phase:
            home_signal = phase.get('home_ht_score_signal')
            away_signal = phase.get('away_ht_score_signal')
            bits = []
            if isinstance(home_signal, (int, float)):
                bits.append(f"主队上半场进球信号{home_signal * 100:.0f}%")
            if isinstance(away_signal, (int, float)):
                bits.append(f"客队上半场进球信号{away_signal * 100:.0f}%")
            home_sample = ((phase.get('home') or {}).get('sample_size'))
            away_sample = ((phase.get('away') or {}).get('sample_size'))
            if home_sample or away_sample:
                bits.append(f"样本{home_sample or 0}/{away_sample or 0}场")
            if phase.get('sample_quality') == 'low':
                bits.append('低样本降权')
            if bits:
                phase_text = '；' + ' / '.join(bits)
        return {
            'base_axes': ['胜平负方向', '进球节奏', '半场路径'],
            'formula': '上半场进失球画像 + 半场Poisson路径 × 全场方向概率，并加入半全场相关系数',
            'summary': f'由{direction}方向和{total_text}推导半场路径{phase_text}{adjustment_text}',
        }
    if play_type == 'bf':
        score_bits = []
        selected_score_cells = axes.get('selected_score_cells') or []
        if away_goal is not None:
            score_bits.append(f"客队进球{pct(away_goal)}")
        if btts is not None:
            score_bits.append(f"双方进球{pct(btts)}")
        if over_line is not None:
            score_bits.append(f"大于盘口{pct(over_line)}")
        if selected_score_cells:
            score_bits.append('展示候选' + '/'.join(cell.get('score', '') for cell in selected_score_cells[:3]))
        if top_cells:
            if not selected_score_cells:
                score_bits.append('候选' + '/'.join(cell.get('score', '') for cell in top_cells[:3]))
        ou_diag = axes.get('ou_diagnostics') or {}
        near_line = ou_diag.get('score_cluster_near_line') or []
        if near_line:
            score_bits.append('盘口附近' + '/'.join(near_line[:3]))
        return {
            'base_axes': ['胜平负方向', '大小球/总进球区间', '比分矩阵落点'],
            'formula': '在方向和总进球区间约束下取比分矩阵概率最高点',
            'summary': f'由{direction}方向 + {ou_text} 推导比分落点；' + ' / '.join(score_bits),
            'conditions': {
                'away_goal_probability': away_goal,
                'both_teams_score_probability': btts,
                'over_line_probability': over_line,
                'top_score_cells': top_cells[:5],
                'selected_score_cells': selected_score_cells[:5],
            },
        }
    return {'base_axes': [], 'formula': '', 'summary': ''}


def _apply_play_consistency(plays: dict) -> None:
    """Keep derived play recommendations logically compatible.

    The card/detail UI shows SPF, RQSPF, BQC, O/U and scores together. A BQC
    recommendation whose full-time side contradicts a hard RQSPF condition is
    worse than "low confidence"; it is internally impossible. This guard keeps
    the displayed set coherent and records the adjustment.
    """
    if not isinstance(plays, dict):
        return

    bqc = plays.get('bqc') if isinstance(plays.get('bqc'), dict) else {}
    if not bqc:
        return

    bqc_cn = {
        'hh': '胜胜', 'hd': '胜平', 'ha': '胜负',
        'dh': '平胜', 'dd': '平平', 'da': '平负',
        'ah': '负胜', 'ad': '负平', 'aa': '负负',
    }

    rqspf_cn = {'3': '让胜', '1': '让平', '0': '让负'}
    spf_cn = {'3': '主胜', '1': '平局', '0': '客胜'}

    def spf_axis_trusted() -> bool:
        spf = plays.get('spf') if isinstance(plays.get('spf'), dict) else {}
        axis_context = spf.get('axis_context') if isinstance(spf.get('axis_context'), dict) else None
        return _axis_context_is_trusted(axis_context) if axis_context is not None else True

    def spf_axis_trusted_for_bqc() -> bool:
        spf = plays.get('spf') if isinstance(plays.get('spf'), dict) else {}
        axis_context = spf.get('axis_context') if isinstance(spf.get('axis_context'), dict) else None
        return _axis_context_is_trusted_for_bqc(axis_context) if axis_context is not None else True

    def apply_spf_arbitration_from_rqspf() -> None:
        spf = plays.get('spf') if isinstance(plays.get('spf'), dict) else {}
        rqspf = plays.get('rqspf') if isinstance(plays.get('rqspf'), dict) else {}
        arbitration = rqspf.get('full_time_arbitration') if isinstance(rqspf.get('full_time_arbitration'), dict) else {}
        target = str(arbitration.get('suggested_spf_direction') or '')
        current = str(spf.get('direction') or '')
        if not spf or not arbitration or target not in {'3', '1', '0'} or target == current:
            return
        probabilities = spf.get('probabilities') if isinstance(spf.get('probabilities'), dict) else {}
        spf['direction'] = target
        spf['recommendation'] = target
        spf['direction_cn'] = spf_cn.get(target, '')
        spf['arbitration_adjustment'] = {
            'from': current,
            'from_cn': spf_cn.get(current, ''),
            'to': target,
            'to_cn': spf_cn.get(target, ''),
            'reason': arbitration.get('reason') or 'rqspf_margin_distribution',
            'original_probability': round(float(probabilities.get(current) or 0.0), 4),
            'selected_probability': round(float(probabilities.get(target) or 0.0), 4),
            'rqspf_direction': arbitration.get('rqspf_direction'),
            'rqspf_probability': arbitration.get('rqspf_probability'),
            'rqspf_gap': arbitration.get('rqspf_gap'),
            'compatible_spf_directions': arbitration.get('compatible_spf_directions'),
        }
        rqspf['full_time_arbitration'] = {
            **arbitration,
            'applied_to_spf': True,
        }
        spf.setdefault('axis_context', {})['usable_for_derived'] = True
        spf.setdefault('axis_context', {})['trusted'] = True
        spf.setdefault('axis_context', {})['reason'] = 'rqspf_arbitrated_spf_axis'

    def spf_full_code() -> Optional[str]:
        if not spf_axis_trusted():
            return None
        spf = plays.get('spf') if isinstance(plays.get('spf'), dict) else {}
        return {'3': 'h', '1': 'd', '0': 'a'}.get(str(spf.get('direction') or ''))

    def rqspf_implied_full_code() -> Optional[str]:
        rqspf = plays.get('rqspf') if isinstance(plays.get('rqspf'), dict) else {}
        direction = str(rqspf.get('direction') or '')
        try:
            handicap = float(rqspf.get('handicap') or 0)
        except (TypeError, ValueError):
            handicap = 0.0
        if handicap > 0 and direction in {'3', '1'}:
            # Home gives goals and still covers/draws the handicap: full-time
            # must be a home win.
            return 'h'
        if handicap < 0 and direction in {'0', '1'}:
            # Home receives goals yet loses/draws the handicap: full-time must
            # be an away win.
            return 'a'
        return None

    def rqspf_compatible_full_codes() -> set:
        rqspf = plays.get('rqspf') if isinstance(plays.get('rqspf'), dict) else {}
        direction = str(rqspf.get('direction') or '')
        try:
            handicap = float(rqspf.get('handicap') or 0)
        except (TypeError, ValueError):
            handicap = 0.0
        codes = _spf_codes_possible_under_rqspf(handicap, direction)
        return {
            {'3': 'h', '1': 'd', '0': 'a'}.get(code)
            for code in codes
            if {'3': 'h', '1': 'd', '0': 'a'}.get(code)
        }

    apply_spf_arbitration_from_rqspf()
    spf_target = spf_full_code()
    rqspf = plays.get('rqspf') if isinstance(plays.get('rqspf'), dict) else {}
    if rqspf and spf_target:
        rqspf_direction = str(rqspf.get('direction') or '')
        try:
            handicap = float(rqspf.get('handicap') or 0)
        except (TypeError, ValueError):
            handicap = 0.0
        adjusted_direction = None
        adjustment_reason = ''
        if handicap > 0 and spf_target != 'h' and rqspf_direction in {'3', '1'}:
            adjusted_direction = '0'
            adjustment_reason = 'spf_axis_blocks_home_cover'
        elif handicap < 0 and spf_target != 'a' and rqspf_direction in {'0', '1'}:
            adjusted_direction = '3'
            adjustment_reason = 'spf_axis_blocks_away_cover'
        if adjusted_direction and adjusted_direction != rqspf_direction:
            probs = rqspf.get('probabilities') if isinstance(rqspf.get('probabilities'), dict) else {}
            rqspf['direction'] = adjusted_direction
            rqspf['recommendation'] = adjusted_direction
            rqspf['recommendation_cn'] = rqspf_cn.get(adjusted_direction, '')
            rqspf['direction_cn'] = {'3': 'home_win', '1': 'draw', '0': 'away_win'}.get(adjusted_direction, '')
            rqspf['consistency_adjustment'] = {
                'from': rqspf_direction,
                'from_cn': rqspf_cn.get(rqspf_direction, ''),
                'to': adjusted_direction,
                'to_cn': rqspf_cn.get(adjusted_direction, ''),
                'reason': adjustment_reason,
                'spf_full_time': spf_target,
                'selected_probability': round(float(probs.get(adjusted_direction) or 0), 4),
            }
        rqspf_direction = str(rqspf.get('direction') or '')
        spf_direction = {'h': '3', 'd': '1', 'a': '0'}.get(spf_target)
        if (
            spf_direction in {'3', '1', '0'}
            and rqspf_direction in {'3', '1', '0'}
            and not _rqspf_direction_possible_under_spf(handicap, rqspf_direction, spf_direction)
        ):
            probs = rqspf.get('probabilities') if isinstance(rqspf.get('probabilities'), dict) else {}
            compatible = [
                code for code in ('3', '1', '0')
                if _rqspf_direction_possible_under_spf(handicap, code, spf_direction)
            ]
            if compatible:
                adjusted_direction = max(compatible, key=lambda code: float(probs.get(code) or 0.0))
                if adjusted_direction != rqspf_direction:
                    rqspf['direction'] = adjusted_direction
                    rqspf['recommendation'] = adjusted_direction
                    rqspf['recommendation_cn'] = rqspf_cn.get(adjusted_direction, '')
                    rqspf['direction_cn'] = {'3': 'home_win', '1': 'draw', '0': 'away_win'}.get(adjusted_direction, '')
                    rqspf['margin_requirement'] = _rqspf_margin_requirement(handicap, adjusted_direction)
                    rqspf['consistency_adjustment'] = {
                        'from': rqspf_direction,
                        'from_cn': rqspf_cn.get(rqspf_direction, ''),
                        'to': adjusted_direction,
                        'to_cn': rqspf_cn.get(adjusted_direction, ''),
                        'reason': 'rqspf_impossible_under_spf_axis',
                        'spf_direction': spf_direction,
                        'spf_direction_cn': spf_cn.get(spf_direction, ''),
                        'compatible_directions': compatible,
                        'selected_probability': round(float(probs.get(adjusted_direction) or 0), 4),
                    }

    target = rqspf_implied_full_code()
    target_reason = 'rqspf_condition'
    current = str(bqc.get('recommendation') or '')
    if not target and current and len(current) == 2:
        compatible_full_codes = rqspf_compatible_full_codes()
        if compatible_full_codes and current[1] not in compatible_full_codes:
            probs = bqc.get('probabilities') or {}
            candidates = {
                key: float(value)
                for key, value in probs.items()
                if isinstance(key, str)
                and len(key) == 2
                and key[1] in compatible_full_codes
                and isinstance(value, (int, float))
            }
            if candidates:
                new_rec = max(candidates, key=candidates.get)
                bqc['recommendation'] = new_rec
                bqc['recommendation_cn'] = bqc_cn.get(new_rec, '')
                bqc['consistency_adjustment'] = {
                    'from': current,
                    'from_cn': bqc_cn.get(current, ''),
                    'to': new_rec,
                    'to_cn': bqc_cn.get(new_rec, ''),
                    'reason': 'rqspf_full_time_compatibility',
                    'compatible_full_time': sorted(compatible_full_codes),
                    'selected_probability': round(candidates[new_rec], 4),
                }
                rqspf = plays.get('rqspf') if isinstance(plays.get('rqspf'), dict) else {}
                if isinstance(rqspf, dict):
                    rqspf['compatible_full_time'] = sorted(compatible_full_codes)
                return
    if not target:
        target = spf_target
        target_reason = 'spf_axis'

    if not target or len(current) != 2 or current[1] == target:
        return

    probs = bqc.get('probabilities') or {}
    candidates = {
        key: float(value)
        for key, value in probs.items()
        if isinstance(key, str)
        and len(key) == 2
        and key[1] == target
        and isinstance(value, (int, float))
    }
    if not candidates:
        return

    new_rec = max(candidates, key=candidates.get)
    bqc['recommendation'] = new_rec
    bqc['recommendation_cn'] = bqc_cn.get(new_rec, '')
    bqc['consistency_adjustment'] = {
        'from': current,
        'from_cn': bqc_cn.get(current, ''),
        'to': new_rec,
        'to_cn': bqc_cn.get(new_rec, ''),
        'reason': target_reason,
        'required_full_time': target,
        'selected_probability': round(candidates[new_rec], 4),
    }

    rqspf = plays.get('rqspf') if isinstance(plays.get('rqspf'), dict) else {}
    if target_reason == 'rqspf_condition' and isinstance(rqspf, dict):
        rqspf['implied_full_time'] = target
    if target_reason == 'rqspf_condition' and spf_target and spf_target != target and isinstance(rqspf, dict):
        rqspf['consistency_warning'] = {
            'type': 'rqspf_spf_axis_conflict',
            'spf_full_time': spf_target,
            'rqspf_required_full_time': target,
        }


def _apply_play_risk_profiles(plays: dict, result: dict, score_matrix=None) -> None:
    axes = _primary_play_axes(plays, result, score_matrix)
    plays['derivation_axes'] = axes
    if isinstance(plays.get('ou'), dict):
        plays['ou']['diagnostics'] = _build_ou_diagnostics(plays['ou'], axes)
        plays['ou']['goal_axis'] = _build_goal_axis(plays['ou'], axes, result)
        axes['ou_diagnostics'] = plays['ou']['diagnostics']
        axes['goal_axis'] = plays['ou']['goal_axis']
        plays['derivation_axes'] = axes
    for play_type in ('spf', 'rqspf', 'ou', 'bqc'):
        prediction = plays.get(play_type)
        if isinstance(prediction, dict):
            prediction['risk_profile'] = _play_risk_profile(play_type, prediction, result)
            prediction['derivation'] = _play_derivation(play_type, axes, prediction)
    top_scores = plays.get('top3_scores')
    if isinstance(top_scores, list):
        for score in top_scores:
            if isinstance(score, dict):
                score['risk_profile'] = {
                    'category': 'high_variance',
                    'risk_level': 'very_high',
                    'risk_label': '比分高波动',
                    'risk_note': '比分是比分矩阵里的最可能点位，但单点命中率天然很低，应只作为进球分布参考。',
                    'top_probability': score.get('probability'),
                    'recommended_usage': 'watch_only',
                }
                score['derivation'] = _play_derivation('bf', axes, score)


def _normalize_matrix(score_matrix) -> list:
    """将score_matrix转为0-1概率矩阵

    score_matrix可能是百分比(总和≈100)或小数(总和≈1)
    """
    total = sum(sum(row) for row in score_matrix)
    if total > 1.5:  # 百分比格式
        return [[v / 100.0 for v in row] for row in score_matrix]
    return score_matrix  # 已经是小数


def _matrix_expected_goals(score_matrix) -> dict:
    if not score_matrix:
        return {}
    norm = _normalize_matrix(score_matrix)
    home_xg = 0.0
    away_xg = 0.0
    total = 0.0
    for home_goals, row in enumerate(norm):
        for away_goals, prob in enumerate(row):
            try:
                p = float(prob or 0)
            except (TypeError, ValueError):
                p = 0.0
            home_xg += home_goals * p
            away_xg += away_goals * p
            total += p
    if total <= 0:
        return {}
    return {'home': home_xg / total, 'away': away_xg / total}


def _matrix_spf_distribution(score_matrix) -> dict:
    if not score_matrix:
        return {}
    norm = _normalize_matrix(score_matrix)
    dist = {'home_win': 0.0, 'draw': 0.0, 'away_win': 0.0}
    for home_goals, row in enumerate(norm):
        for away_goals, prob in enumerate(row):
            try:
                p = float(prob or 0)
            except (TypeError, ValueError):
                p = 0.0
            if home_goals > away_goals:
                dist['home_win'] += p
            elif home_goals == away_goals:
                dist['draw'] += p
            else:
                dist['away_win'] += p
    return _normalize_probs(dist)


def _poisson_score_matrix_from_expected(home_xg: float, away_xg: float, max_goals: int = 9) -> list:
    import math

    home_xg = max(0.05, min(float(home_xg), 7.5))
    away_xg = max(0.05, min(float(away_xg), 7.5))
    matrix = []
    for home_goals in range(max_goals + 1):
        row = []
        home_prob = math.exp(-home_xg) * home_xg ** home_goals / math.factorial(home_goals)
        for away_goals in range(max_goals + 1):
            away_prob = math.exp(-away_xg) * away_xg ** away_goals / math.factorial(away_goals)
            row.append(home_prob * away_prob)
        matrix.append(row)
    total = sum(sum(row) for row in matrix)
    if total > 0:
        matrix = [[value / total for value in row] for row in matrix]
    return matrix


def _align_score_matrix_to_spf(score_matrix, target_probs: dict) -> tuple:
    """Reweight score cells so the matrix matches final SPF probabilities."""
    if not score_matrix or not isinstance(target_probs, dict):
        return score_matrix, {}
    norm = _normalize_matrix(score_matrix)
    current = _matrix_spf_distribution(norm)
    target = _normalize_probs(target_probs)
    ratios = {}
    for key in PROB_KEYS:
        base = float(current.get(key) or 0)
        ratios[key] = (float(target.get(key) or 0) / base) if base > 1e-9 else 1.0

    adjusted = []
    for home_goals, row in enumerate(norm):
        new_row = []
        for away_goals, prob in enumerate(row):
            if home_goals > away_goals:
                outcome = 'home_win'
            elif home_goals == away_goals:
                outcome = 'draw'
            else:
                outcome = 'away_win'
            new_row.append(float(prob or 0) * ratios.get(outcome, 1.0))
        adjusted.append(new_row)

    total = sum(sum(row) for row in adjusted)
    if total > 0:
        adjusted = [[value / total for value in row] for row in adjusted]
    aligned = _matrix_spf_distribution(adjusted)
    meta = {
        'method': 'score_matrix_spf_reweight',
        'applied': True,
        'before_spf': {key: round(current.get(key, 0.0), 4) for key in PROB_KEYS},
        'target_spf': {key: round(target.get(key, 0.0), 4) for key in PROB_KEYS},
        'after_spf': {key: round(aligned.get(key, 0.0), 4) for key in PROB_KEYS},
    }
    return adjusted, meta


def _prepare_joint_score_matrix(result: dict, score_matrix) -> tuple:
    """Build one matrix for SPF, handicap, O/U, BQC and score candidates."""
    fp = (result or {}).get('final_prediction') or {}
    expected = fp.get('expected_score') or {}
    target_probs = fp.get('probabilities') or {}
    goal_profile_adjustment = (result or {}).get('goal_profile_adjustment') or {}
    force_expected_rebuild = bool(goal_profile_adjustment.get('applied'))
    matrix = score_matrix
    meta = {
        'method': 'raw_score_matrix',
        'applied': False,
    }

    expected_home = _to_float(expected.get('home'), None) if isinstance(expected, dict) else None
    expected_away = _to_float(expected.get('away'), None) if isinstance(expected, dict) else None
    raw_expected = _matrix_expected_goals(matrix) if matrix else {}
    should_rebuild = False
    if expected_home is not None and expected_away is not None:
        if force_expected_rebuild:
            should_rebuild = True
        elif not matrix:
            should_rebuild = True
        elif raw_expected:
            drift = abs(raw_expected.get('home', 0.0) - expected_home) + abs(raw_expected.get('away', 0.0) - expected_away)
            should_rebuild = drift >= 0.65
        if should_rebuild:
            matrix = _poisson_score_matrix_from_expected(expected_home, expected_away)
            meta = {
                'method': 'profile_expected_score_poisson_rebuild' if force_expected_rebuild else 'expected_score_poisson_rebuild',
                'applied': True,
                'expected_score': {'home': round(expected_home, 3), 'away': round(expected_away, 3)},
                'raw_expected_score': {
                    'home': round(raw_expected.get('home', 0.0), 3),
                    'away': round(raw_expected.get('away', 0.0), 3),
                } if raw_expected else None,
                'goal_profile_adjustment': goal_profile_adjustment if force_expected_rebuild else None,
            }

    matrix, align_meta = _align_score_matrix_to_spf(matrix, target_probs)
    if align_meta:
        meta = {**meta, 'applied': True, 'spf_alignment': align_meta}
    return matrix, meta if meta.get('applied') else {}


def _score_matches_spf(home_goals: int, away_goals: int, spf_direction: Optional[str]) -> bool:
    if spf_direction == '3':
        return home_goals > away_goals
    if spf_direction == '1':
        return home_goals == away_goals
    if spf_direction == '0':
        return home_goals < away_goals
    return True


def _score_matches_ou(home_goals: int, away_goals: int, ou_prediction: Optional[dict]) -> bool:
    if not isinstance(ou_prediction, dict):
        return True
    side = _ou_side_from_recommendation(ou_prediction.get('recommendation'))
    raw_line = ou_prediction.get('best_line') or ou_prediction.get('line')
    try:
        line = float(raw_line)
    except (TypeError, ValueError):
        return True
    total_goals = home_goals + away_goals
    if side == 'over':
        return total_goals > line
    if side == 'under':
        return total_goals < line
    return True


def _score_matches_rqspf(home_goals: int, away_goals: int, rqspf_prediction: Optional[dict]) -> bool:
    if not isinstance(rqspf_prediction, dict):
        return True
    direction = str(rqspf_prediction.get('direction') or '')
    if direction not in {'3', '1', '0'}:
        return True
    try:
        handicap = float(rqspf_prediction.get('handicap') or 0)
    except (TypeError, ValueError):
        return True
    return _rqspf_code_for_score(home_goals, away_goals, handicap) == direction


def _rqspf_top_score_cells(score_matrix, rqspf_prediction: Optional[dict], limit: int = 5) -> List[dict]:
    """Return the highest-probability exact scores under the current RQSPF path."""
    if not score_matrix or not isinstance(rqspf_prediction, dict):
        return []
    direction = str(rqspf_prediction.get('direction') or '')
    if direction not in {'3', '1', '0'}:
        return []

    matches = []
    for home_goals, row in enumerate(_normalize_matrix(score_matrix)):
        for away_goals, raw_prob in enumerate(row):
            try:
                prob = float(raw_prob or 0.0)
            except (TypeError, ValueError):
                prob = 0.0
            if prob <= 0:
                continue
            if not _score_matches_rqspf(home_goals, away_goals, rqspf_prediction):
                continue
            matches.append({
                'score': f'{home_goals}-{away_goals}',
                'probability': round(prob, 4),
                'home_goals': home_goals,
                'away_goals': away_goals,
            })
    matches.sort(
        key=lambda item: (
            float(item.get('probability') or 0.0),
            int(item.get('home_goals') or 0) + int(item.get('away_goals') or 0),
        ),
        reverse=True,
    )
    return matches[:max(int(limit or 0), 0)]


def _parse_score_text(score: Any) -> Optional[tuple]:
    text = str(score or '').strip().replace(':', '-')
    if '-' not in text:
        return None
    left, right = text.split('-', 1)
    try:
        return int(left), int(right)
    except (TypeError, ValueError):
        return None


def _score_probability_lookup(score_matrix) -> Dict[tuple, float]:
    lookup: Dict[tuple, float] = {}
    if not score_matrix:
        return lookup
    for home_goals, row in enumerate(_normalize_matrix(score_matrix)):
        for away_goals, raw_prob in enumerate(row):
            try:
                lookup[(home_goals, away_goals)] = float(raw_prob or 0)
            except (TypeError, ValueError):
                lookup[(home_goals, away_goals)] = 0.0
    return lookup


def _add_score_target(targets: Dict[tuple, str], home_goals: int, away_goals: int, reason: str) -> None:
    if home_goals < 0 or away_goals < 0:
        return
    key = (int(home_goals), int(away_goals))
    if key not in targets:
        targets[key] = reason


def _structural_score_targets(plays: dict, score_matrix) -> Dict[tuple, str]:
    targets: Dict[tuple, str] = {}
    spf = plays.get('spf') if isinstance(plays.get('spf'), dict) else {}
    rqspf = plays.get('rqspf') if isinstance(plays.get('rqspf'), dict) else {}
    ou = plays.get('ou') if isinstance(plays.get('ou'), dict) else {}
    direction = str(spf.get('direction') or '')
    side = _ou_side_from_recommendation(ou.get('recommendation'))
    line = _to_float(ou.get('best_line') or ou.get('line'), None)
    conditions = _score_matrix_conditions(score_matrix, line)
    btts = _to_float(conditions.get('both_teams_score_probability'), None)
    home_goal = _to_float(conditions.get('home_goal_probability'), None)
    away_goal = _to_float(conditions.get('away_goal_probability'), None)
    matrix_xg = _matrix_expected_goals(score_matrix)
    total_xg = None
    if matrix_xg:
        total_xg = float(matrix_xg.get('home') or 0) + float(matrix_xg.get('away') or 0)

    low_goal = side == 'under' or (line is not None and total_xg is not None and total_xg <= line + 0.20)
    high_goal = side == 'over' or (line is not None and total_xg is not None and total_xg >= line + 0.35)
    one_sided_home = direction == '3' and isinstance(away_goal, (int, float)) and away_goal < 0.46
    one_sided_away = direction == '0' and isinstance(home_goal, (int, float)) and home_goal < 0.46

    if direction == '3':
        if low_goal:
            for score in ((1, 0), (2, 0), (2, 1)):
                _add_score_target(targets, *score, reason='favorite_under_shape')
        if high_goal:
            for score in ((2, 1), (3, 0), (3, 1), (4, 1)):
                _add_score_target(targets, *score, reason='favorite_over_tail_shape')
            if (
                isinstance(btts, (int, float))
                and isinstance(away_goal, (int, float))
                and btts >= 0.58
                and away_goal >= 0.60
            ):
                for score in ((3, 2), (4, 2)):
                    _add_score_target(targets, *score, reason='favorite_over_btts_tail_shape')
        if one_sided_home:
            for score in ((2, 0), (3, 0), (4, 0)):
                _add_score_target(targets, *score, reason='one_sided_home_goal_shape')
            if high_goal and isinstance(home_goal, (int, float)) and home_goal >= 0.82:
                _add_score_target(targets, 5, 0, reason='one_sided_home_blowout_shape')
    elif direction == '0':
        if low_goal:
            for score in ((0, 1), (0, 2), (1, 2)):
                _add_score_target(targets, *score, reason='away_favorite_under_shape')
        if high_goal:
            for score in ((1, 2), (0, 3), (1, 3), (1, 4)):
                _add_score_target(targets, *score, reason='away_favorite_over_tail_shape')
            if (
                isinstance(btts, (int, float))
                and isinstance(home_goal, (int, float))
                and btts >= 0.58
                and home_goal >= 0.60
            ):
                for score in ((2, 3), (2, 4)):
                    _add_score_target(targets, *score, reason='away_favorite_over_btts_tail_shape')
        if one_sided_away:
            for score in ((0, 2), (0, 3), (0, 4)):
                _add_score_target(targets, *score, reason='one_sided_away_goal_shape')
            if high_goal and isinstance(away_goal, (int, float)) and away_goal >= 0.82:
                _add_score_target(targets, 0, 5, reason='one_sided_away_blowout_shape')
    elif direction == '1':
        if high_goal or (isinstance(btts, (int, float)) and btts >= 0.55):
            for score in ((1, 1), (2, 2)):
                _add_score_target(targets, *score, reason='draw_btts_shape')
        else:
            for score in ((0, 0), (1, 1)):
                _add_score_target(targets, *score, reason='draw_low_tempo_shape')

    market_anchor = spf.get('market_anchor') if isinstance(spf.get('market_anchor'), dict) else {}
    if market_anchor.get('applied'):
        before_anchor = market_anchor.get('before_probabilities') if isinstance(market_anchor.get('before_probabilities'), dict) else {}
        after_anchor = market_anchor.get('after_probabilities') if isinstance(market_anchor.get('after_probabilities'), dict) else {}
        draw_support = max(
            _to_float(before_anchor.get('draw'), 0.0) or 0.0,
            _to_float(after_anchor.get('draw'), 0.0) or 0.0,
        )
        if draw_support >= _env_float('FOOTBALL_SCORE_MARKET_ANCHOR_DRAW_MIN', 0.25, 0.0, 1.0):
            if low_goal or (line is not None and float(line) <= 2.5):
                for score in ((1, 1), (0, 0)):
                    _add_score_target(targets, *score, reason='market_anchor_draw_safety')
            elif isinstance(btts, (int, float)) and btts >= 0.52:
                for score in ((1, 1), (2, 2)):
                    _add_score_target(targets, *score, reason='market_anchor_draw_safety')

    try:
        handicap = float(rqspf.get('handicap') or 0)
    except (TypeError, ValueError):
        handicap = 0.0
    rqspf_direction = str(rqspf.get('direction') or '')
    if abs(handicap) > 0 and rqspf_direction in {'3', '1', '0'}:
        h_abs = int(abs(handicap)) if float(abs(handicap)).is_integer() else max(1, int(abs(handicap)))
        if handicap > 0 and direction == '3':
            if float(abs(handicap)).is_integer():
                _add_score_target(targets, h_abs, 0, 'integer_handicap_boundary_margin')
                _add_score_target(targets, h_abs + 1, 0, 'integer_handicap_cover_tail')
                if high_goal or one_sided_home:
                    _add_score_target(targets, h_abs + 2, 0, 'integer_handicap_blowout_tail')
                if isinstance(btts, (int, float)) and btts >= 0.52:
                    _add_score_target(targets, h_abs + 1, 1, 'integer_handicap_btts_tail')
            if rqspf_direction == '3':
                _add_score_target(targets, h_abs + 1, 0, 'handicap_cover_margin')
                _add_score_target(targets, h_abs + 2, 1, 'handicap_cover_margin')
            elif rqspf_direction == '1':
                _add_score_target(targets, h_abs, 0, 'handicap_push_margin')
                _add_score_target(targets, h_abs + 1, 1, 'handicap_push_margin')
            elif not float(abs(handicap)).is_integer():
                _add_score_target(targets, max(1, h_abs - 1), 0, 'handicap_miss_margin')
                _add_score_target(targets, h_abs, 1, 'handicap_miss_margin')
        elif handicap < 0 and direction == '0':
            if float(abs(handicap)).is_integer():
                _add_score_target(targets, 0, h_abs, 'integer_handicap_boundary_margin')
                _add_score_target(targets, 0, h_abs + 1, 'integer_handicap_cover_tail')
                if high_goal or one_sided_away:
                    _add_score_target(targets, 0, h_abs + 2, 'integer_handicap_blowout_tail')
                if isinstance(btts, (int, float)) and btts >= 0.52:
                    _add_score_target(targets, 1, h_abs + 1, 'integer_handicap_btts_tail')
            if rqspf_direction == '0':
                _add_score_target(targets, 0, h_abs + 1, 'handicap_cover_margin')
                _add_score_target(targets, 1, h_abs + 2, 'handicap_cover_margin')
            elif rqspf_direction == '1':
                _add_score_target(targets, 0, h_abs, 'handicap_push_margin')
                _add_score_target(targets, 1, h_abs + 1, 'handicap_push_margin')
            elif not float(abs(handicap)).is_integer():
                _add_score_target(targets, 0, max(1, h_abs - 1), 'handicap_miss_margin')
                _add_score_target(targets, 1, h_abs, 'handicap_miss_margin')
    return targets


def _enhance_score_candidates(score_matrix, plays: dict, limit: int = 3) -> list:
    if not score_matrix:
        return plays.get('top3_scores') if isinstance(plays.get('top3_scores'), list) else []
    spf = plays.get('spf') if isinstance(plays.get('spf'), dict) else {}
    ou = plays.get('ou') if isinstance(plays.get('ou'), dict) else {}
    rqspf = plays.get('rqspf') if isinstance(plays.get('rqspf'), dict) else {}
    spf_direction = spf.get('direction')
    structural_targets = _structural_score_targets(plays, score_matrix)
    probabilities = _score_probability_lookup(score_matrix)
    top_probability = max(probabilities.values(), default=0.0)
    min_structural_prob = max(0.006, top_probability * 0.25)
    rqspf_top_cells = _rqspf_top_score_cells(score_matrix, rqspf, limit=6)
    rqspf_focus_scores = {
        str(item.get('score'))
        for item in rqspf_top_cells
        if isinstance(item, dict) and item.get('score')
    }

    candidates = []
    for (home_goals, away_goals), prob in probabilities.items():
        if prob <= 0:
            continue
        score_key = f'{home_goals}-{away_goals}'
        axis_spf = _score_matches_spf(home_goals, away_goals, spf_direction)
        axis_ou = _score_matches_ou(home_goals, away_goals, ou)
        axis_rqspf = _score_matches_rqspf(home_goals, away_goals, rqspf)
        target_reason = structural_targets.get((home_goals, away_goals))
        adjusted = prob
        reasons = ['matrix_probability']
        if axis_spf:
            adjusted += 0.010
            reasons.append('spf_axis')
        if axis_ou:
            adjusted += 0.008
            reasons.append('ou_axis')
        if axis_rqspf:
            adjusted += 0.006
            reasons.append('rqspf_axis')
        if score_key in rqspf_focus_scores:
            adjusted += 0.010
            reasons.append('rqspf_margin_path')
        if target_reason and prob >= min_structural_prob:
            adjusted += max(0.006, min(0.025, prob * 0.55 + 0.004))
            reasons.append(target_reason)
        elif target_reason:
            reasons.append(f'{target_reason}_low_probability')

        candidates.append({
            'score': score_key,
            'probability': round(prob, 3),
            'home_goals': home_goals,
            'away_goals': away_goals,
            'adjusted_probability': round(adjusted, 4),
            'candidate_reasons': reasons[:7],
            'candidate_source': 'matrix_axis_structural' if target_reason and prob >= min_structural_prob else 'matrix_axis',
            'axis_match': {
                'spf': axis_spf,
                'ou': axis_ou,
                'rqspf': axis_rqspf,
            },
        })

    candidates.sort(
        key=lambda item: (
            item.get('adjusted_probability', 0),
            item.get('probability', 0),
        ),
        reverse=True,
    )
    ou_side = _ou_side_from_recommendation(ou.get('recommendation'))
    ou_line = _to_float(ou.get('best_line') or ou.get('line'), None)
    if ou_side in {'over', 'under'} and ou_line is not None:
        opposite = 'under' if ou_side == 'over' else 'over'

        def candidate_total_side(item: dict) -> str:
            total_goals = int(item.get('home_goals') or 0) + int(item.get('away_goals') or 0)
            if total_goals > float(ou_line):
                return 'over'
            if total_goals < float(ou_line):
                return 'under'
            return 'push'

        min_ou_prob = max(0.004, top_probability * 0.15)
        coherent = [
            item for item in candidates
            if candidate_total_side(item) != opposite
            and float(item.get('probability') or 0) >= min_ou_prob
        ]
        if len(coherent) >= 2:
            preferred_scores = {item.get('score') for item in coherent[:2]}
            front = [item for item in candidates if item.get('score') in preferred_scores]
            tail = [item for item in candidates if item.get('score') not in preferred_scores]
            candidates = front + tail

    selected = []
    seen = set()
    for item in candidates:
        score = item.get('score')
        if not score or score in seen:
            continue
        seen.add(score)
        selected.append(item)
        if len(selected) >= limit:
            break
    selected = _promote_score_axis_coherence(selected, candidates, top_probability, limit)
    selected = _protect_score_boundary_candidates(selected, candidates, spf_direction, top_probability, limit)
    selected = _protect_score_tail_candidates(selected, candidates, top_probability, limit)
    selected = _protect_rqspf_margin_candidates(selected, candidates, rqspf_top_cells, top_probability, limit)
    selected = _prioritize_score_display_axis(selected, limit)
    return selected


def _protect_score_boundary_candidates(selected: list, candidates: list, spf_direction: Any, top_probability: float, limit: int) -> list:
    """Keep high-probability boundary scores inside the displayed top three.

    Structural boosts are useful for explaining a main betting axis, but a score
    recommendation must still respect the raw score matrix. This guard protects
    common boundary cells such as 1-1 on a draw/under axis and 1-0 or 0-1 on a
    narrow-win axis when their raw probability is close enough to the displayed
    tail candidate.
    """
    if not selected or not candidates or limit <= 0:
        return selected

    def prob(item: dict) -> float:
        try:
            return float(item.get('probability') or 0.0)
        except (TypeError, ValueError):
            return 0.0

    def goals(item: dict) -> tuple[int, int]:
        try:
            return int(item.get('home_goals') or 0), int(item.get('away_goals') or 0)
        except (TypeError, ValueError):
            return (0, 0)

    protected: List[dict] = []
    min_draw_prob = max(0.015, float(top_probability or 0.0) * 0.18)
    min_narrow_prob = max(0.015, float(top_probability or 0.0) * 0.45)

    if str(spf_direction) == '1':
        draw_cells = [
            item for item in candidates
            if goals(item)[0] == goals(item)[1]
            and goals(item)[0] <= 2
            and prob(item) >= min_draw_prob
        ]
        draw_cells.sort(key=prob, reverse=True)
        protected.extend(draw_cells[:2])
    elif str(spf_direction) in {'3', '0'}:
        expected_diff = 1 if str(spf_direction) == '3' else -1
        narrow_cells = [
            item for item in candidates
            if goals(item)[0] - goals(item)[1] == expected_diff
            and prob(item) >= min_narrow_prob
        ]
        narrow_cells.sort(key=prob, reverse=True)
        protected.extend(narrow_cells[:1])

    if not protected:
        return selected

    result = list(selected[:limit])
    selected_scores = {item.get('score') for item in result}
    for item in protected:
        score = item.get('score')
        if not score or score in selected_scores:
            continue
        tail_index = len(result) - 1
        tail = result[tail_index]
        if prob(item) < prob(tail) * 0.70:
            continue
        guarded = dict(item)
        reasons = list(guarded.get('candidate_reasons') or [])
        if 'score_probability_guard' not in reasons:
            reasons.append('score_probability_guard')
        guarded['candidate_reasons'] = reasons[:6]
        guarded['candidate_source'] = guarded.get('candidate_source') or 'matrix_probability_guard'
        guarded['boundary_guard'] = {
            'applied': True,
            'replaced_score': tail.get('score'),
            'protected_probability': round(prob(item), 4),
            'replaced_probability': round(prob(tail), 4),
            'min_tail_ratio': 0.70,
        }
        selected_scores.discard(tail.get('score'))
        result[tail_index] = guarded
        selected_scores.add(score)
    return result


def _promote_score_axis_coherence(selected: list, candidates: list, top_probability: float, limit: int) -> list:
    """Prefer score cells that do not visibly contradict the main betting axes.

    Raw Poisson peaks like 1-1 can dominate the matrix even when SPF and O/U
    both point elsewhere. Keep the matrix truth, but do not let a zero-axis
    score crowd out a nearby candidate that matches two or more active axes.
    """
    if not selected or not candidates or limit <= 0:
        return selected

    def prob(item: dict) -> float:
        try:
            return float(item.get('probability') or 0.0)
        except (TypeError, ValueError):
            return 0.0

    def adjusted(item: dict) -> float:
        try:
            return float(item.get('adjusted_probability') or prob(item))
        except (TypeError, ValueError):
            return prob(item)

    def axis(item: dict) -> dict:
        value = item.get('axis_match') if isinstance(item.get('axis_match'), dict) else {}
        return {
            'spf': bool(value.get('spf')),
            'ou': bool(value.get('ou')),
            'rqspf': bool(value.get('rqspf')),
        }

    def axis_count(item: dict) -> int:
        values = axis(item)
        return sum(1 for key in ('spf', 'ou', 'rqspf') if values.get(key))

    result = list(selected[:limit])
    weak_slots = []
    for index, item in enumerate(result):
        item_axis = axis(item)
        item_axis_count = axis_count(item)
        if item_axis_count == 0:
            weak_slots.append((index, 'zero_axis'))
        elif item_axis_count == 1 and not item_axis.get('spf'):
            weak_slots.append((index, 'non_spf_single_axis'))
    if not weak_slots:
        return selected

    selected_scores = {item.get('score') for item in result if isinstance(item, dict)}
    min_candidate_prob = max(0.01, float(top_probability or 0.0) * 0.20)
    eligible = [
        item for item in candidates
        if isinstance(item, dict)
        and item.get('score')
        and item.get('score') not in selected_scores
        and axis_count(item) >= 2
        and prob(item) >= min_candidate_prob
    ]
    if not eligible:
        return selected

    eligible.sort(
        key=lambda item: (
            axis_count(item),
            adjusted(item),
            prob(item),
        ),
        reverse=True,
    )

    used_scores = set(selected_scores)
    for replace_index, weak_reason in weak_slots:
        replace_item = result[replace_index]
        replacement = None
        for item in eligible:
            score = item.get('score')
            if not score or score in used_scores:
                continue
            min_prob_ratio = 0.42 if weak_reason == 'zero_axis' else 0.55
            min_adjusted_ratio = 0.70 if weak_reason == 'zero_axis' else 0.82
            if (
                prob(item) < prob(replace_item) * min_prob_ratio
                and adjusted(item) < adjusted(replace_item) * min_adjusted_ratio
            ):
                continue
            replacement = item
            break
        if replacement is None:
            continue

        guarded = dict(replacement)
        guarded_reasons = list(guarded.get('candidate_reasons') or [])
        if 'axis_coherence_guard' not in guarded_reasons:
            guarded_reasons.append('axis_coherence_guard')
        guarded['candidate_reasons'] = guarded_reasons[:7]
        guarded['candidate_source'] = guarded.get('candidate_source') or 'matrix_axis_coherence_guard'
        guarded['axis_coherence_guard'] = {
            'applied': True,
            'replaced_score': replace_item.get('score'),
            'replaced_probability': round(prob(replace_item), 4),
            'promoted_probability': round(prob(replacement), 4),
            'replaced_axis_count': axis_count(replace_item),
            'promoted_axis_count': axis_count(replacement),
            'weak_reason': weak_reason,
            'min_probability_ratio': round(min_prob_ratio, 4),
            'min_adjusted_ratio': round(min_adjusted_ratio, 4),
        }
        old_score = replace_item.get('score')
        if old_score:
            used_scores.discard(old_score)
        result[replace_index] = guarded
        used_scores.add(guarded.get('score'))
    return result


def _protect_rqspf_margin_candidates(selected: list, candidates: list, rqspf_top_cells: list, top_probability: float, limit: int) -> list:
    """Keep at least one displayed score tied to the chosen handicap path."""
    if not selected or not candidates or limit <= 0 or not rqspf_top_cells:
        return selected

    def prob(item: dict) -> float:
        try:
            return float(item.get('probability') or 0.0)
        except (TypeError, ValueError):
            return 0.0

    def adjusted(item: dict) -> float:
        try:
            return float(item.get('adjusted_probability') or prob(item))
        except (TypeError, ValueError):
            return prob(item)

    target_scores = {
        str(item.get('score'))
        for item in rqspf_top_cells[:4]
        if isinstance(item, dict) and item.get('score')
    }
    if not target_scores:
        return selected

    selected_scores = {item.get('score') for item in selected if isinstance(item, dict)}
    if selected_scores & target_scores:
        return selected

    eligible = [
        item for item in candidates
        if isinstance(item, dict)
        and item.get('score') in target_scores
        and bool((item.get('axis_match') or {}).get('rqspf'))
    ]
    if not eligible:
        return selected

    eligible.sort(
        key=lambda item: (
            adjusted(item),
            prob(item),
            bool((item.get('axis_match') or {}).get('spf')),
            bool((item.get('axis_match') or {}).get('ou')),
        ),
        reverse=True,
    )
    promoted = eligible[0]
    min_focus_prob = max(0.008, float(top_probability or 0.0) * 0.18)
    if prob(promoted) < min_focus_prob:
        return selected

    result = list(selected[:limit])
    replace_index = len(result) - 1
    replace_item = result[replace_index]
    if prob(promoted) < prob(replace_item) * 0.62:
        return selected

    guarded = dict(promoted)
    guarded_reasons = list(guarded.get('candidate_reasons') or [])
    if 'rqspf_margin_guard' not in guarded_reasons:
        guarded_reasons.append('rqspf_margin_guard')
    guarded['candidate_reasons'] = guarded_reasons[:7]
    guarded['candidate_source'] = guarded.get('candidate_source') or 'matrix_axis_rqspf_guard'
    guarded['rqspf_margin_guard'] = {
        'applied': True,
        'replaced_score': replace_item.get('score'),
        'promoted_probability': round(prob(promoted), 4),
        'replaced_probability': round(prob(replace_item), 4),
        'min_probability': round(min_focus_prob, 4),
        'min_tail_ratio': 0.62,
    }
    result[replace_index] = guarded
    return result


def _prioritize_score_display_axis(selected: list, limit: int) -> list:
    """Put a coherent displayed score first when it is already in the shortlist.

    The raw matrix can make 1-1 the single most likely cell while the aggregate
    SPF/O-U/RQSPF axes point to a narrow win. In that case the draw cell should
    remain visible, but the first displayed recommendation should not contradict
    the main betting axes when a close-probability coherent candidate is already
    present.
    """
    if not selected or limit <= 0:
        return selected

    def prob(item: dict) -> float:
        try:
            return float(item.get('probability') or 0.0)
        except (TypeError, ValueError):
            return 0.0

    def adjusted(item: dict) -> float:
        try:
            return float(item.get('adjusted_probability') or prob(item))
        except (TypeError, ValueError):
            return prob(item)

    def axis(item: dict) -> dict:
        value = item.get('axis_match') if isinstance(item.get('axis_match'), dict) else {}
        return {
            'spf': bool(value.get('spf')),
            'ou': bool(value.get('ou')),
            'rqspf': bool(value.get('rqspf')),
        }

    def axis_count(item: dict) -> int:
        values = axis(item)
        return sum(1 for key in ('spf', 'ou', 'rqspf') if values.get(key))

    result = [dict(item) if isinstance(item, dict) else item for item in selected[:limit]]
    if not result or not isinstance(result[0], dict):
        return selected

    first = result[0]
    first_axis = axis(first)
    first_axis_count = axis_count(first)
    if first_axis.get('spf') and first_axis_count >= 2:
        return selected

    best_index = None
    best_score = None
    for index, item in enumerate(result[1:], start=1):
        if not isinstance(item, dict):
            continue
        item_axis = axis(item)
        item_axis_count = axis_count(item)
        if not item_axis.get('spf'):
            continue
        if item_axis_count < 2 and first_axis_count > 0:
            continue
        if prob(item) < prob(first) * 0.55 and adjusted(item) < adjusted(first) * 0.72:
            continue
        rank_score = (
            item_axis_count,
            bool(item_axis.get('ou')),
            adjusted(item),
            prob(item),
        )
        if best_score is None or rank_score > best_score:
            best_score = rank_score
            best_index = index

    if best_index is None:
        return selected

    promoted = dict(result[best_index])
    reasons = list(promoted.get('candidate_reasons') or [])
    if 'score_display_axis_priority' not in reasons:
        reasons.append('score_display_axis_priority')
    promoted['candidate_reasons'] = reasons[:7]
    promoted['score_display_priority'] = {
        'applied': True,
        'reordered_from_index': best_index,
        'previous_top_score': first.get('score'),
        'previous_top_probability': round(prob(first), 4),
        'promoted_probability': round(prob(promoted), 4),
        'reason': 'display_first_score_should_follow_main_axes',
    }
    return [promoted] + [item for index, item in enumerate(result) if index != best_index]


def _protect_score_tail_candidates(selected: list, candidates: list, top_probability: float, limit: int) -> list:
    """Reserve one plausible tail score when the main axes imply tail risk.

    The first three raw Poisson cells often cluster around safe central scores.
    For lottery score validation that hides important paths such as exact
    handicap-boundary wins (3-0 on a -3 line) or blowout tails (4-0/5-1).
    This guard only promotes a tail candidate when it was explicitly introduced
    by the structural score-target rules and its raw probability is still close
    enough to the displayed tail.
    """
    if not selected or not candidates or limit <= 0:
        return selected

    def prob(item: dict) -> float:
        try:
            return float(item.get('probability') or 0.0)
        except (TypeError, ValueError):
            return 0.0

    def adjusted(item: dict) -> float:
        try:
            return float(item.get('adjusted_probability') or prob(item))
        except (TypeError, ValueError):
            return prob(item)

    def goals(item: dict) -> tuple[int, int]:
        try:
            return int(item.get('home_goals') or 0), int(item.get('away_goals') or 0)
        except (TypeError, ValueError):
            return (0, 0)

    def reasons(item: dict) -> set:
        values = item.get('candidate_reasons') or []
        return {str(value) for value in values if value}

    selected_scores = {item.get('score') for item in selected}
    btts_tail_reasons = {
        'favorite_over_btts_tail_shape',
        'away_favorite_over_btts_tail_shape',
    }
    selected_has_btts_tail = any(
        reasons(item) & btts_tail_reasons
        for item in selected
        if isinstance(item, dict)
    )
    if any(
        (goals(item)[0] + goals(item)[1] >= 4 or abs(goals(item)[0] - goals(item)[1]) >= 3)
        and reasons(item) & {
            'favorite_over_tail_shape',
            'favorite_over_btts_tail_shape',
            'away_favorite_over_tail_shape',
            'away_favorite_over_btts_tail_shape',
            'integer_handicap_cover_tail',
            'integer_handicap_blowout_tail',
            'integer_handicap_btts_tail',
            'one_sided_home_goal_shape',
            'one_sided_home_blowout_shape',
            'one_sided_away_goal_shape',
            'one_sided_away_blowout_shape',
        }
        for item in selected
        if isinstance(item, dict)
    ) and selected_has_btts_tail:
        return selected

    tail_reasons = {
        'favorite_over_tail_shape',
        'favorite_over_btts_tail_shape',
        'away_favorite_over_tail_shape',
        'away_favorite_over_btts_tail_shape',
        'integer_handicap_cover_tail',
        'integer_handicap_blowout_tail',
        'integer_handicap_btts_tail',
        'integer_handicap_boundary_margin',
        'handicap_cover_margin',
        'handicap_push_margin',
        'one_sided_home_goal_shape',
        'one_sided_home_blowout_shape',
        'one_sided_away_goal_shape',
        'one_sided_away_blowout_shape',
    }
    min_tail_prob = max(0.012, float(top_probability or 0.0) * 0.28)
    eligible = []
    for item in candidates:
        score = item.get('score')
        if not score or score in selected_scores:
            continue
        item_reasons = reasons(item)
        if not item_reasons & tail_reasons:
            continue
        home_goals, away_goals = goals(item)
        total_goals = home_goals + away_goals
        goal_diff = abs(home_goals - away_goals)
        if total_goals < 3 and goal_diff < 2:
            continue
        item_min_tail_prob = min_tail_prob
        if item_reasons & btts_tail_reasons:
            axis = item.get('axis_match') if isinstance(item.get('axis_match'), dict) else {}
            axis_count = sum(1 for key in ('spf', 'ou', 'rqspf') if axis.get(key))
            btts_tail_ratio = 0.20 if axis_count >= 3 else 0.22
            item_min_tail_prob = max(0.01, float(top_probability or 0.0) * btts_tail_ratio)
        if prob(item) < item_min_tail_prob:
            continue
        axis = item.get('axis_match') if isinstance(item.get('axis_match'), dict) else {}
        axis_count = sum(1 for key in ('spf', 'ou', 'rqspf') if axis.get(key))
        if axis_count < 2:
            continue
        eligible.append(item)

    if not eligible:
        return selected

    eligible.sort(
        key=lambda item: (
            adjusted(item),
            prob(item),
            goals(item)[0] + goals(item)[1],
            abs(goals(item)[0] - goals(item)[1]),
        ),
        reverse=True,
    )
    promoted = eligible[0]
    if not selected_has_btts_tail:
        btts_eligible = [
            item for item in eligible
            if reasons(item) & btts_tail_reasons
        ]
        if btts_eligible:
            btts_eligible.sort(
                key=lambda item: (
                    adjusted(item),
                    prob(item),
                    goals(item)[0] + goals(item)[1],
                    abs(goals(item)[0] - goals(item)[1]),
                ),
                reverse=True,
            )
            best_btts = btts_eligible[0]
            if (
                prob(best_btts) >= prob(promoted) * 0.45
                or adjusted(best_btts) >= adjusted(promoted) * 0.75
            ):
                promoted = best_btts
    result = list(selected[:limit])
    replace_index = len(result) - 1
    replace_item = result[replace_index]
    replace_home, replace_away = goals(replace_item)
    promoted_reasons = reasons(promoted)
    if (
        replace_home + replace_away <= 2
        and prob(replace_item) >= max(0.025, float(top_probability or 0.0) * 0.30)
        and not (promoted_reasons & btts_tail_reasons)
    ):
        return selected
    min_tail_ratio = 0.55
    if promoted_reasons & btts_tail_reasons:
        min_tail_ratio = 0.45
    elif promoted_reasons & {'one_sided_home_blowout_shape', 'one_sided_away_blowout_shape'}:
        min_tail_ratio = 0.40
    if prob(promoted) < prob(replace_item) * min_tail_ratio:
        return selected

    guarded = dict(promoted)
    guarded_reasons = list(guarded.get('candidate_reasons') or [])
    if 'score_tail_guard' not in guarded_reasons:
        guarded_reasons.append('score_tail_guard')
    guarded['candidate_reasons'] = guarded_reasons[:7]
    guarded['candidate_source'] = 'matrix_axis_structural_tail'
    guarded['tail_guard'] = {
        'applied': True,
        'replaced_score': replace_item.get('score'),
        'promoted_probability': round(prob(promoted), 4),
        'replaced_probability': round(prob(replace_item), 4),
        'min_probability': round(min_tail_prob, 4),
        'min_tail_ratio': round(min_tail_ratio, 4),
    }
    result[replace_index] = guarded
    return result


def _get_top3_scores(score_matrix, spf_direction: Optional[str] = None, ou_prediction: Optional[dict] = None) -> list:
    """从统一比分矩阵取TOP3比分，优先满足胜平负和大小球主轴。"""
    norm = _normalize_matrix(score_matrix)
    scores = []
    for i, row in enumerate(norm):
        for j, prob in enumerate(row):
            scores.append({
                'score': '{}-{}'.format(i, j),
                'probability': round(prob, 3),
                'home_goals': i,
                'away_goals': j,
                'axis_match': {
                    'spf': _score_matches_spf(i, j, spf_direction),
                    'ou': _score_matches_ou(i, j, ou_prediction),
                },
            })

    scores.sort(key=lambda x: x['probability'], reverse=True)
    constrained = [
        item for item in scores
        if (item.get('axis_match') or {}).get('spf') and (item.get('axis_match') or {}).get('ou')
    ]
    if len(constrained) >= 3 and sum(item['probability'] for item in constrained[:8]) >= 0.08:
        return constrained[:3]
    spf_only = [item for item in scores if (item.get('axis_match') or {}).get('spf')]
    if len(spf_only) >= 3:
        return spf_only[:3]
    return scores[:3]


def _get_handicap(match: dict, db_path: str = None) -> float:
    """获取让球数。

    Internal convention: positive means the home team gives goals, so RQSPF
    uses home_score - handicap. Sporttery goal_line is displayed from the
    home-team view: -1 means home gives one, +1 means home receives one.
    """
    def from_goal_line(value: Any) -> Optional[float]:
        text = str(value or '').strip()
        if not text:
            return None
        try:
            return -float(text)
        except (TypeError, ValueError):
            return None

    for key in ('rqspf_odds', 'odds'):
        data = match.get(key) if isinstance(match, dict) else None
        if isinstance(data, dict):
            if key == 'odds':
                data = data.get('rqspf') if isinstance(data.get('rqspf'), dict) else data
            parsed = from_goal_line(data.get('goal_line') if isinstance(data, dict) else None)
            if parsed is not None:
                return parsed

    lottery_match_id = match.get('lottery_match_id') if isinstance(match, dict) else None
    if db_path and lottery_match_id:
        try:
            conn = sqlite3.connect(db_path, timeout=10)
            cursor = conn.cursor()
            cursor.execute("""
                SELECT odds_data
                FROM lottery_odds
                WHERE lottery_match_id = ? AND play_type = 'rqspf'
                ORDER BY created_at DESC
                LIMIT 1
            """, (lottery_match_id,))
            row = cursor.fetchone()
            conn.close()
            if row and row[0]:
                odds_data = json.loads(row[0]) if isinstance(row[0], str) else row[0]
                if isinstance(odds_data, dict):
                    parsed = from_goal_line(odds_data.get('goal_line'))
                    if parsed is not None:
                        return parsed
        except Exception as exc:
            logger.debug('读取让球盘口goal_line失败: %s', exc)

    h = match.get('handicap_line')
    if h is not None:
        try:
            return float(h)
        except (ValueError, TypeError):
            pass
    return 0.0


def _rqspf_code_for_score(home_goals: int, away_goals: int, handicap: float) -> str:
    adjusted = (home_goals - handicap) - away_goals
    if adjusted > 0:
        return '3'
    if adjusted == 0:
        return '1'
    return '0'


def _rqspf_projection(score_matrix, handicap: float, predicate=None) -> dict:
    norm = _normalize_matrix(score_matrix)
    totals = {'3': 0.0, '1': 0.0, '0': 0.0}
    margin = {
        'home_win_by_1': 0.0,
        'home_win_by_2_plus': 0.0,
        'draw': 0.0,
        'away_win_by_1': 0.0,
        'away_win_by_2_plus': 0.0,
    }
    goal_diff = {}
    mass = 0.0
    top_cells = []

    for home_goals, row in enumerate(norm):
        for away_goals, raw_prob in enumerate(row):
            try:
                prob = float(raw_prob or 0)
            except (TypeError, ValueError):
                prob = 0.0
            if prob <= 0:
                continue
            if predicate and not predicate(home_goals, away_goals):
                continue
            mass += prob
            code = _rqspf_code_for_score(home_goals, away_goals, handicap)
            totals[code] += prob
            diff = home_goals - away_goals
            goal_diff[str(diff)] = goal_diff.get(str(diff), 0.0) + prob
            if diff == 0:
                margin['draw'] += prob
            elif diff == 1:
                margin['home_win_by_1'] += prob
            elif diff >= 2:
                margin['home_win_by_2_plus'] += prob
            elif diff == -1:
                margin['away_win_by_1'] += prob
            else:
                margin['away_win_by_2_plus'] += prob
            top_cells.append((prob, home_goals, away_goals, code))

    if mass > 0:
        probabilities = {key: round(value / mass, 3) for key, value in totals.items()}
        margin_distribution = {key: round(value / mass, 4) for key, value in margin.items()}
    else:
        probabilities = {'3': 0.0, '1': 0.0, '0': 0.0}
        margin_distribution = {key: 0.0 for key in margin}
    if mass > 0:
        goal_diff_distribution = {
            key: round(value / mass, 4)
            for key, value in sorted(goal_diff.items(), key=lambda item: int(item[0]))
        }
    else:
        goal_diff_distribution = {}
    rec = max(probabilities, key=probabilities.get)
    top_cells.sort(reverse=True)
    return {
        'direction': rec,
        'recommendation_cn': {'3': '让胜', '1': '让平', '0': '让负'}.get(rec, ''),
        'probabilities': probabilities,
        'mass': round(mass, 4),
        'margin_distribution': margin_distribution,
        'goal_diff_distribution': goal_diff_distribution,
        'top_cells': [
            {
                'score': f'{home}-{away}',
                'probability': round(prob, 4),
                'rqspf': {'3': '让胜', '1': '让平', '0': '让负'}.get(code, code),
            }
            for prob, home, away, code in top_cells[:5]
        ],
    }


def _format_goal_line(handicap: float) -> str:
    try:
        goal_line = -float(handicap or 0)
    except (TypeError, ValueError):
        goal_line = 0.0
    if abs(goal_line) < 1e-9:
        return '0'
    if float(goal_line).is_integer():
        return f'{goal_line:+.0f}'
    return f'{goal_line:+g}'


def _rqspf_margin_requirement(handicap: float, direction: str) -> str:
    """Describe the actual full-time margin needed for a handicap result.

    Internal handicap is positive when the home team gives goals. The displayed
    Sporttery line is the opposite sign: internal +1 is shown as -1.
    """
    try:
        h = float(handicap or 0)
    except (TypeError, ValueError):
        h = 0.0
    if abs(h) < 1e-9:
        return {'3': '主队胜出', '1': '双方打平', '0': '客队胜出'}.get(str(direction), '')

    def number(value: float) -> str:
        return str(int(value)) if float(value).is_integer() else f'{value:g}'

    direction = str(direction or '')
    if h > 0:
        line = number(h)
        cover = number(h + 1) if float(h).is_integer() else f'超过{line}'
        if direction == '3':
            return f'主队至少赢{cover}球才是让胜'
        if direction == '1':
            return f'主队正好赢{line}球才是让平'
        if direction == '0':
            return f'主队净胜不足{line}球或不胜才是让负'
    else:
        line_value = abs(h)
        line = number(line_value)
        cover_limit = line_value - 1 if float(line_value).is_integer() else None
        miss = number(line_value + 1) if float(line_value).is_integer() else f'超过{line}'
        if direction == '3':
            if cover_limit is not None and cover_limit <= 0:
                return '主队不败才是让胜'
            if cover_limit is not None:
                return f'主队不败或最多输{number(cover_limit)}球才是让胜'
            return f'主队受让{line}球后仍领先才是让胜'
        if direction == '1':
            return f'客队正好赢{line}球才是让平'
        if direction == '0':
            return f'客队至少赢{miss}球才是让负'
    return ''


def _bqc_full_time_axis(bqc_prediction: Optional[dict]) -> Optional[str]:
    if not isinstance(bqc_prediction, dict):
        return None
    raw = str(
        bqc_prediction.get('recommendation')
        or bqc_prediction.get('direction')
        or ''
    ).strip()
    if len(raw) == 2 and raw[1] in {'h', 'd', 'a'}:
        return {'h': '3', 'd': '1', 'a': '0'}.get(raw[1])
    cn = str(bqc_prediction.get('recommendation_cn') or '').strip()
    if len(cn) >= 2:
        return {'胜': '3', '平': '1', '负': '0'}.get(cn[-1])
    return None


def _rqspf_direction_possible_under_spf(handicap: float, rqspf_dir: str, spf_dir: str) -> bool:
    if spf_dir not in {'3', '1', '0'} or rqspf_dir not in {'3', '1', '0'}:
        return True
    try:
        h = float(handicap or 0)
    except (TypeError, ValueError):
        h = 0.0
    for diff in range(-15, 16):
        if spf_dir == '3' and diff <= 0:
            continue
        if spf_dir == '1' and diff != 0:
            continue
        if spf_dir == '0' and diff >= 0:
            continue
        adjusted = diff - h
        code = '3' if adjusted > 0 else '1' if adjusted == 0 else '0'
        if code == rqspf_dir:
            return True
    return False


def _spf_codes_possible_under_rqspf(handicap: float, rqspf_dir: str) -> set:
    if rqspf_dir not in {'3', '1', '0'}:
        return set()
    try:
        h = float(handicap or 0)
    except (TypeError, ValueError):
        h = 0.0
    possible = set()
    for diff in range(-15, 16):
        adjusted = diff - h
        code = '3' if adjusted > 0 else '1' if adjusted == 0 else '0'
        if code != rqspf_dir:
            continue
        if diff > 0:
            possible.add('3')
        elif diff == 0:
            possible.add('1')
        else:
            possible.add('0')
    return possible


def _rqspf_top_stats(probs: Any) -> dict:
    if not isinstance(probs, dict):
        return {'direction': None, 'probability': 0.0, 'second_direction': None, 'second_probability': 0.0, 'gap': 0.0}
    items = []
    for key in ('3', '1', '0'):
        try:
            items.append((key, float(probs.get(key) or 0.0)))
        except (TypeError, ValueError):
            items.append((key, 0.0))
    items.sort(key=lambda item: item[1], reverse=True)
    top = items[0] if items else (None, 0.0)
    second = items[1] if len(items) > 1 else (None, 0.0)
    return {
        'direction': top[0],
        'probability': top[1],
        'second_direction': second[0],
        'second_probability': second[1],
        'gap': top[1] - second[1],
    }


def _rqspf_score_cells_support_direction(cells: Any, handicap: float, direction: str, top_n: int = 3) -> dict:
    if not isinstance(cells, list) or direction not in {'3', '1', '0'}:
        return {'supported': False, 'rank': None, 'score': None}
    for index, cell in enumerate(cells[:max(top_n, 0)], start=1):
        if not isinstance(cell, dict):
            continue
        parsed = _parse_score_text(cell.get('score'))
        if not parsed:
            continue
        if _rqspf_code_for_score(parsed[0], parsed[1], handicap) == direction:
            return {
                'supported': True,
                'rank': index,
                'score': cell.get('score'),
                'probability': cell.get('probability'),
            }
    return {'supported': False, 'rank': None, 'score': None}


def _rqspf_top_cell_probability(cells: Any, top_n: int = 3) -> float:
    if not isinstance(cells, list):
        return 0.0
    for cell in cells[:max(top_n, 0)]:
        if not isinstance(cell, dict):
            continue
        probability = _to_float(cell.get('probability'), None)
        if probability is not None:
            return float(probability)
    return 0.0


def _rqspf_integer_boundary_adjustment(
    display: dict,
    unconditional: dict,
    axis_projection: dict,
    handicap: float,
    ou_prediction: Optional[dict] = None,
    market_probabilities: Optional[dict] = None,
) -> dict:
    """Protect exact-margin draw on integer handicap lines.

    For a -1/-2/-3 or +1/+2 line, "rqspf draw" means the final goal
    difference lands exactly on the handicap boundary. This is often the right
    place to be cautious when score candidates and O/U imply a boundary score.
    """
    try:
        h = float(handicap or 0)
    except (TypeError, ValueError):
        return {}
    rounded = round(h)
    if abs(h) < 1e-9 or abs(h - rounded) > 1e-9:
        return {}

    probs = display.get('probabilities') if isinstance(display, dict) else {}
    if not isinstance(probs, dict):
        return {}
    stats = _rqspf_top_stats(probs)
    if stats.get('direction') == '1':
        return {}
    draw_probability = _to_float(probs.get('1'), 0.0) or 0.0
    top_probability = float(stats.get('probability') or 0.0)
    gap_to_top = top_probability - draw_probability

    min_probability = _env_float('FOOTBALL_RQSPF_INTEGER_DRAW_MIN', 0.22, 0.0, 1.0)
    max_gap = _env_float('FOOTBALL_RQSPF_INTEGER_DRAW_MAX_GAP', 0.08, 0.0, 1.0)
    standard_probability_condition = bool(
        draw_probability >= min_probability and gap_to_top <= max_gap
    )

    display_cells = display.get('top_cells') if isinstance(display, dict) else None
    unconditional_cells = unconditional.get('top_cells') if isinstance(unconditional, dict) else None
    axis_cells = axis_projection.get('top_cells') if isinstance(axis_projection, dict) else None
    display_support = _rqspf_score_cells_support_direction(display_cells, h, '1', 4)
    unconditional_support = _rqspf_score_cells_support_direction(unconditional_cells, h, '1', 4)
    axis_support = _rqspf_score_cells_support_direction(axis_cells, h, '1', 4)
    exact_margin_supports = [
        item
        for item in (display_support, unconditional_support, axis_support)
        if isinstance(item, dict) and item.get('supported')
    ]

    axis_probs = axis_projection.get('probabilities') if isinstance(axis_projection, dict) else {}
    axis_draw = _to_float(axis_probs.get('1'), None) if isinstance(axis_probs, dict) else None
    axis_stats = _rqspf_top_stats(axis_probs) if isinstance(axis_probs, dict) else {}
    axis_supports_draw = bool(
        axis_draw is not None
        and axis_draw >= min_probability
        and float(axis_stats.get('probability') or 0.0) - float(axis_draw or 0.0) <= max_gap
    )

    ou_side = _ou_side_from_recommendation((ou_prediction or {}).get('recommendation')) if isinstance(ou_prediction, dict) else None
    ou_line = _to_float((ou_prediction or {}).get('best_line') or (ou_prediction or {}).get('line'), None) if isinstance(ou_prediction, dict) else None
    ou_boundary_support = False
    if ou_side == 'under' and ou_line is not None:
        # If the goal line is close to the handicap size, covering by more than
        # the line needs a very specific blowout; exact-margin deserves caution.
        ou_boundary_support = abs(float(ou_line) - abs(h)) <= 0.75 or float(ou_line) <= abs(h) + 0.75
    market_stats = _rqspf_top_stats(market_probabilities) if isinstance(market_probabilities, dict) else {}
    market_draw_probability = (
        _to_float((market_probabilities or {}).get('1'), 0.0)
        if isinstance(market_probabilities, dict)
        else 0.0
    ) or 0.0
    market_top_probability = float(market_stats.get('probability') or 0.0)
    market_draw_gap = market_top_probability - market_draw_probability
    market_supports_draw = bool(
        isinstance(market_probabilities, dict)
        and market_draw_probability >= _env_float('FOOTBALL_RQSPF_BOUNDARY_MARKET_DRAW_MIN', 0.23, 0.0, 1.0)
        and market_draw_gap <= _env_float('FOOTBALL_RQSPF_BOUNDARY_MARKET_MAX_GAP', 0.16, 0.0, 1.0)
        and market_top_probability <= _env_float('FOOTBALL_RQSPF_BOUNDARY_MARKET_TOP_MAX', 0.39, 0.0, 1.0)
    )

    top_cell_probability = max(
        _rqspf_top_cell_probability(display_cells, 4),
        _rqspf_top_cell_probability(unconditional_cells, 4),
        _rqspf_top_cell_probability(axis_cells, 4),
    )
    best_exact_margin_probability = max(
        (
            float(item.get('probability') or 0.0)
            for item in exact_margin_supports
            if isinstance(item, dict)
        ),
        default=0.0,
    )
    best_exact_margin_rank = min(
        (
            int(item.get('rank'))
            for item in exact_margin_supports
            if isinstance(item, dict) and item.get('rank') is not None
        ),
        default=None,
    )
    exact_margin_ratio = (
        best_exact_margin_probability / top_cell_probability
        if top_cell_probability > 0 and best_exact_margin_probability > 0
        else 0.0
    )
    display_goal_diff = display.get('goal_diff_distribution') if isinstance(display, dict) else {}
    axis_goal_diff = axis_projection.get('goal_diff_distribution') if isinstance(axis_projection, dict) else {}
    boundary_key = str(rounded)
    display_boundary_family_probability = (
        _to_float(display_goal_diff.get(boundary_key), 0.0)
        if isinstance(display_goal_diff, dict)
        else 0.0
    ) or 0.0
    axis_boundary_family_probability = (
        _to_float(axis_goal_diff.get(boundary_key), 0.0)
        if isinstance(axis_goal_diff, dict)
        else 0.0
    ) or 0.0
    boundary_family_probability = max(
        float(draw_probability or 0.0),
        float(display_boundary_family_probability or 0.0),
        float(axis_boundary_family_probability or 0.0),
    )
    family_top_probability = max(
        float(top_probability or 0.0),
        float(axis_stats.get('probability') or 0.0) if axis_stats else 0.0,
    )
    boundary_family_ratio = (
        boundary_family_probability / family_top_probability
        if family_top_probability > 0 and boundary_family_probability > 0
        else 0.0
    )
    display_is_axis_projection = bool(axis_projection and display is axis_projection)
    exact_margin_cell_override = bool(
        best_exact_margin_rank is not None
        and best_exact_margin_rank <= 2
        and draw_probability >= _env_float('FOOTBALL_RQSPF_BOUNDARY_CELL_DRAW_MIN', 0.18, 0.0, 1.0)
        and gap_to_top <= _env_float('FOOTBALL_RQSPF_BOUNDARY_CELL_MAX_GAP', 0.48, 0.0, 1.0)
        and exact_margin_ratio >= _env_float('FOOTBALL_RQSPF_BOUNDARY_CELL_MIN_RATIO', 0.85, 0.0, 1.5)
        and market_supports_draw
    )
    exact_margin_family_override = bool(
        display_is_axis_projection
        and best_exact_margin_rank is not None
        and best_exact_margin_rank <= int(_env_float('FOOTBALL_RQSPF_BOUNDARY_FAMILY_MAX_RANK', 1, 1, 4))
        and draw_probability >= _env_float('FOOTBALL_RQSPF_BOUNDARY_FAMILY_DRAW_MIN', 0.18, 0.0, 1.0)
        and gap_to_top <= _env_float('FOOTBALL_RQSPF_BOUNDARY_FAMILY_MAX_GAP', 0.48, 0.0, 1.0)
        and exact_margin_ratio >= _env_float('FOOTBALL_RQSPF_BOUNDARY_FAMILY_CELL_MIN_RATIO', 0.65, 0.0, 1.5)
        and boundary_family_probability >= _env_float('FOOTBALL_RQSPF_BOUNDARY_FAMILY_MIN', 0.24, 0.0, 1.0)
        and boundary_family_ratio >= _env_float('FOOTBALL_RQSPF_BOUNDARY_FAMILY_MIN_RATIO', 0.35, 0.0, 1.5)
    )

    supported = any(
        item.get('supported')
        for item in exact_margin_supports
    ) or axis_supports_draw or ou_boundary_support or exact_margin_cell_override or exact_margin_family_override
    if not standard_probability_condition and not exact_margin_cell_override and not exact_margin_family_override:
        return {}
    if not supported:
        return {}

    return {
        'from': stats.get('direction'),
        'to': '1',
        'reason': 'integer_handicap_boundary_protection',
        'handicap': h,
        'boundary_goal_diff': rounded,
        'draw_probability': round(draw_probability, 4),
        'top_probability': round(top_probability, 4),
        'gap_to_top': round(gap_to_top, 4),
        'min_probability': round(min_probability, 4),
        'max_gap': round(max_gap, 4),
        'standard_probability_condition': standard_probability_condition,
        'display_score_support': display_support,
        'unconditional_score_support': unconditional_support,
        'axis_score_support': axis_support,
        'axis_draw_probability': round(float(axis_draw), 4) if axis_draw is not None else None,
        'ou_boundary_support': ou_boundary_support,
        'ou_side': ou_side,
        'ou_line': ou_line,
        'market_draw_probability': round(market_draw_probability, 4) if market_draw_probability else 0.0,
        'market_top_probability': round(market_top_probability, 4) if market_top_probability else 0.0,
        'market_draw_gap': round(market_draw_gap, 4) if isinstance(market_draw_gap, (int, float)) else None,
        'market_supports_draw': market_supports_draw,
        'exact_margin_cell_override': exact_margin_cell_override,
        'exact_margin_family_override': exact_margin_family_override,
        'exact_margin_rank': best_exact_margin_rank,
        'exact_margin_probability': round(best_exact_margin_probability, 4) if best_exact_margin_probability else 0.0,
        'top_cell_probability': round(top_cell_probability, 4) if top_cell_probability else 0.0,
        'exact_margin_ratio': round(exact_margin_ratio, 4) if exact_margin_ratio else 0.0,
        'boundary_family_probability': round(boundary_family_probability, 4) if boundary_family_probability else 0.0,
        'boundary_family_ratio': round(boundary_family_ratio, 4) if boundary_family_ratio else 0.0,
        'display_is_axis_projection': display_is_axis_projection,
    }


def _axis_context_is_trusted(axis_context: Optional[dict]) -> bool:
    if not isinstance(axis_context, dict):
        return False
    return bool(axis_context.get('usable_for_derived') or axis_context.get('trusted'))


def _axis_context_is_trusted_for_bqc(axis_context: Optional[dict]) -> bool:
    if _env_float('FOOTBALL_BQC_SPF_AXIS_ENABLED', 1.0, 0.0, 1.0) < 1.0:
        return False
    if not _axis_context_is_trusted(axis_context):
        return False
    top_probability = _to_float((axis_context or {}).get('top_probability'), 0.0) or 0.0
    gap = _to_float((axis_context or {}).get('gap'), 0.0) or 0.0
    min_probability = _env_float('FOOTBALL_BQC_AXIS_MIN_PROBABILITY', 0.52, 0.0, 1.0)
    min_gap = _env_float('FOOTBALL_BQC_AXIS_MIN_GAP', 0.05, 0.0, 1.0)
    return bool(top_probability >= min_probability and gap >= min_gap)


def _bqc_phase_profile_enabled() -> bool:
    return _env_float('FOOTBALL_BQC_PHASE_PROFILE_ENABLED', 0.0, 0.0, 1.0) >= 1.0


def _build_spf_axis_context(result: dict, spf_play: dict) -> dict:
    """Decide whether the SPF axis is strong enough to drive derived plays."""
    probs = spf_play.get('probabilities') if isinstance(spf_play, dict) else {}
    stats = _rqspf_top_stats(probs)
    direction = str((spf_play or {}).get('direction') or stats.get('direction') or '')

    fp = (result or {}).get('final_prediction') or {}
    odds_baseline = (result or {}).get('odds_baseline') or {}
    model_vs_odds = (result or {}).get('model_vs_odds') or {}
    source = str(odds_baseline.get('source') or '')
    source_quality = str(odds_baseline.get('source_quality') or '').strip()
    if not source_quality:
        if source.startswith('oddsfe'):
            source_quality = 'oddsfe_proxy'
        elif odds_baseline:
            source_quality = 'market_unknown'
        else:
            source_quality = 'model_only'

    top_probability = float(stats.get('probability') or 0.0)
    gap = float(stats.get('gap') or 0.0)
    final_confidence = _to_float(fp.get('confidence'), top_probability) or top_probability

    prematch_min = _env_float('FOOTBALL_DERIVED_AXIS_PREMATCH_MIN', 0.52, 0.0, 1.0)
    prematch_gap = _env_float('FOOTBALL_DERIVED_AXIS_PREMATCH_GAP', 0.05, 0.0, 1.0)
    proxy_min = _env_float('FOOTBALL_DERIVED_AXIS_PROXY_MIN', 0.56, 0.0, 1.0)
    proxy_gap = _env_float('FOOTBALL_DERIVED_AXIS_PROXY_GAP', 0.08, 0.0, 1.0)
    model_min = _env_float('FOOTBALL_DERIVED_AXIS_MODEL_ONLY_MIN', 0.62, 0.0, 1.0)
    model_gap = _env_float('FOOTBALL_DERIVED_AXIS_MODEL_ONLY_GAP', 0.14, 0.0, 1.0)

    if source_quality == 'prematch':
        min_probability = prematch_min
        min_gap = prematch_gap
        evidence_class = 'prematch_market'
    elif source_quality in {'oddsfe_proxy', 'market_unknown'}:
        min_probability = proxy_min
        min_gap = proxy_gap
        evidence_class = 'market_proxy'
    else:
        min_probability = model_min
        min_gap = model_gap
        evidence_class = 'model_only'

    trusted = bool(
        direction in {'3', '1', '0'}
        and top_probability >= min_probability
        and gap >= min_gap
    )
    if not trusted:
        reason = 'axis_probability_too_thin'
        if direction not in {'3', '1', '0'}:
            reason = 'missing_spf_direction'
        elif top_probability < min_probability:
            reason = 'top_probability_below_threshold'
        elif gap < min_gap:
            reason = 'top_gap_below_threshold'
    else:
        reason = 'trusted_%s_axis' % evidence_class

    return {
        'direction': direction,
        'direction_cn': {'3': '主胜', '1': '平局', '0': '客胜'}.get(direction, ''),
        'top_probability': round(top_probability, 4),
        'second_direction': stats.get('second_direction'),
        'second_probability': round(float(stats.get('second_probability') or 0.0), 4),
        'gap': round(gap, 4),
        'final_confidence': round(float(final_confidence or 0.0), 4),
        'confidence_level': fp.get('confidence_level'),
        'odds_source': source,
        'source_quality': source_quality,
        'evidence_class': evidence_class,
        'model_vs_odds_agreement': model_vs_odds.get('agreement'),
        'min_probability': round(min_probability, 4),
        'min_gap': round(min_gap, 4),
        'trusted': trusted,
        'usable_for_derived': trusted,
        'reason': reason,
    }


def _compute_rqspf(
    score_matrix,
    handicap: float,
    full_time_axis: Optional[str] = None,
    full_time_probabilities: Optional[dict] = None,
    ou_prediction: Optional[dict] = None,
    bqc_prediction: Optional[dict] = None,
    axis_context: Optional[dict] = None,
    rqspf_odds_baseline: Optional[dict] = None,
) -> dict:
    """让球胜平负 — full matrix plus main-axis conditional projection.

    handicap > 0 means home gives goals: adjusted_home = home - handicap.
    handicap < 0 means home receives goals.
    """
    unconditional = _rqspf_projection(score_matrix, handicap)

    axis_trusted = _axis_context_is_trusted(axis_context) if axis_context is not None else True
    bqc_axis = _bqc_full_time_axis(bqc_prediction) if axis_trusted else None
    axis_conflict = bool(
        full_time_axis in {'3', '1', '0'}
        and bqc_axis in {'3', '1', '0'}
        and full_time_axis != bqc_axis
    )
    axis_direction = full_time_axis if axis_trusted and full_time_axis in {'3', '1', '0'} else bqc_axis

    axis_projection = {}
    if axis_direction in {'3', '1', '0'}:
        spf_projection = _rqspf_projection(
            score_matrix,
            handicap,
            lambda h, a: _score_matches_spf(h, a, axis_direction),
        )
        spf_ou_projection = {}
        if isinstance(ou_prediction, dict):
            spf_ou_projection = _rqspf_projection(
                score_matrix,
                handicap,
                lambda h, a: (
                    _score_matches_spf(h, a, axis_direction)
                    and _score_matches_ou(h, a, ou_prediction)
                ),
            )
        axis_basis = (
            'spf_bqc_ou_axis'
            if bqc_axis == axis_direction and spf_ou_projection and spf_ou_projection.get('mass', 0) >= 0.08
            else 'spf_ou_axis'
            if spf_ou_projection and spf_ou_projection.get('mass', 0) >= 0.08
            else 'spf_bqc_axis'
            if bqc_axis == axis_direction
            else 'spf_axis'
        )
        axis_projection = (
            {**spf_ou_projection, 'basis': axis_basis}
            if spf_ou_projection and spf_ou_projection.get('mass', 0) >= 0.08
            else {**spf_projection, 'basis': axis_basis}
        )
        if axis_projection.get('direction'):
            axis_projection['margin_requirement'] = _rqspf_margin_requirement(
                handicap,
                axis_projection.get('direction'),
            )

    axis_min_mass = _env_float('FOOTBALL_RQSPF_AXIS_MIN_MASS', 0.12, 0.0, 1.0)
    axis_top_min = _env_float('FOOTBALL_RQSPF_AXIS_TOP_MIN', 0.0, 0.0, 1.0)
    protect_unconditional_min = _env_float('FOOTBALL_RQSPF_PROTECT_UNCONDITIONAL_MIN', 1.0, 0.0, 1.0)
    protect_unconditional_gap = _env_float('FOOTBALL_RQSPF_PROTECT_UNCONDITIONAL_GAP', 1.0, 0.0, 1.0)
    arbitration_spf_min = _env_float('FOOTBALL_SPF_RQSPF_ARBITRATION_MIN_SPF_CONF', 0.0, 0.0, 1.0)
    arbitration_spf_max = _env_float('FOOTBALL_SPF_RQSPF_ARBITRATION_MAX_SPF_CONF', 0.0, 0.0, 1.0)
    arbitration_rqspf_min = _env_float('FOOTBALL_SPF_RQSPF_ARBITRATION_MIN_RQSPF_CONF', 1.0, 0.0, 1.0)
    arbitration_rqspf_gap = _env_float('FOOTBALL_SPF_RQSPF_ARBITRATION_MIN_RQSPF_GAP', 1.0, 0.0, 1.0)
    unconditional_stats = _rqspf_top_stats(unconditional.get('probabilities'))
    axis_stats = _rqspf_top_stats(axis_projection.get('probabilities')) if axis_projection else {}
    spf_stats = _rqspf_top_stats(full_time_probabilities)
    spf_probs = full_time_probabilities if isinstance(full_time_probabilities, dict) else {}
    market_probs = (
        rqspf_odds_baseline.get('probabilities')
        if isinstance(rqspf_odds_baseline, dict) and isinstance(rqspf_odds_baseline.get('probabilities'), dict)
        else {}
    )
    market_stats = _rqspf_top_stats(market_probs)
    full_time_arbitration = {}
    axis_decision = {
        'axis_min_mass': round(axis_min_mass, 4),
        'axis_top_min': round(axis_top_min, 4),
        'protect_unconditional_min': round(protect_unconditional_min, 4),
        'protect_unconditional_gap': round(protect_unconditional_gap, 4),
        'arbitration_spf_min': round(arbitration_spf_min, 4),
        'arbitration_spf_max': round(arbitration_spf_max, 4),
        'arbitration_rqspf_min': round(arbitration_rqspf_min, 4),
        'arbitration_rqspf_gap': round(arbitration_rqspf_gap, 4),
        'axis_mass': axis_projection.get('mass') if axis_projection else None,
        'axis_top_probability': round(axis_stats.get('probability', 0.0), 4) if axis_stats else None,
        'unconditional_top_probability': round(unconditional_stats.get('probability', 0.0), 4),
        'unconditional_top_gap': round(unconditional_stats.get('gap', 0.0), 4),
        'spf_top_probability': round(spf_stats.get('probability', 0.0), 4),
        'axis_trusted': axis_trusted,
        'axis_context': axis_context or {},
        'rqspf_market': rqspf_odds_baseline or {},
        'rqspf_market_top': market_stats.get('direction'),
        'rqspf_market_top_probability': round(float(market_stats.get('probability') or 0.0), 4),
        'rqspf_market_gap': round(float(market_stats.get('gap') or 0.0), 4),
        'vetoed': False,
        'veto_reason': None,
    }

    display_source = 'unconditional'
    display = unconditional
    axis_can_display = bool(
        axis_projection
        and axis_projection.get('mass', 0) >= axis_min_mass
        and axis_stats.get('probability', 0.0) >= axis_top_min
    )
    unconditional_possible_under_axis = True
    axis_projection_possible_under_axis = True
    if axis_direction in {'3', '1', '0'}:
        unconditional_possible_under_axis = _rqspf_direction_possible_under_spf(
            handicap,
            unconditional.get('direction'),
            axis_direction,
        )
        axis_projection_possible_under_axis = _rqspf_direction_possible_under_spf(
            handicap,
            axis_projection.get('direction') if axis_projection else None,
            axis_direction,
        )
    if axis_can_display and not unconditional_possible_under_axis and axis_projection_possible_under_axis:
        axis_decision['hard_consistency_required'] = True
        axis_decision['hard_consistency_reason'] = 'unconditional_rqspf_impossible_under_full_time_axis'
    if (
        axis_can_display
        and axis_projection.get('direction') != unconditional.get('direction')
        and unconditional_possible_under_axis
        and unconditional_stats.get('probability', 0.0) >= protect_unconditional_min
        and unconditional_stats.get('gap', 0.0) >= protect_unconditional_gap
    ):
        axis_can_display = False
        axis_decision['vetoed'] = True
        axis_decision['veto_reason'] = 'strong_unconditional_margin_distribution'
    market_veto_min = _env_float('FOOTBALL_RQSPF_MARKET_VETO_MIN', 0.34, 0.0, 1.0)
    market_veto_gap = _env_float('FOOTBALL_RQSPF_MARKET_VETO_GAP', 0.015, 0.0, 1.0)
    unconditional_veto_min = _env_float('FOOTBALL_RQSPF_UNCONDITIONAL_MARKET_VETO_MIN', 0.36, 0.0, 1.0)
    if (
        axis_can_display
        and axis_projection
        and axis_projection.get('direction') in {'3', '0'}
        and unconditional.get('direction') in {'3', '1', '0'}
        and axis_projection.get('direction') != unconditional.get('direction')
        and unconditional_possible_under_axis
        and market_stats.get('direction') == unconditional.get('direction')
        and market_stats.get('probability', 0.0) >= market_veto_min
        and market_stats.get('gap', 0.0) >= market_veto_gap
        and unconditional_stats.get('probability', 0.0) >= unconditional_veto_min
    ):
        axis_can_display = False
        axis_decision['vetoed'] = True
        axis_decision['veto_reason'] = 'rqspf_market_unconditional_veto_axis_cover'
    if (
        axis_direction in {'3', '1', '0'}
        and unconditional.get('direction') in {'3', '1', '0'}
        and not _rqspf_direction_possible_under_spf(handicap, unconditional.get('direction'), axis_direction)
        and spf_stats.get('probability', 0.0) >= arbitration_spf_min
        and spf_stats.get('probability', 0.0) <= arbitration_spf_max
        and unconditional_stats.get('probability', 0.0) >= arbitration_rqspf_min
        and unconditional_stats.get('gap', 0.0) >= arbitration_rqspf_gap
    ):
        compatible_spf = _spf_codes_possible_under_rqspf(handicap, unconditional.get('direction'))
        if compatible_spf:
            suggested_spf = max(
                compatible_spf,
                key=lambda code: float(spf_probs.get(code) or 0.0),
            )
            axis_can_display = False
            axis_decision['vetoed'] = True
            axis_decision['veto_reason'] = 'low_confidence_spf_arbitrated_by_margin_distribution'
            full_time_arbitration = {
                'reason': 'low_confidence_spf_arbitrated_by_rqspf',
                'original_spf_direction': axis_direction,
                'original_spf_probability': round(spf_stats.get('probability', 0.0), 4),
                'rqspf_direction': unconditional.get('direction'),
                'rqspf_probability': round(unconditional_stats.get('probability', 0.0), 4),
                'rqspf_gap': round(unconditional_stats.get('gap', 0.0), 4),
                'compatible_spf_directions': sorted(compatible_spf),
                'suggested_spf_direction': suggested_spf,
                'suggested_spf_probability': round(float(spf_probs.get(suggested_spf) or 0.0), 4),
            }
    if axis_can_display:
        # If the full matrix is dominated by off-axis draw/away outcomes while
        # the visible analysis axis says home/draw/away, display the conditional
        # projection. The full matrix is still retained for review.
        if axis_projection.get('direction') != unconditional.get('direction'):
            display = axis_projection
            display_source = axis_projection.get('basis') or 'axis_projection'

    integer_boundary_adjustment = _rqspf_integer_boundary_adjustment(
        display,
        unconditional,
        axis_projection,
        handicap,
        ou_prediction,
        market_probs,
    )
    rec = integer_boundary_adjustment.get('to') or display.get('direction') or unconditional.get('direction')
    if (
        axis_direction in {'3', '1', '0'}
        and rec in {'3', '1', '0'}
        and not _rqspf_direction_possible_under_spf(handicap, rec, axis_direction)
        and axis_projection
        and axis_projection.get('mass', 0) > 0
        and _rqspf_direction_possible_under_spf(handicap, axis_projection.get('direction'), axis_direction)
        and not full_time_arbitration
        and not integer_boundary_adjustment
        and not axis_decision.get('vetoed')
    ):
        display = axis_projection
        display_source = f"{axis_projection.get('basis') or 'axis_projection'}_hard_consistency"
        rec = display.get('direction') or rec
    display_probabilities = display.get('probabilities') or unconditional.get('probabilities') or {}
    sorted_display_probs = sorted(
        (
            (key, float(value))
            for key, value in display_probabilities.items()
            if key in {'3', '1', '0'} and isinstance(value, (int, float))
        ),
        key=lambda item: item[1],
        reverse=True,
    )
    boundary_gap = None
    if len(sorted_display_probs) >= 2:
        boundary_gap = sorted_display_probs[0][1] - sorted_display_probs[1][1]
    result = {
        'direction': rec,
        'direction_cn': {'3': '主胜', '1': '平局', '0': '客胜'}.get(rec, ''),
        'recommendation_cn': {'3': '让胜', '1': '让平', '0': '让负'}.get(rec, ''),
        'handicap': handicap,
        'goal_line': -handicap,
        'goal_line_label': _format_goal_line(handicap),
        'margin_requirement': _rqspf_margin_requirement(handicap, rec),
        'handicap_semantics': 'positive_home_gives',
        'probabilities': display_probabilities,
        'market_probabilities': market_probs,
        'market_baseline': rqspf_odds_baseline or {},
        'display_source': display_source,
        'unconditional_direction': unconditional.get('direction'),
        'unconditional_recommendation_cn': unconditional.get('recommendation_cn'),
        'unconditional_margin_requirement': _rqspf_margin_requirement(handicap, unconditional.get('direction')),
        'unconditional_probabilities': unconditional.get('probabilities'),
        'margin_distribution': unconditional.get('margin_distribution'),
        'goal_diff_distribution': unconditional.get('goal_diff_distribution'),
        'axis_projection': axis_projection,
        'axis_decision': axis_decision,
        'full_time_arbitration': full_time_arbitration,
        'axis_context': {
            'full_time_axis': full_time_axis,
            'full_time_axis_cn': {'3': '主胜', '1': '平局', '0': '客胜'}.get(full_time_axis, ''),
            'bqc_full_time_axis': bqc_axis,
            'bqc_full_time_axis_cn': {'3': '主胜', '1': '平局', '0': '客胜'}.get(bqc_axis, ''),
            'axis_direction': axis_direction,
            'axis_direction_cn': {'3': '主胜', '1': '平局', '0': '客胜'}.get(axis_direction, ''),
            'axis_conflict': axis_conflict,
        },
        'boundary_profile': {
            'top_direction': sorted_display_probs[0][0] if sorted_display_probs else rec,
            'second_direction': sorted_display_probs[1][0] if len(sorted_display_probs) >= 2 else None,
            'top_probability': round(sorted_display_probs[0][1], 4) if sorted_display_probs else None,
            'second_probability': round(sorted_display_probs[1][1], 4) if len(sorted_display_probs) >= 2 else None,
            'top_gap': round(boundary_gap, 4) if isinstance(boundary_gap, (int, float)) else None,
            'is_boundary': bool(isinstance(boundary_gap, (int, float)) and boundary_gap <= 0.08),
            'source': display_source,
        },
    }
    if display_source != 'unconditional':
        result['axis_adjustment'] = {
            'from': unconditional.get('direction'),
            'from_cn': unconditional.get('recommendation_cn'),
            'to': rec,
            'to_cn': result['recommendation_cn'],
            'basis': display_source,
            'axis_mass': axis_projection.get('mass'),
            'axis_probabilities': axis_projection.get('probabilities'),
            'unconditional_probabilities': unconditional.get('probabilities'),
        }
    if integer_boundary_adjustment:
        result['integer_boundary_adjustment'] = {
            **integer_boundary_adjustment,
            'from_cn': {'3': '让胜', '1': '让平', '0': '让负'}.get(integer_boundary_adjustment.get('from'), ''),
            'to_cn': '让平',
        }
    return result


def _get_match_odds_baseline(db_path: str, lottery_match_id: str) -> Optional[Dict]:
    """SPF odds baseline using only pre-kickoff captured lottery odds."""
    if not lottery_match_id:
        return None
    try:
        conn = sqlite3.connect(db_path, timeout=10)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        row = _select_prematch_lottery_odds_row(
            cursor,
            lottery_match_id,
            'spf',
            preferred_snapshots=['latest', 'current', 'midday', 'opening', None],
        )
        conn.close()
        if not row:
            return None
        odds_data = json.loads(row['odds_data']) if isinstance(row['odds_data'], str) else row['odds_data']
        h = float(odds_data.get('3', odds_data.get('home', 0)))
        d = float(odds_data.get('1', odds_data.get('draw', 0)))
        a = float(odds_data.get('0', odds_data.get('away', 0)))
        if h <= 1 or d <= 1 or a <= 1:
            return None
        total = 1 / h + 1 / d + 1 / a
        return {
            'home_win': round((1 / h) / total, 4),
            'draw': round((1 / d) / total, 4),
            'away_win': round((1 / a) / total, 4),
            'source': row['snapshot_type'] or 'default',
            'captured_at': str(_odds_row_captured_at(row) or ''),
            'source_quality': 'prematch',
        }
    except Exception as e:
        logger.debug('SPF odds baseline failed: %s', e)
        return None


def _get_ttg_odds_baseline(db_path: str, lottery_match_id: str) -> Optional[Dict]:
    """TTG odds baseline using only pre-kickoff captured lottery odds."""
    if not lottery_match_id:
        return None
    try:
        conn = sqlite3.connect(db_path, timeout=10)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        row = _select_prematch_lottery_odds_row(cursor, lottery_match_id, 'ttg')
        conn.close()
        if not row:
            return None
        odds_data = json.loads(row['odds_data']) if isinstance(row['odds_data'], str) else row['odds_data']
        implied = {}
        total = 0.0
        for i in range(8):
            odds_val = float(odds_data.get('s' + str(i), 0) or 0)
            if odds_val > 1:
                implied[i] = 1 / odds_val
                total += implied[i]
        if total <= 0:
            return None
        for i in implied:
            implied[i] = implied[i] / total
        under_2_5 = sum(implied.get(i, 0) for i in range(3))
        over_2_5 = sum(implied.get(i, 0) for i in range(3, 8))
        under_3_5 = sum(implied.get(i, 0) for i in range(4))
        over_3_5 = sum(implied.get(i, 0) for i in range(4, 8))
        most_likely = max(implied, key=implied.get) if implied else 2
        best_line = 2.5
        best_gap = 1.0
        best_over = 0.0
        best_under = 0.0
        for line in [1.5, 2.0, 2.5, 3.0, 3.5, 4.0, 4.5]:
            over = sum(implied.get(i, 0) for i in range(int(line) + 1, 8))
            under = 1 - over
            gap = abs(over - under)
            if gap < best_gap:
                best_gap = gap
                best_line = line
                best_over = over
                best_under = under
        return {
            'over_2_5': round(over_2_5, 4),
            'under_2_5': round(under_2_5, 4),
            'over_3_5': round(over_3_5, 4),
            'under_3_5': round(under_3_5, 4),
            'most_likely_total': most_likely,
            'goal_distribution': {str(i): round(implied.get(i, 0), 4) for i in range(8) if implied.get(i, 0) > 0.01},
            'best_line': best_line,
            'best_line_over': round(best_over, 4),
            'best_line_under': round(best_under, 4),
            'source': 'ttg_' + (row['snapshot_type'] or 'default'),
            'captured_at': str(_odds_row_captured_at(row) or ''),
            'source_quality': 'prematch',
        }
    except Exception as e:
        logger.debug('TTG odds baseline failed: %s', e)
        return None


def _get_handicap(match: dict, db_path: str = None) -> float:
    """Resolve Sporttery handicap from pre-kickoff rqspf odds when available."""
    def from_goal_line(value: Any) -> Optional[float]:
        text = str(value or '').strip()
        if not text:
            return None
        try:
            return -float(text)
        except (TypeError, ValueError):
            return None

    for key in ('rqspf_odds', 'odds'):
        data = match.get(key) if isinstance(match, dict) else None
        if isinstance(data, dict):
            if key == 'odds':
                data = data.get('rqspf') if isinstance(data.get('rqspf'), dict) else data
            parsed = from_goal_line(data.get('goal_line') if isinstance(data, dict) else None)
            if parsed is not None:
                return parsed

    lottery_match_id = match.get('lottery_match_id') if isinstance(match, dict) else None
    if db_path and lottery_match_id:
        try:
            conn = sqlite3.connect(db_path, timeout=10)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            row = _select_prematch_lottery_odds_row(
                cursor,
                lottery_match_id,
                'rqspf',
                preferred_snapshots=['latest', 'opening', 'midday', 'current', None],
            )
            conn.close()
            if row and row['odds_data']:
                odds_data = json.loads(row['odds_data']) if isinstance(row['odds_data'], str) else row['odds_data']
                if isinstance(odds_data, dict):
                    parsed = from_goal_line(odds_data.get('goal_line'))
                    if parsed is not None:
                        return parsed
        except Exception as exc:
            logger.debug('Read prematch rqspf goal_line failed: %s', exc)

    h = match.get('handicap_line') if isinstance(match, dict) else None
    if h is not None:
        try:
            return float(h)
        except (ValueError, TypeError):
            pass
    return 0.0


def _get_rqspf_odds_baseline(db_path: str, lottery_match_id: str) -> Optional[Dict]:
    """Read prematch RQSPF odds as an implied-probability guard."""
    if not db_path or not lottery_match_id:
        return None
    try:
        conn = sqlite3.connect(db_path, timeout=10)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        row = _select_prematch_lottery_odds_row(
            cursor,
            lottery_match_id,
            'rqspf',
            preferred_snapshots=['latest', 'opening', 'midday', 'current', None],
        )
        conn.close()
        if not row or not row['odds_data']:
            return None
        odds_data = json.loads(row['odds_data']) if isinstance(row['odds_data'], str) else row['odds_data']
        if not isinstance(odds_data, dict):
            return None
        raw_odds = {}
        implied = {}
        total = 0.0
        for key in ('3', '1', '0'):
            try:
                value = float(odds_data.get(key) or 0)
            except (TypeError, ValueError):
                value = 0.0
            if value <= 1:
                continue
            raw_odds[key] = value
            implied[key] = 1 / value
            total += implied[key]
        if total <= 0 or len(implied) < 3:
            return None
        probabilities = {key: round(implied.get(key, 0.0) / total, 4) for key in ('3', '1', '0')}
        stats = _rqspf_top_stats(probabilities)
        return {
            'probabilities': probabilities,
            'odds': raw_odds,
            'direction': stats.get('direction'),
            'top_probability': round(float(stats.get('probability') or 0.0), 4),
            'gap': round(float(stats.get('gap') or 0.0), 4),
            'goal_line': odds_data.get('goal_line'),
            'source': 'rqspf_' + (row['snapshot_type'] or 'default'),
            'captured_at': str(_odds_row_captured_at(row) or ''),
            'source_quality': 'prematch',
        }
    except Exception as exc:
        logger.debug('RQSPF odds baseline failed: %s', exc)
        return None


def _compute_over_under(score_matrix, ou_odds_baseline=None) -> dict:
    """大小球 — 赔率驱动优先, Poisson兜底

    优先用体彩TTG赔率推导(市场定价最准),
    无赔率时用Poisson比分矩阵推算.
    推荐盘口线选择大小概率最接近50/50的那条.
    """
    # === 赔率驱动路径 ===
    if ou_odds_baseline:
        over_2_5 = ou_odds_baseline.get('over_2_5', 0)
        under_2_5 = ou_odds_baseline.get('under_2_5', 0)
        over_3_5 = ou_odds_baseline.get('over_3_5', 0)
        most_likely = ou_odds_baseline.get('most_likely_total', 2)
        goal_dist = ou_odds_baseline.get('goal_distribution', {})
        source = ou_odds_baseline.get('source', 'ttg')
        best_line = ou_odds_baseline.get('best_line', 2.5)
        best_over = ou_odds_baseline.get('best_line_over', over_2_5)
        best_under = ou_odds_baseline.get('best_line_under', under_2_5)

        # 确定推荐 — 基于最佳盘口线
        if best_over > 0.55:
            recommendation = f'大{best_line:g}'
        elif best_under > 0.55:
            recommendation = f'小{best_line:g}'
        else:
            recommendation = f'大{best_line:g}' if best_over > best_under else f'小{best_line:g}'

        # 计算大2/大3 (从goal_distribution推导)
        over_2 = sum(float(v) for k, v in goal_dist.items() if int(k) > 2)
        over_3 = sum(float(v) for k, v in goal_dist.items() if int(k) > 3)

        return {
            'recommendation': recommendation,
            'best_line': best_line,
            'most_likely_total': most_likely,
            'over_2': round(over_2, 3),
            'over_2_5': round(over_2_5, 3),
            'over_3': round(over_3, 3),
            'under_2_5': round(under_2_5, 3),
            'over_3_5': round(over_3_5, 3),
            'total_goals_distribution': goal_dist,
            'source': source,
        }

    # === Poisson兜底路径 ===
    norm = _normalize_matrix(score_matrix)
    total_goals_prob = {}
    for i, row in enumerate(norm):
        for j, prob in enumerate(row):
            total = i + j
            total_goals_prob[total] = total_goals_prob.get(total, 0) + prob

    # 大2 / 大2.5 / 大3
    over_2 = sum(p for g, p in total_goals_prob.items() if g > 2)
    over_2_5 = sum(p for g, p in total_goals_prob.items() if g > 2)  # >2等价于>=3
    over_3 = sum(p for g, p in total_goals_prob.items() if g > 3)

    # 判断最可能的总进球
    most_likely_goals = max(total_goals_prob, key=total_goals_prob.get) if total_goals_prob else 2

    # 找最佳盘口线(Poisson版)
    best_line = 2.5
    best_gap = 1.0
    for line in [1.5, 2.0, 2.5, 3.0, 3.5, 4.0, 4.5]:
        over = sum(p for g, p in total_goals_prob.items() if g > line)
        under = 1 - over
        gap = abs(over - under)
        if gap < best_gap:
            best_gap = gap
            best_line = line

    best_over = sum(p for g, p in total_goals_prob.items() if g > best_line)
    best_under = 1 - best_over
    if best_over > 0.55:
        recommendation = f'大{best_line:g}'
    elif best_under > 0.55:
        recommendation = f'小{best_line:g}'
    else:
        recommendation = f'大{best_line:g}' if best_over > best_under else f'小{best_line:g}'

    return {
        'recommendation': recommendation,
        'best_line': best_line,
        'most_likely_total': most_likely_goals,
        'over_2': round(over_2, 3),
        'over_2_5': round(over_2_5, 3),
        'over_3': round(over_3, 3),
        'under_2_5': round(1 - over_2_5, 3),
        'total_goals_distribution': {str(g): round(p, 3) for g, p in sorted(total_goals_prob.items()) if p >= 0.01},
        'source': 'poisson',
    }


def _is_senior_team_label(label: Any) -> bool:
    text = str(label or '').strip().lower()
    if not text:
        return True
    youth_markers = (' u16', ' u17', ' u18', ' u19', ' u20', ' u21', ' u23', ' women', ' w ')
    if any(marker in f' {text} ' for marker in youth_markers):
        return False
    if text.endswith(' w') or text.startswith('team '):
        return False
    return True


def _is_national_competition_label(label: Any) -> bool:
    text = str(label or '').strip()
    if not text:
        return False
    excluded = (
        '女', 'U16', 'U17', 'U18', 'U19', 'U20', 'U21', 'U23',
        'Youth', 'Women', 'Libertadores', 'Sudamericana',
        'Champions League', 'Europa League', 'Conference League',
        '俱乐部', '解放者杯', '南球杯', '欧冠', '欧联', '欧协联',
    )
    if any(marker.lower() in text.lower() for marker in excluded):
        return False
    keywords = (
        '世界杯', '国际友谊', '国际赛', '友谊赛',
        '欧洲杯', '欧国联', '美洲杯', '亚洲杯', '非洲杯',
        '中北美国家联赛', '中北美金杯', '金杯',
        '预选赛', '世预赛', '世界杯预选',
        'FIFA World Cup', 'World Cup', 'World Cup Qualification',
        'World Cup Qualifying', 'International Friendly', 'Friendly',
        'Friendlies', 'UEFA Nations League', 'Nations League',
        'UEFA Euro', 'European Championship', 'Copa America',
        'Copa América', 'AFC Asian Cup', 'Asian Cup',
        'Africa Cup of Nations', 'Africa Cup', 'CAF Africa Cup',
        'CONCACAF Gold Cup', 'Gold Cup', 'CONCACAF Nations League',
        'International',
    )
    return any(keyword.lower() in text.lower() for keyword in keywords)


def _national_competition_sql_filter(column: str) -> tuple[str, List[Any]]:
    keywords = (
        '世界杯', '国际友谊', '国际赛', '友谊赛',
        '欧洲杯', '欧国联', '美洲杯', '亚洲杯', '非洲杯',
        '中北美国家联赛', '中北美金杯', '金杯',
        '预选赛', '世预赛', '世界杯预选',
        'FIFA World Cup', 'World Cup', 'World Cup Qualification',
        'World Cup Qualifying', 'International Friendly', 'Friendly',
        'Friendlies', 'UEFA Nations League', 'Nations League',
        'UEFA Euro', 'European Championship', 'Copa America',
        'Copa América', 'AFC Asian Cup', 'Asian Cup',
        'Africa Cup of Nations', 'Africa Cup', 'CAF Africa Cup',
        'CONCACAF Gold Cup', 'Gold Cup', 'CONCACAF Nations League',
        'International',
    )
    excluded = (
        '女', 'U16', 'U17', 'U18', 'U19', 'U20', 'U21', 'U23',
        'Youth', 'Women', 'Libertadores', 'Sudamericana',
        'Champions League', 'Europa League', 'Conference League',
        '俱乐部', '解放者杯', '南球杯', '欧冠', '欧联', '欧协联',
    )
    include = " OR ".join([f"COALESCE({column}, '') LIKE ?" for _ in keywords])
    exclude = " OR ".join([f"COALESCE({column}, '') LIKE ?" for _ in excluded])
    params: List[Any] = [f"%{item}%" for item in keywords] + [f"%{item}%" for item in excluded]
    return f"AND ({include}) AND NOT ({exclude})", params


def _is_national_scope_match(match: Any) -> bool:
    if not isinstance(match, dict):
        return False
    league_text = ' '.join(
        str(match.get(key) or '')
        for key in ('league_name_cn', 'league_name_en', 'league_name', 'competition', 'competition_name')
    )
    if _is_national_competition_label(league_text):
        return True
    competition_type = str(match.get('competition_type') or '').strip().lower()
    participant_type = str(match.get('participant_type') or '').strip().lower()
    if competition_type == 'international' or participant_type == 'national':
        return True
    home_type = str(match.get('home_team_type') or '').strip().lower()
    away_type = str(match.get('away_team_type') or '').strip().lower()
    return bool(home_type == 'national' and away_type == 'national')


def _resolve_team_alias_ids(db_path: str, team_id: Any, name_hint: Any = None) -> List[Any]:
    if not db_path or team_id in (None, ''):
        team_id = None
    try:
        conn = sqlite3.connect(db_path, timeout=10)
        conn.row_factory = sqlite3.Row
        team_columns = {
            item['name']
            for item in conn.execute("PRAGMA table_info(teams)").fetchall()
        }
        base_columns = [
            'team_id', 'name_en', 'name_cn', 'sporttery_name_cn',
            'sporttery_name_en', 'oddsfe_name_cn', 'oddsfe_name_en',
            'oddsfe_team_id', 'sm_team_id',
        ]
        select_columns = [column for column in base_columns if column in team_columns]
        row = None
        if team_id is not None:
            row = conn.execute(f"""
                SELECT {', '.join(select_columns)}
                FROM teams
                WHERE team_id = ?
            """, (team_id,)).fetchone()

        row_dict = dict(row) if row else {}
        candidate_clauses = []
        params: List[Any] = []
        if team_id is not None:
            candidate_clauses.append("team_id = ?")
            params.append(team_id)
        for column in ('oddsfe_team_id', 'sm_team_id', 'name_en', 'name_cn', 'sporttery_name_cn', 'sporttery_name_en'):
            if column not in team_columns:
                continue
            value = row_dict.get(column)
            if value not in (None, ''):
                candidate_clauses.append(f"{column} = ?")
                params.append(value)

        hint = str(name_hint or '').strip()
        if hint:
            hint_bits = []
            for column in ('name_cn', 'sporttery_name_cn', 'oddsfe_name_cn', 'name_en', 'sporttery_name_en', 'oddsfe_name_en'):
                if column in team_columns:
                    hint_bits.append(f"{column} = ?")
                    params.append(hint)
            for column in ('name_cn', 'sporttery_name_cn', 'oddsfe_name_cn'):
                if column in team_columns:
                    hint_bits.append(f"({column} IS NOT NULL AND length({column}) >= 2 AND ? LIKE '%' || {column} || '%')")
                    params.append(hint)
            if 'name_cn_aliases' in team_columns:
                hint_bits.append("name_cn_aliases LIKE ?")
                params.append(f'%{hint}%')
            if hint_bits:
                candidate_clauses.append("(" + " OR ".join(hint_bits) + ")")

        if not candidate_clauses:
            conn.close()
            return []

        rows = conn.execute(f"""
            SELECT {', '.join(select_columns)}
            FROM teams
            WHERE {' OR '.join(candidate_clauses)}
        """, params).fetchall()
        conn.close()

        alias_ids: List[Any] = []
        for item in rows:
            labels = [
                item['name_en'] if 'name_en' in item.keys() else None,
                item['name_cn'] if 'name_cn' in item.keys() else None,
                item['sporttery_name_cn'] if 'sporttery_name_cn' in item.keys() else None,
                item['sporttery_name_en'] if 'sporttery_name_en' in item.keys() else None,
                item['oddsfe_name_cn'] if 'oddsfe_name_cn' in item.keys() else None,
                item['oddsfe_name_en'] if 'oddsfe_name_en' in item.keys() else None,
            ]
            if not all(_is_senior_team_label(label) for label in labels if label):
                continue
            alias_id = item['team_id']
            if alias_id not in alias_ids:
                alias_ids.append(alias_id)
        if team_id is not None and team_id not in alias_ids:
            alias_ids.insert(0, team_id)
        return alias_ids
    except Exception as exc:
        logger.debug('解析球队别名ID失败: %s', exc)
        return [team_id] if team_id is not None else []


def _team_phase_profile(
    db_path: str,
    team_id: Any,
    before_date: Any = None,
    limit: int = 20,
    name_hint: Any = None,
    national_scope: bool = False,
    use_fact_table: bool = True,
) -> dict:
    if not db_path or (team_id in (None, '') and not name_hint):
        return {}
    alias_ids = _resolve_team_alias_ids(db_path, team_id, name_hint)
    if not alias_ids:
        alias_ids = [team_id] if team_id not in (None, '') else []
    if not alias_ids:
        return {}
    placeholders = ','.join(['?'] * len(alias_ids))
    try:
        conn = sqlite3.connect(db_path, timeout=10)
        conn.row_factory = sqlite3.Row
        rows: List[dict] = []
        fact_rows: List[dict] = []

        fact_table = _national_reference_fact_table() if national_scope else 'team_match_facts'
        fact_exists = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
            (fact_table,),
        ).fetchone()
        if fact_exists and use_fact_table:
            fact_scope_filter = ''
            fact_scope_params: List[Any] = []
            if national_scope:
                fact_scope_filter, fact_scope_params = _national_competition_sql_filter('league_name_cn')
            fact_params: List[Any] = [str(item) for item in alias_ids] + fact_scope_params
            fact_date_filter = ''
            if before_date:
                fact_date_filter = "AND date(match_date) < date(?)"
                fact_params.append(str(before_date)[:10])
            fact_params.append(max(limit * 2, limit))
            fact_rows = conn.execute(f"""
                SELECT team_id, opponent_team_id, goals_for, goals_against,
                       goals_ht_for, goals_ht_against, total_goals, ht_total_goals,
                       shots_for, shots_against, shots_on_target_for,
                       shots_on_target_against, xg_for, xg_against,
                       match_date, source_name AS source, source_match_id,
                       1 AS team_oriented
                FROM {fact_table}
                WHERE team_id IN ({','.join(['?'] * len(alias_ids))})
                  AND goals_for IS NOT NULL AND goals_against IS NOT NULL
                  AND goals_ht_for IS NOT NULL AND goals_ht_against IS NOT NULL
                  {fact_scope_filter}
                  {fact_date_filter}
                ORDER BY date(match_date) DESC, source_match_id DESC
                LIMIT ?
            """, fact_params).fetchall()
            rows.extend(dict(row) for row in fact_rows)

        params: List[Any] = list(alias_ids) + list(alias_ids)
        history_scope_filter = ''
        history_join = ''
        if national_scope:
            history_join = 'LEFT JOIN leagues phase_l ON phase_l.league_id = matches.league_id'
            history_scope_filter, history_scope_params = _national_competition_sql_filter('phase_l.name_cn')
            params.extend(history_scope_params)
        date_filter = ''
        if before_date:
            date_filter = "AND date(match_date) < date(?)"
            params.append(str(before_date)[:10])
        if not fact_rows:
            params.append(max(limit * 2, limit))
            history_rows = conn.execute(f"""
                SELECT home_team_id, away_team_id, home_goals, away_goals,
                       home_goals_ht, away_goals_ht, match_date,
                       home_shots, away_shots, home_shots_target, away_shots_target,
                       home_xg, away_xg,
                       'matches' AS source
                FROM matches
                {history_join}
                WHERE (home_team_id IN ({placeholders}) OR away_team_id IN ({placeholders}))
                  AND home_goals IS NOT NULL AND away_goals IS NOT NULL
                  AND home_goals_ht IS NOT NULL AND away_goals_ht IS NOT NULL
                  {history_scope_filter}
                  {date_filter}
                ORDER BY date(match_date) DESC, match_id DESC
                LIMIT ?
            """, params).fetchall()

            rows.extend(dict(row) for row in history_rows)

        lottery_exists = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='lottery_results'"
        ).fetchone()
        if lottery_exists and not fact_rows:
            lottery_params: List[Any] = list(alias_ids) + list(alias_ids)
            lottery_scope_filter = ''
            lottery_scope_params: List[Any] = []
            if national_scope:
                lottery_scope_filter, lottery_scope_params = _national_competition_sql_filter('lm.league_name_cn')
                lottery_params.extend(lottery_scope_params)
            lottery_date_filter = ''
            if before_date:
                lottery_date_filter = "AND date(lm.match_date) < date(?)"
                lottery_params.append(str(before_date)[:10])
            lottery_params.append(max(limit * 2, limit))
            lottery_rows = conn.execute(f"""
                SELECT lm.home_team_id, lm.away_team_id,
                       lr.home_goals_ft AS home_goals,
                       lr.away_goals_ft AS away_goals,
                       lr.home_goals_ht, lr.away_goals_ht,
                       COALESCE(lm.beijing_time, lm.match_date) AS match_date,
                       'lottery_results' AS source
                FROM lottery_matches lm
                JOIN lottery_results lr ON lr.lottery_match_id = lm.lottery_match_id
                WHERE (lm.home_team_id IN ({placeholders}) OR lm.away_team_id IN ({placeholders}))
                  AND lr.home_goals_ft IS NOT NULL AND lr.away_goals_ft IS NOT NULL
                  AND lr.home_goals_ht IS NOT NULL AND lr.away_goals_ht IS NOT NULL
                  {lottery_scope_filter}
                  {lottery_date_filter}
                ORDER BY date(COALESCE(lm.beijing_time, lm.match_date)) DESC, lm.lottery_match_id DESC
                LIMIT ?
            """, lottery_params).fetchall()
            rows.extend(dict(row) for row in lottery_rows)
        conn.close()
    except Exception as exc:
        logger.debug('读取球队阶段进失球画像失败: %s', exc)
        return {}

    if not rows:
        return {}

    def sort_key(row: dict) -> str:
        return str(row.get('match_date') or '')

    # Keep the most recent rows and avoid double-counting the same imported match.
    deduped = []
    seen = set()
    for row in sorted(rows, key=sort_key, reverse=True):
        if row.get('team_oriented'):
            key = (
                'fact',
                str(row.get('team_id')),
                str(row.get('source')),
                str(row.get('source_match_id')),
            )
        else:
            key = (
                str(row.get('home_team_id')),
                str(row.get('away_team_id')),
                str(row.get('match_date'))[:10],
                int(row.get('home_goals') or 0),
                int(row.get('away_goals') or 0),
                int(row.get('home_goals_ht') or 0),
                int(row.get('away_goals_ht') or 0),
            )
        if key in seen:
            continue
        seen.add(key)
        deduped.append(row)
        if len(deduped) >= limit:
            break
    rows = deduped

    totals = {
        'ht_gf': 0.0, 'ht_ga': 0.0, 'ft_gf': 0.0, 'ft_ga': 0.0,
        'ht_scored': 0, 'ht_conceded': 0, 'ft_scored': 0, 'ft_conceded': 0,
        'ft_clean_sheet': 0, 'ft_blank': 0,
        'big_conceded': 0, 'big_scored': 0,
        'ht_zero_zero': 0, 'ht_under_1_5': 0, 'low_total': 0, 'high_total': 0,
        'shots_for': 0.0, 'shots_against': 0.0,
        'sot_for': 0.0, 'sot_against': 0.0,
        'xg_for': 0.0, 'xg_against': 0.0,
        'shot_rows': 0, 'sot_rows': 0, 'xg_rows': 0,
        'defense_collapse': 0, 'attack_spike': 0,
    }
    sources_used = {}
    alias_set = {str(item) for item in alias_ids}
    for row in rows:
        source_name = row.get('source') or 'unknown'
        sources_used[source_name] = sources_used.get(source_name, 0) + 1
        if row.get('team_oriented'):
            gf_ht = row.get('goals_ht_for')
            ga_ht = row.get('goals_ht_against')
            gf_ft = row.get('goals_for')
            ga_ft = row.get('goals_against')
            shots_for = row.get('shots_for')
            shots_against = row.get('shots_against')
            sot_for = row.get('shots_on_target_for')
            sot_against = row.get('shots_on_target_against')
            xg_for = row.get('xg_for')
            xg_against = row.get('xg_against')
        else:
            is_home = str(row.get('home_team_id')) in alias_set
            gf_ht = row.get('home_goals_ht') if is_home else row.get('away_goals_ht')
            ga_ht = row.get('away_goals_ht') if is_home else row.get('home_goals_ht')
            gf_ft = row.get('home_goals') if is_home else row.get('away_goals')
            ga_ft = row.get('away_goals') if is_home else row.get('home_goals')
            shots_for = row.get('home_shots') if is_home else row.get('away_shots')
            shots_against = row.get('away_shots') if is_home else row.get('home_shots')
            sot_for = row.get('home_shots_target') if is_home else row.get('away_shots_target')
            sot_against = row.get('away_shots_target') if is_home else row.get('home_shots_target')
            xg_for = row.get('home_xg') if is_home else row.get('away_xg')
            xg_against = row.get('away_xg') if is_home else row.get('home_xg')
        gf_ht = int(gf_ht or 0)
        ga_ht = int(ga_ht or 0)
        gf_ft = int(gf_ft or 0)
        ga_ft = int(ga_ft or 0)
        total_goals = gf_ft + ga_ft
        ht_total_goals = gf_ht + ga_ht
        totals['ht_gf'] += gf_ht
        totals['ht_ga'] += ga_ht
        totals['ft_gf'] += gf_ft
        totals['ft_ga'] += ga_ft
        totals['ht_scored'] += 1 if gf_ht > 0 else 0
        totals['ht_conceded'] += 1 if ga_ht > 0 else 0
        totals['ft_scored'] += 1 if gf_ft > 0 else 0
        totals['ft_conceded'] += 1 if ga_ft > 0 else 0
        totals['ft_clean_sheet'] += 1 if ga_ft == 0 else 0
        totals['ft_blank'] += 1 if gf_ft == 0 else 0
        totals['big_conceded'] += 1 if ga_ft >= 3 else 0
        totals['big_scored'] += 1 if gf_ft >= 3 else 0
        totals['ht_zero_zero'] += 1 if ht_total_goals == 0 else 0
        totals['ht_under_1_5'] += 1 if ht_total_goals <= 1 else 0
        totals['low_total'] += 1 if total_goals <= 2 else 0
        totals['high_total'] += 1 if total_goals >= 4 else 0

        try:
            shots_for_value = float(shots_for) if shots_for is not None else None
            shots_against_value = float(shots_against) if shots_against is not None else None
        except (TypeError, ValueError):
            shots_for_value = None
            shots_against_value = None
        if shots_for_value is not None and shots_against_value is not None:
            totals['shots_for'] += shots_for_value
            totals['shots_against'] += shots_against_value
            totals['shot_rows'] += 1

        try:
            sot_for_value = float(sot_for) if sot_for is not None else None
            sot_against_value = float(sot_against) if sot_against is not None else None
        except (TypeError, ValueError):
            sot_for_value = None
            sot_against_value = None
        if sot_for_value is not None and sot_against_value is not None:
            totals['sot_for'] += sot_for_value
            totals['sot_against'] += sot_against_value
            totals['sot_rows'] += 1

        try:
            xg_for_value = float(xg_for) if xg_for is not None else None
            xg_against_value = float(xg_against) if xg_against is not None else None
        except (TypeError, ValueError):
            xg_for_value = None
            xg_against_value = None
        if xg_for_value is not None and xg_against_value is not None:
            totals['xg_for'] += xg_for_value
            totals['xg_against'] += xg_against_value
            totals['xg_rows'] += 1

        defense_collapse = (
            ga_ft >= 3
            or (shots_against_value is not None and shots_against_value >= 16)
            or (sot_against_value is not None and sot_against_value >= 6)
            or (xg_against_value is not None and xg_against_value >= 2.2)
        )
        attack_spike = (
            gf_ft >= 3
            or (shots_for_value is not None and shots_for_value >= 16)
            or (sot_for_value is not None and sot_for_value >= 6)
            or (xg_for_value is not None and xg_for_value >= 2.2)
        )
        totals['defense_collapse'] += 1 if defense_collapse else 0
        totals['attack_spike'] += 1 if attack_spike else 0

    n = len(rows)
    def rate(key: str) -> float:
        return round(totals[key] / n, 4)

    def avg_stat(sum_key: str, count_key: str) -> Optional[float]:
        count = totals.get(count_key, 0)
        if not count:
            return None
        return round(totals[sum_key] / count, 3)

    return {
        'sample_size': n,
        'team_ids_used': alias_ids,
        'ht_avg_for': round(totals['ht_gf'] / n, 3),
        'ht_avg_against': round(totals['ht_ga'] / n, 3),
        'ft_avg_for': round(totals['ft_gf'] / n, 3),
        'ft_avg_against': round(totals['ft_ga'] / n, 3),
        'ht_score_rate': rate('ht_scored'),
        'ht_concede_rate': rate('ht_conceded'),
        'ft_score_rate': rate('ft_scored'),
        'ft_concede_rate': rate('ft_conceded'),
        'ft_clean_sheet_rate': rate('ft_clean_sheet'),
        'ft_blank_rate': rate('ft_blank'),
        'big_concede_rate': rate('big_conceded'),
        'big_score_rate': rate('big_scored'),
        'ht_zero_zero_rate': rate('ht_zero_zero'),
        'ht_under_1_5_rate': rate('ht_under_1_5'),
        'low_total_rate': rate('low_total'),
        'high_total_rate': rate('high_total'),
        'avg_shots_for': avg_stat('shots_for', 'shot_rows'),
        'avg_shots_against': avg_stat('shots_against', 'shot_rows'),
        'avg_sot_for': avg_stat('sot_for', 'sot_rows'),
        'avg_sot_against': avg_stat('sot_against', 'sot_rows'),
        'avg_xg_for': avg_stat('xg_for', 'xg_rows'),
        'avg_xg_against': avg_stat('xg_against', 'xg_rows'),
        'shot_sample_size': totals.get('shot_rows', 0),
        'xg_sample_size': totals.get('xg_rows', 0),
        'defense_collapse_rate': rate('defense_collapse'),
        'attack_spike_rate': rate('attack_spike'),
        'sources_used': sources_used,
        'source': 'team_match_facts' if fact_rows else 'matches_plus_lottery_recent_with_half_time',
        'national_scope': bool(national_scope),
    }


def _phase_probability_to_xg(probability: float) -> float:
    import math
    p = max(0.03, min(0.97, float(probability)))
    return -math.log(1 - p)


def _phase_profile_weight(sample_a: Any, sample_b: Any) -> float:
    try:
        sample = min(float(sample_a or 0), float(sample_b or 0))
    except (TypeError, ValueError):
        sample = 0.0
    if sample <= 0:
        return 0.0
    return max(0.0, min(0.32, 0.32 * min(sample, 16.0) / 16.0))


def _blend_phase_xg(base_xg: float, attack_rate: Optional[float], concede_rate: Optional[float], profile_weight: float = 0.32) -> float:
    if not isinstance(attack_rate, (int, float)) or not isinstance(concede_rate, (int, float)):
        return base_xg
    if profile_weight <= 0:
        return base_xg
    profile_prob = (float(attack_rate) * 0.58) + (float(concede_rate) * 0.42)
    profile_xg = _phase_probability_to_xg(profile_prob)
    blended = (base_xg * (1 - profile_weight)) + (profile_xg * profile_weight)
    return max(0.05, min(2.8, blended))


def _load_bqc_phase_profile(
    db_path: str,
    match: dict,
    national_scope_override: Optional[bool] = None,
    use_fact_table: bool = True,
) -> dict:
    if not db_path or not isinstance(match, dict):
        return {}
    before_date = match.get('match_date') or match.get('beijing_time')
    national_scope = (
        bool(national_scope_override)
        if national_scope_override is not None
        else _is_national_scope_match(match)
    )
    home_profile = _team_phase_profile(
        db_path,
        match.get('home_team_id'),
        before_date,
        name_hint=match.get('home_team_cn') or match.get('home_team') or match.get('home_team_name'),
        national_scope=national_scope,
        use_fact_table=use_fact_table,
    )
    away_profile = _team_phase_profile(
        db_path,
        match.get('away_team_id'),
        before_date,
        name_hint=match.get('away_team_cn') or match.get('away_team') or match.get('away_team_name'),
        national_scope=national_scope,
        use_fact_table=use_fact_table,
    )
    if not home_profile and not away_profile:
        return {}
    home_ht_weight = _phase_profile_weight(
        home_profile.get('sample_size') if home_profile else 0,
        away_profile.get('sample_size') if away_profile else 0,
    )
    away_ht_weight = _phase_profile_weight(
        away_profile.get('sample_size') if away_profile else 0,
        home_profile.get('sample_size') if home_profile else 0,
    )
    return {
        'home': home_profile,
        'away': away_profile,
        'home_ht_weight': round(home_ht_weight, 4),
        'away_ht_weight': round(away_ht_weight, 4),
        'source': 'matches_plus_lottery_recent_with_half_time',
        'national_scope': bool(national_scope),
        'scope_label': 'national_team_competitions' if national_scope else 'all_competitions',
        'sources_used': {
            'home': home_profile.get('sources_used') if home_profile else {},
            'away': away_profile.get('sources_used') if away_profile else {},
        },
        'sample_quality': (
            'low' if min(home_profile.get('sample_size', 0) if home_profile else 0,
                         away_profile.get('sample_size', 0) if away_profile else 0) < 8
            else 'ok'
        ),
        'home_ht_score_signal': round(
            (home_profile.get('ht_score_rate', 0) * 0.58) + (away_profile.get('ht_concede_rate', 0) * 0.42),
            4
        ) if home_profile and away_profile else None,
        'away_ht_score_signal': round(
            (away_profile.get('ht_score_rate', 0) * 0.58) + (home_profile.get('ht_concede_rate', 0) * 0.42),
            4
        ) if home_profile and away_profile else None,
        'home_ft_score_signal': round(
            (home_profile.get('ft_score_rate', 0) * 0.58) + (away_profile.get('ft_concede_rate', 0) * 0.42),
            4
        ) if home_profile and away_profile else None,
        'away_ft_score_signal': round(
            (away_profile.get('ft_score_rate', 0) * 0.58) + (home_profile.get('ft_concede_rate', 0) * 0.42),
            4
        ) if home_profile and away_profile else None,
    }


def _compact_phase_profile_reference(profile: dict) -> dict:
    if not isinstance(profile, dict) or not profile:
        return {}
    home = profile.get('home') if isinstance(profile.get('home'), dict) else {}
    away = profile.get('away') if isinstance(profile.get('away'), dict) else {}
    return {
        'source': profile.get('source'),
        'national_scope': profile.get('national_scope'),
        'scope_label': profile.get('scope_label'),
        'sample_quality': profile.get('sample_quality'),
        'home_sample': home.get('sample_size'),
        'away_sample': away.get('sample_size'),
        'home_signal': {
            'ht_score': profile.get('home_ht_score_signal'),
            'ft_score': profile.get('home_ft_score_signal'),
            'ft_avg_for': home.get('ft_avg_for'),
            'ft_avg_against': home.get('ft_avg_against'),
            'high_total_rate': home.get('high_total_rate'),
            'low_total_rate': home.get('low_total_rate'),
        },
        'away_signal': {
            'ht_score': profile.get('away_ht_score_signal'),
            'ft_score': profile.get('away_ft_score_signal'),
            'ft_avg_for': away.get('ft_avg_for'),
            'ft_avg_against': away.get('ft_avg_against'),
            'high_total_rate': away.get('high_total_rate'),
            'low_total_rate': away.get('low_total_rate'),
        },
    }


def _bounded_goal_delta(base_value: float, target_value: float, max_delta: float) -> float:
    delta = float(target_value) - float(base_value)
    delta = max(-max_delta, min(max_delta, delta))
    return round(max(0.05, min(5.5, float(base_value) + delta)), 3)


def _profile_goal_signal(attack_profile: dict, defense_profile: dict) -> Optional[float]:
    if not attack_profile or not defense_profile:
        return None
    attack_avg = _to_float(attack_profile.get('ft_avg_for'), None)
    defense_avg = _to_float(defense_profile.get('ft_avg_against'), None)
    if attack_avg is None or defense_avg is None:
        return None
    signal = (attack_avg * 0.62) + (defense_avg * 0.38)
    signal += max(0.0, _to_float(attack_profile.get('big_score_rate'), 0.0) - 0.25) * 0.28
    signal += max(0.0, _to_float(defense_profile.get('big_concede_rate'), 0.0) - 0.15) * 0.24
    signal -= max(0.0, _to_float(defense_profile.get('ft_clean_sheet_rate'), 0.0) - 0.34) * 0.22
    signal -= max(0.0, _to_float(attack_profile.get('ft_blank_rate'), 0.0) - 0.28) * 0.18
    return round(max(0.12, min(4.8, signal)), 3)


def _profile_from_goal_fact_rows(rows: List[dict]) -> dict:
    usable = []
    for row in rows or []:
        gf = _to_float(row.get('goals_for'), None)
        ga = _to_float(row.get('goals_against'), None)
        if gf is None or ga is None:
            continue
        usable.append({'gf': gf, 'ga': ga})
    n = len(usable)
    if n <= 0:
        return {}

    def rate(fn) -> float:
        return round(sum(1 for item in usable if fn(item)) / n, 4)

    return {
        'sample_size': n,
        'ft_avg_for': round(sum(item['gf'] for item in usable) / n, 3),
        'ft_avg_against': round(sum(item['ga'] for item in usable) / n, 3),
        'ft_score_rate': rate(lambda item: item['gf'] > 0),
        'ft_concede_rate': rate(lambda item: item['ga'] > 0),
        'ft_clean_sheet_rate': rate(lambda item: item['ga'] == 0),
        'ft_blank_rate': rate(lambda item: item['gf'] == 0),
        'big_score_rate': rate(lambda item: item['gf'] >= 3),
        'big_concede_rate': rate(lambda item: item['ga'] >= 3),
        'high_total_rate': rate(lambda item: item['gf'] + item['ga'] >= 4),
        'low_total_rate': rate(lambda item: item['gf'] + item['ga'] <= 2),
    }


def _load_national_goal_fact_profile(
    db_path: str,
    team_id: Any,
    before_date: Any,
    name_hint: Any = None,
    limit: int = 20,
) -> dict:
    if not db_path or (team_id in (None, '') and not name_hint):
        return {}
    alias_ids = _resolve_team_alias_ids(db_path, team_id, name_hint)
    if not alias_ids and team_id not in (None, ''):
        alias_ids = [team_id]
    if not alias_ids:
        return {}

    fact_table = _national_reference_fact_table()
    placeholders = ','.join(['?'] * len(alias_ids))
    try:
        conn = sqlite3.connect(db_path, timeout=10)
        conn.row_factory = sqlite3.Row
        exists = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
            (fact_table,),
        ).fetchone()
        if not exists:
            conn.close()
            return {}
        fact_columns = {
            row['name']
            for row in conn.execute(f"PRAGMA table_info({fact_table})").fetchall()
        }
        required = {'team_id', 'goals_for', 'goals_against', 'match_date'}
        if not required.issubset(fact_columns):
            conn.close()
            return {}

        params: List[Any] = [str(item) for item in alias_ids]
        scope_filter = ''
        if 'league_name_cn' in fact_columns:
            scope_filter, scope_params = _national_competition_sql_filter('league_name_cn')
            params.extend(scope_params)
        date_filter = ''
        if before_date:
            date_filter = "AND date(match_date) < date(?)"
            params.append(str(before_date)[:10])
        source_order = ', source_match_id DESC' if 'source_match_id' in fact_columns else ''
        params.append(max(limit * 2, limit))
        rows = conn.execute(f"""
            SELECT team_id, goals_for, goals_against, match_date
            FROM {fact_table}
            WHERE team_id IN ({placeholders})
              AND goals_for IS NOT NULL AND goals_against IS NOT NULL
              {scope_filter}
              {date_filter}
            ORDER BY date(match_date) DESC{source_order}
            LIMIT ?
        """, params).fetchall()
        conn.close()
    except Exception as exc:
        logger.debug('load national goal fact profile failed: %s', exc)
        return {}

    seen = set()
    deduped: List[dict] = []
    for row in rows:
        item = dict(row)
        key = (
            str(item.get('team_id')),
            str(item.get('match_date'))[:10],
            str(item.get('goals_for')),
            str(item.get('goals_against')),
        )
        if key in seen:
            continue
        seen.add(key)
        deduped.append(item)
        if len(deduped) >= limit:
            break
    profile = _profile_from_goal_fact_rows(deduped)
    if profile:
        profile['source'] = fact_table
        profile['team_ids_used'] = alias_ids
    return profile


def _national_ou_reference_signal(db_path: str, match: dict, line: Any) -> dict:
    if not db_path or not isinstance(match, dict):
        return {}
    if not _is_national_scope_match(match):
        return {'eligible': False, 'reason': 'not_national_scope'}

    line_value = _to_float(line, None)
    if line_value is None:
        return {'eligible': False, 'reason': 'missing_ou_line'}

    limit = _env_int('FOOTBALL_NATIONAL_OU_REFERENCE_LIMIT', 20, 8, 60)
    min_sample = _env_int('FOOTBALL_NATIONAL_OU_MIN_SAMPLE', 16, 4, 60)
    band = _env_float('FOOTBALL_NATIONAL_OU_CONFLICT_BAND', 0.25, 0.0, 1.5)
    before_date = match.get('match_date') or match.get('beijing_time')
    home_profile = _load_national_goal_fact_profile(
        db_path,
        match.get('home_team_id'),
        before_date,
        name_hint=match.get('home_team_cn') or match.get('home_team') or match.get('home_team_name'),
        limit=limit,
    )
    away_profile = _load_national_goal_fact_profile(
        db_path,
        match.get('away_team_id'),
        before_date,
        name_hint=match.get('away_team_cn') or match.get('away_team') or match.get('away_team_name'),
        limit=limit,
    )
    if not home_profile or not away_profile:
        return {
            'eligible': False,
            'reason': 'missing_team_profile',
            'source_table': _national_reference_fact_table(),
            'home_sample': home_profile.get('sample_size') if home_profile else 0,
            'away_sample': away_profile.get('sample_size') if away_profile else 0,
        }

    home_signal = _profile_goal_signal(home_profile, away_profile)
    away_signal = _profile_goal_signal(away_profile, home_profile)
    min_actual_sample = min(int(home_profile.get('sample_size') or 0), int(away_profile.get('sample_size') or 0))
    if home_signal is None or away_signal is None:
        return {
            'eligible': False,
            'reason': 'missing_signal',
            'source_table': _national_reference_fact_table(),
            'home_sample': home_profile.get('sample_size'),
            'away_sample': away_profile.get('sample_size'),
        }
    total_signal = round(home_signal + away_signal, 3)
    gap = round(total_signal - float(line_value), 3)
    if min_actual_sample < min_sample:
        side = None
        reason = 'insufficient_sample'
        eligible = False
    elif gap >= band:
        side = 'over'
        reason = 'above_line_band'
        eligible = True
    elif gap <= -band:
        side = 'under'
        reason = 'below_line_band'
        eligible = True
    else:
        side = None
        reason = 'inside_neutral_band'
        eligible = False

    return {
        'eligible': eligible,
        'reason': reason,
        'side': side,
        'line': round(float(line_value), 3),
        'band': band,
        'total_signal': total_signal,
        'total_gap': gap,
        'home_signal': home_signal,
        'away_signal': away_signal,
        'home_sample': home_profile.get('sample_size'),
        'away_sample': away_profile.get('sample_size'),
        'min_sample_required': min_sample,
        'source_table': _national_reference_fact_table(),
        'home_profile': {
            'ft_avg_for': home_profile.get('ft_avg_for'),
            'ft_avg_against': home_profile.get('ft_avg_against'),
            'high_total_rate': home_profile.get('high_total_rate'),
            'low_total_rate': home_profile.get('low_total_rate'),
            'big_score_rate': home_profile.get('big_score_rate'),
            'big_concede_rate': home_profile.get('big_concede_rate'),
            'clean_sheet_rate': home_profile.get('ft_clean_sheet_rate'),
            'blank_rate': home_profile.get('ft_blank_rate'),
        },
        'away_profile': {
            'ft_avg_for': away_profile.get('ft_avg_for'),
            'ft_avg_against': away_profile.get('ft_avg_against'),
            'high_total_rate': away_profile.get('high_total_rate'),
            'low_total_rate': away_profile.get('low_total_rate'),
            'big_score_rate': away_profile.get('big_score_rate'),
            'big_concede_rate': away_profile.get('big_concede_rate'),
            'clean_sheet_rate': away_profile.get('ft_clean_sheet_rate'),
            'blank_rate': away_profile.get('ft_blank_rate'),
        },
    }


def _goal_profile_weight(home_sample: Any, away_sample: Any) -> float:
    try:
        sample = min(float(home_sample or 0), float(away_sample or 0))
    except (TypeError, ValueError):
        sample = 0.0
    if sample < 3:
        return 0.0
    if sample < 8:
        return 0.08
    return round(max(0.10, min(0.20, 0.10 + min(sample, 20.0) / 20.0 * 0.10)), 4)


def _apply_goal_profile_adjustment(db_path: str, match: dict, result: dict) -> None:
    """Adjust expected goals with pre-match team facts.

    The adjustment is deliberately bounded. It does not change the SPF axis
    directly; it only gives total-goals, margins, half/full and score candidates
    a better shared matrix when enough prior team facts exist.
    """
    if not db_path or not isinstance(match, dict) or not isinstance(result, dict):
        return
    final_prediction = result.get('final_prediction') if isinstance(result.get('final_prediction'), dict) else {}
    expected = final_prediction.get('expected_score') if isinstance(final_prediction.get('expected_score'), dict) else {}
    home_base = _to_float(expected.get('home'), None)
    away_base = _to_float(expected.get('away'), None)
    if home_base is None or away_base is None:
        return

    # Keep the accepted goal-matrix adjustment on the broad historical fact
    # profile. For national-team matches, load a separate national-only
    # reference so it can explain/learn without replacing the calibrated path.
    phase_profile = _load_bqc_phase_profile(
        db_path,
        match,
        national_scope_override=False,
        use_fact_table=False,
    )
    national_reference = (
        _compact_phase_profile_reference(
            _load_bqc_phase_profile(
                db_path,
                match,
                national_scope_override=True,
                use_fact_table=True,
            )
        )
        if _is_national_scope_match(match)
        else {}
    )
    home_profile = phase_profile.get('home') if isinstance(phase_profile.get('home'), dict) else {}
    away_profile = phase_profile.get('away') if isinstance(phase_profile.get('away'), dict) else {}
    if not home_profile or not away_profile:
        return

    weight = _goal_profile_weight(home_profile.get('sample_size'), away_profile.get('sample_size'))
    if weight <= 0:
        result['goal_profile_adjustment'] = {
            'applied': False,
            'reason': 'insufficient_sample',
            'home_sample': home_profile.get('sample_size'),
            'away_sample': away_profile.get('sample_size'),
            'source': phase_profile.get('source'),
            'national_scope': phase_profile.get('national_scope'),
            'scope_label': phase_profile.get('scope_label'),
            'national_reference': national_reference or None,
        }
        return

    home_signal = _profile_goal_signal(home_profile, away_profile)
    away_signal = _profile_goal_signal(away_profile, home_profile)
    if home_signal is None or away_signal is None:
        return

    if (
        phase_profile.get('national_scope')
        and _env_float('FOOTBALL_NATIONAL_GOAL_PROFILE_ADJUSTMENT_ENABLED', 0.0, 0.0, 1.0) < 1.0
    ):
        result['goal_profile_adjustment'] = {
            'applied': False,
            'reason': 'national_scope_diagnostic_only',
            'raw_expected_score': {'home': round(home_base, 3), 'away': round(away_base, 3)},
            'profile_signal': {'home': home_signal, 'away': away_signal},
            'weight': weight,
            'home_sample': home_profile.get('sample_size'),
            'away_sample': away_profile.get('sample_size'),
            'source': phase_profile.get('source'),
            'national_scope': phase_profile.get('national_scope'),
            'scope_label': phase_profile.get('scope_label'),
            'national_reference': national_reference or None,
            'home_profile': {
                'ft_avg_for': home_profile.get('ft_avg_for'),
                'ft_avg_against': home_profile.get('ft_avg_against'),
                'ft_score_rate': home_profile.get('ft_score_rate'),
                'ft_concede_rate': home_profile.get('ft_concede_rate'),
                'ft_clean_sheet_rate': home_profile.get('ft_clean_sheet_rate'),
                'ft_blank_rate': home_profile.get('ft_blank_rate'),
                'big_score_rate': home_profile.get('big_score_rate'),
                'big_concede_rate': home_profile.get('big_concede_rate'),
                'high_total_rate': home_profile.get('high_total_rate'),
                'low_total_rate': home_profile.get('low_total_rate'),
            },
            'away_profile': {
                'ft_avg_for': away_profile.get('ft_avg_for'),
                'ft_avg_against': away_profile.get('ft_avg_against'),
                'ft_score_rate': away_profile.get('ft_score_rate'),
                'ft_concede_rate': away_profile.get('ft_concede_rate'),
                'ft_clean_sheet_rate': away_profile.get('ft_clean_sheet_rate'),
                'ft_blank_rate': away_profile.get('ft_blank_rate'),
                'big_score_rate': away_profile.get('big_score_rate'),
                'big_concede_rate': away_profile.get('big_concede_rate'),
                'high_total_rate': away_profile.get('high_total_rate'),
                'low_total_rate': away_profile.get('low_total_rate'),
            },
        }
        return

    blended_home = (home_base * (1 - weight)) + (home_signal * weight)
    blended_away = (away_base * (1 - weight)) + (away_signal * weight)
    max_delta = 0.24 if weight <= 0.10 else 0.38
    adjusted_home = _bounded_goal_delta(home_base, blended_home, max_delta)
    adjusted_away = _bounded_goal_delta(away_base, blended_away, max_delta)
    if abs(adjusted_home - home_base) < 0.035 and abs(adjusted_away - away_base) < 0.035:
        result['goal_profile_adjustment'] = {
            'applied': False,
            'reason': 'below_delta_threshold',
            'raw_expected_score': {'home': round(home_base, 3), 'away': round(away_base, 3)},
            'profile_signal': {'home': home_signal, 'away': away_signal},
            'weight': weight,
            'source': phase_profile.get('source'),
            'national_scope': phase_profile.get('national_scope'),
            'scope_label': phase_profile.get('scope_label'),
            'national_reference': national_reference or None,
        }
        return

    final_prediction['expected_score'] = {'home': adjusted_home, 'away': adjusted_away}
    poisson = (result.get('base_prediction') or {}).get('poisson')
    if isinstance(poisson, dict):
        poisson['profile_adjusted_expected_score'] = {'home': adjusted_home, 'away': adjusted_away}
    result['goal_profile_adjustment'] = {
        'applied': True,
        'source': phase_profile.get('source'),
        'national_scope': phase_profile.get('national_scope'),
        'scope_label': phase_profile.get('scope_label'),
        'national_reference': national_reference or None,
        'weight': weight,
        'raw_expected_score': {'home': round(home_base, 3), 'away': round(away_base, 3)},
        'adjusted_expected_score': {'home': adjusted_home, 'away': adjusted_away},
        'profile_signal': {'home': home_signal, 'away': away_signal},
        'home_sample': home_profile.get('sample_size'),
        'away_sample': away_profile.get('sample_size'),
        'home_profile': {
            'ft_avg_for': home_profile.get('ft_avg_for'),
            'ft_avg_against': home_profile.get('ft_avg_against'),
            'ft_score_rate': home_profile.get('ft_score_rate'),
            'ft_concede_rate': home_profile.get('ft_concede_rate'),
            'ft_clean_sheet_rate': home_profile.get('ft_clean_sheet_rate'),
            'ft_blank_rate': home_profile.get('ft_blank_rate'),
            'big_score_rate': home_profile.get('big_score_rate'),
            'big_concede_rate': home_profile.get('big_concede_rate'),
            'high_total_rate': home_profile.get('high_total_rate'),
            'low_total_rate': home_profile.get('low_total_rate'),
        },
        'away_profile': {
            'ft_avg_for': away_profile.get('ft_avg_for'),
            'ft_avg_against': away_profile.get('ft_avg_against'),
            'ft_score_rate': away_profile.get('ft_score_rate'),
            'ft_concede_rate': away_profile.get('ft_concede_rate'),
            'ft_clean_sheet_rate': away_profile.get('ft_clean_sheet_rate'),
            'ft_blank_rate': away_profile.get('ft_blank_rate'),
            'big_score_rate': away_profile.get('big_score_rate'),
            'big_concede_rate': away_profile.get('big_concede_rate'),
            'high_total_rate': away_profile.get('high_total_rate'),
            'low_total_rate': away_profile.get('low_total_rate'),
        },
    }


def _infer_bqc_scene(match: dict) -> str:
    """从match字段推断scenario_type — 与_analysis_scenario_type对齐但更简单"""
    league_text = ' '.join(
        str((match or {}).get(key) or '')
        for key in ('league_name_cn', 'league_name_en', 'league_name', 'competition', 'competition_name')
    )
    if any(t in league_text for t in ('友谊', '国际赛')):
        return 'friendly_intl'
    if any(t in league_text for t in ('世预', '欧预', '非预', '亚预', '南美预')):
        return 'qualifier'
    if '欧洲联' in league_text:
        return 'nations_league'
    if (any(t in league_text for t in ('世界杯', '欧洲杯', '亚洲杯', '美洲杯', '非洲杯'))
            or 'world cup' in league_text.lower()
            or 'euro' in league_text.lower()
            or 'copa america' in league_text.lower()):
        return 'international_cup'
    if any(t in league_text for t in ('欧冠', '欧联', '欧协', '解放者', '亚冠')):
        return 'continental_cup'
    if '杯' in league_text:
        return 'domestic_cup'
    return 'league'


def _load_scene_ht_transition(db_path: str, scene: str) -> Optional[dict]:
    """从model_params_history加载scene-specific HT→FT transition matrix

    Returns: {'h': {'h': p, 'd': p, 'a': p}, 'd': {...}, 'a': {...}} 或 None
    """
    if not db_path or not scene:
        return None
    try:
        import sqlite3, json
        conn = sqlite3.connect(db_path)
        try:
            row = conn.execute("""
                SELECT new_value FROM model_params_history
                WHERE param_name = ?
                ORDER BY changed_at DESC LIMIT 1
            """, (f'bqc_ht_transition_{scene}_attribution',)).fetchone()
            if row and row[0]:
                data = json.loads(row[0])
                # 必须三个key都有
                if all(k in data for k in ('h', 'd', 'a')):
                    return {k: data[k] for k in ('h', 'd', 'a')}
        finally:
            conn.close()
    except Exception:
        pass
    return None


def _load_scene_ou_lambda_scale(db_path: str, scene: str) -> float:
    """从model_params_history加载scene-specific OU lambda缩放因子

    Returns: scale (默认1.0, 范围0.80-1.20)
    """
    if not db_path or not scene:
        return 1.0
    try:
        import sqlite3
        conn = sqlite3.connect(db_path)
        try:
            row = conn.execute("""
                SELECT new_value FROM model_params_history
                WHERE param_name = ?
                ORDER BY changed_at DESC LIMIT 1
            """, (f'ou_lambda_scale_{scene}_attribution',)).fetchone()
            if row and row[0]:
                scale = float(row[0])
                if 0.5 <= scale <= 1.5:
                    return scale
        finally:
            conn.close()
    except Exception:
        pass
    return 1.0


def _compute_bqc(
    score_matrix,
    match: dict = None,
    db_path: str = None,
    full_time_axis: str = None,
    axis_context: Optional[dict] = None,
) -> dict:
    """半全场 — 阶段进失球画像 + Poisson比分矩阵推算

    9种结果: hh/hd/ha/dh/dd/da/ah/ad/aa
    h=主胜(3), d=平(1), a=客胜(0)
    """
    import math

    # 从全场矩阵反推xG
    norm = _normalize_matrix(score_matrix)
    total_home = 0.0
    total_away = 0.0
    for i, row in enumerate(norm):
        for j, prob in enumerate(row):
            total_home += i * prob
            total_away += j * prob

    # 半场xG — 按全场总进球量动态调整占比
    # Empirical: FT_total=1 → 0.565, FT_total=2 → 0.465, FT_total=3 → 0.388, FT_total=4 → 0.388
    # 高进球场次下半场占比更高, 固定0.45会高估半场领先概率导致过度预测33
    total_goals_xg = total_home + total_away
    if total_goals_xg <= 1.5:
        _ht_ratio = 0.50
    elif total_goals_xg <= 2.5:
        _ht_ratio = 0.45
    elif total_goals_xg <= 3.5:
        _ht_ratio = 0.40
    else:
        _ht_ratio = 0.38
    half_home_xg = total_home * _ht_ratio
    half_away_xg = total_away * _ht_ratio
    phase_profile = _load_bqc_phase_profile(db_path, match or {}) if _bqc_phase_profile_enabled() and db_path and match else {}
    if phase_profile:
        home_phase = phase_profile.get('home') or {}
        away_phase = phase_profile.get('away') or {}
        half_home_xg = _blend_phase_xg(
            half_home_xg,
            home_phase.get('ht_score_rate'),
            away_phase.get('ht_concede_rate'),
            phase_profile.get('home_ht_weight', 0.32),
        )
        half_away_xg = _blend_phase_xg(
            half_away_xg,
            away_phase.get('ht_score_rate'),
            home_phase.get('ht_concede_rate'),
            phase_profile.get('away_ht_weight', 0.32),
        )

    # 生成半场Poisson比分矩阵
    max_g = 4
    half_matrix = []
    for i in range(max_g):
        row = []
        for j in range(max_g):
            p = (math.exp(-half_home_xg) * half_home_xg**i / math.factorial(i) *
                 math.exp(-half_away_xg) * half_away_xg**j / math.factorial(j))
            row.append(p)
        half_matrix.append(row)

    # 半场胜平负概率
    half_home = sum(half_matrix[i][j] for i in range(max_g) for j in range(max_g) if i > j)
    half_draw = sum(half_matrix[i][j] for i in range(max_g) for j in range(max_g) if i == j)
    half_away = sum(half_matrix[i][j] for i in range(max_g) for j in range(max_g) if i < j)
    half_matrix_mass = sum(sum(row) for row in half_matrix)
    half_zero_zero = (half_matrix[0][0] / half_matrix_mass) if half_matrix_mass > 0 else 0.0
    half_under_1_5 = (
        sum(half_matrix[i][j] for i in range(max_g) for j in range(max_g) if i + j <= 1) / half_matrix_mass
        if half_matrix_mass > 0 else 0.0
    )
    low_tempo_half = half_zero_zero >= 0.34 or half_under_1_5 >= 0.70
    half_total = half_home + half_draw + half_away
    if half_total > 0:
        half_home /= half_total
        half_draw /= half_total
        half_away /= half_total

    # 全场胜平负概率(从归一化矩阵)
    full_home = 0.0
    full_draw = 0.0
    full_away = 0.0
    for i, row in enumerate(norm):
        for j, prob in enumerate(row):
            if i > j:
                full_home += prob
            elif i == j:
                full_draw += prob
            else:
                full_away += prob

    # BQC = P(半场X) × P(全场Y|半场X)  (empirical transition matrix)
    # Empirical P(FT|HT) from 30K matches:
    #   HT=3(主胜): FT=3 77.6%, FT=1 15.9%, FT=0 6.5%
    #   HT=1(平局): FT=3 34.9%, FT=1 40.1%, FT=0 25.1%
    #   HT=0(客胜): FT=3 11.1%, FT=1 20.9%, FT=0 68.0%
    _EMPIRICAL_TRANSITION = {
        'h': {'h': 0.776, 'd': 0.159, 'a': 0.065},
        'd': {'h': 0.349, 'd': 0.401, 'a': 0.251},
        'a': {'h': 0.111, 'd': 0.209, 'a': 0.680},
    }
    # 归因驱动: 若该场景有lottery_validation重算的transition, 优先使用
    try:
        _bqc_scene = _infer_bqc_scene(match or {})
        _scene_transition = _load_scene_ht_transition(db_path, _bqc_scene)
        if _scene_transition:
            _EMPIRICAL_TRANSITION = _scene_transition
    except Exception:
        pass
    bqc_raw = {
        'hh': half_home * _EMPIRICAL_TRANSITION['h']['h'],
        'hd': half_home * _EMPIRICAL_TRANSITION['h']['d'],
        'ha': half_home * _EMPIRICAL_TRANSITION['h']['a'],
        'dh': half_draw * _EMPIRICAL_TRANSITION['d']['h'],
        'dd': half_draw * _EMPIRICAL_TRANSITION['d']['d'],
        'da': half_draw * _EMPIRICAL_TRANSITION['d']['a'],
        'ah': half_away * _EMPIRICAL_TRANSITION['a']['h'],
        'ad': half_away * _EMPIRICAL_TRANSITION['a']['d'],
        'aa': half_away * _EMPIRICAL_TRANSITION['a']['a'],
    }
    bqc_method = 'empirical_transition'
    if _env_float('FOOTBALL_BQC_JOINT_PATH_ENABLED', 0.0, 0.0, 1.0) >= 1.0:
        def result_key(home_goals: int, away_goals: int) -> str:
            if home_goals > away_goals:
                return 'h'
            if home_goals < away_goals:
                return 'a'
            return 'd'

        def poisson_distribution(lam: float, size: int) -> List[float]:
            lam = max(0.03, min(float(lam or 0.0), 7.5))
            values = [math.exp(-lam) * lam**goals / math.factorial(goals) for goals in range(size)]
            total = sum(values)
            return [value / total for value in values] if total > 0 else values

        second_home_xg = max(0.05, total_home - half_home_xg)
        second_away_xg = max(0.05, total_away - half_away_xg)
        ht_home_dist = poisson_distribution(half_home_xg, 5)
        ht_away_dist = poisson_distribution(half_away_xg, 5)
        st_home_dist = poisson_distribution(second_home_xg, 7)
        st_away_dist = poisson_distribution(second_away_xg, 7)
        bqc_raw = {key: 0.0 for key in ('hh', 'hd', 'ha', 'dh', 'dd', 'da', 'ah', 'ad', 'aa')}
        for ht_home_goals, ht_home_prob in enumerate(ht_home_dist):
            for ht_away_goals, ht_away_prob in enumerate(ht_away_dist):
                ht_key = result_key(ht_home_goals, ht_away_goals)
                ht_prob = ht_home_prob * ht_away_prob
                for st_home_goals, st_home_prob in enumerate(st_home_dist):
                    for st_away_goals, st_away_prob in enumerate(st_away_dist):
                        ft_key = result_key(ht_home_goals + st_home_goals, ht_away_goals + st_away_goals)
                        bqc_raw[ht_key + ft_key] += ht_prob * st_home_prob * st_away_prob
        bqc_method = 'joint_half_second_path'

    # 归一化
    total_bqc = sum(bqc_raw.values())
    bqc_probs = {}
    if total_bqc > 0:
        for k in bqc_raw:
            bqc_probs[k] = round(bqc_raw[k] / total_bqc, 3)

    # 推荐：半全场是全场方向的路径推导，先在胜平负主轴内择优。
    # 始终约束到SPF全场方向(数据验证: always-axis=35.8% vs gated-axis=34.2%)
    axis_enabled = _env_float('FOOTBALL_BQC_SPF_AXIS_ENABLED', 1.0, 0.0, 1.0) >= 1.0
    axis_target = {'3': 'h', '1': 'd', '0': 'a'}.get(str(full_time_axis or '')) if axis_enabled else ''
    constrained_probs = {
        key: value
        for key, value in bqc_probs.items()
        if axis_target and isinstance(key, str) and len(key) == 2 and key[1] == axis_target
    }
    rec_pool = constrained_probs or bqc_probs
    rec = max(rec_pool, key=rec_pool.get) if rec_pool else 'dd'
    phase_axis_adjustment = None
    if axis_target and constrained_probs:
        half_axis_probs = {'h': half_home, 'd': half_draw, 'a': half_away}
        same_half = half_axis_probs.get(axis_target, 0.0)
        draw_half = half_axis_probs.get('d', 0.0)
        opposite = {'h': 'a', 'a': 'h', 'd': 'd'}.get(axis_target, 'd')
        opposite_half = half_axis_probs.get(opposite, 0.0)
        preferred_half = axis_target
        if axis_target == 'h':
            if low_tempo_half and draw_half >= same_half * 0.82:
                preferred_half = 'd'
            elif draw_half >= same_half + 0.035:
                preferred_half = 'd'
            elif opposite_half >= same_half + 0.10 and opposite_half >= draw_half + 0.04:
                preferred_half = opposite
        elif axis_target == 'a':
            if draw_half >= same_half + 0.035:
                preferred_half = 'd'
            elif opposite_half >= same_half + 0.10 and opposite_half >= draw_half + 0.04:
                preferred_half = opposite
        elif axis_target == 'd':
            if half_home >= draw_half + 0.08:
                preferred_half = 'h'
            elif half_away >= draw_half + 0.08:
                preferred_half = 'a'
        phase_candidate = f'{preferred_half}{axis_target}'
        if phase_candidate in constrained_probs and phase_candidate != rec:
            max_constrained = max(constrained_probs.values()) if constrained_probs else 0.0
            min_candidate_ratio = (
                _env_float('FOOTBALL_BQC_PHASE_MIN_RATIO_AWAY', 1.0, 0.0, 1.5)
                if axis_target == 'a'
                else _env_float('FOOTBALL_BQC_PHASE_MIN_RATIO_HOME_DRAW', 0.55, 0.0, 1.5)
            )
            if max_constrained <= 0 or constrained_probs[phase_candidate] >= max_constrained * min_candidate_ratio:
                phase_axis_adjustment = {
                    'from': rec,
                    'to': phase_candidate,
                    'reason': 'half_time_low_tempo_axis' if low_tempo_half and preferred_half == 'd' else 'half_time_phase_axis',
                    'half_time_probabilities': {
                        'h': round(half_home, 4),
                        'd': round(half_draw, 4),
                        'a': round(half_away, 4),
                    },
                    'half_time_tempo': {
                        'zero_zero_probability': round(half_zero_zero, 4),
                        'under_1_5_probability': round(half_under_1_5, 4),
                        'low_tempo_half': low_tempo_half,
                    },
                    'selected_probability': round(constrained_probs[phase_candidate], 4),
                    'best_full_axis_probability': round(max_constrained, 4),
                    'min_candidate_ratio': round(min_candidate_ratio, 4),
                }
                rec = phase_candidate
    soft_full_axis_adjustment = None
    if (
        not axis_target
        and _env_float('FOOTBALL_BQC_SOFT_FULL_AXIS_ENABLED', 1.0, 0.0, 1.0) >= 1.0
        and bqc_probs
    ):
        full_axis_probs = {'h': full_home, 'd': full_draw, 'a': full_away}
        ordered_full_axis = sorted(full_axis_probs.items(), key=lambda item: item[1], reverse=True)
        soft_axis = ordered_full_axis[0][0] if ordered_full_axis else ''
        soft_axis_prob = ordered_full_axis[0][1] if ordered_full_axis else 0.0
        second_axis_prob = ordered_full_axis[1][1] if len(ordered_full_axis) >= 2 else 0.0
        soft_min_probability = _env_float('FOOTBALL_BQC_SOFT_FULL_AXIS_MIN_PROBABILITY', 0.37, 0.0, 1.0)
        soft_min_gap = _env_float('FOOTBALL_BQC_SOFT_FULL_AXIS_MIN_GAP', 0.045, 0.0, 1.0)
        if soft_axis in {'h', 'a'} and soft_axis_prob >= soft_min_probability and (soft_axis_prob - second_axis_prob) >= soft_min_gap:
            draw_pref = low_tempo_half or half_draw >= max(half_home, half_away) * _env_float('FOOTBALL_BQC_SOFT_DRAW_RATIO', 0.92, 0.0, 1.5)
            preferred_half = 'd' if draw_pref else soft_axis
            soft_candidate = f'{preferred_half}{soft_axis}'
            if soft_candidate in bqc_probs and soft_candidate != rec:
                max_bqc_prob = max(bqc_probs.values()) if bqc_probs else 0.0
                min_candidate_ratio = (
                    _env_float('FOOTBALL_BQC_SOFT_DRAW_CANDIDATE_RATIO', 0.78, 0.0, 1.5)
                    if preferred_half == 'd'
                    else _env_float('FOOTBALL_BQC_SOFT_SAME_SIDE_CANDIDATE_RATIO', 0.72, 0.0, 1.5)
                )
                if max_bqc_prob <= 0 or bqc_probs[soft_candidate] >= max_bqc_prob * min_candidate_ratio:
                    soft_full_axis_adjustment = {
                        'from': rec,
                        'to': soft_candidate,
                        'reason': 'soft_full_time_axis_low_tempo' if preferred_half == 'd' else 'soft_full_time_axis',
                        'full_time_probabilities': {
                            'h': round(full_home, 4),
                            'd': round(full_draw, 4),
                            'a': round(full_away, 4),
                        },
                        'half_time_probabilities': {
                            'h': round(half_home, 4),
                            'd': round(half_draw, 4),
                            'a': round(half_away, 4),
                        },
                        'selected_probability': round(bqc_probs[soft_candidate], 4),
                        'best_probability': round(max_bqc_prob, 4),
                        'full_time_axis': soft_axis,
                        'full_time_axis_probability': round(soft_axis_prob, 4),
                        'full_time_axis_gap': round(soft_axis_prob - second_axis_prob, 4),
                        'low_tempo_half': low_tempo_half,
                        'min_probability': round(soft_min_probability, 4),
                        'min_gap': round(soft_min_gap, 4),
                        'min_candidate_ratio': round(min_candidate_ratio, 4),
                    }
                    rec = soft_candidate
    bqc_cn = {
        'hh': '胜胜', 'hd': '胜平', 'ha': '胜负',
        'dh': '平胜', 'dd': '平平', 'da': '平负',
        'ah': '负胜', 'ad': '负平', 'aa': '负负',
    }

    result = {
        'recommendation': rec,
        'recommendation_cn': bqc_cn.get(rec, ''),
        'probabilities': bqc_probs,
        'half_time': {'3': round(half_home, 3), '1': round(half_draw, 3), '0': round(half_away, 3)},
        'phase_profile': phase_profile,
        'phase_xg': {'home_ht': round(half_home_xg, 3), 'away_ht': round(half_away_xg, 3)},
        'phase_tempo': {
            'half_0_0_probability': round(half_zero_zero, 4),
            'half_under_1_5_probability': round(half_under_1_5, 4),
            'low_tempo_half': low_tempo_half,
        },
        'method': ('phase_profile_' if phase_profile else '') + bqc_method,
    }
    if axis_target:
        result['axis_constraint'] = {
            'source': 'spf_axis',
            'full_time_axis': axis_target,
            'candidate_count': len(constrained_probs),
            'trusted': bool(axis_target),
            'axis_context': axis_context or {},
        }
    elif axis_context:
        result['axis_constraint'] = {
            'source': 'spf_axis',
            'applied': False,
            'reason': 'bqc_axis_disabled' if _env_float('FOOTBALL_BQC_SPF_AXIS_ENABLED', 1.0, 0.0, 1.0) < 1.0 else 'no_spf_direction',
            'axis_context': axis_context,
            'min_probability': _env_float('FOOTBALL_BQC_AXIS_MIN_PROBABILITY', 0.52, 0.0, 1.0),
            'min_gap': _env_float('FOOTBALL_BQC_AXIS_MIN_GAP', 0.05, 0.0, 1.0),
        }
    if phase_axis_adjustment:
        result['phase_axis_adjustment'] = {
            **phase_axis_adjustment,
            'from_cn': bqc_cn.get(phase_axis_adjustment.get('from'), ''),
            'to_cn': bqc_cn.get(phase_axis_adjustment.get('to'), ''),
        }
    if soft_full_axis_adjustment:
        result['soft_full_axis_adjustment'] = {
            **soft_full_axis_adjustment,
            'from_cn': bqc_cn.get(soft_full_axis_adjustment.get('from'), ''),
            'to_cn': bqc_cn.get(soft_full_axis_adjustment.get('to'), ''),
            'full_time_axis_cn': {'h': '主胜', 'd': '平局', 'a': '客胜'}.get(
                soft_full_axis_adjustment.get('full_time_axis'), ''
            ),
        }
    return result
