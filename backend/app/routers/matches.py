"""
比赛相关路由
"""

from fastapi import APIRouter, Query
import sqlite3
import os
import json
from datetime import datetime, timedelta
from typing import Optional

router = APIRouter(prefix="/api/v1/matches", tags=["Matches"])

DATABASE_PATH = os.path.join(os.path.dirname(__file__), '..', '..', '..', 'data', 'football_v2.db')
LINKAGE_PATH = os.path.join(os.path.dirname(__file__), '..', '..', '..', 'data', 'linkage')

# 时区配置
TIMEZONE_OFFSETS = {
    'England': -7, 'Scotland': -7, 'Wales': -7, 'France': -7, 'Germany': -7,
    'Italy': -7, 'Spain': -7, 'Portugal': -7, 'Netherlands': -7, 'Belgium': -7,
    'Austria': -7, 'Switzerland': -7, 'Poland': -7, 'Czech Republic': -7,
    'Denmark': -7, 'Sweden': -7, 'Norway': -7, 'Finland': -6, 'Greece': -6,
    'Turkey': -6, 'Russia': -5, 'Ukraine': -6, 'Croatia': -7, 'Serbia': -7,
    'Romania': -6, 'Hungary': -7, 'Europe': -7,
    'China': 0, 'Japan': 1, 'Korea': 1, 'South Korea': 1, 'Australia': 2,
    'Saudi Arabia': -5, 'Qatar': -5, 'UAE': -4, 'Asia': 0,
    'USA': -13, 'Mexico': -14, 'Brazil': -11, 'Argentina': -11, 'Chile': -12,
    'Colombia': -13, 'Egypt': -6, 'South Africa': -6, 'Morocco': -8, 'Africa': -7,
    'International': -8, 'World': -8,
}

# 加载中文名称映射
def load_chinese_names():
    team_names = {}
    league_names = {}
    country_names = {}

    team_file = os.path.join(LINKAGE_PATH, 'team_chinese_names.json')
    if os.path.exists(team_file):
        with open(team_file, 'r', encoding='utf-8') as f:
            team_names = json.load(f)

    league_file = os.path.join(LINKAGE_PATH, 'league_chinese_names.json')
    if os.path.exists(league_file):
        with open(league_file, 'r', encoding='utf-8') as f:
            league_names = json.load(f)

    country_file = os.path.join(LINKAGE_PATH, 'country_chinese_names.json')
    if os.path.exists(country_file):
        with open(country_file, 'r', encoding='utf-8') as f:
            country_names = json.load(f)

    return team_names, league_names, country_names

TEAM_CN, LEAGUE_CN, COUNTRY_CN = load_chinese_names()

def get_db():
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def get_whitelist_league_ids(conn):
    """获取白名单联赛ID列表，空列表表示显示全部"""
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT item_id FROM user_favorites WHERE item_type = 'league'")
        return [int(row[0]) for row in cursor.fetchall()]
    except Exception:
        return []

def apply_whitelist_filter(query, params, conn, league_column='l.league_id'):
    """如果用户设置了联赛白名单，追加过滤条件"""
    fav_ids = get_whitelist_league_ids(conn)
    if fav_ids:
        placeholders = ','.join(['?'] * len(fav_ids))
        query += f" AND {league_column} IN ({placeholders})"
        params.extend(fav_ids)
    return query, params

def filter_dirty_matches(matches):
    """应用层过滤：移除占位符/测试球队"""
    invalid_keywords = ['W95', 'W100', 'W101', 'W50', '待定球队', '待定']
    return [m for m in matches
            if not any(kw in (m.get('home_team', '') or '') for kw in invalid_keywords)
            and not any(kw in (m.get('away_team', '') or '') for kw in invalid_keywords)
            and not (m.get('home_team', '') or '').startswith('W')
            and not (m.get('away_team', '') or '').startswith('W')
            and not (m.get('home_team', '') or '').startswith('Team ')
            and not (m.get('away_team', '') or '').startswith('Team ')]

def get_timezone_offset(country):
    if not country:
        return -8  # 国际赛事无国家信息时假设UTC
    return TIMEZONE_OFFSETS.get(country, -8)  # 未知国家也假设UTC

def convert_to_beijing_time(match_date, match_time, country, time_type='local'):
    """时间转换"""
    if not match_time:
        return {'beijing_time': None, 'beijing_datetime': None, 'local_time': None, 'offset': 0}

    try:
        from datetime import datetime, timedelta

        if time_type == 'utc':
            offset = -8  # UTC→Beijing: +8h
        elif time_type == 'beijing':
            offset = 0  # Already Beijing time
        else:
            offset = get_timezone_offset(country)

        time_parts = match_time.split(':')
        hour, minute = int(time_parts[0]), int(time_parts[1]) if len(time_parts) > 1 else 0

        date_parts = match_date.split('-') if match_date else None
        year = int(date_parts[0]) if date_parts else 2024
        month = int(date_parts[1]) if date_parts else 1
        day = int(date_parts[2]) if date_parts else 1

        local_dt = datetime(year, month, day, hour, minute)
        beijing_dt = local_dt - timedelta(hours=offset)

        return {
            'beijing_time': beijing_dt.strftime('%H:%M'),
            'beijing_datetime': beijing_dt.strftime('%Y-%m-%d %H:%M'),
            'beijing_date': beijing_dt.strftime('%Y-%m-%d'),
            'local_time': match_time,
            'local_date': match_date,
            'offset': offset,
            'date_changed': beijing_dt.date() != local_dt.date()
        }
    except:
        return {'beijing_time': match_time, 'beijing_datetime': f"{match_date} {match_time}", 'local_time': match_time}

def get_chinese_team_name(name):
    return TEAM_CN.get(name, name)

def get_chinese_league_name(name):
    return LEAGUE_CN.get(name, name)

def get_chinese_country_name(name):
    if not name:
        return '国际'
    return COUNTRY_CN.get(name, name)


@router.get("/today")
async def get_today_matches():
    """获取今日比赛（包含简要分析）"""
    conn = get_db()
    cursor = conn.cursor()

    # 北京时间"今天"可能跨两个UTC日期(北京0:00=UTC前一天16:00)
    # 所以查 match_date 在 yesterday~tomorrow 范围，转北京时间后再过滤
    from backend.app.core.time_utils import now_beijing, yesterday_beijing, tomorrow_beijing
    now_bj = now_beijing()
    bj_today = now_bj.strftime('%Y-%m-%d')
    bj_yesterday = yesterday_beijing()
    bj_tomorrow = tomorrow_beijing()

    query = """
        SELECT m.match_id, m.match_date, m.match_time, m.time_type,
               l.name_en as league, l.name_cn as league_cn, l.country as league_country, l.league_id,
               m.home_team_id, m.away_team_id,
               ht.name_en as home_team, ht.name_cn as home_team_cn,
               at.name_en as away_team, at.name_cn as away_team_cn,
               m.home_goals, m.away_goals, m.status
        FROM matches m
        JOIN teams ht ON m.home_team_id = ht.team_id
        JOIN teams at ON m.away_team_id = at.team_id
        JOIN leagues l ON m.league_id = l.league_id
        WHERE m.match_date IN (?, ?, ?)
          AND ht.name_en NOT LIKE 'W%'
          AND at.name_en NOT LIKE 'W%'
          AND ht.name_en NOT LIKE '待定%'
          AND at.name_en NOT LIKE '待定%'
          AND ht.name_en NOT LIKE 'Team %'
          AND at.name_en NOT LIKE 'Team %'
          AND ht.name_en NOT LIKE 'Team %'
          AND at.name_en NOT LIKE 'Team %'
    """
    params = [bj_yesterday, bj_today, bj_tomorrow]
    query, params = apply_whitelist_filter(query, params, conn)
    query += " ORDER BY m.match_date, m.match_time"
    cursor.execute(query, params)
    all_matches = [dict(row) for row in cursor.fetchall()]

    # 转北京时间后过滤: 今天全天 + 明天12:00之前(凌晨/早场比赛算"今日")
    matches = []
    for match in all_matches:
        time_type = match.get('time_type', 'local')
        time_info = convert_to_beijing_time(match['match_date'], match['match_time'], match.get('league_country', ''), time_type)
        bj_date = time_info.get('beijing_date', match['match_date'])
        bj_time = time_info.get('beijing_time', '')
        # 保留: 今天全天的 + 明天12:00之前的
        if bj_date == bj_today:
            include = True
        elif bj_date == bj_tomorrow and bj_time and bj_time < '12:00':
            include = True
        else:
            include = False

        if include:
            match['beijing_time'] = time_info['beijing_time']
            match['beijing_datetime'] = time_info['beijing_datetime']
            match['beijing_date'] = bj_date
            match['local_time'] = time_info['local_time']
            match['local_date'] = time_info.get('local_date', match['match_date'])
            match['date_changed'] = time_info.get('date_changed', False)
            match['time_type'] = time_type
            matches.append(match)

    # 先解析中文名(去重需要用CN名作为key)
    for match in matches:
        match['home_team_cn'] = match.get('home_team_cn') or get_chinese_team_name(match['home_team'])
        match['away_team_cn'] = match.get('away_team_cn') or get_chinese_team_name(match['away_team'])
        match['league_cn'] = match.get('league_cn') or get_chinese_league_name(match['league'])
        match['league_country_cn'] = get_chinese_country_name(match['league_country'])

    # 去重: 同一天同一对球队可能来自不同数据源(如世界杯 vs World Championship)
    # 使用CN名去重(因为"Bosnia and Herzegovina"和"Bosnia & Herzegovina"映射到同一个"波黑")
    # 优先保留较低league_id(主数据源)
    seen = {}
    deduped = []
    for match in matches:
        home_cn = match.get('home_team_cn', match.get('home_team', ''))
        away_cn = match.get('away_team_cn', match.get('away_team', ''))
        date = match.get('beijing_date', match['match_date'])
        key = (home_cn, away_cn, date)
        if key in seen:
            prev_idx = seen[key]
            prev = deduped[prev_idx]
            # 优先: 较低league_id(主数据源)
            if match.get('league_id', 99999) < prev.get('league_id', 99999):
                deduped[prev_idx] = match
        else:
            seen[key] = len(deduped)
            deduped.append(match)
    matches = deduped

    # 导入Elo分析器获取简要预测
    from ..analytics.elo import EloAnalyzer
    db_path = os.path.join(os.path.dirname(__file__), '..', '..', 'data', 'football_v2.db')
    elo_analyzer = EloAnalyzer(db_path)

    for match in matches:
        # CN names already resolved above in dedup phase

        # 添加简要分析（Elo + 简单预测）
        try:
            elo_pred = elo_analyzer.calculate_match_elo_prediction(
                match['home_team_id'], match['away_team_id'], conn
            )
            match['home_elo'] = round(elo_pred.get('home_elo', 0))
            match['away_elo'] = round(elo_pred.get('away_elo', 0))
            probs = elo_pred.get('predictions', {})
            match['home_win_prob'] = round(probs.get('home_win', 0.33) * 100)
            match['draw_prob'] = round(probs.get('draw', 0.33) * 100)
            match['away_win_prob'] = round(probs.get('away_win', 0.33) * 100)
            # 简要分析文本
            elo_diff = elo_pred.get('elo_diff', 0)
            if elo_diff > 100:
                match['analysis_summary'] = '主队明显占优'
            elif elo_diff > 50:
                match['analysis_summary'] = '主队略占优势'
            elif elo_diff < -100:
                match['analysis_summary'] = '客队明显占优'
            elif elo_diff < -50:
                match['analysis_summary'] = '客队略占优势'
            else:
                match['analysis_summary'] = '实力接近'
        except Exception:
            match['home_elo'] = None
            match['away_elo'] = None
            match['home_win_prob'] = None
            match['draw_prob'] = None
            match['away_win_prob'] = None
            match['analysis_summary'] = None

    conn.close()
    return {"data": matches, "current_date": bj_today}


@router.get("/date-range")
async def get_matches_by_date_range(from_date: str = Query(...), to_date: str = Query(...)):
    """获取日期范围内的比赛（支持联赛白名单过滤）"""
    conn = get_db()
    cursor = conn.cursor()

    # 构建SQL
    base_query = """
        SELECT m.match_id, m.match_date, m.match_time, m.time_type,
               m.home_team_id, m.away_team_id,
               l.name_en as league, l.name_cn as league_cn, l.country as league_country, l.league_id,
               ht.name_en as home_team, ht.name_cn as home_team_cn,
               at.name_en as away_team, at.name_cn as away_team_cn,
               m.home_goals, m.away_goals, m.status
        FROM matches m
        JOIN teams ht ON m.home_team_id = ht.team_id
        JOIN teams at ON m.away_team_id = at.team_id
        JOIN leagues l ON m.league_id = l.league_id
        WHERE m.match_date >= ? AND m.match_date <= ?
          AND ht.name_en NOT LIKE 'W%'
          AND at.name_en NOT LIKE 'W%'
          AND ht.name_en NOT LIKE '待定%'
          AND at.name_en NOT LIKE '待定%'
          AND ht.name_en NOT LIKE 'Team %'
          AND at.name_en NOT LIKE 'Team %'
          AND ht.name_en NOT LIKE 'Team %'
          AND at.name_en NOT LIKE 'Team %'
    """
    params = [from_date, to_date]

    # 白名单过滤
    base_query, params = apply_whitelist_filter(base_query, params, conn)

    base_query += " ORDER BY m.match_date, m.match_time, m.league_id"

    cursor.execute(base_query, params)
    matches = [dict(row) for row in cursor.fetchall()]

    # 先解析中文名(去重需要用CN名作为key)
    for match in matches:
        match['home_team_cn'] = match.get('home_team_cn') or get_chinese_team_name(match['home_team'])
        match['away_team_cn'] = match.get('away_team_cn') or get_chinese_team_name(match['away_team'])
        match['league_cn'] = match.get('league_cn') or get_chinese_league_name(match['league'])
        match['league_country_cn'] = get_chinese_country_name(match['league_country'])
        time_type = match.get('time_type', 'local')
        time_info = convert_to_beijing_time(match['match_date'], match['match_time'], match['league_country'], time_type)
        match['beijing_time'] = time_info['beijing_time']
        match['beijing_datetime'] = time_info['beijing_datetime']
        match['local_time'] = time_info['local_time']
        match['local_date'] = time_info.get('local_date', match['match_date'])
        match['date_changed'] = time_info.get('date_changed', False)
        match['time_type'] = time_type

    # 去重: 使用CN名(因为不同英文拼写可能映射同一中文)
    # 优先保留较低league_id(主数据源)
    seen = {}
    deduped = []
    for match in matches:
        home_cn = match.get('home_team_cn', match.get('home_team', ''))
        away_cn = match.get('away_team_cn', match.get('away_team', ''))
        date = match.get('match_date', '')
        key = (home_cn, away_cn, date)
        if key in seen:
            prev_idx = seen[key]
            prev = deduped[prev_idx]
            # 优先: 较低league_id(主数据源)
            if match.get('league_id', 99999) < prev.get('league_id', 99999):
                deduped[prev_idx] = match
        else:
            seen[key] = len(deduped)
            deduped.append(match)
    matches = deduped

    conn.close()
    return {"data": matches, "from": from_date, "to": to_date, "count": len(matches)}


@router.get("/date/{date}")
async def get_matches_by_date(date: str):
    """获取指定日期的比赛（按北京时间）"""
    conn = get_db()
    cursor = conn.cursor()

    from datetime import datetime as _dt, timedelta as _td
    dt = _dt.strptime(date, '%Y-%m-%d')
    prev_day = (dt - _td(days=1)).strftime('%Y-%m-%d')

    query = """
        SELECT m.match_id, m.match_date, m.match_time, m.time_type,
               m.home_team_id, m.away_team_id,
               l.name_en as league, l.name_cn as league_cn, l.country as league_country, l.league_id,
               ht.name_en as home_team, ht.name_cn as home_team_cn,
               at.name_en as away_team, at.name_cn as away_team_cn,
               m.home_goals, m.away_goals, m.status
        FROM matches m
        JOIN teams ht ON m.home_team_id = ht.team_id
        JOIN teams at ON m.away_team_id = at.team_id
        JOIN leagues l ON m.league_id = l.league_id
        WHERE m.match_date IN (?, ?)
          AND ht.name_en NOT LIKE 'W%'
          AND at.name_en NOT LIKE 'W%'
          AND ht.name_en NOT LIKE '待定%'
          AND at.name_en NOT LIKE '待定%'
          AND ht.name_en NOT LIKE 'Team %'
          AND at.name_en NOT LIKE 'Team %'
          AND ht.name_en NOT LIKE 'Team %'
          AND at.name_en NOT LIKE 'Team %'
    """
    params = [prev_day, date]
    query, params = apply_whitelist_filter(query, params, conn)
    query += " ORDER BY m.match_date, m.match_time"
    cursor.execute(query, params)
    all_matches = [dict(row) for row in cursor.fetchall()]

    # 转北京时间后过滤
    matches = []
    for match in all_matches:
        time_type = match.get('time_type', 'local')
        time_info = convert_to_beijing_time(match['match_date'], match['match_time'], match.get('league_country', ''), time_type)
        bj_date = time_info.get('beijing_date', match['match_date'])
        if bj_date == date:
            match['beijing_time'] = time_info['beijing_time']
            match['beijing_datetime'] = time_info['beijing_datetime']
            match['beijing_date'] = bj_date
            match['local_time'] = time_info['local_time']
            match['local_date'] = time_info.get('local_date', match['match_date'])
            match['date_changed'] = time_info.get('date_changed', False)
            match['time_type'] = time_type
            matches.append(match)

    for match in matches:
        match['home_team_cn'] = match.get('home_team_cn') or get_chinese_team_name(match['home_team'])
        match['away_team_cn'] = match.get('away_team_cn') or get_chinese_team_name(match['away_team'])
        match['league_cn'] = match.get('league_cn') or get_chinese_league_name(match['league'])
        match['league_country_cn'] = get_chinese_country_name(match['league_country'])

    conn.close()
    return {"data": matches, "date": date}


@router.get("/list")
async def get_matches_list(
    league_id: int = None,
    season: str = None,
    status: str = None,
    date_from: str = None,
    date_to: str = None,
    limit: int = 500
):
    """获取比赛列表（用于数据中心）"""
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
        WHERE 1=1
          AND ht.name_en NOT LIKE 'W%'
          AND at.name_en NOT LIKE 'W%'
          AND ht.name_en NOT LIKE '待定%'
          AND at.name_en NOT LIKE '待定%'
          AND ht.name_en NOT LIKE 'Team %'
          AND at.name_en NOT LIKE 'Team %'
    """
    params = []

    if league_id:
        query += " AND m.league_id = ?"
        params.append(league_id)
    if season:
        query += " AND s.season_name = ?"
        params.append(season)
    if status:
        query += " AND m.status = ?"
        params.append(status)
    if date_from:
        query += " AND m.match_date >= ?"
        params.append(date_from)
    if date_to:
        query += " AND m.match_date <= ?"
        params.append(date_to)

    # 白名单过滤
    query, params = apply_whitelist_filter(query, params, conn, 'm.league_id')

    query += " ORDER BY m.match_date DESC, m.match_time LIMIT ?"
    params.append(limit)

    cursor.execute(query, params)
    matches = [dict(row) for row in cursor.fetchall()]

    conn.close()
    return {"matches": matches, "total": len(matches)}


@router.get("/upcoming")
async def get_upcoming_matches(days: int = 7):
    """获取即将开始的比赛"""
    conn = get_db()
    cursor = conn.cursor()

    today = datetime.now().strftime('%Y-%m-%d')
    end_date = (datetime.now() + timedelta(days=days)).strftime('%Y-%m-%d')

    query = """
        SELECT m.match_id, m.match_date, m.match_time, m.time_type,
               m.home_team_id, m.away_team_id,
               l.name_en as league, l.name_cn as league_cn, l.country as league_country, l.league_id,
               ht.name_en as home_team, ht.name_cn as home_team_cn,
               at.name_en as away_team, at.name_cn as away_team_cn,
               m.home_goals, m.away_goals, m.status
        FROM matches m
        JOIN teams ht ON m.home_team_id = ht.team_id
        JOIN teams at ON m.away_team_id = at.team_id
        JOIN leagues l ON m.league_id = l.league_id
        WHERE m.match_date >= ? AND m.match_date <= ? AND m.status = 'scheduled'
          AND ht.name_en NOT LIKE 'W%'
          AND at.name_en NOT LIKE 'W%'
          AND ht.name_en NOT LIKE '待定%'
          AND at.name_en NOT LIKE '待定%'
          AND ht.name_en NOT LIKE 'Team %'
          AND at.name_en NOT LIKE 'Team %'
    """
    params = [today, end_date]
    query, params = apply_whitelist_filter(query, params, conn)
    query += " ORDER BY m.match_date, m.match_time"
    cursor.execute(query, params)
    matches = [dict(row) for row in cursor.fetchall()]

    # 先解析中文名(去重需要用CN名作为key)
    for match in matches:
        match['home_team_cn'] = match.get('home_team_cn') or get_chinese_team_name(match['home_team'])
        match['away_team_cn'] = match.get('away_team_cn') or get_chinese_team_name(match['away_team'])
        match['league_cn'] = match.get('league_cn') or get_chinese_league_name(match['league'])
        match['league_country_cn'] = get_chinese_country_name(match['league_country'])
        time_type = match.get('time_type', 'local')
        time_info = convert_to_beijing_time(match['match_date'], match['match_time'], match['league_country'], time_type)
        match['beijing_time'] = time_info['beijing_time']
        match['local_time'] = time_info['local_time']
        match['time_type'] = time_type

    # 去重: 使用CN名(因为不同英文拼写可能映射同一中文)
    # 优先保留较低league_id(主数据源)
    seen = {}
    deduped = []
    for match in matches:
        home_cn = match.get('home_team_cn', match.get('home_team', ''))
        away_cn = match.get('away_team_cn', match.get('away_team', ''))
        date = match.get('match_date', '')
        key = (home_cn, away_cn, date)
        if key in seen:
            prev_idx = seen[key]
            prev = deduped[prev_idx]
            if match.get('league_id', 99999) < prev.get('league_id', 99999):
                deduped[prev_idx] = match
        else:
            seen[key] = len(deduped)
            deduped.append(match)
    matches = deduped

    conn.close()
    return {"data": matches, "days": days}


@router.get("/{match_id}")
async def get_match_detail(match_id: str):
    """获取比赛详情"""
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT m.*, l.name_en as league, l.name_cn as league_cn, l.country as league_country,
               ht.name_en as home_team, ht.name_cn as home_team_cn,
               at.name_en as away_team, at.name_cn as away_team_cn
        FROM matches m
        JOIN teams ht ON m.home_team_id = ht.team_id
        JOIN teams at ON m.away_team_id = at.team_id
        JOIN leagues l ON m.league_id = l.league_id
        WHERE m.match_id = ?
    """, (match_id,))
    match = cursor.fetchone()

    conn.close()

    if not match:
        return {"error": "Match not found"}

    result = dict(match)
    result['home_team_cn'] = get_chinese_team_name(result['home_team'])
    result['away_team_cn'] = get_chinese_team_name(result['away_team'])
    result['league_cn'] = get_chinese_league_name(result['league'])

    return {"data": result}