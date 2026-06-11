"""
字段映射表 — 每个fetcher每个函数的 原始字段名→统一字段名 映射

格式:
{
    "fetcher_name": {
        "func_name": {
            "原始字段": "统一字段",       # 直接重命名
            "_computed": {                 # 需要计算的派生字段
                "统一字段": lambda rec: ...
            },
            "_meta": {                     # 元信息
                "data_type": "match"       # match/odds/prediction/lineup/injury/news/weather/standing/player
            }
        }
    }
}

统一字段命名规范:
- 比赛类: match_key, date, time, home_team, away_team, home_score, away_score, status, league, league_standard, league_id, round, venue, referee, match_id
- 赔率类: match_key, date, home_team, away_team, league, bookmaker, home_win, draw, away_win, over_2_5, under_2_5, handicap, ah_home, ah_away, line, over_val, under_val, btts_yes, btts_no
- xG/预测类: match_key, date, home_team, away_team, league, home_xg, away_xg, home_win_prob, draw_prob, away_win_prob, over_2_5_prob, btts_yes_prob
- 阵容类: match_key, date, home_team, away_team, home_lineup, away_lineup, home_formation, away_formation
- 伤病类: player_name, team, team_standard, status, reason, date, league
- 新闻类: title, url, date, source, matched_teams
- 天气类: match_key, date, home_team, city, temp_c, humidity, wind, description, precipitation
- 积分榜类: league, team, position, played, won, drawn, lost, goals_for, goals_against, goal_diff, points
- 球员类: player_name, team, position, market_value, number
"""

from fetchers.common.team_names import normalize_team_name
from fetchers.common.league_names import normalize_league_name
from fetchers.common.date_utils import normalize_date
from fetchers.common.match_key import make_match_key


# ==================== 比赛结果/赛程类 ====================

APIFOOTBALL_MAP = {
    "get_livescores": {
        "match_id": "match_id",
        "home_team": "home_team",
        "away_team": "away_team",
        "home_score": "home_score",
        "away_score": "away_score",
        "date": "date",
        "time": "time",
        "status": "status",
        "league": "league",
        "league_standard": "league_standard",
        "league_id": "league_id",
        "round": "round",
        "source": "source",
        "_computed": {
            "match_key": lambda r: make_match_key(
                r.get("date", ""), r.get("home_team", ""), r.get("away_team", ""))
        },
        "_meta": {"data_type": "match"}
    },
    "get_fixtures": {
        "match_id": "match_id",
        "home_team": "home_team",
        "home_team_id": "home_team_id",
        "away_team": "away_team",
        "away_team_id": "away_team_id",
        "home_score": "home_score",
        "away_score": "away_score",
        "home_score_ht": "home_score_ht",
        "away_score_ht": "away_score_ht",
        "date": "date",
        "time": "time",
        "status": "status",
        "league": "league",
        "league_standard": "league_standard",
        "league_id": "league_id",
        "round": "round",
        "venue": "venue",
        "referee": "referee",
        "source": "source",
        "_computed": {
            "match_key": lambda r: make_match_key(
                r.get("date", ""), r.get("home_team", ""), r.get("away_team", ""))
        },
        "_meta": {"data_type": "match"}
    },
    "get_match_detail": {
        "match_id": "match_id",
        "date": "date",
        "time": "time",
        "status": "status",
        "home_team": "home_team",
        "home_team_id": "home_team_id",
        "away_team": "away_team",
        "away_team_id": "away_team_id",
        "home_score": "home_score",
        "away_score": "away_score",
        "home_score_ht": "home_score_ht",
        "away_score_ht": "away_score_ht",
        "league": "league",
        "league_id": "league_id",
        "round": "round",
        "venue": "venue",
        "referee": "referee",
        "goalscorer": "goalscorer",
        "substitutions": "substitutions",
        "cards": "cards",
        "lineup": "lineup",
        "statistics": "statistics",
        "statistics_1half": "statistics_1half",
        "source": "source",
        "_computed": {
            "match_key": lambda r: make_match_key(
                r.get("date", ""), r.get("home_team", ""), r.get("away_team", ""))
        },
        "_meta": {"data_type": "match"}
    },
    "get_standings": {
        "position": "position",
        "team": "team",
        "team_id": "team_id",
        "played": "played",
        "won": "won",
        "drawn": "drawn",
        "lost": "lost",
        "goals_for": "goals_for",
        "goals_against": "goals_against",
        "goal_difference": "goal_difference",
        "points": "points",
        "league": "league",
        "source": "source",
        "_computed": {},
        "_meta": {"data_type": "standing"}
    },
    "get_match_odds": {
        "match_id": "match_id",
        "bookmaker": "bookmaker",
        "updated": "updated",
        "home_win": "home_win",
        "draw": "draw",
        "away_win": "away_win",
        "home_win_or_draw": "home_win_or_draw",
        "home_win_or_away": "home_win_or_away",
        "draw_or_away": "draw_or_away",
        "over_2_5": "over_2_5",
        "under_2_5": "under_2_5",
        "btts_yes": "btts_yes",
        "btts_no": "btts_no",
        "source": "source",
        "_computed": {
            "match_key": lambda r: r.get("match_id", "")
        },
        "_meta": {"data_type": "odds"}
    },
    "get_predictions": {
        "match_id": "match_id",
        "home_team": "home_team",
        "away_team": "away_team",
        "date": "date",
        "league": "league",
        "league_standard": "league_standard",
        "league_id": "league_id",
        "home_win_prob": "home_win_prob",
        "draw_prob": "draw_prob",
        "away_win_prob": "away_win_prob",
        "over_2_5_prob": "over_2_5_prob",
        "under_2_5_prob": "under_2_5_prob",
        "btts_yes_prob": "btts_yes_prob",
        "btts_no_prob": "btts_no_prob",
        "source": "source",
        "_computed": {
            "match_key": lambda r: make_match_key(
                r.get("date", ""), r.get("home_team", ""), r.get("away_team", ""))
        },
        "_meta": {"data_type": "prediction"}
    },
    "get_h2h": {
        "match_id": "match_id",
        "home_team": "home_team",
        "away_team": "away_team",
        "home_score": "home_score",
        "away_score": "away_score",
        "date": "date",
        "league": "league",
        "source": "source",
        "_computed": {
            "match_key": lambda r: make_match_key(
                r.get("date", ""), r.get("home_team", ""), r.get("away_team", ""))
        },
        "_meta": {"data_type": "match"}
    },
}

FOOTBALL_DATA_ORG_MAP = {
    "get_matches": {
        "match_id": "match_id",
        "date": "date",
        "status": "status",
        "matchday": "round",
        "home_team": "home_team",
        "away_team": "away_team",
        "home_score": "home_score",
        "away_score": "away_score",
        "league": "league",
        "league_id": "league_id",
        "source": "source",
        "_computed": {
            "match_key": lambda r: make_match_key(
                r.get("date", ""), r.get("home_team", ""), r.get("away_team", ""))
        },
        "_meta": {"data_type": "match"}
    },
    "get_standings": {
        "position": "position",
        "team": "team",
        "team_id": "team_id",
        "played": "played",
        "won": "won",
        "drawn": "drawn",
        "lost": "lost",
        "goals_for": "goals_for",
        "goals_against": "goals_against",
        "goal_difference": "goal_difference",
        "points": "points",
        "form": "form",
        "league": "league",
        "league_code": "league_id",
        "season": "season",
        "source": "source",
        "_computed": {
            "league_standard": lambda r: normalize_league_name(r.get("league", "") or r.get("league_code", "")),
            "team_standard": lambda r: normalize_team_name(r.get("team", "")),
        },
        "_meta": {"data_type": "standing"}
    },
}

ESPN_MAP = {
    "get_livescores": {
        "home_team": "home_team",
        "away_team": "away_team",
        "home_score": "home_score",
        "away_score": "away_score",
        "date": "date",
        "status": "status",
        "source": "source",
        "_computed": {
            "match_key": lambda r: make_match_key(
                r.get("date", ""), r.get("home_team", ""), r.get("away_team", ""))
        },
        "_meta": {"data_type": "match"}
    },
}

SOCCERWAY_MAP = {
    "get_matches": {
        "home_team": "home_team",
        "away_team": "away_team",
        "home_score": "home_score",
        "away_score": "away_score",
        "league": "league",
        "league_standard": "league_standard",
        "source": "source",
        "_computed": {
            "match_key": lambda r: make_match_key(
                "", r.get("home_team", ""), r.get("away_team", ""))
        },
        "_meta": {"data_type": "match"}
    },
}

SCORES365_MAP = {
    "get_livescores": {
        "match_id": "match_id",
        "home_team": "home_team",
        "away_team": "away_team",
        "home_score": "home_score",
        "away_score": "away_score",
        "date": "date",
        "status": "status",
        "league": "league",
        "league_id": "league_id",
        "source": "source",
        "_computed": {
            "match_key": lambda r: make_match_key(
                r.get("date", ""), r.get("home_team", ""), r.get("away_team", ""))
        },
        "_meta": {"data_type": "match"}
    },
}

FLASHLIVE_MAP = {
    "get_livescores": {
        "match_id": "match_id",
        "home_team": "home_team",
        "away_team": "away_team",
        "home_score": "home_score",
        "away_score": "away_score",
        "date": "date",
        "status": "status",
        "league": "league",
        "league_id": "league_id",
        "source": "source",
        "_computed": {
            "match_key": lambda r: make_match_key(
                r.get("date", ""), r.get("home_team", ""), r.get("away_team", ""))
        },
        "_meta": {"data_type": "match"}
    },
}

SOFASCORE_MAP = {
    "get_livescores": {
        "match_id": "match_id",
        "home_team": "home_team",
        "away_team": "away_team",
        "home_score": "home_score",
        "away_score": "away_score",
        "date": "date",
        "status": "status",
        "league": "league",
        "league_id": "league_id",
        "source": "source",
        "_computed": {
            "match_key": lambda r: make_match_key(
                r.get("date", ""), r.get("home_team", ""), r.get("away_team", ""))
        },
        "_meta": {"data_type": "match"}
    },
}

THESPORTSDB_MAP = {
    "get_events": {
        "match_id": "match_id",
        "home_team": "home_team",
        "away_team": "away_team",
        "home_score": "home_score",
        "away_score": "away_score",
        "date": "date",
        "league": "league",
        "league_id": "league_id",
        "season": "season",
        "venue": "venue",
        "source": "source",
        "_computed": {
            "match_key": lambda r: make_match_key(
                r.get("date", ""), r.get("home_team", ""), r.get("away_team", ""))
        },
        "_meta": {"data_type": "match"}
    },
    "get_players": {
        "player_name": "player_name",
        "team": "team",
        "position": "position",
        "number": "number",
        "thumb": "thumb",
        "source": "source",
        "_computed": {},
        "_meta": {"data_type": "player"}
    },
}

OPENLIGADB_MAP = {
    "get_matches": {
        "match_id": "match_id",
        "date": "date",
        "home_team": "home_team",
        "away_team": "away_team",
        "home_score": "home_score",
        "away_score": "away_score",
        "league": "league",
        "matchday": "round",
        "source": "source",
        "_computed": {
            "match_key": lambda r: make_match_key(
                r.get("date", ""), r.get("home_team", ""), r.get("away_team", ""))
        },
        "_meta": {"data_type": "match"}
    },
}

API_SPORTS_MAP = {
    "get_fixtures": {
        "match_id": "match_id",
        "date": "date",
        "home_team": "home_team",
        "away_team": "away_team",
        "home_score": "home_score",
        "away_score": "away_score",
        "league": "league",
        "league_id": "league_id",
        "round": "round",
        "status": "status",
        "source": "source",
        "_computed": {
            "match_key": lambda r: make_match_key(
                r.get("date", ""), r.get("home_team", ""), r.get("away_team", ""))
        },
        "_meta": {"data_type": "match"}
    },
    "get_injuries": {
        "player": "player_name",
        "player_id": "player_id",
        "team": "team",
        "team_id": "team_id",
        "reason": "reason",
        "type": "type",
        "source": "source",
        "_computed": {
            "team_standard": lambda r: normalize_team_name(r.get("team", "")),
        },
        "_meta": {"data_type": "injury"}
    },
}

FBREF_MAP = {
    "get_match_results": {
        "home_team": "home_team",
        "away_team": "away_team",
        "home_goals": "home_score",
        "away_goals": "away_score",
        "date": "date",
        "league": "league",
        "source": "source",
        "_computed": {
            "match_key": lambda r: make_match_key(
                r.get("date", ""), r.get("home_team", ""), r.get("away_team", ""))
        },
        "_meta": {"data_type": "match"}
    },
    "get_league_standings": {
        "league": "league",
        "team": "team",
        "rank": "position",
        "points": "points",
        "goal_diff": "goal_difference",
        "source": "source",
        "_computed": {},
        "_meta": {"data_type": "standing"}
    },
}


# ==================== 赔率类 ====================

OKOOO_MAP = {
    "get_match_basic": {
        "match_id": "match_id",
        "home_team": "home_team",
        "home_team_standard": "home_team_standard",
        "away_team": "away_team",
        "away_team_standard": "away_team_standard",
        "league": "league",
        "date": "date",
        "source": "source",
        "_computed": {
            "match_key": lambda r: make_match_key(
                r.get("date", ""),
                r.get("home_team_standard") or r.get("home_team", ""),
                r.get("away_team_standard") or r.get("away_team", ""))
        },
        "_meta": {"data_type": "match"}
    },
    "get_odds_change": {
        "match_id": "match_id",
        "company_id": "company_id",
        "h": "hour",
        "odds_home": "home_win",
        "odds_draw": "draw",
        "odds_away": "away_win",
        "source": "source",
        "_computed": {
            "match_key": lambda r: r.get("match_id", "")
        },
        "_meta": {"data_type": "odds"}
    },
    "get_ah_change": {
        "match_id": "match_id",
        "company_id": "company_id",
        "h": "hour",
        "handicap": "handicap",
        "ah_home": "ah_home",
        "ah_away": "ah_away",
        "source": "source",
        "_computed": {
            "match_key": lambda r: r.get("match_id", "")
        },
        "_meta": {"data_type": "odds"}
    },
    "get_ou_change": {
        "match_id": "match_id",
        "company_id": "company_id",
        "h": "hour",
        "line": "line",
        "over": "over_val",
        "under": "under_val",
        "source": "source",
        "_computed": {
            "match_key": lambda r: r.get("match_id", "")
        },
        "_meta": {"data_type": "odds"}
    },
    "get_full_odds_matrix": {
        "match_id": "match_id",
        "odds": "odds",
        "source": "source",
        "_computed": {
            "match_key": lambda r: r.get("match_id", "")
        },
        "_meta": {"data_type": "odds"}
    },
    "get_league_schedule": {
        "match_id": "match_id",
        "home_team_cn": "home_team_cn",
        "away_team_cn": "away_team_cn",
        "league_cn": "league_cn",
        "date_time": "date_time",
        "home_win": "home_win",
        "draw": "draw",
        "away_win": "away_win",
        "home_score": "home_score",
        "source": "source",
        "_computed": {
            "match_key": lambda r: make_match_key(
                r.get("date_time", "").split(" ")[0] if " " in r.get("date_time", "") else "",
                r.get("home_team_cn", ""),
                r.get("away_team_cn", "")),
            "home_team": lambda r: normalize_team_name(r.get("home_team_cn", "")),
            "away_team": lambda r: normalize_team_name(r.get("away_team_cn", "")),
            "league": lambda r: normalize_league_name(r.get("league_cn", "")),
            "league_standard": lambda r: normalize_league_name(r.get("league_cn", "")),
            "date": lambda r: r.get("date_time", "").split(" ")[0] if " " in r.get("date_time", "") else r.get("date_time", ""),
            "time": lambda r: r.get("date_time", "").split(" ")[1] if " " in r.get("date_time", "") else "",
        },
        "_meta": {"data_type": "odds"}
    },
}

THE_ODDS_API_MAP = {
    "get_odds": {
        "date": "date",
        "home_team": "home_team",
        "away_team": "away_team",
        "league": "league",
        "market_type": "market_type",
        "odds_data": "odds_data",
        "source": "source",
        "_computed": {
            "match_key": lambda r: make_match_key(
                r.get("date", ""), r.get("home_team", ""), r.get("away_team", ""))
        },
        "_meta": {"data_type": "odds"}
    },
}

ODDS_API_MAP = {
    "get_odds_feed": {
        "date": "date",
        "home_team": "home_team",
        "away_team": "away_team",
        "league": "league",
        "home_win": "home_win",
        "draw": "draw",
        "away_win": "away_win",
        "source": "source",
        "_computed": {
            "match_key": lambda r: make_match_key(
                r.get("date", ""), r.get("home_team", ""), r.get("away_team", ""))
        },
        "_meta": {"data_type": "odds"}
    },
    "get_bet365_odds": {
        "input_id": "input_id",
        "data": "data",
        "source": "source",
        "_computed": {
            "match_key": lambda r: r.get("input_id", "")
        },
        "_meta": {"data_type": "odds"}
    },
    "get_fb_odds": {
        "input_id": "input_id",
        "data": "data",
        "source": "source",
        "_computed": {
            "match_key": lambda r: r.get("input_id", "")
        },
        "_meta": {"data_type": "odds"}
    },
}

SPORTTERY_MAP = {
    "get_selling_matches": {
        "match_id": "match_id",
        "home_team_cn": "home_team_cn",
        "away_team_cn": "away_team_cn",
        "league_cn": "league_cn",
        "match_date": "date",
        "sp_home": "home_win",
        "sp_draw": "draw",
        "sp_away": "away_win",
        "source": "source",
        "_computed": {
            "match_key": lambda r: make_match_key(
                r.get("match_date", ""), r.get("home_team_cn", ""), r.get("away_team_cn", "")),
            "home_team": lambda r: normalize_team_name(r.get("home_team_cn", "")),
            "away_team": lambda r: normalize_team_name(r.get("away_team_cn", "")),
            "league": lambda r: normalize_league_name(r.get("league_cn", "")),
        },
        "_meta": {"data_type": "odds"}
    },
    "get_match_list": {
        "lottery_match_id": "match_id",
        "home_team_cn": "home_team_cn",
        "away_team_cn": "away_team_cn",
        "league_name_cn": "league_cn",
        "match_date": "date",
        "match_time": "time",
        "handicap_line": "handicap_line",
        "odds": "odds",
        "sell_end_time": "sell_end_time",
        "_computed": {
            "match_key": lambda r: make_match_key(
                r.get("match_date", ""), r.get("home_team_cn", ""), r.get("away_team_cn", "")),
            "home_team": lambda r: normalize_team_name(r.get("home_team_cn", "")),
            "away_team": lambda r: normalize_team_name(r.get("away_team_cn", "")),
            "league": lambda r: normalize_league_name(r.get("league_name_cn", "")),
            "league_standard": lambda r: normalize_league_name(r.get("league_name_cn", "")),
        },
        "_meta": {"data_type": "match"}
    },
}


# ==================== xG/预测类 ====================

UNDERSTAT_MAP = {
    "get_match_xg": {
        "home_team": "home_team",
        "away_team": "away_team",
        "home_xg": "home_xg",
        "away_xg": "away_xg",
        "source": "source",
        "_computed": {
            "match_key": lambda r: make_match_key(
                "", r.get("home_team", ""), r.get("away_team", ""))
        },
        "_meta": {"data_type": "prediction"}
    },
    "get_league_teams_xg": {
        "team": "team",
        "league": "league",
        "season": "season",
        "games": "games",
        "goals": "goals",
        "xg": "xg",
        "xa": "xa",
        "xga": "xga",
        "npg": "npg",
        "npxg": "npxg",
        "npxga": "npxga",
        "pts": "pts",
        "source": "source",
        "_computed": {},
        "_meta": {"data_type": "prediction"}
    },
    "get_league_players_xg": {
        "player_name": "player_name",
        "team": "team",
        "league": "league",
        "games": "games",
        "goals": "goals",
        "xg": "xg",
        "xa": "xa",
        "npg": "npg",
        "npxg": "npxg",
        "source": "source",
        "_computed": {},
        "_meta": {"data_type": "prediction"}
    },
}

STATSBOMB_MAP = {
    "get_match_xg": {
        "home_team": "home_team",
        "away_team": "away_team",
        "home_xg": "home_xg",
        "away_xg": "away_xg",
        "match_date": "date",
        "competition": "league",
        "source": "source",
        "_computed": {
            "match_key": lambda r: make_match_key(
                r.get("match_date", ""), r.get("home_team", ""), r.get("away_team", ""))
        },
        "_meta": {"data_type": "prediction"}
    },
}

SPORTMONKS_MAP = {
    "get_predictions": {
        "fixture_id": "match_id",
        "data": "data",
        "source": "source",
        "_computed": {
            "match_key": lambda r: r.get("fixture_id", "")
        },
        "_meta": {"data_type": "prediction"}
    },
    "get_lineups": {
        "fixture_id": "match_id",
        "data": "data",
        "source": "source",
        "_computed": {
            "match_key": lambda r: r.get("fixture_id", "")
        },
        "_meta": {"data_type": "lineup"}
    },
}


# ==================== 阵容/伤病类 ====================

BIFEN188_MAP = {
    "get_predicted_lineups": {
        "home_lineup": "home_lineup",
        "away_lineup": "away_lineup",
        "home_formation": "home_formation",
        "away_formation": "away_formation",
        "match_url": "match_url",
        "source": "source",
        "_computed": {
            "match_key": lambda r: r.get("match_url", "")
        },
        "_meta": {"data_type": "lineup"}
    },
}

PREMIERLEAGUE_MAP = {
    "get_injuries": {
        "player": "player_name",
        "team": "team",
        "status": "status",
        "reason": "reason",
        "league": "league",
        "source": "source",
        "_computed": {},
        "_meta": {"data_type": "injury"}
    },
    "get_fixtures": {
        "home_team": "home_team",
        "away_team": "away_team",
        "date": "date",
        "league": "league",
        "season": "season",
        "source": "source",
        "_computed": {
            "match_key": lambda r: make_match_key(
                r.get("date", ""), r.get("home_team", ""), r.get("away_team", ""))
        },
        "_meta": {"data_type": "match"}
    },
}


# ==================== 新闻/视频类 ====================

DONGQIUDI_MAP = {
    "get_news": {
        "title": "title",
        "url": "url",
        "date": "date",
        "source": "source",
        "_computed": {},
        "_meta": {"data_type": "news"}
    },
}

HUPU_MAP = {
    "get_news": {
        "title": "title",
        "url": "url",
        "date": "date",
        "source": "source",
        "_computed": {},
        "_meta": {"data_type": "news"}
    },
}

ZHIRBO8_MAP = {
    "get_news": {
        "title": "title",
        "url": "url",
        "date": "date",
        "source": "source",
        "_computed": {},
        "_meta": {"data_type": "news"}
    },
}

SCOREBAT_MAP = {
    "get_highlights": {
        "title": "title",
        "url": "url",
        "video_url": "video_url",
        "home_team": "home_team",
        "away_team": "away_team",
        "source": "source",
        "_computed": {
            "match_key": lambda r: make_match_key(
                "", r.get("home_team", ""), r.get("away_team", ""))
        },
        "_meta": {"data_type": "news"}
    },
}


# ==================== 天气类 ====================

WEATHER_MAP = {
    "get_match_weather": {
        "city": "city",
        "city_input": "city_input",
        "home_team": "home_team",
        "date": "date",
        "temp_c": "temp_c",
        "humidity": "humidity",
        "wind": "wind",
        "precipitation": "precipitation",
        "description": "description",
        "source": "source",
        "_computed": {
            "match_key": lambda r: make_match_key(
                r.get("date", ""), r.get("home_team", ""), "")
        },
        "_meta": {"data_type": "weather"}
    },
}

OPENWEATHERMAP_MAP = {
    "get_current_weather": {
        "city": "city",
        "city_input": "city_input",
        "country": "country",
        "temp_c": "temp_c",
        "humidity": "humidity",
        "description": "description",
        "source": "source",
        "_computed": {},
        "_meta": {"data_type": "weather"}
    },
    "get_forecast": {
        "city": "city",
        "city_input": "city_input",
        "datetime": "datetime",
        "temp_c": "temp_c",
        "humidity": "humidity",
        "source": "source",
        "_computed": {},
        "_meta": {"data_type": "weather"}
    },
    "get_air_quality": {
        "lat": "lat",
        "lon": "lon",
        "aqi": "aqi",
        "pm2_5": "pm2_5",
        "pm10": "pm10",
        "source": "source",
        "_computed": {},
        "_meta": {"data_type": "weather"}
    },
}


# ==================== 积分榜/球员/身价类 ====================

TRANSFERMARKT_MAP = {
    "get_squad": {
        "team_url": "team_url",
        "data": "data",
        "source": "source",
        "_computed": {},
        "_meta": {"data_type": "player"}
    },
    "get_player_value": {
        "player_name": "player_name",
        "market_value": "market_value",
        "club": "team",
        "source": "source",
        "_computed": {},
        "_meta": {"data_type": "player"}
    },
    "get_league_valuations": {
        "data": "data",
        "source": "source",
        "_computed": {},
        "_meta": {"data_type": "player"}
    },
}

FOOTBALL_DATA_UK_MAP = {
    "batch_fetch_to_csv": {
        "league": "league",
        "source": "source",
        "_computed": {},
        "_meta": {"data_type": "match"}
    },
}

# ==================== World Cup 历史数据 ====================

WORLD_CUP_MAP = {
    "get_matches": {
        "match_key": "match_key",
        "date": "date",
        "home_team": "home_team",
        "away_team": "away_team",
        "home_score": "home_score",
        "away_score": "away_score",
        "home_xg": "home_xg",
        "away_xg": "away_xg",
        "home_shots": "home_shots",
        "away_shots": "away_shots",
        "league": "league",
        "source": "source",
        "_computed": {},
        "_meta": {"data_type": "match"}
    },
    "get_odds": {
        "match_key": "match_key",
        "date": "date",
        "home_team": "home_team",
        "away_team": "away_team",
        "odds_home": "home_win",
        "odds_draw": "draw",
        "odds_away": "away_win",
        "odds_source": "bookmaker",
        "source": "source",
        "_computed": {},
        "_meta": {"data_type": "odds"}
    },
    "get_lineups": {
        "match_key": "match_key",
        "date": "date",
        "home_team": "home_team",
        "away_team": "away_team",
        "home_formation": "home_formation",
        "away_formation": "away_formation",
        "home_lineup": "home_lineup",
        "away_lineup": "away_lineup",
        "source": "source",
        "_computed": {},
        "_meta": {"data_type": "lineup"}
    },
    "get_statistics": {
        "match_key": "match_key",
        "date": "date",
        "home_team": "home_team",
        "away_team": "away_team",
        "statistics": "statistics",
        "source": "source",
        "_computed": {},
        "_meta": {"data_type": "match"}
    },
    "get_full_data": {
        "match_key": "match_key",
        "date": "date",
        "home_team": "home_team",
        "away_team": "away_team",
        "home_score": "home_score",
        "away_score": "away_score",
        "home_xg": "home_xg",
        "away_xg": "away_xg",
        "odds_home": "home_win",
        "odds_draw": "draw",
        "odds_away": "away_win",
        "home_formation": "home_formation",
        "away_formation": "away_formation",
        "home_lineup": "home_lineup",
        "away_lineup": "away_lineup",
        "statistics": "statistics",
        "league": "league",
        "source": "source",
        "_computed": {},
        "_meta": {"data_type": "match"}
    },
}


# ==================== 总映射表 ====================

FIELD_MAPS = {
    "apifootball": APIFOOTBALL_MAP,
    "football_data_org": FOOTBALL_DATA_ORG_MAP,
    "espn": ESPN_MAP,
    "soccerway": SOCCERWAY_MAP,
    "scores365": SCORES365_MAP,
    "flashlive": FLASHLIVE_MAP,
    "sofascore": SOFASCORE_MAP,
    "thesportsdb": THESPORTSDB_MAP,
    "openligadb": OPENLIGADB_MAP,
    "api_sports": API_SPORTS_MAP,
    "fbref": FBREF_MAP,
    "okooo": OKOOO_MAP,
    "the_odds_api": THE_ODDS_API_MAP,
    "odds_api": ODDS_API_MAP,
    "sporttery": SPORTTERY_MAP,
    "understat": UNDERSTAT_MAP,
    "statsbomb": STATSBOMB_MAP,
    "sportmonks": SPORTMONKS_MAP,
    "bifen188": BIFEN188_MAP,
    "premierleague": PREMIERLEAGUE_MAP,
    "dongqiudi": DONGQIUDI_MAP,
    "hupu": HUPU_MAP,
    "zhibo8": ZHIRBO8_MAP,
    "scorebat": SCOREBAT_MAP,
    "weather": WEATHER_MAP,
    "openweathermap": OPENWEATHERMAP_MAP,
    "transfermarkt": TRANSFERMARKT_MAP,
    "football_data_uk": FOOTBALL_DATA_UK_MAP,
    "world_cup": WORLD_CUP_MAP,
    "fifa_ranking": {
        "get_rankings": {
            "rank": "position",
            "team": "team",
            "points": "points",
            "confederation": "confederation",
            "source": "source",
            "_computed": {},
            "_meta": {"data_type": "standing"}
        },
        "get_team_ranking": {
            "rank": "position",
            "team": "team",
            "points": "points",
            "confederation": "confederation",
            "source": "source",
            "_computed": {},
            "_meta": {"data_type": "standing"}
        },
        "get_ranking_diff": {
            "home_rank": "home_rank",
            "away_rank": "away_rank",
            "rank_diff": "rank_diff",
            "home_points": "home_points",
            "away_points": "away_points",
            "points_diff": "points_diff",
            "home_confederation": "home_confederation",
            "away_confederation": "away_confederation",
            "confederation_strength_diff": "confederation_strength_diff",
            "source": "source",
            "_computed": {},
            "_meta": {"data_type": "prediction"}
        },
    },
}


def get_field_map(fetcher_name: str, func_name: str) -> dict:
    """获取指定fetcher+函数的字段映射表"""
    fetcher_map = FIELD_MAPS.get(fetcher_name)
    if not fetcher_map:
        return {}
    return fetcher_map.get(func_name, {})


def get_data_type(fetcher_name: str, func_name: str) -> str:
    """获取数据类型 (match/odds/prediction/lineup/injury/news/weather/standing/player)"""
    fmap = get_field_map(fetcher_name, func_name)
    meta = fmap.get("_meta", {})
    return meta.get("data_type", "unknown")


def list_supported_functions() -> dict:
    """列出所有已支持映射的fetcher+函数"""
    result = {}
    for fetcher, funcs in FIELD_MAPS.items():
        result[fetcher] = list(funcs.keys())
    return result