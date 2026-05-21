"""
后端API接口
提供数据查询服务
"""
from fastapi import FastAPI, Query, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import sqlite3
from pathlib import Path
from typing import Optional, List
import json

app = FastAPI(title="Football Data API", version="1.0.0")

# 跨域配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

DB_PATH = Path("d:/football_tools/data/football_v2.db")


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


# ==================== 联赛接口 ====================

@app.get("/api/leagues")
def get_leagues():
    """获取所有联赛列表"""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT league_id, league_code, name, name_cn, country, tier, league_type
        FROM leagues
        ORDER BY tier, country, name
    """)
    leagues = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return {"leagues": leagues, "total": len(leagues)}


@app.get("/api/leagues/{league_id}")
def get_league(league_id: int):
    """获取单个联赛详情"""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT l.*, COUNT(DISTINCT s.season_id) as seasons_count, COUNT(m.match_id) as matches_count
        FROM leagues l
        LEFT JOIN seasons s ON l.league_id = s.league_id
        LEFT JOIN matches m ON l.league_id = m.league_id
        WHERE l.league_id = ?
        GROUP BY l.league_id
    """, (league_id,))
    row = cursor.fetchone()
    conn.close()
    if not row:
        raise HTTPException(status_code=404, detail="联赛不存在")
    return dict(row)


@app.get("/api/leagues/{league_id}/seasons")
def get_league_seasons(league_id: int):
    """获取联赛的所有赛季"""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT s.season_id, s.season_name, s.year, s.status, COUNT(m.match_id) as matches_count
        FROM seasons s
        LEFT JOIN matches m ON s.season_id = m.season_id
        WHERE s.league_id = ?
        GROUP BY s.season_id
        ORDER BY s.year DESC
    """, (league_id,))
    seasons = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return {"seasons": seasons, "total": len(seasons)}


# ==================== 比赛接口 ====================

@app.get("/api/matches")
def get_matches(
    league_id: Optional[int] = None,
    season_id: Optional[int] = None,
    team_id: Optional[int] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    limit: int = Query(100, le=1000),
    offset: int = 0
):
    """获取比赛列表"""
    conn = get_db()
    cursor = conn.cursor()

    sql = """
        SELECT m.*, l.name_en as league_name, l.name_cn as league_name_cn,
               ht.name_en as home_team_name, at.name_en as away_team_name,
               s.season_name
        FROM matches m
        JOIN leagues l ON m.league_id = l.league_id
        JOIN teams ht ON m.home_team_id = ht.team_id
        JOIN teams at ON m.away_team_id = at.team_id
        LEFT JOIN seasons s ON m.season_id = s.season_id
        WHERE 1=1
    """
    params = []

    if league_id:
        sql += " AND m.league_id = ?"
        params.append(league_id)
    if season_id:
        sql += " AND m.season_id = ?"
        params.append(season_id)
    if team_id:
        sql += " AND (m.home_team_id = ? OR m.away_team_id = ?)"
        params.extend([team_id, team_id])
    if date_from:
        sql += " AND m.match_date >= ?"
        params.append(date_from)
    if date_to:
        sql += " AND m.match_date <= ?"
        params.append(date_to)

    sql += " ORDER BY m.match_date DESC, m.match_time LIMIT ? OFFSET ?"
    params.extend([limit, offset])

    cursor.execute(sql, params)
    matches = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return {"matches": matches, "limit": limit, "offset": offset}


@app.get("/api/matches/{match_id}")
def get_match(match_id: int):
    """获取单场比赛详情"""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT m.*, l.name as league_name, l.name_cn as league_name_cn,
               ht.name_en as home_team_name, at.name_en as away_team_name,
               s.season_name
        FROM matches m
        JOIN leagues l ON m.league_id = l.league_id
        JOIN teams ht ON m.home_team_id = ht.team_id
        JOIN teams at ON m.away_team_id = at.team_id
        LEFT JOIN seasons s ON m.season_id = s.season_id
        WHERE m.match_id = ?
    """, (match_id,))
    row = cursor.fetchone()
    conn.close()
    if not row:
        raise HTTPException(status_code=404, detail="比赛不存在")
    return dict(row)


# ==================== 球队接口 ====================

@app.get("/api/teams")
def get_teams(
    team_type: Optional[str] = None,
    country: Optional[str] = None,
    search: Optional[str] = None,
    limit: int = Query(100, le=500)
):
    """获取球队列表"""
    conn = get_db()
    cursor = conn.cursor()

    sql = "SELECT * FROM teams WHERE 1=1"
    params = []

    if team_type:
        sql += " AND team_type = ?"
        params.append(team_type)
    if country:
        sql += " AND country = ?"
        params.append(country)
    if search:
        sql += " AND (name_en LIKE ? OR name_cn LIKE ?)"
        params.extend([f"%{search}%", f"%{search}%"])

    sql += " ORDER BY name_en LIMIT ?"
    params.append(limit)

    cursor.execute(sql, params)
    teams = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return {"teams": teams, "total": len(teams)}


@app.get("/api/teams/{team_id}")
def get_team(team_id: int):
    """获取球队详情"""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT t.*,
               (SELECT COUNT(*) FROM matches WHERE home_team_id = t.team_id) as home_matches,
               (SELECT COUNT(*) FROM matches WHERE away_team_id = t.team_id) as away_matches
        FROM teams t
        WHERE t.team_id = ?
    """, (team_id,))
    row = cursor.fetchone()
    conn.close()
    if not row:
        raise HTTPException(status_code=404, detail="球队不存在")
    return dict(row)


@app.get("/api/teams/{team_id}/matches")
def get_team_matches(
    team_id: int,
    limit: int = Query(50, le=200)
):
    """获取球队的比赛记录"""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT m.*, l.name as league_name, l.name_cn as league_name_cn,
               ht.name_en as home_team_name, at.name_en as away_team_name
        FROM matches m
        JOIN leagues l ON m.league_id = l.league_id
        JOIN teams ht ON m.home_team_id = ht.team_id
        JOIN teams at ON m.away_team_id = at.team_id
        WHERE m.home_team_id = ? OR m.away_team_id = ?
        ORDER BY m.match_date DESC
        LIMIT ?
    """, (team_id, team_id, limit))
    matches = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return {"matches": matches, "total": len(matches)}


# ==================== 统计接口 ====================

@app.get("/api/stats/summary")
def get_stats_summary():
    """获取数据统计概览"""
    conn = get_db()
    cursor = conn.cursor()

    stats = {}

    cursor.execute("SELECT COUNT(*) FROM matches")
    stats['total_matches'] = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM teams")
    stats['total_teams'] = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM leagues")
    stats['total_leagues'] = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM seasons")
    stats['total_seasons'] = cursor.fetchone()[0]

    cursor.execute("""
        SELECT l.name_en as name, l.name_cn, COUNT(m.match_id) as matches
        FROM leagues l
        JOIN matches m ON l.league_id = m.league_id
        GROUP BY l.league_id
        ORDER BY matches DESC
        LIMIT 10
    """)
    stats['top_leagues'] = [dict(row) for row in cursor.fetchall()]

    conn.close()
    return stats


@app.get("/api/stats/league/{league_id}")
def get_league_stats(league_id: int, season_id: Optional[int] = None):
    """获取联赛统计"""
    conn = get_db()
    cursor = conn.cursor()

    stats = {}

    # 总场次
    sql = "SELECT COUNT(*) FROM matches WHERE league_id = ?"
    params = [league_id]
    if season_id:
        sql += " AND season_id = ?"
        params.append(season_id)
    cursor.execute(sql, params)
    stats['total_matches'] = cursor.fetchone()[0]

    # 进球统计
    sql = """
        SELECT SUM(home_goals) as home_goals, SUM(away_goals) as away_goals,
               AVG(home_goals) as avg_home_goals, AVG(away_goals) as avg_away_goals
        FROM matches WHERE league_id = ?
    """
    params = [league_id]
    if season_id:
        sql += " AND season_id = ?"
        params.append(season_id)
    cursor.execute(sql, params)
    row = cursor.fetchone()
    stats['goals'] = dict(row) if row else {}

    # 胜负统计
    sql = """
        SELECT
            SUM(CASE WHEN result = 'H' THEN 1 ELSE 0 END) as home_wins,
            SUM(CASE WHEN result = 'D' THEN 1 ELSE 0 END) as draws,
            SUM(CASE WHEN result = 'A' THEN 1 ELSE 0 END) as away_wins
        FROM matches WHERE league_id = ?
    """
    params = [league_id]
    if season_id:
        sql += " AND season_id = ?"
        params.append(season_id)
    cursor.execute(sql, params)
    row = cursor.fetchone()
    stats['results'] = dict(row) if row else {}

    conn.close()
    return stats


# ==================== 启动 ====================

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
