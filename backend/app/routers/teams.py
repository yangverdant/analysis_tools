"""
球队相关路由
"""

from fastapi import APIRouter
import sqlite3
import os
import json

router = APIRouter(prefix="/api/v1/teams", tags=["Teams"])

DATABASE_PATH = os.path.join(os.path.dirname(__file__), '..', '..', '..', 'data', 'football_v2.db')
LINKAGE_PATH = os.path.join(os.path.dirname(__file__), '..', '..', '..', 'data', 'linkage')

# 加载中文名称映射
TEAM_CN = {}
COUNTRY_CN = {}

def load_chinese_names():
    global TEAM_CN, COUNTRY_CN
    team_file = os.path.join(LINKAGE_PATH, 'team_chinese_names.json')
    if os.path.exists(team_file):
        with open(team_file, 'r', encoding='utf-8') as f:
            TEAM_CN = json.load(f)

    country_file = os.path.join(LINKAGE_PATH, 'country_chinese_names.json')
    if os.path.exists(country_file):
        with open(country_file, 'r', encoding='utf-8') as f:
            COUNTRY_CN = json.load(f)

load_chinese_names()

def get_db():
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def get_chinese_team_name(name):
    return TEAM_CN.get(name, name)

def get_chinese_country_name(name):
    return COUNTRY_CN.get(name, name)


@router.get("")
async def get_teams(league_id: int = None, country: str = None, limit: int = 100):
    """获取球队列表"""
    conn = get_db()
    cursor = conn.cursor()

    query = """
        SELECT t.team_id, t.name_en, t.name_cn, t.country, t.founded_year
        FROM teams t
        WHERE 1=1
    """
    params = []

    if league_id:
        query += " AND EXISTS (SELECT 1 FROM matches m WHERE m.league_id = ? AND (m.home_team_id = t.team_id OR m.away_team_id = t.team_id))"
        params.append(league_id)

    if country:
        query += " AND t.country LIKE ?"
        params.append(f"%{country}%")

    query += " ORDER BY t.name_en LIMIT ?"
    params.append(limit)

    cursor.execute(query, params)
    teams = [dict(row) for row in cursor.fetchall()]

    # 添加中文名称
    for team in teams:
        team['name_cn'] = team.get('name_cn') or get_chinese_team_name(team['name_en'])
        team['country_cn'] = get_chinese_country_name(team.get('country', ''))

    conn.close()
    return {"data": teams, "count": len(teams)}


@router.get("/{team_id}")
async def get_team_detail(team_id: int):
    """获取球队详情"""
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT t.*,
               (SELECT COUNT(*) FROM matches m WHERE m.home_team_id = t.team_id OR m.away_team_id = t.team_id) as total_matches
        FROM teams t
        WHERE t.team_id = ?
    """, (team_id,))
    team = cursor.fetchone()

    conn.close()

    if not team:
        return {"error": "Team not found"}

    result = dict(team)
    result['name_cn'] = result.get('name_cn') or get_chinese_team_name(result['name_en'])
    result['country_cn'] = get_chinese_country_name(result.get('country', ''))

    return {"data": result}


@router.get("/{team_id}/matches")
async def get_team_matches(team_id: int, limit: int = 50):
    """获取球队比赛记录"""
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT m.match_id, m.match_date, m.match_time, m.status,
               m.home_goals, m.away_goals,
               ht.name_en as home_team, ht.name_cn as home_team_cn,
               at.name_en as away_team, at.name_cn as away_team_cn,
               l.name_en as league, l.name_cn as league_cn, l.country as league_country,
               CASE WHEN m.home_team_id = ? THEN 'H' ELSE 'A' END as venue
        FROM matches m
        JOIN teams ht ON m.home_team_id = ht.team_id
        JOIN teams at ON m.away_team_id = at.team_id
        JOIN leagues l ON m.league_id = l.league_id
        WHERE m.home_team_id = ? OR m.away_team_id = ?
        ORDER BY m.match_date DESC
        LIMIT ?
    """, (team_id, team_id, team_id, limit))
    matches = [dict(row) for row in cursor.fetchall()]

    # 添加中文名称
    for match in matches:
        match['home_team_cn'] = match.get('home_team_cn') or get_chinese_team_name(match.get('home_team', ''))
        match['away_team_cn'] = match.get('away_team_cn') or get_chinese_team_name(match.get('away_team', ''))
        match['league_cn'] = match.get('league_cn') or get_chinese_team_name(match.get('league', ''))
        match['league_country_cn'] = get_chinese_country_name(match.get('league_country', ''))

    conn.close()
    return {"data": matches, "team_id": team_id}


@router.get("/{team_id}/form")
async def get_team_form(team_id: int, matches: int = 10):
    """获取球队近期状态"""
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT m.match_date, m.home_goals, m.away_goals,
               ht.name_en as home_team, ht.name_cn as home_team_cn,
               at.name_en as away_team, at.name_cn as away_team_cn,
               CASE WHEN m.home_team_id = ? THEN 'H' ELSE 'A' END as venue
        FROM matches m
        JOIN teams ht ON m.home_team_id = ht.team_id
        JOIN teams at ON m.away_team_id = at.team_id
        WHERE (m.home_team_id = ? OR m.away_team_id = ?) AND m.home_goals IS NOT NULL
        ORDER BY m.match_date DESC
        LIMIT ?
    """, (team_id, team_id, team_id, matches))
    results = cursor.fetchall()

    form = []
    wins, draws, losses = 0, 0, 0

    for row in results:
        r = dict(row)
        is_home = r['venue'] == 'H'
        team_goals = r['home_goals'] if is_home else r['away_goals']
        opp_goals = r['away_goals'] if is_home else r['home_goals']

        if team_goals > opp_goals:
            form.append('W')
            wins += 1
        elif team_goals < opp_goals:
            form.append('L')
            losses += 1
        else:
            form.append('D')
            draws += 1

    conn.close()
    return {
        "team_id": team_id,
        "form": form,
        "wins": wins,
        "draws": draws,
        "losses": losses,
        "points": wins * 3 + draws
    }