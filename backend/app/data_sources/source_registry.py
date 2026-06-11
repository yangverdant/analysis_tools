"""
数据源注册表 - 统一管理所有数据源的字段映射和能力
支持:
1. 数据源注册 - 记录每个数据源包含的字段
2. 智能匹配 - 根据需要的字段推荐数据源
3. 字段映射 - 数据源字段到数据库字段的转换
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Any, Callable
from enum import Enum
import json
from pathlib import Path


class SourceType(str, Enum):
    """数据源类型"""
    API = "api"           # REST API
    SCRAPER = "scraper"   # 网页爬虫
    LOCAL = "local"       # 本地文件
    DATABASE = "database" # 数据库


class FieldType(str, Enum):
    """字段类型"""
    STRING = "string"
    INTEGER = "integer"
    FLOAT = "float"
    DATE = "date"
    TIME = "time"
    DATETIME = "datetime"
    BOOLEAN = "boolean"


@dataclass
class FieldMapping:
    """字段映射配置"""
    db_field: str                    # 数据库字段名
    db_type: FieldType               # 数据库字段类型
    source_field: str                # 数据源字段名 (可以是路径如 "score.home_score")
    source_type: FieldType           # 数据源字段类型
    transform: Optional[str] = None  # 转换函数名
    required: bool = False           # 是否必需
    default: Any = None              # 默认值
    description: str = ""            # 字段描述


@dataclass
class DataSourceRegistry:
    """数据源注册信息"""
    name: str                              # 数据源名称
    source_type: SourceType                # 数据源类型
    description: str = ""                  # 描述
    base_url: str = ""                     # API基础URL
    auth_type: str = "none"                # 认证类型: none, header, query_param, bearer
    api_key: str = ""                      # API密钥
    rate_limit: int = 60                   # 每分钟请求限制
    request_interval: float = 1.0          # 请求间隔(秒)
    priority: int = 10                     # 优先级 (越小越优先)
    enabled: bool = True                   # 是否启用

    # 支持的数据类别
    categories: Set[str] = field(default_factory=set)

    # 支持的联赛ID映射
    league_ids: Dict[str, int] = field(default_factory=dict)

    # 字段映射配置
    field_mappings: Dict[str, List[FieldMapping]] = field(default_factory=dict)

    # 端点配置
    endpoints: Dict[str, Dict] = field(default_factory=dict)

    def supports_category(self, category: str) -> bool:
        """检查是否支持某类数据"""
        return category in self.categories

    def supports_league(self, league_id: str) -> bool:
        """检查是否支持某联赛"""
        return league_id in self.league_ids

    def get_field_mapping(self, table: str) -> List[FieldMapping]:
        """获取某表的字段映射"""
        return self.field_mappings.get(table, [])

    def get_available_fields(self, table: str) -> Set[str]:
        """获取某表可提供的字段"""
        mappings = self.field_mappings.get(table, [])
        return {m.db_field for m in mappings}


# ==================== 数据源注册配置 ====================

# Sportmonks API 注册
SPORTMONKS_REGISTRY = DataSourceRegistry(
    name="sportmonks",
    source_type=SourceType.API,
    description="足球数据API，覆盖全球联赛/杯赛，数据最全",
    base_url="https://api.sportmonks.com/v3/football",
    auth_type="query_param",
    rate_limit=30,
    request_interval=2.0,
    priority=1,
    enabled=True,
    categories={
        "livescores", "fixtures", "standings", "teams", "players",
        "squad", "events", "statistics", "xg", "odds", "predictions",
        "lineups", "head2head", "referee", "sidelined", "news"
    },
    league_ids={
        "premier_league": 8,
        "la_liga": 564,
        "bundesliga": 35,
        "serie_a": 384,
        "ligue_1": 301,
        "champions_league": 7,
        "europa_league": 679,
    },
    field_mappings={
        "matches": [
            # 基础信息
            FieldMapping("match_id", FieldType.STRING, "id", FieldType.INTEGER, "str", True),
            FieldMapping("league_id", FieldType.INTEGER, "league_id", FieldType.INTEGER),
            FieldMapping("season_id", FieldType.INTEGER, "season_id", FieldType.INTEGER),
            FieldMapping("match_date", FieldType.DATE, "starting_at", FieldType.DATETIME, "extract_date"),
            FieldMapping("match_time", FieldType.TIME, "starting_at", FieldType.DATETIME, "extract_time"),
            FieldMapping("round_num", FieldType.INTEGER, "round_name", FieldType.STRING, "parse_round"),
            FieldMapping("venue", FieldType.STRING, "venue.name", FieldType.STRING),
            FieldMapping("venue_city", FieldType.STRING, "venue.city", FieldType.STRING),
            FieldMapping("referee", FieldType.STRING, "referee.common_name", FieldType.STRING),
            FieldMapping("attendance", FieldType.INTEGER, "attendance", FieldType.INTEGER),

            # 球队
            FieldMapping("home_team_id", FieldType.INTEGER, "participants[meta.location=home].id", FieldType.INTEGER),
            FieldMapping("away_team_id", FieldType.INTEGER, "participants[meta.location=away].id", FieldType.INTEGER),

            # 比分
            FieldMapping("home_goals", FieldType.INTEGER, "scores.ft.home_score", FieldType.INTEGER),
            FieldMapping("away_goals", FieldType.INTEGER, "scores.ft.away_score", FieldType.INTEGER),
            FieldMapping("home_goals_ht", FieldType.INTEGER, "scores.ht.home_score", FieldType.INTEGER),
            FieldMapping("away_goals_ht", FieldType.INTEGER, "scores.ht.away_score", FieldType.INTEGER),

            # 统计
            FieldMapping("home_shots", FieldType.INTEGER, "statistics.shots_total.home", FieldType.INTEGER),
            FieldMapping("away_shots", FieldType.INTEGER, "statistics.shots_total.away", FieldType.INTEGER),
            FieldMapping("home_shots_target", FieldType.INTEGER, "statistics.shots_on_target.home", FieldType.INTEGER),
            FieldMapping("away_shots_target", FieldType.INTEGER, "statistics.shots_on_target.away", FieldType.INTEGER),
            FieldMapping("home_corners", FieldType.INTEGER, "statistics.corners.home", FieldType.INTEGER),
            FieldMapping("away_corners", FieldType.INTEGER, "statistics.corners.away", FieldType.INTEGER),
            FieldMapping("home_fouls", FieldType.INTEGER, "statistics.fouls.home", FieldType.INTEGER),
            FieldMapping("away_fouls", FieldType.INTEGER, "statistics.fouls.away", FieldType.INTEGER),
            FieldMapping("home_yellow", FieldType.INTEGER, "statistics.yellow_cards.home", FieldType.INTEGER),
            FieldMapping("away_yellow", FieldType.INTEGER, "statistics.yellow_cards.away", FieldType.INTEGER),
            FieldMapping("home_red", FieldType.INTEGER, "statistics.red_cards.home", FieldType.INTEGER),
            FieldMapping("away_red", FieldType.INTEGER, "statistics.red_cards.away", FieldType.INTEGER),
            FieldMapping("home_possession", FieldType.FLOAT, "statistics.ball_possession.home", FieldType.FLOAT),
            FieldMapping("away_possession", FieldType.FLOAT, "statistics.ball_possession.away", FieldType.FLOAT),

            # xG
            FieldMapping("home_xg", FieldType.FLOAT, "xgfixture.home", FieldType.FLOAT),
            FieldMapping("away_xg", FieldType.FLOAT, "xgfixture.away", FieldType.FLOAT),

            # 状态
            FieldMapping("status", FieldType.STRING, "state_id", FieldType.INTEGER, "match_status"),
            FieldMapping("source", FieldType.STRING, None, FieldType.STRING, default="sportmonks"),
        ],
        "teams": [
            FieldMapping("team_id", FieldType.INTEGER, "id", FieldType.INTEGER, required=True),
            FieldMapping("name_en", FieldType.STRING, "name", FieldType.STRING, required=True),
            FieldMapping("short_name", FieldType.STRING, "short_code", FieldType.STRING),
            FieldMapping("tla", FieldType.STRING, "short_code", FieldType.STRING),
            FieldMapping("country", FieldType.STRING, "country.name", FieldType.STRING),
            FieldMapping("stadium", FieldType.STRING, "venue.name", FieldType.STRING),
            FieldMapping("stadium_capacity", FieldType.INTEGER, "venue.capacity", FieldType.INTEGER),
            FieldMapping("founded_year", FieldType.INTEGER, "founded", FieldType.INTEGER),
            FieldMapping("logo_url", FieldType.STRING, "image_path", FieldType.STRING),
            FieldMapping("sm_team_id", FieldType.INTEGER, "id", FieldType.INTEGER),
        ],
        "standings": [
            FieldMapping("position", FieldType.INTEGER, "position", FieldType.INTEGER, required=True),
            FieldMapping("team_id", FieldType.INTEGER, "participant_id", FieldType.INTEGER, required=True),
            FieldMapping("played", FieldType.INTEGER, "details.played", FieldType.INTEGER),
            FieldMapping("won", FieldType.INTEGER, "details.won", FieldType.INTEGER),
            FieldMapping("drawn", FieldType.INTEGER, "details.draw", FieldType.INTEGER),
            FieldMapping("lost", FieldType.INTEGER, "details.lost", FieldType.INTEGER),
            FieldMapping("goals_for", FieldType.INTEGER, "details.goals_scored", FieldType.INTEGER),
            FieldMapping("goals_against", FieldType.INTEGER, "details.goals_against", FieldType.INTEGER),
            FieldMapping("goal_diff", FieldType.INTEGER, "details.goal_difference", FieldType.INTEGER),
            FieldMapping("points", FieldType.INTEGER, "details.points", FieldType.INTEGER),
            FieldMapping("form", FieldType.STRING, "form", FieldType.STRING),
        ],
        "players": [
            FieldMapping("player_id", FieldType.INTEGER, "id", FieldType.INTEGER, required=True),
            FieldMapping("name_en", FieldType.STRING, "name", FieldType.STRING, required=True),
            FieldMapping("full_name", FieldType.STRING, "display_name", FieldType.STRING),
            FieldMapping("nationality", FieldType.STRING, "country.name", FieldType.STRING),
            FieldMapping("birth_date", FieldType.DATE, "date_of_birth", FieldType.STRING),
            FieldMapping("height", FieldType.INTEGER, "height", FieldType.INTEGER),
            FieldMapping("weight", FieldType.INTEGER, "weight", FieldType.INTEGER),
            FieldMapping("position_main", FieldType.STRING, "position.name", FieldType.STRING),
            FieldMapping("logo_url", FieldType.STRING, "image_path", FieldType.STRING),
            FieldMapping("sm_player_id", FieldType.INTEGER, "id", FieldType.INTEGER),
        ],
    },
    endpoints={
        "livescores": {
            "path": "/livescores/inplay",
            "method": "GET",
            "include": "participants;scores;periods;events;league.country;round"
        },
        "fixtures_by_date": {
            "path": "/fixtures/date/{date}",
            "method": "GET",
            "include": "participants;scores;league.country;round;venue;referee"
        },
        "league_fixtures": {
            "path": "/leagues/{league_id}/fixtures",
            "method": "GET",
            "include": "participants;scores;league.country;round;statistics"
        },
        "standings": {
            "path": "/standings/seasons/{season_id}",
            "method": "GET",
            "include": "participant;details;form"
        },
        "team_detail": {
            "path": "/teams/{team_id}",
            "method": "GET",
            "include": "country;venue;coaches"
        },
        "player_detail": {
            "path": "/players/{player_id}",
            "method": "GET",
            "include": "country;position;teams"
        },
    }
)

# football-data.org 注册
FOOTBALL_DATA_ORG_REGISTRY = DataSourceRegistry(
    name="football_data_org",
    source_type=SourceType.API,
    description="免费足球数据API，覆盖12个T1联赛",
    base_url="https://api.football-data.org/v4",
    auth_type="header",
    rate_limit=10,
    request_interval=7.0,
    priority=2,
    enabled=True,
    categories={
        "matches", "standings", "scorers", "squads", "teams", "competitions"
    },
    league_ids={
        "premier_league": 2021,
        "la_liga": 2014,
        "bundesliga": 2002,
        "serie_a": 2019,
        "ligue_1": 2015,
        "champions_league": 2001,
    },
    field_mappings={
        "matches": [
            FieldMapping("match_id", FieldType.STRING, "id", FieldType.INTEGER, "str", True),
            FieldMapping("league_id", FieldType.INTEGER, "competition.code", FieldType.STRING, "league_id_fd"),
            FieldMapping("match_date", FieldType.DATE, "utcDate", FieldType.DATETIME, "extract_date"),
            FieldMapping("match_time", FieldType.TIME, "utcDate", FieldType.DATETIME, "extract_time"),
            FieldMapping("round_num", FieldType.INTEGER, "matchday", FieldType.INTEGER),
            FieldMapping("stage_type", FieldType.STRING, "stage", FieldType.STRING),
            FieldMapping("group_name", FieldType.STRING, "group", FieldType.STRING),
            FieldMapping("home_team_id", FieldType.INTEGER, "homeTeam.id", FieldType.INTEGER),
            FieldMapping("away_team_id", FieldType.INTEGER, "awayTeam.id", FieldType.INTEGER),
            FieldMapping("home_goals", FieldType.INTEGER, "score.fullTime.home", FieldType.INTEGER),
            FieldMapping("away_goals", FieldType.INTEGER, "score.fullTime.away", FieldType.INTEGER),
            FieldMapping("home_goals_ht", FieldType.INTEGER, "score.halfTime.home", FieldType.INTEGER),
            FieldMapping("away_goals_ht", FieldType.INTEGER, "score.halfTime.away", FieldType.INTEGER),
            FieldMapping("home_goals_et", FieldType.INTEGER, "score.extraTime.home", FieldType.INTEGER),
            FieldMapping("away_goals_et", FieldType.INTEGER, "score.extraTime.away", FieldType.INTEGER),
            FieldMapping("home_penalties", FieldType.INTEGER, "score.penalties.home", FieldType.INTEGER),
            FieldMapping("away_penalties", FieldType.INTEGER, "score.penalties.away", FieldType.INTEGER),
            FieldMapping("status", FieldType.STRING, "status", FieldType.STRING),
            FieldMapping("referee", FieldType.STRING, "referees[0].name", FieldType.STRING),
            FieldMapping("source", FieldType.STRING, None, FieldType.STRING, default="football_data_org"),
        ],
        "teams": [
            FieldMapping("team_id", FieldType.INTEGER, "id", FieldType.INTEGER, required=True),
            FieldMapping("name_en", FieldType.STRING, "name", FieldType.STRING, required=True),
            FieldMapping("short_name", FieldType.STRING, "shortName", FieldType.STRING),
            FieldMapping("tla", FieldType.STRING, "tla", FieldType.STRING),
            FieldMapping("country", FieldType.STRING, "area.name", FieldType.STRING),
            FieldMapping("stadium", FieldType.STRING, "venue", FieldType.STRING),
            FieldMapping("founded_year", FieldType.INTEGER, "founded", FieldType.INTEGER),
            FieldMapping("logo_url", FieldType.STRING, "crest", FieldType.STRING),
            FieldMapping("fd_team_id", FieldType.INTEGER, "id", FieldType.INTEGER),
        ],
        "standings": [
            FieldMapping("position", FieldType.INTEGER, "position", FieldType.INTEGER, required=True),
            FieldMapping("team_id", FieldType.INTEGER, "team.id", FieldType.INTEGER, required=True),
            FieldMapping("played", FieldType.INTEGER, "playedGames", FieldType.INTEGER),
            FieldMapping("won", FieldType.INTEGER, "won", FieldType.INTEGER),
            FieldMapping("drawn", FieldType.INTEGER, "draw", FieldType.INTEGER),
            FieldMapping("lost", FieldType.INTEGER, "lost", FieldType.INTEGER),
            FieldMapping("goals_for", FieldType.INTEGER, "goalsFor", FieldType.INTEGER),
            FieldMapping("goals_against", FieldType.INTEGER, "goalsAgainst", FieldType.INTEGER),
            FieldMapping("goal_diff", FieldType.INTEGER, "goalDifference", FieldType.INTEGER),
            FieldMapping("points", FieldType.INTEGER, "points", FieldType.INTEGER),
            FieldMapping("form", FieldType.STRING, "form", FieldType.STRING),
        ],
        "players": [
            FieldMapping("player_id", FieldType.INTEGER, "id", FieldType.INTEGER, required=True),
            FieldMapping("name_en", FieldType.STRING, "name", FieldType.STRING, required=True),
            FieldMapping("nationality", FieldType.STRING, "nationality", FieldType.STRING),
            FieldMapping("birth_date", FieldType.DATE, "dateOfBirth", FieldType.STRING),
            FieldMapping("position_main", FieldType.STRING, "section", FieldType.STRING),
            FieldMapping("fd_player_id", FieldType.INTEGER, "id", FieldType.INTEGER),
        ],
    },
    endpoints={
        "competition_matches": {
            "path": "/competitions/{code}/matches",
            "method": "GET",
        },
        "competition_standings": {
            "path": "/competitions/{code}/standings",
            "method": "GET",
        },
        "competition_scorers": {
            "path": "/competitions/{code}/scorers",
            "method": "GET",
        },
        "team_detail": {
            "path": "/teams/{id}",
            "method": "GET",
        },
    }
)

# FBref 爬虫注册
FBREF_REGISTRY = DataSourceRegistry(
    name="fbref",
    source_type=SourceType.SCRAPER,
    description="FBref网站爬虫，获取免费足球数据",
    base_url="https://fbref.com",
    auth_type="none",
    rate_limit=20,
    request_interval=3.0,
    priority=7,
    enabled=True,
    categories={
        "matches", "standings", "player_stats", "team_stats", "advanced_stats", "xg"
    },
    league_ids={
        "k_league": 313,
        "j_league": 25,
        "mls": 22,
        "liga_mx": 24,
        "brasileirao": 24,
    },
    field_mappings={
        "matches": [
            FieldMapping("match_date", FieldType.DATE, "Date", FieldType.STRING),
            FieldMapping("match_time", FieldType.TIME, "Time", FieldType.STRING),
            FieldMapping("home_team_id", FieldType.INTEGER, "HomeTeam", FieldType.STRING, "team_name_to_id"),
            FieldMapping("away_team_id", FieldType.INTEGER, "AwayTeam", FieldType.STRING, "team_name_to_id"),
            FieldMapping("home_goals", FieldType.INTEGER, "FTHG", FieldType.INTEGER),
            FieldMapping("away_goals", FieldType.INTEGER, "FTAG", FieldType.INTEGER),
            FieldMapping("home_goals_ht", FieldType.INTEGER, "HTHG", FieldType.INTEGER),
            FieldMapping("away_goals_ht", FieldType.INTEGER, "HTAG", FieldType.INTEGER),
            FieldMapping("result", FieldType.STRING, "FTR", FieldType.STRING),
            FieldMapping("home_shots", FieldType.INTEGER, "HS", FieldType.INTEGER),
            FieldMapping("away_shots", FieldType.INTEGER, "AS", FieldType.INTEGER),
            FieldMapping("home_shots_target", FieldType.INTEGER, "HST", FieldType.INTEGER),
            FieldMapping("away_shots_target", FieldType.INTEGER, "AST", FieldType.INTEGER),
            FieldMapping("home_corners", FieldType.INTEGER, "HC", FieldType.INTEGER),
            FieldMapping("away_corners", FieldType.INTEGER, "AC", FieldType.INTEGER),
            FieldMapping("home_fouls", FieldType.INTEGER, "HF", FieldType.INTEGER),
            FieldMapping("away_fouls", FieldType.INTEGER, "AF", FieldType.INTEGER),
            FieldMapping("home_yellow", FieldType.INTEGER, "HY", FieldType.INTEGER),
            FieldMapping("away_yellow", FieldType.INTEGER, "AY", FieldType.INTEGER),
            FieldMapping("home_red", FieldType.INTEGER, "HR", FieldType.INTEGER),
            FieldMapping("away_red", FieldType.INTEGER, "AR", FieldType.INTEGER),
            FieldMapping("referee", FieldType.STRING, "Referee", FieldType.STRING),
            FieldMapping("attendance", FieldType.INTEGER, "Attendance", FieldType.INTEGER),
            FieldMapping("home_xg", FieldType.FLOAT, "Home xG", FieldType.FLOAT),
            FieldMapping("away_xg", FieldType.FLOAT, "Away xG", FieldType.FLOAT),
            FieldMapping("odds_home", FieldType.FLOAT, "B365H", FieldType.FLOAT),
            FieldMapping("odds_draw", FieldType.FLOAT, "B365D", FieldType.FLOAT),
            FieldMapping("odds_away", FieldType.FLOAT, "B365A", FieldType.FLOAT),
            FieldMapping("source", FieldType.STRING, None, FieldType.STRING, default="fbref"),
        ],
    },
)

# TheSportsDB 注册
THESPORTSDB_REGISTRY = DataSourceRegistry(
    name="thesportsdb",
    source_type=SourceType.API,
    description="免费体育数据API，无需Key",
    base_url="https://www.thesportsdb.com/api/v1/json/3",
    auth_type="none",
    rate_limit=60,
    request_interval=1.0,
    priority=4,
    enabled=True,
    categories={
        "livescores", "events", "leagues", "teams", "players"
    },
    field_mappings={
        "matches": [
            FieldMapping("match_id", FieldType.STRING, "idEvent", FieldType.STRING, required=True),
            FieldMapping("league_id", FieldType.INTEGER, "idLeague", FieldType.INTEGER),
            FieldMapping("match_date", FieldType.DATE, "dateEvent", FieldType.STRING),
            FieldMapping("match_time", FieldType.TIME, "strTime", FieldType.STRING),
            FieldMapping("round_num", FieldType.INTEGER, "intRound", FieldType.INTEGER),
            FieldMapping("venue", FieldType.STRING, "strVenue", FieldType.STRING),
            FieldMapping("home_team_id", FieldType.INTEGER, "idHomeTeam", FieldType.INTEGER),
            FieldMapping("away_team_id", FieldType.INTEGER, "idAwayTeam", FieldType.INTEGER),
            FieldMapping("home_goals", FieldType.INTEGER, "intHomeScore", FieldType.INTEGER),
            FieldMapping("away_goals", FieldType.INTEGER, "intAwayScore", FieldType.INTEGER),
            FieldMapping("status", FieldType.STRING, "strStatus", FieldType.STRING),
            FieldMapping("source", FieldType.STRING, None, FieldType.STRING, default="thesportsdb"),
        ],
        "teams": [
            FieldMapping("team_id", FieldType.INTEGER, "idTeam", FieldType.INTEGER, required=True),
            FieldMapping("name_en", FieldType.STRING, "strTeam", FieldType.STRING, required=True),
            FieldMapping("short_name", FieldType.STRING, "strTeamShort", FieldType.STRING),
            FieldMapping("country", FieldType.STRING, "strCountry", FieldType.STRING),
            FieldMapping("stadium", FieldType.STRING, "strStadium", FieldType.STRING),
            FieldMapping("stadium_capacity", FieldType.INTEGER, "intStadiumCapacity", FieldType.INTEGER),
            FieldMapping("logo_url", FieldType.STRING, "strTeamBadge", FieldType.STRING),
            FieldMapping("tsdb_team_id", FieldType.INTEGER, "idTeam", FieldType.INTEGER),
        ],
    },
)


class SourceRegistryManager:
    """数据源注册管理器"""

    def __init__(self):
        self.registries: Dict[str, DataSourceRegistry] = {}
        self._register_default_sources()

    def _register_default_sources(self):
        """注册默认数据源"""
        self.register(SPORTMONKS_REGISTRY)
        self.register(FOOTBALL_DATA_ORG_REGISTRY)
        self.register(FBREF_REGISTRY)
        self.register(THESPORTSDB_REGISTRY)

    def register(self, registry: DataSourceRegistry):
        """注册数据源"""
        self.registries[registry.name] = registry

    def get(self, name: str) -> Optional[DataSourceRegistry]:
        """获取数据源注册信息"""
        return self.registries.get(name)

    def list_sources(self) -> List[DataSourceRegistry]:
        """列出所有数据源"""
        return sorted(self.registries.values(), key=lambda x: x.priority)

    def find_sources_for_category(self, category: str) -> List[DataSourceRegistry]:
        """查找支持某类数据的所有数据源"""
        sources = [s for s in self.registries.values()
                   if s.supports_category(category) and s.enabled]
        return sorted(sources, key=lambda x: x.priority)

    def find_sources_for_fields(self, table: str, fields: Set[str]) -> List[DataSourceRegistry]:
        """根据需要的字段查找数据源"""
        sources = []
        for source in self.registries.values():
            if not source.enabled:
                continue
            available = source.get_available_fields(table)
            # 计算覆盖率
            coverage = len(fields & available) / len(fields) if fields else 0
            if coverage > 0:
                sources.append((source, coverage))

        # 按覆盖率降序，同覆盖率按优先级升序
        sources.sort(key=lambda x: (-x[1], x[0].priority))
        return [s[0] for s in sources]

    def find_best_source(self, table: str, fields: Set[str]) -> Optional[DataSourceRegistry]:
        """找到最佳数据源"""
        sources = self.find_sources_for_fields(table, fields)
        return sources[0] if sources else None

    def get_field_coverage_report(self, table: str, fields: Set[str]) -> Dict[str, Dict]:
        """获取字段覆盖报告"""
        report = {}
        for source in self.registries.values():
            if not source.enabled:
                continue
            available = source.get_available_fields(table)
            covered = fields & available
            missing = fields - available
            report[source.name] = {
                "coverage": len(covered) / len(fields) if fields else 0,
                "covered_fields": list(covered),
                "missing_fields": list(missing),
                "priority": source.priority,
            }
        return report

    def to_json(self) -> str:
        """导出为JSON"""
        data = {}
        for name, registry in self.registries.items():
            data[name] = {
                "name": registry.name,
                "type": registry.source_type.value,
                "description": registry.description,
                "categories": list(registry.categories),
                "priority": registry.priority,
                "enabled": registry.enabled,
                "rate_limit": registry.rate_limit,
                "field_mappings": {
                    table: [
                        {
                            "db_field": m.db_field,
                            "source_field": m.source_field,
                            "transform": m.transform,
                            "required": m.required,
                        }
                        for m in mappings
                    ]
                    for table, mappings in registry.field_mappings.items()
                }
            }
        return json.dumps(data, indent=2, ensure_ascii=False)


# 全局实例
registry_manager = SourceRegistryManager()
