"""
采集编排器 — 调fetcher → 经adapter → 存storage

核心流程:
1. 调用fetcher获取原始数据
2. 经adapter翻译成统一格式
3. 存入unified_storage（自动去重合并）

设计原则:
- 不修改fetcher代码
- 失败的源不影响其他源
- 每次采集记录日志
"""

import logging
from datetime import date as _date, datetime
from typing import Any, Callable, Dict, List, Optional

from fetchers.adapter.adapter import adapt
from fetchers.adapter.field_map import get_data_type
from fetchers.storage.crud import UnifiedStorage
from fetchers.storage.database import init_database

logger = logging.getLogger(__name__)


class DataCollector:
    """数据采集编排器"""

    def __init__(self, db_path: str = None):
        init_database(db_path)
        self.storage = UnifiedStorage(db_path)
        self._fetcher_cache = {}

    def _get_fetcher_func(self, fetcher_name: str, func_name: str) -> Optional[Callable]:
        """动态导入fetcher函数"""
        cache_key = f"{fetcher_name}.{func_name}"
        if cache_key in self._fetcher_cache:
            return self._fetcher_cache[cache_key]

        try:
            # 根据fetcher名称构建导入路径
            module_map = {
                "apifootball": "fetchers.apifootball.get_data",
                "football_data_org": "fetchers.football_data_org.get_data",
                "espn": "fetchers.espn.get_scores",
                "soccerway": "fetchers.soccerway.get_matches",
                "scores365": "fetchers.scores365.get_scores",
                "flashlive": "fetchers.flashlive.get_scores",
                "sofascore": "fetchers.sofascore.get_data",
                "thesportsdb": "fetchers.thesportsdb.get_data",
                "openligadb": "fetchers.openligadb.get_data",
                "api_sports": "fetchers.api_sports.get_data",
                "fbref": "fetchers.fbref.get_data",
                "okooo": "fetchers.okooo.get_odds",
                "the_odds_api": "fetchers.the_odds_api.get_odds",
                "odds_api": "fetchers.odds_api.get_odds",
                "sporttery": "fetchers.sporttery.get_matches",
                "understat": "fetchers.understat.get_xg",
                "statsbomb": "fetchers.statsbomb.get_xg",
                "sportmonks": "fetchers.sportmonks.get_data",
                "bifen188": "fetchers.bifen188.get_lineups",
                "premierleague": "fetchers.premierleague.get_data",
                "dongqiudi": "fetchers.dongqiudi.get_news",
                "hupu": "fetchers.hupu.get_news",
                "zhibo8": "fetchers.zhibo8.get_news",
                "scorebat": "fetchers.scorebat.get_highlights",
                "weather": "fetchers.weather.get_weather",
                "openweathermap": "fetchers.openweathermap.get_weather",
                "transfermarkt": "fetchers.transfermarkt.get_data",
            }

            module_path = module_map.get(fetcher_name)
            if not module_path:
                logger.warning(f"未知fetcher: {fetcher_name}")
                return None

            import importlib
            module = importlib.import_module(module_path)
            func = getattr(module, func_name, None)
            if func is None:
                logger.warning(f"函数不存在: {module_path}.{func_name}")
                return None

            self._fetcher_cache[cache_key] = func
            return func
        except Exception as e:
            logger.error(f"导入失败: {fetcher_name}.{func_name}: {e}")
            return None

    def fetch_and_store(self, fetcher_name: str, func_name: str,
                         **kwargs) -> int:
        """采集单个源的数据并存储

        Returns:
            存储的记录数
        """
        data_type = get_data_type(fetcher_name, func_name)
        started_at = datetime.now().isoformat()

        try:
            func = self._get_fetcher_func(fetcher_name, func_name)
            if not func:
                self.storage.log_fetch(fetcher_name, func_name, data_type,
                                        "error", 0, "函数不可用", started_at)
                return 0

            # 调用fetcher获取原始数据
            raw_data = func(**kwargs) if kwargs else func()

            # 适配为统一格式
            adapted = adapt(fetcher_name, func_name, raw_data)
            if not adapted:
                self.storage.log_fetch(fetcher_name, func_name, data_type,
                                        "empty", 0, None, started_at)
                return 0

            # 存入数据库
            count = self.storage.upsert_match_data(adapted)
            self.storage.log_fetch(fetcher_name, func_name, data_type,
                                    "success", count, None, started_at)
            return count

        except Exception as e:
            logger.error(f"采集失败: {fetcher_name}.{func_name}: {e}")
            self.storage.log_fetch(fetcher_name, func_name, data_type,
                                    "error", 0, str(e)[:200], started_at)
            return 0

    def collect_todays_matches(self) -> Dict[str, int]:
        """采集今日比赛数据（多源并行）

        Returns:
            {fetcher_name: record_count}
        """
        today = str(_date.today())
        results = {}

        # 主要比赛源
        match_sources = [
            ("apifootball", "get_livescores"),
            ("espn", "get_livescores"),
            ("scores365", "get_livescores"),
            ("flashlive", "get_livescores"),
            ("sofascore", "get_livescores"),
        ]

        for fetcher_name, func_name in match_sources:
            count = self.fetch_and_store(fetcher_name, func_name)
            results[fetcher_name] = count
            logger.info(f"[{fetcher_name}] 存储 {count} 条")

        return results

    def collect_fixtures(self, from_date: str = None, to_date: str = None,
                          league: str = None) -> Dict[str, int]:
        """采集赛程数据"""
        results = {}

        fixture_sources = [
            ("apifootball", "get_fixtures"),
            ("football_data_org", "get_matches"),
            ("openligadb", "get_matches"),
            ("api_sports", "get_fixtures"),
        ]

        for fetcher_name, func_name in fixture_sources:
            kwargs = {}
            if from_date:
                kwargs["from_date"] = from_date
            if to_date:
                kwargs["to_date"] = to_date
            if league:
                kwargs["league"] = league

            count = self.fetch_and_store(fetcher_name, func_name, **kwargs)
            results[fetcher_name] = count

        return results

    def collect_odds_for_match(self, match_key: str) -> Dict[str, int]:
        """为特定比赛采集赔率"""
        results = {}

        # 从match_key解析date+home+away
        parts = match_key.split("|")
        if len(parts) != 3:
            logger.warning(f"无效match_key: {match_key}")
            return results

        date_str, home_team, away_team = parts

        odds_sources = [
            ("apifootball", "get_match_odds"),
            ("odds_api", "get_odds_feed"),
        ]

        for fetcher_name, func_name in odds_sources:
            count = self.fetch_and_store(fetcher_name, func_name)
            results[fetcher_name] = count

        return results

    def collect_match_context(self, match_key: str) -> Dict[str, int]:
        """为特定比赛采集上下文（xG/天气/伤病）"""
        results = {}

        parts = match_key.split("|")
        if len(parts) != 3:
            return results

        date_str, home_team, away_team = parts

        # xG数据
        xg_sources = [
            ("understat", "get_match_xg"),
            ("statsbomb", "get_match_xg"),
        ]
        for fetcher_name, func_name in xg_sources:
            count = self.fetch_and_store(fetcher_name, func_name)
            results[fetcher_name] = count

        # 天气
        weather_count = self.fetch_and_store("weather", "get_match_weather",
                                              city=home_team, date=date_str)
        results["weather"] = weather_count

        # 伤病
        injury_sources = [
            ("premierleague", "get_injuries"),
        ]
        for fetcher_name, func_name in injury_sources:
            count = self.fetch_and_store(fetcher_name, func_name)
            results[fetcher_name] = count

        return results

    def collect_standings(self, league: str, season: str = None) -> Dict[str, int]:
        """采集积分榜"""
        results = {}

        standing_sources = [
            ("apifootball", "get_standings"),
            ("fbref", "get_league_standings"),
        ]

        for fetcher_name, func_name in standing_sources:
            kwargs = {"league": league}
            if season:
                kwargs["season"] = season
            count = self.fetch_and_store(fetcher_name, func_name, **kwargs)
            results[fetcher_name] = count

        return results

    def collect_news(self) -> Dict[str, int]:
        """采集新闻"""
        results = {}

        news_sources = [
            ("dongqiudi", "get_news"),
            ("hupu", "get_news"),
        ]

        for fetcher_name, func_name in news_sources:
            count = self.fetch_and_store(fetcher_name, func_name)
            results[fetcher_name] = count

        return results

    def full_collect(self, date: str = None, league: str = None) -> Dict[str, int]:
        """全量采集（比赛+赔率+xG+新闻）"""
        results = {}

        # 1. 比赛数据
        if date:
            results.update(self.collect_fixtures(from_date=date, to_date=date, league=league))
        else:
            results.update(self.collect_todays_matches())

        # 2. 积分榜
        if league:
            results.update(self.collect_standings(league))

        # 3. 新闻
        results.update(self.collect_news())

        # 4. 对每场比赛补充上下文
        matches = self.storage.get_matches_by_date(date or str(_date.today()))
        for match in matches[:20]:
            match_key = match["match_key"]
            context = self.collect_match_context(match_key)
            for k, v in context.items():
                results[f"{k}_{match_key[:10]}"] = v

        return results