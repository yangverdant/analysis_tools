"""
数据源配置模块
详细记录每个API渠道的：
1. 免费版/付费版差异
2. 支持的联赛/赛事
3. 可获取的数据字段
4. 速率限制
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Set
from enum import Enum


class DataSourceType(Enum):
    """数据源类型"""
    API = "api"
    SCRAPER = "scraper"
    LLM = "llm"
    LOCAL = "local"


class PricingType(Enum):
    """定价类型"""
    FREE = "free"
    FREEMIUM = "freemium"
    PAID = "paid"


@dataclass
class RateLimit:
    """速率限制"""
    requests_per_minute: int = 60
    requests_per_day: int = 1000
    requests_per_month: Optional[int] = None
    current_usage: int = 0


@dataclass
class TierLimit:
    """套餐限制"""
    tier_name: str                           # 套餐名称
    price: str                               # 价格
    requests_per_minute: int = 60            # 每分钟请求
    requests_per_day: int = 1000             # 每日请求
    requests_per_month: Optional[int] = None # 每月请求
    max_leagues: int = 999                   # 最大联赛数
    max_seasons: int = 999                   # 最大赛季数
    historical_years: int = 0                # 历史数据年数
    has_realtime: bool = True                # 是否有实时数据
    has_odds: bool = False                   # 是否有赔率
    has_lineups: bool = True                 # 是否有阵容
    has_statistics: bool = True              # 是否有统计
    has_player_data: bool = True             # 是否有球员数据
    priority_support: bool = False           # 优先支持
    notes: str = ""


@dataclass
class DataField:
    """数据字段定义"""
    field_name: str           # 字段名
    field_name_cn: str        # 中文名
    description: str = ""     # 描述
    free_available: bool = True    # 免费版是否可用
    paid_available: bool = True    # 付费版是否可用
    realtime: bool = False         # 是否实时更新
    delay_seconds: int = 0         # 延迟秒数


@dataclass
class DataTypeSupport:
    """数据类型支持情况"""
    data_type: str                    # 数据类型
    data_type_cn: str                 # 中文名
    free_available: bool = False      # 免费版是否可用
    paid_available: bool = True       # 付费版是否可用
    quality_score: int = 5            # 质量评分 1-10
    coverage: float = 0.8             # 覆盖率
    update_frequency: str = "daily"   # 更新频率
    delay_seconds: int = 0            # 延迟
    fields: List[DataField] = field(default_factory=list)  # 可获取字段
    notes: str = ""


@dataclass
class LeagueSupport:
    """联赛支持情况"""
    league_id: int
    league_name: str
    league_name_cn: str = ""
    country: str = ""
    free_available: bool = True       # 免费版是否可用
    paid_available: bool = True       # 付费版是否可用
    coverage: float = 1.0
    notes: str = ""


@dataclass
class DataSourceConfig:
    """数据源完整配置"""
    id: str
    name: str
    name_cn: str = ""
    type: DataSourceType = DataSourceType.API
    base_url: str = ""
    api_key_env: str = ""
    enabled: bool = True
    priority: int = 5

    # 套餐信息
    tiers: List[TierLimit] = field(default_factory=list)

    # 数据类型支持
    data_types: Dict[str, DataTypeSupport] = field(default_factory=dict)

    # 联赛支持
    leagues: List[LeagueSupport] = field(default_factory=list)
    free_leagues_count: int = 0       # 免费版支持的联赛数
    paid_leagues_count: int = 0       # 付费版支持的联赛数

    # 统计
    total_leagues: int = 0
    total_countries: int = 0

    description: str = ""
    notes: str = ""


# ==================== API数据源配置 ====================

API_SPORTS_CONFIG = DataSourceConfig(
    id="api_sports",
    name="API-Sports (Football)",
    name_cn="API-Sports足球接口",
    type=DataSourceType.API,
    base_url="https://api-football-v1.p.rapidapi.com/v3",
    api_key_env="API_SPORT_KEY",
    enabled=True,
    priority=1,

    # 套餐信息
    tiers=[
        TierLimit(
            tier_name="FREE",
            price="$0/月",
            requests_per_minute=30,
            requests_per_day=100,
            requests_per_month=100,
            max_leagues=10,           # 免费版只能访问10个联赛
            max_seasons=1,            # 只能访问当前赛季
            historical_years=0,       # 无历史数据
            has_realtime=True,
            has_odds=False,           # 无赔率
            has_lineups=True,
            has_statistics=True,
            has_player_data=True,
            notes="免费版限制较多，仅主流联赛当前赛季"
        ),
        TierLimit(
            tier_name="STARTER",
            price="$9.99/月",
            requests_per_minute=100,
            requests_per_day=3000,
            requests_per_month=30000,
            max_leagues=100,
            max_seasons=3,
            historical_years=2,
            has_realtime=True,
            has_odds=True,
            has_lineups=True,
            has_statistics=True,
            has_player_data=True,
            notes="入门版，支持历史数据"
        ),
        TierLimit(
            tier_name="PRO",
            price="$29.99/月",
            requests_per_minute=200,
            requests_per_day=10000,
            requests_per_month=100000,
            max_leagues=999,
            max_seasons=999,
            historical_years=15,
            has_realtime=True,
            has_odds=True,
            has_lineups=True,
            has_statistics=True,
            has_player_data=True,
            priority_support=True,
            notes="专业版，完整数据访问"
        ),
    ],

    # 数据类型支持
    data_types={
        "matches": DataTypeSupport(
            data_type="matches",
            data_type_cn="比赛数据",
            free_available=True,
            paid_available=True,
            quality_score=9,
            coverage=0.95,
            update_frequency="realtime",
            delay_seconds=60,
            fields=[
                DataField("fixture_id", "比赛ID", free_available=True),
                DataField("date", "比赛日期", free_available=True),
                DataField("time", "比赛时间", free_available=True),
                DataField("status", "比赛状态", free_available=True, realtime=True),
                DataField("home_team", "主队", free_available=True),
                DataField("away_team", "客队", free_available=True),
                DataField("home_goals", "主队进球", free_available=True, realtime=True),
                DataField("away_goals", "客队进球", free_available=True, realtime=True),
                DataField("half_time_score", "半场比分", free_available=True, realtime=True),
                DataField("full_time_score", "全场比分", free_available=True, realtime=True),
                DataField("venue", "球场", free_available=True),
                DataField("referee", "裁判", free_available=True),
            ],
            notes="免费版仅当前赛季，付费版可查历史"
        ),
        "standings": DataTypeSupport(
            data_type="standings",
            data_type_cn="积分榜",
            free_available=True,
            paid_available=True,
            quality_score=9,
            coverage=0.95,
            update_frequency="realtime",
            fields=[
                DataField("rank", "排名", free_available=True),
                DataField("points", "积分", free_available=True),
                DataField("played", "已赛场次", free_available=True),
                DataField("won", "胜", free_available=True),
                DataField("draw", "平", free_available=True),
                DataField("lost", "负", free_available=True),
                DataField("goals_for", "进球", free_available=True),
                DataField("goals_against", "失球", free_available=True),
                DataField("goal_diff", "净胜球", free_available=True),
                DataField("form", "近期战绩", free_available=True),
            ]
        ),
        "lineups": DataTypeSupport(
            data_type="lineups",
            data_type_cn="阵容数据",
            free_available=True,
            paid_available=True,
            quality_score=7,
            coverage=0.7,
            update_frequency="realtime",
            delay_seconds=300,
            fields=[
                DataField("formation", "阵型", free_available=True),
                DataField("startXI", "首发阵容", free_available=True),
                DataField("substitutes", "替补席", free_available=True),
                DataField("coach", "主教练", free_available=True),
            ],
            notes="部分比赛可能无阵容数据"
        ),
        "events": DataTypeSupport(
            data_type="events",
            data_type_cn="比赛事件",
            free_available=True,
            paid_available=True,
            quality_score=8,
            coverage=0.85,
            update_frequency="realtime",
            delay_seconds=30,
            fields=[
                DataField("goal", "进球", free_available=True, realtime=True),
                DataField("assist", "助攻", free_available=True, realtime=True),
                DataField("yellow_card", "黄牌", free_available=True, realtime=True),
                DataField("red_card", "红牌", free_available=True, realtime=True),
                DataField("substitution", "换人", free_available=True, realtime=True),
                DataField("penalty", "点球", free_available=True, realtime=True),
                DataField("own_goal", "乌龙球", free_available=True, realtime=True),
            ]
        ),
        "statistics": DataTypeSupport(
            data_type="statistics",
            data_type_cn="比赛统计",
            free_available=True,
            paid_available=True,
            quality_score=8,
            coverage=0.8,
            update_frequency="realtime",
            fields=[
                DataField("shots_on_goal", "射正", free_available=True),
                DataField("shots_off_goal", "射偏", free_available=True),
                DataField("total_shots", "总射门", free_available=True),
                DataField("blocked_shots", "被封堵", free_available=True),
                DataField("corners", "角球", free_available=True),
                DataField("offsides", "越位", free_available=True),
                DataField("possession", "控球率", free_available=True),
                DataField("passes", "传球", free_available=True),
                DataField("pass_accuracy", "传球成功率", free_available=True),
                DataField("fouls", "犯规", free_available=True),
                DataField("yellow_cards", "黄牌数", free_available=True),
                DataField("red_cards", "红牌数", free_available=True),
            ]
        ),
        "players": DataTypeSupport(
            data_type="players",
            data_type_cn="球员数据",
            free_available=True,
            paid_available=True,
            quality_score=7,
            coverage=0.75,
            fields=[
                DataField("player_id", "球员ID", free_available=True),
                DataField("name", "姓名", free_available=True),
                DataField("age", "年龄", free_available=True),
                DataField("nationality", "国籍", free_available=True),
                DataField("height", "身高", free_available=True),
                DataField("weight", "体重", free_available=True),
                DataField("position", "位置", free_available=True),
                DataField("rating", "评分", free_available=True),
                DataField("goals", "进球数", paid_available=True),  # 付费
                DataField("assists", "助攻数", paid_available=True),  # 付费
                DataField("cards", "红黄牌", paid_available=True),    # 付费
            ],
            notes="详细统计数据需付费版"
        ),
        "teams": DataTypeSupport(
            data_type="teams",
            data_type_cn="球队数据",
            free_available=True,
            paid_available=True,
            quality_score=8,
            coverage=0.9,
            fields=[
                DataField("team_id", "球队ID", free_available=True),
                DataField("name", "队名", free_available=True),
                DataField("country", "国家", free_available=True),
                DataField("founded", "成立年份", free_available=True),
                DataField("venue", "主场", free_available=True),
                DataField("capacity", "容量", free_available=True),
                DataField("logo", "队徽", free_available=True),
            ]
        ),
        "odds": DataTypeSupport(
            data_type="odds",
            data_type_cn="赔率数据",
            free_available=False,        # 免费版无赔率
            paid_available=True,
            quality_score=6,
            coverage=0.6,
            update_frequency="hourly",
            fields=[
                DataField("home_win", "主胜赔率", free_available=False),
                DataField("draw", "平局赔率", free_available=False),
                DataField("away_win", "客胜赔率", free_available=False),
                DataField("asian_handicap", "亚盘", free_available=False),
                DataField("over_under", "大小球", free_available=False),
                DataField("correct_score", "波胆", free_available=False),
                DataField("half_time_full_time", "半全场", free_available=False),
            ],
            notes="赔率数据需付费版，覆盖有限"
        ),
        "predictions": DataTypeSupport(
            data_type="predictions",
            data_type_cn="预测数据",
            free_available=True,
            paid_available=True,
            quality_score=5,
            coverage=0.5,
            fields=[
                DataField("winner", "预测胜者", free_available=True),
                DataField("win_percent", "胜率预测", free_available=True),
                DataField("advice", "建议", free_available=True),
            ],
            notes="API提供的预测，仅供参考"
        ),
        "injuries": DataTypeSupport(
            data_type="injuries",
            data_type_cn="伤病名单",
            free_available=True,
            paid_available=True,
            quality_score=6,
            coverage=0.5,
            fields=[
                DataField("player", "球员", free_available=True),
                DataField("type", "伤病类型", free_available=True),
                DataField("reason", "原因", free_available=True),
            ]
        ),
        "transfers": DataTypeSupport(
            data_type="transfers",
            data_type_cn="转会数据",
            free_available=True,
            paid_available=True,
            quality_score=7,
            coverage=0.7,
            fields=[
                DataField("player", "球员", free_available=True),
                DataField("from_team", "转出球队", free_available=True),
                DataField("to_team", "转入球队", free_available=True),
                DataField("date", "转会日期", free_available=True),
                DataField("type", "转会类型", free_available=True),
            ]
        ),
    },

    # 联赛支持
    leagues=[
        # 免费版可访问的联赛 (前10个)
        LeagueSupport(39, "Premier League", "英超", "England", free_available=True),
        LeagueSupport(140, "La Liga", "西甲", "Spain", free_available=True),
        LeagueSupport(135, "Serie A", "意甲", "Italy", free_available=True),
        LeagueSupport(78, "Bundesliga", "德甲", "Germany", free_available=True),
        LeagueSupport(61, "Ligue 1", "法甲", "France", free_available=True),
        LeagueSupport(2, "UEFA Champions League", "欧冠", "Europe", free_available=True),
        LeagueSupport(3, "UEFA Europa League", "欧联杯", "Europe", free_available=True),
        LeagueSupport(1, "FIFA World Cup", "世界杯", "World", free_available=True),
        LeagueSupport(4, "UEFA European Championship", "欧洲杯", "Europe", free_available=True),
        LeagueSupport(144, "Eredivisie", "荷甲", "Netherlands", free_available=True),

        # 付费版才能访问的联赛
        LeagueSupport(94, "Primeira Liga", "葡超", "Portugal", free_available=False, paid_available=True),
        LeagueSupport(88, "Jupiler Pro League", "比甲", "Belgium", free_available=False, paid_available=True),
        LeagueSupport(113, "Championship", "英冠", "England", free_available=False, paid_available=True),
        LeagueSupport(45, "FA Cup", "足总杯", "England", free_available=False, paid_available=True),
        LeagueSupport(48, "Carabao Cup", "联赛杯", "England", free_available=False, paid_available=True),
        LeagueSupport(143, "Copa del Rey", "国王杯", "Spain", free_available=False, paid_available=True),
        LeagueSupport(137, "Coppa Italia", "意大利杯", "Italy", free_available=False, paid_available=True),
        LeagueSupport(81, "DFB-Pokal", "德国杯", "Germany", free_available=False, paid_available=True),

        # 亚洲联赛 (付费)
        LeagueSupport(169, "J1 League", "J联赛", "Japan", free_available=False, paid_available=True),
        LeagueSupport(292, "K League 1", "K联赛", "South Korea", free_available=False, paid_available=True),
        LeagueSupport(197, "Chinese Super League", "中超", "China", free_available=False, paid_available=True),
        LeagueSupport(307, "Saudi Pro League", "沙特联", "Saudi Arabia", free_available=False, paid_available=True),

        # 美洲联赛 (付费)
        LeagueSupport(71, "Brasileirão", "巴甲", "Brazil", free_available=False, paid_available=True),
        LeagueSupport(128, "Primera División", "阿甲", "Argentina", free_available=False, paid_available=True),
        LeagueSupport(253, "MLS", "美职联", "USA", free_available=False, paid_available=True),
    ],
    free_leagues_count=10,
    paid_leagues_count=900,
    total_leagues=900,
    total_countries=170,
    description="全球最大的足球数据API，覆盖900+联赛",
    notes="免费版限制较多，建议付费版获取完整数据"
)


# TheSportsDB 配置
THE_SPORTS_DB_CONFIG = DataSourceConfig(
    id="thesportsdb",
    name="TheSportsDB",
    name_cn="体育数据库",
    type=DataSourceType.API,
    base_url="https://www.thesportsdb.com/api/v1/json/3",
    enabled=True,
    priority=3,

    tiers=[
        TierLimit(
            tier_name="FREE",
            price="$0/月",
            requests_per_minute=60,
            requests_per_day=1000,
            max_leagues=999,
            has_realtime=False,        # 无实时数据
            has_odds=False,
            has_lineups=False,
            has_statistics=False,
            has_player_data=False,
            notes="完全免费，但数据更新慢，无实时数据"
        ),
        TierLimit(
            tier_name="PATRON",
            price="$3/月",
            requests_per_minute=120,
            requests_per_day=5000,
            max_leagues=999,
            has_realtime=True,
            has_odds=False,
            has_lineups=True,
            has_statistics=True,
            has_player_data=True,
            notes="支持者订阅，解锁更多功能"
        ),
    ],

    data_types={
        "matches": DataTypeSupport(
            data_type="matches",
            data_type_cn="比赛数据",
            free_available=True,
            paid_available=True,
            quality_score=6,
            coverage=0.7,
            update_frequency="hourly",
            fields=[
                DataField("idEvent", "比赛ID", free_available=True),
                DataField("dateEvent", "比赛日期", free_available=True),
                DataField("strTime", "比赛时间", free_available=True),
                DataField("strHomeTeam", "主队", free_available=True),
                DataField("strAwayTeam", "客队", free_available=True),
                DataField("intHomeScore", "主队进球", free_available=True),
                DataField("intAwayScore", "客队进球", free_available=True),
            ],
            notes="无实时数据，更新较慢"
        ),
        "teams": DataTypeSupport(
            data_type="teams",
            data_type_cn="球队数据",
            free_available=True,
            paid_available=True,
            quality_score=6,
            coverage=0.75,
            fields=[
                DataField("idTeam", "球队ID", free_available=True),
                DataField("strTeam", "队名", free_available=True),
                DataField("strStadium", "主场", free_available=True),
                DataField("strTeamBadge", "队徽", free_available=True),
                DataField("strDescriptionEN", "英文简介", free_available=True),
            ]
        ),
        "leagues": DataTypeSupport(
            data_type="leagues",
            data_type_cn="联赛数据",
            free_available=True,
            paid_available=True,
            quality_score=6,
            coverage=0.8,
            fields=[
                DataField("idLeague", "联赛ID", free_available=True),
                DataField("strLeague", "联赛名", free_available=True),
                DataField("strCountry", "国家", free_available=True),
            ]
        ),
        "standings": DataTypeSupport(
            data_type="standings",
            data_type_cn="积分榜",
            free_available=True,
            paid_available=True,
            quality_score=5,
            coverage=0.6,
            fields=[
                DataField("intRank", "排名", free_available=True),
                DataField("strTeam", "球队", free_available=True),
                DataField("intPoints", "积分", free_available=True),
            ],
            notes="积分榜数据不完整"
        ),
    },

    leagues=[
        LeagueSupport(4328, "Premier League", "英超", "England", free_available=True),
        LeagueSupport(4335, "La Liga", "西甲", "Spain", free_available=True),
        LeagueSupport(4332, "Serie A", "意甲", "Italy", free_available=True),
        LeagueSupport(4331, "Bundesliga", "德甲", "Germany", free_available=True),
        LeagueSupport(4334, "Ligue 1", "法甲", "France", free_available=True),
        LeagueSupport(4336, "Eredivisie", "荷甲", "Netherlands", free_available=True),
        LeagueSupport(4344, "Primeira Liga", "葡超", "Portugal", free_available=True),
        LeagueSupport(4330, "UEFA Champions League", "欧冠", "Europe", free_available=True),
        LeagueSupport(4331, "UEFA Europa League", "欧联杯", "Europe", free_available=True),
    ],
    free_leagues_count=200,
    paid_leagues_count=200,
    total_leagues=200,
    total_countries=50,
    description="免费开放的体育数据库，社区维护",
    notes="数据质量一般，更新不及时，但完全免费"
)


# Football-Data.org 配置
FOOTBALL_DATA_CONFIG = DataSourceConfig(
    id="football_data",
    name="Football-Data.org",
    name_cn="足球数据",
    type=DataSourceType.API,
    base_url="https://api.football-data.org/v4",
    api_key_env="FOOTBALL_DATA_KEY",
    enabled=True,
    priority=4,

    tiers=[
        TierLimit(
            tier_name="FREE",
            price="$0/月",
            requests_per_minute=10,
            requests_per_day=500,
            max_leagues=12,            # 免费版12个联赛
            max_seasons=1,
            historical_years=0,
            has_realtime=True,
            has_odds=False,
            has_lineups=False,
            has_statistics=False,
            has_player_data=False,
            notes="免费版仅欧洲主流联赛"
        ),
        TierLimit(
            tier_name="STANDARD",
            price="$10/月",
            requests_per_minute=30,
            requests_per_day=3000,
            max_leagues=20,
            max_seasons=3,
            historical_years=2,
            has_realtime=True,
            has_odds=False,
            has_lineups=True,
            has_statistics=True,
            has_player_data=True,
        ),
        TierLimit(
            tier_name="PRO",
            price="$50/月",
            requests_per_minute=60,
            requests_per_day=10000,
            max_leagues=999,
            max_seasons=999,
            historical_years=10,
            has_realtime=True,
            has_odds=True,
            has_lineups=True,
            has_statistics=True,
            has_player_data=True,
        ),
    ],

    data_types={
        "matches": DataTypeSupport(
            data_type="matches",
            data_type_cn="比赛数据",
            free_available=True,
            paid_available=True,
            quality_score=7,
            coverage=0.8,
            update_frequency="realtime",
            delay_seconds=120,
            fields=[
                DataField("id", "比赛ID", free_available=True),
                DataField("utcDate", "比赛时间(UTC)", free_available=True),
                DataField("status", "比赛状态", free_available=True, realtime=True),
                DataField("homeTeam", "主队", free_available=True),
                DataField("awayTeam", "客队", free_available=True),
                DataField("score", "比分", free_available=True, realtime=True),
                DataField("halfTime", "半场比分", free_available=True),
                DataField("matchday", "比赛日", free_available=True),
            ]
        ),
        "standings": DataTypeSupport(
            data_type="standings",
            data_type_cn="积分榜",
            free_available=True,
            paid_available=True,
            quality_score=7,
            coverage=0.8,
            fields=[
                DataField("position", "排名", free_available=True),
                DataField("team", "球队", free_available=True),
                DataField("playedGames", "已赛", free_available=True),
                DataField("won", "胜", free_available=True),
                DataField("draw", "平", free_available=True),
                DataField("lost", "负", free_available=True),
                DataField("goalsFor", "进球", free_available=True),
                DataField("goalsAgainst", "失球", free_available=True),
                DataField("goalDifference", "净胜球", free_available=True),
                DataField("points", "积分", free_available=True),
            ]
        ),
        "scorers": DataTypeSupport(
            data_type="scorers",
            data_type_cn="射手榜",
            free_available=True,
            paid_available=True,
            quality_score=7,
            coverage=0.75,
            fields=[
                DataField("player", "球员", free_available=True),
                DataField("team", "球队", free_available=True),
                DataField("goals", "进球数", free_available=True),
                DataField("assists", "助攻数", paid_available=True),
            ]
        ),
    },

    leagues=[
        LeagueSupport(2021, "Premier League", "英超", "England", free_available=True),
        LeagueSupport(2014, "La Liga", "西甲", "Spain", free_available=True),
        LeagueSupport(2019, "Serie A", "意甲", "Italy", free_available=True),
        LeagueSupport(2002, "Bundesliga", "德甲", "Germany", free_available=True),
        LeagueSupport(2015, "Ligue 1", "法甲", "France", free_available=True),
        LeagueSupport(2003, "Eredivisie", "荷甲", "Netherlands", free_available=True),
        LeagueSupport(2017, "Primeira Liga", "葡超", "Portugal", free_available=True),
        LeagueSupport(2001, "UEFA Champions League", "欧冠", "Europe", free_available=True),
        LeagueSupport(2018, "UEFA Europa League", "欧联杯", "Europe", free_available=True),
        LeagueSupport(2007, "Championship", "英冠", "England", free_available=False, paid_available=True),
        LeagueSupport(2020, "Serie B", "意乙", "Italy", free_available=False, paid_available=True),
    ],
    free_leagues_count=12,
    paid_leagues_count=20,
    total_leagues=20,
    total_countries=12,
    description="欧洲足球数据API，主要覆盖欧洲主流联赛",
    notes="免费版限制较多，适合欧洲联赛"
)


# ==================== 爬虫数据源配置 ====================

DONGQIUDI_CONFIG = DataSourceConfig(
    id="dongqiudi_scraper",
    name="懂球帝",
    name_cn="懂球帝爬虫",
    type=DataSourceType.SCRAPER,
    base_url="https://www.dongqiudi.com",
    enabled=True,
    priority=2,

    tiers=[
        TierLimit(
            tier_name="FREE",
            price="$0/月",
            requests_per_minute=30,
            requests_per_day=500,
            max_leagues=999,
            has_realtime=True,
            has_odds=False,
            has_lineups=True,
            has_statistics=False,
            has_player_data=True,
            notes="爬虫免费，但需要处理反爬"
        ),
    ],

    data_types={
        "matches": DataTypeSupport(
            data_type="matches",
            data_type_cn="比赛数据",
            free_available=True,
            quality_score=7,
            coverage=0.85,
            update_frequency="realtime",
            delay_seconds=60,
            fields=[
                DataField("match_id", "比赛ID", free_available=True),
                DataField("date", "日期", free_available=True),
                DataField("time", "时间", free_available=True),
                DataField("home_team", "主队", free_available=True),
                DataField("away_team", "客队", free_available=True),
                DataField("home_score", "主队比分", free_available=True, realtime=True),
                DataField("away_score", "客队比分", free_available=True, realtime=True),
                DataField("half_score", "半场比分", free_available=True),
                DataField("league", "联赛", free_available=True),
            ]
        ),
        "news": DataTypeSupport(
            data_type="news",
            data_type_cn="新闻资讯",
            free_available=True,
            quality_score=8,
            coverage=0.9,
            update_frequency="realtime",
            fields=[
                DataField("title", "标题", free_available=True),
                DataField("content", "内容", free_available=True),
                DataField("author", "作者", free_available=True),
                DataField("publish_time", "发布时间", free_available=True),
                DataField("source", "来源", free_available=True),
            ],
            notes="中文足球新闻最全"
        ),
        "team_chinese": DataTypeSupport(
            data_type="team_chinese",
            data_type_cn="球队中文名",
            free_available=True,
            quality_score=9,
            coverage=0.95,
            fields=[
                DataField("name_cn", "中文名", free_available=True),
                DataField("name_en", "英文名", free_available=True),
                DataField("abbreviation", "简称", free_available=True),
            ],
            notes="球队中文名最全"
        ),
        "player_chinese": DataTypeSupport(
            data_type="player_chinese",
            data_type_cn="球员中文名",
            free_available=True,
            quality_score=8,
            coverage=0.85,
            fields=[
                DataField("name_cn", "中文名", free_available=True),
                DataField("name_en", "英文名", free_available=True),
                DataField("position", "位置", free_available=True),
            ]
        ),
        "lineups": DataTypeSupport(
            data_type="lineups",
            data_type_cn="阵容",
            free_available=True,
            quality_score=7,
            coverage=0.7,
            fields=[
                DataField("formation", "阵型", free_available=True),
                DataField("startXI", "首发", free_available=True),
                DataField("substitutes", "替补", free_available=True),
            ]
        ),
    },

    leagues=[
        LeagueSupport(1, "中超", "中超", "中国", free_available=True),
        LeagueSupport(2, "英超", "英超", "England", free_available=True),
        LeagueSupport(3, "西甲", "西甲", "Spain", free_available=True),
        LeagueSupport(4, "意甲", "意甲", "Italy", free_available=True),
        LeagueSupport(5, "德甲", "德甲", "Germany", free_available=True),
        LeagueSupport(6, "法甲", "法甲", "France", free_available=True),
        LeagueSupport(7, "欧冠", "欧冠", "Europe", free_available=True),
        LeagueSupport(8, "欧联杯", "欧联杯", "Europe", free_available=True),
        LeagueSupport(9, "亚冠", "亚冠", "Asia", free_available=True),
        LeagueSupport(10, "J联赛", "J联赛", "Japan", free_available=True),
        LeagueSupport(11, "K联赛", "K联赛", "South Korea", free_available=True),
        LeagueSupport(12, "沙特联", "沙特联", "Saudi Arabia", free_available=True),
        LeagueSupport(13, "世界杯", "世界杯", "World", free_available=True),
        LeagueSupport(14, "欧洲杯", "欧洲杯", "Europe", free_available=True),
        LeagueSupport(15, "亚洲杯", "亚洲杯", "Asia", free_available=True),
    ],
    free_leagues_count=50,
    paid_leagues_count=50,
    total_leagues=50,
    total_countries=30,
    description="懂球帝网站爬虫，中文内容最全",
    notes="需要处理反爬机制，建议使用代理"
)


# Transfermarkt 配置
TRANSFERMARKT_CONFIG = DataSourceConfig(
    id="transfermarkt_scraper",
    name="Transfermarkt",
    name_cn="德国转会市场",
    type=DataSourceType.SCRAPER,
    base_url="https://www.transfermarkt.com",
    enabled=True,
    priority=4,

    tiers=[
        TierLimit(
            tier_name="FREE",
            price="$0/月",
            requests_per_minute=15,
            requests_per_day=200,
            max_leagues=999,
            has_realtime=False,
            has_odds=False,
            has_lineups=False,
            has_statistics=False,
            has_player_data=True,
            notes="爬虫免费，反爬较严格"
        ),
    ],

    data_types={
        "player_value": DataTypeSupport(
            data_type="player_value",
            data_type_cn="球员身价",
            free_available=True,
            quality_score=9,
            coverage=0.9,
            update_frequency="monthly",
            fields=[
                DataField("market_value", "市值", free_available=True),
                DataField("market_value_history", "市值历史", free_available=True),
                DataField("highest_value", "最高市值", free_available=True),
            ],
            notes="球员身价最权威来源"
        ),
        "transfers": DataTypeSupport(
            data_type="transfers",
            data_type_cn="转会数据",
            free_available=True,
            quality_score=9,
            coverage=0.9,
            fields=[
                DataField("player", "球员", free_available=True),
                DataField("from_club", "转出俱乐部", free_available=True),
                DataField("to_club", "转入俱乐部", free_available=True),
                DataField("fee", "转会费", free_available=True),
                DataField("date", "日期", free_available=True),
                DataField("type", "类型", free_available=True),
            ]
        ),
        "team_squad": DataTypeSupport(
            data_type="team_squad",
            data_type_cn="球队阵容",
            free_available=True,
            quality_score=8,
            coverage=0.85,
            fields=[
                DataField("players", "球员列表", free_available=True),
                DataField("positions", "位置", free_available=True),
                DataField("ages", "年龄", free_available=True),
                DataField("nationalities", "国籍", free_available=True),
                DataField("market_values", "市值", free_available=True),
            ]
        ),
        "contracts": DataTypeSupport(
            data_type="contracts",
            data_type_cn="合同信息",
            free_available=True,
            quality_score=7,
            coverage=0.7,
            fields=[
                DataField("player", "球员", free_available=True),
                DataField("expires", "到期时间", free_available=True),
                DataField("option", "续约选项", free_available=True),
            ]
        ),
    },

    leagues=[
        LeagueSupport(1, "Premier League", "英超", "England", free_available=True),
        LeagueSupport(2, "La Liga", "西甲", "Spain", free_available=True),
        LeagueSupport(3, "Serie A", "意甲", "Italy", free_available=True),
        LeagueSupport(4, "Bundesliga", "德甲", "Germany", free_available=True),
        LeagueSupport(5, "Ligue 1", "法甲", "France", free_available=True),
        LeagueSupport(6, "Eredivisie", "荷甲", "Netherlands", free_available=True),
        LeagueSupport(7, "Primeira Liga", "葡超", "Portugal", free_available=True),
        LeagueSupport(8, "中超", "中超", "China", free_available=True),
        LeagueSupport(9, "J1 League", "J联赛", "Japan", free_available=True),
        LeagueSupport(10, "K League 1", "K联赛", "South Korea", free_available=True),
    ],
    free_leagues_count=100,
    paid_leagues_count=100,
    total_leagues=100,
    total_countries=50,
    description="德国转会市场，球员身价和转会数据最权威",
    notes="反爬较严格，建议低频访问"
)


# 联赛官网爬虫配置
LEAGUE_OFFICIAL_CONFIG = DataSourceConfig(
    id="league_official_scraper",
    name="联赛官网",
    name_cn="联赛官网爬虫",
    type=DataSourceType.SCRAPER,
    enabled=True,
    priority=3,

    tiers=[
        TierLimit(
            tier_name="FREE",
            price="$0/月",
            requests_per_minute=20,
            requests_per_day=300,
            max_leagues=10,
            has_realtime=True,
            has_odds=False,
            has_lineups=True,
            has_statistics=True,
            has_player_data=True,
            notes="每个联赛需要单独适配"
        ),
    ],

    data_types={
        "league_rules": DataTypeSupport(
            data_type="league_rules",
            data_type_cn="联赛规则",
            free_available=True,
            quality_score=10,
            coverage=0.95,
            fields=[
                DataField("promotion_spots", "升级名额", free_available=True),
                DataField("relegation_spots", "降级名额", free_available=True),
                DataField("playoff_format", "季后赛格式", free_available=True),
                DataField("foreign_player_limit", "外援限制", free_available=True),
                DataField("substitute_rules", "换人规则", free_available=True),
                DataField("var_usage", "VAR使用", free_available=True),
            ],
            notes="联赛规则最权威来源"
        ),
        "standings": DataTypeSupport(
            data_type="standings",
            data_type_cn="积分榜",
            free_available=True,
            quality_score=10,
            coverage=1.0,
            update_frequency="realtime",
            fields=[
                DataField("rank", "排名", free_available=True),
                DataField("team", "球队", free_available=True),
                DataField("played", "已赛", free_available=True),
                DataField("won", "胜", free_available=True),
                DataField("draw", "平", free_available=True),
                DataField("lost", "负", free_available=True),
                DataField("gf", "进球", free_available=True),
                DataField("ga", "失球", free_available=True),
                DataField("gd", "净胜球", free_available=True),
                DataField("points", "积分", free_available=True),
            ]
        ),
        "schedule": DataTypeSupport(
            data_type="schedule",
            data_type_cn="赛程",
            free_available=True,
            quality_score=9,
            coverage=0.95,
            fields=[
                DataField("match_id", "比赛ID", free_available=True),
                DataField("date", "日期", free_available=True),
                DataField("time", "时间", free_available=True),
                DataField("home", "主队", free_available=True),
                DataField("away", "客队", free_available=True),
                DataField("venue", "球场", free_available=True),
            ]
        ),
    },

    leagues=[
        LeagueSupport(1, "Premier League", "英超", "England", free_available=True,
                      notes="官网: premierleague.com"),
        LeagueSupport(2, "La Liga", "西甲", "Spain", free_available=True,
                      notes="官网: laliga.com"),
        LeagueSupport(3, "Serie A", "意甲", "Italy", free_available=True,
                      notes="官网: seriea.com"),
        LeagueSupport(4, "Bundesliga", "德甲", "Germany", free_available=True,
                      notes="官网: bundesliga.com"),
        LeagueSupport(5, "Ligue 1", "法甲", "France", free_available=True,
                      notes="官网: ligue1.com"),
        LeagueSupport(6, "中超", "中超", "China", free_available=True,
                      notes="官网: csl-league.com"),
    ],
    free_leagues_count=10,
    paid_leagues_count=10,
    total_leagues=10,
    total_countries=10,
    description="各联赛官网爬虫，数据最权威",
    notes="每个联赛需要单独适配解析逻辑"
)


# LLM 智能检索配置
LLM_SEARCH_CONFIG = DataSourceConfig(
    id="llm_search",
    name="LLM智能检索",
    name_cn="LLM智能检索",
    type=DataSourceType.LLM,
    enabled=False,
    priority=10,

    tiers=[
        TierLimit(
            tier_name="PAY_PER_USE",
            price="按使用付费",
            requests_per_minute=10,
            requests_per_day=100,
            max_leagues=999,
            has_realtime=False,
            notes="成本较高，作为最后备选"
        ),
    ],

    data_types={
        "general_info": DataTypeSupport(
            data_type="general_info",
            data_type_cn="通用信息",
            free_available=False,
            paid_available=True,
            quality_score=6,
            coverage=0.7,
            fields=[
                DataField("description", "描述", paid_available=True),
                DataField("history", "历史", paid_available=True),
                DataField("facts", "事实", paid_available=True),
            ]
        ),
        "translation": DataTypeSupport(
            data_type="translation",
            data_type_cn="翻译",
            free_available=False,
            paid_available=True,
            quality_score=7,
            coverage=0.8,
            fields=[
                DataField("chinese_name", "中文名", paid_available=True),
                DataField("description", "描述", paid_available=True),
            ]
        ),
    },

    leagues=[],
    free_leagues_count=0,
    paid_leagues_count=999,
    total_leagues=0,
    total_countries=0,
    description="LLM模型智能检索，作为最后备选",
    notes="当所有API和爬虫都无法获取时使用"
)


# ==================== 数据源注册表 ====================

DATA_SOURCES: Dict[str, DataSourceConfig] = {
    "api_sports": API_SPORTS_CONFIG,
    "thesportsdb": THE_SPORTS_DB_CONFIG,
    "football_data": FOOTBALL_DATA_CONFIG,
    "dongqiudi_scraper": DONGQIUDI_CONFIG,
    "transfermarkt_scraper": TRANSFERMARKT_CONFIG,
    "league_official_scraper": LEAGUE_OFFICIAL_CONFIG,
    "llm_search": LLM_SEARCH_CONFIG,
}


# ==================== 任务类型到数据源优先级映射 ====================

TASK_SOURCE_PRIORITY: Dict[str, List[str]] = {
    "matches": ["api_sports", "dongqiudi_scraper", "thesportsdb"],
    "match_score": ["api_sports", "dongqiudi_scraper"],
    "match_schedule": ["api_sports", "dongqiudi_scraper", "league_official_scraper"],
    "teams": ["api_sports", "thesportsdb", "dongqiudi_scraper"],
    "team_chinese_name": ["dongqiudi_scraper", "llm_search"],
    "team_squad": ["transfermarkt_scraper", "api_sports"],
    "team_value": ["transfermarkt_scraper"],
    "standings": ["api_sports", "league_official_scraper", "dongqiudi_scraper"],
    "league_rules": ["league_official_scraper", "dongqiudi_scraper", "llm_search"],
    "league_info": ["api_sports", "thesportsdb", "dongqiudi_scraper"],
    "players": ["api_sports", "transfermarkt_scraper"],
    "player_value": ["transfermarkt_scraper"],
    "player_chinese_name": ["dongqiudi_scraper", "llm_search"],
    "news": ["dongqiudi_scraper"],
    "statistics": ["api_sports", "league_official_scraper"],
    "lineups": ["api_sports", "dongqiudi_scraper"],
    "events": ["api_sports", "dongqiudi_scraper"],
    "transfers": ["transfermarkt_scraper"],
    "odds": ["api_sports"],
    "injuries": ["api_sports"],
    "predictions": ["api_sports"],
}


def get_source_config(source_id: str) -> Optional[DataSourceConfig]:
    """获取数据源配置"""
    return DATA_SOURCES.get(source_id)


def get_sources_for_task(task_type: str) -> List[DataSourceConfig]:
    """获取任务类型对应的数据源列表"""
    source_ids = TASK_SOURCE_PRIORITY.get(task_type, [])
    sources = []
    for sid in source_ids:
        config = DATA_SOURCES.get(sid)
        if config and config.enabled:
            sources.append(config)
    return sources


def get_best_source(task_type: str) -> Optional[DataSourceConfig]:
    """获取任务类型的最佳数据源"""
    sources = get_sources_for_task(task_type)
    return sources[0] if sources else None


def check_rate_limit(source_id: str) -> bool:
    """检查是否超过速率限制"""
    config = DATA_SOURCES.get(source_id)
    if not config or not config.tiers:
        return False
    tier = config.tiers[0]  # 使用第一个套餐的限制
    return tier.requests_per_day > 0


def update_usage(source_id: str, increment: int = 1):
    """更新使用量"""
    pass  # 实际使用中需要持久化


def get_league_support(source_id: str, league_id: int) -> Optional[LeagueSupport]:
    """获取数据源对特定联赛的支持情况"""
    config = DATA_SOURCES.get(source_id)
    if not config:
        return None
    for league in config.leagues:
        if league.league_id == league_id:
            return league
    return None


def get_sources_for_league(league_id: int) -> List[Dict[str, Any]]:
    """获取支持特定联赛的所有数据源"""
    result = []
    for source_id, config in DATA_SOURCES.items():
        for league in config.leagues:
            if league.league_id == league_id:
                result.append({
                    "source_id": source_id,
                    "source_name": config.name,
                    "priority": config.priority,
                    "coverage": league.coverage,
                    "free_available": league.free_available,
                    "paid_available": league.paid_available,
                })
                break
    result.sort(key=lambda x: x["priority"])
    return result


def get_all_supported_leagues() -> Dict[str, List[Dict]]:
    """获取所有支持的联赛列表"""
    result = {}
    for source_id, config in DATA_SOURCES.items():
        result[source_id] = [
            {
                "league_id": league.league_id,
                "league_name": league.league_name,
                "league_name_cn": league.league_name_cn,
                "country": league.country,
                "free_available": league.free_available,
                "paid_available": league.paid_available,
            }
            for league in config.leagues
        ]
    return result


def get_data_type_support(source_id: str, data_type: str) -> Optional[DataTypeSupport]:
    """获取数据源对特定数据类型的支持情况"""
    config = DATA_SOURCES.get(source_id)
    if not config:
        return None
    return config.data_types.get(data_type)


def get_available_fields(source_id: str, data_type: str, is_free: bool = True) -> List[str]:
    """获取可用的数据字段"""
    support = get_data_type_support(source_id, data_type)
    if not support:
        return []
    fields = []
    for field in support.fields:
        if is_free and field.free_available:
            fields.append(field.field_name)
        elif not is_free and field.paid_available:
            fields.append(field.field_name)
    return fields
