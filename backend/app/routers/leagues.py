"""
联赛相关路由
"""

from fastapi import APIRouter, Path
import sqlite3
import os
import json

router = APIRouter(prefix="/api/v1/leagues", tags=["Leagues"])

DATABASE_PATH = os.path.join(os.path.dirname(__file__), '..', '..', '..', 'data', 'football_v2.db')
LINKAGE_PATH = os.path.join(os.path.dirname(__file__), '..', '..', '..', 'data', 'linkage')

# 加载中文名称映射
def load_chinese_names():
    league_names = {}
    country_names = {}

    league_file = os.path.join(LINKAGE_PATH, 'league_chinese_names.json')
    if os.path.exists(league_file):
        with open(league_file, 'r', encoding='utf-8') as f:
            league_names = json.load(f)

    country_file = os.path.join(LINKAGE_PATH, 'country_chinese_names.json')
    if os.path.exists(country_file):
        with open(country_file, 'r', encoding='utf-8') as f:
            country_names = json.load(f)

    return league_names, country_names

LEAGUE_CN, COUNTRY_CN = load_chinese_names()

def get_db():
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def get_chinese_league_name(name):
    return LEAGUE_CN.get(name, name)

def get_chinese_country_name(name):
    if not name:
        return '国际'
    return COUNTRY_CN.get(name, name)


@router.get("")
async def get_leagues(country: str = None, league_type: str = None):
    """获取联赛列表"""
    conn = get_db()
    cursor = conn.cursor()

    query = "SELECT * FROM leagues WHERE 1=1"
    params = []

    if country:
        query += " AND country LIKE ?"
        params.append(f"%{country}%")

    if league_type:
        query += " AND competition_type = ?"
        params.append(league_type)

    query += " ORDER BY country, tier, name_en"

    cursor.execute(query, params)
    leagues = [dict(row) for row in cursor.fetchall()]

    # 补充country_cn
    for lg in leagues:
        if not lg.get('country_cn') and lg.get('country'):
            lg['country_cn'] = get_chinese_country_name(lg['country'])

    conn.close()
    return {"data": leagues}


# ==================== 具体路由必须放在前面 ====================


@router.get("/{league_id}/seasons")
async def get_league_seasons(league_id: int):
    """获取联赛赛季列表"""
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
    return {"data": seasons, "league_id": league_id}


@router.get("/{league_id}/seasons-stats")
async def get_league_seasons_stats(league_id: int):
    """获取联赛各赛季数据统计"""
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT s.season_name as season,
               COUNT(m.match_id) as matches_count,
               COUNT(DISTINCT m.home_team_id) as teams_count,
               SUM(CASE WHEN m.status = 'finished' THEN 1 ELSE 0 END) as finished_count,
               SUM(CASE WHEN m.status = 'scheduled' THEN 1 ELSE 0 END) as scheduled_count,
               SUM(CASE WHEN m.status = 'finished' AND (m.home_goals IS NULL OR m.away_goals IS NULL) THEN 1 ELSE 0 END) as missing_scores,
               SUM(CASE WHEN m.match_date IS NULL OR m.match_time IS NULL THEN 1 ELSE 0 END) as missing_dates
        FROM seasons s
        LEFT JOIN matches m ON s.season_id = m.season_id
        WHERE s.league_id = ?
        GROUP BY s.season_id, s.season_name
        ORDER BY s.season_name DESC
    """, (league_id,))

    seasons = []
    for row in cursor.fetchall():
        d = dict(row)
        if d['matches_count'] > 0:
            completeness = round(100 - (d['missing_scores'] + d['missing_dates']) / d['matches_count'] * 100)
            d['completeness'] = max(0, min(100, completeness))
        else:
            d['completeness'] = 0
        seasons.append(d)

    conn.close()
    return {"seasons": seasons, "total": len(seasons)}


@router.get("/{league_id}/matches")
async def get_league_matches(league_id: int, season: str = None, status: str = None, limit: int = 500):
    """获取联赛比赛列表"""
    conn = get_db()
    cursor = conn.cursor()

    query = """
        SELECT m.*, l.name_en as league_name, l.name_cn as league_name_cn,
               ht.name_en as home_team, ht.name_cn as home_team_cn,
               at.name_en as away_team, at.name_cn as away_team_cn,
               s.season_name,
               m.odds_home as home_odds, m.odds_draw as draw_odds, m.odds_away as away_odds
        FROM matches m
        JOIN leagues l ON m.league_id = l.league_id
        JOIN teams ht ON m.home_team_id = ht.team_id
        JOIN teams at ON m.away_team_id = at.team_id
        LEFT JOIN seasons s ON m.season_id = s.season_id
        WHERE m.league_id = ?
    """
    params = [league_id]

    if season:
        query += " AND s.season_name = ?"
        params.append(season)

    if status:
        query += " AND m.status = ?"
        params.append(status)

    query += " ORDER BY m.match_date DESC, m.match_time LIMIT ?"
    params.append(limit)

    cursor.execute(query, params)
    matches = [dict(row) for row in cursor.fetchall()]

    conn.close()
    return {"matches": matches, "total": len(matches)}


@router.get("/{league_id}/matches/latest-round")
async def get_latest_round(league_id: int, season: str = None):
    """获取最新一轮比赛"""
    conn = get_db()
    cursor = conn.cursor()

    if season:
        cursor.execute("""
            SELECT MAX(round_num) FROM matches m
            LEFT JOIN seasons s ON m.season_id = s.season_id
            WHERE m.league_id = ? AND s.season_name = ? AND m.round_num IS NOT NULL
        """, (league_id, season))
    else:
        cursor.execute("""
            SELECT MAX(round_num) FROM matches
            WHERE league_id = ? AND round_num IS NOT NULL
        """, (league_id,))

    max_round = cursor.fetchone()[0]

    if max_round is None:
        conn.close()
        return {"data": {"matches": [], "round": None}}

    if season:
        cursor.execute("""
            SELECT m.*, ht.name_en as home_team, ht.name_cn as home_team_cn,
                   at.name_en as away_team, at.name_cn as away_team_cn,
                   l.name_en as league, l.country as league_country
            FROM matches m
            JOIN teams ht ON m.home_team_id = ht.team_id
            JOIN teams at ON m.away_team_id = at.team_id
            JOIN leagues l ON m.league_id = l.league_id
            LEFT JOIN seasons s ON m.season_id = s.season_id
            WHERE m.league_id = ? AND m.round_num = ? AND s.season_name = ?
            ORDER BY m.match_date, m.match_time
        """, (league_id, max_round, season))
    else:
        cursor.execute("""
            SELECT m.*, ht.name_en as home_team, ht.name_cn as home_team_cn,
                   at.name_en as away_team, at.name_cn as away_team_cn,
                   l.name_en as league, l.country as league_country
            FROM matches m
            JOIN teams ht ON m.home_team_id = ht.team_id
            JOIN teams at ON m.away_team_id = at.team_id
            JOIN leagues l ON m.league_id = l.league_id
            WHERE m.league_id = ? AND m.round_num = ?
            ORDER BY m.match_date, m.match_time
        """, (league_id, max_round))

    matches = [dict(row) for row in cursor.fetchall()]
    conn.close()

    return {"data": {"matches": matches, "round": max_round}}


@router.get("/{league_id}/matches/grouped")
async def get_matches_grouped(league_id: int, season: str = None):
    """获取按日期分组的比赛"""
    conn = get_db()
    cursor = conn.cursor()

    if season:
        cursor.execute("""
            SELECT m.match_date, m.*,
                   ht.name_en as home_team, ht.name_cn as home_team_cn,
                   at.name_en as away_team, at.name_cn as away_team_cn
            FROM matches m
            JOIN teams ht ON m.home_team_id = ht.team_id
            JOIN teams at ON m.away_team_id = at.team_id
            LEFT JOIN seasons s ON m.season_id = s.season_id
            WHERE m.league_id = ? AND s.season_name = ?
            ORDER BY m.match_date, m.match_time
        """, (league_id, season))
    else:
        cursor.execute("""
            SELECT m.match_date, m.*,
                   ht.name_en as home_team, ht.name_cn as home_team_cn,
                   at.name_en as away_team, at.name_cn as away_team_cn
            FROM matches m
            JOIN teams ht ON m.home_team_id = ht.team_id
            JOIN teams at ON m.away_team_id = at.team_id
            WHERE m.league_id = ?
            ORDER BY m.match_date, m.match_time
        """, (league_id,))

    matches = [dict(row) for row in cursor.fetchall()]

    grouped = {}
    for match in matches:
        date = match['match_date']
        if date not in grouped:
            grouped[date] = []
        grouped[date].append(match)

    conn.close()
    return {"data": grouped}


@router.get("/{league_id}/matches/by-round/{round_num}")
async def get_matches_by_round(league_id: int, round_num: int, season: str = None):
    """获取指定轮次的比赛"""
    conn = get_db()
    cursor = conn.cursor()

    if season:
        cursor.execute("""
            SELECT m.*, ht.name_en as home_team, ht.name_cn as home_team_cn,
                   at.name_en as away_team, at.name_cn as away_team_cn,
                   l.name_en as league, l.country as league_country
            FROM matches m
            JOIN teams ht ON m.home_team_id = ht.team_id
            JOIN teams at ON m.away_team_id = at.team_id
            JOIN leagues l ON m.league_id = l.league_id
            LEFT JOIN seasons s ON m.season_id = s.season_id
            WHERE m.league_id = ? AND m.round_num = ? AND s.season_name = ?
            ORDER BY m.match_date, m.match_time
        """, (league_id, round_num, season))
    else:
        cursor.execute("""
            SELECT m.*, ht.name_en as home_team, ht.name_cn as home_team_cn,
                   at.name_en as away_team, at.name_cn as away_team_cn,
                   l.name_en as league, l.country as league_country
            FROM matches m
            JOIN teams ht ON m.home_team_id = ht.team_id
            JOIN teams at ON m.away_team_id = at.team_id
            JOIN leagues l ON m.league_id = l.league_id
            WHERE m.league_id = ? AND m.round_num = ?
            ORDER BY m.match_date, m.match_time
        """, (league_id, round_num))

    matches = [dict(row) for row in cursor.fetchall()]
    conn.close()

    return {"data": matches, "round": round_num}


@router.get("/{league_id}/standings")
async def get_league_standings(league_id: int, season: str = None):
    """获取联赛积分榜（含主客场完整统计）"""
    conn = get_db()
    cursor = conn.cursor()

    # 构建赛季过滤条件
    season_join = ""
    season_where = ""
    params = [league_id]

    if season:
        season_join = " LEFT JOIN seasons s ON m.season_id = s.season_id"
        season_where = " AND s.season_name = ?"
        params.append(season)

    # 主场统计
    home_query = f"""
        SELECT
            ht.team_id,
            ht.name_en as team_name,
            ht.name_cn as team_name_cn,
            COUNT(*) as home_played,
            SUM(CASE WHEN m.home_goals > m.away_goals THEN 1 ELSE 0 END) as home_wins,
            SUM(CASE WHEN m.home_goals = m.away_goals THEN 1 ELSE 0 END) as home_draws,
            SUM(CASE WHEN m.home_goals < m.away_goals THEN 1 ELSE 0 END) as home_losses,
            SUM(m.home_goals) as home_goals_for,
            SUM(m.away_goals) as home_goals_against
        FROM matches m
        JOIN teams ht ON m.home_team_id = ht.team_id
        {season_join}
        WHERE m.league_id = ? AND m.home_goals IS NOT NULL{season_where}
        GROUP BY ht.team_id
    """

    # 客场统计
    away_query = f"""
        SELECT
            at.team_id,
            COUNT(*) as away_played,
            SUM(CASE WHEN m.away_goals > m.home_goals THEN 1 ELSE 0 END) as away_wins,
            SUM(CASE WHEN m.away_goals = m.home_goals THEN 1 ELSE 0 END) as away_draws,
            SUM(CASE WHEN m.away_goals < m.home_goals THEN 1 ELSE 0 END) as away_losses,
            SUM(m.away_goals) as away_goals_for,
            SUM(m.home_goals) as away_goals_against
        FROM matches m
        JOIN teams at ON m.away_team_id = at.team_id
        {season_join}
        WHERE m.league_id = ? AND m.away_goals IS NOT NULL{season_where}
        GROUP BY at.team_id
    """

    cursor.execute(home_query, params)
    home_stats = {row['team_id']: dict(row) for row in cursor.fetchall()}

    cursor.execute(away_query, params)
    away_stats = {row['team_id']: dict(row) for row in cursor.fetchall()}

    # 合并主客场数据
    all_team_ids = set(home_stats.keys()) | set(away_stats.keys())
    standings = []

    for team_id in all_team_ids:
        h = home_stats.get(team_id, {})
        a = away_stats.get(team_id, {})

        team_name = h.get('team_name', a.get('team_name', ''))
        team_name_cn = h.get('team_name_cn', a.get('team_name_cn', ''))

        home_played = h.get('home_played', 0) or 0
        away_played = a.get('away_played', 0) or 0
        home_wins = h.get('home_wins', 0) or 0
        away_wins = a.get('away_wins', 0) or 0
        home_draws = h.get('home_draws', 0) or 0
        away_draws = a.get('away_draws', 0) or 0
        home_losses = h.get('home_losses', 0) or 0
        away_losses = a.get('away_losses', 0) or 0
        home_gf = h.get('home_goals_for', 0) or 0
        away_gf = a.get('away_goals_for', 0) or 0
        home_ga = h.get('home_goals_against', 0) or 0
        away_ga = a.get('away_goals_against', 0) or 0

        matches = home_played + away_played
        wins = home_wins + away_wins
        draws = home_draws + away_draws
        losses = home_losses + away_losses
        goals_for = home_gf + away_gf
        goals_against = home_ga + away_ga
        goal_diff = goals_for - goals_against
        points = wins * 3 + draws

        standings.append({
            'team_id': team_id,
            'team_name': team_name,
            'team_name_cn': team_name_cn,
            'matches': matches,
            'wins': wins,
            'draws': draws,
            'losses': losses,
            'goals_for': goals_for,
            'goals_against': goals_against,
            'goal_diff': goal_diff,
            'points': points,
            'home_played': home_played,
            'home_wins': home_wins,
            'home_draws': home_draws,
            'home_losses': home_losses,
            'away_played': away_played,
            'away_wins': away_wins,
            'away_draws': away_draws,
            'away_losses': away_losses,
        })

    # 按积分、净胜球、进球数排序
    standings.sort(key=lambda x: (x['points'], x['goal_diff'], x['goals_for']), reverse=True)

    for i, team in enumerate(standings, 1):
        team['rank'] = i

    conn.close()
    return {"data": standings, "league_id": league_id}


@router.get("/{league_id}/rounds")
async def get_league_rounds(league_id: int, season: str = None):
    """获取联赛轮次列表"""
    conn = get_db()
    cursor = conn.cursor()

    if season:
        cursor.execute("""
            SELECT DISTINCT m.round_num
            FROM matches m
            LEFT JOIN seasons s ON m.season_id = s.season_id
            WHERE m.league_id = ? AND m.round_num IS NOT NULL AND s.season_name = ?
            ORDER BY m.round_num
        """, (league_id, season))
    else:
        cursor.execute("""
            SELECT DISTINCT round_num
            FROM matches
            WHERE league_id = ? AND round_num IS NOT NULL
            ORDER BY round_num
        """, (league_id,))

    rounds = [row[0] for row in cursor.fetchall()]

    conn.close()
    return {"data": rounds, "league_id": league_id}


@router.get("/{league_id}/detect-missing")
async def detect_league_missing(league_id: int):
    """检测联赛缺失数据"""
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT
            SUM(CASE WHEN m.status = 'finished' AND (m.home_goals IS NULL OR m.away_goals IS NULL) THEN 1 ELSE 0 END) as missing_scores,
            SUM(CASE WHEN m.match_date IS NULL OR m.match_time IS NULL THEN 1 ELSE 0 END) as missing_dates
        FROM matches m
        WHERE m.league_id = ?
    """, (league_id,))

    row = cursor.fetchone()
    missing_scores = row[0] or 0
    missing_dates = row[1] or 0

    conn.close()
    return {"success": True, "missing_scores": missing_scores, "missing_dates": missing_dates}


@router.get("/{league_id}/player-stats")
async def get_player_stats(league_id: int, season: str = None, stat_type: str = 'goals'):
    """获取球员统计数据"""
    conn = get_db()
    cursor = conn.cursor()

    # 暂时返回空数据
    conn.close()
    return {"data": []}


@router.get("/{league_id}/rules")
async def get_league_rules(league_id: int):
    """获取联赛规则"""
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM league_rules WHERE league_id = ?", (league_id,))
    rules = cursor.fetchone()

    conn.close()
    if rules:
        return {"data": dict(rules)}
    return {"data": None}


@router.get("/{league_id}/teams-season")
async def get_league_teams_season(league_id: int, season: str = None):
    """获取联赛某赛季球队列表"""
    conn = get_db()
    cursor = conn.cursor()

    if season:
        cursor.execute("""
            SELECT DISTINCT t.*,
                   (SELECT COUNT(*) FROM matches m2 LEFT JOIN seasons s2 ON m2.season_id = s2.season_id
                    WHERE (m2.home_team_id = t.team_id OR m2.away_team_id = t.team_id)
                    AND m2.league_id = ? AND s2.season_name = ?) as matches_played
            FROM teams t
            JOIN matches m ON (m.home_team_id = t.team_id OR m.away_team_id = t.team_id)
            LEFT JOIN seasons s ON m.season_id = s.season_id
            WHERE m.league_id = ? AND s.season_name = ?
            GROUP BY t.team_id
        """, (league_id, season, league_id, season))
    else:
        cursor.execute("""
            SELECT DISTINCT t.*,
                   (SELECT COUNT(*) FROM matches WHERE home_team_id = t.team_id) as matches_played
            FROM teams t
            JOIN matches m ON (m.home_team_id = t.team_id OR m.away_team_id = t.team_id)
            WHERE m.league_id = ?
            GROUP BY t.team_id
        """, (league_id,))

    teams = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return {"data": teams}


# ==================== 通用路由放在最后 ====================

@router.get("/{league_id:int}")
async def get_league_detail(league_id: int):
    """获取联赛详情（含规则和统计）"""
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM leagues WHERE league_id = ?", (league_id,))
    league = cursor.fetchone()

    if not league:
        conn.close()
        return {"error": "League not found"}

    result = dict(league)

    # 加载联赛规则
    cursor.execute("SELECT * FROM league_rules WHERE league_id = ?", (league_id,))
    rules = cursor.fetchone()
    if rules:
        result['rules'] = dict(rules)
    else:
        result['rules'] = None

    # 统计最近赛季的数据
    cursor.execute("""
        SELECT s.season_name,
               COUNT(m.match_id) as matches_count,
               COUNT(DISTINCT m.home_team_id) as teams_count
        FROM seasons s
        LEFT JOIN matches m ON s.season_id = m.season_id
        WHERE s.league_id = ?
        GROUP BY s.season_id
        ORDER BY s.season_name DESC
        LIMIT 1
    """, (league_id,))
    season_stats = cursor.fetchone()
    if season_stats:
        result['current_season'] = dict(season_stats)

    # 生成联赛介绍文本
    intro_parts = []
    country_cn = get_chinese_country_name(result.get('country', ''))
    name_cn = result.get('name_cn') or result.get('name_en', '')

    if result.get('country'):
        intro_parts.append(f"{country_cn}{'杯赛' if result.get('competition_type') == 'cup' else '联赛'}")

    if result.get('tier'):
        tier_map = {1: '顶级', 2: '第二级别', 3: '第三级别', 4: '第四级别', 5: '第五级别'}
        tier_str = tier_map.get(result['tier'], f'第{result["tier"]}级别')
        intro_parts.append(tier_str)

    teams_count = 0
    if result.get('rules') and result['rules'].get('teams_count'):
        teams_count = result['rules']['teams_count']
    elif season_stats:
        teams_count = season_stats['teams_count'] or 0

    if teams_count:
        intro_parts.append(f"{teams_count}支球队")

    result['intro'] = '，'.join(intro_parts) if intro_parts else ''

    # 生成赛制描述
    format_parts = []
    if rules:
        r = dict(rules)
        if r.get('teams_count'):
            format_parts.append(f"共{r['teams_count']}支球队参赛")
        if r.get('champions_league_spots'):
            format_parts.append(f"前{r['champions_league_spots']}名获得欧冠资格")
        if r.get('europa_league_spots'):
            format_parts.append(f"第{r['champions_league_spots']+1 if r.get('champions_league_spots') else ''}-{r['champions_league_spots']+r['europa_league_spots'] if r.get('champions_league_spots') else r['europa_league_spots']}名获得欧联资格")
        if r.get('conference_league_spots'):
            format_parts.append(f"获得欧会杯资格{r['conference_league_spots']}个名额")
        if r.get('relegation_spots'):
            format_parts.append(f"后{r['relegation_spots']}名降级")
        if r.get('promotion_spots'):
            format_parts.append(f"前{r['promotion_spots']}名升级")
        if r.get('playoff_spots'):
            format_parts.append(f"第{r.get('teams_count',0)-r['playoff_spots']+1}-{r.get('teams_count',0)}名参加保级附加赛")

    result['format_desc'] = '；'.join(format_parts) if format_parts else ''

    conn.close()
    return {"data": result}
