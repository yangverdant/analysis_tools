"""
杯赛相关路由
"""

from fastapi import APIRouter
import sqlite3
import os

router = APIRouter(prefix="/api/v1/cups", tags=["Cups"])

DATABASE_PATH = os.path.join(os.path.dirname(__file__), '..', '..', '..', 'data', 'football_v2.db')

def get_db():
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    return conn


@router.get("/{league_id}/seasons")
async def get_cup_seasons(league_id: int):
    """获取杯赛赛季列表"""
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT DISTINCT season_name
        FROM seasons
        WHERE league_id = ?
        ORDER BY season_name DESC
    """, (league_id,))
    seasons = [row[0] for row in cursor.fetchall()]

    conn.close()
    return {"data": seasons}


@router.get("/{league_id}/stages")
async def get_cup_stages(league_id: int, season: str = None):
    """获取杯赛阶段列表"""
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT DISTINCT round_stage, stage_type
        FROM matches
        WHERE league_id = ?
        ORDER BY round_stage
    """, (league_id,))
    stages = [dict(row) for row in cursor.fetchall()]

    conn.close()
    return {"data": stages}


@router.get("/{league_id}/matches")
async def get_cup_matches(league_id: int, season: str = None, stage: str = None):
    """获取杯赛比赛"""
    conn = get_db()
    cursor = conn.cursor()

    query = """
        SELECT m.match_id, m.match_date, m.match_time, m.round_stage,
               m.home_goals, m.away_goals, m.status,
               ht.name_en as home_team, ht.name_cn as home_team_cn,
               at.name_en as away_team, at.name_cn as away_team_cn
        FROM matches m
        JOIN teams ht ON m.home_team_id = ht.team_id
        JOIN teams at ON m.away_team_id = at.team_id
        WHERE m.league_id = ?
    """
    params = [league_id]

    if stage:
        query += " AND m.round_stage = ?"
        params.append(stage)

    query += " ORDER BY m.match_date, m.match_time"

    cursor.execute(query, params)
    matches = [dict(row) for row in cursor.fetchall()]

    conn.close()
    return {"data": matches}