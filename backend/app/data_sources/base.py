"""
数据源基类和枚举定义
"""

from abc import ABC, abstractmethod
from enum import Enum
from typing import Dict, List, Optional, Any
from datetime import datetime
from pydantic import BaseModel


class DataSourceType(str, Enum):
    """数据源类型"""
    API = "api"                    # 官方/第三方API
    SCRAPER = "scraper"            # 网页爬虫
    LOCAL = "local"                # 本地文件/数据库
    AI = "ai"                      # AI模型


class DataCategory(str, Enum):
    """数据类别"""
    LIVESCORES = "livescores"      # 实时比分
    FIXTURES = "fixtures"          # 赛程
    STANDINGS = "standings"        # 积分榜
    MATCHES = "matches"            # 历史比赛
    TEAMS = "teams"                # 球队信息
    PLAYERS = "players"            # 球员信息
    SCORERS = "scorers"            # 射手榜
    SQUADS = "squads"              # 阵容
    STATISTICS = "statistics"      # 统计数据
    XG = "xg"                      # 预期进球数据
    ODDS = "odds"                  # 赔率数据
    PREDICTIONS = "predictions"    # 预测数据
    ANALYSIS = "analysis"          # AI分析


class MatchData(BaseModel):
    """比赛数据模型"""
    match_id: Optional[str] = None
    home_team: str
    away_team: str
    home_score: Optional[int] = None
    away_score: Optional[int] = None
    home_score_ht: Optional[int] = None
    away_score_ht: Optional[int] = None
    date: Optional[str] = None
    time: Optional[str] = None
    status: Optional[str] = None
    league: Optional[str] = None
    league_id: Optional[str] = None
    season: Optional[str] = None
    round_num: Optional[int] = None
    venue: Optional[str] = None
    referee: Optional[str] = None
    attendance: Optional[int] = None
    events: Optional[List[Dict]] = None
    statistics: Optional[Dict] = None
    source: Optional[str] = None


class StandingData(BaseModel):
    """积分榜数据模型"""
    position: int
    team: str
    team_id: Optional[str] = None
    played: int
    won: int
    drawn: int
    lost: int
    goals_for: int
    goals_against: int
    goal_difference: int
    points: int
    form: Optional[str] = None
    league: Optional[str] = None
    season: Optional[str] = None
    source: Optional[str] = None


class TeamData(BaseModel):
    """球队数据模型"""
    team_id: Optional[str] = None
    name: str
    short_name: Optional[str] = None
    tla: Optional[str] = None
    country: Optional[str] = None
    founded: Optional[int] = None
    venue: Optional[str] = None
    capacity: Optional[int] = None
    logo_url: Optional[str] = None
    source: Optional[str] = None


class PlayerData(BaseModel):
    """球员数据模型"""
    player_id: Optional[str] = None
    name: str
    team: Optional[str] = None
    position: Optional[str] = None
    nationality: Optional[str] = None
    date_of_birth: Optional[str] = None
    height: Optional[int] = None
    weight: Optional[int] = None
    goals: Optional[int] = None
    assists: Optional[int] = None
    appearances: Optional[int] = None
    source: Optional[str] = None


class DataSourceConfig(BaseModel):
    """数据源配置"""
    name: str
    source_type: DataSourceType
    base_url: Optional[str] = None
    api_key: Optional[str] = None
    auth_type: Optional[str] = None
    rate_limit: Optional[int] = None
    request_interval: float = 1.0
    enabled: bool = True
    priority: int = 10
    capabilities: List[DataCategory] = []
    leagues: Dict[str, Any] = {}


class BaseDataSource(ABC):
    """数据源基类"""

    def __init__(self, config: DataSourceConfig):
        self.config = config
        self._last_request_time = 0.0

    @property
    def name(self) -> str:
        return self.config.name

    @property
    def source_type(self) -> DataSourceType:
        return self.config.source_type

    @property
    def capabilities(self) -> List[DataCategory]:
        return self.config.capabilities

    def supports(self, category: DataCategory) -> bool:
        """检查是否支持某类数据"""
        return category in self.capabilities

    @abstractmethod
    async def get_livescores(
        self,
        leagues: Optional[List[str]] = None,
        date: Optional[str] = None
    ) -> List[MatchData]:
        """获取实时比分"""
        pass

    @abstractmethod
    async def get_fixtures(
        self,
        league: str,
        season: Optional[str] = None,
        team: Optional[str] = None,
        from_date: Optional[str] = None,
        to_date: Optional[str] = None
    ) -> List[MatchData]:
        """获取赛程"""
        pass

    @abstractmethod
    async def get_standings(
        self,
        league: str,
        season: Optional[str] = None
    ) -> List[StandingData]:
        """获取积分榜"""
        pass

    @abstractmethod
    async def get_matches(
        self,
        league: str,
        season: Optional[str] = None,
        team: Optional[str] = None,
        limit: Optional[int] = None
    ) -> List[MatchData]:
        """获取历史比赛"""
        pass

    @abstractmethod
    async def get_team(
        self,
        team_id: str
    ) -> Optional[TeamData]:
        """获取球队信息"""
        pass

    @abstractmethod
    async def get_players(
        self,
        team: Optional[str] = None,
        league: Optional[str] = None,
        season: Optional[str] = None
    ) -> List[PlayerData]:
        """获取球员信息"""
        pass

    @abstractmethod
    async def get_scorers(
        self,
        league: str,
        season: Optional[str] = None,
        limit: Optional[int] = None
    ) -> List[PlayerData]:
        """获取射手榜"""
        pass

    async def test_connection(self) -> bool:
        """测试连接"""
        try:
            livescores = await self.get_livescores()
            return True
        except Exception:
            return False

    def _rate_limit(self):
        """请求限流"""
        import time
        elapsed = time.time() - self._last_request_time
        if elapsed < self.config.request_interval:
            time.sleep(self.config.request_interval - elapsed)
        self._last_request_time = time.time()
