"""
足球分析模块
"""

from .core import (
    get_elo_rating,
    calculate_xg,
    predict_match,
    get_league_importance,
    get_team_upcoming_fixtures,
    get_team_league_position,
    analyze_team_motivation,
    generate_match_summary,
    get_recent_trend_analysis,
    get_h2h_stats,
    calculate_h2h_summary
)

__all__ = [
    'get_elo_rating',
    'calculate_xg',
    'predict_match',
    'get_league_importance',
    'get_team_upcoming_fixtures',
    'get_team_league_position',
    'analyze_team_motivation',
    'generate_match_summary',
    'get_recent_trend_analysis',
    'get_h2h_stats',
    'calculate_h2h_summary'
]
