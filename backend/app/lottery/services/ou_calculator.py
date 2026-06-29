"""
ou_calculator.py — 统一大小球(O/U)计算模块

四级fallback:
1. Pinnacle O/U (pinnacle_ou.py)
2. Bet365 O/U 2.5 (match_odds表)
3. TTG体彩赔率推导
4. Poisson比分矩阵兜底

所有调用方(core/analyze, analysis_service, lottery router)统一使用此模块。
"""

import sqlite3
import json
import os
import logging
import re
from typing import Optional, Dict

logger = logging.getLogger(__name__)

_FOOTBALL_V2_DEFAULT = os.path.abspath(
    os.path.join(os.path.dirname(__file__), '..', '..', '..', '..', 'data', 'football_v2.db')
)


def compute_ou_analysis(
    db_path: str = None,
    match: dict = None,
    score_matrix=None,
    lottery_match_id: str = None,
) -> Optional[Dict]:
    """统一大小球分析入口

    Args:
        db_path: football_v2.db路径
        match: 比赛信息dict(需含home_team_cn, away_team_cn, home_team_id, away_team_id, match_date)
        score_matrix: Poisson比分矩阵(可选, Tier 4兜底用)
        lottery_match_id: 体彩比赛ID(可选, Tier 3用)

    Returns:
        {
            'recommendation': str,      # '大2.5' / '小2.5'
            'best_line': float,         # 最佳盘口线
            'most_likely_total': int,   # 最可能总进球
            'over_2': float, 'over_2_5': float, 'over_3': float,
            'under_2_5': float, 'over_3_5': float,
            'total_goals_distribution': dict,
            'source': str,              # 'pinnacle_ou_*' | 'bet365_ou' | 'ttg_*' | 'poisson'
        }
        or None if no data available.
    """
    if db_path is None:
        db_path = _FOOTBALL_V2_DEFAULT

    # Tier 1: Pinnacle O/U
    baseline = _get_pinnacle_baseline(db_path, match)
    if baseline:
        return _derive_ou_from_baseline(baseline, score_matrix=score_matrix)

    # Tier 2: Bet365 O/U (match_odds表)
    baseline = _get_bet365_baseline(db_path, match)
    if baseline:
        return _derive_ou_from_baseline(baseline, score_matrix=score_matrix)

    # Tier 3: TTG odds
    if lottery_match_id:
        baseline = _get_ttg_baseline(db_path, lottery_match_id)
        if baseline:
            return _derive_ou_from_baseline(baseline, score_matrix=score_matrix)

    # Tier 4: Poisson
    if score_matrix is not None:
        return _derive_ou_from_poisson(score_matrix)

    return None


def compute_ou_result(total_goals: int, best_line: float) -> str:
    """Compute O/U result string from total goals and line.

    Args:
        total_goals: actual total goals scored
        best_line: O/U line (e.g. 2.5)

    Returns:
        '大2.5' or '小2.5'
    """
    return f'大{best_line:g}' if total_goals > best_line else f'小{best_line:g}'


def format_ou_line(best_line: float) -> str:
    try:
        value = float(best_line)
    except (TypeError, ValueError):
        value = 2.5
    return f"{value:g}"


def parse_ou_line(value) -> Optional[float]:
    if value is None:
        return None
    text = str(value).strip()
    match = re.search(r"(?:大|小|走|over|under|o|u)?\s*(\d+(?:\.\d+)?)", text, re.IGNORECASE)
    if not match:
        return None
    try:
        return float(match.group(1))
    except ValueError:
        return None


def compute_ou_result(total_goals: int, best_line: float) -> str:
    """Compute O/U result string from total goals and line."""
    line = float(best_line)
    line_text = format_ou_line(line)
    if total_goals > line:
        return f"大{line_text}"
    if total_goals < line:
        return f"小{line_text}"
    return f"走{line_text}"


def compute_ou_result_from_prediction(total_goals: int, prediction, default_line: float = 2.5) -> str:
    line = parse_ou_line(prediction)
    if line is None:
        line = default_line
    return compute_ou_result(total_goals, line)


def asian_ou_line_probabilities(total_goals_prob: dict, line: float) -> dict:
    """Return side probabilities for Asian total-goals lines.

    The model previously treated 3.25 like a simple 3.25 threshold, so all
    three-goal outcomes counted as full under. For recommendation confidence we
    split quarter lines into their two Asian components and share push outcomes
    evenly between over and under. This prevents 2.25/2.75/3.25 lines from
    overstating one side when the distribution clusters around the boundary.
    """
    try:
        line_value = float(line)
    except (TypeError, ValueError):
        line_value = 2.5
    components = _asian_ou_components(line_value)
    if not components:
        components = [line_value]

    over = 0.0
    under = 0.0
    push = 0.0
    for goals, raw_prob in (total_goals_prob or {}).items():
        try:
            total = int(goals)
            prob = float(raw_prob or 0)
        except (TypeError, ValueError):
            continue
        if prob <= 0:
            continue
        over_share = 0.0
        under_share = 0.0
        push_share = 0.0
        for component in components:
            if total > component:
                over_share += 1.0
            elif total < component:
                under_share += 1.0
            else:
                over_share += 0.5
                under_share += 0.5
                push_share += 1.0
        divisor = float(len(components))
        over += prob * (over_share / divisor)
        under += prob * (under_share / divisor)
        push += prob * (push_share / divisor)

    total_mass = over + under
    if total_mass > 0:
        over_decision = over / total_mass
        under_decision = under / total_mass
    else:
        over_decision = None
        under_decision = None
    return {
        "line": line_value,
        "components": components,
        "over": over,
        "under": under,
        "push": push,
        "decision_over": over_decision,
        "decision_under": under_decision,
    }


def _asian_ou_components(line: float) -> list:
    """Convert an Asian O/U line into component thresholds."""
    try:
        rounded = round(float(line) * 4) / 4
    except (TypeError, ValueError):
        return []
    whole = int(rounded)
    quarter = int(round((rounded - whole) * 4))
    if quarter == 0:
        return [float(whole)]
    if quarter == 1:
        return [float(whole), whole + 0.5]
    if quarter == 2:
        return [whole + 0.5]
    if quarter == 3:
        return [whole + 0.5, float(whole + 1)]
    return [rounded]


def get_ou_line_for_match(
    db_path: str,
    lottery_match_id: str = None,
    match: dict = None,
) -> Optional[Dict]:
    """Get just the O/U line info for a match (for display/results, no full analysis).

    Returns:
        {'best_line': float, 'over_prob': float, 'under_prob': float, 'source': str}
        or None
    """
    if db_path is None:
        db_path = _FOOTBALL_V2_DEFAULT

    # Try Pinnacle first
    baseline = _get_pinnacle_baseline(db_path, match)
    if baseline:
        return {
            'best_line': baseline['best_line'],
            'over_prob': baseline.get('best_line_over', 0),
            'under_prob': baseline.get('best_line_under', 0),
            'source': baseline.get('source', 'pinnacle'),
        }

    # Try Bet365
    baseline = _get_bet365_baseline(db_path, match)
    if baseline:
        return {
            'best_line': baseline['best_line'],
            'over_prob': baseline.get('best_line_over', 0),
            'under_prob': baseline.get('best_line_under', 0),
            'source': baseline.get('source', 'bet365'),
        }

    # Try TTG
    if lottery_match_id:
        baseline = _get_ttg_baseline(db_path, lottery_match_id)
        if baseline:
            return {
                'best_line': baseline['best_line'],
                'over_prob': baseline.get('best_line_over', 0),
                'under_prob': baseline.get('best_line_under', 0),
                'source': baseline.get('source', 'ttg'),
            }

    return None


# ============================================================
# Internal: Tier 1 - Pinnacle O/U
# ============================================================

def _get_pinnacle_baseline(db_path: str, match: dict) -> Optional[Dict]:
    """Fetch Pinnacle O/U odds and convert to baseline format."""
    if not match:
        return None

    event_baseline = _get_pinnacle_baseline_by_event_id(db_path, match)
    if event_baseline:
        return event_baseline

    try:
        from backend.app.lottery.services.pinnacle_ou import get_pinnacle_ou_odds
        from fetchers.common.team_names import normalize_team_name

        home_en = ''
        away_en = ''
        match_date = match.get('match_date', '')

        # Try team_id → English name
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

        # Fallback: normalize Chinese names
        if not home_en:
            home_en = normalize_team_name(
                match.get('home_team_cn', '') or match.get('home_team', '') or ''
            )
        if not away_en:
            away_en = normalize_team_name(
                match.get('away_team_cn', '') or match.get('away_team', '') or ''
            )

        if not home_en or not away_en or not match_date:
            return None

        result = get_pinnacle_ou_odds(home_en, away_en, match_date, db_path)
        if not result:
            return None

        over_prob = result['over_prob']
        under_prob = result['under_prob']
        line = result['line']

        baseline = {
            'best_line': line,
            'best_line_over': round(over_prob, 4),
            'best_line_under': round(under_prob, 4),
            'source': f"pinnacle_ou_{result.get('source', 'unknown')}",
        }

        # Derive over/under 2.5 and 3.5 from all_lines
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
                        baseline['over_2_5'] = round(p_over, 4)
                        baseline['under_2_5'] = round(p_under, 4)
                    elif abs(lv - 3.5) < 0.01:
                        baseline['over_3_5'] = round(p_over, 4)
                        baseline['under_3_5'] = round(p_under, 4)
            except (ValueError, KeyError):
                pass

        return baseline

    except Exception as e:
        logger.debug(f'Pinnacle O/U baseline获取失败: {e}')
        return None


# ============================================================
# Internal: Tier 2 - Bet365 O/U (match_odds表)
# ============================================================

def _get_pinnacle_baseline_by_event_id(db_path: str, match: dict) -> Optional[Dict]:
    """Fetch Pinnacle O/U by exact oddsfe event id when the lottery bridge has it."""
    event_id = (
        match.get('oddsfe_event_id')
        or match.get('event_id')
        or match.get('odds_event_id')
        or ''
    )
    event_id = str(event_id).strip()
    if not event_id:
        return None

    try:
        conn = sqlite3.connect(db_path, timeout=10)
        cursor = conn.cursor()
        cursor.execute("""
            SELECT ou_pinnacle_line, ou_pinnacle_over, ou_pinnacle_under
            FROM oddsfe_matches
            WHERE event_id = ?
            LIMIT 1
        """, (event_id,))
        row = cursor.fetchone()
        conn.close()

        if not row or row[0] in (None, '') or row[1] in (None, '') or row[2] in (None, ''):
            return None

        line = float(row[0])
        over_odds = float(row[1])
        under_odds = float(row[2])
        if line <= 0 or over_odds <= 1 or under_odds <= 1:
            return None

        total_implied = 1 / over_odds + 1 / under_odds
        if total_implied <= 0:
            return None

        over_prob = (1 / over_odds) / total_implied
        under_prob = (1 / under_odds) / total_implied
        baseline = {
            'best_line': line,
            'best_line_over': round(over_prob, 4),
            'best_line_under': round(under_prob, 4),
            'source': 'pinnacle_ou_event_id',
        }

        if abs(line - 2.5) < 0.01:
            baseline['over_2_5'] = round(over_prob, 4)
            baseline['under_2_5'] = round(under_prob, 4)
        elif abs(line - 3.5) < 0.01:
            baseline['over_3_5'] = round(over_prob, 4)
            baseline['under_3_5'] = round(under_prob, 4)

        return baseline
    except Exception as e:
        logger.debug('Pinnacle O/U event-id baseline failed: %s', e)
        return None


def _get_bet365_baseline(db_path: str, match: dict) -> Optional[Dict]:
    """从match_odds表获取Bet365 O/U 2.5赔率

    match_odds表结构: match_id, b365_over_2_5, b365_under_2_5
    通过match_id链接matches表, 或通过team_id+date匹配
    """
    if not match:
        return None
    try:
        conn = sqlite3.connect(db_path, timeout=10)
        cursor = conn.cursor()

        row = None
        match_id = match.get('match_id')

        # 方法1: 直接用match_id
        if match_id:
            cursor.execute(
                "SELECT b365_over_2_5, b365_under_2_5 FROM match_odds WHERE match_id = ? LIMIT 1",
                (match_id,)
            )
            row = cursor.fetchone()

        # 方法2: 通过team_id+date在matches表找match_id
        if not row:
            home_id = match.get('home_team_id')
            away_id = match.get('away_team_id')
            match_date = match.get('match_date', '')
            if home_id and away_id and match_date:
                cursor.execute("""
                    SELECT m.match_id FROM matches m
                    WHERE m.home_team_id = ? AND m.away_team_id = ?
                    AND m.match_date = ? LIMIT 1
                """, (home_id, away_id, match_date))
                m_row = cursor.fetchone()
                if m_row:
                    cursor.execute(
                        "SELECT b365_over_2_5, b365_under_2_5 FROM match_odds WHERE match_id = ? LIMIT 1",
                        (m_row[0],)
                    )
                    row = cursor.fetchone()

        conn.close()

        if not row or not row[0] or not row[1]:
            return None

        b365_over = float(row[0])
        b365_under = float(row[1])

        if b365_over <= 1 or b365_under <= 1:
            return None

        # 隐含概率(去除利润)
        total_implied = 1/b365_over + 1/b365_under
        over_prob = (1/b365_over) / total_implied
        under_prob = (1/b365_under) / total_implied

        return {
            'best_line': 2.5,
            'best_line_over': round(over_prob, 4),
            'best_line_under': round(under_prob, 4),
            'over_2_5': round(over_prob, 4),
            'under_2_5': round(under_prob, 4),
            'most_likely_total': 2 if under_prob > over_prob else 3,
            'source': 'bet365_ou',
        }

    except Exception as e:
        logger.debug(f'Bet365 O/U baseline获取失败: {e}')
        return None


# ============================================================
# Internal: Tier 3 - TTG odds derivation
# ============================================================

def _get_ttg_baseline(db_path: str, lottery_match_id: str) -> Optional[Dict]:
    """从lottery_odds获取TTG(总进球)赔率, 推导大小球概率

    TTG格式: s0-s7 对应0-7+球的赔率
    """
    if not lottery_match_id:
        return None
    try:
        conn = sqlite3.connect(db_path, timeout=10)
        cursor = conn.cursor()
        for snapshot in ['opening', 'latest', 'midday', 'current', None]:
            if snapshot:
                cursor.execute("""
                    SELECT odds_data FROM lottery_odds
                    WHERE lottery_match_id = ? AND play_type = 'ttg'
                    AND snapshot_type = ?
                    ORDER BY created_at ASC LIMIT 1
                """, (lottery_match_id, snapshot))
            else:
                cursor.execute("""
                    SELECT odds_data FROM lottery_odds
                    WHERE lottery_match_id = ? AND play_type = 'ttg'
                    AND snapshot_type IS NULL
                    ORDER BY created_at ASC LIMIT 1
                """, (lottery_match_id,))
            row = cursor.fetchone()
            if row:
                break
        conn.close()

        if not row:
            return None

        odds_data = json.loads(row[0]) if isinstance(row[0], str) else row[0]
        implied, total = _compute_ttg_implied(odds_data)
        if total <= 0:
            return None

        return _derive_ttg_baseline(implied, snapshot)

    except Exception as e:
        logger.debug('TTG赔率获取失败: %s', e)
        return None


def _compute_ttg_implied(odds_data: dict) -> tuple:
    """Compute implied probabilities from TTG odds data (s0-s7).

    Returns: (implied dict, total)
    """
    implied = {}
    total = 0
    for i in range(8):
        key = 's' + str(i)
        odds_val = float(odds_data.get(key, 0))
        if odds_val > 1:
            implied[i] = 1 / odds_val
            total += implied[i]

    # Normalize
    if total > 0:
        for i in implied:
            implied[i] = implied[i] / total

    return implied, total


def _derive_ttg_baseline(implied: dict, snapshot: str = None) -> dict:
    """Derive O/U baseline from TTG implied probabilities."""
    under_2_5 = sum(implied.get(i, 0) for i in range(3))
    over_2_5 = sum(implied.get(i, 0) for i in range(3, 8))
    under_3_5 = sum(implied.get(i, 0) for i in range(4))
    over_3_5 = sum(implied.get(i, 0) for i in range(4, 8))
    most_likely = max(implied, key=implied.get) if implied else 2

    # Find best line (smallest over/under gap)
    best_line, best_over, best_under = _find_best_line(implied)

    return {
        'over_2_5': round(over_2_5, 4),
        'under_2_5': round(under_2_5, 4),
        'over_3_5': round(over_3_5, 4),
        'under_3_5': round(under_3_5, 4),
        'most_likely_total': most_likely,
        'goal_distribution': {
            str(i): round(implied.get(i, 0), 4)
            for i in range(8) if implied.get(i, 0) > 0.01
        },
        'best_line': best_line,
        'best_line_over': round(best_over, 4),
        'best_line_under': round(best_under, 4),
        'source': 'ttg_' + (snapshot or 'default'),
    }


def _find_best_line(implied_or_probs, max_goals: int = 8) -> tuple:
    """Find the best O/U line where over/under probabilities are closest to 50/50.

    Args:
        implied_or_probs: dict mapping goal_count → probability
        max_goals: upper bound for goal sums

    Returns:
        (best_line, best_over, best_under)
    """
    best_line = 2.5
    best_gap = 1.0
    best_over = 0
    best_under = 0

    for line in [1.5, 2.0, 2.5, 3.0, 3.5, 4.0, 4.5]:
        over = sum(implied_or_probs.get(i, 0) for i in range(int(line) + 1, max_goals))
        under = 1 - over
        gap = abs(over - under)
        if gap < best_gap:
            best_gap = gap
            best_line = line
            best_over = over
            best_under = under

    return best_line, best_over, best_under


# ============================================================
# Internal: Tier 4 - Poisson
# ============================================================

def _total_goals_prob_from_matrix(score_matrix) -> dict:
    norm = _normalize_matrix(score_matrix)
    total_goals_prob = {}
    for i, row in enumerate(norm):
        for j, prob in enumerate(row):
            total = i + j
            total_goals_prob[total] = total_goals_prob.get(total, 0) + prob
    return total_goals_prob


def _line_probs(total_goals_prob: dict, line: float) -> tuple:
    probs = asian_ou_line_probabilities(total_goals_prob, line)
    return probs.get("over", 0.0), probs.get("under", 0.0)


def _derive_ou_from_poisson(score_matrix) -> dict:
    """Derive O/U from Poisson score matrix."""
    total_goals_prob = _total_goals_prob_from_matrix(score_matrix)

    over_2 = sum(p for g, p in total_goals_prob.items() if g > 2)
    over_2_5 = over_2  # >2 ≡ ≥3
    over_3 = sum(p for g, p in total_goals_prob.items() if g > 3)
    most_likely = max(total_goals_prob, key=total_goals_prob.get) if total_goals_prob else 2

    # Find best line
    best_line = 2.5
    best_gap = 1.0
    for line in [1.5, 2.0, 2.5, 3.0, 3.5, 4.0, 4.5]:
        over, under = _line_probs(total_goals_prob, line)
        gap = abs(over - under)
        if gap < best_gap:
            best_gap = gap
            best_line = line

    best_over, best_under = _line_probs(total_goals_prob, best_line)
    model_recommendation = _make_recommendation(best_over, best_under, best_line)
    recommendation = model_recommendation
    model_edge = abs(best_over - best_under)

    return {
        'recommendation': recommendation,
        'model_recommendation': model_recommendation,
        'model_edge': round(model_edge, 4),
        'best_line': best_line,
        'line': best_line,
        'best_line_probs': {
            'over': round(best_over, 3),
            'under': round(best_under, 3),
        },
        'confidence': round(max(best_over, best_under), 3),
        'confidence_level': (
            'high' if max(best_over, best_under) >= 0.6
            else 'medium' if max(best_over, best_under) >= 0.53
            else 'low'
        ),
        'most_likely_total': most_likely,
        'over_2': round(over_2, 3),
        'over_2_5': round(over_2_5, 3),
        'over_3': round(over_3, 3),
        'under_2_5': round(1 - over_2_5, 3),
        'over_3_5': round(sum(p for g, p in total_goals_prob.items() if g > 3), 3),
        'total_goals_distribution': {
            str(g): round(p, 3) for g, p in sorted(total_goals_prob.items()) if p >= 0.01
        },
        'source': 'poisson',
    }


# ============================================================
# Shared helpers
# ============================================================

def _derive_ou_from_baseline(baseline: dict, score_matrix=None) -> dict:
    """Derive full O/U result from a real market line baseline.

    When a score matrix is available, keep the real O/U line from the market,
    but calculate the recommendation from the model distribution at that line.
    This keeps O/U, score recommendations and derivation text internally aligned.
    """
    over_2_5 = baseline.get('over_2_5', 0)
    under_2_5 = baseline.get('under_2_5', 0)
    over_3_5 = baseline.get('over_3_5', 0)
    most_likely = baseline.get('most_likely_total', 2)
    goal_dist = baseline.get('goal_distribution', {})
    source = baseline.get('source', 'unknown')
    best_line = float(baseline.get('best_line', 2.5) or 2.5)
    market_over = float(baseline.get('best_line_over', over_2_5) or 0)
    market_under = float(baseline.get('best_line_under', under_2_5) or 0)
    best_over = market_over
    best_under = market_under
    recommendation_basis = 'market_implied'

    model_goal_dist = None
    if score_matrix is not None:
        try:
            model_goal_dist = _total_goals_prob_from_matrix(score_matrix)
        except Exception as e:
            logger.debug('O/U model distribution failed: %s', e)

    if model_goal_dist:
        best_over, best_under = _line_probs(model_goal_dist, best_line)
        over_2 = sum(p for g, p in model_goal_dist.items() if g > 2)
        over_2_5 = over_2
        over_3 = sum(p for g, p in model_goal_dist.items() if g > 3)
        under_2_5 = 1 - over_2_5
        over_3_5 = over_3
        most_likely = max(model_goal_dist, key=model_goal_dist.get)
        goal_dist = {
            str(g): round(p, 3)
            for g, p in sorted(model_goal_dist.items())
            if p >= 0.01
        }
        recommendation_basis = 'model_at_market_line'
    else:
        over_2 = sum(float(v) for k, v in goal_dist.items() if int(k) > 2)
        over_3 = sum(float(v) for k, v in goal_dist.items() if int(k) > 3)

    model_recommendation = _make_recommendation(best_over, best_under, best_line)
    recommendation = model_recommendation
    model_edge = abs(best_over - best_under)
    recommendation_adjustment = None
    expected_total = None
    if model_goal_dist:
        expected_total = sum(float(goal) * float(prob) for goal, prob in model_goal_dist.items())
    gap = expected_total - best_line if expected_total is not None else None
    strong_xg_side = None
    if isinstance(gap, (int, float)):
        if gap >= 0.45:
            strong_xg_side = 'over'
        elif gap <= -0.45:
            strong_xg_side = 'under'

    model_side = 'over' if best_over >= best_under else 'under'
    market_side = 'over' if market_over >= market_under else 'under'
    market_edge = abs(market_over - market_under)
    market_selected = max(market_over, market_under)
    if (
        market_side != model_side
        and model_edge <= 0.02
        and max(best_over, best_under) < 0.515
        and market_edge >= 0.018
        and market_selected >= 0.512
        and market_edge >= model_edge + 0.012
        and strong_xg_side not in {'over', 'under'}
    ):
        recommendation = _make_recommendation(
            market_over if market_side == 'over' else 0,
            market_under if market_side == 'under' else 0,
            best_line,
        )
        recommendation_basis = 'market_tiebreaker_thin_model_edge'
        recommendation_adjustment = {
            'from': model_recommendation,
            'to': recommendation,
            'reason': recommendation_basis,
            'model_side': model_side,
            'model_edge': round(model_edge, 4),
            'market_side': market_side,
            'market_edge': round(market_edge, 4),
            'expected_total_minus_line': round(gap, 4) if isinstance(gap, (int, float)) else None,
        }

    return {
        'recommendation': recommendation,
        'model_recommendation': model_recommendation,
        'model_edge': round(model_edge, 4),
        'best_line': best_line,
        'line': best_line,
        'best_line_probs': {
            'over': round(best_over, 3),
            'under': round(best_under, 3),
        },
        'confidence': round(max(best_over, best_under), 3),
        'confidence_level': (
            'high' if max(best_over, best_under) >= 0.6
            else 'medium' if max(best_over, best_under) >= 0.53
            else 'low'
        ),
        'most_likely_total': most_likely,
        'over_2': round(over_2, 3),
        'over_2_5': round(over_2_5, 3),
        'over_3': round(over_3, 3),
        'under_2_5': round(under_2_5, 3),
        'over_3_5': round(over_3_5, 3),
        'total_goals_distribution': goal_dist,
        'source': source,
        'line_source': source,
        'recommendation_basis': recommendation_basis,
        'market_recommendation': _make_recommendation(market_over, market_under, best_line) if market_over or market_under else None,
        'market_best_line_probs': {
            'over': round(market_over, 3),
            'under': round(market_under, 3),
        },
        'recommendation_adjustment': recommendation_adjustment,
    }


def _make_recommendation(best_over: float, best_under: float, best_line: float) -> str:
    """Make O/U recommendation based on probabilities."""
    if best_over > 0.55:
        return f'大{best_line:g}'
    elif best_under > 0.55:
        return f'小{best_line:g}'
    else:
        return f'大{best_line:g}' if best_over > best_under else f'小{best_line:g}'


def _normalize_matrix(score_matrix) -> list:
    """Normalize a score matrix so all values sum to 1."""
    total = sum(sum(row) for row in score_matrix)
    if total <= 0:
        return score_matrix
    return [[p / total for p in row] for row in score_matrix]
