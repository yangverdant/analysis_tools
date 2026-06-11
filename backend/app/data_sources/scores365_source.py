"""
365Scores 数据源
实时比分数据，覆盖全球联赛
"""
import aiohttp
import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import logging

logger = logging.getLogger(__name__)


class Scores365Source:
    """365Scores实时比分数据源"""

    BASE_URL = "https://webws.365scores.com/web"

    def __init__(self):
        self.session = None

    async def _get_session(self):
        if not self.session:
            self.session = aiohttp.ClientSession()
        return self.session

    async def close(self):
        if self.session:
            await self.session.close()
            self.session = None

    async def get_games(self, sport_id: int = 1, country_id: Optional[int] = None,
                        date: Optional[str] = None) -> List[Dict]:
        """
        获取比赛数据

        Args:
            sport_id: 体育类型ID (1=足球)
            country_id: 国家ID (24=瑞典)
            date: 日期过滤
        """
        session = await self._get_session()

        params = {
            'langId': '1',
            'timezoneName': 'Asia/Shanghai',
            'userCountryId': '1',
            'appTypeId': '1',
            'sportId': sport_id
        }

        if country_id:
            params['countryId'] = country_id

        url = f"{self.BASE_URL}/games"
        try:
            async with session.get(url, params=params) as resp:
                data = await resp.json()
                games = data.get('games', [])

                # 按日期过滤
                if date:
                    games = [g for g in games if g.get('startTime', '').startswith(date)]

                return games
        except Exception as e:
            logger.error(f"365Scores获取比赛失败: {e}")
            return []

    async def get_finished_matches(self, days: int = 7) -> List[Dict]:
        """
        获取已结束的比赛（用于同步比分）

        Args:
            days: 最近多少天
        """
        games = await self.get_games()

        # 过滤已结束的比赛
        finished = []
        for game in games:
            status = game.get('statusText', '')
            if status == 'Ended':
                start_time = game.get('startTime', '')
                if start_time:
                    game_date = datetime.fromisoformat(start_time.replace('+08:00', '+08:00'))
                    if game_date >= datetime.now() - timedelta(days=days):
                        finished.append(game)

        return finished

    def parse_match_data(self, game: Dict) -> Dict:
        """
        解析比赛数据为标准格式

        Args:
            game: 365Scores比赛数据
        """
        home = game.get('homeCompetitor', {})
        away = game.get('awayCompetitor', {})

        return {
            'match_id': f"365scores_{game.get('id')}",
            'league': game.get('competitionDisplayName', ''),
            'league_id': game.get('competitionId'),
            'home_team': home.get('name', ''),
            'home_team_id': home.get('id'),
            'away_team': away.get('name', ''),
            'away_team_id': away.get('id'),
            'home_goals': int(home.get('score', 0)) if home.get('score') else None,
            'away_goals': int(away.get('score', 0)) if away.get('score') else None,
            'status': 'finished' if game.get('statusText') == 'Ended' else 'scheduled',
            'match_date': game.get('startTime', '').split('T')[0] if game.get('startTime') else None,
            'match_time': game.get('startTime', '').split('T')[1][:5] if game.get('startTime') else None,
            'source': '365scores',
            'has_lineups': game.get('hasLineups', False),
            'has_stats': game.get('hasStats', False)
        }

    async def sync_finished_matches(self, db_path: str, days: int = 7) -> Dict:
        """
        同步已结束比赛的比分到数据库

        Args:
            db_path: 数据库路径
            days: 同步最近多少天
        """
        import sqlite3

        games = await self.get_finished_matches(days)
        synced = 0
        errors = []

        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        for game in games:
            try:
                match_data = self.parse_match_data(game)

                # 尝试匹配数据库中的比赛
                # 使用球队名称匹配
                cursor.execute("""
                    SELECT match_id FROM matches
                    WHERE match_date = ?
                    AND (home_team_id = ? OR away_team_id = ?)
                    AND status = 'finished'
                    AND home_goals IS NULL
                """, (match_data['match_date'], match_data['home_team_id'],
                      match_data['away_team_id']))

                # 也尝试用球队名称匹配
                cursor.execute("""
                    SELECT match_id, ht.name_en, at.name_en FROM matches m
                    JOIN teams ht ON m.home_team_id = ht.team_id
                    JOIN teams at ON m.away_team_id = at.team_id
                    WHERE m.match_date = ?
                    AND (LOWER(ht.name_en) = LOWER(?) OR LOWER(at.name_en) = LOWER(?))
                    AND m.status = 'finished'
                    AND m.home_goals IS NULL
                """, (match_data['match_date'], match_data['home_team'].lower(),
                      match_data['away_team'].lower()))

                row = cursor.fetchone()
                if row:
                    match_id = row[0]
                    cursor.execute("""
                        UPDATE matches
                        SET home_goals = ?, away_goals = ?, result = ?, source = ?
                        WHERE match_id = ?
                    """, (match_data['home_goals'], match_data['away_goals'],
                          self._get_result(match_data['home_goals'], match_data['away_goals']),
                          '365scores', match_id))
                    synced += 1
                    logger.info(f"更新比分: {match_data['home_team']} {match_data['home_goals']}-{match_data['away_goals']} {match_data['away_team']}")

            except Exception as e:
                errors.append(str(e))
                logger.error(f"同步比赛失败: {e}")

        conn.commit()
        conn.close()

        return {'synced': synced, 'errors': errors}

    def _get_result(self, home_goals: int, away_goals: int) -> str:
        """计算比赛结果"""
        if home_goals > away_goals:
            return 'H'
        elif home_goals < away_goals:
            return 'A'
        else:
            return 'D'

    # 国家ID映射
    COUNTRY_IDS = {
        'sweden': 24,
        'england': 1,
        'germany': 2,
        'france': 3,
        'italy': 4,
        'spain': 5,
        'netherlands': 6,
        'portugal': 7,
        'brazil': 10,
        'argentina': 11,
        'usa': 12,
        'japan': 13,
        'korea': 14,
        'china': 15,
        'russia': 16,
        'turkey': 17,
        'poland': 18,
        'greece': 19,
        'denmark': 320,
        'norway': 21,
        'finland': 22,
        'austria': 23,
        'switzerland': 25,
        'belgium': 26,
        'scotland': 1161,
    }

    async def get_league_matches(self, league_name: str, days: int = 30) -> List[Dict]:
        """
        获取特定联赛的比赛

        Args:
            league_name: 联赛名称（如 'Allsvenskan'）
            days: 最近多少天
        """
        games = await self.get_games()

        # 按联赛名称过滤
        league_games = []
        for game in games:
            comp_name = game.get('competitionDisplayName', '')
            if league_name.lower() in comp_name.lower():
                start_time = game.get('startTime', '')
                if start_time:
                    game_date = datetime.fromisoformat(start_time.replace('+08:00', '+08:00'))
                    if game_date >= datetime.now() - timedelta(days=days):
                        league_games.append(self.parse_match_data(game))

        return league_games