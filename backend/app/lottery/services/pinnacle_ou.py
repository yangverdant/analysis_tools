"""
pinnacle_ou.py — Pinnacle O/U赔率查询工具

优先级链:
1. oddsfe_matches表 (football_v2.db, 由collect.py每日同步)
2. oddsfe_merged.db直接查询 (fallback, 可能略旧)
3. None → 调用方走TTG → Poisson

返回: 盘口线、over/under赔率、去vig后的隐含概率、最佳盘口线
"""

import sqlite3
import os
import logging
from typing import Optional, Dict

logger = logging.getLogger(__name__)

# 默认DB路径
_FOOTBALL_V2_DEFAULT = os.path.abspath(
    os.path.join(os.path.dirname(__file__), '..', '..', '..', '..', 'data', 'football_v2.db')
)
_ODDSFE_MERGED_DEFAULT = os.path.abspath(
    os.path.join(os.path.dirname(__file__), '..', '..', '..', '..', 'fetchers', 'odds_feed_api', 'oddsfe_merged.db')
)


def get_pinnacle_ou_odds(
    home_team_name: str,
    away_team_name: str,
    match_date: str,
    football_v2_path: str = None,
    oddsfe_db_path: str = None,
) -> Optional[Dict]:
    """Query Pinnacle O/U line from oddsfe data.

    Args:
        home_team_name: English team name (normalized)
        away_team_name: English team name (normalized)
        match_date: YYYY-MM-DD format
        football_v2_path: Path to football_v2.db
        oddsfe_db_path: Optional path to oddsfe_merged.db

    Returns:
        {
            'line': float,            # best line (e.g. 2.5)
            'over_odds': float,       # raw over odds
            'under_odds': float,      # raw under odds
            'over_prob': float,       # implied probability (vig removed)
            'under_prob': float,      # implied probability (vig removed)
            'source': str,            # 'oddsfe_matches' | 'oddsfe_merged_db'
            'all_lines': dict,        # all available lines with odds
        }
        or None if no data found.
    """
    if not home_team_name or not away_team_name:
        return None

    if football_v2_path is None:
        football_v2_path = _FOOTBALL_V2_DEFAULT

    # Priority 1: oddsfe_matches table in football_v2.db
    result = _query_oddsfe_matches(home_team_name, away_team_name, match_date, football_v2_path)
    if result:
        return result

    # Priority 2: oddsfe_merged.db direct query
    if oddsfe_db_path is None:
        oddsfe_db_path = _ODDSFE_MERGED_DEFAULT
    result = _query_oddsfe_merged(home_team_name, away_team_name, match_date, oddsfe_db_path)
    if result:
        return result

    return None


def _remove_vig(over_odds: float, under_odds: float) -> tuple:
    """Remove vig from over/under odds.

    Returns: (over_prob, under_prob) summing to 1.0
    """
    if over_odds <= 1.0 or under_odds <= 1.0:
        return (0.5, 0.5)

    over_implied = 1.0 / over_odds
    under_implied = 1.0 / under_odds
    total = over_implied + under_implied

    if total <= 0:
        return (0.5, 0.5)

    return (over_implied / total, under_implied / total)


def _date_range(match_date: str) -> list:
    """Generate date range for UTC offset. Beijing=UTC+8, so match_date
    could be previous day in UTC."""
    from datetime import datetime, timedelta
    dates = [f'{match_date}%']
    try:
        dt = datetime.strptime(match_date, '%Y-%m-%d')
        prev = (dt - timedelta(days=1)).strftime('%Y-%m-%d')
        dates.append(f'{prev}%')
    except ValueError:
        pass
    return dates


def _query_oddsfe_matches(
    home_team_name: str,
    away_team_name: str,
    match_date: str,
    db_path: str,
) -> Optional[Dict]:
    """Query oddsfe_matches table in football_v2.db."""
    if not os.path.exists(db_path):
        return None

    try:
        conn = sqlite3.connect(db_path, timeout=10)
        conn.row_factory = sqlite3.Row
        date_patterns = _date_range(match_date)

        row = None
        for dp in date_patterns:
            # Try exact match on team names
            row = conn.execute("""
                SELECT ou_pinnacle_line, ou_pinnacle_over, ou_pinnacle_under
                FROM oddsfe_matches
                WHERE (home_team_name = ? AND away_team_name = ?)
                AND event_start_at LIKE ?
                AND ou_pinnacle_line IS NOT NULL
                ORDER BY ou_pinnacle_updated_at DESC
                LIMIT 1
            """, (home_team_name, away_team_name, dp)).fetchone()
            if row:
                break

            # Try reversed (home/away may be swapped)
            row = conn.execute("""
                SELECT ou_pinnacle_line, ou_pinnacle_over, ou_pinnacle_under
                FROM oddsfe_matches
                WHERE (home_team_name = ? AND away_team_name = ?)
                AND event_start_at LIKE ?
                AND ou_pinnacle_line IS NOT NULL
                ORDER BY ou_pinnacle_updated_at DESC
                LIMIT 1
            """, (away_team_name, home_team_name, dp)).fetchone()
            if row:
                break

        conn.close()

        if not row or not row['ou_pinnacle_line']:
            return None

        line = float(row['ou_pinnacle_line'])
        over_odds = float(row['ou_pinnacle_over'])
        under_odds = float(row['ou_pinnacle_under'])

        if line <= 0 or over_odds <= 1.0 or under_odds <= 1.0:
            return None

        over_prob, under_prob = _remove_vig(over_odds, under_odds)

        return {
            'line': line,
            'over_odds': over_odds,
            'under_odds': under_odds,
            'over_prob': round(over_prob, 4),
            'under_prob': round(under_prob, 4),
            'source': 'oddsfe_matches',
            'all_lines': {str(line): {'over': over_odds, 'under': under_odds}},
        }

    except Exception as e:
        logger.debug(f'oddsfe_matches查询失败: {e}')
        return None


def _query_oddsfe_merged(
    home_team_name: str,
    away_team_name: str,
    match_date: str,
    db_path: str,
) -> Optional[Dict]:
    """Query oddsfe_merged.db directly using OVER_UNDER_prematch_lines column.

    This parses the same format as get_oddsfe_ou_line() in lottery.py.
    """
    if not os.path.exists(db_path):
        return None

    try:
        conn = sqlite3.connect(db_path, timeout=10)
        date_patterns = _date_range(match_date)

        row = None
        for dp in date_patterns:
            # Try expanded PINNACLE columns first (faster)
            row = conn.execute("""
                SELECT event_id, "OVER_UNDER_prematch_PINNACLE_line",
                       "OVER_UNDER_prematch_PINNACLE_over",
                       "OVER_UNDER_prematch_PINNACLE_under"
                FROM oddsfe
                WHERE (home_team_name = ? AND away_team_name = ?)
                AND event_start_at LIKE ?
                AND "OVER_UNDER_prematch_PINNACLE_line" IS NOT NULL
                AND "OVER_UNDER_prematch_PINNACLE_line" != ''
                LIMIT 1
            """, (home_team_name, away_team_name, dp)).fetchone()
            if row and row[1]:
                conn.close()
                line = float(row[1])
                over_odds = float(row[2]) if row[2] else 0
                under_odds = float(row[3]) if row[3] else 0
                if line > 0 and over_odds > 1 and under_odds > 1:
                    over_prob, under_prob = _remove_vig(over_odds, under_odds)
                    return {
                        'line': line,
                        'over_odds': over_odds,
                        'under_odds': under_odds,
                        'over_prob': round(over_prob, 4),
                        'under_prob': round(under_prob, 4),
                        'source': 'oddsfe_merged_db',
                        'all_lines': {str(line): {'over': over_odds, 'under': under_odds}},
                    }
            if not row:
                # Try reversed
                row = conn.execute("""
                    SELECT event_id, "OVER_UNDER_prematch_PINNACLE_line",
                           "OVER_UNDER_prematch_PINNACLE_over",
                           "OVER_UNDER_prematch_PINNACLE_under"
                    FROM oddsfe
                    WHERE (home_team_name = ? AND away_team_name = ?)
                    AND event_start_at LIKE ?
                    AND "OVER_UNDER_prematch_PINNACLE_line" IS NOT NULL
                    AND "OVER_UNDER_prematch_PINNACLE_line" != ''
                    LIMIT 1
                """, (away_team_name, home_team_name, dp)).fetchone()
                if row and row[1]:
                    conn.close()
                    line = float(row[1])
                    over_odds = float(row[2]) if row[2] else 0
                    under_odds = float(row[3]) if row[3] else 0
                    if line > 0 and over_odds > 1 and under_odds > 1:
                        over_prob, under_prob = _remove_vig(over_odds, under_odds)
                        return {
                            'line': line,
                            'over_odds': over_odds,
                            'under_odds': under_odds,
                            'over_prob': round(over_prob, 4),
                            'under_prob': round(under_prob, 4),
                            'source': 'oddsfe_merged_db',
                            'all_lines': {str(line): {'over': over_odds, 'under': under_odds}},
                        }

            # Fallback: try OVER_UNDER_prematch_lines format
            row2 = conn.execute("""
                SELECT event_id, OVER_UNDER_prematch_lines FROM oddsfe
                WHERE (home_team_name = ? AND away_team_name = ?)
                AND event_start_at LIKE ?
                AND OVER_UNDER_prematch_lines IS NOT NULL
                AND OVER_UNDER_prematch_lines != ''
                LIMIT 1
            """, (home_team_name, away_team_name, dp)).fetchone()
            if not row2:
                row2 = conn.execute("""
                    SELECT event_id, OVER_UNDER_prematch_lines FROM oddsfe
                    WHERE (home_team_name = ? AND away_team_name = ?)
                    AND event_start_at LIKE ?
                    AND OVER_UNDER_prematch_lines IS NOT NULL
                    AND OVER_UNDER_prematch_lines != ''
                    LIMIT 1
                """, (away_team_name, home_team_name, dp)).fetchone()
            if row2:
                result = _parse_ou_lines(row2[1])
                if result:
                    conn.close()
                    result['source'] = 'oddsfe_merged_db'
                    return result

        conn.close()
        return None

    except Exception as e:
        logger.debug(f'oddsfe_merged查询失败: {e}')
        return None


def _parse_ou_lines(lines_str: str) -> Optional[Dict]:
    """Parse OVER_UNDER_prematch_lines packed format."""
    if not lines_str:
        return None

    pinnacle_data = {}

    for segment in lines_str.split('||'):
        if not segment.strip():
            continue
        parts = segment.split('|')
        line_info = parts[0]
        line_parts = line_info.split(':')
        line_val = line_parts[0]

        # Find Pinnacle in bookmaker data
        for bm in parts[1:]:
            bm_parts = bm.split(':')
            if len(bm_parts) >= 3 and bm_parts[0] == 'PINNACLE':
                try:
                    pinnacle_data[line_val] = {
                        'over': float(bm_parts[1]),
                        'under': float(bm_parts[2])
                    }
                except ValueError:
                    pass

        # Fallback: use line_info summary odds
        if line_val not in pinnacle_data:
            ou_str = line_parts[1] if len(line_parts) > 1 else ''
            over_under = ou_str.split('/')
            if len(over_under) >= 2:
                try:
                    pinnacle_data[line_val] = {
                        'over': float(over_under[0]),
                        'under': float(over_under[1])
                    }
                except ValueError:
                    pass

    if not pinnacle_data:
        return None

    # Find best line (smallest over/under odds gap = tightest market)
    best_line = None
    best_gap = float('inf')
    for line_val, odds in pinnacle_data.items():
        try:
            gap = abs(odds['over'] - odds['under'])
            if gap < best_gap:
                best_gap = gap
                best_line = float(line_val)
                best_over = odds['over']
                best_under = odds['under']
        except (ValueError, KeyError):
            continue

    if best_line is None:
        return None

    over_prob, under_prob = _remove_vig(best_over, best_under)

    return {
        'line': best_line,
        'over_odds': best_over,
        'under_odds': best_under,
        'over_prob': round(over_prob, 4),
        'under_prob': round(under_prob, 4),
        'all_lines': pinnacle_data,
    }
