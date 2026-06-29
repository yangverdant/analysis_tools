"""Model baseline comparison system.

Computes predictions from multiple baseline models for every analyzed match,
so that model improvements are measured against objective benchmarks:

  market_favorite  — argmax of odds-implied probabilities
  market_implied   — full odds-implied probability distribution
  poisson          — raw Poisson prediction (no adjustments)
  elo              — raw Elo/FIFA prediction (no adjustments)
  recent_form      — form-only prediction direction
  hybrid_current   — the current model's full prediction

Baseline results are stored in the `model_baselines` table alongside
`lottery_validation`, enabling queries like:

  SELECT play_type,
         AVG(CASE WHEN baseline='market_favorite' AND is_correct THEN 1 END) AS market_acc,
         AVG(CASE WHEN baseline='hybrid_current'  AND is_correct THEN 1 END) AS model_acc
  FROM model_baselines
  GROUP BY play_type;
"""

import json
import logging
import math
import sqlite3
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

BASELINES = ('market_favorite', 'market_implied', 'poisson', 'elo', 'recent_form', 'hybrid_current')


# ---------------------------------------------------------------------------
# Baseline prediction functions
# ---------------------------------------------------------------------------

def _implied_probs_from_odds(home_odds, draw_odds, away_odds) -> Optional[Dict[str, float]]:
    """Convert decimal odds to normalized implied probabilities."""
    try:
        h = 1.0 / float(home_odds) if float(home_odds) > 1.0 else 0
        d = 1.0 / float(draw_odds) if float(draw_odds) > 1.0 else 0
        a = 1.0 / float(away_odds) if float(away_odds) > 1.0 else 0
        total = h + d + a
        if total <= 0:
            return None
        return {'home_win': h / total, 'draw': d / total, 'away_win': a / total}
    except (TypeError, ValueError, ZeroDivisionError):
        return None


def baseline_market_favorite(odds_baseline: dict) -> Optional[Dict]:
    """Market favorite baseline: pick the outcome with lowest odds / highest implied prob."""
    probs = _implied_probs_from_odds(
        odds_baseline.get('home_win_odds'),
        odds_baseline.get('draw_odds'),
        odds_baseline.get('away_win_odds'),
    )
    if not probs:
        return None
    direction_map = {'home_win': '3', 'draw': '1', 'away_win': '0'}
    rec = max(probs, key=probs.get)
    return {
        'baseline': 'market_favorite',
        'probabilities': probs,
        'direction': direction_map[rec],
        'direction_cn': {'3': '主胜', '1': '平局', '0': '客胜'}[direction_map[rec]],
        'confidence': round(probs[rec], 4),
    }


def baseline_market_implied(odds_baseline: dict) -> Optional[Dict]:
    """Full odds-implied probability distribution (same as market_favorite but keeps all probs)."""
    return baseline_market_favorite(odds_baseline)


def baseline_poisson(poisson_prediction: dict) -> Optional[Dict]:
    """Raw Poisson prediction without adjustments."""
    probs = poisson_prediction.get('probabilities', {})
    if not probs or not isinstance(probs, dict):
        return None
    direction_map = {'home_win': '3', 'draw': '1', 'away_win': '0'}
    rec = max(probs, key=probs.get) if probs else None
    if not rec:
        return None
    return {
        'baseline': 'poisson',
        'probabilities': {k: round(v, 4) for k, v in probs.items()},
        'direction': direction_map.get(rec, '?'),
        'direction_cn': {'3': '主胜', '1': '平局', '0': '客胜'}.get(direction_map.get(rec, '?'), ''),
        'confidence': round(probs[rec], 4),
        'home_xg': poisson_prediction.get('home_xg'),
        'away_xg': poisson_prediction.get('away_xg'),
    }


def baseline_elo(elo_prediction: dict) -> Optional[Dict]:
    """Raw Elo/FIFA prediction without adjustments."""
    probs = elo_prediction.get('predictions', {})
    if not probs or not isinstance(probs, dict):
        return None
    direction_map = {'home_win': '3', 'draw': '1', 'away_win': '0'}
    rec = max(probs, key=probs.get) if probs else None
    if not rec:
        return None
    return {
        'baseline': 'elo',
        'probabilities': {k: round(v, 4) for k, v in probs.items()},
        'direction': direction_map.get(rec, '?'),
        'direction_cn': {'3': '主胜', '1': '平局', '0': '客胜'}.get(direction_map.get(rec, '?'), ''),
        'confidence': round(probs[rec], 4),
        'home_elo': elo_prediction.get('home_elo'),
        'away_elo': elo_prediction.get('away_elo'),
        'strength_method': elo_prediction.get('strength_method'),
    }


def baseline_recent_form(form_comparison: dict) -> Optional[Dict]:
    """Form-only baseline: direction from form score comparison."""
    if not isinstance(form_comparison, dict):
        return None
    last6 = form_comparison.get('last6', {})
    if not isinstance(last6, dict):
        return None
    t1 = last6.get('team1_form', {})
    t2 = last6.get('team2_form', {})
    comp = last6.get('comparison', {})
    if not isinstance(t1, dict) or not isinstance(t2, dict):
        return None

    s1 = float(t1.get('form_score', 0) or 0)
    s2 = float(t2.get('form_score', 0) or 0)
    advantage = comp.get('advantage', 'balanced') if isinstance(comp, dict) else 'balanced'

    # Simple form-based probability estimate
    diff = (s1 - s2) / 100.0
    home_p = max(0.15, min(0.85, 0.40 + diff * 0.8))
    draw_p = max(0.15, 0.28 - abs(diff) * 0.3)
    away_p = max(0.05, 1.0 - home_p - draw_p)
    total = home_p + draw_p + away_p
    probs = {'home_win': round(home_p / total, 4), 'draw': round(draw_p / total, 4), 'away_win': round(away_p / total, 4)}

    rec = max(probs, key=probs.get)
    direction_map = {'home_win': '3', 'draw': '1', 'away_win': '0'}
    return {
        'baseline': 'recent_form',
        'probabilities': probs,
        'direction': direction_map[rec],
        'direction_cn': {'3': '主胜', '1': '平局', '0': '客胜'}[direction_map[rec]],
        'confidence': round(probs[rec], 4),
        'home_form_score': round(s1, 2),
        'away_form_score': round(s2, 2),
    }


def baseline_hybrid_current(final_prediction: dict) -> Optional[Dict]:
    """The current hybrid model's prediction (as-is)."""
    probs = final_prediction.get('probabilities', {})
    if not probs or not isinstance(probs, dict):
        return None
    direction_map = {'home_win': '3', 'draw': '1', 'away_win': '0'}
    rec = max(probs, key=probs.get) if probs else None
    if not rec:
        return None
    return {
        'baseline': 'hybrid_current',
        'probabilities': {k: round(v, 4) for k, v in probs.items()},
        'direction': direction_map.get(rec, '?'),
        'direction_cn': {'3': '主胜', '1': '平局', '0': '客胜'}.get(direction_map.get(rec, '?'), ''),
        'confidence': round(probs[rec], 4),
        'confidence_level': final_prediction.get('confidence_level'),
    }


# ---------------------------------------------------------------------------
# Compute all baselines for a single match
# ---------------------------------------------------------------------------

def compute_all_baselines(
    result: dict,
    odds_baseline: Optional[dict] = None,
    elo_prediction: Optional[dict] = None,
    poisson_prediction: Optional[dict] = None,
    form_comparison: Optional[dict] = None,
) -> Dict[str, dict]:
    """Compute all baseline predictions from analysis results.

    Returns dict keyed by baseline name -> baseline prediction dict.
    """
    baselines = {}
    final_prediction = result.get('final_prediction', {})
    base_prediction = result.get('base_prediction', {})

    # Market favorite
    if odds_baseline:
        b = baseline_market_favorite(odds_baseline)
        if b:
            baselines['market_favorite'] = b
            baselines['market_implied'] = baseline_market_implied(odds_baseline)

    # Poisson
    pp = poisson_prediction or base_prediction.get('poisson', {})
    if pp:
        b = baseline_poisson(pp)
        if b:
            baselines['poisson'] = b

    # Elo
    ep = elo_prediction or {}
    if not ep and isinstance(result.get('elo_prediction'), dict):
        ep = result['elo_prediction']
    if ep:
        b = baseline_elo(ep)
        if b:
            baselines['elo'] = b

    # Recent form
    fc = form_comparison or {}
    if not fc and isinstance(result.get('form_comparison'), dict):
        fc = result['form_comparison']
    if fc:
        b = baseline_recent_form(fc)
        if b:
            baselines['recent_form'] = b

    # Hybrid current
    if final_prediction:
        b = baseline_hybrid_current(final_prediction)
        if b:
            baselines['hybrid_current'] = b

    return baselines


# ---------------------------------------------------------------------------
# Play-type baseline evaluation
# ---------------------------------------------------------------------------

def _evaluate_baseline_play(
    baseline: dict,
    play_type: str,
    match: dict,
    actual_result: Optional[str] = None,
    handicap: float = 0,
    ou_line: Optional[float] = None,
) -> Optional[Dict]:
    """Evaluate a baseline's prediction for a specific play type.

    Returns: {baseline, play_type, direction, is_correct (if actual given), probabilities}
    """
    probs = baseline.get('probabilities', {})
    if not probs:
        return None

    spf_dir = baseline.get('direction', '?')

    if play_type == 'spf':
        is_correct = None
        if actual_result:
            is_correct = 1 if spf_dir == actual_result else 0
        return {
            'baseline': baseline['baseline'],
            'play_type': 'spf',
            'direction': spf_dir,
            'probabilities': probs,
            'is_correct': is_correct,
        }

    if play_type == 'rqspf':
        # Simple RQSPF from SPF direction + handicap
        rqspf_probs = _rqspf_probs_from_spf(probs, handicap)
        rq_dir = max(rqspf_probs, key=rqspf_probs.get) if rqspf_probs else '?'
        is_correct = None
        if actual_result:
            is_correct = 1 if rq_dir == actual_result else 0
        return {
            'baseline': baseline['baseline'],
            'play_type': 'rqspf',
            'direction': rq_dir,
            'probabilities': rqspf_probs,
            'is_correct': is_correct,
        }

    if play_type == 'ou':
        if ou_line is None:
            return None
        home_xg = baseline.get('home_xg') or baseline.get('probabilities', {}).get('home_win', 0.4) * 2.5
        away_xg = baseline.get('away_xg') or baseline.get('probabilities', {}).get('away_win', 0.3) * 2.0
        total_xg = float(home_xg) + float(away_xg)
        ou_probs = _ou_probs_from_xg(total_xg, ou_line)
        ou_dir = 'over' if total_xg > ou_line else 'under'
        is_correct = None
        if actual_result:
            is_correct = 1 if ou_dir == actual_result else 0
        return {
            'baseline': baseline['baseline'],
            'play_type': 'ou',
            'direction': ou_dir,
            'probabilities': ou_probs,
            'is_correct': is_correct,
        }

    return None


def _rqspf_probs_from_spf(spf_probs: dict, handicap: float) -> dict:
    """Simple RQSPF probability from SPF probs and handicap."""
    hw = float(spf_probs.get('home_win', 0.33))
    dr = float(spf_probs.get('draw', 0.33))
    aw = float(spf_probs.get('away_win', 0.33))
    try:
        h = float(handicap)
    except (TypeError, ValueError):
        h = 0.0

    if h == 0:
        return {'3': round(hw, 4), '1': round(dr, 4), '0': round(aw, 4)}

    # Positive handicap: home team gives advantage
    if h > 0:  # home gives handicap
        shift = min(0.15, abs(h) * 0.08)
        rq_win = max(0.05, hw - shift)
        rq_draw = min(0.45, dr + shift * 0.3)
        rq_lose = min(0.85, aw + shift * 0.7)
    else:  # away gives handicap
        shift = min(0.15, abs(h) * 0.08)
        rq_win = min(0.85, hw + shift * 0.7)
        rq_draw = min(0.45, dr + shift * 0.3)
        rq_lose = max(0.05, aw - shift)

    total = rq_win + rq_draw + rq_lose
    if total > 0:
        rq_win /= total
        rq_draw /= total
        rq_lose /= total
    return {'3': round(rq_win, 4), '1': round(rq_draw, 4), '0': round(rq_lose, 4)}


def _ou_probs_from_xg(total_xg: float, line: float) -> dict:
    """Simple O/U probability from expected total goals and line."""
    try:
        t = float(total_xg)
        l = float(line)
    except (TypeError, ValueError):
        return {'over': 0.5, 'under': 0.5}

    # Poisson-based over/under
    import math as _math
    over = sum(
        _math.exp(-t) * t ** g / _math.factorial(g)
        for g in range(int(_math.ceil(l)) + 1, 10)
        if g > l
    )
    under = 1.0 - over
    total = over + under
    return {'over': round(over / total, 4), 'under': round(under / total, 4)}


# ---------------------------------------------------------------------------
# DB persistence
# ---------------------------------------------------------------------------

_CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS model_baselines (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    lottery_match_id TEXT NOT NULL,
    play_type TEXT NOT NULL,
    baseline TEXT NOT NULL,
    direction TEXT,
    probabilities_json TEXT,
    is_correct INTEGER,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE(lottery_match_id, play_type, baseline)
);
"""

_CREATE_INDEX_SQL = """
CREATE INDEX IF NOT EXISTS idx_model_baselines_match
    ON model_baselines(lottery_match_id);
CREATE INDEX IF NOT EXISTS idx_model_baselines_play
    ON model_baselines(play_type, baseline);
"""


def ensure_table(conn: sqlite3.Connection) -> None:
    """Create the model_baselines table if it does not exist."""
    conn.executescript(_CREATE_TABLE_SQL + _CREATE_INDEX_SQL)
    # Add brier_score column if missing
    cols = {r[1] for r in conn.execute("PRAGMA table_info(model_baselines)").fetchall()}
    if 'brier_score' not in cols:
        conn.execute("ALTER TABLE model_baselines ADD COLUMN brier_score REAL")
    conn.commit()


def _compute_brier(evaluated: dict, actual_result: Optional[str]) -> Optional[float]:
    """Compute Brier score for a baseline prediction."""
    if not actual_result:
        return None
    probs = evaluated.get('probabilities', {})
    if not probs:
        return None
    direction_map = {'3': 'home_win', '1': 'draw', '0': 'away_win',
                     'home_win': 'home_win', 'draw': 'draw', 'away_win': 'away_win'}
    actual_key = direction_map.get(actual_result)
    if not actual_key:
        return None
    brier = 0.0
    for key in ('home_win', 'draw', 'away_win'):
        forecast = float(probs.get(key, 0))
        outcome = 1.0 if key == actual_key else 0.0
        brier += (forecast - outcome) ** 2
    return round(brier, 4)


def save_baselines(
    conn: sqlite3.Connection,
    lottery_match_id: str,
    baselines: Dict[str, dict],
    play_types: tuple = ('spf', 'rqspf', 'ou'),
    actual_results: Optional[Dict[str, str]] = None,
    handicap: float = 0,
    ou_line: Optional[float] = None,
) -> int:
    """Save baseline evaluations to model_baselines table.

    Returns number of rows saved.
    """
    ensure_table(conn)
    saved = 0
    for baseline_name, baseline in baselines.items():
        for pt in play_types:
            evaluated = _evaluate_baseline_play(
                baseline, pt, {},
                actual_result=(actual_results or {}).get(pt),
                handicap=handicap,
                ou_line=ou_line,
            )
            if not evaluated:
                continue
            try:
                # Compute Brier score if actual result and probabilities are available
                brier = _compute_brier(evaluated, (actual_results or {}).get(pt))
                conn.execute(
                    """INSERT OR REPLACE INTO model_baselines
                       (lottery_match_id, play_type, baseline, direction, probabilities_json, is_correct, brier_score)
                       VALUES (?, ?, ?, ?, ?, ?, ?)""",
                    (
                        lottery_match_id,
                        evaluated['play_type'],
                        evaluated['baseline'],
                        evaluated.get('direction'),
                        json.dumps(evaluated.get('probabilities', {}), ensure_ascii=False),
                        evaluated.get('is_correct'),
                        brier,
                    ),
                )
                saved += 1
            except Exception as exc:
                logger.debug('save_baselines skip %s/%s/%s: %s', lottery_match_id, pt, baseline_name, exc)
    conn.commit()
    return saved


def query_baseline_accuracy(
    conn: sqlite3.Connection,
    play_type: str = 'spf',
    baseline: Optional[str] = None,
    days: int = 30,
) -> List[Dict]:
    """Query baseline accuracy comparison for a play type.

    Returns list of {baseline, total, correct, accuracy}.
    """
    ensure_table(conn)
    where = ["play_type = ?", "is_correct IS NOT NULL"]
    params: list = [play_type]
    if baseline:
        where.append("baseline = ?")
        params.append(baseline)
    where.append("created_at >= datetime('now', ?)")
    params.append(f'-{days} days')

    rows = conn.execute(
        f"""SELECT baseline,
                   COUNT(*) AS total,
                   SUM(is_correct) AS correct,
                   ROUND(AVG(is_correct), 4) AS accuracy
            FROM model_baselines
            WHERE {' AND '.join(where)}
            GROUP BY baseline
            ORDER BY accuracy DESC""",
        params,
    ).fetchall()
    return [
        {'baseline': r[0], 'total': r[1], 'correct': r[2], 'accuracy': r[3]}
        for r in rows
    ]


def query_baseline_comparison(
    conn: sqlite3.Connection,
    play_type: str = 'spf',
    days: int = 30,
) -> Dict[str, Any]:
    """Full baseline comparison for a play type, including hybrid_current vs market_favorite."""
    rows = query_baseline_accuracy(conn, play_type=play_type, days=days)
    if not rows:
        return {'play_type': play_type, 'baselines': [], 'model_vs_market': None}

    by_name = {r['baseline']: r for r in rows}
    market = by_name.get('market_favorite', {})
    model = by_name.get('hybrid_current', {})

    model_vs_market = None
    if market and model:
        model_vs_market = {
            'market_accuracy': market.get('accuracy'),
            'model_accuracy': model.get('accuracy'),
            'delta_pp': round((model.get('accuracy') or 0) * 100 - (market.get('accuracy') or 0) * 100, 2),
            'beats_market': (model.get('accuracy') or 0) > (market.get('accuracy') or 0),
        }

    return {
        'play_type': play_type,
        'baselines': rows,
        'model_vs_market': model_vs_market,
    }


def query_time_split_comparison(
    conn: sqlite3.Connection,
    play_type: str = 'spf',
    total_days: int = 90,
    train_ratio: float = 0.6,
    val_ratio: float = 0.2,
) -> Dict[str, Any]:
    """Time-split baseline comparison: train / validation / test windows.

    Splits the last `total_days` into three contiguous periods:
      train:      oldest 60%  (parameter learning)
      validation: middle 20%  (hyperparameter tuning)
      test:       newest 20%  (final evaluation, never used for learning)

    Returns per-split accuracy for each baseline, plus Brier scores.
    """
    ensure_table(conn)
    train_days = int(total_days * train_ratio)
    val_days = int(total_days * val_ratio)
    test_days = total_days - train_days - val_days

    splits = {
        'train': (f'-{total_days} days', f'-{total_days - train_days} days'),
        'validation': (f'-{total_days - train_days} days', f'-{total_days - train_days - val_days} days'),
        'test': (f'-{test_days} days', 'now'),
    }

    result = {
        'play_type': play_type,
        'total_days': total_days,
        'train_days': train_days,
        'val_days': val_days,
        'test_days': test_days,
        'splits': {},
    }

    for split_name, (from_clause, to_clause) in splits.items():
        rows = conn.execute(
            """
            SELECT baseline,
                   COUNT(*) AS total,
                   SUM(is_correct) AS correct,
                   ROUND(AVG(is_correct), 4) AS accuracy,
                   ROUND(AVG(CASE WHEN brier_score IS NOT NULL THEN brier_score END), 4) AS avg_brier
            FROM model_baselines
            WHERE play_type = ?
              AND is_correct IS NOT NULL
              AND created_at >= datetime('now', ?)
              AND created_at < datetime('now', ?)
            GROUP BY baseline
            ORDER BY accuracy DESC
            """,
            (play_type, from_clause, to_clause),
        ).fetchall()

        result['splits'][split_name] = [
            {
                'baseline': r[0],
                'total': r[1],
                'correct': r[2],
                'accuracy': r[3],
                'avg_brier': r[4],
            }
            for r in rows
        ]

    # Check if model beats market on test set (the only set that matters)
    test_rows = result['splits'].get('test', [])
    test_by_name = {r['baseline']: r for r in test_rows}
    market_test = test_by_name.get('market_favorite', {})
    model_test = test_by_name.get('hybrid_current', {})

    result['test_model_vs_market'] = None
    if market_test and model_test:
        m_acc = market_test.get('accuracy') or 0
        o_acc = model_test.get('accuracy') or 0
        result['test_model_vs_market'] = {
            'market_accuracy': m_acc,
            'model_accuracy': o_acc,
            'delta_pp': round((o_acc - m_acc) * 100, 2),
            'beats_market': o_acc > m_acc,
            'market_brier': market_test.get('avg_brier'),
            'model_brier': model_test.get('avg_brier'),
        }

    # Check for overfitting: train accuracy >> test accuracy
    train_rows = result['splits'].get('train', [])
    train_by_name = {r['baseline']: r for r in train_rows}
    model_train = train_by_name.get('hybrid_current', {})
    if model_train and model_test:
        train_acc = model_train.get('accuracy') or 0
        test_acc = model_test.get('accuracy') or 0
        gap_pp = round((train_acc - test_acc) * 100, 2)
        result['overfitting_check'] = {
            'train_accuracy': train_acc,
            'test_accuracy': test_acc,
            'gap_pp': gap_pp,
            'likely_overfitting': gap_pp > 5,
        }

    return result


def query_competition_split_comparison(
    conn: sqlite3.Connection,
    play_type: str = 'spf',
    days: int = 90,
) -> Dict[str, Any]:
    """By-competition baseline comparison.

    Groups model_baselines by competition type (from lottery_matches.league_name_cn)
    and computes accuracy per competition for each baseline.
    """
    ensure_table(conn)

    rows = conn.execute(
        """
        SELECT mb.baseline,
               COALESCE(lm.league_name_cn, 'unknown') AS competition,
               COUNT(*) AS total,
               SUM(mb.is_correct) AS correct,
               ROUND(AVG(mb.is_correct), 4) AS accuracy
        FROM model_baselines mb
        LEFT JOIN lottery_matches lm ON mb.lottery_match_id = lm.lottery_match_id
        WHERE mb.play_type = ?
          AND mb.is_correct IS NOT NULL
          AND mb.created_at >= datetime('now', ?)
        GROUP BY mb.baseline, competition
        ORDER BY competition, accuracy DESC
        """,
        (play_type, f'-{days} days'),
    ).fetchall()

    by_competition = {}
    for r in rows:
        comp = r[1]
        if comp not in by_competition:
            by_competition[comp] = []
        by_competition[comp].append({
            'baseline': r[0],
            'total': r[2],
            'correct': r[3],
            'accuracy': r[4],
        })

    return {
        'play_type': play_type,
        'days': days,
        'by_competition': by_competition,
    }
