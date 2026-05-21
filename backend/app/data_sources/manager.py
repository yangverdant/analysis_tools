"""
数据源管理器 - 统一管理所有数据源
支持多数据源切换、优先级排序、自动fallback
"""

import json
from pathlib import Path
from typing import Dict, List, Optional, Any, Type
from datetime import datetime

from .base import (
    BaseDataSource, DataSourceConfig, DataSourceType, DataCategory,
    MatchData, StandingData, TeamData, PlayerData
)
from .api_sources import (
    SportmonksAPI, FootballDataOrgAPI, TheSportsDBAPI,
    ScoreBatAPI, Scores365API, OpenLigaDBAPI
)
from .scraper_sources import (
    FBrefScraper, FlashScoreScraper, SoccerwayScraper,
    ESPNScraper, UnderstatScraper, TransfermarktScraper
)
from .local_sources import LocalCSVSource, DatabaseSource, StatsBombSource


class DataSourceManager:
    """数据源管理器"""

    # 数据源类映射
    SOURCE_CLASSES: Dict[str, Type[BaseDataSource]] = {
        # API类
        "sportmonks": SportmonksAPI,
        "football_data_org": FootballDataOrgAPI,
        "thesportsdb": TheSportsDBAPI,
        "scorebat": ScoreBatAPI,
        "365scores": Scores365API,
        "openligadb": OpenLigaDBAPI,
        # 爬虫类
        "fbref": FBrefScraper,
        "flashscore": FlashScoreScraper,
        "soccerway": SoccerwayScraper,
        "espn": ESPNScraper,
        "understat": UnderstatScraper,
        "transfermarkt": TransfermarktScraper,
        # 本地类
        "local_csv": LocalCSVSource,
        "database": DatabaseSource,
        "statsbomb": StatsBombSource,
    }

    def __init__(self, config_path: Optional[str] = None):
        self.sources: Dict[str, BaseDataSource] = {}
        # 使用绝对路径
        if config_path:
            self.config_path = config_path
        else:
            # 获取项目根目录 (manager.py -> data_sources -> app -> backend -> project_root)
            project_root = Path(__file__).parent.parent.parent.parent
            self.config_path = str(project_root / "api_config.json")
        self._load_config()

    def _load_config(self):
        """加载配置文件"""
        config_file = Path(self.config_path)
        if config_file.exists():
            with open(config_file, 'r', encoding='utf-8') as f:
                config_data = json.load(f)

            # 加载API配置
            apis = config_data.get("apis", {})
            for name, api_config in apis.items():
                if name in self.SOURCE_CLASSES:
                    source_config = DataSourceConfig(
                        name=name,
                        source_type=DataSourceType.API if api_config.get("auth_type") else DataSourceType.SCRAPER,
                        base_url=api_config.get("base_url"),
                        api_key=api_config.get("api_token") or api_config.get("api_key"),
                        auth_type=api_config.get("auth_type"),
                        rate_limit=api_config.get("rate_limit", {}).get("requests_per_minute"),
                        request_interval=api_config.get("request_interval_seconds", 1.0),
                        enabled=api_config.get("status") == "active",
                        priority=api_config.get("priority", 10),
                        capabilities=[DataCategory(c) for c in api_config.get("capabilities", []) if c in [e.value for e in DataCategory]],
                        leagues=api_config.get("leagues", {}) if isinstance(api_config.get("leagues"), dict) else {}
                    )
                    self.sources[name] = self.SOURCE_CLASSES[name](source_config)

        # 添加本地数据源
        self._add_local_sources()

    def _add_local_sources(self):
        """添加本地数据源"""
        # CSV数据源
        csv_config = DataSourceConfig(
            name="local_csv",
            source_type=DataSourceType.LOCAL,
            base_url="data",
            enabled=True,
            priority=1,
            capabilities=[DataCategory.MATCHES, DataCategory.STANDINGS, DataCategory.FIXTURES]
        )
        self.sources["local_csv"] = LocalCSVSource(csv_config)

        # 数据库数据源
        db_config = DataSourceConfig(
            name="database",
            source_type=DataSourceType.LOCAL,
            base_url="data/football_unified.db",
            enabled=True,
            priority=2,
            capabilities=[DataCategory.MATCHES, DataCategory.STANDINGS, DataCategory.TEAMS, DataCategory.PLAYERS, DataCategory.SCORERS]
        )
        self.sources["database"] = DatabaseSource(db_config)

        # StatsBomb数据源
        statsbomb_config = DataSourceConfig(
            name="statsbomb",
            source_type=DataSourceType.LOCAL,
            base_url="new_data/matches",
            enabled=True,
            priority=3,
            capabilities=[DataCategory.MATCHES, DataCategory.STATISTICS, DataCategory.XG]
        )
        self.sources["statsbomb"] = StatsBombSource(statsbomb_config)

    def get_source(self, name: str) -> Optional[BaseDataSource]:
        """获取指定数据源"""
        return self.sources.get(name)

    def get_sources_by_category(self, category: DataCategory) -> List[BaseDataSource]:
        """获取支持某类数据的所有数据源"""
        sources = [s for s in self.sources.values() if s.supports(category) and s.config.enabled]
        return sorted(sources, key=lambda s: s.config.priority)

    def get_best_source(self, category: DataCategory) -> Optional[BaseDataSource]:
        """获取某类数据的最佳数据源"""
        sources = self.get_sources_by_category(category)
        return sources[0] if sources else None

    async def get_livescores(
        self,
        leagues: Optional[List[str]] = None,
        date: Optional[str] = None,
        sources: Optional[List[str]] = None
    ) -> Dict[str, List[MatchData]]:
        """获取实时比分 - 支持多数据源"""
        result = {}

        if sources:
            # 使用指定的数据源
            for source_name in sources:
                source = self.get_source(source_name)
                if source and source.supports(DataCategory.LIVESCORES):
                    try:
                        matches = await source.get_livescores(leagues, date)
                        result[source_name] = matches
                    except Exception as e:
                        result[source_name] = []
                        print(f"{source_name} error: {e}")
        else:
            # 使用所有支持的数据源
            for source in self.get_sources_by_category(DataCategory.LIVESCORES):
                try:
                    matches = await source.get_livescores(leagues, date)
                    result[source.name] = matches
                except Exception as e:
                    result[source.name] = []
                    print(f"{source.name} error: {e}")

        return result

    async def get_livescores_merged(
        self,
        leagues: Optional[List[str]] = None,
        date: Optional[str] = None
    ) -> List[MatchData]:
        """获取实时比分 - 合并多数据源并去重"""
        all_matches = []
        seen = set()

        for source in self.get_sources_by_category(DataCategory.LIVESCORES):
            try:
                matches = await source.get_livescores(leagues, date)
                for m in matches:
                    key = (m.home_team, m.away_team, m.home_score, m.away_score)
                    if key not in seen:
                        seen.add(key)
                        all_matches.append(m)
            except Exception as e:
                print(f"{source.name} error: {e}")

        return all_matches

    async def get_fixtures(
        self,
        league: str,
        season: Optional[str] = None,
        team: Optional[str] = None,
        from_date: Optional[str] = None,
        to_date: Optional[str] = None,
        source_name: Optional[str] = None
    ) -> List[MatchData]:
        """获取赛程"""
        if source_name:
            source = self.get_source(source_name)
            if source:
                return await source.get_fixtures(league, season, team, from_date, to_date)

        # 尝试所有支持的数据源
        for source in self.get_sources_by_category(DataCategory.FIXTURES):
            try:
                matches = await source.get_fixtures(league, season, team, from_date, to_date)
                if matches:
                    return matches
            except Exception as e:
                print(f"{source.name} error: {e}")

        return []

    async def get_standings(
        self,
        league: str,
        season: Optional[str] = None,
        source_name: Optional[str] = None
    ) -> List[StandingData]:
        """获取积分榜"""
        if source_name:
            source = self.get_source(source_name)
            if source:
                return await source.get_standings(league, season)

        # 尝试所有支持的数据源
        for source in self.get_sources_by_category(DataCategory.STANDINGS):
            try:
                standings = await source.get_standings(league, season)
                if standings:
                    return standings
            except Exception as e:
                print(f"{source.name} error: {e}")

        return []

    async def get_matches(
        self,
        league: str,
        season: Optional[str] = None,
        team: Optional[str] = None,
        limit: Optional[int] = None,
        source_name: Optional[str] = None
    ) -> List[MatchData]:
        """获取历史比赛"""
        if source_name:
            source = self.get_source(source_name)
            if source:
                return await source.get_matches(league, season, team, limit)

        for source in self.get_sources_by_category(DataCategory.MATCHES):
            try:
                matches = await source.get_matches(league, season, team, limit)
                if matches:
                    return matches
            except Exception as e:
                print(f"{source.name} error: {e}")

        return []

    async def get_team(
        self,
        team_id: str,
        source_name: Optional[str] = None
    ) -> Optional[TeamData]:
        """获取球队信息"""
        if source_name:
            source = self.get_source(source_name)
            if source:
                return await source.get_team(team_id)

        for source in self.get_sources_by_category(DataCategory.TEAMS):
            try:
                team = await source.get_team(team_id)
                if team:
                    return team
            except Exception as e:
                print(f"{source.name} error: {e}")

        return None

    async def get_players(
        self,
        team: Optional[str] = None,
        league: Optional[str] = None,
        season: Optional[str] = None,
        source_name: Optional[str] = None
    ) -> List[PlayerData]:
        """获取球员信息"""
        if source_name:
            source = self.get_source(source_name)
            if source:
                return await source.get_players(team, league, season)

        for source in self.get_sources_by_category(DataCategory.PLAYERS):
            try:
                players = await source.get_players(team, league, season)
                if players:
                    return players
            except Exception as e:
                print(f"{source.name} error: {e}")

        return []

    async def get_scorers(
        self,
        league: str,
        season: Optional[str] = None,
        limit: Optional[int] = None,
        source_name: Optional[str] = None
    ) -> List[PlayerData]:
        """获取射手榜"""
        if source_name:
            source = self.get_source(source_name)
            if source:
                return await source.get_scorers(league, season, limit)

        for source in self.get_sources_by_category(DataCategory.SCORERS):
            try:
                scorers = await source.get_scorers(league, season, limit)
                if scorers:
                    return scorers
            except Exception as e:
                print(f"{source.name} error: {e}")

        return []

    def list_sources(self) -> List[Dict[str, Any]]:
        """列出所有数据源"""
        return [
            {
                "name": s.name,
                "type": s.source_type.value,
                "enabled": s.config.enabled,
                "priority": s.config.priority,
                "capabilities": [c.value for c in s.capabilities],
                "rate_limit": s.config.rate_limit,
            }
            for s in self.sources.values()
        ]

    def get_source_info(self, name: str) -> Optional[Dict[str, Any]]:
        """获取数据源详情"""
        source = self.get_source(name)
        if source:
            return {
                "name": source.name,
                "type": source.source_type.value,
                "enabled": source.config.enabled,
                "priority": source.config.priority,
                "capabilities": [c.value for c in source.capabilities],
                "base_url": source.config.base_url,
                "rate_limit": source.config.rate_limit,
                "request_interval": source.config.request_interval,
                "leagues": source.config.leagues,
            }
        return None

    async def test_source(self, name: str) -> Dict[str, Any]:
        """测试数据源连接"""
        source = self.get_source(name)
        if not source:
            return {"success": False, "error": "Source not found"}

        try:
            success = await source.test_connection()
            return {"success": success, "source": name}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def test_all_sources(self) -> Dict[str, Dict[str, Any]]:
        """测试所有数据源"""
        results = {}
        for name in self.sources:
            results[name] = await self.test_source(name)
        return results