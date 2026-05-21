"""
本地数据源实现
包含: CSV文件、数据库、StatsBomb本地数据
"""

import os
import json
import sqlite3
from typing import Dict, List, Optional, Any
from datetime import datetime
from pathlib import Path
import pandas as pd

from .base import (
    BaseDataSource, DataSourceConfig, DataSourceType, DataCategory,
    MatchData, StandingData, TeamData, PlayerData
)


class LocalCSVSource(BaseDataSource):
    """本地CSV文件数据源"""

    def __init__(self, config: DataSourceConfig):
        super().__init__(config)
        self.data_dir = Path(config.base_url or "data")

    def _find_csv_file(self, league: str, season: Optional[str] = None) -> Optional[Path]:
        """查找CSV文件"""
        # 尝试多种路径格式
        patterns = [
            f"**/{league}*{season}*.csv" if season else f"**/{league}*.csv",
            f"**/leagues/**/{league}*.csv",
            f"**/{league}/**/{season}*.csv" if season else f"**/{league}/*.csv",
        ]

        for pattern in patterns:
            matches = list(self.data_dir.glob(pattern))
            if matches:
                return matches[0]
        return None

    async def get_livescores(
        self,
        leagues: Optional[List[str]] = None,
        date: Optional[str] = None
    ) -> List[MatchData]:
        """获取实时比分 - 从最新CSV"""
        matches = []
        for league in leagues or []:
            csv_file = self._find_csv_file(league)
            if csv_file:
                df = pd.read_csv(csv_file)
                # 获取最近的比赛
                if 'Date' in df.columns:
                    df['Date'] = pd.to_datetime(df['Date'], errors='coerce')
                    df = df.sort_values('Date', ascending=False)
                    for _, row in df.head(20).iterrows():
                        matches.append(self._parse_row(row, league))
        return matches

    async def get_fixtures(
        self,
        league: str,
        season: Optional[str] = None,
        team: Optional[str] = None,
        from_date: Optional[str] = None,
        to_date: Optional[str] = None
    ) -> List[MatchData]:
        """获取赛程"""
        csv_file = self._find_csv_file(league, season)
        if not csv_file:
            return []

        df = pd.read_csv(csv_file)
        matches = []

        for _, row in df.iterrows():
            match = self._parse_row(row, league)
            if team:
                if team.lower() not in match.home_team.lower() and team.lower() not in match.away_team.lower():
                    continue
            matches.append(match)

        return matches

    async def get_standings(
        self,
        league: str,
        season: Optional[str] = None
    ) -> List[StandingData]:
        """获取积分榜 - 从比赛数据计算"""
        matches = await self.get_fixtures(league, season)
        if not matches:
            return []

        # 计算积分榜
        teams = {}
        for m in matches:
            if m.home_score is None or m.away_score is None:
                continue

            # 主队
            if m.home_team not in teams:
                teams[m.home_team] = {'played': 0, 'won': 0, 'drawn': 0, 'lost': 0, 'gf': 0, 'ga': 0, 'points': 0}

            teams[m.home_team]['played'] += 1
            teams[m.home_team]['gf'] += m.home_score
            teams[m.home_team]['ga'] += m.away_score

            if m.home_score > m.away_score:
                teams[m.home_team]['won'] += 1
                teams[m.home_team]['points'] += 3
            elif m.home_score < m.away_score:
                teams[m.home_team]['lost'] += 1
            else:
                teams[m.home_team]['drawn'] += 1
                teams[m.home_team]['points'] += 1

            # 客队
            if m.away_team not in teams:
                teams[m.away_team] = {'played': 0, 'won': 0, 'drawn': 0, 'lost': 0, 'gf': 0, 'ga': 0, 'points': 0}

            teams[m.away_team]['played'] += 1
            teams[m.away_team]['gf'] += m.away_score
            teams[m.away_team]['ga'] += m.home_score

            if m.away_score > m.home_score:
                teams[m.away_team]['won'] += 1
                teams[m.away_team]['points'] += 3
            elif m.away_score < m.home_score:
                teams[m.away_team]['lost'] += 1
            else:
                teams[m.away_team]['drawn'] += 1
                teams[m.away_team]['points'] += 1

        # 排序
        standings = []
        sorted_teams = sorted(teams.items(), key=lambda x: (-x[1]['points'], -x[1]['gf'] + x[1]['ga']))

        for i, (team, stats) in enumerate(sorted_teams, 1):
            standings.append(StandingData(
                position=i,
                team=team,
                played=stats['played'],
                won=stats['won'],
                drawn=stats['drawn'],
                lost=stats['lost'],
                goals_for=stats['gf'],
                goals_against=stats['ga'],
                goal_difference=stats['gf'] - stats['ga'],
                points=stats['points'],
                league=league,
                season=season,
                source="local_csv"
            ))

        return standings

    async def get_matches(
        self,
        league: str,
        season: Optional[str] = None,
        team: Optional[str] = None,
        limit: Optional[int] = None
    ) -> List[MatchData]:
        """获取历史比赛"""
        matches = await self.get_fixtures(league, season, team)
        if limit:
            matches = matches[:limit]
        return matches

    async def get_team(self, team_id: str) -> Optional[TeamData]:
        """获取球队信息"""
        return None

    async def get_players(
        self,
        team: Optional[str] = None,
        league: Optional[str] = None,
        season: Optional[str] = None
    ) -> List[PlayerData]:
        """获取球员信息"""
        return []

    async def get_scorers(
        self,
        league: str,
        season: Optional[str] = None,
        limit: Optional[int] = None
    ) -> List[PlayerData]:
        """获取射手榜"""
        return []

    def _parse_row(self, row: pd.Series, league: str) -> MatchData:
        """解析CSV行"""
        return MatchData(
            date=str(row.get('Date', ''))[:10] if pd.notna(row.get('Date')) else None,
            home_team=str(row.get('HomeTeam', '')),
            away_team=str(row.get('AwayTeam', '')),
            home_score=int(row.get('FTHG', 0)) if pd.notna(row.get('FTHG')) else None,
            away_score=int(row.get('FTAG', 0)) if pd.notna(row.get('FTAG')) else None,
            home_score_ht=int(row.get('HTHG', 0)) if pd.notna(row.get('HTHG')) else None,
            away_score_ht=int(row.get('HTAG', 0)) if pd.notna(row.get('HTAG')) else None,
            round_num=int(row.get('round', 0)) if pd.notna(row.get('round')) else None,
            league=league,
            source="local_csv"
        )


class DatabaseSource(BaseDataSource):
    """数据库数据源"""

    def __init__(self, config: DataSourceConfig):
        super().__init__(config)
        self.db_path = Path(config.base_url or "data/football_unified.db")

    def _get_connection(self) -> sqlite3.Connection:
        """获取数据库连接"""
        return sqlite3.connect(self.db_path)

    async def get_livescores(
        self,
        leagues: Optional[List[str]] = None,
        date: Optional[str] = None
    ) -> List[MatchData]:
        """获取实时比分"""
        conn = self._get_connection()
        cursor = conn.cursor()

        query = "SELECT * FROM matches WHERE 1=1"
        params = []

        if leagues:
            query += f" AND league IN ({','.join(['?' for _ in leagues])})"
            params.extend(leagues)

        if date:
            query += " AND date = ?"
            params.append(date)

        query += " ORDER BY date DESC LIMIT 100"

        cursor.execute(query, params)
        rows = cursor.fetchall()
        conn.close()

        return [self._parse_row(row) for row in rows]

    async def get_fixtures(
        self,
        league: str,
        season: Optional[str] = None,
        team: Optional[str] = None,
        from_date: Optional[str] = None,
        to_date: Optional[str] = None
    ) -> List[MatchData]:
        """获取赛程"""
        conn = self._get_connection()
        cursor = conn.cursor()

        query = "SELECT * FROM matches WHERE league = ?"
        params = [league]

        if season:
            query += " AND season = ?"
            params.append(season)

        if team:
            query += " AND (home_team LIKE ? OR away_team LIKE ?)"
            params.extend([f"%{team}%", f"%{team}%"])

        if from_date:
            query += " AND date >= ?"
            params.append(from_date)

        if to_date:
            query += " AND date <= ?"
            params.append(to_date)

        cursor.execute(query, params)
        rows = cursor.fetchall()
        conn.close()

        return [self._parse_row(row) for row in rows]

    async def get_standings(
        self,
        league: str,
        season: Optional[str] = None
    ) -> List[StandingData]:
        """获取积分榜"""
        conn = self._get_connection()
        cursor = conn.cursor()

        query = "SELECT * FROM standings WHERE league = ?"
        params = [league]

        if season:
            query += " AND season = ?"
            params.append(season)

        query += " ORDER BY position"

        cursor.execute(query, params)
        rows = cursor.fetchall()
        conn.close()

        return [self._parse_standing(row) for row in rows]

    async def get_matches(
        self,
        league: str,
        season: Optional[str] = None,
        team: Optional[str] = None,
        limit: Optional[int] = None
    ) -> List[MatchData]:
        """获取历史比赛"""
        matches = await self.get_fixtures(league, season, team)
        if limit:
            matches = matches[:limit]
        return matches

    async def get_team(self, team_id: str) -> Optional[TeamData]:
        """获取球队信息"""
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM teams WHERE id = ? OR name = ?", (team_id, team_id))
        row = cursor.fetchone()
        conn.close()

        if row:
            return self._parse_team(row)
        return None

    async def get_players(
        self,
        team: Optional[str] = None,
        league: Optional[str] = None,
        season: Optional[str] = None
    ) -> List[PlayerData]:
        """获取球员信息"""
        conn = self._get_connection()
        cursor = conn.cursor()

        query = "SELECT * FROM players WHERE 1=1"
        params = []

        if team:
            query += " AND team = ?"
            params.append(team)

        if league:
            query += " AND league = ?"
            params.append(league)

        cursor.execute(query, params)
        rows = cursor.fetchall()
        conn.close()

        return [self._parse_player(row) for row in rows]

    async def get_scorers(
        self,
        league: str,
        season: Optional[str] = None,
        limit: Optional[int] = None
    ) -> List[PlayerData]:
        """获取射手榜"""
        conn = self._get_connection()
        cursor = conn.cursor()

        query = "SELECT * FROM scorers WHERE league = ?"
        params = [league]

        if season:
            query += " AND season = ?"
            params.append(season)

        query += " ORDER BY goals DESC"

        if limit:
            query += f" LIMIT {limit}"

        cursor.execute(query, params)
        rows = cursor.fetchall()
        conn.close()

        return [self._parse_player(row) for row in rows]

    def _parse_row(self, row: tuple) -> MatchData:
        """解析数据库行"""
        # 假设列顺序: id, date, home_team, away_team, home_score, away_score, league, season, ...
        return MatchData(
            match_id=str(row[0]) if row[0] else None,
            date=str(row[1])[:10] if row[1] else None,
            home_team=str(row[2]) if len(row) > 2 else "",
            away_team=str(row[3]) if len(row) > 3 else "",
            home_score=row[4] if len(row) > 4 and row[4] is not None else None,
            away_score=row[5] if len(row) > 5 and row[5] is not None else None,
            league=str(row[6]) if len(row) > 6 else None,
            season=str(row[7]) if len(row) > 7 else None,
            source="database"
        )

    def _parse_standing(self, row: tuple) -> StandingData:
        """解析积分榜行"""
        return StandingData(
            position=row[0] if row[0] else 0,
            team=str(row[1]) if len(row) > 1 else "",
            played=row[2] if len(row) > 2 else 0,
            won=row[3] if len(row) > 3 else 0,
            drawn=row[4] if len(row) > 4 else 0,
            lost=row[5] if len(row) > 5 else 0,
            goals_for=row[6] if len(row) > 6 else 0,
            goals_against=row[7] if len(row) > 7 else 0,
            goal_difference=row[8] if len(row) > 8 else 0,
            points=row[9] if len(row) > 9 else 0,
            source="database"
        )

    def _parse_team(self, row: tuple) -> TeamData:
        """解析球队行"""
        return TeamData(
            team_id=str(row[0]) if row[0] else None,
            name=str(row[1]) if len(row) > 1 else "",
            country=str(row[2]) if len(row) > 2 else None,
            founded=row[3] if len(row) > 3 else None,
            venue=str(row[4]) if len(row) > 4 else None,
            source="database"
        )

    def _parse_player(self, row: tuple) -> PlayerData:
        """解析球员行"""
        return PlayerData(
            player_id=str(row[0]) if row[0] else None,
            name=str(row[1]) if len(row) > 1 else "",
            team=str(row[2]) if len(row) > 2 else None,
            position=str(row[3]) if len(row) > 3 else None,
            goals=row[4] if len(row) > 4 else None,
            assists=row[5] if len(row) > 5 else None,
            source="database"
        )


class StatsBombSource(BaseDataSource):
    """StatsBomb本地数据源"""

    def __init__(self, config: DataSourceConfig):
        super().__init__(config)
        self.data_dir = Path(config.base_url or "new_data/matches")

    def _load_competitions(self) -> List[Dict]:
        """加载赛事列表"""
        competitions_file = self.data_dir / "StatsBomb_competitions.json"
        if competitions_file.exists():
            with open(competitions_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        return []

    async def get_livescores(
        self,
        leagues: Optional[List[str]] = None,
        date: Optional[str] = None
    ) -> List[MatchData]:
        """获取实时比分 - StatsBomb是历史数据"""
        return []

    async def get_fixtures(
        self,
        league: str,
        season: Optional[str] = None,
        team: Optional[str] = None,
        from_date: Optional[str] = None,
        to_date: Optional[str] = None
    ) -> List[MatchData]:
        """获取赛程"""
        matches_dir = self.data_dir / "StatsBomb_matches"
        if not matches_dir.exists():
            return []

        matches = []
        for match_file in matches_dir.glob("*.json"):
            try:
                with open(match_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    match = self._parse_match(data)
                    if match:
                        matches.append(match)
            except:
                continue

        return matches

    async def get_standings(
        self,
        league: str,
        season: Optional[str] = None
    ) -> List[StandingData]:
        """获取积分榜"""
        return []

    async def get_matches(
        self,
        league: str,
        season: Optional[str] = None,
        team: Optional[str] = None,
        limit: Optional[int] = None
    ) -> List[MatchData]:
        """获取历史比赛"""
        return await self.get_fixtures(league, season, team)

    async def get_team(self, team_id: str) -> Optional[TeamData]:
        """获取球队信息"""
        return None

    async def get_players(
        self,
        team: Optional[str] = None,
        league: Optional[str] = None,
        season: Optional[str] = None
    ) -> List[PlayerData]:
        """获取球员信息"""
        return []

    async def get_scorers(
        self,
        league: str,
        season: Optional[str] = None,
        limit: Optional[int] = None
    ) -> List[PlayerData]:
        """获取射手榜"""
        return []

    def _parse_match(self, data: Dict) -> Optional[MatchData]:
        """解析StatsBomb比赛数据"""
        if not data:
            return None

        home_team = data.get('home_team', {})
        away_team = data.get('away_team', {})

        home_score = away_score = 0
        for event in data.get('events', []):
            if event.get('type', {}).get('name') == 'Shot':
                if event.get('shot', {}).get('outcome', {}).get('name') == 'Goal':
                    if event.get('team', {}).get('id') == home_team.get('id'):
                        home_score += 1
                    else:
                        away_score += 1

        return MatchData(
            match_id=str(data.get('match_id', '')),
            home_team=home_team.get('name', ''),
            away_team=away_team.get('name', ''),
            home_score=home_score,
            away_score=away_score,
            date=data.get('match_date', '')[:10],
            league=data.get('competition', {}).get('name', ''),
            season=data.get('season', {}).get('name', ''),
            source="statsbomb"
        )
