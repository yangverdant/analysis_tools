"""
数据源管理器 - 统一管理所有数据源
支持多数据源切换、优先级排序、自动fallback
包含同步服务：未来比赛同步、实时事件同步、过期比赛修复
"""

import json
import asyncio
import sqlite3
import logging
from pathlib import Path
from typing import Dict, List, Optional, Any, Type
from datetime import datetime, timedelta

from .base import (
    BaseDataSource, DataSourceConfig, DataSourceType, DataCategory,
    MatchData, StandingData, TeamData, PlayerData
)
from .api_sources import (
    SportmonksAPI, FootballDataOrgAPI, TheSportsDBAPI,
    ScoreBatAPI, Scores365API, OpenLigaDBAPI
)
from .apifootball_source import APIFootballSource
from .odds_sources import OddsFeedAPI, Bet365API, FootballBettingOddsAPI
from .scraper_sources import (
    FBrefScraper, FlashScoreScraper, SoccerwayScraper,
    ESPNScraper, UnderstatScraper, TransfermarktScraper
)
from .local_sources import LocalCSVSource, DatabaseSource, StatsBombSource
from ..analytics.sofascore_crawler import SofascoreCrawler
from ..analytics.social_news import SocialMediaNewsAggregator

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class DataSourceManager:
    """数据源管理器"""

    # 数据源类映射
    SOURCE_CLASSES: Dict[str, Type[BaseDataSource]] = {
        # API类
        "sportmonks": SportmonksAPI,
        "football_data_org": FootballDataOrgAPI,
        "apifootball": APIFootballSource,
        "thesportsdb": TheSportsDBAPI,
        "scorebat": ScoreBatAPI,
        "365scores": Scores365API,
        "openligadb": OpenLigaDBAPI,
        # 赔率API (RapidAPI)
        "odds_feed": OddsFeedAPI,
        "bet365": Bet365API,
        "football_betting_odds": FootballBettingOddsAPI,
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
        config_data = {}
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

        # 加载RapidAPI配置（赔率API）
        self._load_rapidapi_config(config_data)

        # 添加本地数据源
        self._add_local_sources()

    def _load_rapidapi_config(self, config_data: dict):
        """加载RapidAPI配置"""
        rapidapi = config_data.get("rapidapi", {})
        api_key = rapidapi.get("key")

        if not api_key:
            return

        apis = rapidapi.get("apis", {})
        for name, api_config in apis.items():
            if name in self.SOURCE_CLASSES and api_config.get("status") == "active":
                source_config = DataSourceConfig(
                    name=name,
                    source_type=DataSourceType.API,
                    base_url=api_config.get("base_url"),
                    api_key=api_key,
                    enabled=True,
                    priority=15,
                    capabilities=[DataCategory.ODDS]
                )
                self.sources[name] = self.SOURCE_CLASSES[name](source_config)
                logger.info(f"Loaded RapidAPI source: {name}")

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

    # ==================== 同步服务功能 ====================

    # 主要联赛ID配置
    SYNC_LEAGUES = {
        '152': 'Premier League',
        '302': 'La Liga',
        '207': 'Bundesliga',
        '168': 'Serie A',
        '153': 'Ligue 1',
        '3': 'Champions League',
    }

    async def sync_future_matches(self, db_path: str, days: int = 7) -> Dict:
        """同步未来比赛数据（时间、状态）"""
        logger.info("Syncing future matches...")

        source = self.get_source('apifootball')
        if not source:
            return {'error': 'apifootball source not found'}

        results = {'synced': 0, 'updated': 0, 'added': 0, 'errors': []}

        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        today = datetime.now().strftime('%Y-%m-%d')
        future = (datetime.now() + timedelta(days=days)).strftime('%Y-%m-%d')

        for league_id, league_name in self.SYNC_LEAGUES.items():
            try:
                fixtures = await source.get_fixtures(
                    league_id=league_id,
                    from_date=today,
                    to_date=future
                )

                if not fixtures:
                    continue

                for f in fixtures:
                    # 查找球队ID
                    cursor.execute('''
                        SELECT team_id FROM teams
                        WHERE name_en LIKE ? OR name_cn LIKE ? OR short_name LIKE ?
                        LIMIT 1
                    ''', (f'%{f.home_team}%', f'%{f.home_team}%', f'%{f.home_team}%'))
                    home_row = cursor.fetchone()

                    cursor.execute('''
                        SELECT team_id FROM teams
                        WHERE name_en LIKE ? OR name_cn LIKE ? OR short_name LIKE ?
                        LIMIT 1
                    ''', (f'%{f.away_team}%', f'%{f.away_team}%', f'%{f.away_team}%'))
                    away_row = cursor.fetchone()

                    if not home_row or not away_row:
                        continue

                    home_id, away_id = home_row[0], away_row[0]

                    cursor.execute('''
                        SELECT match_id FROM matches
                        WHERE match_date = ? AND home_team_id = ? AND away_team_id = ?
                    ''', (f.date, home_id, away_id))

                    existing = cursor.fetchone()

                    if existing:
                        cursor.execute('''
                            UPDATE matches SET
                                match_time = ?,
                                status = ?,
                                source = 'apifootball'
                            WHERE match_id = ?
                        ''', (f.time, f.status or 'scheduled', existing[0]))
                        results['updated'] += 1
                    else:
                        cursor.execute('''
                            INSERT INTO matches (
                                match_date, match_time, home_team_id, away_team_id,
                                status, league_id, source
                            ) VALUES (?, ?, ?, ?, ?, ?, ?)
                        ''', (f.date, f.time, home_id, away_id, f.status or 'scheduled',
                              int(league_id), 'apifootball'))
                        results['added'] += 1

                    results['synced'] += 1

                conn.commit()

            except Exception as e:
                results['errors'].append(f"{league_name}: {str(e)}")
                logger.error(f"Error syncing {league_name}: {e}")

        conn.close()
        logger.info(f"Future sync done: {results['synced']} matches")
        return results

    async def sync_recent_events(self, db_path: str, days: int = 7) -> Dict:
        """同步最近比赛事件（进球、换人、红黄牌等）"""
        logger.info("Syncing recent match events...")

        source = self.get_source('apifootball')
        if not source or not hasattr(source, 'get_match_events_by_date'):
            return {'error': 'apifootball source not available'}

        results = {'synced': 0, 'goals': 0, 'cards': 0, 'lineups': 0, 'errors': []}

        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        past = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')
        today = datetime.now().strftime('%Y-%m-%d')

        for league_id, league_name in self.SYNC_LEAGUES.items():
            try:
                events = await source.get_match_events_by_date(past, today, league_id)

                for event in events:
                    match_date = event.get('date')
                    home_team = event.get('home_team', '')
                    away_team = event.get('away_team', '')

                    # 查找球队ID
                    cursor.execute('''
                        SELECT team_id FROM teams
                        WHERE name_en LIKE ? OR name_cn LIKE ? OR short_name LIKE ?
                        LIMIT 1
                    ''', (f'%{home_team}%', f'%{home_team}%', f'%{home_team}%'))
                    home_row = cursor.fetchone()

                    cursor.execute('''
                        SELECT team_id FROM teams
                        WHERE name_en LIKE ? OR name_cn LIKE ? OR short_name LIKE ?
                        LIMIT 1
                    ''', (f'%{away_team}%', f'%{away_team}%', f'%{away_team}%'))
                    away_row = cursor.fetchone()

                    if not home_row or not away_row:
                        continue

                    cursor.execute('''
                        SELECT match_id FROM matches
                        WHERE match_date = ? AND home_team_id = ? AND away_team_id = ?
                    ''', (match_date, home_row[0], away_row[0]))

                    existing = cursor.fetchone()
                    if not existing:
                        continue

                    # 更新比分和状态
                    status = event.get('status', '')
                    if "'" in status:
                        status = 'live'
                    elif status == 'Finished':
                        status = 'finished'

                    cursor.execute('''
                        UPDATE matches SET
                            home_goals = ?,
                            away_goals = ?,
                            home_goals_ht = ?,
                            away_goals_ht = ?,
                            status = ?,
                            source = 'apifootball_events'
                        WHERE match_id = ?
                    ''', (
                        event.get('home_score'),
                        event.get('away_score'),
                        event.get('home_score_ht'),
                        event.get('away_score_ht'),
                        status or 'finished',
                        existing[0]
                    ))

                    results['goals'] += len(event.get('goalscorer', []))
                    results['cards'] += len(event.get('cards', []))
                    if event.get('lineup'):
                        results['lineups'] += 1
                    results['synced'] += 1

                conn.commit()

            except Exception as e:
                results['errors'].append(f"{league_name}: {str(e)}")
                logger.error(f"Error: {e}")

        conn.close()
        logger.info(f"Events sync done: {results['synced']} matches, {results['goals']} goals")

        # 使用365Scores同步缺失比分的比赛
        scores365_results = await self.sync_365scores_scores(db_path, days)
        results['scores365'] = scores365_results

        return results

    async def sync_365scores_scores(self, db_path: str, days: int = 7) -> Dict:
        """使用365Scores同步缺失比分的比赛"""
        logger.info("Syncing scores from 365Scores...")

        try:
            from .scores365_source import Scores365Source
            source = Scores365Source()

            games = await source.get_games()
            synced = 0
            goals = 0

            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()

            for game in games:
                status = game.get('statusText', '')
                if status != 'Ended':
                    continue

                home = game.get('homeCompetitor', {})
                away = game.get('awayCompetitor', {})
                home_name = home.get('name', '')
                away_name = away.get('name', '')
                home_score = home.get('score')
                away_score = away.get('score')

                if home_score is None or away_score is None:
                    continue

                start_time = game.get('startTime', '')
                if not start_time:
                    continue

                match_date = start_time.split('T')[0]

                # 尝试匹配比赛 - 使用多种名称匹配
                cursor.execute('''
                    SELECT m.match_id, ht.name_en, at.name_en
                    FROM matches m
                    JOIN teams ht ON m.home_team_id = ht.team_id
                    JOIN teams at ON m.away_team_id = at.team_id
                    WHERE m.match_date = ?
                    AND m.status = 'finished'
                    AND m.home_goals IS NULL
                    AND (
                        LOWER(ht.name_en) = LOWER(?)
                        OR LOWER(ht.name_cn) = LOWER(?)
                        OR REPLACE(LOWER(ht.name_en), ' ', '') = REPLACE(LOWER(?), ' ', '')
                        OR LOWER(at.name_en) = LOWER(?)
                        OR LOWER(at.name_cn) = LOWER(?)
                        OR REPLACE(LOWER(at.name_en), ' ', '') = REPLACE(LOWER(?), ' ', '')
                    )
                ''', (match_date, home_name, home_name, home_name, away_name, away_name, away_name))

                row = cursor.fetchone()
                if row:
                    match_id, db_home, db_away = row
                    # 确定主客队顺序
                    home_match = (home_name.lower() in db_home.lower() or
                                  home_name.lower().replace(' ', '') in db_home.lower().replace(' ', ''))
                    away_match = (away_name.lower() in db_away.lower() or
                                   away_name.lower().replace(' ', '') in db_away.lower().replace(' ', ''))

                    if home_match and away_match:
                        result = 'H' if home_score > away_score else ('A' if home_score < away_score else 'D')
                        cursor.execute('''
                            UPDATE matches
                            SET home_goals = ?, away_goals = ?, result = ?, source = '365scores'
                            WHERE match_id = ?
                        ''', (int(home_score), int(away_score), result, match_id))
                        synced += 1
                        goals += int(home_score) + int(away_score)
                        logger.info(f"365Scores: {db_home} {int(home_score)}-{int(away_score)} {db_away}")

            conn.commit()
            conn.close()
            await source.close()

            logger.info(f"365Scores sync done: {synced} matches, {goals} goals")
            return {'synced': synced, 'goals': goals}

        except Exception as e:
            logger.error(f"365Scores sync error: {e}")
            return {'error': str(e)}

    def fix_expired_matches(self, db_path: str) -> Dict:
        """修复过期比赛状态"""
        logger.info("Fixing expired matches...")

        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        today = datetime.now().strftime('%Y-%m-%d')

        cursor.execute('''
            SELECT COUNT(*) FROM matches
            WHERE match_date < ?
            AND status = 'scheduled'
        ''', (today,))

        count = cursor.fetchone()[0]

        if count > 0:
            cursor.execute('''
                UPDATE matches SET
                    status = 'finished',
                    source = 'auto_fixed'
                WHERE match_date < ?
                AND status = 'scheduled'
            ''', (today,))
            conn.commit()

        conn.close()
        logger.info(f"Fixed {count} expired matches")
        return {'fixed': count}

    async def sync_all(self, db_path: str) -> Dict:
        """执行完整同步（未来 + 实时 + 修复过期）"""
        logger.info("Starting full sync...")

        results = {
            'expired': self.fix_expired_matches(db_path),
            'future': await self.sync_future_matches(db_path),
            'events': await self.sync_recent_events(db_path),
            'timestamp': datetime.now().isoformat()
        }

        logger.info("Full sync completed")
        return results

    def get_sync_status(self, db_path: str) -> Dict:
        """获取同步状态报告"""
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        today = datetime.now().strftime('%Y-%m-%d')
        future_3 = (datetime.now() + timedelta(days=3)).strftime('%Y-%m-%d')
        future_7 = (datetime.now() + timedelta(days=7)).strftime('%Y-%m-%d')
        past_7 = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d')

        report = {'timestamp': datetime.now().isoformat()}

        # 未来3天
        cursor.execute('''
            SELECT COUNT(*), SUM(CASE WHEN match_time IS NOT NULL AND match_time != '' THEN 1 ELSE 0 END)
            FROM matches WHERE match_date >= ? AND match_date <= ?
        ''', (today, future_3))
        row = cursor.fetchone()
        report['next_3_days'] = {'total': row[0], 'with_time': row[1],
                                  'coverage': round(row[1]/row[0]*100, 1) if row[0] > 0 else 0}

        # 未来7天
        cursor.execute('''
            SELECT COUNT(*), SUM(CASE WHEN match_time IS NOT NULL AND match_time != '' THEN 1 ELSE 0 END)
            FROM matches WHERE match_date >= ? AND match_date <= ?
        ''', (today, future_7))
        row = cursor.fetchone()
        report['next_7_days'] = {'total': row[0], 'with_time': row[1],
                                  'coverage': round(row[1]/row[0]*100, 1) if row[0] > 0 else 0}

        # 最近7天已结束
        cursor.execute('''
            SELECT COUNT(*) FROM matches
            WHERE match_date >= ? AND match_date < ?
            AND status IN ('finished', 'FINISHED')
        ''', (past_7, today))
        report['recent_finished'] = cursor.fetchone()[0]

        # 过期但状态错误
        cursor.execute('''
            SELECT COUNT(*) FROM matches
            WHERE match_date < ?
            AND status = 'scheduled'
        ''', (today,))
        report['expired_wrong_status'] = cursor.fetchone()[0]

        # 球队动态统计
        cursor.execute('''
            SELECT COUNT(*) FROM team_news WHERE news_date >= ?
        ''', (past_7,))
        report['team_news'] = cursor.fetchone()[0]

        cursor.execute('''
            SELECT category, COUNT(*) FROM team_news WHERE news_date >= ?
            GROUP BY category
        ''', (past_7,))
        report['team_news_by_category'] = {row[0]: row[1] for row in cursor.fetchall()}

        conn.close()
        return report

    # ==================== 球队动态爬虫 ====================

    def crawl_news(self, db_path: str) -> Dict:
        """爬取新闻资讯"""
        logger.info("Crawling news...")
        import requests
        from bs4 import BeautifulSoup

        news_list = []
        try:
            session = requests.Session()
            session.headers.update({
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            })

            resp = session.get(
                "https://news.zhibo8.com/zuqiu/more.htm",
                timeout=15,
                proxies={'http': None, 'https': None}
            )
            resp.encoding = 'utf-8'
            soup = BeautifulSoup(resp.text, 'html.parser')

            data_list = soup.select_one('.dataList')
            if not data_list:
                return {'error': 'No data found'}

            items = data_list.select('li')[:100]

            for item in items:
                link = item.select_one('a')
                if not link:
                    continue

                title = link.get_text(strip=True)
                href = link.get('href', '')

                if len(title) < 5:
                    continue

                time_span = item.select_one('span')
                news_time = time_span.get_text(strip=True) if time_span else ''

                news_date = datetime.now().strftime('%Y-%m-%d')
                if news_time:
                    try:
                        match = re.search(r'(\d{1,2})-(\d{1,2})', news_time)
                        if match:
                            month, day = int(match.group(1)), int(match.group(2))
                            news_date = f"{datetime.now().year}-{month:02d}-{day:02d}"
                    except:
                        pass

                news_list.append({
                    'title': title,
                    'url': href if href.startswith('http') else f"https://news.zhibo8.com{href}",
                    'date': news_date,
                    'source': 'zhibo8'
                })

        except Exception as e:
            logger.error(f"News crawl error: {e}")
            return {'error': str(e)}

        # 保存到数据库
        saved = self._save_news_to_db(db_path, news_list)
        logger.info(f"News crawled: {len(news_list)}, saved: {saved}")
        return {'crawled': len(news_list), 'saved': saved}

    def crawl_injuries(self, db_path: str) -> Dict:
        """爬取伤病名单"""
        logger.info("Crawling injuries...")
        import requests
        from bs4 import BeautifulSoup

        injuries = []
        try:
            session = requests.Session()
            session.headers.update({
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            })

            resp = session.get(
                "https://www.premierleague.com/injuries",
                timeout=15,
                proxies={'http': None, 'https': None}
            )
            soup = BeautifulSoup(resp.text, 'html.parser')

            rows = soup.select('.tableContainer tbody tr, .injuryTable tr')

            for row in rows[:50]:
                cols = row.select('td')
                if len(cols) >= 3:
                    player_name = cols[0].get_text(strip=True)
                    team_name = cols[1].get_text(strip=True)
                    injury_type = cols[2].get_text(strip=True) if len(cols) > 2 else ''

                    injuries.append({
                        'player': player_name,
                        'team': team_name,
                        'injury_type': injury_type,
                        'source': 'premier_league_official',
                        'date': datetime.now().strftime('%Y-%m-%d')
                    })

        except Exception as e:
            logger.error(f"Injury crawl error: {e}")

        # 保存到数据库
        saved = self._save_injuries_to_db(db_path, injuries)
        logger.info(f"Injuries crawled: {len(injuries)}, saved: {saved}")
        return {'crawled': len(injuries), 'saved': saved}

    def crawl_lineups(self) -> Dict:
        """爬取阵容预测"""
        logger.info("Crawling lineups...")
        import requests
        from bs4 import BeautifulSoup

        lineups = []
        try:
            session = requests.Session()
            session.headers.update({
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            })

            resp = session.get(
                "https://www.188bifen.com/lineup/",
                timeout=15,
                proxies={'http': None, 'https': None}
            )
            resp.encoding = 'utf-8'
            soup = BeautifulSoup(resp.text, 'html.parser')

            matches = soup.select('.match-item, .lineup-match')

            for match in matches[:20]:
                try:
                    home_team = match.select_one('.home-team')
                    away_team = match.select_one('.away-team')
                    match_time = match.select_one('.match-time')

                    if home_team and away_team:
                        lineups.append({
                            'home_team': home_team.get_text(strip=True),
                            'away_team': away_team.get_text(strip=True),
                            'match_time': match_time.get_text(strip=True) if match_time else '',
                            'source': '188bifen',
                            'date': datetime.now().strftime('%Y-%m-%d')
                        })

                except Exception:
                    continue

        except Exception as e:
            logger.error(f"Lineup crawl error: {e}")

        logger.info(f"Lineups crawled: {len(lineups)}")
        return {'crawled': len(lineups), 'data': lineups[:5]}

    def _save_news_to_db(self, db_path: str, news_list: List) -> int:
        """保存新闻到数据库"""
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        saved = 0

        news_type_map = {
            'injury': ['伤', '受伤', '伤病', '伤缺', '伤停'],
            'suspension': ['停赛', '红牌', '禁赛'],
            'transfer': ['转会', '签约', '加盟', '租借'],
            'return': ['复出', '回归', '伤愈'],
            'coach': ['主帅', '教练', '下课', '解雇'],
        }

        for news in news_list:
            try:
                cursor.execute(
                    "SELECT news_id FROM team_news WHERE title = ? AND news_date = ?",
                    (news['title'], news['date'])
                )
                if cursor.fetchone():
                    continue

                # 解析新闻类型
                news_type = 'other'
                for ntype, keywords in news_type_map.items():
                    if any(kw in news['title'] for kw in keywords):
                        news_type = ntype
                        break

                positive = ['复出', '回归', '续约', '连胜', '签约', '加盟']
                negative = ['伤', '停赛', '下课', '解雇', '连败']

                if any(kw in news['title'] for kw in positive):
                    category = 'positive'
                elif any(kw in news['title'] for kw in negative):
                    category = 'negative'
                else:
                    category = 'neutral'

                impact = 4 if any(kw in news['title'] for kw in ['核心', '主力', '队长']) else 2

                # 提取球队
                cursor.execute("SELECT team_id, name_en, name_cn FROM teams")
                teams = cursor.fetchall()
                team_ids = []
                for team in teams:
                    if team[2] and team[2] in news['title']:
                        team_ids.append(team[0])
                    elif team[1] and team[1] in news['title']:
                        team_ids.append(team[0])

                if not team_ids:
                    continue

                for tid in team_ids[:2]:
                    cursor.execute("""
                        INSERT INTO team_news (
                            team_id, title, news_type, category,
                            impact_level, news_date, source, verified
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, 0)
                    """, (tid, news['title'], news_type, category, impact,
                          news['date'], news['source']))
                    saved += 1

            except Exception:
                continue

        conn.commit()
        conn.close()
        return saved

    def _save_injuries_to_db(self, db_path: str, injuries: List) -> int:
        """保存伤病数据"""
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        saved = 0

        for injury in injuries:
            try:
                cursor.execute(
                    "SELECT team_id FROM teams WHERE name_en LIKE ? OR name_cn LIKE ?",
                    (f'%{injury["team"]}%', f'%{injury["team"]}%')
                )
                team = cursor.fetchone()
                if not team:
                    continue

                cursor.execute(
                    "SELECT player_id FROM players WHERE name LIKE ? AND team_id = ?",
                    (f'%{injury["player"]}%', team[0])
                )
                player = cursor.fetchone()

                if player:
                    cursor.execute("""
                        INSERT OR REPLACE INTO player_status (
                            player_id, team_id, status, injury_type,
                            source, updated_at
                        ) VALUES (?, ?, 'injured', ?, ?, CURRENT_TIMESTAMP)
                    """, (player[0], team[0], injury['injury_type'], injury['source']))
                    saved += 1

            except Exception:
                continue

        conn.commit()
        conn.close()
        return saved

    async def full_sync(self, db_path: str) -> Dict:
        """执行完整同步（比赛数据 + 爬虫数据）"""
        logger.info("Starting full sync (matches + crawlers)...")

        results = {
            'timestamp': datetime.now().isoformat(),
            # 比赛数据同步
            'expired': self.fix_expired_matches(db_path),
            'future': await self.sync_future_matches(db_path),
            'events': await self.sync_recent_events(db_path),
            # 爬虫数据
            'news': self.crawl_news(db_path),
            'injuries': self.crawl_injuries(db_path),
            'lineups': self.crawl_lineups(),
        }

        logger.info("Full sync completed")
        return results

    # ==================== 实时数据同步 ====================

    async def sync_live_matches(self, db_path: str) -> Dict:
        """
        同步实时比赛数据

        使用 Sofascore 爬虫获取实时比分、事件、统计
        """
        logger.info("Syncing live matches...")

        try:
            crawler = SofascoreCrawler(db_path)

            # 获取实时比赛
            live_matches = crawler.get_live_matches()

            # 获取即将开始的比赛
            upcoming_matches = crawler.get_upcoming_matches()

            # 保存到数据库
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()

            synced_live = 0
            synced_upcoming = 0

            # 更新实时比分
            for match in live_matches:
                try:
                    home_team = match.get('home_team', '')
                    away_team = match.get('away_team', '')

                    # 查找对应的比赛记录
                    cursor.execute('''
                        SELECT m.match_id FROM matches m
                        JOIN teams ht ON m.home_team_id = ht.team_id
                        JOIN teams at ON m.away_team_id = at.team_id
                        WHERE (LOWER(ht.name_en) LIKE LOWER(?) OR LOWER(ht.name_cn) LIKE LOWER(?))
                        AND (LOWER(at.name_en) LIKE LOWER(?) OR LOWER(at.name_cn) LIKE LOWER(?))
                        AND m.match_date = DATE('now')
                    ''', (f'%{home_team}%', f'%{home_team}%', f'%{away_team}%', f'%{away_team}%'))

                    row = cursor.fetchone()
                    if row:
                        cursor.execute('''
                            UPDATE matches SET
                                home_goals = ?,
                                away_goals = ?,
                                status = ?,
                                source = 'live_sync'
                            WHERE match_id = ?
                        ''', (
                            match.get('home_score'),
                            match.get('away_score'),
                            'live' if match.get('status') in ['IN_PLAY', 'PAUSED', 'LIVE'] else 'finished',
                            row[0]
                        ))
                        synced_live += 1

                except Exception as e:
                    logger.debug(f"Error syncing live match: {e}")
                    continue

            # 更新即将开始的比赛时间
            for match in upcoming_matches:
                try:
                    home_team = match.get('home_team', '')
                    away_team = match.get('away_team', '')
                    start_time = match.get('start_time', '')

                    if not start_time:
                        continue

                    # 解析时间
                    from datetime import datetime
                    if 'T' in start_time:
                        dt = datetime.fromisoformat(start_time.replace('Z', '+00:00'))
                        match_date = dt.strftime('%Y-%m-%d')
                        match_time = dt.strftime('%H:%M')
                    else:
                        continue

                    # 查找对应的比赛记录
                    cursor.execute('''
                        SELECT m.match_id FROM matches m
                        JOIN teams ht ON m.home_team_id = ht.team_id
                        JOIN teams at ON m.away_team_id = at.team_id
                        WHERE (LOWER(ht.name_en) LIKE LOWER(?) OR LOWER(ht.name_cn) LIKE LOWER(?))
                        AND (LOWER(at.name_en) LIKE LOWER(?) OR LOWER(at.name_cn) LIKE LOWER(?))
                        AND m.match_date = ?
                    ''', (f'%{home_team}%', f'%{home_team}%', f'%{away_team}%', f'%{away_team}%', match_date))

                    row = cursor.fetchone()
                    if row:
                        cursor.execute('''
                            UPDATE matches SET
                                match_time = ?,
                                status = 'scheduled',
                                source = 'live_sync'
                            WHERE match_id = ?
                        ''', (match_time, row[0]))
                        synced_upcoming += 1

                except Exception as e:
                    logger.debug(f"Error syncing upcoming match: {e}")
                    continue

            conn.commit()
            conn.close()

            logger.info(f"Live sync done: {synced_live} live, {synced_upcoming} upcoming")
            return {
                'live_matches': len(live_matches),
                'upcoming_matches': len(upcoming_matches),
                'synced_live': synced_live,
                'synced_upcoming': synced_upcoming
            }

        except Exception as e:
            logger.error(f"Live sync error: {e}")
            return {'error': str(e)}

    async def sync_match_events(self, db_path: str, event_id: int) -> Dict:
        """
        同步单场比赛的详细事件

        Args:
            db_path: 数据库路径
            event_id: 比赛ID（Sofascore/football-data.org格式）
        """
        logger.info(f"Syncing events for match {event_id}...")

        try:
            crawler = SofascoreCrawler(db_path)

            # 获取比赛事件
            events = crawler.get_match_events(event_id)

            # 获取比赛统计
            statistics = crawler.get_match_statistics(event_id)

            # 获取球员评分
            ratings = crawler.get_player_ratings(event_id)

            return {
                'events': len(events),
                'statistics': len(statistics),
                'ratings': len(ratings),
                'data': {
                    'events': events[:10],  # 返回前10个事件
                    'statistics': statistics,
                    'ratings': ratings[:5]  # 返回前5个评分
                }
            }

        except Exception as e:
            logger.error(f"Match events sync error: {e}")
            return {'error': str(e)}

    # ==================== 新闻聚合同步 ====================

    async def sync_news_aggregate(self, db_path: str, team_name: str = None) -> Dict:
        """
        同步聚合新闻数据

        Args:
            db_path: 数据库路径
            team_name: 可选，指定球队
        """
        logger.info("Syncing aggregated news...")

        try:
            aggregator = SocialMediaNewsAggregator(db_path)

            # 聚合所有来源的新闻
            all_news = aggregator.aggregate_all_news(team_name)

            # 保存到数据库
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()

            saved = 0
            for news in all_news:
                try:
                    # 检查是否已存在
                    cursor.execute('''
                        SELECT news_id FROM team_news
                        WHERE title = ? AND news_date = DATE(?)
                    ''', (news.title[:200], news.published_at[:10] if news.published_at else datetime.now().strftime('%Y-%m-%d')))

                    if cursor.fetchone():
                        continue

                    # 查找关联球队
                    team_ids = []
                    for team in news.team_mentioned:
                        cursor.execute('''
                            SELECT team_id FROM teams
                            WHERE name_en LIKE ? OR name_cn LIKE ?
                        ''', (f'%{team}%', f'%{team}%'))
                        row = cursor.fetchone()
                        if row:
                            team_ids.append(row[0])

                    # 确定新闻类型
                    news_type = 'other'
                    if any(kw in news.title for kw in ['伤', '受伤', '伤病']):
                        news_type = 'injury'
                    elif any(kw in news.title for kw in ['转会', '签约', '加盟']):
                        news_type = 'transfer'
                    elif any(kw in news.title for kw in ['停赛', '红牌']):
                        news_type = 'suspension'

                    # 影响等级
                    impact = 4 if any(kw in news.title for kw in ['核心', '主力', '队长']) else 2

                    # 保存新闻
                    for team_id in team_ids[:2]:  # 最多关联2个球队
                        cursor.execute('''
                            INSERT INTO team_news (
                                team_id, title, news_type, category,
                                impact_level, news_date, source, verified
                            ) VALUES (?, ?, ?, ?, ?, ?, ?, 0)
                        ''', (
                            team_id,
                            news.title[:200],
                            news_type,
                            news.sentiment,
                            impact,
                            news.published_at[:10] if news.published_at else datetime.now().strftime('%Y-%m-%d'),
                            news.source
                        ))
                        saved += 1

                except Exception as e:
                    logger.debug(f"Error saving news: {e}")
                    continue

            conn.commit()
            conn.close()

            logger.info(f"News sync done: {len(all_news)} fetched, {saved} saved")
            return {
                'fetched': len(all_news),
                'saved': saved,
                'sources': list(set(n.source for n in all_news))
            }

        except Exception as e:
            logger.error(f"News aggregate sync error: {e}")
            return {'error': str(e)}

    async def sync_team_specific_news(self, db_path: str, team_name: str) -> Dict:
        """
        同步特定球队的新闻

        Args:
            db_path: 数据库路径
            team_name: 球队名称
        """
        logger.info(f"Syncing news for team: {team_name}")
        return await self.sync_news_aggregate(db_path, team_name)

    # ==================== 综合同步 ====================

    async def full_sync_v2(self, db_path: str) -> Dict:
        """
        执行完整同步 V2（包含实时数据和新闻聚合）
        """
        logger.info("Starting full sync V2...")

        results = {
            'timestamp': datetime.now().isoformat(),
            # 基础比赛数据同步
            'expired': self.fix_expired_matches(db_path),
            'future': await self.sync_future_matches(db_path),
            'events': await self.sync_recent_events(db_path),
            # 实时数据同步
            'live': await self.sync_live_matches(db_path),
            # 新闻聚合同步
            'news_aggregate': await self.sync_news_aggregate(db_path),
            # 爬虫数据
            'news': self.crawl_news(db_path),
            'injuries': self.crawl_injuries(db_path),
            'lineups': self.crawl_lineups(),
        }

        logger.info("Full sync V2 completed")
        return results