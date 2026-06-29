"""Match script layer — unified match narrative from which all play types derive.

Every match gets a single match_script that captures the core narrative:
  direction_axis   — who wins and by what margin tendency
  margin_axis      — expected goal margin (by 1, by 2+, etc.)
  goal_axis        — total goals expectation (over/under zone)
  btts_axis        — both teams to score likelihood
  first_half_axis  — first-half tempo and scoring pattern
  late_goal_risk   — probability of late goals shifting result
  uncertainty      — overall prediction uncertainty level
  key_drivers      — list of factors driving the prediction

All 5 play types (SPF, RQSPF, O/U, BF, BQC) derive from this script,
ensuring internal consistency. Cross-play contradictions are flagged.
"""

import logging
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# Direction axis labels
DIRECTION_LABELS = {
    'home_strong': '主队明显优势',
    'home_edge': '主队略优',
    'balanced': '势均力敌',
    'away_edge': '客队略优',
    'away_strong': '客队明显优势',
}

# Margin axis labels
MARGIN_LABELS = {
    'home_by_2plus': '主队赢2+球',
    'home_by_1': '主队赢1球',
    'draw': '平局',
    'away_by_1': '客队赢1球',
    'away_by_2plus': '客队赢2+球',
}

# Goal axis labels
GOAL_ZONE_LABELS = {
    'very_low': '0-1球 (极低)',
    'low': '2球 (低)',
    'moderate': '2-3球 (中)',
    'high': '3+球 (高)',
    'very_high': '4+球 (极高)',
}

# BTTS axis labels
BTTS_LABELS = {
    'both_score': '双方进球',
    'one_side': '单方进球',
    'neither': '双方不进球',
}

# First half axis labels
FIRST_HALF_LABELS = {
    'slow_00': '慢节奏 0-0',
    'low_scoring': '低进球',
    'moderate': '中等节奏',
    'early_goal': '早进球',
    'high_scoring': '高进球',
}

# Uncertainty levels
UNCERTAINTY_LABELS = {
    'low': '低 — 多轴一致',
    'medium': '中 — 存在一个不确定轴',
    'high': '高 — 多轴分歧',
    'very_high': '极高 — 方向不明确',
}


# ---------------------------------------------------------------------------
# Build match script from analysis result
# ---------------------------------------------------------------------------

def build_match_script(plays: dict, result: dict, match: dict = None) -> dict:
    """Build a unified match script from the analysis result.

    The match script is the single source of truth. All play type
    recommendations must be derivable from it without contradiction.
    """
    fp = result.get('final_prediction', {}) or {}
    probs = fp.get('probabilities', {}) or {}
    spf = plays.get('spf') if isinstance(plays.get('spf'), dict) else {}
    ou = plays.get('ou') if isinstance(plays.get('ou'), dict) else {}
    rqspf = plays.get('rqspf') if isinstance(plays.get('rqspf'), dict) else {}
    bqc = plays.get('bqc') if isinstance(plays.get('bqc'), dict) else {}
    top_scores = plays.get('top3_scores') if isinstance(plays.get('top3_scores'), list) else []

    # 1. Direction axis
    direction_axis = _build_direction_axis(probs, spf)

    # 2. Margin axis
    margin_axis = _build_margin_axis(result, plays)

    # 3. Goal axis
    goal_axis = _build_goal_axis(ou, result)

    # 4. BTTS axis
    btts_axis = _build_btts_axis(result, plays)

    # 5. First half axis
    first_half_axis = _build_first_half_axis(bqc, result)

    # 6. Late goal risk
    late_goal_risk = _assess_late_goal_risk(goal_axis, btts_axis, result)

    # 7. Key drivers
    key_drivers = _identify_key_drivers(result, plays)

    # 8. Uncertainty
    uncertainty = _assess_uncertainty(direction_axis, margin_axis, goal_axis, btts_axis, result)

    script = {
        'direction_axis': direction_axis,
        'margin_axis': margin_axis,
        'goal_axis': goal_axis,
        'btts_axis': btts_axis,
        'first_half_axis': first_half_axis,
        'late_goal_risk': late_goal_risk,
        'uncertainty': uncertainty,
        'key_drivers': key_drivers,
    }

    # 9. Cross-play consistency check
    contradictions = _check_cross_play_consistency(script, plays)
    script['contradictions'] = contradictions
    script['is_consistent'] = len(contradictions) == 0

    # 10. Derive play recommendations from script (for verification)
    script['derived'] = _derive_from_script(script, plays, match)

    return script


def _build_direction_axis(probs: dict, spf: dict) -> dict:
    """Build direction axis from SPF probabilities."""
    hw = float(probs.get('home_win', 0.33))
    dr = float(probs.get('draw', 0.33))
    aw = float(probs.get('away_win', 0.33))

    diff = hw - aw
    if diff >= 0.20:
        side = 'home_strong'
    elif diff >= 0.06:
        side = 'home_edge'
    elif diff <= -0.20:
        side = 'away_strong'
    elif diff <= -0.06:
        side = 'away_edge'
    else:
        side = 'balanced'

    spf_dir = str(spf.get('direction') or '')
    return {
        'side': side,
        'label': DIRECTION_LABELS.get(side, side),
        'spf_direction': spf_dir,
        'home_win_prob': round(hw, 4),
        'draw_prob': round(dr, 4),
        'away_win_prob': round(aw, 4),
        'edge': round(abs(diff), 4),
    }


def _build_margin_axis(result: dict, plays: dict) -> dict:
    """Build margin axis from score matrix conditions."""
    conditions = (result.get('play_predictions', {}) or {}).get('derivation_axes', {})
    if not conditions:
        conditions = result.get('derivation_axes', {})

    home_by_1 = _safe_float(conditions.get('home_win_by_1_probability'))
    home_by_2p = _safe_float(conditions.get('home_win_by_2_plus_probability'))
    away_by_1 = _safe_float(conditions.get('away_win_by_1_probability'))
    away_by_2p = _safe_float(conditions.get('away_win_by_2_plus_probability'))
    draw_p = _safe_float(conditions.get('draw_probability_from_matrix'))

    if home_by_2p and home_by_2p > max(draw_p or 0, away_by_1 or 0, away_by_2p or 0):
        margin = 'home_by_2plus'
    elif home_by_1 and home_by_1 > max(draw_p or 0, away_by_1 or 0):
        margin = 'home_by_1'
    elif away_by_2p and away_by_2p > max(draw_p or 0, home_by_1 or 0, home_by_2p or 0):
        margin = 'away_by_2plus'
    elif away_by_1 and away_by_1 > max(draw_p or 0, home_by_1 or 0):
        margin = 'away_by_1'
    elif draw_p and draw_p > max(home_by_1 or 0, away_by_1 or 0):
        margin = 'draw'
    else:
        margin = 'draw'

    rqspf = plays.get('rqspf') if isinstance(plays.get('rqspf'), dict) else {}
    return {
        'margin': margin,
        'label': MARGIN_LABELS.get(margin, margin),
        'home_by_1': home_by_1,
        'home_by_2plus': home_by_2p,
        'away_by_1': away_by_1,
        'away_by_2plus': away_by_2p,
        'draw': draw_p,
        'rqspf_direction': str(rqspf.get('direction') or ''),
        'handicap': _safe_float(rqspf.get('handicap')),
    }


def _build_goal_axis(ou: dict, result: dict) -> dict:
    """Build goal axis from O/U prediction."""
    ou_rec = str(ou.get('recommendation') or '')
    ou_line = _safe_float(ou.get('best_line') or ou.get('line'))
    expected_total = None

    fp = result.get('final_prediction', {}) or {}
    expected = fp.get('expected_score', {}) or {}
    if isinstance(expected, dict):
        h = _safe_float(expected.get('home'))
        a = _safe_float(expected.get('away'))
        if h is not None and a is not None:
            expected_total = round(h + a, 2)

    diagnostics = ou.get('diagnostics') if isinstance(ou.get('diagnostics'), dict) else {}
    if expected_total is None:
        expected_total = _safe_float(diagnostics.get('expected_total'))

    # Goal zone
    if expected_total is not None:
        if expected_total < 1.5:
            zone = 'very_low'
        elif expected_total < 2.3:
            zone = 'low'
        elif expected_total < 3.0:
            zone = 'moderate'
        elif expected_total < 3.8:
            zone = 'high'
        else:
            zone = 'very_high'
    else:
        zone = 'moderate'

    side = 'over' if '大' in ou_rec or 'over' in ou_rec.lower() else ('under' if '小' in ou_rec or 'under' in ou_rec.lower() else 'unknown')

    return {
        'zone': zone,
        'label': GOAL_ZONE_LABELS.get(zone, zone),
        'side': side,
        'ou_recommendation': ou_rec,
        'ou_line': ou_line,
        'expected_total': expected_total,
        'line_gap': round(expected_total - ou_line, 2) if expected_total is not None and ou_line is not None else None,
    }


def _build_btts_axis(result: dict, plays: dict) -> dict:
    """Build BTTS axis from score matrix conditions."""
    conditions = (result.get('play_predictions', {}) or {}).get('derivation_axes', {})
    if not conditions:
        conditions = result.get('derivation_axes', {})

    btts_prob = _safe_float(conditions.get('both_teams_score_probability'))
    home_goal = _safe_float(conditions.get('home_goal_probability'))
    away_goal = _safe_float(conditions.get('away_goal_probability'))

    if btts_prob is not None:
        if btts_prob >= 0.55:
            btts = 'both_score'
        elif btts_prob >= 0.35:
            btts = 'one_side'
        else:
            btts = 'neither'
    elif home_goal is not None and away_goal is not None:
        if home_goal >= 0.60 and away_goal >= 0.50:
            btts = 'both_score'
        elif home_goal < 0.45 and away_goal < 0.45:
            btts = 'neither'
        else:
            btts = 'one_side'
    else:
        btts = 'one_side'

    return {
        'btts': btts,
        'label': BTTS_LABELS.get(btts, btts),
        'both_teams_score_probability': btts_prob,
        'home_goal_probability': home_goal,
        'away_goal_probability': away_goal,
    }


def _build_first_half_axis(bqc: dict, result: dict) -> dict:
    """Build first half axis from BQC phase profile."""
    phase = bqc.get('phase_profile') if isinstance(bqc.get('phase_profile'), dict) else {}

    ht00 = _safe_float(phase.get('ht_zero_zero_rate'))
    ht_under = _safe_float(phase.get('ht_under_1_5_rate'))
    home_ht_gf = _safe_float(phase.get('home_ht_avg_for'))
    away_ht_gf = _safe_float(phase.get('away_ht_avg_for'))

    # Determine first-half tempo
    if ht00 is not None and ht00 >= 0.35:
        fh = 'slow_00'
    elif ht_under is not None and ht_under >= 0.55:
        fh = 'low_scoring'
    elif home_ht_gf is not None and away_ht_gf is not None:
        total_ht = home_ht_gf + away_ht_gf
        if total_ht >= 1.5:
            fh = 'high_scoring'
        elif total_ht >= 1.0:
            fh = 'early_goal'
        elif total_ht >= 0.6:
            fh = 'moderate'
        else:
            fh = 'low_scoring'
    else:
        fh = 'moderate'

    bqc_rec = str(bqc.get('recommendation') or '')

    return {
        'tempo': fh,
        'label': FIRST_HALF_LABELS.get(fh, fh),
        'ht_zero_zero_rate': ht00,
        'ht_under_1_5_rate': ht_under,
        'bqc_recommendation': bqc_rec,
        'bqc_half_time_leg': bqc_rec[0] if len(bqc_rec) >= 1 else '',
        'bqc_full_time_leg': bqc_rec[1] if len(bqc_rec) >= 2 else '',
    }


def _assess_late_goal_risk(goal_axis: dict, btts_axis: dict, result: dict) -> dict:
    """Assess risk of late goals changing the result."""
    expected = goal_axis.get('expected_total')
    zone = goal_axis.get('zone', 'moderate')

    if expected is not None and expected >= 3.0:
        risk = 'high'
    elif expected is not None and expected >= 2.5:
        risk = 'medium'
    else:
        risk = 'low'

    return {
        'level': risk,
        'label': {'low': '低', 'medium': '中', 'high': '高'}.get(risk, risk),
        'reason': f'预期总进球{expected}' if expected is not None else '总进球未知',
    }


def _identify_key_drivers(result: dict, plays: dict) -> List[str]:
    """Identify the key factors driving the prediction."""
    drivers = []
    fp = result.get('final_prediction', {}) or {}
    probs = fp.get('probabilities', {}) or {}

    # Market alignment
    mvo = result.get('model_vs_odds', {}) or {}
    if isinstance(mvo, dict):
        if mvo.get('agreement'):
            drivers.append('market_aligned')
        else:
            drivers.append('market_diverged')

    # Elo/FIFA
    if result.get('elo_prediction'):
        drivers.append('elo_fifa')

    # Form
    if result.get('form_comparison'):
        drivers.append('recent_form')

    # Intelligence
    if result.get('intelligence_adjustment', {}).get('applied'):
        drivers.append('intelligence')

    # Goal profile
    if result.get('goal_profile_adjustment', {}).get('applied'):
        drivers.append('attack_defense_profile')

    # Disagreement boost
    if result.get('disagreement_boost', {}).get('applied'):
        drivers.append('model_odds_disagreement')

    # Competition context
    if result.get('competition_context'):
        drivers.append('competition_context')

    # Draw calibration
    if result.get('draw_calibration', {}).get('applied'):
        drivers.append('draw_calibration')

    if not drivers:
        drivers.append('odds_only')

    return drivers


def _assess_uncertainty(direction: dict, margin: dict, goal: dict, btts: dict, result: dict) -> dict:
    """Assess overall prediction uncertainty from multi-axis consistency."""
    issues = 0
    reasons = []

    # Direction uncertainty
    edge = direction.get('edge', 0)
    if edge < 0.06:
        issues += 2
        reasons.append('方向不明确')
    elif edge < 0.12:
        issues += 1
        reasons.append('方向偏弱')

    # Goal axis uncertainty
    line_gap = goal.get('line_gap')
    if line_gap is not None and abs(line_gap) < 0.25:
        issues += 1
        reasons.append('进球贴近盘口')

    # Model vs market divergence
    mvo = result.get('model_vs_odds', {}) or {}
    if isinstance(mvo, dict) and not mvo.get('agreement', True):
        issues += 1
        reasons.append('模型与市场分歧')

    # Confidence level
    fp = result.get('final_prediction', {}) or {}
    cl = fp.get('confidence_level', '')
    if cl in ('low', 'odds_only'):
        issues += 2
        reasons.append('置信度低')
    elif cl == 'medium':
        issues += 1

    if issues >= 4:
        level = 'very_high'
    elif issues >= 3:
        level = 'high'
    elif issues >= 1:
        level = 'medium'
    else:
        level = 'low'

    return {
        'level': level,
        'label': UNCERTAINTY_LABELS.get(level, level),
        'issues': issues,
        'reasons': reasons,
    }


# ---------------------------------------------------------------------------
# Cross-play consistency validation
# ---------------------------------------------------------------------------

def _check_cross_play_consistency(script: dict, plays: dict) -> List[dict]:
    """Check for contradictions between play types and the match script.

    Returns list of contradiction dicts:
      {type, description, severity, play_types_involved}
    """
    contradictions = []
    direction = script.get('direction_axis', {})
    margin = script.get('margin_axis', {})
    goal = script.get('goal_axis', {})
    btts = script.get('btts_axis', {})
    first_half = script.get('first_half_axis', {})

    spf = plays.get('spf') if isinstance(plays.get('spf'), dict) else {}
    rqspf = plays.get('rqspf') if isinstance(plays.get('rqspf'), dict) else {}
    bqc = plays.get('bqc') if isinstance(plays.get('bqc'), dict) else {}
    ou = plays.get('ou') if isinstance(plays.get('ou'), dict) else {}

    # 1. SPF vs BQC full-time leg
    spf_dir = str(spf.get('direction') or '')
    bqc_rec = str(bqc.get('recommendation') or '')
    if spf_dir and len(bqc_rec) == 2:
        bqc_full = bqc_rec[1]
        spf_to_full = {'3': 'h', '1': 'd', '0': 'a'}
        expected_full = spf_to_full.get(spf_dir)
        if expected_full and bqc_full != expected_full:
            contradictions.append({
                'type': 'spf_bqc_full_time_mismatch',
                'description': f'SPF={spf_dir}({{"3":"主胜","1":"平局","0":"客胜"}}.get(spf_dir,"")) 但BQC全场={bqc_full}',
                'severity': 'high',
                'play_types_involved': ['spf', 'bqc'],
            })

    # 2. RQSPF vs BQC full-time leg
    rqspf_dir = str(rqspf.get('direction') or '')
    if rqspf_dir and len(bqc_rec) == 2:
        try:
            handicap = float(rqspf.get('handicap') or 0)
        except (TypeError, ValueError):
            handicap = 0.0
        # If RQSPF=让胜(handicap>0), full-time must be home_win
        if handicap > 0 and rqspf_dir == '3' and bqc_full != 'h':
            contradictions.append({
                'type': 'rqspf_bqc_full_time_mismatch',
                'description': f'让球让胜但BQC全场={bqc_full}',
                'severity': 'high',
                'play_types_involved': ['rqspf', 'bqc'],
            })
        elif handicap < 0 and rqspf_dir == '0' and bqc_full != 'a':
            contradictions.append({
                'type': 'rqspf_bqc_full_time_mismatch',
                'description': f'让球让负但BQC全场={bqc_full}',
                'severity': 'high',
                'play_types_involved': ['rqspf', 'bqc'],
            })

    # 3. Goal axis vs top score
    top_scores = plays.get('top3_scores') if isinstance(plays.get('top3_scores'), list) else []
    if top_scores and goal.get('side') == 'under':
        top1 = top_scores[0] if isinstance(top_scores[0], dict) else {}
        score_str = str(top1.get('score', ''))
        try:
            total_goals = sum(int(x) for x in score_str.split('-') if x.isdigit())
            ou_line = goal.get('ou_line') or 2.5
            if total_goals > ou_line + 0.5:
                contradictions.append({
                    'type': 'goal_axis_score_candidate_mismatch',
                    'description': f'O/U看小球但首选比分{score_str}(总{total_goals}球)',
                    'severity': 'medium',
                    'play_types_involved': ['ou', 'bf'],
                })
        except (ValueError, TypeError):
            pass

    # 4. Direction axis vs margin axis
    dir_side = direction.get('side', '')
    margin_m = margin.get('margin', '')
    if dir_side in ('home_strong', 'home_edge') and margin_m in ('away_by_1', 'away_by_2plus'):
        contradictions.append({
            'type': 'direction_margin_contradiction',
            'description': f'方向轴={dir_side}但边界轴={margin_m}',
            'severity': 'high',
            'play_types_involved': ['spf', 'rqspf'],
        })
    elif dir_side in ('away_strong', 'away_edge') and margin_m in ('home_by_1', 'home_by_2plus'):
        contradictions.append({
            'type': 'direction_margin_contradiction',
            'description': f'方向轴={dir_side}但边界轴={margin_m}',
            'severity': 'high',
            'play_types_involved': ['spf', 'rqspf'],
        })

    # 5. First half vs BQC
    fh_tempo = first_half.get('tempo', '')
    if fh_tempo == 'slow_00' and len(bqc_rec) == 2:
        ht_leg = bqc_rec[0]
        if ht_leg in ('h', 'a'):  # BQC half-time leg is win, but script says slow 0-0
            contradictions.append({
                'type': 'first_half_bqc_mismatch',
                'description': f'半场节奏=慢0-0但BQC半场={ht_leg}(有进球)',
                'severity': 'medium',
                'play_types_involved': ['bqc'],
            })

    return contradictions


# ---------------------------------------------------------------------------
# Derive play recommendations from script (verification)
# ---------------------------------------------------------------------------

def _derive_from_script(script: dict, plays: dict, match: dict = None) -> dict:
    """Derive what each play type SHOULD recommend based on the script.

    This is for verification — comparing actual vs script-derived recommendations.
    """
    direction = script.get('direction_axis', {})
    margin = script.get('margin_axis', {})
    goal = script.get('goal_axis', {})
    btts = script.get('btts_axis', {})
    first_half = script.get('first_half_axis', {})

    # SPF from direction axis
    spf_dir = direction.get('spf_direction', '?')

    # RQSPF from margin axis
    margin_to_rqspf = {
        'home_by_2plus': '3',
        'home_by_1': '1',
        'draw': '1',
        'away_by_1': '1',
        'away_by_2plus': '0',
    }
    rqspf_dir = margin_to_rqspf.get(margin.get('margin', ''), '?')

    # O/U from goal axis
    ou_dir = goal.get('side', 'unknown')

    # BQC from first_half + direction
    ht_leg = first_half.get('bqc_half_time_leg', '?')
    ft_leg = {'3': 'h', '1': 'd', '0': 'a'}.get(spf_dir, '?')
    bqc_code = f'{ht_leg}{ft_leg}' if ht_leg != '?' and ft_leg != '?' else '??'

    # BF from direction + goal + btts
    # (simplified — just note the expected zone)
    bf_zone = goal.get('zone', 'moderate')

    derived = {
        'spf': spf_dir,
        'rqspf': rqspf_dir,
        'ou': ou_dir,
        'bqc': bqc_code,
        'bf_zone': bf_zone,
    }

    # Compare with actual
    spf = plays.get('spf') if isinstance(plays.get('spf'), dict) else {}
    rqspf = plays.get('rqspf') if isinstance(plays.get('rqspf'), dict) else {}
    bqc = plays.get('bqc') if isinstance(plays.get('bqc'), dict) else {}

    derived['matches_actual'] = {
        'spf': str(spf.get('direction') or '') == spf_dir,
        'rqspf': str(rqspf.get('direction') or '') == rqspf_dir,
        'bqc': str(bqc.get('recommendation') or '') == bqc_code,
    }

    return derived


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _safe_float(value) -> Optional[float]:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
