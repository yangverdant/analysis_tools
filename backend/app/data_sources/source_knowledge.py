"""
数据源能力知识库 - 完整记录每个数据源的能力、字段、格式

这个文件是数据采集层的核心知识库，包含：
1. 每个数据源支持的联赛
2. 每个数据源提供的字段
3. 数据返回格式示例
4. 字段到数据库的映射关系
5. 数据源之间的互补关系
"""

from dataclasses import dataclass, field
from typing import Dict, List, Set, Optional, Any
from enum import Enum


# ==================== 联赛定义 ====================

LEAGUES = {
    # 五大联赛
    "premier_league": {
        "name_en": "Premier League",
        "name_cn": "英超",
        "country": "England",
        "tier": 1,
        "sm_id": 8,
        "fd_code": "PL",
        "tsdb_id": 4328,
    },
    "la_liga": {
        "name_en": "La Liga",
        "name_cn": "西甲",
        "country": "Spain",
        "tier": 1,
        "sm_id": 564,
        "fd_code": "PD",
        "tsdb_id": 4335,
    },
    "bundesliga": {
        "name_en": "Bundesliga",
        "name_cn": "德甲",
        "country": "Germany",
        "tier": 1,
        "sm_id": 35,
        "fd_code": "BL1",
        "tsdb_id": 4331,
    },
    "serie_a": {
        "name_en": "Serie A",
        "name_cn": "意甲",
        "country": "Italy",
        "tier": 1,
        "sm_id": 384,
        "fd_code": "SA",
        "tsdb_id": 4332,
    },
    "ligue_1": {
        "name_en": "Ligue 1",
        "name_cn": "法甲",
        "country": "France",
        "tier": 1,
        "sm_id": 301,
        "fd_code": "FL1",
        "tsdb_id": 4334,
    },
    # 二级联赛
    "championship": {
        "name_en": "Championship",
        "name_cn": "英冠",
        "country": "England",
        "tier": 2,
        "sm_id": 48,
        "fd_code": "ELC",
        "tsdb_id": 4329,
    },
    "bundesliga_2": {
        "name_en": "2. Bundesliga",
        "name_cn": "德乙",
        "country": "Germany",
        "tier": 2,
        "sm_id": 36,
        "fd_code": "BL2",
        "tsdb_id": 4330,
    },
    "segunda_division": {
        "name_en": "Segunda División",
        "name_cn": "西乙",
        "country": "Spain",
        "tier": 2,
        "sm_id": 565,
        "fd_code": "SD",
        "tsdb_id": 4336,
    },
    "serie_b": {
        "name_en": "Serie B",
        "name_cn": "意乙",
        "country": "Italy",
        "tier": 2,
        "sm_id": 385,
        "fd_code": "SB",
        "tsdb_id": 4333,
    },
    "ligue_2": {
        "name_en": "Ligue 2",
        "name_cn": "法乙",
        "country": "France",
        "tier": 2,
        "sm_id": 302,
        "fd_code": "FL2",
        "tsdb_id": 4337,
    },
    # 欧战
    "champions_league": {
        "name_en": "Champions League",
        "name_cn": "欧冠",
        "country": "Europe",
        "tier": 1,
        "sm_id": 7,
        "fd_code": "CL",
        "tsdb_id": 4480,
    },
    "europa_league": {
        "name_en": "Europa League",
        "name_cn": "欧联",
        "country": "Europe",
        "tier": 1,
        "sm_id": 679,
        "fd_code": "EL",
        "tsdb_id": 4481,
    },
    "conference_league": {
        "name_en": "Conference League",
        "name_cn": "欧协联",
        "country": "Europe",
        "tier": 1,
        "sm_id": 832,
        "fd_code": "ECL",
        "tsdb_id": 4482,
    },
    # 其他联赛
    "eredivisie": {
        "name_en": "Eredivisie",
        "name_cn": "荷甲",
        "country": "Netherlands",
        "tier": 1,
        "sm_id": 64,
        "fd_code": "DED",
        "tsdb_id": 4338,
    },
    "primeira_liga": {
        "name_en": "Primeira Liga",
        "name_cn": "葡超",
        "country": "Portugal",
        "tier": 1,
        "sm_id": 2,
        "fd_code": "PPL",
        "tsdb_id": 4340,
    },
    # 国际赛事
    "world_cup": {
        "name_en": "World Cup",
        "name_cn": "世界杯",
        "country": "International",
        "tier": 1,
        "sm_id": 1,
        "fd_code": "WC",
        "tsdb_id": 4643,
    },
    "euro": {
        "name_en": "European Championship",
        "name_cn": "欧洲杯",
        "country": "Europe",
        "tier": 1,
        "sm_id": 10,
        "fd_code": "EC",
        "tsdb_id": 4496,
    },
    # 亚洲联赛
    "j1_league": {
        "name_en": "J1 League",
        "name_cn": "J联赛",
        "country": "Japan",
        "tier": 1,
        "sm_id": 25,
        "fd_code": None,
        "tsdb_id": 4380,
    },
    "k1_league": {
        "name_en": "K League 1",
        "name_cn": "K联赛",
        "country": "South Korea",
        "tier": 1,
        "sm_id": 313,
        "fd_code": None,
        "tsdb_id": 4381,
    },
    # 美洲联赛
    "mls": {
        "name_en": "Major League Soccer",
        "name_cn": "美职联",
        "country": "USA",
        "tier": 1,
        "sm_id": 22,
        "fd_code": "MLS",
        "tsdb_id": 4346,
    },
    "brasileirao": {
        "name_en": "Brasileirão",
        "name_cn": "巴甲",
        "country": "Brazil",
        "tier": 1,
        "sm_id": 24,
        "fd_code": "BSA",
        "tsdb_id": 4343,
    },
}


# ==================== 数据源能力定义 ====================

@dataclass
class DataSourceCapability:
    """数据源能力定义"""
    name: str                                    # 数据源名称
    source_type: str                             # api/scraper/local
    description: str = ""                         # 描述

    # 支持的联赛 (空=全部支持)
    supported_leagues: Set[str] = field(default_factory=set)
    unsupported_leagues: Set[str] = field(default_factory=set)

    # 支持的数据类别
    categories: Set[str] = field(default_factory=set)

    # 比赛数据字段
    match_fields: Dict[str, Dict] = field(default_factory=dict)

    # 球队数据字段
    team_fields: Dict[str, Dict] = field(default_factory=dict)

    # 球员数据字段
    player_fields: Dict[str, Dict] = field(default_factory=dict)

    # 积分榜字段
    standings_fields: Dict[str, Dict] = field(default_factory=dict)

    # 特殊能力
    special_features: Set[str] = field(default_factory=set)

    # 限制
    rate_limit: int = 60
    request_interval: float = 1.0
    priority: int = 10

    # 返回格式示例
    sample_response: Dict = field(default_factory=dict)


# ==================== Sportmonks API ====================

SPORTMONKS_CAPABILITY = DataSourceCapability(
    name="sportmonks",
    source_type="api",
    description="足球数据API，覆盖全球联赛/杯赛，数据最全",

    supported_leagues=set(LEAGUES.keys()),  # 支持所有联赛

    categories={
        "livescores",      # 实时比分
        "fixtures",        # 赛程
        "standings",       # 积分榜
        "matches",         # 历史比赛
        "teams",           # 球队
        "players",         # 球员
        "squad",           # 阵容
        "events",          # 比赛事件
        "statistics",      # 统计数据
        "xg",              # 预期进球
        "odds",            # 赔率
        "predictions",     # AI预测
        "lineups",         # 阵容
        "head2head",       # 交锋
        "referee",         # 裁判
        "sidelined",       # 伤病
        "news",            # 新闻
    },

    match_fields={
        # 基础信息
        "match_id": {"source": "id", "type": "int", "required": True},
        "league_id": {"source": "league_id", "type": "int"},
        "season_id": {"source": "season_id", "type": "int"},
        "match_date": {"source": "starting_at", "type": "datetime", "transform": "extract_date"},
        "match_time": {"source": "starting_at", "type": "datetime", "transform": "extract_time"},
        "round_num": {"source": "round_name", "type": "str", "transform": "parse_round"},
        "venue": {"source": "venue.name", "type": "str"},
        "venue_city": {"source": "venue.city", "type": "str"},
        "referee": {"source": "referee.common_name", "type": "str"},
        "attendance": {"source": "attendance", "type": "int"},

        # 球队
        "home_team_id": {"source": "participants[location=home].id", "type": "int"},
        "away_team_id": {"source": "participants[location=away].id", "type": "int"},

        # 比分
        "home_goals": {"source": "scores.ft.home_score", "type": "int"},
        "away_goals": {"source": "scores.ft.away_score", "type": "int"},
        "home_goals_ht": {"source": "scores.ht.home_score", "type": "int"},
        "away_goals_ht": {"source": "scores.ht.away_score", "type": "int"},

        # 统计数据
        "home_shots": {"source": "statistics.shots_total.home", "type": "int"},
        "away_shots": {"source": "statistics.shots_total.away", "type": "int"},
        "home_shots_target": {"source": "statistics.shots_on_target.home", "type": "int"},
        "away_shots_target": {"source": "statistics.shots_on_target.away", "type": "int"},
        "home_corners": {"source": "statistics.corners.home", "type": "int"},
        "away_corners": {"source": "statistics.corners.away", "type": "int"},
        "home_fouls": {"source": "statistics.fouls.home", "type": "int"},
        "away_fouls": {"source": "statistics.fouls.away", "type": "int"},
        "home_yellow": {"source": "statistics.yellow_cards.home", "type": "int"},
        "away_yellow": {"source": "statistics.yellow_cards.away", "type": "int"},
        "home_red": {"source": "statistics.red_cards.home", "type": "int"},
        "away_red": {"source": "statistics.red_cards.away", "type": "int"},
        "home_possession": {"source": "statistics.ball_possession.home", "type": "float"},
        "away_possession": {"source": "statistics.ball_possession.away", "type": "float"},

        # xG数据
        "home_xg": {"source": "xg.home", "type": "float"},
        "away_xg": {"source": "xg.away", "type": "float"},

        # 状态
        "status": {"source": "state_id", "type": "int", "transform": "match_status"},
    },

    team_fields={
        "team_id": {"source": "id", "type": "int", "required": True},
        "name_en": {"source": "name", "type": "str", "required": True},
        "short_name": {"source": "short_code", "type": "str"},
        "tla": {"source": "short_code", "type": "str"},
        "country": {"source": "country.name", "type": "str"},
        "stadium": {"source": "venue.name", "type": "str"},
        "stadium_capacity": {"source": "venue.capacity", "type": "int"},
        "founded_year": {"source": "founded", "type": "int"},
        "logo_url": {"source": "image_path", "type": "str"},
    },

    player_fields={
        "player_id": {"source": "id", "type": "int", "required": True},
        "name_en": {"source": "name", "type": "str", "required": True},
        "full_name": {"source": "display_name", "type": "str"},
        "nationality": {"source": "country.name", "type": "str"},
        "birth_date": {"source": "date_of_birth", "type": "date"},
        "height": {"source": "height", "type": "int"},
        "weight": {"source": "weight", "type": "int"},
        "position_main": {"source": "position.name", "type": "str"},
        "logo_url": {"source": "image_path", "type": "str"},
    },

    standings_fields={
        "position": {"source": "position", "type": "int", "required": True},
        "team_id": {"source": "participant_id", "type": "int", "required": True},
        "played": {"source": "details.played", "type": "int"},
        "won": {"source": "details.won", "type": "int"},
        "drawn": {"source": "details.draw", "type": "int"},
        "lost": {"source": "details.lost", "type": "int"},
        "goals_for": {"source": "details.goals_scored", "type": "int"},
        "goals_against": {"source": "details.goals_against", "type": "int"},
        "goal_diff": {"source": "details.goal_difference", "type": "int"},
        "points": {"source": "details.points", "type": "int"},
        "form": {"source": "form", "type": "str"},
    },

    special_features={
        "xg_data",           # xG数据
        "odds_data",         # 赔率数据
        "predictions",       # AI预测
        "pressure_index",    # 压力指数
        "sidelined",         # 伤病信息
        "detailed_stats",    # 详细统计
        "live_standings",    # 实时积分榜
    },

    rate_limit=30,
    request_interval=2.0,
    priority=1,

    sample_response={
        "fixture": {
            "id": 12345678,
            "league_id": 8,
            "season_id": 25659,
            "starting_at": "2025-05-21 15:00:00",
            "venue": {"name": "Emirates Stadium", "city": "London"},
            "participants": [
                {"id": 42, "name": "Arsenal", "meta": {"location": "home"}},
                {"id": 33, "name": "Newcastle", "meta": {"location": "away"}}
            ],
            "scores": {
                "ft": {"home_score": 2, "away_score": 1},
                "ht": {"home_score": 1, "away_score": 0}
            }
        }
    }
)


# ==================== football-data.org API ====================

FOOTBALL_DATA_ORG_CAPABILITY = DataSourceCapability(
    name="football_data_org",
    source_type="api",
    description="免费足球数据API，覆盖12个T1联赛",

    supported_leagues={
        "premier_league", "la_liga", "bundesliga", "serie_a", "ligue_1",
        "eredivisie", "primeira_liga", "champions_league", "europa_league",
        "championship", "world_cup", "euro"
    },

    categories={
        "matches",
        "standings",
        "scorers",
        "squads",
        "teams",
        "competitions",
    },

    match_fields={
        "match_id": {"source": "id", "type": "int", "required": True},
        "league_id": {"source": "competition.code", "type": "str", "transform": "league_id_fd"},
        "match_date": {"source": "utcDate", "type": "datetime", "transform": "extract_date"},
        "match_time": {"source": "utcDate", "type": "datetime", "transform": "extract_time"},
        "round_num": {"source": "matchday", "type": "int"},
        "stage_type": {"source": "stage", "type": "str"},
        "group_name": {"source": "group", "type": "str"},
        "home_team_id": {"source": "homeTeam.id", "type": "int"},
        "away_team_id": {"source": "awayTeam.id", "type": "int"},
        "home_goals": {"source": "score.fullTime.home", "type": "int"},
        "away_goals": {"source": "score.fullTime.away", "type": "int"},
        "home_goals_ht": {"source": "score.halfTime.home", "type": "int"},
        "away_goals_ht": {"source": "score.halfTime.away", "type": "int"},
        "home_goals_et": {"source": "score.extraTime.home", "type": "int"},
        "away_goals_et": {"source": "score.extraTime.away", "type": "int"},
        "home_penalties": {"source": "score.penalties.home", "type": "int"},
        "away_penalties": {"source": "score.penalties.away", "type": "int"},
        "status": {"source": "status", "type": "str"},
        "referee": {"source": "referees[0].name", "type": "str"},
    },

    team_fields={
        "team_id": {"source": "id", "type": "int", "required": True},
        "name_en": {"source": "name", "type": "str", "required": True},
        "short_name": {"source": "shortName", "type": "str"},
        "tla": {"source": "tla", "type": "str"},
        "country": {"source": "area.name", "type": "str"},
        "stadium": {"source": "venue", "type": "str"},
        "founded_year": {"source": "founded", "type": "int"},
        "logo_url": {"source": "crest", "type": "str"},
    },

    player_fields={
        "player_id": {"source": "id", "type": "int", "required": True},
        "name_en": {"source": "name", "type": "str", "required": True},
        "nationality": {"source": "nationality", "type": "str"},
        "birth_date": {"source": "dateOfBirth", "type": "date"},
        "position_main": {"source": "section", "type": "str"},
    },

    standings_fields={
        "position": {"source": "position", "type": "int", "required": True},
        "team_id": {"source": "team.id", "type": "int", "required": True},
        "played": {"source": "playedGames", "type": "int"},
        "won": {"source": "won", "type": "int"},
        "drawn": {"source": "draw", "type": "int"},
        "lost": {"source": "lost", "type": "int"},
        "goals_for": {"source": "goalsFor", "type": "int"},
        "goals_against": {"source": "goalsAgainst", "type": "int"},
        "goal_diff": {"source": "goalDifference", "type": "int"},
        "points": {"source": "points", "type": "int"},
        "form": {"source": "form", "type": "str"},
    },

    special_features={
        "free_access",
        "squad_data",
        "scorer_data",
    },

    rate_limit=10,
    request_interval=7.0,
    priority=2,

    sample_response={
        "match": {
            "id": 123456,
            "utcDate": "2025-05-21T15:00:00Z",
            "status": "FINISHED",
            "matchday": 38,
            "competition": {"code": "PL"},
            "homeTeam": {"id": 57, "name": "Arsenal"},
            "awayTeam": {"id": 64, "name": "Newcastle"},
            "score": {
                "fullTime": {"home": 2, "away": 1},
                "halfTime": {"home": 1, "away": 0}
            }
        }
    }
)


# ==================== FBref Scraper ====================

FBREF_CAPABILITY = DataSourceCapability(
    name="fbref",
    source_type="scraper",
    description="FBref网站爬虫，获取免费足球数据，含高级统计",

    supported_leagues={
        "premier_league", "la_liga", "bundesliga", "serie_a", "ligue_1",
        "j1_league", "k1_league", "mls", "brasileirao",
        "eredivisie", "primeira_liga", "champions_league", "europa_league"
    },

    categories={
        "matches",
        "standings",
        "player_stats",
        "team_stats",
        "advanced_stats",
        "xg",
    },

    match_fields={
        "match_date": {"source": "Date", "type": "date"},
        "match_time": {"source": "Time", "type": "time"},
        "home_team_id": {"source": "HomeTeam", "type": "str", "transform": "team_name_to_id"},
        "away_team_id": {"source": "AwayTeam", "type": "str", "transform": "team_name_to_id"},
        "home_goals": {"source": "FTHG", "type": "int"},
        "away_goals": {"source": "FTAG", "type": "int"},
        "home_goals_ht": {"source": "HTHG", "type": "int"},
        "away_goals_ht": {"source": "HTAG", "type": "int"},
        "result": {"source": "FTR", "type": "str"},
        "home_shots": {"source": "HS", "type": "int"},
        "away_shots": {"source": "AS", "type": "int"},
        "home_shots_target": {"source": "HST", "type": "int"},
        "away_shots_target": {"source": "AST", "type": "int"},
        "home_corners": {"source": "HC", "type": "int"},
        "away_corners": {"source": "AC", "type": "int"},
        "home_fouls": {"source": "HF", "type": "int"},
        "away_fouls": {"source": "AF", "type": "int"},
        "home_yellow": {"source": "HY", "type": "int"},
        "away_yellow": {"source": "AY", "type": "int"},
        "home_red": {"source": "HR", "type": "int"},
        "away_red": {"source": "AR", "type": "int"},
        "referee": {"source": "Referee", "type": "str"},
        "attendance": {"source": "Attendance", "type": "int"},
        "home_xg": {"source": "Home xG", "type": "float"},
        "away_xg": {"source": "Away xG", "type": "float"},
        "odds_home": {"source": "B365H", "type": "float"},
        "odds_draw": {"source": "B365D", "type": "float"},
        "odds_away": {"source": "B365A", "type": "float"},
    },

    special_features={
        "xg_data",
        "advanced_player_stats",
        "detailed_team_stats",
        "free_access",
        "historical_data",
    },

    rate_limit=20,
    request_interval=3.0,
    priority=7,
)


# ==================== TheSportsDB API ====================

THESPORTSDB_CAPABILITY = DataSourceCapability(
    name="thesportsdb",
    source_type="api",
    description="免费体育数据API，无需Key，覆盖多运动项目",

    supported_leagues=set(LEAGUES.keys()),  # 支持所有联赛

    categories={
        "livescores",
        "events",
        "leagues",
        "teams",
        "players",
    },

    match_fields={
        "match_id": {"source": "idEvent", "type": "str", "required": True},
        "league_id": {"source": "idLeague", "type": "int"},
        "match_date": {"source": "dateEvent", "type": "date"},
        "match_time": {"source": "strTime", "type": "time"},
        "round_num": {"source": "intRound", "type": "int"},
        "venue": {"source": "strVenue", "type": "str"},
        "home_team_id": {"source": "idHomeTeam", "type": "int"},
        "away_team_id": {"source": "idAwayTeam", "type": "int"},
        "home_goals": {"source": "intHomeScore", "type": "int"},
        "away_goals": {"source": "intAwayScore", "type": "int"},
        "status": {"source": "strStatus", "type": "str"},
    },

    team_fields={
        "team_id": {"source": "idTeam", "type": "int", "required": True},
        "name_en": {"source": "strTeam", "type": "str", "required": True},
        "short_name": {"source": "strTeamShort", "type": "str"},
        "country": {"source": "strCountry", "type": "str"},
        "stadium": {"source": "strStadium", "type": "str"},
        "stadium_capacity": {"source": "intStadiumCapacity", "type": "int"},
        "logo_url": {"source": "strTeamBadge", "type": "str"},
    },

    special_features={
        "free_access",
        "no_auth_required",
        "multi_sport",
    },

    rate_limit=60,
    request_interval=1.0,
    priority=4,
)


# ==================== ScoreBat API ====================

SCOREBAT_CAPABILITY = DataSourceCapability(
    name="scorebat",
    source_type="api",
    description="免费足球视频API，可从标题解析比分",

    supported_leagues=set(LEAGUES.keys()),

    categories={
        "livescores",
        "highlights",
    },

    match_fields={
        "match_date": {"source": "date", "type": "datetime"},
        "league_id": {"source": "competition.id", "type": "int"},
        "home_team_id": {"source": "title", "type": "str", "transform": "parse_home_team"},
        "away_team_id": {"source": "title", "type": "str", "transform": "parse_away_team"},
        "home_goals": {"source": "title", "type": "str", "transform": "parse_home_score"},
        "away_goals": {"source": "title", "type": "str", "transform": "parse_away_score"},
    },

    special_features={
        "free_access",
        "video_highlights",
    },

    rate_limit=60,
    request_interval=1.0,
    priority=5,
)


# ==================== OpenLigaDB API ====================

OPENLIGADB_CAPABILITY = DataSourceCapability(
    name="openligadb",
    source_type="api",
    description="德国足球数据API，专注德甲/德乙",

    supported_leagues={
        "bundesliga",
        "bundesliga_2",
    },

    categories={
        "matches",
        "standings",
        "teams",
    },

    match_fields={
        "match_id": {"source": "matchID", "type": "int", "required": True},
        "match_date": {"source": "matchDateTime", "type": "datetime"},
        "round_num": {"source": "group.groupOrderID", "type": "int"},
        "home_team_id": {"source": "team1.teamId", "type": "int"},
        "away_team_id": {"source": "team2.teamId", "type": "int"},
        "home_goals": {"source": "matchResults[0].pointsTeam1", "type": "int"},
        "away_goals": {"source": "matchResults[0].pointsTeam2", "type": "int"},
    },

    special_features={
        "free_access",
        "german_focus",
        "real_time",
    },

    rate_limit=60,
    request_interval=1.0,
    priority=6,
)


# ==================== StatsBomb (本地数据) ====================

STATSBOMB_CAPABILITY = DataSourceCapability(
    name="statsbomb",
    source_type="local",
    description="StatsBomb开源数据，含详细xG和事件数据",

    supported_leagues={
        "premier_league", "la_liga", "bundesliga", "serie_a", "ligue_1",
        "champions_league", "world_cup", "euro"
    },

    categories={
        "matches",
        "events",
        "xg",
        "player_stats",
        "advanced_stats",
    },

    match_fields={
        "match_id": {"source": "match_id", "type": "str", "required": True},
        "match_date": {"source": "match_date", "type": "date"},
        "home_team_id": {"source": "home_team.home_team_id", "type": "str"},
        "away_team_id": {"source": "away_team.away_team_id", "type": "str"},
        "home_goals": {"source": "home_score", "type": "int"},
        "away_goals": {"source": "away_score", "type": "int"},
        "home_xg": {"source": "home_xg", "type": "float"},
        "away_xg": {"source": "away_xg", "type": "float"},
    },

    special_features={
        "detailed_events",
        "xg_data",
        "freeze_frames",
        "360_data",
        "free_access",
    },

    priority=3,
)


# ==================== 数据源注册管理 ====================

class DataSourceKnowledgeBase:
    """数据源知识库"""

    def __init__(self):
        self.capabilities: Dict[str, DataSourceCapability] = {}
        self._register_all_sources()

    def _register_all_sources(self):
        """注册所有数据源"""
        self.register(SPORTMONKS_CAPABILITY)
        self.register(FOOTBALL_DATA_ORG_CAPABILITY)
        self.register(FBREF_CAPABILITY)
        self.register(THESPORTSDB_CAPABILITY)
        self.register(SCOREBAT_CAPABILITY)
        self.register(OPENLIGADB_CAPABILITY)
        self.register(STATSBOMB_CAPABILITY)

    def register(self, capability: DataSourceCapability):
        """注册数据源"""
        self.capabilities[capability.name] = capability

    def get_source(self, name: str) -> Optional[DataSourceCapability]:
        """获取数据源能力"""
        return self.capabilities.get(name)

    def get_sources_for_league(self, league: str) -> List[DataSourceCapability]:
        """获取支持某联赛的所有数据源"""
        sources = []
        for cap in self.capabilities.values():
            # 空集合表示支持所有联赛
            if not cap.supported_leagues or league in cap.supported_leagues:
                if league not in cap.unsupported_leagues:
                    sources.append(cap)
        return sorted(sources, key=lambda x: x.priority)

    def get_sources_for_category(self, category: str) -> List[DataSourceCapability]:
        """获取支持某类数据的所有数据源"""
        sources = [c for c in self.capabilities.values() if category in c.categories]
        return sorted(sources, key=lambda x: x.priority)

    def get_sources_for_field(self, table: str, field: str) -> List[DataSourceCapability]:
        """获取能提供某字段的数据源"""
        sources = []
        for cap in self.capabilities.values():
            fields_map = getattr(cap, f"{table}_fields", {})
            if field in fields_map:
                sources.append(cap)
        return sorted(sources, key=lambda x: x.priority)

    def get_field_coverage(self, table: str, fields: Set[str]) -> Dict[str, Dict]:
        """获取字段覆盖报告"""
        report = {}
        for name, cap in self.capabilities.items():
            fields_map = getattr(cap, f"{table}_fields", {})
            available = set(fields_map.keys())
            covered = fields & available
            missing = fields - available
            report[name] = {
                "coverage": len(covered) / len(fields) if fields else 0,
                "covered_fields": list(covered),
                "missing_fields": list(missing),
                "priority": cap.priority,
            }
        return report

    def find_best_sources(self, table: str, fields: Set[str], league: str = None) -> List[DataSourceCapability]:
        """找到最佳数据源组合"""
        # 先按联赛过滤
        if league:
            sources = self.get_sources_for_league(league)
        else:
            sources = list(self.capabilities.values())

        # 按字段覆盖率排序
        scored_sources = []
        remaining_fields = set(fields)

        for source in sources:
            fields_map = getattr(source, f"{table}_fields", {})
            available = set(fields_map.keys())
            covered = remaining_fields & available

            if covered:
                scored_sources.append((source, covered))

        # 贪心选择：每次选择覆盖最多剩余字段的源
        result = []
        while remaining_fields and scored_sources:
            # 重新计算覆盖
            scored_sources = [
                (s, getattr(s, f"{table}_fields", {}).keys() & remaining_fields)
                for s, _ in scored_sources
            ]
            # 按覆盖数量排序
            scored_sources.sort(key=lambda x: (-len(x[1]), x[0].priority))

            if scored_sources and scored_sources[0][1]:
                best, covered = scored_sources[0]
                result.append(best)
                remaining_fields -= covered
                scored_sources = scored_sources[1:]

        return result

    def get_all_match_fields(self) -> Set[str]:
        """获取所有数据源能提供的比赛字段"""
        all_fields = set()
        for cap in self.capabilities.values():
            all_fields.update(cap.match_fields.keys())
        return all_fields

    def get_league_info(self, league_code: str) -> Optional[Dict]:
        """获取联赛信息"""
        return LEAGUES.get(league_code)


# 全局实例
knowledge_base = DataSourceKnowledgeBase()
