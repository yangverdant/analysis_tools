"""
LangChain Tools for Football Analysis
提供比赛查询、球队分析、预测等工具
"""

import sqlite3
import json
import os
from typing import Optional, Type, Any
from pydantic import BaseModel, Field
from langchain.tools import BaseTool

# 数据库路径
DB_PATH = os.path.join(os.path.dirname(__file__), '..', '..', '..', '..', 'data', 'football_v2.db')


class MatchQueryInput(BaseModel):
    """比赛查询输入"""
    query_type: str = Field(description="查询类型: 'upcoming', 'finished', 'by_team', 'by_league', 'by_date'")
    team_name: Optional[str] = Field(default=None, description="球队名称")
    league_name: Optional[str] = Field(default=None, description="联赛名称")
    date: Optional[str] = Field(default=None, description="日期 YYYY-MM-DD")
    limit: int = Field(default=10, description="返回数量限制")


class MatchQueryTool(BaseTool):
    """比赛查询工具"""
    name: str = "match_query"
    description: str = "查询比赛信息，包括即将开始的比赛、已结束的比赛、某球队的比赛等"
    args_schema: Type[BaseModel] = MatchQueryInput

    def _run(self, query_type: str, team_name: Optional[str] = None,
             league_name: Optional[str] = None, date: Optional[str] = None,
             limit: int = 10) -> str:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        try:
            if query_type == 'upcoming':
                cursor.execute("""
                    SELECT m.match_date, m.match_time, ht.name_en as home, at.name_en as away,
                           l.name_en as league, m.status
                    FROM matches m
                    JOIN teams ht ON m.home_team_id = ht.team_id
                    JOIN teams at ON m.away_team_id = at.team_id
                    JOIN leagues l ON m.league_id = l.league_id
                    WHERE m.status = 'scheduled' AND m.match_date >= date('now')
                    ORDER BY m.match_date, m.match_time
                    LIMIT ?
                """, (limit,))

            elif query_type == 'finished':
                cursor.execute("""
                    SELECT m.match_date, ht.name_en as home, at.name_en as away,
                           m.home_goals, m.away_goals, l.name_en as league
                    FROM matches m
                    JOIN teams ht ON m.home_team_id = ht.team_id
                    JOIN teams at ON m.away_team_id = at.team_id
                    JOIN leagues l ON m.league_id = l.league_id
                    WHERE m.home_goals IS NOT NULL
                    ORDER BY m.match_date DESC
                    LIMIT ?
                """, (limit,))

            elif query_type == 'by_team' and team_name:
                cursor.execute("""
                    SELECT m.match_date, ht.name_en as home, at.name_en as away,
                           m.home_goals, m.away_goals, l.name_en as league, m.status
                    FROM matches m
                    JOIN teams ht ON m.home_team_id = ht.team_id
                    JOIN teams at ON m.away_team_id = at.team_id
                    JOIN leagues l ON m.league_id = l.league_id
                    WHERE ht.name_en LIKE ? OR at.name_en LIKE ?
                    ORDER BY m.match_date DESC
                    LIMIT ?
                """, (f'%{team_name}%', f'%{team_name}%', limit))

            elif query_type == 'by_league' and league_name:
                cursor.execute("""
                    SELECT m.match_date, m.match_time, ht.name_en as home, at.name_en as away,
                           m.home_goals, m.away_goals, m.status
                    FROM matches m
                    JOIN teams ht ON m.home_team_id = ht.team_id
                    JOIN teams at ON m.away_team_id = at.team_id
                    JOIN leagues l ON m.league_id = l.league_id
                    WHERE l.name_en LIKE ?
                    ORDER BY m.match_date DESC
                    LIMIT ?
                """, (f'%{league_name}%', limit))

            else:
                return json.dumps({"error": "Invalid query_type or missing parameters"})

            results = [dict(row) for row in cursor.fetchall()]
            return json.dumps(results, ensure_ascii=False, indent=2)

        finally:
            conn.close()


class TeamQueryInput(BaseModel):
    """球队查询输入"""
    team_name: str = Field(description="球队名称")
    info_type: str = Field(default="basic", description="信息类型: 'basic', 'form', 'stats'")


class TeamQueryTool(BaseTool):
    """球队查询工具"""
    name: str = "team_query"
    description: str = "查询球队信息，包括基本信息、近期状态、统计数据等"
    args_schema: Type[BaseModel] = TeamQueryInput

    def _run(self, team_name: str, info_type: str = "basic") -> str:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        try:
            # 查找球队
            cursor.execute("""
                SELECT team_id, name_en, name_cn, country
                FROM teams
                WHERE name_en LIKE ? OR name_cn LIKE ?
                LIMIT 1
            """, (f'%{team_name}%', f'%{team_name}%'))
            team = cursor.fetchone()

            if not team:
                return json.dumps({"error": f"Team not found: {team_name}"})

            team_id = team['team_id']
            result = {"team": dict(team)}

            if info_type == 'form':
                # 获取最近10场比赛
                cursor.execute("""
                    SELECT m.match_date, ht.name_en as home, at.name_en as away,
                           m.home_goals, m.away_goals,
                           CASE WHEN m.home_team_id = ? THEN 'H' ELSE 'A' END as venue
                    FROM matches m
                    JOIN teams ht ON m.home_team_id = ht.team_id
                    JOIN teams at ON m.away_team_id = at.team_id
                    WHERE (m.home_team_id = ? OR m.away_team_id = ?)
                    AND m.home_goals IS NOT NULL
                    ORDER BY m.match_date DESC
                    LIMIT 10
                """, (team_id, team_id, team_id))
                result['recent_matches'] = [dict(row) for row in cursor.fetchall()]

            return json.dumps(result, ensure_ascii=False, indent=2)

        finally:
            conn.close()


class PredictionInput(BaseModel):
    """预测输入"""
    home_team: str = Field(description="主队名称")
    away_team: str = Field(description="客队名称")
    league: Optional[str] = Field(default=None, description="联赛名称")


class PredictionTool(BaseTool):
    """比赛预测工具"""
    name: str = "match_prediction"
    description: str = "预测比赛结果，基于历史数据、球队状态等"
    args_schema: Type[BaseModel] = PredictionInput

    def _run(self, home_team: str, away_team: str, league: Optional[str] = None) -> str:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        try:
            # 获取两队历史交锋
            cursor.execute("""
                SELECT m.match_date, ht.name_en as home, at.name_en as away,
                       m.home_goals, m.away_goals
                FROM matches m
                JOIN teams ht ON m.home_team_id = ht.team_id
                JOIN teams at ON m.away_team_id = at.team_id
                WHERE (ht.name_en LIKE ? AND at.name_en LIKE ?)
                   OR (ht.name_en LIKE ? AND at.name_en LIKE ?)
                AND m.home_goals IS NOT NULL
                ORDER BY m.match_date DESC
                LIMIT 10
            """, (f'%{home_team}%', f'%{away_team}%', f'%{away_team}%', f'%{home_team}%'))
            h2h = [dict(row) for row in cursor.fetchall()]

            # 简单统计
            home_wins = sum(1 for m in h2h if m['home'] == home_team and m['home_goals'] > m['away_goals'])
            away_wins = sum(1 for m in h2h if m['away'] == away_team and m['away_goals'] > m['home_goals'])
            draws = sum(1 for m in h2h if m['home_goals'] == m['away_goals'])

            return json.dumps({
                "home_team": home_team,
                "away_team": away_team,
                "h2h_matches": len(h2h),
                "h2h_record": {"home_wins": home_wins, "draws": draws, "away_wins": away_wins},
                "recent_h2h": h2h[:5]
            }, ensure_ascii=False, indent=2)

        finally:
            conn.close()


class AnalysisInput(BaseModel):
    """分析输入"""
    match_id: Optional[str] = Field(default=None, description="比赛ID")
    home_team: Optional[str] = Field(default=None, description="主队名称")
    away_team: Optional[str] = Field(default=None, description="客队名称")


class AnalysisTool(BaseTool):
    """深度分析工具"""
    name: str = "match_analysis"
    description: str = "深度分析比赛，包括战术、球员状态、历史数据等"
    args_schema: Type[BaseModel] = AnalysisInput

    def _run(self, match_id: Optional[str] = None, home_team: Optional[str] = None,
             away_team: Optional[str] = None) -> str:
        # 这里可以调用现有的分析模块
        return json.dumps({
            "message": "Analysis tool ready",
            "match_id": match_id,
            "teams": f"{home_team} vs {away_team}" if home_team and away_team else None
        }, ensure_ascii=False)


class StandingsInput(BaseModel):
    """积分榜输入"""
    league_name: str = Field(description="联赛名称")
    season: Optional[str] = Field(default=None, description="赛季")


class StandingsTool(BaseTool):
    """积分榜查询工具"""
    name: str = "standings_query"
    description: str = "查询联赛积分榜"
    args_schema: Type[BaseModel] = StandingsInput

    def _run(self, league_name: str, season: Optional[str] = None) -> str:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        try:
            # 查找联赛
            cursor.execute("""
                SELECT league_id FROM leagues
                WHERE name_en LIKE ? OR name_cn LIKE ?
                LIMIT 1
            """, (f'%{league_name}%', f'%{league_name}%'))
            league = cursor.fetchone()

            if not league:
                return json.dumps({"error": f"League not found: {league_name}"})

            # 获取最新赛季的比赛数据来计算积分榜
            cursor.execute("""
                SELECT ht.name_en as team,
                       COUNT(*) as played,
                       SUM(CASE WHEN m.home_goals > m.away_goals THEN 1 ELSE 0 END) as wins,
                       SUM(CASE WHEN m.home_goals = m.away_goals THEN 1 ELSE 0 END) as draws,
                       SUM(CASE WHEN m.home_goals < m.away_goals THEN 1 ELSE 0 END) as losses,
                       SUM(m.home_goals) as gf,
                       SUM(m.away_goals) as ga
                FROM matches m
                JOIN teams ht ON m.home_team_id = ht.team_id
                WHERE m.league_id = ? AND m.home_goals IS NOT NULL
                GROUP BY ht.team_id
                ORDER BY (SUM(CASE WHEN m.home_goals > m.away_goals THEN 3 ELSE 0 END) +
                          SUM(CASE WHEN m.home_goals = m.away_goals THEN 1 ELSE 0 END)) DESC
                LIMIT 20
            """, (league['league_id'],))

            standings = []
            for i, row in enumerate(cursor.fetchall(), 1):
                d = dict(row)
                d['rank'] = i
                d['gd'] = d['gf'] - d['ga']
                d['points'] = d['wins'] * 3 + d['draws']
                standings.append(d)

            return json.dumps(standings, ensure_ascii=False, indent=2)

        finally:
            conn.close()


__all__ = [
    'MatchQueryTool',
    'TeamQueryTool',
    'PredictionTool',
    'AnalysisTool',
    'StandingsTool'
]