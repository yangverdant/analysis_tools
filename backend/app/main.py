"""
足球数据分析API - 主入口
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import sqlite3
import os
import json
from datetime import datetime, timedelta
from typing import Optional

# 数据库路径
DATABASE_PATH = os.path.join(os.path.dirname(__file__), '..', '..', 'data', 'football_v2.db')
LINKAGE_PATH = os.path.join(os.path.dirname(__file__), '..', '..', 'data', 'linkage')

# 国家/联赛时区映射（相对于北京时间的时差）
# 北京时间是 UTC+8
TIMEZONE_OFFSETS = {
    # 欧洲（夏季时间）
    'England': -7,      # BST (UTC+1), 北京时间+8, 差7小时
    'Scotland': -7,
    'Wales': -7,
    'France': -7,       # CET夏令时 (UTC+2)
    'Germany': -7,
    'Italy': -7,
    'Spain': -7,
    'Portugal': -7,     # WEST夏令时 (UTC+1)
    'Netherlands': -7,
    'Belgium': -7,
    'Austria': -7,
    'Switzerland': -7,
    'Poland': -7,
    'Czech Republic': -7,
    'Denmark': -7,
    'Sweden': -7,
    'Norway': -7,
    'Finland': -6,
    'Greece': -6,
    'Turkey': -6,
    'Russia': -5,
    'Ukraine': -6,
    'Croatia': -7,
    'Serbia': -7,
    'Romania': -6,
    'Hungary': -7,
    'Europe': -7,       # 欧洲比赛默认
    # 亚洲
    'China': 0,         # 北京时间
    'Japan': 1,         # UTC+9
    'Korea': 1,
    'South Korea': 1,
    'Australia': 2,     # 东部时间
    'Saudi Arabia': -5,
    'Qatar': -5,
    'UAE': -4,
    'Asia': 0,          # 亚洲比赛默认
    # 美洲
    'USA': -13,         # 东部时间
    'Mexico': -14,
    'Brazil': -11,
    'Argentina': -11,
    'Chile': -12,
    'Colombia': -13,
    # 非洲
    'Egypt': -6,
    'South Africa': -6,
    'Morocco': -8,
    'Africa': -7,
    # 其他
    None: 0,            # 未知默认为北京时间
}

def get_timezone_offset(country: Optional[str]) -> int:
    """获取国家相对于北京时间的时差"""
    if country is None:
        return 0
    return TIMEZONE_OFFSETS.get(country, 0)

def convert_to_beijing_time(match_date: str, match_time: str, country: Optional[str], time_type: str = 'local') -> dict:
    """
    将时间转换为北京时间
    time_type: 'local'(当地时间), 'beijing'(北京时间), 'utc'(UTC时间)
    返回: {'beijing_time': 'HH:MM', 'beijing_datetime': 'YYYY-MM-DD HH:MM', 'local_time': 'HH:MM', 'offset': int}
    """
    if not match_time:
        return {
            'beijing_time': None,
            'beijing_datetime': None,
            'local_time': None,
            'offset': 0
        }

    try:
        # 如果已经是北京时间，直接返回
        if time_type == 'beijing':
            return {
                'beijing_time': match_time,
                'beijing_datetime': f"{match_date} {match_time}" if match_date else None,
                'local_time': match_time,
                'offset': 0,
                'date_changed': False
            }

        # UTC时间转北京时间 (+8)
        if time_type == 'utc':
            offset = -8  # UTC比北京时间慢8小时
        else:  # 'local' - 当地时间
            offset = get_timezone_offset(country)

        # 解析时间
        time_parts = match_time.split(':')
        hour = int(time_parts[0])
        minute = int(time_parts[1]) if len(time_parts) > 1 else 0

        # 计算北京时间
        beijing_hour = hour - offset

        # 处理跨天
        date_parts = match_date.split('-') if match_date else None
        year = int(date_parts[0]) if date_parts else 2024
        month = int(date_parts[1]) if date_parts else 1
        day = int(date_parts[2]) if date_parts else 1

        from datetime import datetime, timedelta
        local_dt = datetime(year, month, day, hour, minute)
        beijing_dt = local_dt - timedelta(hours=offset)

        return {
            'beijing_time': beijing_dt.strftime('%H:%M'),
            'beijing_datetime': beijing_dt.strftime('%Y-%m-%d %H:%M'),
            'local_time': match_time,
            'offset': offset,
            'date_changed': beijing_dt.date() != local_dt.date()
        }
    except Exception as e:
        return {
            'beijing_time': match_time,
            'beijing_datetime': f"{match_date} {match_time}" if match_date else None,
            'local_time': match_time,
            'offset': 0,
            'error': str(e)
        }

# 加载中文名称映射
def load_chinese_names():
    """加载中文名称映射"""
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

def get_chinese_team_name(english_name):
    """获取球队中文名称"""
    return TEAM_CN.get(english_name, english_name)

def get_chinese_league_name(english_name):
    """获取联赛中文名称"""
    return LEAGUE_CN.get(english_name, english_name)

def get_chinese_country_name(english_name):
    """获取国家中文名称"""
    return COUNTRY_CN.get(english_name, english_name)

# 创建FastAPI应用
app = FastAPI(
    title="足球数据分析API",
    description="提供足球数据查询、分析和预测功能",
    version="1.0.0"
)

# CORS配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册数据源路由
from app.data_sources.routes import router as data_sources_router
app.include_router(data_sources_router, prefix="/api/v1")

# 注册分析模块路由
from app.analytics import analytics_router
app.include_router(analytics_router)


def get_db():
    """获取数据库连接"""
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    return conn


# ==================== 基础路由 ====================

@app.get("/")
async def root():
    """API根路径"""
    return {
        "message": "足球数据分析API",
        "version": "1.0.0",
        "docs": "/docs"
    }


@app.get("/api/v1/health")
async def health_check():
    """健康检查"""
    return {"status": "healthy", "team_cn_count": len(TEAM_CN), "gais_cn": TEAM_CN.get("GAIS", "NOT FOUND")}


# ==================== CSV 数据管理 ====================

import csv
from pathlib import Path

DATA_ROOT = os.path.join(os.path.dirname(__file__), '..', '..', 'data')

@app.get("/api/v1/csv/read")
async def read_csv_file(path: str):
    """读取CSV文件内容"""
    try:
        # 安全检查：确保路径在data目录下
        full_path = os.path.normpath(os.path.join(DATA_ROOT, path))
        if not full_path.startswith(os.path.normpath(DATA_ROOT)):
            return {"error": "非法路径"}

        if not os.path.exists(full_path):
            return {"error": "文件不存在", "path": path}

        # 尝试多种编码读取
        encodings = ['utf-8', 'utf-8-sig', 'latin-1', 'cp1252', 'iso-8859-1']
        content = None
        used_encoding = None

        for encoding in encodings:
            try:
                with open(full_path, 'r', encoding=encoding) as f:
                    reader = csv.DictReader(f)
                    rows = list(reader)
                    content = rows
                    used_encoding = encoding
                    break
            except UnicodeDecodeError:
                continue

        if content is None:
            return {"error": "无法读取文件，编码不支持"}

        return {
            "success": True,
            "data": content,
            "count": len(content),
            "encoding": used_encoding,
            "path": path
        }
    except Exception as e:
        return {"error": str(e)}


@app.post("/api/v1/csv/write")
async def write_csv_file(request: dict):
    """写入CSV文件"""
    try:
        path = request.get("path")
        data = request.get("data", [])

        if not path:
            return {"error": "缺少路径参数"}

        # 安全检查：确保路径在data目录下
        full_path = os.path.normpath(os.path.join(DATA_ROOT, path))
        if not full_path.startswith(os.path.normpath(DATA_ROOT)):
            return {"error": "非法路径"}

        # 确保目录存在
        os.makedirs(os.path.dirname(full_path), exist_ok=True)

        # 获取所有字段名
        fieldnames = set()
        for row in data:
            fieldnames.update(row.keys())
        fieldnames = sorted(list(fieldnames))

        # 写入CSV
        with open(full_path, 'w', encoding='utf-8', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(data)

        return {
            "success": True,
            "count": len(data),
            "path": path
        }
    except Exception as e:
        return {"error": str(e)}


@app.get("/api/v1/csv/list")
async def list_csv_files(league: str = None):
    """列出可用的CSV文件"""
    try:
        csv_files = []

        # 遍历data目录
        for root, dirs, files in os.walk(DATA_ROOT):
            # 跳过特定目录
            skip_dirs = ['openfootball', 'international_results', 'linkage', 'fifa_rankings',
                        'coaches', 'players', 'football_info', 'formations', 'season_info',
                        'league_rules', 'world_cup_2026', 'european_championship']
            if any(d in root for d in skip_dirs):
                continue

            for f in files:
                if f.endswith('.csv') and not f.endswith('_all.csv'):
                    rel_path = os.path.relpath(os.path.join(root, f), DATA_ROOT)
                    csv_files.append({
                        "name": f,
                        "path": rel_path.replace('\\', '/'),
                        "league": os.path.basename(root)
                    })

        # 按联赛筛选
        if league:
            csv_files = [f for f in csv_files if league in f['league']]

        return {
            "success": True,
            "files": csv_files,
            "count": len(csv_files)
        }
    except Exception as e:
        return {"error": str(e)}


@app.get("/api/v1/teams")
async def get_teams_list(league: str = None, country: str = None, missing_cn: bool = False):
    """获取球队列表，支持按联赛筛选"""
    conn = get_db()
    cursor = conn.cursor()

    try:
        query = """
            SELECT DISTINCT t.team_id, t.name_en, t.name_cn, t.team_type, t.country
            FROM teams t
        """
        params = []
        conditions = []

        # 如果指定了联赛，通过比赛记录筛选该联赛的球队
        if league:
            query = """
                SELECT DISTINCT t.team_id, t.name_en, t.name_cn, t.team_type, t.country
                FROM teams t
                JOIN matches m ON (t.team_id = m.home_team_id OR t.team_id = m.away_team_id)
                JOIN leagues l ON m.league_id = l.league_id
            """
            conditions.append("l.name_en LIKE ? OR l.league_code LIKE ?")
            params.extend([f"%{league}%", f"%{league}%"])

        if country:
            conditions.append("t.country = ?")
            params.append(country)

        if missing_cn:
            conditions.append("(t.name_cn IS NULL OR t.name_cn = '')")

        if conditions:
            query += " WHERE " + " AND ".join(conditions)

        query += " ORDER BY t.name_en"

        cursor.execute(query, params)
        teams = [dict(row) for row in cursor.fetchall()]

        return {
            "success": True,
            "teams": teams,
            "count": len(teams)
        }
    except Exception as e:
        return {"error": str(e)}
    finally:
        conn.close()


@app.put("/api/v1/teams/{team_id}")
async def update_team(team_id: int, request: dict):
    """更新球队信息"""
    conn = get_db()
    cursor = conn.cursor()

    try:
        name_cn = request.get("name_cn")
        team_type = request.get("team_type")
        country = request.get("country")

        cursor.execute("""
            UPDATE teams
            SET name_cn = ?, team_type = ?, country = ?
            WHERE team_id = ?
        """, (name_cn, team_type, country, team_id))

        conn.commit()

        return {"success": True, "team_id": team_id}
    except Exception as e:
        conn.rollback()
        return {"error": str(e)}
    finally:
        conn.close()


@app.post("/api/v1/teams/batch-update")
async def batch_update_teams(request: dict):
    """批量更新球队信息"""
    conn = get_db()
    cursor = conn.cursor()

    try:
        teams = request.get("teams", [])
        updated = 0

        for team in teams:
            if team.get("modified"):
                cursor.execute("""
                    UPDATE teams
                    SET name_cn = ?, team_type = ?, country = ?
                    WHERE team_id = ?
                """, (team.get("name_cn"), team.get("team_type"), team.get("country"), team.get("team_id")))
                updated += 1

        conn.commit()

        return {"success": True, "updated": updated}
    except Exception as e:
        conn.rollback()
        return {"error": str(e)}
    finally:
        conn.close()


# ==================== 联赛相关 ====================

@app.get("/api/v1/leagues")
async def get_leagues():
    """获取联赛列表 - 按知名度和等级排序"""
    conn = get_db()
    cursor = conn.cursor()

    # 定义联赛排序优先级
    # 五大联赛一级 > 五大联赛二级 > 其他知名甲级 > 其他乙级 > 其他
    league_priority = {
        # 五大联赛一级 (优先级 1-5)
        'Premier League': 1,
        'La Liga': 2,
        'Bundesliga': 3,
        'Serie A': 4,
        'Ligue 1': 5,
        # 五大联赛二级 (优先级 10-14)
        'Championship': 10,
        'Segunda Division': 11,
        '2. Bundesliga': 12,
        'Serie B': 13,
        'Ligue 2': 14,
        # 其他知名甲级联赛 (优先级 20-29)
        'Eredivisie': 20,
        'Primeira Liga': 21,
        'Belgian Pro League': 22,
        'Super Lig': 23,
        'Ekstraklasa': 24,
        'Eliteserien': 25,
        'Super League': 26,
        'Scottish Premiership': 27,
        'J1 League': 28,
        'A-League': 29,
        # 其他知名二级联赛 (优先级 30-39)
        'Eerste Divisie': 30,
        'League One': 31,
        'League Two': 32,
        '3. Liga': 33,
        'Scottish Championship': 34,
        'J2 League': 35,
        # 杯赛和国际赛事 (优先级 200+)
        'FA Cup': 200,
        'EFL Cup': 201,
        'DFB-Pokal': 202,
        'Copa del Rey': 203,
        'Coppa Italia': 204,
        'Coupe de France': 205,
        'Champions League': 210,
        'Europa League': 211,
        'Conference League': 212,
        'FIFA World Cup': 220,
        'World Cup Qualifiers': 221,
        'Euro': 222,
        'Copa America': 223,
        'Africa Cup of Nations': 224,
        'AFC Asian Cup': 225,
        'CONCACAF Gold Cup': 226,
    }

    cursor.execute("""
        SELECT league_id, league_code, name_en, name_cn, country, tier, competition_type as league_type
        FROM leagues
    """)

    leagues_data = []
    for row in cursor.fetchall():
        league = dict(row)
        league['name'] = league['name_en']
        if not league.get('name_cn'):
            league['name_cn'] = get_chinese_league_name(league['name_en'])
        league['country_cn'] = get_chinese_country_name(league['country']) if league.get('country') else None
        # 获取排序优先级，未定义的联赛按tier排序
        if league['name_en'] in league_priority:
            league['priority'] = league_priority[league['name']]
        else:
            # 未定义的联赛：联赛用50+，杯赛用250+
            if league.get('league_type') in ['cup', 'international']:
                league['priority'] = 250 + (league.get('tier') or 10)
            else:
                league['priority'] = 50 + (league.get('tier') or 10)
        leagues_data.append(league)

    # 按优先级排序
    leagues_data.sort(key=lambda x: x['priority'])

    conn.close()
    return {"data": leagues_data}


@app.get("/api/v1/seasons")
async def get_all_seasons():
    """获取所有可用赛季"""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT DISTINCT season_name FROM seasons
        ORDER BY season_name DESC
    """)
    seasons = [row['season_name'] for row in cursor.fetchall()]
    conn.close()
    return {"data": seasons}


@app.get("/api/v1/leagues/{league_id}")
async def get_league(league_id: int):
    """获取联赛详情"""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT league_id, league_code, name, country, tier, league_type
        FROM leagues WHERE league_id = ?
    """, (league_id,))
    league = cursor.fetchone()
    conn.close()
    if not league:
        return {"error": "联赛不存在"}

    league_data = dict(league)
    # 添加中文名称
    league_data['name_cn'] = get_chinese_league_name(league_data['name'])
    league_data['country_cn'] = get_chinese_country_name(league_data['country']) if league_data.get('country') else None

    return {"data": league_data}


@app.get("/api/v1/leagues/{league_id}/standings")
async def get_standings(league_id: int, season: str = None):
    """获取积分榜 - 按赛季筛选"""
    conn = get_db()
    cursor = conn.cursor()

    # 如果没有指定赛季，获取最新赛季
    if not season:
        cursor.execute('''
            SELECT s.season_name
            FROM seasons s
            WHERE s.league_id = ?
            ORDER BY s.season_name DESC
            LIMIT 1
        ''', (league_id,))
        result = cursor.fetchone()
        if result:
            season = result[0]
        else:
            return {"data": [], "season": None}

    # 构建积分榜 - 按赛季筛选
    query = """
    WITH team_stats AS (
        SELECT
            t.team_id,
            t.name_en as team_name,
            COUNT(*) as matches,
            SUM(CASE
                WHEN (m.home_team_id = t.team_id AND m.home_goals > m.away_goals) THEN 1
                WHEN (m.away_team_id = t.team_id AND m.away_goals > m.home_goals) THEN 1
                ELSE 0
            END) as wins,
            SUM(CASE WHEN m.home_goals = m.away_goals THEN 1 ELSE 0 END) as draws,
            SUM(CASE
                WHEN (m.home_team_id = t.team_id AND m.home_goals < m.away_goals) THEN 1
                WHEN (m.away_team_id = t.team_id AND m.away_goals < m.home_goals) THEN 1
                ELSE 0
            END) as losses,
            SUM(CASE WHEN m.home_team_id = t.team_id THEN m.home_goals ELSE m.away_goals END) as goals_for,
            SUM(CASE WHEN m.home_team_id = t.team_id THEN m.away_goals ELSE m.home_goals END) as goals_against
        FROM teams t
        JOIN matches m ON (t.team_id = m.home_team_id OR t.team_id = m.away_team_id)
        JOIN seasons s ON m.season_id = s.season_id
        WHERE m.league_id = ? AND s.season_name = ?
        AND m.home_goals IS NOT NULL AND m.away_goals IS NOT NULL
        GROUP BY t.team_id, t.name_en
    )
    SELECT
        team_id,
        team_name,
        matches,
        wins,
        draws,
        losses,
        goals_for,
        goals_against,
        goals_for - goals_against as goal_diff,
        wins * 3 + draws as points
    FROM team_stats
    ORDER BY points DESC, goal_diff DESC, goals_for DESC
    """

    cursor.execute(query, (league_id, season))
    standings = [dict(row) for row in cursor.fetchall()]

    # 添加排名和中文名称
    for i, team in enumerate(standings):
        team['rank'] = i + 1
        team['team_name_cn'] = get_chinese_team_name(team['team_name'])

    conn.close()
    return {"data": standings, "season": season}


@app.get("/api/v1/leagues/{league_id}/seasons")
async def get_league_seasons(league_id: int):
    """获取联赛可用赛季列表"""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT DISTINCT s.season_name
        FROM seasons s
        WHERE s.league_id = ?
        ORDER BY s.season_name DESC
    ''', (league_id,))
    seasons = [row[0] for row in cursor.fetchall()]
    conn.close()
    return {"data": seasons}


@app.get("/api/v1/leagues/{league_id}/rounds")
async def get_league_rounds(league_id: int, season: str = None):
    """获取联赛某赛季的轮次列表"""
    conn = get_db()
    cursor = conn.cursor()

    if not season:
        cursor.execute('''
            SELECT s.season_name
            FROM seasons s
            WHERE s.league_id = ?
            ORDER BY s.season_name DESC
            LIMIT 1
        ''', (league_id,))
        result = cursor.fetchone()
        season = result[0] if result else None

    if not season:
        conn.close()
        return {"data": [], "season": None}

    # 获取轮次列表
    cursor.execute('''
        SELECT DISTINCT m.round_num
        FROM matches m
        JOIN seasons s ON m.season_id = s.season_id
        WHERE m.league_id = ? AND s.season_name = ? AND m.round_num IS NOT NULL
        ORDER BY m.round_num
    ''', (league_id, season))
    rounds = [row[0] for row in cursor.fetchall() if row[0] is not None]
    conn.close()
    return {"data": rounds, "season": season}


@app.get("/api/v1/leagues/{league_id}/matches/by-round/{round_num}")
async def get_matches_by_round(league_id: int, round_num: int, season: str = None):
    """获取某轮次的比赛"""
    try:
        conn = get_db()
        cursor = conn.cursor()

        # 获取联赛信息
        cursor.execute("SELECT country, name_en as name FROM leagues WHERE league_id = ?", (league_id,))
        league_info = cursor.fetchone()
        league_country = league_info['country'] if league_info else None

        if not season:
            cursor.execute('''
                SELECT s.season_name
                FROM seasons s
                WHERE s.league_id = ?
                ORDER BY s.season_name DESC
                LIMIT 1
            ''', (league_id,))
            result = cursor.fetchone()
            season = result[0] if result else None

        if not season:
            conn.close()
            return {"data": [], "season": None, "round": round_num}

        cursor.execute('''
            SELECT
                m.match_id,
                m.match_date,
                m.match_time,
                m.round_num as round_stage,
                ht.team_id as home_team_id,
                at.team_id as away_team_id,
                ht.name_en as home_team,
                at.name_en as away_team,
                m.home_goals,
                m.away_goals,
                m.odds_home as home_odds,
                m.odds_draw as draw_odds,
                m.odds_away as away_odds,
                m.status
            FROM matches m
            JOIN teams ht ON m.home_team_id = ht.team_id
            JOIN teams at ON m.away_team_id = at.team_id
            JOIN seasons s ON m.season_id = s.season_id
            WHERE m.league_id = ? AND s.season_name = ? AND m.round_num = ?
            ORDER BY m.match_date, m.match_time
        ''', (league_id, season, round_num))
        matches = [dict(row) for row in cursor.fetchall()]

        for match in matches:
            match['home_team_cn'] = get_chinese_team_name(match['home_team'])
            match['away_team_cn'] = get_chinese_team_name(match['away_team'])
            match['beijing_time'] = convert_to_beijing_time(match['match_date'], match['match_time'], league_country)

        conn.close()
        return {"data": matches, "season": season, "round": round_num}
    except Exception as e:
        print(f"Error in get_matches_by_round: {e}")
        import traceback
        traceback.print_exc()
        return {"data": [], "season": season, "round": round_num, "error": str(e)}


@app.get("/api/v1/leagues/{league_id}/matches/latest-round")
async def get_latest_round_matches(league_id: int, season: str = None):
    """获取最新一轮比赛"""
    conn = get_db()
    cursor = conn.cursor()

    # 获取联赛国家
    cursor.execute("SELECT country, name_en as name FROM leagues WHERE league_id = ?", (league_id,))
    league_info = cursor.fetchone()
    league_country = league_info['country'] if league_info else None
    league_name = league_info['name'] if league_info else None

    # 如果没有指定赛季，获取最新赛季
    if not season:
        cursor.execute('''
            SELECT s.season_name
            FROM seasons s
            WHERE s.league_id = ?
            ORDER BY s.season_name DESC
            LIMIT 1
        ''', (league_id,))
        result = cursor.fetchone()
        if result:
            season = result[0]
        else:
            conn.close()
            return {"data": {"matches": [], "round": None, "season": None}}

    # 获取最新有比赛结果的日期
    cursor.execute('''
        SELECT m.match_date
        FROM matches m
        JOIN seasons s ON m.season_id = s.season_id
        WHERE m.league_id = ? AND s.season_name = ?
        AND m.home_goals IS NOT NULL AND m.away_goals IS NOT NULL
        ORDER BY m.match_date DESC
        LIMIT 1
    ''', (league_id, season))
    date_result = cursor.fetchone()

    if not date_result:
        # 如果没有已结束的比赛，获取最近的比赛
        cursor.execute('''
            SELECT m.match_date
            FROM matches m
            JOIN seasons s ON m.season_id = s.season_id
            WHERE m.league_id = ? AND s.season_name = ?
            ORDER BY m.match_date DESC
            LIMIT 1
        ''', (league_id, season))
        date_result = cursor.fetchone()

    if not date_result:
        conn.close()
        return {"data": {"matches": [], "round": None, "season": season}}

    # 获取最近的比赛
    cursor.execute('''
        SELECT
            m.match_id,
            m.match_date,
            m.match_time,
            ht.team_id as home_team_id,
            at.team_id as away_team_id,
            ht.name_en as home_team,
            at.name_en as away_team,
            m.home_goals,
            m.away_goals,
            m.odds_home as home_odds,
            m.odds_draw as draw_odds,
            m.odds_away as away_odds,
            m.status
        FROM matches m
        JOIN teams ht ON m.home_team_id = ht.team_id
        JOIN teams at ON m.away_team_id = at.team_id
        JOIN seasons s ON m.season_id = s.season_id
        WHERE m.league_id = ? AND s.season_name = ?
        ORDER BY m.match_date DESC, m.match_time
        LIMIT 20
    ''', (league_id, season))
    matches = [dict(row) for row in cursor.fetchall()]

    # 添加中文名称和北京时间
    for match in matches:
        match['home_team_cn'] = get_chinese_team_name(match['home_team'])
        match['away_team_cn'] = get_chinese_team_name(match['away_team'])
        match['league'] = league_name
        match['league_cn'] = get_chinese_league_name(league_name) if league_name else None
        # 转换北京时间
        time_info = convert_to_beijing_time(match['match_date'], match['match_time'], league_country)
        match['beijing_time'] = time_info['beijing_time']
        match['beijing_datetime'] = time_info['beijing_datetime']
        match['local_time'] = time_info['local_time']

    conn.close()
    return {"data": {"matches": matches, "round": None, "season": season}}


@app.get("/api/v1/leagues/{league_id}/matches")
async def get_league_matches(league_id: int, season: str = None, limit: int = 1000):
    """获取联赛比赛"""
    conn = get_db()
    cursor = conn.cursor()

    # 获取联赛信息
    cursor.execute("SELECT country, name_en, name_cn FROM leagues WHERE league_id = ?", (league_id,))
    league_info = cursor.fetchone()
    if not league_info:
        conn.close()
        return {"matches": [], "total": 0}

    league_country = league_info['country']
    league_name_en = league_info['name_en']
    league_name_cn = league_info['name_cn']

    if season:
        cursor.execute("""
            SELECT
                m.match_id,
                m.match_date,
                m.match_time,
                m.status,
                ht.name_en as home_team,
                ht.name_cn as home_team_cn,
                at.name_en as away_team,
                at.name_cn as away_team_cn,
                m.home_goals,
                m.away_goals,
                m.source as data_source
            FROM matches m
            JOIN teams ht ON m.home_team_id = ht.team_id
            JOIN teams at ON m.away_team_id = at.team_id
            JOIN seasons s ON m.season_id = s.season_id
            WHERE m.league_id = ? AND s.season_name = ?
            ORDER BY m.match_date DESC, m.match_time DESC
            LIMIT ?
        """, (league_id, season, limit))
    else:
        cursor.execute("""
            SELECT
                m.match_id,
                m.match_date,
                m.match_time,
                m.status,
                ht.name_en as home_team,
                ht.name_cn as home_team_cn,
                at.name_en as away_team,
                at.name_cn as away_team_cn,
                m.home_goals,
                m.away_goals,
                m.source as data_source
            FROM matches m
            JOIN teams ht ON m.home_team_id = ht.team_id
            JOIN teams at ON m.away_team_id = at.team_id
            WHERE m.league_id = ?
            ORDER BY m.match_date DESC, m.match_time DESC
            LIMIT ?
        """, (league_id, limit))
    matches = [dict(row) for row in cursor.fetchall()]

    # 添加联赛名称
    for match in matches:
        match['league_name'] = league_name_en
        match['league_name_cn'] = league_name_cn
        match['league_id'] = league_id
        # 确保中文名称存在
        if not match.get('home_team_cn'):
            match['home_team_cn'] = get_chinese_team_name(match['home_team'])
        if not match.get('away_team_cn'):
            match['away_team_cn'] = get_chinese_team_name(match['away_team'])

    conn.close()
    return {"matches": matches, "total": len(matches)}


# ==================== 球队相关 ====================

@app.get("/api/v1/teams")
async def get_teams(team_type: str = None, country: str = None, limit: int = 100):
    """获取球队列表"""
    conn = get_db()
    cursor = conn.cursor()

    query = "SELECT team_id, name_en, team_type, country FROM teams WHERE 1=1"
    params = []

    if team_type:
        query += " AND team_type = ?"
        params.append(team_type)
    if country:
        query += " AND country LIKE ?"
        params.append(f"%{country}%")

    query += f" ORDER BY name_en LIMIT {limit}"

    cursor.execute(query, params)
    teams = []
    for row in cursor.fetchall():
        team = dict(row)
        team['name_cn'] = get_chinese_team_name(team['name_en'])
        team['country_cn'] = get_chinese_country_name(team['country'])
        teams.append(team)
    conn.close()
    return {"data": teams}


@app.get("/api/v1/teams/{team_id}")
async def get_team(team_id: int):
    """获取球队详情"""
    conn = get_db()
    cursor = conn.cursor()

    # 基本信息
    cursor.execute("""
        SELECT team_id, name_en, team_type, country, stadium, founded_year
        FROM teams WHERE team_id = ?
    """, (team_id,))
    team = cursor.fetchone()

    if not team:
        conn.close()
        return {"error": "球队不存在"}

    team_data = dict(team)

    # 添加中文名称
    team_data['team_name_cn'] = get_chinese_team_name(team_data['name_en'])
    team_data['country_cn'] = get_chinese_country_name(team_data['country']) if team_data.get('country') else None

    # 统计信息
    cursor.execute("""
        SELECT
            COUNT(*) as total_matches,
            SUM(CASE
                WHEN (m.home_team_id = ? AND m.home_goals > m.away_goals) THEN 1
                WHEN (m.away_team_id = ? AND m.away_goals > m.home_goals) THEN 1
                ELSE 0
            END) as wins,
            SUM(CASE WHEN m.home_goals = m.away_goals THEN 1 ELSE 0 END) as draws,
            SUM(CASE
                WHEN (m.home_team_id = ? AND m.home_goals < m.away_goals) THEN 1
                WHEN (m.away_team_id = ? AND m.away_goals < m.home_goals) THEN 1
                ELSE 0
            END) as losses,
            SUM(CASE WHEN m.home_team_id = ? THEN m.home_goals ELSE m.away_goals END) as goals_for,
            SUM(CASE WHEN m.home_team_id = ? THEN m.away_goals ELSE m.home_goals END) as goals_against
        FROM matches m
        WHERE m.home_team_id = ? OR m.away_team_id = ?
    """, (team_id, team_id, team_id, team_id, team_id, team_id, team_id, team_id))

    stats = cursor.fetchone()
    if stats:
        team_data['stats'] = dict(stats)

    conn.close()
    return {"data": team_data}


@app.get("/api/v1/teams/{team_id}/matches")
async def get_team_matches(team_id: int, limit: int = 50):
    """获取球队历史战绩"""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT
            m.match_id,
            m.match_date,
            l.name_en as league,
            ht.name_en as home_team,
            at.name_en as away_team,
            m.home_goals,
            m.away_goals,
            CASE
                WHEN m.home_goals > m.away_goals THEN 'H'
                WHEN m.home_goals < m.away_goals THEN 'A'
                ELSE 'D'
            END as result,
            CASE
                WHEN (m.home_team_id = ? AND m.home_goals > m.away_goals) THEN 'W'
                WHEN (m.away_team_id = ? AND m.away_goals > m.home_goals) THEN 'W'
                WHEN m.home_goals = m.away_goals THEN 'D'
                ELSE 'L'
            END as team_result
        FROM matches m
        JOIN teams ht ON m.home_team_id = ht.team_id
        JOIN teams at ON m.away_team_id = at.team_id
        JOIN leagues l ON m.league_id = l.league_id
        WHERE m.home_team_id = ? OR m.away_team_id = ?
        ORDER BY m.match_date DESC
        LIMIT ?
    """, (team_id, team_id, team_id, team_id, limit))
    matches = [dict(row) for row in cursor.fetchall()]

    # 添加中文名称
    for m in matches:
        m['home_team_cn'] = get_chinese_team_name(m['home_team'])
        m['away_team_cn'] = get_chinese_team_name(m['away_team'])
        m['league_cn'] = get_chinese_league_name(m['league'])

    conn.close()
    return {"data": matches}


@app.get("/api/v1/teams/{team_id}/form")
async def get_team_form(team_id: int, matches: int = 10):
    """获取球队近期状态"""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT
            m.match_date,
            CASE
                WHEN (m.home_team_id = ? AND m.home_goals > m.away_goals) THEN 'W'
                WHEN (m.away_team_id = ? AND m.away_goals > m.home_goals) THEN 'W'
                WHEN m.home_goals = m.away_goals THEN 'D'
                ELSE 'L'
            END as result,
            CASE WHEN m.home_team_id = ? THEN m.home_goals ELSE m.away_goals END as goals_for,
            CASE WHEN m.home_team_id = ? THEN m.away_goals ELSE m.home_goals END as goals_against
        FROM matches m
        WHERE m.home_team_id = ? OR m.away_team_id = ?
        ORDER BY m.match_date DESC
        LIMIT ?
    """, (team_id, team_id, team_id, team_id, team_id, team_id, matches))

    form_data = cursor.fetchall()
    form_string = ''.join([row['result'] for row in form_data])

    wins = form_string.count('W')
    draws = form_string.count('D')
    losses = form_string.count('L')
    points = wins * 3 + draws

    total_gf = sum(row['goals_for'] or 0 for row in form_data)
    total_ga = sum(row['goals_against'] or 0 for row in form_data)

    conn.close()
    return {
        "data": {
            "form_string": form_string,
            "wins": wins,
            "draws": draws,
            "losses": losses,
            "points": points,
            "goals_for": total_gf,
            "goals_against": total_ga
        }
    }


@app.get("/api/v1/teams/{team_id}/schedule")
async def get_team_schedule(team_id: int, days: int = 14):
    """获取球队赛程密集度"""
    conn = get_db()
    cursor = conn.cursor()

    # 使用数据库当前日期
    current_date = get_current_match_date(conn)

    cursor.execute("""
        SELECT
            m.match_date,
            l.name_en as competition,
            ht.name_en as home_team,
            at.name_en as away_team
        FROM matches m
        JOIN teams ht ON m.home_team_id = ht.team_id
        JOIN teams at ON m.away_team_id = at.team_id
        JOIN leagues l ON m.league_id = l.league_id
        WHERE (m.home_team_id = ? OR m.away_team_id = ?)
        AND m.match_date >= ?
        AND m.home_goals IS NULL
        ORDER BY m.match_date
    """, (team_id, team_id, current_date))

    fixtures = [dict(row) for row in cursor.fetchall()]
    conn.close()

    intensity = "high" if len(fixtures) >= 5 else ("medium" if len(fixtures) >= 3 else "low")

    return {
        "data": {
            "matches_in_period": len(fixtures),
            "intensity": intensity,
            "fixtures": fixtures
        }
    }


# ==================== 比赛相关 ====================

def get_current_match_date(conn):
    """获取当前日期（实时系统日期）"""
    # 始终使用实际的当前日期
    return datetime.now().strftime('%Y-%m-%d')


@app.get("/api/v1/matches/list")
async def get_all_matches(limit: int = 500, status: str = '', date_from: str = '', date_to: str = ''):
    """获取全部比赛列表"""
    conn = get_db()
    cursor = conn.cursor()

    query = """
        SELECT
            m.match_id,
            m.match_date,
            m.match_time,
            m.status,
            l.name_en as league_name,
            l.name_cn as league_name_cn,
            l.league_id,
            m.home_team_id,
            m.away_team_id,
            ht.name_en as home_team,
            ht.name_cn as home_team_cn,
            at.name_en as away_team,
            at.name_cn as away_team_cn,
            m.home_goals,
            m.away_goals,
            m.source as data_source
        FROM matches m
        JOIN teams ht ON m.home_team_id = ht.team_id
        JOIN teams at ON m.away_team_id = at.team_id
        JOIN leagues l ON m.league_id = l.league_id
        WHERE 1=1
    """
    params = []

    if status:
        query += " AND m.status = ?"
        params.append(status)

    if date_from:
        query += " AND m.match_date >= ?"
        params.append(date_from)

    if date_to:
        query += " AND m.match_date <= ?"
        params.append(date_to)

    query += " ORDER BY m.match_date DESC, m.match_time DESC LIMIT ?"
    params.append(limit)

    cursor.execute(query, params)
    matches = [dict(row) for row in cursor.fetchall()]

    # 获取总数
    count_query = "SELECT COUNT(*) as total FROM matches WHERE 1=1"
    count_params = []
    if status:
        count_query += " AND status = ?"
        count_params.append(status)
    if date_from:
        count_query += " AND match_date >= ?"
        count_params.append(date_from)
    if date_to:
        count_query += " AND match_date <= ?"
        count_params.append(date_to)

    cursor.execute(count_query, count_params)
    total = cursor.fetchone()['total']

    conn.close()
    return {"matches": matches, "total": total}


@app.get("/api/v1/matches/today")
async def get_today_matches():
    """获取今日比赛（使用数据库最新日期）"""
    conn = get_db()
    cursor = conn.cursor()

    # 使用数据库中最新的比赛日期
    current_date = get_current_match_date(conn)

    cursor.execute("""
        SELECT
            m.match_id,
            m.match_date,
            m.match_time,
            m.time_type,
            l.name_en as league,
            l.country as league_country,
            m.home_team_id,
            m.away_team_id,
            ht.name_en as home_team,
            at.name_en as away_team,
            m.home_goals,
            m.away_goals
        FROM matches m
        JOIN teams ht ON m.home_team_id = ht.team_id
        JOIN teams at ON m.away_team_id = at.team_id
        JOIN leagues l ON m.league_id = l.league_id
        WHERE m.match_date = ?
        ORDER BY m.match_time
    """, (current_date,))
    matches = [dict(row) for row in cursor.fetchall()]

    # 添加中文名称和北京时间
    for match in matches:
        match['home_team_cn'] = get_chinese_team_name(match['home_team'])
        match['away_team_cn'] = get_chinese_team_name(match['away_team'])
        match['league_cn'] = get_chinese_league_name(match['league'])
        # 转换北京时间
        time_type = match['time_type'] if 'time_type' in match.keys() else 'local'
        time_info = convert_to_beijing_time(match['match_date'], match['match_time'], match['league_country'], time_type)
        match['beijing_time'] = time_info['beijing_time']
        match['beijing_datetime'] = time_info['beijing_datetime']
        match['local_time'] = time_info['local_time']

    conn.close()
    return {"data": matches, "current_date": current_date}


@app.get("/api/v1/matches/date/{date}")
async def get_matches_by_date(date: str):
    """获取指定日期的比赛"""
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT
            m.match_id,
            m.match_date,
            m.match_time,
            m.home_team_id,
            m.away_team_id,
            l.name_en as league,
            l.country as league_country,
            l.league_id,
            ht.name_en as home_team,
            at.name_en as away_team,
            m.home_goals,
            m.away_goals,
            m.status
        FROM matches m
        JOIN teams ht ON m.home_team_id = ht.team_id
        JOIN teams at ON m.away_team_id = at.team_id
        JOIN leagues l ON m.league_id = l.league_id
        WHERE m.match_date = ?
        ORDER BY m.match_time
    """, (date,))
    matches = [dict(row) for row in cursor.fetchall()]

    # 添加中文名称和北京时间
    for match in matches:
        match['home_team_cn'] = get_chinese_team_name(match['home_team'])
        match['away_team_cn'] = get_chinese_team_name(match['away_team'])
        match['league_cn'] = get_chinese_league_name(match['league'])
        # 转换北京时间
        time_info = convert_to_beijing_time(match['match_date'], match['match_time'], match['league_country'])
        match['beijing_time'] = time_info['beijing_time']
        match['beijing_datetime'] = time_info['beijing_datetime']
        match['local_time'] = time_info['local_time']

    conn.close()
    return {"data": matches, "date": date}


@app.get("/api/v1/matches/upcoming")
async def get_upcoming_matches(days: int = 7, limit: int = 50):
    """获取即将开始的比赛（未开始的比赛）"""
    conn = get_db()
    cursor = conn.cursor()

    # 获取当前日期（最新有结果的比赛日期）
    current_date = get_current_match_date(conn)

    cursor.execute("""
        SELECT
            m.match_id,
            m.match_date,
            m.match_time,
            m.time_type,
            l.name_en as league,
            l.country as league_country,
            ht.name_en as home_team,
            at.name_en as away_team,
            m.odds_home as home_odds,
            m.odds_draw as draw_odds,
            m.odds_away as away_odds
        FROM matches m
        JOIN teams ht ON m.home_team_id = ht.team_id
        JOIN teams at ON m.away_team_id = at.team_id
        JOIN leagues l ON m.league_id = l.league_id
        WHERE m.match_date >= ?
        AND m.home_goals IS NULL
        ORDER BY m.match_date, m.match_time
        LIMIT ?
    """, (current_date, limit))
    matches = [dict(row) for row in cursor.fetchall()]

    # 添加中文名称和北京时间
    for match in matches:
        match['home_team_cn'] = get_chinese_team_name(match['home_team'])
        match['away_team_cn'] = get_chinese_team_name(match['away_team'])
        match['league_cn'] = get_chinese_league_name(match['league'])
        # 转换北京时间
        time_type = match['time_type'] if 'time_type' in match.keys() else 'local'
        time_info = convert_to_beijing_time(match['match_date'], match['match_time'], match['league_country'], time_type)
        match['beijing_time'] = time_info['beijing_time']
        match['beijing_datetime'] = time_info['beijing_datetime']
        match['local_time'] = time_info['local_time']
        match['date_changed'] = time_info.get('date_changed', False)

    conn.close()
    return {"data": matches, "current_date": current_date}


# ==================== 排名相关 ====================

@app.get("/api/v1/rankings/fifa/national")
async def get_fifa_national_rankings(limit: int = 50):
    """获取FIFA国家队排名"""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT fr.team_id, fr.rank, fr.points, fr.rank_date, t.name_en as country
        FROM fifa_rankings fr
        LEFT JOIN teams t ON fr.team_id = t.team_id
        WHERE fr.rank_date = (SELECT MAX(rank_date) FROM fifa_rankings)
        ORDER BY fr.rank
        LIMIT ?
    """, (limit,))
    rankings = [dict(row) for row in cursor.fetchall()]

    # 添加中文名称
    for r in rankings:
        r['country_cn'] = get_chinese_team_name(r['country']) if r['country'] else None

    conn.close()
    return {"data": rankings}


@app.get("/api/v1/rankings/fifa/club")
async def get_fifa_club_rankings(limit: int = 50):
    """获取FIFA俱乐部排名"""
    conn = get_db()
    cursor = conn.cursor()

    # 检查表是否存在
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='fifa_club_rankings'")
    if not cursor.fetchone():
        conn.close()
        return {"data": [], "message": "俱乐部排名数据暂未导入"}

    cursor.execute("""
        SELECT club, country, rank, points, rank_date
        FROM fifa_club_rankings
        WHERE rank_date = (SELECT MAX(rank_date) FROM fifa_club_rankings)
        ORDER BY rank
        LIMIT ?
    """, (limit,))
    rankings = [dict(row) for row in cursor.fetchall()]

    # 添加中文名称
    for r in rankings:
        r['club_cn'] = get_chinese_team_name(r['club'])
        r['country_cn'] = get_chinese_country_name(r['country']) if r.get('country') else None

    conn.close()
    return {"data": rankings}


@app.get("/api/v1/matches/{match_id}")
async def get_match_detail(match_id: str):
    """获取比赛详情"""
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT
            m.match_id,
            m.match_date,
            m.match_time,
            m.home_goals,
            m.away_goals,
            m.odds_home as home_odds,
            m.odds_draw as draw_odds,
            m.odds_away as away_odds,
            m.home_xg,
            m.away_xg,
            l.league_id,
            l.name_en as league,
            l.country as league_country,
            ht.team_id as home_team_id,
            ht.name_en as home_team,
            at.team_id as away_team_id,
            at.name_en as away_team
        FROM matches m
        JOIN teams ht ON m.home_team_id = ht.team_id
        JOIN teams at ON m.away_team_id = at.team_id
        JOIN leagues l ON m.league_id = l.league_id
        WHERE m.match_id = ?
    """, (match_id,))

    match = cursor.fetchone()
    if not match:
        conn.close()
        return {"error": "比赛不存在"}

    match = dict(match)

    # 添加中文名称
    match['home_team_cn'] = get_chinese_team_name(match['home_team'])
    match['away_team_cn'] = get_chinese_team_name(match['away_team'])
    match['league_cn'] = get_chinese_league_name(match['league'])

    # 转换北京时间
    time_info = convert_to_beijing_time(match['match_date'], match['match_time'], match['league_country'])
    match['beijing_time'] = time_info['beijing_time']
    match['beijing_datetime'] = time_info['beijing_datetime']
    match['local_time'] = time_info['local_time']

    # 获取主队近期战绩
    cursor.execute("""
        SELECT match_date, home_team_id, away_team_id, home_goals, away_goals
        FROM matches
        WHERE (home_team_id = ? OR away_team_id = ?)
        AND match_date < ?
        ORDER BY match_date DESC
        LIMIT 5
    """, (match['home_team_id'], match['home_team_id'], match['match_date']))
    home_recent = [dict(row) for row in cursor.fetchall()]

    # 获取客队近期战绩
    cursor.execute("""
        SELECT match_date, home_team_id, away_team_id, home_goals, away_goals
        FROM matches
        WHERE (home_team_id = ? OR away_team_id = ?)
        AND match_date < ?
        ORDER BY match_date DESC
        LIMIT 5
    """, (match['away_team_id'], match['away_team_id'], match['match_date']))
    away_recent = [dict(row) for row in cursor.fetchall()]

    # 获取历史交锋
    cursor.execute("""
        SELECT match_date, home_team_id, away_team_id, home_goals, away_goals
        FROM matches
        WHERE ((home_team_id = ? AND away_team_id = ?)
           OR (home_team_id = ? AND away_team_id = ?))
        AND match_date < ?
        ORDER BY match_date DESC
        LIMIT 10
    """, (match['home_team_id'], match['away_team_id'],
          match['away_team_id'], match['home_team_id'], match['match_date']))
    h2h_matches = [dict(row) for row in cursor.fetchall()]

    conn.close()

    return {
        "data": match,
        "home_recent": home_recent,
        "away_recent": away_recent,
        "h2h_matches": h2h_matches
    }


# ==================== 分析相关 ====================

# Elo评分系统
ELO_K = 32  # K因子
DEFAULT_ELO = 1500  # 默认Elo分数

# 球队Elo缓存
team_elo_cache = {}

def get_elo_rating(team_id, conn):
    """获取球队Elo评分"""
    if team_id in team_elo_cache:
        return team_elo_cache[team_id]

    cursor = conn.cursor()
    # 基于历史比赛计算Elo
    cursor.execute("""
        SELECT
            m.match_date,
            m.home_team_id,
            m.away_team_id,
            m.home_goals,
            m.away_goals
        FROM matches m
        WHERE (m.home_team_id = ? OR m.away_team_id = ?)
        AND m.home_goals IS NOT NULL AND m.away_goals IS NOT NULL
        ORDER BY m.match_date
    """, (team_id, team_id))

    matches = cursor.fetchall()
    if not matches:
        return DEFAULT_ELO

    # 计算Elo
    elo = DEFAULT_ELO
    for match in matches:
        is_home = match['home_team_id'] == team_id
        opponent_id = match['away_team_id'] if is_home else match['home_team_id']

        # 获取对手Elo（简化处理，使用默认值）
        opponent_elo = DEFAULT_ELO

        # 计算期望得分
        expected = 1 / (1 + 10 ** ((opponent_elo - elo) / 400))

        # 实际得分
        if is_home:
            if match['home_goals'] > match['away_goals']:
                actual = 1
            elif match['home_goals'] < match['away_goals']:
                actual = 0
            else:
                actual = 0.5
        else:
            if match['away_goals'] > match['home_goals']:
                actual = 1
            elif match['away_goals'] < match['home_goals']:
                actual = 0
            else:
                actual = 0.5

        # 更新Elo
        elo = elo + ELO_K * (actual - expected)

    team_elo_cache[team_id] = elo
    return elo


def calculate_xg(home_team_id, away_team_id, conn):
    """计算预期进球(xG)"""
    cursor = conn.cursor()

    # 获取球队历史进球数据
    # 主队主场进攻力
    cursor.execute("""
        SELECT
            AVG(home_goals) as avg_home_goals,
            AVG(away_goals) as avg_conceded,
            COUNT(*) as matches
        FROM matches
        WHERE home_team_id = ? AND home_goals IS NOT NULL
    """, (home_team_id,))
    home_stats = cursor.fetchone()

    # 客队客场数据
    cursor.execute("""
        SELECT
            AVG(away_goals) as avg_away_goals,
            AVG(home_goals) as avg_conceded,
            COUNT(*) as matches
        FROM matches
        WHERE away_team_id = ? AND away_goals IS NOT NULL
    """, (away_team_id,))
    away_stats = cursor.fetchone()

    # 计算xG（简化模型）
    home_xg = home_stats['avg_home_goals'] or 1.35
    away_xg = away_stats['avg_away_goals'] or 1.05

    # 考虑防守因素
    if away_stats['avg_conceded']:
        home_xg = (home_xg + away_stats['avg_conceded']) / 2
    if home_stats['avg_conceded']:
        away_xg = (away_xg + home_stats['avg_conceded']) / 2

    return round(home_xg, 2), round(away_xg, 2)


def predict_match(home_team_id, away_team_id, conn):
    """预测比赛结果"""
    import math

    # 获取Elo评分
    home_elo = get_elo_rating(home_team_id, conn)
    away_elo = get_elo_rating(away_team_id, conn)

    # 主场优势
    home_elo += 100

    # 计算xG
    home_xg, away_xg = calculate_xg(home_team_id, away_team_id, conn)

    # 基于Elo计算胜率
    elo_diff = home_elo - away_elo
    home_win_prob = 1 / (1 + 10 ** (-elo_diff / 400))

    # 使用泊松分布计算精确概率
    def poisson_prob(k, lambda_val):
        return (lambda_val ** k) * math.exp(-lambda_val) / math.factorial(k)

    # 计算各结果概率
    home_win = 0
    draw = 0
    away_win = 0

    for h in range(8):
        for a in range(8):
            prob = poisson_prob(h, home_xg) * poisson_prob(a, away_xg)
            if h > a:
                home_win += prob
            elif h == a:
                draw += prob
            else:
                away_win += prob

    return {
        'home_win_prob': round(home_win * 100, 1),
        'draw_prob': round(draw * 100, 1),
        'away_win_prob': round(away_win * 100, 1),
        'predicted_home_goals': home_xg,
        'predicted_away_goals': away_xg,
        'home_elo': round(home_elo, 0),
        'away_elo': round(away_elo, 0)
    }


@app.get("/api/v1/analytics/head-to-head")
async def get_head_to_head(team1_id: int, team2_id: int, limit: int = 20):
    """获取交锋记录"""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT
            m.match_id,
            m.match_date,
            l.name_en as league,
            ht.name_en as home_team,
            at.name_en as away_team,
            ht.team_id as home_team_id,
            at.team_id as away_team_id,
            m.home_goals,
            m.away_goals,
            CASE
                WHEN m.home_goals > m.away_goals THEN 'H'
                WHEN m.home_goals < m.away_goals THEN 'A'
                ELSE 'D'
            END as result
        FROM matches m
        JOIN teams ht ON m.home_team_id = ht.team_id
        JOIN teams at ON m.away_team_id = at.team_id
        JOIN leagues l ON m.league_id = l.league_id
        WHERE (m.home_team_id = ? AND m.away_team_id = ?)
           OR (m.home_team_id = ? AND m.away_team_id = ?)
        ORDER BY m.match_date DESC
        LIMIT ?
    """, (team1_id, team2_id, team2_id, team1_id, limit))

    matches = list(cursor.fetchall())

    team1_wins = 0
    team2_wins = 0
    draws = 0

    for match in matches:
        if match['result'] == 'D':
            draws += 1
        elif match['result'] == 'H':
            if match['home_team_id'] == team1_id:
                team1_wins += 1
            else:
                team2_wins += 1
        else:  # 'A'
            if match['away_team_id'] == team1_id:
                team1_wins += 1
            else:
                team2_wins += 1

    # 添加中文名称
    matches_data = []
    for match in matches:
        m = dict(match)
        m['home_team_cn'] = get_chinese_team_name(m['home_team'])
        m['away_team_cn'] = get_chinese_team_name(m['away_team'])
        matches_data.append(m)

    conn.close()
    return {
        "data": {
            "total_matches": len(matches),
            "team1_wins": team1_wins,
            "team2_wins": team2_wins,
            "draws": draws,
            "matches": matches_data
        }
    }


@app.get("/api/v1/analytics/predict")
async def predict_match_result(home_team_id: int, away_team_id: int):
    """预测比赛结果"""
    conn = get_db()

    try:
        prediction = predict_match(home_team_id, away_team_id, conn)

        # 获取球队名称
        cursor = conn.cursor()
        cursor.execute("SELECT name_en FROM teams WHERE team_id = ?", (home_team_id,))
        home_team = cursor.fetchone()
        cursor.execute("SELECT name_en FROM teams WHERE team_id = ?", (away_team_id,))
        away_team = cursor.fetchone()

        conn.close()

        return {
            "data": {
                "home_team": home_team['name_en'] if home_team else None,
                "away_team": away_team['name_en'] if away_team else None,
                "home_team_cn": get_chinese_team_name(home_team['name_en']) if home_team else None,
                "away_team_cn": get_chinese_team_name(away_team['name_en']) if away_team else None,
                **prediction
            }
        }
    except Exception as e:
        conn.close()
        return {"error": str(e)}


@app.get("/api/v1/analytics/elo/{team_id}")
async def get_team_elo(team_id: int):
    """获取球队Elo评分"""
    conn = get_db()

    try:
        elo = get_elo_rating(team_id, conn)

        cursor = conn.cursor()
        cursor.execute("SELECT name_en, team_type, country FROM teams WHERE team_id = ?", (team_id,))
        team = cursor.fetchone()

        conn.close()

        if not team:
            return {"error": "球队不存在"}

        return {
            "data": {
                "team_id": team_id,
                "team_name": team['name_en'],
                "team_name_cn": get_chinese_team_name(team['name_en']),
                "elo": round(elo, 0),
                "team_type": team['team_type'],
                "country": team['country']
            }
        }
    except Exception as e:
        conn.close()
        return {"error": str(e)}


@app.get("/api/v1/analytics/xg")
async def get_xg_analysis(home_team_id: int, away_team_id: int):
    """获取xG分析"""
    conn = get_db()

    try:
        home_xg, away_xg = calculate_xg(home_team_id, away_team_id, conn)

        cursor = conn.cursor()
        cursor.execute("SELECT name_en FROM teams WHERE team_id = ?", (home_team_id,))
        home_team = cursor.fetchone()
        cursor.execute("SELECT name_en FROM teams WHERE team_id = ?", (away_team_id,))
        away_team = cursor.fetchone()

        conn.close()

        return {
            "data": {
                "home_team": home_team['name_en'] if home_team else None,
                "away_team": away_team['name_en'] if away_team else None,
                "home_team_cn": get_chinese_team_name(home_team['name_en']) if home_team else None,
                "away_team_cn": get_chinese_team_name(away_team['name_en']) if away_team else None,
                "home_xg": home_xg,
                "away_xg": away_xg,
                "total_xg": round(home_xg + away_xg, 2)
            }
        }
    except Exception as e:
        conn.close()
        return {"error": str(e)}


@app.get("/api/v1/analytics/compare")
async def compare_teams(team1_id: int, team2_id: int):
    """球队实力对比"""
    conn = get_db()
    cursor = conn.cursor()

    try:
        # 获取球队基本信息
        cursor.execute("SELECT team_id, name_en, team_type, country FROM teams WHERE team_id = ?", (team1_id,))
        team1 = cursor.fetchone()
        cursor.execute("SELECT team_id, name_en, team_type, country FROM teams WHERE team_id = ?", (team2_id,))
        team2 = cursor.fetchone()

        if not team1 or not team2:
            conn.close()
            return {"error": "球队不存在"}

        # Elo评分
        team1_elo = get_elo_rating(team1_id, conn)
        team2_elo = get_elo_rating(team2_id, conn)

        # 近期状态
        def get_form_stats(team_id):
            cursor.execute("""
                SELECT
                    COUNT(*) as matches,
                    SUM(CASE
                        WHEN (m.home_team_id = ? AND m.home_goals > m.away_goals) THEN 1
                        WHEN (m.away_team_id = ? AND m.away_goals > m.home_goals) THEN 1
                        ELSE 0
                    END) as wins,
                    SUM(CASE WHEN m.home_goals = m.away_goals THEN 1 ELSE 0 END) as draws,
                    SUM(CASE WHEN m.home_team_id = ? THEN m.home_goals ELSE m.away_goals END) as goals_for,
                    SUM(CASE WHEN m.home_team_id = ? THEN m.away_goals ELSE m.home_goals END) as goals_against
                FROM matches m
                WHERE (m.home_team_id = ? OR m.away_team_id = ?)
                AND m.home_goals IS NOT NULL
                ORDER BY m.match_date DESC
                LIMIT 10
            """, (team_id, team_id, team_id, team_id, team_id, team_id))
            return cursor.fetchone()

        team1_form = get_form_stats(team1_id)
        team2_form = get_form_stats(team2_id)

        # 预测
        prediction = predict_match(team1_id, team2_id, conn)

        conn.close()

        return {
            "data": {
                "team1": {
                    "team_id": team1_id,
                    "name": team1['name_en'],
                    "name_cn": get_chinese_team_name(team1['name_en']),
                    "team_type": team1['team_type'],
                    "country": team1['country'],
                    "elo": round(team1_elo, 0),
                    "form": {
                        "matches": team1_form['matches'] or 0,
                        "wins": team1_form['wins'] or 0,
                        "draws": team1_form['draws'] or 0,
                        "losses": (team1_form['matches'] or 0) - (team1_form['wins'] or 0) - (team1_form['draws'] or 0),
                        "goals_for": team1_form['goals_for'] or 0,
                        "goals_against": team1_form['goals_against'] or 0
                    }
                },
                "team2": {
                    "team_id": team2_id,
                    "name": team2['name_en'],
                    "name_cn": get_chinese_team_name(team2['name_en']),
                    "team_type": team2['team_type'],
                    "country": team2['country'],
                    "elo": round(team2_elo, 0),
                    "form": {
                        "matches": team2_form['matches'] or 0,
                        "wins": team2_form['wins'] or 0,
                        "draws": team2_form['draws'] or 0,
                        "losses": (team2_form['matches'] or 0) - (team2_form['wins'] or 0) - (team2_form['draws'] or 0),
                        "goals_for": team2_form['goals_for'] or 0,
                        "goals_against": team2_form['goals_against'] or 0
                    }
                },
                "prediction": prediction,
                "elo_diff": round(team1_elo - team2_elo, 0)
            }
        }
    except Exception as e:
        conn.close()
        return {"error": str(e)}


@app.get("/api/v1/analytics/search")
async def search_teams(q: str, limit: int = 20):
    """搜索球队"""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT team_id, name_en, team_type, country
        FROM teams
        WHERE name_en LIKE ?
        ORDER BY name_en
        LIMIT ?
    """, (f"%{q}%", limit))
    teams = []
    for row in cursor.fetchall():
        team = dict(row)
        team['name_cn'] = get_chinese_team_name(team['name_en'])
        teams.append(team)
    conn.close()
    return {"data": teams}


# ==================== 高级分析功能 ====================

def get_league_importance(league_id, conn):
    """获取联赛重要性评分"""
    cursor = conn.cursor()
    cursor.execute("SELECT name_en as name, tier, competition_type as league_type FROM leagues WHERE league_id = ?", (league_id,))
    league = cursor.fetchone()
    if not league:
        return 5  # 默认中等重要性

    importance = 5
    # 顶级联赛更重要
    if league['tier'] == 1:
        importance = 10
    elif league['tier'] == 2:
        importance = 7
    elif league['tier'] == 3:
        importance = 5
    else:
        importance = 3

    # 杯赛特殊处理
    if 'Champions League' in league['name'] or 'Europa League' in league['name']:
        importance = 10
    elif 'Cup' in league['name'] or 'Cup' in str(league['name']):
        importance = 6

    return importance


def get_team_upcoming_fixtures(team_id, days, conn):
    """获取球队未来几天的比赛"""
    cursor = conn.cursor()
    current_date = get_current_match_date(conn)
    cursor.execute("""
        SELECT
            m.match_id,
            m.match_date,
            l.name_en as league,
            l.league_id,
            ht.name_en as home_team,
            at.name_en as away_team,
            m.home_team_id,
            m.away_team_id
        FROM matches m
        JOIN leagues l ON m.league_id = l.league_id
        JOIN teams ht ON m.home_team_id = ht.team_id
        JOIN teams at ON m.away_team_id = at.team_id
        WHERE (m.home_team_id = ? OR m.away_team_id = ?)
        AND m.match_date >= ?
        AND m.home_goals IS NULL
        ORDER BY m.match_date
    """, (team_id, team_id, current_date))
    return [dict(row) for row in cursor.fetchall()]


def get_team_league_position(team_id, league_id, season, conn):
    """获取球队在联赛中的排名"""
    cursor = conn.cursor()
    cursor.execute("""
        WITH team_stats AS (
            SELECT
                t.team_id,
                t.name_en as team_name,
                COUNT(*) as matches,
                SUM(CASE
                    WHEN (m.home_team_id = t.team_id AND m.home_goals > m.away_goals) THEN 1
                    WHEN (m.away_team_id = t.team_id AND m.away_goals > m.home_goals) THEN 1
                    ELSE 0
                END) as wins,
                SUM(CASE WHEN m.home_goals = m.away_goals THEN 1 ELSE 0 END) as draws,
                SUM(CASE WHEN m.home_team_id = t.team_id THEN m.home_goals ELSE m.away_goals END) as goals_for,
                SUM(CASE WHEN m.home_team_id = t.team_id THEN m.away_goals ELSE m.home_goals END) as goals_against
            FROM teams t
            JOIN matches m ON (t.team_id = m.home_team_id OR t.team_id = m.away_team_id)
            JOIN seasons s ON m.season_id = s.season_id
            WHERE m.league_id = ? AND s.season_name = ?
            AND m.home_goals IS NOT NULL AND m.away_goals IS NOT NULL
            GROUP BY t.team_id, t.name_en
        )
        SELECT
            team_id,
            team_name,
            matches,
            wins,
            draws,
            matches - wins - draws as losses,
            goals_for,
            goals_against,
            goals_for - goals_against as goal_diff,
            wins * 3 + draws as points
        FROM team_stats
        ORDER BY points DESC, goal_diff DESC, goals_for DESC
    """, (league_id, season))

    standings = cursor.fetchall()
    total_teams = len(standings)

    for i, team in enumerate(standings):
        if team['team_id'] == team_id:
            return {
                'position': i + 1,
                'total_teams': total_teams,
                'points': team['points'],
                'matches': team['matches'],
                'goal_diff': team['goal_diff']
            }
    return None


def analyze_team_motivation(team_id, league_id, season, conn):
    """分析球队比赛动机"""
    cursor = conn.cursor()

    # 获取球队排名
    position_info = get_team_league_position(team_id, league_id, season, conn)

    if not position_info:
        return {"motivation": "unknown", "reason": "无法获取排名信息"}

    position = position_info['position']
    total_teams = position_info['total_teams']
    points = position_info['points']

    # 获取联赛总轮次（假设每队打38轮或根据实际计算）
    total_rounds = (total_teams - 1) * 2 if total_teams else 38
    matches_played = position_info['matches']
    matches_left = total_rounds - matches_played

    # 获取第一名和降级区的分数
    cursor.execute("""
        WITH team_stats AS (
            SELECT
                t.team_id,
                SUM(CASE
                    WHEN (m.home_team_id = t.team_id AND m.home_goals > m.away_goals) THEN 1
                    WHEN (m.away_team_id = t.team_id AND m.away_goals > m.home_goals) THEN 1
                    ELSE 0
                END) * 3 + SUM(CASE WHEN m.home_goals = m.away_goals THEN 1 ELSE 0 END) as points
            FROM teams t
            JOIN matches m ON (t.team_id = m.home_team_id OR t.team_id = m.away_team_id)
            JOIN seasons s ON m.season_id = s.season_id
            WHERE m.league_id = ? AND s.season_name = ?
            AND m.home_goals IS NOT NULL AND m.away_goals IS NOT NULL
            GROUP BY t.team_id
        )
        SELECT points FROM team_stats ORDER BY points DESC
    """, (league_id, season))

    all_points = [row[0] for row in cursor.fetchall()]

    motivation = "normal"
    reasons = []

    # 冠军争夺分析
    if position == 1:
        if len(all_points) > 1 and points - all_points[1] > matches_left * 3:
            motivation = "low"
            reasons.append("已提前夺冠，无欲无求")
        elif position <= 1:
            reasons.append("榜首位置，争冠动力强")
            motivation = "high"
    elif position <= 3:
        gap_to_first = all_points[0] - points if all_points else 0
        if gap_to_first <= matches_left * 3:
            reasons.append("争冠集团，动力强")
            motivation = "high"
        else:
            reasons.append("欧冠区，保住位置")
            motivation = "normal"
    elif position <= 4:
        # 欧冠区边缘
        reasons.append("欧冠资格争夺中")
        motivation = "high"
    elif position <= 6:
        # 欧联区
        reasons.append("欧战资格争夺中")
        motivation = "normal"

    # 降级分析
    relegation_zone = total_teams - 3 if total_teams > 3 else total_teams
    if position >= relegation_zone - 2:
        reasons.append("保级压力区，必须拿分")
        motivation = "desperate"
    elif position >= relegation_zone:
        reasons.append("降级区，生死战")
        motivation = "desperate"

    # 中游无欲无求
    if total_teams >= 10:
        safe_zone_top = int(total_teams * 0.4)  # 前40%
        safe_zone_bottom = int(total_teams * 0.7)  # 后30%

        if safe_zone_top < position < safe_zone_bottom:
            if matches_left <= 5:
                gap_to_europe = all_points[int(total_teams * 0.3) - 1] - points if len(all_points) > int(total_teams * 0.3) else 100
                gap_to_relegation = points - all_points[-3] if len(all_points) >= 3 else 0

                if gap_to_europe > matches_left * 3 and gap_to_relegation > matches_left * 3:
                    motivation = "low"
                    reasons.append("中游位置，无欲无求")

    return {
        "motivation": motivation,
        "reasons": reasons,
        "position": position,
        "total_teams": total_teams,
        "points": points,
        "matches_left": matches_left
    }


@app.get("/api/v1/analytics/match-context")
async def analyze_match_context(
    home_team_id: int,
    away_team_id: int,
    league_id: int = None,
    match_date: str = None
):
    """分析比赛背景 - 包括赛程重要性、球队动机等"""

    conn = get_db()
    cursor = conn.cursor()

    try:
        # 获取球队信息
        cursor.execute("SELECT team_id, name_en FROM teams WHERE team_id = ?", (home_team_id,))
        home_team = cursor.fetchone()
        cursor.execute("SELECT team_id, name_en FROM teams WHERE team_id = ?", (away_team_id,))
        away_team = cursor.fetchone()

        if not home_team or not away_team:
            conn.close()
            return {"error": "球队不存在"}

        # 获取当前赛季
        cursor.execute("""
            SELECT s.season_name, s.season_id
            FROM seasons s
            WHERE s.league_id = ?
            ORDER BY s.season_name DESC
            LIMIT 1
        """, (league_id,))
        season_info = cursor.fetchone()
        season = season_info['season_name'] if season_info else None

        # 分析主队未来赛程
        home_upcoming = get_team_upcoming_fixtures(home_team_id, 14, conn)
        away_upcoming = get_team_upcoming_fixtures(away_team_id, 14, conn)

        # 分析赛程密集度
        home_intensity = len(home_upcoming)
        away_intensity = len(away_upcoming)

        # 分析是否有重要比赛即将到来
        def analyze_important_fixtures(fixtures, team_id):
            important_matches = []
            for f in fixtures:
                importance = get_league_importance(f['league_id'], conn)
                if importance >= 8:
                    days_away = (f['match_date'] - match_date).days if match_date else 0
                    important_matches.append({
                        "date": f['match_date'],
                        "opponent": f['away_team'] if f['home_team_id'] == team_id else f['home_team'],
                        "competition": f['league'],
                        "importance": importance,
                        "days_away": days_away
                    })
            return important_matches

        home_important = analyze_important_fixtures(home_upcoming, home_team_id)
        away_important = analyze_important_fixtures(away_upcoming, away_team_id)

        # 分析球队动机
        home_motivation = analyze_team_motivation(home_team_id, league_id, season, conn) if season else {"motivation": "unknown"}
        away_motivation = analyze_team_motivation(away_team_id, league_id, season, conn) if season else {"motivation": "unknown"}

        # 判断是否可能轮换/放水
        home_rotation_risk = "low"
        away_rotation_risk = "low"

        rotation_reasons = {"home": [], "away": []}

        # 主队轮换风险
        if home_intensity >= 4:
            home_rotation_risk = "high"
            rotation_reasons["home"].append(f"14天内{home_intensity}场比赛，赛程密集")
        elif home_intensity >= 3:
            home_rotation_risk = "medium"
            rotation_reasons["home"].append(f"14天内{home_intensity}场比赛")

        if len(home_important) > 0:
            for im in home_important:
                if im['days_away'] <= 3:
                    rotation_reasons["home"].append(f"{im['days_away']}天后有重要比赛vs {im['opponent']}({im['competition']})")
                    home_rotation_risk = "high" if home_rotation_risk != "high" else home_rotation_risk

        if home_motivation.get('motivation') == 'low':
            rotation_reasons["home"].append("球队无欲无求，可能战意不足")
            home_rotation_risk = "high"

        # 客队轮换风险
        if away_intensity >= 4:
            away_rotation_risk = "high"
            rotation_reasons["away"].append(f"14天内{away_intensity}场比赛，赛程密集")
        elif away_intensity >= 3:
            away_rotation_risk = "medium"
            rotation_reasons["away"].append(f"14天内{away_intensity}场比赛")

        if len(away_important) > 0:
            for im in away_important:
                if im['days_away'] <= 3:
                    rotation_reasons["away"].append(f"{im['days_away']}天后有重要比赛vs {im['opponent']}({im['competition']})")
                    away_rotation_risk = "high" if away_rotation_risk != "high" else away_rotation_risk

        if away_motivation.get('motivation') == 'low':
            rotation_reasons["away"].append("球队无欲无求，可能战意不足")
            away_rotation_risk = "high"

        # 综合分析建议
        analysis_summary = []

        if home_rotation_risk == "high" and away_rotation_risk != "high":
            analysis_summary.append("主队可能轮换/放水，客队更有战意")
        elif away_rotation_risk == "high" and home_rotation_risk != "high":
            analysis_summary.append("客队可能轮换/放水，主队更有战意")
        elif home_rotation_risk == "high" and away_rotation_risk == "high":
            analysis_summary.append("双方都可能轮换，比赛质量可能下降")

        if home_motivation.get('motivation') == 'desperate':
            analysis_summary.append("主队保级压力大，必须拿分")
        if away_motivation.get('motivation') == 'desperate':
            analysis_summary.append("客队保级压力大，必须拿分")

        conn.close()

        return {
            "data": {
                "home_team": {
                    "name": home_team['name_en'],
                    "name_cn": get_chinese_team_name(home_team['name_en']),
                    "motivation": home_motivation,
                    "schedule": {
                        "intensity": home_intensity,
                        "upcoming_fixtures": home_upcoming[:5],
                        "important_fixtures": home_important
                    },
                    "rotation_risk": home_rotation_risk,
                    "rotation_reasons": rotation_reasons["home"]
                },
                "away_team": {
                    "name": away_team['name_en'],
                    "name_cn": get_chinese_team_name(away_team['name_en']),
                    "motivation": away_motivation,
                    "schedule": {
                        "intensity": away_intensity,
                        "upcoming_fixtures": away_upcoming[:5],
                        "important_fixtures": away_important
                    },
                    "rotation_risk": away_rotation_risk,
                    "rotation_reasons": rotation_reasons["away"]
                },
                "analysis_summary": analysis_summary,
                "season": season
            }
        }
    except Exception as e:
        conn.close()
        return {"error": str(e)}


@app.get("/api/v1/analytics/rest-days")
async def analyze_rest_days(home_team_id: int, away_team_id: int, match_date: str = None):
    """分析双方休息天数"""

    conn = get_db()
    cursor = conn.cursor()

    try:
        from datetime import datetime, timedelta

        if match_date:
            current_date = datetime.strptime(match_date, '%Y-%m-%d')
        else:
            current_date = datetime.now()

        def get_last_match_date(team_id):
            cursor.execute("""
                SELECT MAX(match_date) as last_match
                FROM matches
                WHERE (home_team_id = ? OR away_team_id = ?)
                AND home_goals IS NOT NULL
                AND match_date < ?
            """, (team_id, team_id, current_date.strftime('%Y-%m-%d')))
            result = cursor.fetchone()
            return result['last_match'] if result else None

        home_last = get_last_match_date(home_team_id)
        away_last = get_last_match_date(away_team_id)

        home_rest = None
        away_rest = None

        if home_last:
            home_last_date = datetime.strptime(home_last, '%Y-%m-%d')
            home_rest = (current_date - home_last_date).days

        if away_last:
            away_last_date = datetime.strptime(away_last, '%Y-%m-%d')
            away_rest = (current_date - away_last_date).days

        # 休息天数分析
        def analyze_rest(rest_days):
            if rest_days is None:
                return {"status": "unknown", "description": "无历史比赛数据"}
            if rest_days >= 7:
                return {"status": "excellent", "description": "休息充分，体能充沛"}
            elif rest_days >= 5:
                return {"status": "good", "description": "休息充足"}
            elif rest_days >= 3:
                return {"status": "normal", "description": "休息正常"}
            elif rest_days == 2:
                return {"status": "tired", "description": "休息不足，可能疲劳"}
            else:
                return {"status": "exhausted", "description": "极度疲劳，影响发挥"}

        home_analysis = analyze_rest(home_rest)
        away_analysis = analyze_rest(away_rest)

        # 体能对比
        advantage = "even"
        if home_rest and away_rest:
            if home_rest - away_rest >= 3:
                advantage = "home"
            elif away_rest - home_rest >= 3:
                advantage = "away"

        conn.close()

        return {
            "data": {
                "home_team": {
                    "rest_days": home_rest,
                    **home_analysis
                },
                "away_team": {
                    "rest_days": away_rest,
                    **away_analysis
                },
                "advantage": advantage,
                "summary": f"主队休息{home_rest}天，客队休息{away_rest}天" if home_rest and away_rest else "休息数据不完整"
            }
        }
    except Exception as e:
        conn.close()
        return {"error": str(e)}


@app.get("/api/v1/analytics/season-situation")
async def analyze_season_situation(team_id: int, league_id: int):
    """分析球队赛季形势"""

    conn = get_db()
    cursor = conn.cursor()

    try:
        # 获取球队信息
        cursor.execute("SELECT name_en FROM teams WHERE team_id = ?", (team_id,))
        team = cursor.fetchone()
        if not team:
            conn.close()
            return {"error": "球队不存在"}

        # 获取当前赛季
        cursor.execute("""
            SELECT s.season_name, s.season_id
            FROM seasons s
            WHERE s.league_id = ?
            ORDER BY s.season_name DESC
            LIMIT 1
        """, (league_id,))
        season_info = cursor.fetchone()

        if not season_info:
            conn.close()
            return {"error": "无赛季数据"}

        season = season_info['season_name']

        # 获取积分榜
        cursor.execute("""
            WITH team_stats AS (
                SELECT
                    t.team_id,
                    t.name_en as team_name,
                    COUNT(*) as matches,
                    SUM(CASE
                        WHEN (m.home_team_id = t.team_id AND m.home_goals > m.away_goals) THEN 1
                        WHEN (m.away_team_id = t.team_id AND m.away_goals > m.home_goals) THEN 1
                        ELSE 0
                    END) as wins,
                    SUM(CASE WHEN m.home_goals = m.away_goals THEN 1 ELSE 0 END) as draws,
                    SUM(CASE WHEN m.home_team_id = t.team_id THEN m.home_goals ELSE m.away_goals END) as goals_for,
                    SUM(CASE WHEN m.home_team_id = t.team_id THEN m.away_goals ELSE m.home_goals END) as goals_against
                FROM teams t
                JOIN matches m ON (t.team_id = m.home_team_id OR t.team_id = m.away_team_id)
                JOIN seasons s ON m.season_id = s.season_id
                WHERE m.league_id = ? AND s.season_name = ?
                AND m.home_goals IS NOT NULL AND m.away_goals IS NOT NULL
                GROUP BY t.team_id, t.name_en
            )
            SELECT
                team_id,
                team_name,
                matches,
                wins,
                draws,
                matches - wins - draws as losses,
                goals_for,
                goals_against,
                goals_for - goals_against as goal_diff,
                wins * 3 + draws as points
            FROM team_stats
            ORDER BY points DESC, goal_diff DESC, goals_for DESC
        """, (league_id, season))

        standings = cursor.fetchall()
        total_teams = len(standings)

        # 找到球队位置
        team_position = None
        for i, row in enumerate(standings):
            if row['team_id'] == team_id:
                team_position = i + 1
                team_stats = dict(row)
                break

        if not team_position:
            conn.close()
            return {"error": "球队不在此联赛"}

        # 分析形势
        all_points = [row['points'] for row in standings]

        # 冠军分析
        first_points = all_points[0]
        points_to_first = first_points - team_stats['points']

        # 降级分析
        relegation_line = total_teams - 2  # 倒数第三
        relegation_points = all_points[-3] if len(all_points) >= 3 else 0
        points_to_relegation = team_stats['points'] - relegation_points

        # 欧战区分析
        europe_spots = min(4, total_teams // 4)
        europe_points = all_points[europe_spots - 1] if len(all_points) >= europe_spots else 0
        points_to_europe = europe_points - team_stats['points']

        # 剩余比赛
        total_rounds = (total_teams - 1) * 2
        matches_left = total_rounds - team_stats['matches']

        # 形势判断
        situation = {
            "position": team_position,
            "total_teams": total_teams,
            "points": team_stats['points'],
            "goal_diff": team_stats['goal_diff'],
            "matches_played": team_stats['matches'],
            "matches_left": matches_left,
            "form": {
                "wins": team_stats['wins'],
                "draws": team_stats['draws'],
                "losses": team_stats['losses']
            }
        }

        # 目标分析
        targets = []

        # 冠军可能性
        if team_position == 1:
            if points_to_first == 0 and matches_left * 3 < all_points[1] - team_stats['points'] if len(all_points) > 1 else True:
                targets.append({"target": "champion", "status": "secured", "description": "已提前夺冠"})
            else:
                targets.append({"target": "champion", "status": "fighting", "description": f"榜首，领先{all_points[1] - team_stats['points']}分" if len(all_points) > 1 else "榜首"})
        elif points_to_first <= matches_left * 3:
            targets.append({"target": "champion", "status": "possible", "description": f"落后{points_to_first}分，{matches_left}轮可追"})

        # 欧战区
        if team_position <= europe_spots:
            if team_position == europe_spots:
                targets.append({"target": "europe", "status": "borderline", "description": f"欧战区边缘"})
            else:
                targets.append({"target": "europe", "status": "secured", "description": f"欧战区内，第{team_position}名"})
        elif points_to_europe <= matches_left * 3:
            targets.append({"target": "europe", "status": "fighting", "description": f"距欧战区{points_to_europe}分"})

        # 保级分析
        if team_position >= total_teams - 2:
            if team_position == total_teams:
                targets.append({"target": "relegation", "status": "danger", "description": "垫底，深陷降级区"})
            elif team_position == total_teams - 1:
                targets.append({"target": "relegation", "status": "danger", "description": "降级区内"})
            else:
                targets.append({"target": "relegation", "status": "warning", "description": "降级区边缘"})
        elif points_to_relegation <= 6:
            targets.append({"target": "relegation", "status": "warning", "description": f"仅领先降级区{points_to_relegation}分"})

        # 无欲无求判断
        if not targets:
            targets.append({"target": "midtable", "status": "safe", "description": "中游位置，无欲无求"})

        situation["targets"] = targets

        conn.close()

        return {
            "data": {
                "team": team['name_en'],
                "team_cn": get_chinese_team_name(team['name_en']),
                "season": season,
                "situation": situation
            }
        }
    except Exception as e:
        conn.close()
        return {"error": str(e)}


@app.get("/api/v1/analytics/full-analysis")
async def full_match_analysis(
    home_team_id: int,
    away_team_id: int,
    league_id: int = None,
    match_date: str = None
):
    """综合比赛分析 - 包含所有分析维度"""

    conn = get_db()
    cursor = conn.cursor()

    try:
        # 获取球队信息
        cursor.execute("SELECT name_en FROM teams WHERE team_id = ?", (home_team_id,))
        home_team = cursor.fetchone()
        cursor.execute("SELECT name_en FROM teams WHERE team_id = ?", (away_team_id,))
        away_team = cursor.fetchone()

        if not home_team or not away_team:
            conn.close()
            return {"error": "球队不存在"}

        # 1. 基础实力对比
        home_elo = get_elo_rating(home_team_id, conn)
        away_elo = get_elo_rating(away_team_id, conn)

        # 2. 比赛预测
        prediction = predict_match(home_team_id, away_team_id, conn)

        # 3. 赛季形势
        home_situation = None
        away_situation = None
        if league_id:
            cursor.execute("""
                SELECT s.season_name FROM seasons s
                WHERE s.league_id = ? ORDER BY s.season_name DESC LIMIT 1
            """, (league_id,))
            season_row = cursor.fetchone()
            if season_row:
                home_motivation = analyze_team_motivation(home_team_id, league_id, season_row['season_name'], conn)
                away_motivation = analyze_team_motivation(away_team_id, league_id, season_row['season_name'], conn)
            else:
                home_motivation = {"motivation": "unknown"}
                away_motivation = {"motivation": "unknown"}
        else:
            home_motivation = {"motivation": "unknown"}
            away_motivation = {"motivation": "unknown"}

        # 4. 赛程分析
        home_upcoming = get_team_upcoming_fixtures(home_team_id, 14, conn)
        away_upcoming = get_team_upcoming_fixtures(away_team_id, 14, conn)

        # 5. 休息天数
        from datetime import datetime
        current_date = datetime.strptime(match_date, '%Y-%m-%d') if match_date else datetime.now()

        def get_rest_days(team_id):
            cursor.execute("""
                SELECT MAX(match_date) as last_match
                FROM matches
                WHERE (home_team_id = ? OR away_team_id = ?)
                AND home_goals IS NOT NULL
                AND match_date < ?
            """, (team_id, team_id, current_date.strftime('%Y-%m-%d')))
            result = cursor.fetchone()
            if result and result['last_match']:
                last_date = datetime.strptime(result['last_match'], '%Y-%m-%d')
                return (current_date - last_date).days
            return None

        home_rest = get_rest_days(home_team_id)
        away_rest = get_rest_days(away_team_id)

        # 6. 综合建议
        recommendations = []

        # Elo差距
        elo_diff = home_elo - away_elo
        if abs(elo_diff) > 200:
            stronger = "主队" if elo_diff > 0 else "客队"
            recommendations.append(f"实力差距明显，{stronger}占优")
        elif abs(elo_diff) > 100:
            stronger = "主队" if elo_diff > 0 else "客队"
            recommendations.append(f"{stronger}略占优势")

        # 动机对比
        motivation_map = {"desperate": 3, "high": 2, "normal": 1, "low": 0, "unknown": 1}
        home_motivation_score = motivation_map.get(home_motivation.get('motivation', 'unknown'), 1)
        away_motivation_score = motivation_map.get(away_motivation.get('motivation', 'unknown'), 1)

        if home_motivation_score > away_motivation_score + 1:
            recommendations.append("主队战意明显更强")
        elif away_motivation_score > home_motivation_score + 1:
            recommendations.append("客队战意明显更强")

        # 休息对比
        if home_rest and away_rest:
            if home_rest >= 5 and away_rest <= 2:
                recommendations.append("主队休息充分，客队疲劳作战")
            elif away_rest >= 5 and home_rest <= 2:
                recommendations.append("客队休息充分，主队疲劳作战")

        # 赛程密集度
        if len(home_upcoming) >= 4 and len(away_upcoming) <= 2:
            recommendations.append("主队赛程密集，可能轮换")
        elif len(away_upcoming) >= 4 and len(home_upcoming) <= 2:
            recommendations.append("客队赛程密集，可能轮换")

        conn.close()

        return {
            "data": {
                "home_team": {
                    "name": home_team['name_en'],
                    "name_cn": get_chinese_team_name(home_team['name_en']),
                    "elo": round(home_elo, 0),
                    "motivation": home_motivation,
                    "rest_days": home_rest,
                    "upcoming_matches": len(home_upcoming)
                },
                "away_team": {
                    "name": away_team['name_en'],
                    "name_cn": get_chinese_team_name(away_team['name_en']),
                    "elo": round(away_elo, 0),
                    "motivation": away_motivation,
                    "rest_days": away_rest,
                    "upcoming_matches": len(away_upcoming)
                },
                "prediction": prediction,
                "recommendations": recommendations,
                "elo_diff": round(elo_diff, 0)
            }
        }
    except Exception as e:
        conn.close()
        return {"error": str(e)}


@app.get("/api/v1/matches/{match_id}/analysis-summary")
async def get_match_analysis_summary(match_id: str):
    """获取比赛简略分析摘要（用于首页展示）"""
    conn = get_db()
    cursor = conn.cursor()

    try:
        # 获取比赛信息
        cursor.execute("""
            SELECT
                m.match_id,
                m.match_date,
                m.match_time,
                m.home_team_id,
                m.away_team_id,
                m.home_goals,
                m.away_goals,
                ht.name_en as home_team,
                at.name_en as away_team,
                l.name_en as league,
                l.country as league_country
            FROM matches m
            JOIN teams ht ON m.home_team_id = ht.team_id
            JOIN teams at ON m.away_team_id = at.team_id
            JOIN leagues l ON m.league_id = l.league_id
            WHERE m.match_id = ?
        """, (match_id,))
        match = cursor.fetchone()

        if not match:
            conn.close()
            return {"error": "比赛不存在"}

        home_team_id = match['home_team_id']
        away_team_id = match['away_team_id']

        # 获取Elo评分
        home_elo = get_elo_rating(home_team_id, conn)
        away_elo = get_elo_rating(away_team_id, conn)
        elo_diff = home_elo - away_elo

        # 获取预测
        prediction = predict_match(home_team_id, away_team_id, conn)

        # 简单的H2H统计
        cursor.execute("""
            SELECT COUNT(*) as total,
                   SUM(CASE WHEN (home_team_id = ? AND home_goals > away_goals) OR
                                (away_team_id = ? AND away_goals > home_goals) THEN 1 ELSE 0 END) as home_wins,
                   SUM(CASE WHEN home_goals = away_goals THEN 1 ELSE 0 END) as draws
            FROM matches
            WHERE ((home_team_id = ? AND away_team_id = ?) OR
                   (home_team_id = ? AND away_team_id = ?))
            AND home_goals IS NOT NULL
        """, (home_team_id, away_team_id, home_team_id, away_team_id, away_team_id, home_team_id))
        h2h = cursor.fetchone()

        # 生成简短分析文本
        summary_text = generate_match_summary(
            match['home_team'], match['away_team'],
            home_elo, away_elo, prediction, h2h
        )

        conn.close()

        return {
            "data": {
                "match_id": match_id,
                "home_team": match['home_team'],
                "away_team": match['away_team'],
                "home_team_cn": get_chinese_team_name(match['home_team']),
                "away_team_cn": get_chinese_team_name(match['away_team']),
                "league": match['league'],
                "league_cn": get_chinese_league_name(match['league']),
                "home_elo": round(home_elo, 0),
                "away_elo": round(away_elo, 0),
                "elo_diff": round(elo_diff, 0),
                "prediction": {
                    "home_win": prediction['home_win_prob'],
                    "draw": prediction['draw_prob'],
                    "away_win": prediction['away_win_prob']
                },
                "h2h": {
                    "total": h2h['total'] or 0,
                    "home_wins": h2h['home_wins'] or 0,
                    "draws": h2h['draws'] or 0,
                    "away_wins": (h2h['total'] or 0) - (h2h['home_wins'] or 0) - (h2h['draws'] or 0)
                },
                "summary": summary_text
            }
        }
    except Exception as e:
        conn.close()
        return {"error": str(e)}


def generate_match_summary(home_team, away_team, home_elo, away_elo, prediction, h2h):
    """生成比赛简略分析文本"""
    elo_diff = home_elo - away_elo

    # Elo分析
    if elo_diff > 100:
        elo_analysis = f"{home_team}实力明显占优"
    elif elo_diff > 50:
        elo_analysis = f"{home_team}略占优势"
    elif elo_diff < -100:
        elo_analysis = f"{away_team}实力明显占优"
    elif elo_diff < -50:
        elo_analysis = f"{away_team}略占优势"
    else:
        elo_analysis = "双方实力接近"

    # 预测分析
    if prediction['home_win_prob'] > 50:
        pred_analysis = f"主胜概率{round(prediction['home_win_prob'])}%"
    elif prediction['away_win_prob'] > 40:
        pred_analysis = f"客胜概率{round(prediction['away_win_prob'])}%"
    else:
        pred_analysis = f"平局概率{round(prediction['draw_prob'])}%"

    # H2H分析
    if h2h['total'] and h2h['total'] > 0:
        home_win_rate = (h2h['home_wins'] or 0) / h2h['total']
        h2h_analysis = f"历史{h2h['total']}次交锋"
    else:
        h2h_analysis = "无历史交锋"

    return f"{elo_analysis}，{pred_analysis}，{h2h_analysis}"


# ==================== 新增分析函数 ====================

def get_recent_trend_analysis(home_team_id, away_team_id, conn):
    """获取近期走势分析（多时间段）"""
    cursor = conn.cursor()

    def get_team_trend(team_id, limit=5):
        cursor.execute("""
            SELECT
                m.match_date,
                m.home_team_id,
                m.away_team_id,
                m.home_goals,
                m.away_goals,
                CASE
                    WHEN (m.home_team_id = ? AND m.home_goals > m.away_goals) OR
                         (m.away_team_id = ? AND m.away_goals > m.home_goals) THEN 3
                    WHEN m.home_goals = m.away_goals THEN 1
                    ELSE 0
                END as points
            FROM matches m
            WHERE (m.home_team_id = ? OR m.away_team_id = ?)
            AND m.home_goals IS NOT NULL
            ORDER BY m.match_date DESC
            LIMIT ?
        """, (team_id, team_id, team_id, team_id, limit))
        matches = cursor.fetchall()

        if not matches:
            return {"trend": [], "total_points": 0, "avg_points": 0, "form": "未知"}

        trend = [m['points'] for m in matches]
        total = sum(trend)
        avg = total / len(trend) if trend else 0

        # 判断状态
        if avg >= 2:
            form = "极佳"
        elif avg >= 1.5:
            form = "良好"
        elif avg >= 1:
            form = "一般"
        else:
            form = "低迷"

        return {
            "trend": trend,
            "total_points": total,
            "avg_points": round(avg, 2),
            "form": form
        }

    return {
        "home": {
            "last6": get_team_trend(home_team_id, 6),
            "last10": get_team_trend(home_team_id, 10),
            "last20": get_team_trend(home_team_id, 20)
        },
        "away": {
            "last6": get_team_trend(away_team_id, 6),
            "last10": get_team_trend(away_team_id, 10),
            "last20": get_team_trend(away_team_id, 20)
        }
    }


def get_match_importance_analysis(home_team_id, away_team_id, league_id, match_date, conn):
    """分析比赛重要性（基于积分榜位置）"""
    cursor = conn.cursor()

    try:
        # 检查 league_standings 表是否存在
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='league_standings'")
        if cursor.fetchone():
            # 获取当前赛季积分榜
            cursor.execute("""
                SELECT
                    team_id,
                    points,
                    played,
                    position
                FROM league_standings
                WHERE league_id = ?
                ORDER BY position ASC
            """, (league_id,))
            standings = cursor.fetchall()

            if standings and len(standings) >= 2:
                # 找到两队排名
                home_rank = None
                away_rank = None
                total_teams = len(standings)

                for s in standings:
                    if s['team_id'] == home_team_id:
                        home_rank = s['position']
                    if s['team_id'] == away_team_id:
                        away_rank = s['position']

                if home_rank and away_rank:
                    # 分析形势
                    def get_situation(rank, total):
                        if rank <= 1:
                            return "争冠关键战"
                        elif rank <= 4 and total >= 6:
                            return "欧战资格争夺"
                        elif rank >= total - 3:
                            return "保级关键战"
                        else:
                            return "中游位置"

                    home_situation = get_situation(home_rank, total_teams)
                    away_situation = get_situation(away_rank, total_teams)

                    # 判断比赛重要性
                    if "争冠" in home_situation or "争冠" in away_situation:
                        importance = "⭐⭐⭐ 争冠关键战"
                    elif "欧战" in home_situation and "欧战" in away_situation:
                        importance = "⭐⭐⭐ 欧战资格关键战"
                    elif "保级" in home_situation and "保级" in away_situation:
                        importance = "⭐⭐⭐ 保级生死战"
                    elif "欧战" in home_situation or "欧战" in away_situation:
                        importance = "⭐⭐ 重要比赛"
                    elif "保级" in home_situation or "保级" in away_situation:
                        importance = "⭐⭐ 保级相关"
                    else:
                        importance = "⭐ 常规比赛"

                    return {
                        "importance": importance,
                        "home_rank": home_rank,
                        "away_rank": away_rank,
                        "home_situation": home_situation,
                        "away_situation": away_situation,
                        "total_teams": total_teams
                    }

        # 如果没有积分榜数据，基于近期表现估算
        # 获取两队近期胜率来估算实力
        def get_recent_win_rate(team_id):
            cursor.execute("""
                SELECT
                    COUNT(*) as matches,
                    SUM(CASE
                        WHEN (m.home_team_id = ? AND m.home_goals > m.away_goals) OR
                             (m.away_team_id = ? AND m.away_goals > m.home_goals) THEN 1
                        ELSE 0
                    END) as wins
                FROM matches m
                WHERE (m.home_team_id = ? OR m.away_team_id = ?)
                AND m.home_goals IS NOT NULL
                ORDER BY m.match_date DESC
                LIMIT 10
            """, (team_id, team_id, team_id, team_id))
            result = cursor.fetchone()
            if result and result['matches'] > 0:
                return result['wins'] / result['matches']
            return 0.5

        home_win_rate = get_recent_win_rate(home_team_id)
        away_win_rate = get_recent_win_rate(away_team_id)

        # 基于胜率判断重要性
        if home_win_rate > 0.6 and away_win_rate > 0.6:
            importance = "⭐⭐⭐ 强强对话"
        elif home_win_rate < 0.3 and away_win_rate < 0.3:
            importance = "⭐⭐ 保级大战"
        elif abs(home_win_rate - away_win_rate) > 0.3:
            importance = "⭐ 实力悬殊"
        else:
            importance = "⭐⭐ 常规比赛"

        return {
            "importance": importance,
            "home_rank": None,
            "away_rank": None,
            "home_situation": "暂无积分榜数据",
            "away_situation": "暂无积分榜数据",
            "home_win_rate": round(home_win_rate * 100, 1),
            "away_win_rate": round(away_win_rate * 100, 1)
        }
    except Exception as e:
        return {"importance": "未知", "home_situation": "未知", "away_situation": "未知", "error": str(e)}


def get_h2h_psychology_analysis(home_team_id, away_team_id, h2h_stats, conn):
    """分析历史交锋心理压制"""
    total = h2h_stats.get('total', 0)

    if total == 0:
        return {"advantage": "无交锋记录", "description": "两队无历史交锋，心理层面未知"}

    home_wins = h2h_stats.get('home_wins', 0)
    away_wins = h2h_stats.get('away_wins', 0)
    draws = h2h_stats.get('draws', 0)

    home_win_rate = home_wins / total * 100
    away_win_rate = away_wins / total * 100

    # 判断心理优势
    if home_win_rate >= 60:
        advantage = "home"
        description = f"主队心理优势明显，历史胜率{home_win_rate:.0f}%"
    elif away_win_rate >= 60:
        advantage = "away"
        description = f"客队心理优势明显，历史胜率{away_win_rate:.0f}%"
    elif home_win_rate >= 50:
        advantage = "home_slight"
        description = f"主队略有心理优势，历史胜率{home_win_rate:.0f}%"
    elif away_win_rate >= 50:
        advantage = "away_slight"
        description = f"客队略有心理优势，历史胜率{away_win_rate:.0f}%"
    else:
        advantage = "even"
        description = "两队历史交锋势均力敌"

    return {
        "advantage": advantage,
        "description": description,
        "home_win_rate": round(home_win_rate, 1),
        "away_win_rate": round(away_win_rate, 1),
        "total_matches": total
    }


def get_attack_efficiency_analysis(home_team_id, away_team_id, conn):
    """分析进攻效率对比"""
    cursor = conn.cursor()

    def get_team_efficiency(team_id):
        # 近10场比赛的进攻数据（简化版，不依赖shots字段）
        cursor.execute("""
            SELECT
                COUNT(*) as matches,
                SUM(CASE WHEN m.home_team_id = ? THEN m.home_goals ELSE m.away_goals END) as goals_for,
                SUM(CASE WHEN m.home_team_id = ? THEN m.away_goals ELSE m.home_goals END) as goals_against
            FROM matches m
            WHERE (m.home_team_id = ? OR m.away_team_id = ?)
            AND m.home_goals IS NOT NULL
            ORDER BY m.match_date DESC
            LIMIT 10
        """, (team_id, team_id, team_id, team_id))
        result = cursor.fetchone()

        if not result or result['matches'] == 0:
            return {"avg_goals": 0, "avg_conceded": 0, "efficiency": "未知"}

        matches = result['matches']
        goals_for = result['goals_for'] or 0
        goals_against = result['goals_against'] or 0

        avg_goals = goals_for / matches
        avg_conceded = goals_against / matches

        # 效率评级
        if avg_goals >= 2:
            efficiency = "高效"
        elif avg_goals >= 1.5:
            efficiency = "良好"
        elif avg_goals >= 1:
            efficiency = "一般"
        else:
            efficiency = "低迷"

        return {
            "avg_goals": round(avg_goals, 2),
            "avg_conceded": round(avg_conceded, 2),
            "efficiency": efficiency,
            "total_goals": goals_for,
            "total_conceded": goals_against
        }

    home_eff = get_team_efficiency(home_team_id)
    away_eff = get_team_efficiency(away_team_id)

    # 对比分析
    if home_eff['avg_goals'] > away_eff['avg_goals'] + 0.5:
        attack_comparison = "主队进攻更强"
    elif away_eff['avg_goals'] > home_eff['avg_goals'] + 0.5:
        attack_comparison = "客队进攻更强"
    else:
        attack_comparison = "两队进攻相当"

    if home_eff['avg_conceded'] < away_eff['avg_conceded'] - 0.3:
        defense_comparison = "主队防守更稳"
    elif away_eff['avg_conceded'] < home_eff['avg_conceded'] - 0.3:
        defense_comparison = "客队防守更稳"
    else:
        defense_comparison = "两队防守相当"

    return {
        "home": home_eff,
        "away": away_eff,
        "attack_comparison": attack_comparison,
        "defense_comparison": defense_comparison
    }


def get_over_under_analysis(home_team_id, away_team_id, prediction, conn):
    """大小球分析"""
    cursor = conn.cursor()

    # 获取两队近10场比赛的总进球数
    def get_team_goals_stats(team_id):
        cursor.execute("""
            SELECT
                COUNT(*) as matches,
                SUM(m.home_goals + m.away_goals) as total_goals
            FROM matches m
            WHERE (m.home_team_id = ? OR m.away_team_id = ?)
            AND m.home_goals IS NOT NULL
            ORDER BY m.match_date DESC
            LIMIT 10
        """, (team_id, team_id))
        result = cursor.fetchone()
        if result and result['matches'] > 0:
            return result['total_goals'] / result['matches']
        return 2.0

    home_avg = get_team_goals_stats(home_team_id)
    away_avg = get_team_goals_stats(away_team_id)
    combined_avg = (home_avg + away_avg) / 2

    # 基于预测计算大小球概率
    predicted_total = prediction['predicted_home_goals'] + prediction['predicted_away_goals']

    # 简单的概率估算
    if predicted_total >= 3.0:
        over_2_5_prob = 65 + (predicted_total - 3.0) * 15
    elif predicted_total >= 2.5:
        over_2_5_prob = 50 + (predicted_total - 2.5) * 30
    else:
        over_2_5_prob = 30 + (predicted_total - 2.0) * 40

    over_2_5_prob = min(85, max(15, over_2_5_prob))
    under_2_5_prob = 100 - over_2_5_prob

    # 判断推荐
    if over_2_5_prob >= 60:
        recommendation = "大2.5球"
        confidence = "高" if over_2_5_prob >= 70 else "中"
    elif under_2_5_prob >= 60:
        recommendation = "小2.5球"
        confidence = "高" if under_2_5_prob >= 70 else "中"
    else:
        recommendation = "观望"
        confidence = "低"

    return {
        "predicted_total_goals": round(predicted_total, 2),
        "over_2_5_prob": round(over_2_5_prob, 1),
        "under_2_5_prob": round(under_2_5_prob, 1),
        "recommendation": recommendation,
        "confidence": confidence,
        "avg_goals_home_team": round(home_avg, 2),
        "avg_goals_away_team": round(away_avg, 2)
    }


def get_score_prediction(prediction, h2h_stats):
    """比分预测"""
    home_goals = round(prediction['predicted_home_goals'])
    away_goals = round(prediction['predicted_away_goals'])

    # 生成可能的比分列表
    possible_scores = []

    # 基于预测生成主要比分
    base_scores = [
        (home_goals, away_goals, 25),
        (home_goals + 1, away_goals, 15),
        (home_goals, away_goals + 1, 15),
        (home_goals - 1 if home_goals > 0 else 0, away_goals, 10),
        (home_goals, away_goals - 1 if away_goals > 0 else 0, 10),
        (1, 0, 8),
        (0, 1, 8),
        (1, 1, 12),
        (2, 0, 6),
        (0, 2, 6),
        (2, 1, 5),
        (1, 2, 5),
        (0, 0, 8),
        (2, 2, 4),
    ]

    # 根据历史交锋调整
    if h2h_stats.get('draws', 0) / max(1, h2h_stats.get('total', 1)) > 0.4:
        # 平局多
        for i, (h, a, p) in enumerate(base_scores):
            if h == a:
                base_scores[i] = (h, a, p + 5)

    # 排序并取前5个
    base_scores.sort(key=lambda x: x[2], reverse=True)
    for h, a, prob in base_scores[:5]:
        possible_scores.append({
            "home": h,
            "away": a,
            "probability": prob,
            "result": "主胜" if h > a else ("平局" if h == a else "客胜")
        })

    # 最可能的比分
    most_likely = possible_scores[0]

    return {
        "most_likely": most_likely,
        "possible_scores": possible_scores
    }


def get_betting_analysis(prediction, elo_diff, h2h_stats):
    """胜平负概率分布与投注建议"""
    home_prob = prediction['home_win_prob']
    draw_prob = prediction['draw_prob']
    away_prob = prediction['away_win_prob']

    # 根据Elo和历史交锋微调
    if elo_diff > 50:
        home_prob += 5
        away_prob -= 5
    elif elo_diff < -50:
        away_prob += 5
        home_prob -= 5

    # 归一化
    total = home_prob + draw_prob + away_prob
    home_prob = home_prob / total * 100
    draw_prob = draw_prob / total * 100
    away_prob = away_prob / total * 100

    # 投注建议
    recommendations = []

    if home_prob >= 50:
        recommendations.append({"type": "主胜", "confidence": "高" if home_prob >= 60 else "中", "prob": round(home_prob, 1)})
    elif home_prob >= 40:
        recommendations.append({"type": "主胜", "confidence": "中", "prob": round(home_prob, 1)})

    if away_prob >= 50:
        recommendations.append({"type": "客胜", "confidence": "高" if away_prob >= 60 else "中", "prob": round(away_prob, 1)})
    elif away_prob >= 40:
        recommendations.append({"type": "客胜", "confidence": "中", "prob": round(away_prob, 1)})

    if draw_prob >= 30:
        recommendations.append({"type": "平局", "confidence": "中", "prob": round(draw_prob, 1)})

    # 双选建议
    if home_prob >= 35 and draw_prob >= 25:
        recommendations.append({"type": "主胜/平局", "confidence": "稳健", "prob": round(home_prob + draw_prob, 1)})
    if away_prob >= 35 and draw_prob >= 25:
        recommendations.append({"type": "客胜/平局", "confidence": "稳健", "prob": round(away_prob + draw_prob, 1)})

    return {
        "home_win_prob": round(home_prob, 1),
        "draw_prob": round(draw_prob, 1),
        "away_win_prob": round(away_prob, 1),
        "recommendations": recommendations[:4]
    }


def get_odds_analysis(match_id, prediction, conn):
    """赔率分析"""
    cursor = conn.cursor()

    # 尝试获取实际赔率
    cursor.execute("""
        SELECT odds_home as home_odds, odds_draw as draw_odds, odds_away as away_odds
        FROM matches
        WHERE match_id = ?
    """, (match_id,))
    odds_data = cursor.fetchone()

    if odds_data and odds_data['home_odds']:
        # 有实际赔率
        home_odds = odds_data['home_odds']
        draw_odds = odds_data['draw_odds']
        away_odds = odds_data['away_odds']

        # 计算隐含概率
        home_implied = 100 / home_odds if home_odds else 0
        draw_implied = 100 / draw_odds if draw_odds else 0
        away_implied = 100 / away_odds if away_odds else 0

        # 归一化
        total_implied = home_implied + draw_implied + away_implied
        home_implied = home_implied / total_implied * 100
        draw_implied = draw_implied / total_implied * 100
        away_implied = away_implied / total_implied * 100

        # 与模型预测对比
        home_diff = prediction['home_win_prob'] - home_implied
        draw_diff = prediction['draw_prob'] - draw_implied
        away_diff = prediction['away_win_prob'] - away_implied

        # 寻找价值投注
        value_bets = []
        if home_diff > 5:
            value_bets.append({"type": "主胜", "model_prob": round(prediction['home_win_prob'], 1), "implied_prob": round(home_implied, 1), "value": round(home_diff, 1)})
        if draw_diff > 5:
            value_bets.append({"type": "平局", "model_prob": round(prediction['draw_prob'], 1), "implied_prob": round(draw_implied, 1), "value": round(draw_diff, 1)})
        if away_diff > 5:
            value_bets.append({"type": "客胜", "model_prob": round(prediction['away_win_prob'], 1), "implied_prob": round(away_implied, 1), "value": round(away_diff, 1)})

        return {
            "has_odds": True,
            "home_odds": home_odds,
            "draw_odds": draw_odds,
            "away_odds": away_odds,
            "home_implied": round(home_implied, 1),
            "draw_implied": round(draw_implied, 1),
            "away_implied": round(away_implied, 1),
            "value_bets": value_bets
        }
    else:
        # 无赔率数据，使用模型预测估算
        return {
            "has_odds": False,
            "estimated_home_odds": round(100 / prediction['home_win_prob'], 2) if prediction['home_win_prob'] > 0 else 0,
            "estimated_draw_odds": round(100 / prediction['draw_prob'], 2) if prediction['draw_prob'] > 0 else 0,
            "estimated_away_odds": round(100 / prediction['away_win_prob'], 2) if prediction['away_win_prob'] > 0 else 0
        }


def get_future_fixtures_analysis(home_team_id, away_team_id, match_date, conn):
    """分析两队未来赛程"""
    cursor = conn.cursor()

    def get_team_future(team_id, current_date):
        cursor.execute("""
            SELECT m.match_date, m.home_team_id, m.away_team_id,
                   ht.name_en as home_team, at.name_en as away_team, l.name_en as league
            FROM matches m
            JOIN teams ht ON m.home_team_id = ht.team_id
            JOIN teams at ON m.away_team_id = at.team_id
            JOIN leagues l ON m.league_id = l.league_id
            WHERE (m.home_team_id = ? OR m.away_team_id = ?)
            AND m.match_date > ?
            AND m.home_goals IS NULL
            ORDER BY m.match_date ASC
            LIMIT 5
        """, (team_id, team_id, current_date))
        fixtures = cursor.fetchall()

        result = []
        for f in fixtures:
            is_home = f['home_team_id'] == team_id
            opponent = f['away_team'] if is_home else f['home_team']
            result.append({
                "date": f['match_date'],
                "opponent": opponent,
                "opponent_cn": get_chinese_team_name(opponent),
                "venue": "主场" if is_home else "客场",
                "league": f['league']
            })
        return result

    return {
        "home_next": get_team_future(home_team_id, match_date),
        "away_next": get_team_future(away_team_id, match_date)
    }


def get_match_critical_reasons(home_team_id, away_team_id, league_id, match_date, conn):
    """分析比赛关键理由（不能输/不能赢的原因）"""
    cursor = conn.cursor()
    reasons = {"home": {"must_win": [], "must_not_lose": [], "can_afford_loss": []},
               "away": {"must_win": [], "must_not_lose": [], "can_afford_loss": []}}

    # 获取积分榜位置
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='league_standings'")
    if cursor.fetchone():
        # 获取主队排名和积分
        cursor.execute("""
            SELECT position, points, played FROM league_standings
            WHERE team_id = ? AND league_id = ?
            ORDER BY season DESC LIMIT 1
        """, (home_team_id, league_id))
        home_stand = cursor.fetchone()

        cursor.execute("""
            SELECT position, points, played FROM league_standings
            WHERE team_id = ? AND league_id = ?
            ORDER BY season DESC LIMIT 1
        """, (away_team_id, league_id))
        away_stand = cursor.fetchone()

        # 获取积分榜总数
        cursor.execute("SELECT COUNT(*) as total FROM league_standings WHERE league_id = ?", (league_id,))
        total_teams = cursor.fetchone()['total'] or 20

        if home_stand:
            pos, pts, played = home_stand['position'], home_stand['points'], home_stand['played']
            # 争冠区
            if pos <= 2:
                reasons["home"]["must_win"].append("争冠关键战，需要3分保持争冠希望")
            # 欧战区
            elif pos <= 4:
                reasons["home"]["must_not_lose"].append("欧战资格争夺，不能掉队")
            # 保级区
            elif pos >= total_teams - 3:
                reasons["home"]["must_not_lose"].append("保级压力巨大，急需积分")
            # 中游
            else:
                reasons["home"]["can_afford_loss"].append("中游位置，压力相对较小")

        if away_stand:
            pos, pts, played = away_stand['position'], away_stand['points'], away_stand['played']
            if pos <= 2:
                reasons["away"]["must_win"].append("争冠关键战，需要3分保持争冠希望")
            elif pos <= 4:
                reasons["away"]["must_not_lose"].append("欧战资格争夺，不能掉队")
            elif pos >= total_teams - 3:
                reasons["away"]["must_not_lose"].append("保级压力巨大，急需积分")
            else:
                reasons["away"]["can_afford_loss"].append("中游位置，压力相对较小")

    # 基于近期状态分析
    def get_recent_form(team_id):
        cursor.execute("""
            SELECT COUNT(*) as matches,
                   SUM(CASE WHEN (home_team_id = ? AND home_goals > away_goals) OR
                               (away_team_id = ? AND away_goals > home_goals) THEN 1 ELSE 0 END) as wins
            FROM matches
            WHERE (home_team_id = ? OR away_team_id = ?) AND home_goals IS NOT NULL
            ORDER BY match_date DESC LIMIT 5
        """, (team_id, team_id, team_id, team_id))
        r = cursor.fetchone()
        return r['wins'] / r['matches'] if r and r['matches'] > 0 else 0.5

    home_form = get_recent_form(home_team_id)
    away_form = get_recent_form(away_team_id)

    if home_form < 0.2:
        reasons["home"]["must_not_lose"].append("近期状态低迷，急需反弹")
    if away_form < 0.2:
        reasons["away"]["must_not_lose"].append("近期状态低迷，急需反弹")

    return reasons


def get_rivalry_analysis(home_team_id, away_team_id, home_team, away_team, h2h_stats, conn):
    """分析敌对关系和仇恨值"""
    cursor = conn.cursor()

    rivalry = {
        "level": "普通",
        "description": "两队无特殊恩怨",
        "indicators": []
    }

    # 基于交锋次数判断
    total_h2h = h2h_stats.get('total', 0)
    if total_h2h >= 20:
        rivalry["level"] = "宿敌"
        rivalry["indicators"].append(f"历史交锋{total_h2h}次，老对手")

    # 检查是否有德比关系（同城德比）
    cursor.execute("SELECT country, stadium FROM teams WHERE team_id = ?", (home_team_id,))
    home_info = cursor.fetchone()
    cursor.execute("SELECT country, stadium FROM teams WHERE team_id = ?", (away_team_id,))
    away_info = cursor.fetchone()

    if home_info and away_info:
        # 检查是否同国
        if home_info['country'] and away_info['country'] and home_info['country'] == away_info['country']:
            if total_h2h >= 10:
                rivalry["level"] = "国家德比"
                rivalry["description"] = "国内豪门对决"
                rivalry["indicators"].append("国家德比")

    # 检查近期交锋是否有大比分/冲突
    if total_h2h > 0:
        home_wins = h2h_stats.get('home_wins', 0)
        away_wins = h2h_stats.get('away_wins', 0)

        # 一方压制另一方
        if home_wins > away_wins * 2 and home_wins >= 5:
            rivalry["indicators"].append(f"主队历史压制客队 ({home_wins}胜 vs {away_wins}胜)")
        elif away_wins > home_wins * 2 and away_wins >= 5:
            rivalry["indicators"].append(f"客队历史压制主队 ({away_wins}胜 vs {home_wins}胜)")

    # 特殊德比识别
    derbies = {
        ("Manchester United", "Manchester City"): "曼彻斯特德比",
        ("Liverpool", "Manchester United"): "双红会",
        ("Real Madrid", "Barcelona"): "国家德比",
        ("Arsenal", "Tottenham"): "北伦敦德比",
        ("AC Milan", "Inter"): "米兰德比",
        ("Juventus", "Inter"): "意大利德比",
        ("Bayern Munich", "Borussia Dortmund"): "德国国家德比",
    }

    for (t1, t2), name in derbies.items():
        if (home_team == t1 and away_team == t2) or (home_team == t2 and away_team == t1):
            rivalry["level"] = name
            rivalry["description"] = f"{name}，焦点之战"
            rivalry["indicators"] = [name]
            break

    return rivalry


def get_ht_stats_analysis(home_team_id, away_team_id, conn):
    """分析半场战绩"""
    cursor = conn.cursor()

    def get_team_ht_stats(team_id, limit=10):
        cursor.execute("""
            SELECT
                COUNT(*) as matches,
                SUM(CASE
                    WHEN (home_team_id = ? AND home_goals > away_goals) OR
                         (away_team_id = ? AND away_goals > home_goals) THEN 1
                    ELSE 0
                END) as wins,
                SUM(CASE WHEN home_goals = away_goals THEN 1 ELSE 0 END) as draws
            FROM (
                SELECT home_team_id, away_team_id,
                       COALESCE(home_goals_ht, 0) as home_goals,
                       COALESCE(away_goals_ht, 0) as away_goals
                FROM matches
                WHERE (home_team_id = ? OR away_team_id = ?) AND home_goals IS NOT NULL
                ORDER BY match_date DESC LIMIT ?
            )
        """, (team_id, team_id, team_id, team_id, limit))
        result = cursor.fetchone()
        if result and result['matches'] > 0:
            return {
                "wins": result['wins'] or 0,
                "draws": result['draws'] or 0,
                "losses": result['matches'] - (result['wins'] or 0) - (result['draws'] or 0)
            }
        return {"wins": 0, "draws": 0, "losses": 0}

    return {
        "home": get_team_ht_stats(home_team_id),
        "away": get_team_ht_stats(away_team_id)
    }


def get_goal_timing_analysis(home_team_id, away_team_id, conn):
    """分析进球时间分布"""
    cursor = conn.cursor()

    def get_team_goal_timing(team_id):
        # 从statsbomb_shots表获取真实进球时间分布
        # 注意：需要team_id字段已正确填充
        cursor.execute("""
            SELECT minute
            FROM statsbomb_shots
            WHERE team_id = ? AND shot_outcome = 'Goal'
            AND minute IS NOT NULL
        """, (team_id,))
        goals = [row['minute'] for row in cursor.fetchall()]

        if not goals:
            return {"by_period": [0, 0, 0, 0, 0, 0], "total": 0}

        # 按6个时间段分类
        p1 = len([g for g in goals if g <= 15])      # 0-15分钟
        p2 = len([g for g in goals if 16 <= g <= 30]) # 16-30分钟
        p3 = len([g for g in goals if 31 <= g <= 45]) # 31-45分钟
        p4 = len([g for g in goals if 46 <= g <= 60]) # 46-60分钟
        p5 = len([g for g in goals if 61 <= g <= 75]) # 61-75分钟
        p6 = len([g for g in goals if g >= 76])       # 76-90分钟

        return {"by_period": [p1, p2, p3, p4, p5, p6], "total": len(goals)}

    return {
        "home": get_team_goal_timing(home_team_id),
        "away": get_team_goal_timing(away_team_id)
    }


def get_team_news_analysis(home_team_id, away_team_id, conn):
    """分析球队动态（简化版，返回基于数据的推断）"""
    cursor = conn.cursor()
    news = {"home": [], "away": []}

    # 基于近期状态推断
    def get_team_status(team_id):
        cursor.execute("""
            SELECT COUNT(*) as matches,
                   SUM(CASE WHEN (home_team_id = ? AND home_goals > away_goals) OR
                               (away_team_id = ? AND away_goals > home_goals) THEN 1 ELSE 0 END) as wins,
                   SUM(CASE WHEN home_team_id = ? THEN home_goals ELSE away_goals END) as goals
            FROM matches
            WHERE (home_team_id = ? OR away_team_id = ?) AND home_goals IS NOT NULL
            ORDER BY match_date DESC LIMIT 5
        """, (team_id, team_id, team_id, team_id, team_id))
        return cursor.fetchone()

    home_status = get_team_status(home_team_id)
    away_status = get_team_status(away_team_id)

    if home_status:
        win_rate = home_status['wins'] / home_status['matches'] if home_status['matches'] > 0 else 0
        if win_rate >= 0.6:
            news["home"].append({"text": "近期状态出色", "impact": "positive"})
        elif win_rate <= 0.2:
            news["home"].append({"text": "近期状态低迷", "impact": "negative"})

        if home_status['goals'] >= 10:
            news["home"].append({"text": "进攻火力充足", "impact": "positive"})
        elif home_status['goals'] <= 3:
            news["home"].append({"text": "进攻端乏力", "impact": "negative"})

    if away_status:
        win_rate = away_status['wins'] / away_status['matches'] if away_status['matches'] > 0 else 0
        if win_rate >= 0.6:
            news["away"].append({"text": "近期状态出色", "impact": "positive"})
        elif win_rate <= 0.2:
            news["away"].append({"text": "近期状态低迷", "impact": "negative"})

        if away_status['goals'] >= 10:
            news["away"].append({"text": "进攻火力充足", "impact": "positive"})
        elif away_status['goals'] <= 3:
            news["away"].append({"text": "进攻端乏力", "impact": "negative"})

    return news


@app.get("/api/v1/matches/{match_id}/full-analysis")
async def get_match_full_analysis(match_id: str):
    """获取比赛全面分析（用于详情页）"""
    conn = get_db()
    cursor = conn.cursor()

    try:
        # 获取比赛信息
        cursor.execute("""
            SELECT
                m.match_id,
                m.match_date,
                m.match_time,
                m.time_type,
                m.home_team_id,
                m.away_team_id,
                m.home_goals,
                m.away_goals,
                ht.name_en as home_team,
                at.name_en as away_team,
                l.name_en as league,
                l.league_id,
                l.country as league_country
            FROM matches m
            JOIN teams ht ON m.home_team_id = ht.team_id
            JOIN teams at ON m.away_team_id = at.team_id
            JOIN leagues l ON m.league_id = l.league_id
            WHERE m.match_id = ?
        """, (match_id,))
        match = cursor.fetchone()

        if not match:
            conn.close()
            return {"error": "比赛不存在"}

        home_team_id = match['home_team_id']
        away_team_id = match['away_team_id']
        league_id = match['league_id']

        # 并行获取所有分析数据
        # 1. Elo评分
        home_elo = get_elo_rating(home_team_id, conn)
        away_elo = get_elo_rating(away_team_id, conn)

        # 2. 预测
        prediction = predict_match(home_team_id, away_team_id, conn)

        # 3. 近期状态 - 多时间段
        def get_form_stats(team_id, limit=10):
            cursor.execute("""
                SELECT
                    COUNT(*) as matches,
                    SUM(CASE
                        WHEN (m.home_team_id = ? AND m.home_goals > m.away_goals) OR
                             (m.away_team_id = ? AND m.away_goals > m.home_goals) THEN 1
                        ELSE 0
                    END) as wins,
                    SUM(CASE WHEN m.home_goals = m.away_goals THEN 1 ELSE 0 END) as draws,
                    SUM(CASE WHEN m.home_team_id = ? THEN m.home_goals ELSE m.away_goals END) as goals_for,
                    SUM(CASE WHEN m.home_team_id = ? THEN m.away_goals ELSE m.home_goals END) as goals_against
                FROM (
                    SELECT * FROM matches
                    WHERE (home_team_id = ? OR away_team_id = ?)
                    AND home_goals IS NOT NULL
                    ORDER BY match_date DESC
                    LIMIT ?
                ) m
            """, (team_id, team_id, team_id, team_id, team_id, team_id, limit))
            return cursor.fetchone()

        # 获取多时间段数据
        home_form_6 = get_form_stats(home_team_id, 6)
        home_form_10 = get_form_stats(home_team_id, 10)
        home_form_20 = get_form_stats(home_team_id, 20)
        away_form_6 = get_form_stats(away_team_id, 6)
        away_form_10 = get_form_stats(away_team_id, 10)
        away_form_20 = get_form_stats(away_team_id, 20)

        # 4. H2H记录
        cursor.execute("""
            SELECT
                m.match_id,
                m.match_date,
                m.home_team_id,
                m.away_team_id,
                ht.name_en as home_team,
                at.name_en as away_team,
                m.home_goals,
                m.away_goals
            FROM matches m
            JOIN teams ht ON m.home_team_id = ht.team_id
            JOIN teams at ON m.away_team_id = at.team_id
            WHERE ((m.home_team_id = ? AND m.away_team_id = ?) OR
                   (m.home_team_id = ? AND m.away_team_id = ?))
            AND m.home_goals IS NOT NULL
            ORDER BY m.match_date DESC
            LIMIT 10
        """, (home_team_id, away_team_id, away_team_id, home_team_id))
        h2h_matches = [dict(row) for row in cursor.fetchall()]

        # 为H2H比赛添加中文名
        for m in h2h_matches:
            m['home_team_cn'] = get_chinese_team_name(m['home_team'])
            m['away_team_cn'] = get_chinese_team_name(m['away_team'])

        # H2H统计
        h2h_stats = {"home_wins": 0, "away_wins": 0, "draws": 0, "total": len(h2h_matches)}
        for m in h2h_matches:
            if m['home_goals'] > m['away_goals']:
                if m['home_team_id'] == home_team_id:
                    h2h_stats['home_wins'] += 1
                else:
                    h2h_stats['away_wins'] += 1
            elif m['home_goals'] < m['away_goals']:
                if m['away_team_id'] == away_team_id:
                    h2h_stats['away_wins'] += 1
                else:
                    h2h_stats['home_wins'] += 1
            else:
                h2h_stats['draws'] += 1

        # 5. 主客场表现 - 多时间段
        def get_home_away_stats(team_id, is_home, limit=10):
            field = 'home' if is_home else 'away'
            cursor.execute(f"""
                SELECT
                    COUNT(*) as matches,
                    SUM(CASE WHEN {field}_goals > {'away' if is_home else 'home'}_goals THEN 1 ELSE 0 END) as wins,
                    SUM(CASE WHEN home_goals = away_goals THEN 1 ELSE 0 END) as draws,
                    SUM({field}_goals) as goals_for,
                    SUM({'away' if is_home else 'home'}_goals) as goals_against
                FROM (
                    SELECT * FROM matches
                    WHERE {field}_team_id = ?
                    AND home_goals IS NOT NULL
                    ORDER BY match_date DESC
                    LIMIT ?
                )
            """, (team_id, limit))
            return cursor.fetchone()

        # 主队主场多时间段
        home_home_6 = get_home_away_stats(home_team_id, True, 6)
        home_home_10 = get_home_away_stats(home_team_id, True, 10)
        home_home_20 = get_home_away_stats(home_team_id, True, 20)
        # 客队客场多时间段
        away_away_6 = get_home_away_stats(away_team_id, False, 6)
        away_away_10 = get_home_away_stats(away_team_id, False, 10)
        away_away_20 = get_home_away_stats(away_team_id, False, 20)

        # 6. 休息天数
        def get_last_match_date(team_id, before_date):
            cursor.execute("""
                SELECT MAX(match_date) as last_match
                FROM matches
                WHERE (home_team_id = ? OR away_team_id = ?)
                AND match_date < ?
                AND home_goals IS NOT NULL
            """, (team_id, team_id, before_date))
            result = cursor.fetchone()
            return result['last_match'] if result else None

        match_date = match['match_date']
        home_last = get_last_match_date(home_team_id, match_date)
        away_last = get_last_match_date(away_team_id, match_date)

        home_rest = None
        away_rest = None
        if home_last:
            from datetime import datetime
            home_rest = (datetime.strptime(match_date, '%Y-%m-%d') -
                        datetime.strptime(home_last, '%Y-%m-%d')).days
        if away_last:
            from datetime import datetime
            away_rest = (datetime.strptime(match_date, '%Y-%m-%d') -
                        datetime.strptime(away_last, '%Y-%m-%d')).days

        # 在关闭连接前获取新增分析数据
        recent_trend = get_recent_trend_analysis(home_team_id, away_team_id, conn)
        match_importance = get_match_importance_analysis(home_team_id, away_team_id, league_id, match['match_date'], conn)
        psychology = get_h2h_psychology_analysis(home_team_id, away_team_id, h2h_stats, conn)
        attack_efficiency = get_attack_efficiency_analysis(home_team_id, away_team_id, conn)

        # 新增分析模块
        over_under = get_over_under_analysis(home_team_id, away_team_id, prediction, conn)
        score_prediction = get_score_prediction(prediction, h2h_stats)
        betting_analysis = get_betting_analysis(prediction, home_elo - away_elo, h2h_stats)
        odds_analysis = get_odds_analysis(match_id, prediction, conn)

        # 新增更多分析模块
        future_fixtures = get_future_fixtures_analysis(home_team_id, away_team_id, match['match_date'], conn)
        critical_reasons = get_match_critical_reasons(home_team_id, away_team_id, league_id, match['match_date'], conn)
        rivalry = get_rivalry_analysis(home_team_id, away_team_id, match['home_team'], match['away_team'], h2h_stats, conn)
        ht_stats = get_ht_stats_analysis(home_team_id, away_team_id, conn)
        goal_timing = get_goal_timing_analysis(home_team_id, away_team_id, conn)
        team_news = get_team_news_analysis(home_team_id, away_team_id, conn)

        conn.close()

        # 转换北京时间
        time_type = match['time_type'] if 'time_type' in match.keys() else 'local'
        time_info = convert_to_beijing_time(match['match_date'], match['match_time'], match['league_country'], time_type)

        return {
            "data": {
                "match": {
                    "match_id": match_id,
                    "match_date": match['match_date'],
                    "match_time": match['match_time'],
                    "beijing_time": time_info['beijing_time'],
                    "local_time": time_info['local_time'],
                    "home_team": match['home_team'],
                    "away_team": match['away_team'],
                    "home_team_id": match['home_team_id'],
                    "away_team_id": match['away_team_id'],
                    "home_team_cn": get_chinese_team_name(match['home_team']),
                    "away_team_cn": get_chinese_team_name(match['away_team']),
                    "home_goals": match['home_goals'],
                    "away_goals": match['away_goals'],
                    "league": match['league'],
                    "league_cn": get_chinese_league_name(match['league'])
                },
                "elo": {
                    "home": round(home_elo, 0),
                    "away": round(away_elo, 0),
                    "diff": round(home_elo - away_elo, 0)
                },
                "prediction": {
                    "home_win_prob": prediction['home_win_prob'],
                    "draw_prob": prediction['draw_prob'],
                    "away_win_prob": prediction['away_win_prob'],
                    "predicted_home_goals": round(prediction['predicted_home_goals'], 2),
                    "predicted_away_goals": round(prediction['predicted_away_goals'], 2)
                },
                "form": {
                    "home": {
                        "last6": {
                            "matches": home_form_6['matches'] or 0,
                            "wins": home_form_6['wins'] or 0,
                            "draws": home_form_6['draws'] or 0,
                            "losses": (home_form_6['matches'] or 0) - (home_form_6['wins'] or 0) - (home_form_6['draws'] or 0),
                            "goals_for": home_form_6['goals_for'] or 0,
                            "goals_against": home_form_6['goals_against'] or 0
                        },
                        "last10": {
                            "matches": home_form_10['matches'] or 0,
                            "wins": home_form_10['wins'] or 0,
                            "draws": home_form_10['draws'] or 0,
                            "losses": (home_form_10['matches'] or 0) - (home_form_10['wins'] or 0) - (home_form_10['draws'] or 0),
                            "goals_for": home_form_10['goals_for'] or 0,
                            "goals_against": home_form_10['goals_against'] or 0
                        },
                        "last20": {
                            "matches": home_form_20['matches'] or 0,
                            "wins": home_form_20['wins'] or 0,
                            "draws": home_form_20['draws'] or 0,
                            "losses": (home_form_20['matches'] or 0) - (home_form_20['wins'] or 0) - (home_form_20['draws'] or 0),
                            "goals_for": home_form_20['goals_for'] or 0,
                            "goals_against": home_form_20['goals_against'] or 0
                        }
                    },
                    "away": {
                        "last6": {
                            "matches": away_form_6['matches'] or 0,
                            "wins": away_form_6['wins'] or 0,
                            "draws": away_form_6['draws'] or 0,
                            "losses": (away_form_6['matches'] or 0) - (away_form_6['wins'] or 0) - (away_form_6['draws'] or 0),
                            "goals_for": away_form_6['goals_for'] or 0,
                            "goals_against": away_form_6['goals_against'] or 0
                        },
                        "last10": {
                            "matches": away_form_10['matches'] or 0,
                            "wins": away_form_10['wins'] or 0,
                            "draws": away_form_10['draws'] or 0,
                            "losses": (away_form_10['matches'] or 0) - (away_form_10['wins'] or 0) - (away_form_10['draws'] or 0),
                            "goals_for": away_form_10['goals_for'] or 0,
                            "goals_against": away_form_10['goals_against'] or 0
                        },
                        "last20": {
                            "matches": away_form_20['matches'] or 0,
                            "wins": away_form_20['wins'] or 0,
                            "draws": away_form_20['draws'] or 0,
                            "losses": (away_form_20['matches'] or 0) - (away_form_20['wins'] or 0) - (away_form_20['draws'] or 0),
                            "goals_for": away_form_20['goals_for'] or 0,
                            "goals_against": away_form_20['goals_against'] or 0
                        }
                    }
                },
                "h2h": {
                    "stats": h2h_stats,
                    "matches": h2h_matches[:5]  # 最近5场交锋
                },
                "home_away": {
                    "home_at_home": {
                        "last6": {
                            "matches": home_home_6['matches'] or 0,
                            "wins": home_home_6['wins'] or 0,
                            "draws": home_home_6['draws'] or 0,
                            "losses": (home_home_6['matches'] or 0) - (home_home_6['wins'] or 0) - (home_home_6['draws'] or 0),
                            "goals_for": home_home_6['goals_for'] or 0,
                            "goals_against": home_home_6['goals_against'] or 0
                        },
                        "last10": {
                            "matches": home_home_10['matches'] or 0,
                            "wins": home_home_10['wins'] or 0,
                            "draws": home_home_10['draws'] or 0,
                            "losses": (home_home_10['matches'] or 0) - (home_home_10['wins'] or 0) - (home_home_10['draws'] or 0),
                            "goals_for": home_home_10['goals_for'] or 0,
                            "goals_against": home_home_10['goals_against'] or 0
                        },
                        "last20": {
                            "matches": home_home_20['matches'] or 0,
                            "wins": home_home_20['wins'] or 0,
                            "draws": home_home_20['draws'] or 0,
                            "losses": (home_home_20['matches'] or 0) - (home_home_20['wins'] or 0) - (home_home_20['draws'] or 0),
                            "goals_for": home_home_20['goals_for'] or 0,
                            "goals_against": home_home_20['goals_against'] or 0
                        }
                    },
                    "away_at_away": {
                        "last6": {
                            "matches": away_away_6['matches'] or 0,
                            "wins": away_away_6['wins'] or 0,
                            "draws": away_away_6['draws'] or 0,
                            "losses": (away_away_6['matches'] or 0) - (away_away_6['wins'] or 0) - (away_away_6['draws'] or 0),
                            "goals_for": away_away_6['goals_for'] or 0,
                            "goals_against": away_away_6['goals_against'] or 0
                        },
                        "last10": {
                            "matches": away_away_10['matches'] or 0,
                            "wins": away_away_10['wins'] or 0,
                            "draws": away_away_10['draws'] or 0,
                            "losses": (away_away_10['matches'] or 0) - (away_away_10['wins'] or 0) - (away_away_10['draws'] or 0),
                            "goals_for": away_away_10['goals_for'] or 0,
                            "goals_against": away_away_10['goals_against'] or 0
                        },
                        "last20": {
                            "matches": away_away_20['matches'] or 0,
                            "wins": away_away_20['wins'] or 0,
                            "draws": away_away_20['draws'] or 0,
                            "losses": (away_away_20['matches'] or 0) - (away_away_20['wins'] or 0) - (away_away_20['draws'] or 0),
                            "goals_for": away_away_20['goals_for'] or 0,
                            "goals_against": away_away_20['goals_against'] or 0
                        }
                    }
                },
                "rest_days": {
                    "home": home_rest,
                    "away": away_rest,
                    "diff": (home_rest - away_rest) if home_rest and away_rest else None
                },
                # 新增分析模块
                "recent_trend": recent_trend,
                "match_importance": match_importance,
                "psychology": psychology,
                "attack_efficiency": attack_efficiency,
                # 新增投注分析模块
                "over_under": over_under,
                "score_prediction": score_prediction,
                "betting_analysis": betting_analysis,
                "odds_analysis": odds_analysis,
                # 新增更多分析模块
                "future_fixtures": future_fixtures,
                "critical_reasons": critical_reasons,
                "rivalry": rivalry,
                "ht_stats": ht_stats,
                "goal_timing": goal_timing,
                "team_news": team_news
            }
        }
    except Exception as e:
        conn.close()
        return {"error": str(e)}


# 启动配置
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)


# ==================== 更多高级分析功能 ====================

@app.get("/api/v1/analytics/home-away-performance")
async def analyze_home_away_performance(team_id: int, league_id: int = None, season: str = None):
    """分析球队主客场表现差异"""

    conn = get_db()
    cursor = conn.cursor()

    try:
        # 获取球队信息
        cursor.execute("SELECT name_en FROM teams WHERE team_id = ?", (team_id,))
        team = cursor.fetchone()
        if not team:
            conn.close()
            return {"error": "球队不存在"}

        # 主场表现
        cursor.execute("""
            SELECT
                COUNT(*) as matches,
                SUM(CASE WHEN home_goals > away_goals THEN 1 ELSE 0 END) as wins,
                SUM(CASE WHEN home_goals = away_goals THEN 1 ELSE 0 END) as draws,
                SUM(CASE WHEN home_goals < away_goals THEN 1 ELSE 0 END) as losses,
                SUM(home_goals) as goals_for,
                SUM(away_goals) as goals_against,
                AVG(home_goals) as avg_goals,
                AVG(away_goals) as avg_conceded
            FROM matches m
            WHERE m.home_team_id = ?
            AND m.home_goals IS NOT NULL
        """, (team_id,))
        home_stats = cursor.fetchone()

        # 客场表现
        cursor.execute("""
            SELECT
                COUNT(*) as matches,
                SUM(CASE WHEN away_goals > home_goals THEN 1 ELSE 0 END) as wins,
                SUM(CASE WHEN away_goals = home_goals THEN 1 ELSE 0 END) as draws,
                SUM(CASE WHEN away_goals < home_goals THEN 1 ELSE 0 END) as losses,
                SUM(away_goals) as goals_for,
                SUM(home_goals) as goals_against,
                AVG(away_goals) as avg_goals,
                AVG(home_goals) as avg_conceded
            FROM matches m
            WHERE m.away_team_id = ?
            AND m.away_goals IS NOT NULL
        """, (team_id,))
        away_stats = cursor.fetchone()

        # 计算主场优势
        home_win_rate = (home_stats['wins'] or 0) / (home_stats['matches'] or 1) * 100
        away_win_rate = (away_stats['wins'] or 0) / (away_stats['matches'] or 1) * 100

        home_points_per_game = ((home_stats['wins'] or 0) * 3 + (home_stats['draws'] or 0)) / (home_stats['matches'] or 1)
        away_points_per_game = ((away_stats['wins'] or 0) * 3 + (away_stats['draws'] or 0)) / (away_stats['matches'] or 1)

        # 判断主场龙/客场虫属性
        home_advantage_type = "normal"
        if home_win_rate - away_win_rate > 20:
            home_advantage_type = "home_dragon"  # 主场龙
        elif away_win_rate - home_win_rate > 10:
            home_advantage_type = "away_strong"  # 客场强
        elif home_win_rate < 30 and away_win_rate < 30:
            home_advantage_type = "weak_both"  # 主客场都弱

        conn.close()

        return {
            "data": {
                "team": team['name_en'],
                "team_cn": get_chinese_team_name(team['name_en']),
                "home": {
                    "matches": home_stats['matches'] or 0,
                    "wins": home_stats['wins'] or 0,
                    "draws": home_stats['draws'] or 0,
                    "losses": home_stats['losses'] or 0,
                    "goals_for": home_stats['goals_for'] or 0,
                    "goals_against": home_stats['goals_against'] or 0,
                    "avg_goals": round(home_stats['avg_goals'] or 0, 2),
                    "avg_conceded": round(home_stats['avg_conceded'] or 0, 2),
                    "win_rate": round(home_win_rate, 1),
                    "points_per_game": round(home_points_per_game, 2)
                },
                "away": {
                    "matches": away_stats['matches'] or 0,
                    "wins": away_stats['wins'] or 0,
                    "draws": away_stats['draws'] or 0,
                    "losses": away_stats['losses'] or 0,
                    "goals_for": away_stats['goals_for'] or 0,
                    "goals_against": away_stats['goals_against'] or 0,
                    "avg_goals": round(away_stats['avg_goals'] or 0, 2),
                    "avg_conceded": round(away_stats['avg_conceded'] or 0, 2),
                    "win_rate": round(away_win_rate, 1),
                    "points_per_game": round(away_points_per_game, 2)
                },
                "home_advantage_type": home_advantage_type,
                "home_advantage_score": round(home_win_rate - away_win_rate, 1),
                "summary": get_home_advantage_summary(home_advantage_type, home_win_rate, away_win_rate)
            }
        }
    except Exception as e:
        conn.close()
        return {"error": str(e)}


def get_home_advantage_summary(type_name, home_rate, away_rate):
    """生成主场优势描述"""
    summaries = {
        "home_dragon": f"典型主场龙，主场胜率{home_rate}%远超客场{away_rate}%，主场作战优势明显",
        "away_strong": f"客场表现反而更好，客场胜率{away_rate}%高于主场{home_rate}%",
        "weak_both": f"主客场表现均较弱，整体实力有限",
        "normal": f"主客场表现相对均衡，主场胜率{home_rate}%，客场{away_rate}%"
    }
    return summaries.get(type_name, "数据不足")


@app.get("/api/v1/analytics/h2h-psychology")
async def analyze_h2h_psychology(team1_id: int, team2_id: int):
    """分析历史交锋心理压制"""

    conn = get_db()
    cursor = conn.cursor()

    try:
        # 获取球队信息
        cursor.execute("SELECT name_en FROM teams WHERE team_id = ?", (team1_id,))
        team1 = cursor.fetchone()
        cursor.execute("SELECT name_en FROM teams WHERE team_id = ?", (team2_id,))
        team2 = cursor.fetchone()

        if not team1 or not team2:
            conn.close()
            return {"error": "球队不存在"}

        # 获取历史交锋
        cursor.execute("""
            SELECT
                m.match_date,
                m.home_team_id,
                m.away_team_id,
                ht.name_en as home_team,
                at.name_en as away_team,
                m.home_goals,
                m.away_goals
            FROM matches m
            JOIN teams ht ON m.home_team_id = ht.team_id
            JOIN teams at ON m.away_team_id = at.team_id
            WHERE (m.home_team_id = ? AND m.away_team_id = ?)
               OR (m.home_team_id = ? AND m.away_team_id = ?)
            AND m.home_goals IS NOT NULL
            ORDER BY m.match_date DESC
            LIMIT 20
        """, (team1_id, team2_id, team2_id, team1_id))

        matches = cursor.fetchall()

        if not matches:
            conn.close()
            return {
                "data": {
                    "team1": team1['name_en'],
                    "team2": team2['name_en'],
                    "total_matches": 0,
                    "psychology": "unknown",
                    "summary": "无历史交锋记录"
                }
            }

        # 统计胜负
        team1_wins = 0
        team2_wins = 0
        draws = 0

        # 最近5场记录
        recent_5 = matches[:5]
        recent_team1_wins = 0
        recent_team2_wins = 0
        recent_draws = 0

        for match in matches:
            if match['home_goals'] == match['away_goals']:
                draws += 1
            elif match['home_goals'] > match['away_goals']:
                if match['home_team_id'] == team1_id:
                    team1_wins += 1
                else:
                    team2_wins += 1
            else:
                if match['away_team_id'] == team1_id:
                    team1_wins += 1
                else:
                    team2_wins += 1

        for match in recent_5:
            if match['home_goals'] == match['away_goals']:
                recent_draws += 1
            elif match['home_goals'] > match['away_goals']:
                if match['home_team_id'] == team1_id:
                    recent_team1_wins += 1
                else:
                    recent_team2_wins += 1
            else:
                if match['away_team_id'] == team1_id:
                    recent_team1_wins += 1
                else:
                    recent_team2_wins += 1

        total = len(matches)
        team1_win_rate = team1_wins / total * 100
        team2_win_rate = team2_wins / total * 100

        # 分析心理压制
        psychology = "balanced"
        psychology_summary = ""

        if team1_win_rate >= 60:
            psychology = "team1_dominates"
            psychology_summary = f"{team1['name_en']}对{team2['name_en']}有明显的心理压制，历史胜率{team1_win_rate:.1f}%"
        elif team2_win_rate >= 60:
            psychology = "team2_dominates"
            psychology_summary = f"{team2['name_en']}对{team1['name_en']}有明显的心理压制，历史胜率{team2_win_rate:.1f}%"
        elif recent_team1_wins >= 4:
            psychology = "team1_recent_dominates"
            psychology_summary = f"最近5场{team1['name_en']}赢下{recent_team1_wins}场，近期压制明显"
        elif recent_team2_wins >= 4:
            psychology = "team2_recent_dominates"
            psychology_summary = f"最近5场{team2['name_en']}赢下{recent_team2_wins}场，近期压制明显"

        # 连胜/连败分析
        consecutive_wins = 0
        consecutive_winner = None
        for match in matches:
            winner = None
            if match['home_goals'] > match['away_goals']:
                winner = match['home_team_id']
            elif match['away_goals'] > match['home_goals']:
                winner = match['away_team_id']

            if winner == consecutive_winner:
                consecutive_wins += 1
            elif winner:
                consecutive_winner = winner
                consecutive_wins = 1
            else:
                consecutive_winner = None
                consecutive_wins = 0

        if consecutive_wins >= 3:
            if consecutive_winner == team1_id:
                psychology_summary += f"，目前对{team2['name_en']}连胜{consecutive_wins}场"
            else:
                psychology_summary += f"，目前对{team1['name_en']}连胜{consecutive_wins}场"

        conn.close()

        return {
            "data": {
                "team1": {
                    "name": team1['name_en'],
                    "name_cn": get_chinese_team_name(team1['name_en']),
                    "wins": team1_wins,
                    "recent_wins": recent_team1_wins
                },
                "team2": {
                    "name": team2['name_en'],
                    "name_cn": get_chinese_team_name(team2['name_en']),
                    "wins": team2_wins,
                    "recent_wins": recent_team2_wins
                },
                "total_matches": total,
                "draws": draws,
                "team1_win_rate": round(team1_win_rate, 1),
                "team2_win_rate": round(team2_win_rate, 1),
                "psychology": psychology,
                "summary": psychology_summary or "双方历史交锋相对均衡",
                "consecutive_wins": consecutive_wins if consecutive_wins >= 3 else 0
            }
        }
    except Exception as e:
        conn.close()
        return {"error": str(e)}


@app.get("/api/v1/analytics/match-importance")
async def analyze_match_importance(
    home_team_id: int,
    away_team_id: int,
    league_id: int,
    match_date: str = None
):
    """分析比赛重要性评分"""

    conn = get_db()
    cursor = conn.cursor()

    try:
        # 获取球队信息
        cursor.execute("SELECT name_en FROM teams WHERE team_id = ?", (home_team_id,))
        home_team = cursor.fetchone()
        cursor.execute("SELECT name_en FROM teams WHERE team_id = ?", (away_team_id,))
        away_team = cursor.fetchone()

        if not home_team or not away_team:
            conn.close()
            return {"error": "球队不存在"}

        # 获取当前赛季
        cursor.execute("""
            SELECT s.season_name FROM seasons s
            WHERE s.league_id = ? ORDER BY s.season_name DESC LIMIT 1
        """, (league_id,))
        season_row = cursor.fetchone()
        season = season_row['season_name'] if season_row else None

        if not season:
            conn.close()
            return {"error": "无赛季数据"}

        # 获取积分榜
        home_position = get_team_league_position(home_team_id, league_id, season, conn)
        away_position = get_team_league_position(away_team_id, league_id, season, conn)

        # 计算比赛重要性
        importance_score = 0
        importance_factors = []

        # 联赛重要性（顶级联赛更重要）
        league_importance = get_league_importance(league_id, conn)
        importance_score += league_importance

        # 争冠战
        if home_position and away_position:
            if home_position['position'] <= 3 and away_position['position'] <= 3:
                importance_score += 30
                importance_factors.append("争冠集团对决")
            elif home_position['position'] <= 3 or away_position['position'] <= 3:
                importance_score += 15
                importance_factors.append("争冠球队参赛")

            # 保级战
            total_teams = home_position['total_teams']
            relegation_zone = total_teams - 3
            if home_position['position'] >= relegation_zone and away_position['position'] >= relegation_zone:
                importance_score += 25
                importance_factors.append("保级生死战")
            elif home_position['position'] >= relegation_zone - 2 or away_position['position'] >= relegation_zone - 2:
                importance_score += 15
                importance_factors.append("保级关键战")

            # 欧战资格争夺
            europe_zone = min(4, int(total_teams * 0.25))
            if abs(home_position['position'] - away_position['position']) <= 3:
                if home_position['position'] <= europe_zone + 2 and away_position['position'] <= europe_zone + 2:
                    importance_score += 20
                    importance_factors.append("欧战资格直接竞争")

            # 德比战（同城球队）
            cursor.execute("SELECT country FROM teams WHERE team_id IN (?, ?)", (home_team_id, away_team_id))
            team_countries = cursor.fetchall()
            if len(team_countries) == 2 and team_countries[0]['country'] == team_countries[1]['country']:
                # 检查是否同城（简化判断）
                importance_score += 10
                importance_factors.append("国内对决")

        # 赛季末关键战
        if match_date:
            from datetime import datetime
            match_dt = datetime.strptime(match_date, '%Y-%m-%d')
            # 假设赛季末是5月
            if match_dt.month >= 4:
                importance_score += 10
                importance_factors.append("赛季末关键阶段")

        # 重要性等级
        if importance_score >= 50:
            level = "critical"
            level_desc = "关键战役"
        elif importance_score >= 35:
            level = "important"
            level_desc = "重要比赛"
        elif importance_score >= 20:
            level = "normal"
            level_desc = "常规比赛"
        else:
            level = "minor"
            level_desc = "普通比赛"

        conn.close()

        return {
            "data": {
                "home_team": {
                    "name": home_team['name_en'],
                    "name_cn": get_chinese_team_name(home_team['name_en']),
                    "position": home_position['position'] if home_position else None
                },
                "away_team": {
                    "name": away_team['name_en'],
                    "name_cn": get_chinese_team_name(away_team['name_en']),
                    "position": away_position['position'] if away_position else None
                },
                "importance_score": importance_score,
                "level": level,
                "level_description": level_desc,
                "factors": importance_factors,
                "season": season
            }
        }
    except Exception as e:
        conn.close()
        return {"error": str(e)}


@app.get("/api/v1/analytics/recent-form-trend")
async def analyze_recent_form_trend(team_id: int, matches_count: int = 10):
    """分析球队近期走势趋势"""

    conn = get_db()
    cursor = conn.cursor()

    try:
        # 获取球队信息
        cursor.execute("SELECT name_en FROM teams WHERE team_id = ?", (team_id,))
        team = cursor.fetchone()
        if not team:
            conn.close()
            return {"error": "球队不存在"}

        # 获取近期比赛
        cursor.execute("""
            SELECT
                m.match_date,
                ht.name_en as home_team,
                at.name_en as away_team,
                m.home_team_id,
                m.away_team_id,
                m.home_goals,
                m.away_goals
            FROM matches m
            JOIN teams ht ON m.home_team_id = ht.team_id
            JOIN teams at ON m.away_team_id = at.team_id
            WHERE (m.home_team_id = ? OR m.away_team_id = ?)
            AND m.home_goals IS NOT NULL
            ORDER BY m.match_date DESC
            LIMIT ?
        """, (team_id, team_id, matches_count))

        recent_matches = cursor.fetchall()

        if not recent_matches:
            conn.close()
            return {
                "data": {
                    "team": team['name_en'],
                    "trend": "unknown",
                    "summary": "无近期比赛数据"
                }
            }

        # 计算走势
        results = []
        points_sequence = []

        for match in recent_matches:
            is_home = match['home_team_id'] == team_id
            team_goals = match['home_goals'] if is_home else match['away_goals']
            opponent_goals = match['away_goals'] if is_home else match['home_goals']

            if team_goals > opponent_goals:
                results.append('W')
                points_sequence.append(3)
            elif team_goals < opponent_goals:
                results.append('L')
                points_sequence.append(0)
            else:
                results.append('D')
                points_sequence.append(1)

        # 分析走势
        form_string = ''.join(results)

        # 计算趋势（比较前半段和后半段）
        half = len(points_sequence) // 2
        if half >= 3:
            first_half_avg = sum(points_sequence[:half]) / half
            second_half_avg = sum(points_sequence[half:]) / (len(points_sequence) - half)

            if second_half_avg > first_half_avg + 0.5:
                trend = "improving"
                trend_desc = "状态回升"
            elif second_half_avg < first_half_avg - 0.5:
                trend = "declining"
                trend_desc = "状态下滑"
            else:
                trend = "stable"
                trend_desc = "状态稳定"
        else:
            trend = "unknown"
            trend_desc = "数据不足"

        # 计算各项统计
        wins = results.count('W')
        draws = results.count('D')
        losses = results.count('L')
        total_points = sum(points_sequence)

        # 进球走势
        goals_sequence = []
        for match in recent_matches:
            is_home = match['home_team_id'] == team_id
            goals = match['home_goals'] if is_home else match['away_goals']
            goals_sequence.append(goals)

        avg_goals = sum(goals_sequence) / len(goals_sequence)

        # 连胜/连败分析
        current_streak = 0
        streak_type = None
        for r in results:
            if r == streak_type:
                current_streak += 1
            elif r in ['W', 'L']:
                streak_type = r
                current_streak = 1
            else:
                streak_type = None
                current_streak = 0

        conn.close()

        return {
            "data": {
                "team": {
                    "name": team['name_en'],
                    "name_cn": get_chinese_team_name(team['name_en'])
                },
                "form_string": form_string,
                "wins": wins,
                "draws": draws,
                "losses": losses,
                "total_points": total_points,
                "avg_points_per_game": round(total_points / len(results), 2),
                "avg_goals": round(avg_goals, 2),
                "trend": trend,
                "trend_description": trend_desc,
                "current_streak": {
                    "type": streak_type,
                    "count": current_streak,
                    "description": f"{'连胜' if streak_type == 'W' else '连败' if streak_type == 'L' else '无'}{current_streak}场" if streak_type else "无连续"
                },
                "matches": [dict(m) for m in recent_matches[:5]]
            }
        }
    except Exception as e:
        conn.close()
        return {"error": str(e)}


# ==================== 联赛规则相关 ====================

@app.get("/api/v1/leagues/{league_id}/rules")
async def get_league_rules(league_id: int, season: str = None):
    """获取联赛规则信息（支持按赛季查询）"""
    conn = get_db()
    cursor = conn.cursor()

    # 获取联赛基本信息
    cursor.execute("""
        SELECT league_id, name_en as name, name_cn, country, tier
        FROM leagues WHERE league_id = ?
    """, (league_id,))
    league = cursor.fetchone()

    if not league:
        conn.close()
        return {"error": "联赛不存在"}

    # 获取规则信息（优先获取指定赛季，其次获取默认规则）
    if season:
        cursor.execute("""
            SELECT season, teams_count, matches_per_team, format_type, points_for_win,
                   champions_league_spots, europa_league_spots, conference_league_spots,
                   afc_champions_league_spots, afc_cup_spots,
                   copa_libertadores_spots, copa_sudamericana_spots,
                   promotion_spots, promotion_playoff_spots,
                   relegation_spots, relegation_playoff_spots,
                   has_playoffs, has_promotion_playoff, has_relegation_playoff,
                   playoff_teams, playoff_format,
                   has_conferences, has_split, has_two_stages,
                   conference_names, split_after_rounds,
                   draw_resolution, draw_points, penalty_win_points, penalty_lose_points,
                   season_start_month, season_end_month
            FROM league_rules WHERE league_id = ? AND season = ?
        """, (league_id, season))
        rule = cursor.fetchone()

        # 如果指定赛季没有规则，获取默认规则
        if not rule:
            cursor.execute("""
                SELECT season, teams_count, matches_per_team, format_type, points_for_win,
                       champions_league_spots, europa_league_spots, conference_league_spots,
                       afc_champions_league_spots, afc_cup_spots,
                       copa_libertadores_spots, copa_sudamericana_spots,
                       promotion_spots, promotion_playoff_spots,
                       relegation_spots, relegation_playoff_spots,
                       has_playoffs, has_promotion_playoff, has_relegation_playoff,
                       playoff_teams, playoff_format,
                       has_conferences, has_split, has_two_stages,
                       conference_names, split_after_rounds,
                       draw_resolution, draw_points, penalty_win_points, penalty_lose_points,
                       season_start_month, season_end_month
                FROM league_rules WHERE league_id = ? AND season IS NULL
            """, (league_id,))
            rule = cursor.fetchone()
    else:
        # 获取默认规则（season为NULL）
        cursor.execute("""
            SELECT season, teams_count, matches_per_team, format_type, points_for_win,
                   champions_league_spots, europa_league_spots, conference_league_spots,
                   afc_champions_league_spots, afc_cup_spots,
                   copa_libertadores_spots, copa_sudamericana_spots,
                   promotion_spots, promotion_playoff_spots,
                   relegation_spots, relegation_playoff_spots,
                   has_playoffs, has_promotion_playoff, has_relegation_playoff,
                   playoff_teams, playoff_format,
                   has_conferences, has_split, has_two_stages,
                   conference_names, split_after_rounds,
                   draw_resolution, draw_points, penalty_win_points, penalty_lose_points,
                   season_start_month, season_end_month
            FROM league_rules WHERE league_id = ? AND season IS NULL
        """, (league_id,))
        rule = cursor.fetchone()

    # 获取所有可用赛季列表
    cursor.execute("""
        SELECT DISTINCT season FROM league_rules
        WHERE league_id = ? AND season IS NOT NULL
        ORDER BY season DESC
    """, (league_id,))
    available_seasons = [row[0] for row in cursor.fetchall()]

    conn.close()

    data = dict(league)
    data['available_seasons'] = available_seasons

    if rule:
        rule_dict = dict(rule)
        # 处理布尔值
        rule_dict['has_playoffs'] = bool(rule_dict.get('has_playoffs'))
        rule_dict['has_promotion_playoff'] = bool(rule_dict.get('has_promotion_playoff'))
        rule_dict['has_relegation_playoff'] = bool(rule_dict.get('has_relegation_playoff'))
        rule_dict['has_conferences'] = bool(rule_dict.get('has_conferences'))
        rule_dict['has_split'] = bool(rule_dict.get('has_split'))
        rule_dict['has_two_stages'] = bool(rule_dict.get('has_two_stages'))
        # 处理分区名称
        if rule_dict.get('conference_names'):
            rule_dict['conference_names'] = rule_dict['conference_names'].split(',')
        data.update(rule_dict)

    return {"data": data}


# ==================== 球员统计相关 ====================

@app.get("/api/v1/leagues/{league_id}/teams-season")
async def get_league_teams_season(league_id: int, season: str = None):
    """获取联赛某赛季的球队列表（含主教练、阵型）"""
    conn = get_db()
    cursor = conn.cursor()

    if not season:
        cursor.execute("""
            SELECT s.season_name FROM seasons s
            WHERE s.league_id = ? ORDER BY s.season_name DESC LIMIT 1
        """, (league_id,))
        result = cursor.fetchone()
        season = result[0] if result else None

    if not season:
        conn.close()
        return {"data": [], "season": None}

    cursor.execute("""
        SELECT t.team_id, t.name_en as team_name, ts.head_coach, ts.head_coach_cn,
               ts.formation, ts.formation_main
        FROM teams t
        LEFT JOIN team_seasons ts ON t.team_id = ts.team_id AND ts.season = ? AND ts.league_id = ?
        WHERE t.team_id IN (
            SELECT DISTINCT home_team_id FROM matches m
            JOIN seasons s ON m.season_id = s.season_id
            WHERE m.league_id = ? AND s.season_name = ?
        )
        ORDER BY t.name_en
    """, (season, league_id, league_id, season))

    teams = []
    for row in cursor.fetchall():
        team = dict(row)
        team['team_name_cn'] = get_chinese_team_name(team['team_name'])
        teams.append(team)

    conn.close()
    return {"data": teams, "season": season}


@app.get("/api/v1/teams/{team_id}/season-info")
async def get_team_season_info(team_id: int, season: str = None):
    """获取球队某赛季信息（主教练、阵型、球员）"""
    conn = get_db()
    cursor = conn.cursor()

    if not season:
        cursor.execute("""
            SELECT season FROM team_seasons WHERE team_id = ?
            ORDER BY season DESC LIMIT 1
        """, (team_id,))
        result = cursor.fetchone()
        season = result[0] if result else None

    cursor.execute("""
        SELECT team_id, season, league_id, head_coach, head_coach_cn, formation, formation_main
        FROM team_seasons WHERE team_id = ? AND season = ?
    """, (team_id, season))

    info = cursor.fetchone()
    if not info:
        conn.close()
        return {"error": "暂无该球队赛季信息"}

    data = dict(info)

    # 获取球员名单
    cursor.execute("""
        SELECT p.player_id, p.name, p.name_cn, p.position, tp.shirt_number
        FROM team_players tp
        JOIN players p ON tp.player_id = p.player_id
        WHERE tp.team_id = ? AND tp.season = ?
        ORDER BY tp.shirt_number
    """, (team_id, season))

    data['players'] = [dict(row) for row in cursor.fetchall()]

    conn.close()
    return {"data": data}


@app.get("/api/v1/leagues/{league_id}/player-stats")
async def get_player_stats(league_id: int, season: str = None, stat_type: str = "goals", limit: int = 50):
    """获取球员统计数据

    stat_type: goals(射手榜), assists(助攻榜), cards(红黄牌), minutes(出场时间)
    """
    conn = get_db()
    cursor = conn.cursor()

    # 获取联赛名称
    cursor.execute("SELECT name_en as name FROM leagues WHERE league_id = ?", (league_id,))
    league = cursor.fetchone()
    if not league:
        conn.close()
        return {"error": "联赛不存在"}

    # 检查表是否存在
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='player_stats'")
    if not cursor.fetchone():
        conn.close()
        return {"data": [], "season": season, "stat_type": stat_type, "message": "球员统计数据暂未导入"}

    # 如果没有指定赛季，获取最新赛季
    if not season:
        cursor.execute("""
            SELECT DISTINCT season FROM player_stats
            WHERE league_id = ?
            ORDER BY season DESC LIMIT 1
        """, (league_id,))
        result = cursor.fetchone()
        season = result[0] if result else None

    if not season:
        conn.close()
        return {"data": [], "season": None, "stat_type": stat_type}

    # 根据统计类型排序
    order_map = {
        "goals": "goals DESC, assists DESC",
        "assists": "assists DESC, goals DESC",
        "cards": "yellow_cards DESC, red_cards DESC",
        "minutes": "minutes DESC"
    }
    order_by = order_map.get(stat_type, "goals DESC")

    cursor.execute(f"""
        SELECT player, player_cn, team, team_cn, nation, nation_cn, position,
               age, matches, starts, minutes, goals, assists, penalties,
               penalty_attempts, yellow_cards, red_cards,
               goals_per_90, assists_per_90, g_a_per_90
        FROM player_stats
        WHERE league_id = ? AND season = ?
        ORDER BY {order_by}
        LIMIT ?
    """, (league_id, season, limit))

    players = []
    for i, row in enumerate(cursor.fetchall()):
        p = dict(row)
        p["rank"] = i + 1
        players.append(p)

    conn.close()
    return {"data": players, "season": season, "stat_type": stat_type}


@app.get("/api/v1/leagues/{league_id}/matches/grouped")
async def get_matches_grouped(league_id: int, season: str = None):
    """获取按日期分组的比赛列表"""
    conn = get_db()
    cursor = conn.cursor()

    # 获取联赛国家
    cursor.execute("SELECT country, name_en as name FROM leagues WHERE league_id = ?", (league_id,))
    league_info = cursor.fetchone()
    if not league_info:
        conn.close()
        return {"error": "联赛不存在"}

    league_country = league_info["country"]
    league_name = league_info["name"]

    # 如果没有指定赛季，获取最新赛季
    if not season:
        cursor.execute("""
            SELECT s.season_name FROM seasons s
            WHERE s.league_id = ?
            ORDER BY s.season_name DESC LIMIT 1
        """, (league_id,))
        result = cursor.fetchone()
        season = result[0] if result else None

    if not season:
        conn.close()
        return {"data": [], "season": None}

    # 获取比赛
    cursor.execute("""
        SELECT
            m.match_id,
            m.match_date,
            m.match_time,
            ht.name_en as home_team,
            at.name_en as away_team,
            m.home_goals,
            m.away_goals,
            m.odds_home as home_odds,
            m.odds_draw as draw_odds,
            m.odds_away as away_odds,
            m.status
        FROM matches m
        JOIN teams ht ON m.home_team_id = ht.team_id
        JOIN teams at ON m.away_team_id = at.team_id
        JOIN seasons s ON m.season_id = s.season_id
        WHERE m.league_id = ? AND s.season_name = ?
        ORDER BY m.match_date DESC, m.match_time
    """, (league_id, season))

    matches = [dict(row) for row in cursor.fetchall()]

    # 添加中文名称和北京时间
    for match in matches:
        match["home_team_cn"] = get_chinese_team_name(match["home_team"])
        match["away_team_cn"] = get_chinese_team_name(match["away_team"])
        time_info = convert_to_beijing_time(match["match_date"], match["match_time"], league_country)
        match["beijing_time"] = time_info["beijing_time"]
        match["beijing_datetime"] = time_info["beijing_datetime"]
        match["local_time"] = time_info["local_time"]

        # 判断比赛状态
        if match["home_goals"] is not None and match["away_goals"] is not None:
            match["status_cn"] = "已结束"
        else:
            match["status_cn"] = "未开始"

    # 按日期分组
    grouped = {}
    for match in matches:
        date = match["match_date"]
        if date not in grouped:
            grouped[date] = {
                "date": date,
                "matches": [],
                "finished": 0,
                "upcoming": 0
            }
        grouped[date]["matches"].append(match)
        if match["status_cn"] == "已结束":
            grouped[date]["finished"] += 1
        else:
            grouped[date]["upcoming"] += 1

    # 转换为列表并排序
    result = sorted(grouped.values(), key=lambda x: x["date"], reverse=True)

    conn.close()
    return {"data": result, "season": season, "league": league_name, "league_cn": get_chinese_league_name(league_name)}


# ==================== 杯赛API ====================

@app.get("/api/v1/cups/{league_id}/seasons")
async def get_cup_seasons(league_id: int):
    """获取杯赛的所有赛季"""
    conn = get_db()
    cursor = conn.cursor()

    # 检查是否是杯赛
    cursor.execute("SELECT name_en as name, cycle_type as frequency FROM leagues WHERE league_id = ?", (league_id,))
    league_info = cursor.fetchone()
    if not league_info:
        conn.close()
        return {"data": [], "error": "联赛不存在"}

    # 从cup_matches表获取赛季列表
    cursor.execute('''
        SELECT DISTINCT season
        FROM cup_matches
        WHERE league_id = ?
        ORDER BY season DESC
    ''', (league_id,))
    seasons = [row[0] for row in cursor.fetchall()]

    conn.close()
    return {
        "data": seasons,
        "league_id": league_id,
        "league_name": league_info['name'],
        "league_cn": get_chinese_league_name(league_info['name']),
        "frequency": league_info['frequency'] or 'yearly'
    }


@app.get("/api/v1/cups/{league_id}/stages")
async def get_cup_stages(league_id: int, season: str = None):
    """获取杯赛某赛季的所有阶段"""
    conn = get_db()
    cursor = conn.cursor()

    # 获取联赛信息
    cursor.execute("SELECT name_en as name, cycle_type as frequency FROM leagues WHERE league_id = ?", (league_id,))
    league_info = cursor.fetchone()
    if not league_info:
        conn.close()
        return {"data": [], "error": "联赛不存在"}

    # 如果没有指定赛季，获取最新赛季
    if not season:
        cursor.execute('''
            SELECT season FROM cup_matches
            WHERE league_id = ?
            ORDER BY season DESC
            LIMIT 1
        ''', (league_id,))
        result = cursor.fetchone()
        if result:
            season = result[0]
        else:
            conn.close()
            return {"data": [], "season": None}

    # 获取该赛季的所有阶段
    cursor.execute('''
        SELECT DISTINCT stage, stage_order
        FROM cup_matches
        WHERE league_id = ? AND season = ?
        ORDER BY stage_order
    ''', (league_id, season))
    stages = [dict(row) for row in cursor.fetchall()]

    # 阶段中文名称映射
    stage_cn_map = {
        'qualifying': '预选赛',
        'playoff': '附加赛',
        'group': '小组赛',
        'league_phase': '联赛阶段',
        'round_of_32': '32强',
        'round_of_16': '16强',
        'quarterfinal': '八强',
        'semifinal': '半决赛',
        'final': '决赛',
        'first_round': '第一轮',
        'second_round': '第二轮',
        'third_round': '第三轮',
        'fourth_round': '第四轮',
        'fifth_round': '第五轮',
        'unknown': '未知'
    }

    for stage in stages:
        stage['stage_cn'] = stage_cn_map.get(stage['stage'], stage['stage'])

    conn.close()
    return {
        "data": stages,
        "season": season,
        "league_id": league_id,
        "league_name": league_info['name'],
        "league_cn": get_chinese_league_name(league_info['name']),
        "frequency": league_info['frequency'] or 'yearly'
    }


@app.get("/api/v1/cups/{league_id}/matches")
async def get_cup_matches(league_id: int, season: str = None, stage: str = None):
    """获取杯赛比赛数据"""
    conn = get_db()
    cursor = conn.cursor()

    # 获取联赛信息
    cursor.execute("SELECT name_en as name, cycle_type as frequency, country FROM leagues WHERE league_id = ?", (league_id,))
    league_info = cursor.fetchone()
    if not league_info:
        conn.close()
        return {"data": [], "error": "联赛不存在"}

    league_country = league_info['country']

    # 如果没有指定赛季，获取最新赛季
    if not season:
        cursor.execute('''
            SELECT season FROM cup_matches
            WHERE league_id = ?
            ORDER BY season DESC
            LIMIT 1
        ''', (league_id,))
        result = cursor.fetchone()
        if result:
            season = result[0]
        else:
            conn.close()
            return {"data": [], "season": None}

    # 构建查询条件
    query = '''
        SELECT
            match_id, season, stage, stage_order,
            group_name, group_round, leg,
            match_date, match_time,
            home_team, away_team,
            home_goals, away_goals,
            home_goals_ht, away_goals_ht,
            home_goals_et, away_goals_et,
            home_penalties, away_penalties,
            result, venue, attendance, referee, status
        FROM cup_matches
        WHERE league_id = ? AND season = ?
    '''
    params = [league_id, season]

    if stage:
        query += ' AND stage = ?'
        params.append(stage)

    query += ' ORDER BY stage_order, match_date, match_time'

    cursor.execute(query, params)
    matches = [dict(row) for row in cursor.fetchall()]

    # 添加中文名称和时间转换
    for match in matches:
        match['home_team_cn'] = get_chinese_team_name(match['home_team'])
        match['away_team_cn'] = get_chinese_team_name(match['away_team'])
        time_info = convert_to_beijing_time(match['match_date'], match['match_time'], league_country)
        match['beijing_time'] = time_info['beijing_time']
        match['beijing_datetime'] = time_info['beijing_datetime']

    conn.close()
    return {
        "data": matches,
        "season": season,
        "stage": stage,
        "league_id": league_id,
        "league_name": league_info['name'],
        "league_cn": get_chinese_league_name(league_info['name']),
        "frequency": league_info['frequency'] or 'yearly'
    }


@app.get("/api/v1/cups/{league_id}/groups")
async def get_cup_groups(league_id: int, season: str = None):
    """获取杯赛小组赛数据（小组积分榜和比赛）"""
    conn = get_db()
    cursor = conn.cursor()

    # 获取联赛信息
    cursor.execute("SELECT name_en as name, cycle_type as frequency, country FROM leagues WHERE league_id = ?", (league_id,))
    league_info = cursor.fetchone()
    if not league_info:
        conn.close()
        return {"data": [], "error": "联赛不存在"}

    league_country = league_info['country']

    # 如果没有指定赛季，获取最新赛季
    if not season:
        cursor.execute('''
            SELECT season FROM cup_matches
            WHERE league_id = ?
            ORDER BY season DESC
            LIMIT 1
        ''', (league_id,))
        result = cursor.fetchone()
        if result:
            season = result[0]
        else:
            conn.close()
            return {"data": [], "season": None}

    # 获取小组赛比赛
    cursor.execute('''
        SELECT
            match_id, stage, group_name, group_round,
            match_date, match_time,
            home_team, away_team,
            home_goals, away_goals,
            home_goals_ht, away_goals_ht,
            result, status
        FROM cup_matches
        WHERE league_id = ? AND season = ?
        AND stage IN ('group', 'league_phase')
        AND group_name IS NOT NULL AND group_name != ''
        ORDER BY group_name, group_round, match_date, match_time
    ''', (league_id, season))
    matches = [dict(row) for row in cursor.fetchall()]

    # 添加中文名称
    for match in matches:
        match['home_team_cn'] = get_chinese_team_name(match['home_team'])
        match['away_team_cn'] = get_chinese_team_name(match['away_team'])
        time_info = convert_to_beijing_time(match['match_date'], match['match_time'], league_country)
        match['beijing_time'] = time_info['beijing_time']

    # 计算小组积分榜
    groups = {}
    for match in matches:
        group_name = match['group_name']
        if group_name not in groups:
            groups[group_name] = {}

        home_team = match['home_team']
        away_team = match['away_team']

        if home_team not in groups[group_name]:
            groups[group_name][home_team] = {
                'team': home_team,
                'team_cn': get_chinese_team_name(home_team),
                'played': 0,
                'won': 0,
                'drawn': 0,
                'lost': 0,
                'goals_for': 0,
                'goals_against': 0,
                'points': 0
            }

        if away_team not in groups[group_name]:
            groups[group_name][away_team] = {
                'team': away_team,
                'team_cn': get_chinese_team_name(away_team),
                'played': 0,
                'won': 0,
                'drawn': 0,
                'lost': 0,
                'goals_for': 0,
                'goals_against': 0,
                'points': 0
            }

        # 只计算已完成的比赛
        if match['home_goals'] is not None and match['away_goals'] is not None:
            groups[group_name][home_team]['played'] += 1
            groups[group_name][away_team]['played'] += 1

            groups[group_name][home_team]['goals_for'] += match['home_goals']
            groups[group_name][home_team]['goals_against'] += match['away_goals']
            groups[group_name][away_team]['goals_for'] += match['away_goals']
            groups[group_name][away_team]['goals_against'] += match['home_goals']

            if match['result'] == 'H':
                groups[group_name][home_team]['won'] += 1
                groups[group_name][home_team]['points'] += 3
                groups[group_name][away_team]['lost'] += 1
            elif match['result'] == 'A':
                groups[group_name][away_team]['won'] += 1
                groups[group_name][away_team]['points'] += 3
                groups[group_name][home_team]['lost'] += 1
            elif match['result'] == 'D':
                groups[group_name][home_team]['drawn'] += 1
                groups[group_name][away_team]['drawn'] += 1
                groups[group_name][home_team]['points'] += 1
                groups[group_name][away_team]['points'] += 1

    # 转换为列表并排序
    standings_list = []
    for group_name, teams in groups.items():
        team_list = sorted(teams.values(), key=lambda x: (-x['points'], -(x['goals_for']-x['goals_against']), -x['goals_for']))
        standings_list.append({
            'group': group_name,
            'teams': team_list
        })

    standings_list = sorted(standings_list, key=lambda x: x['group'])

    conn.close()
    return {
        "data": {
            "standings": standings_list,
            "matches": matches
        },
        "season": season,
        "league_id": league_id,
        "league_name": league_info['name'],
        "league_cn": get_chinese_league_name(league_info['name']),
        "frequency": league_info['frequency'] or 'yearly'
    }


@app.get("/api/v1/cups/{league_id}/knockout")
async def get_cup_knockout(league_id: int, season: str = None):
    """获取杯赛淘汰赛数据（用于绘制对阵树）"""
    conn = get_db()
    cursor = conn.cursor()

    # 获取联赛信息
    cursor.execute("SELECT name_en as name, cycle_type as frequency, country FROM leagues WHERE league_id = ?", (league_id,))
    league_info = cursor.fetchone()
    if not league_info:
        conn.close()
        return {"data": [], "error": "联赛不存在"}

    league_country = league_info['country']

    # 如果没有指定赛季，获取最新赛季
    if not season:
        cursor.execute('''
            SELECT season FROM cup_matches
            WHERE league_id = ?
            ORDER BY season DESC
            LIMIT 1
        ''', (league_id,))
        result = cursor.fetchone()
        if result:
            season = result[0]
        else:
            conn.close()
            return {"data": [], "season": None}

    # 获取淘汰赛比赛（按阶段分组）
    knockout_stages = ['round_of_32', 'round_of_16', 'quarterfinal', 'semifinal', 'final',
                       'first_round', 'second_round', 'third_round', 'fourth_round', 'fifth_round']

    cursor.execute('''
        SELECT
            match_id, stage, stage_order, leg,
            match_date, match_time,
            home_team, away_team,
            home_goals, away_goals,
            home_goals_et, away_goals_et,
            home_penalties, away_penalties,
            result, status
        FROM cup_matches
        WHERE league_id = ? AND season = ?
        AND stage IN (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ORDER BY stage_order, match_date, match_time
    ''', [league_id, season] + knockout_stages)
    matches = [dict(row) for row in cursor.fetchall()]

    # 添加中文名称
    for match in matches:
        match['home_team_cn'] = get_chinese_team_name(match['home_team'])
        match['away_team_cn'] = get_chinese_team_name(match['away_team'])
        time_info = convert_to_beijing_time(match['match_date'], match['match_time'], league_country)
        match['beijing_time'] = time_info['beijing_time']

    # 按阶段分组
    stages_data = {}
    for match in matches:
        stage = match['stage']
        if stage not in stages_data:
            stages_data[stage] = {
                'stage': stage,
                'stage_order': match['stage_order'],
                'matches': []
            }
        stages_data[stage]['matches'].append(match)

    # 转换为列表并排序
    knockout_list = sorted(stages_data.values(), key=lambda x: x['stage_order'])

    conn.close()
    return {
        "data": knockout_list,
        "season": season,
        "league_id": league_id,
        "league_name": league_info['name'],
        "league_cn": get_chinese_league_name(league_info['name']),
        "frequency": league_info['frequency'] or 'yearly'
    }


# ==================== 数据同步 ====================

@app.get("/api/v1/sync/status")
async def get_sync_status():
    """获取同步状态和联赛赛季状态"""
    try:
        from app.services.sync_service import SyncService
        sync = SyncService()
        leagues_status = sync.get_league_season_status()
        return {
            "success": True,
            "leagues": leagues_status,
            "current_month": datetime.now().month,
            "current_date": datetime.now().strftime("%Y-%m-%d")
        }
    except Exception as e:
        return {"error": str(e)}


@app.post("/api/v1/sync/csv")
async def sync_from_csv(league_name: str = None):
    """
    从本地CSV文件同步比赛结果
    使用 new_data/matches/clubs/leagues/ 下的 CSV 文件更新数据库
    这是最可靠的同步方式，不依赖外部API
    """
    try:
        from app.services.sync_service import SyncService
        sync = SyncService()
        result = sync.sync_from_local_csv(league_name=league_name)
        return result
    except Exception as e:
        return {"success": False, "error": str(e)}


@app.post("/api/v1/sync/start")
async def start_sync(leagues: str = None):
    """
    启动同步服务（前端打开时自动调用）

    功能：
    1. 同步已结束的比赛 - 查找状态为scheduled但实际已结束的比赛，更新为实际赛果
    2. 同步未来赛程 - 获取未来3个月的赛程数据

    Args:
        leagues: 要同步的联赛，逗号分隔，默认同步主要联赛
    """
    try:
        from app.services.sync_service import SyncService
        sync = SyncService()
        league_list = None
        if leagues:
            league_list = [l.strip() for l in leagues.split(',')]

        result = sync.start_sync(leagues=league_list)
        return result
    except Exception as e:
        return {"success": False, "error": str(e)}


@app.post("/api/v1/sync/finished")
async def sync_finished_matches(days: int = 7):
    """
    同步最近已结束的比赛结果
    查找数据库中最近N天内状态为scheduled或缺少比分的比赛，更新为实际结果
    """
    try:
        from app.services.sync_service import SyncService
        sync = SyncService()
        result = sync.sync_recent_finished_matches(days=days)
        return result
    except Exception as e:
        return {"success": False, "error": str(e)}


@app.post("/api/v1/sync/upcoming")
async def sync_upcoming_fixtures(months: int = 3):
    """
    同步未来N个月的赛程
    自动跳过休赛期的联赛
    """
    try:
        from app.services.sync_service import SyncService
        sync = SyncService()
        result = sync.sync_upcoming_fixtures(months=months)
        return result
    except Exception as e:
        return {"success": False, "error": str(e)}


@app.post("/api/v1/sync/full")
async def full_sync():
    """
    完整同步：同时执行历史结果同步和未来赛程同步
    建议在打开网页时自动调用此接口
    """
    try:
        from app.services.sync_service import SyncService
        sync = SyncService()
        result = sync.full_sync()
        return result
    except Exception as e:
        return {"success": False, "error": str(e)}


@app.get("/api/v1/sync/check-needed")
async def check_sync_needed():
    """
    检查是否需要同步
    返回需要更新的比赛数量和未来赛程数量
    """
    conn = get_db()
    cursor = conn.cursor()

    today = datetime.now().date()
    week_ago = today - timedelta(days=7)

    # 检查需要更新结果的比赛
    cursor.execute('''
        SELECT COUNT(*) as count
        FROM matches
        WHERE match_date >= ? AND match_date < ?
        AND (
            (status = 'scheduled' AND match_date < ?)
            OR (home_goals IS NULL AND away_goals IS NULL)
        )
    ''', (week_ago.isoformat(), today.isoformat(), today.isoformat()))
    need_result = cursor.fetchone()['count']

    # 检查未来赛程数量
    cursor.execute('''
        SELECT COUNT(*) as count
        FROM matches
        WHERE match_date >= ? AND status = 'scheduled'
    ''', (today.isoformat(),))
    upcoming_count = cursor.fetchone()['count']

    conn.close()

    return {
        "success": True,
        "need_update_results": need_result,
        "upcoming_scheduled": upcoming_count,
        "sync_recommended": need_result > 0,
        "last_check": datetime.now().isoformat()
    }


# ==================== 数据缺失检测 ====================

@app.get("/api/v1/data/detect-missing")
async def detect_missing_data():
    """
    检测数据库中缺失的数据
    包括：缺失中文名的球队、缺失比分的已结束比赛、缺失日期的比赛、缺失规则的联赛
    """
    conn = get_db()
    cursor = conn.cursor()

    result = {
        "missing_team_cn": 0,
        "missing_scores": 0,
        "missing_dates": 0,
        "missing_league_rules": 0,
        "details": {
            "missing_cn_teams": [],
            "missing_score_matches": [],
            "missing_date_matches": [],
            "missing_rules_leagues": []
        }
    }

    try:
        # 1. 检测缺失中文名的球队
        cursor.execute("""
            SELECT team_id, name_en, country
            FROM teams
            WHERE (name_cn IS NULL OR name_cn = '')
            ORDER BY team_id
            LIMIT 20
        """)
        result["details"]["missing_cn_teams"] = [dict(row) for row in cursor.fetchall()]

        cursor.execute("""
            SELECT COUNT(*) as count FROM teams
            WHERE (name_cn IS NULL OR name_cn = '')
        """)
        result["missing_team_cn"] = cursor.fetchone()['count']

        # 2. 检测缺失比分的已结束比赛
        cursor.execute("""
            SELECT m.match_id, m.match_date,
                   ht.name_en as home_team, at.name_en as away_team,
                   l.name_en as league_name
            FROM matches m
            JOIN leagues l ON m.league_id = l.league_id
            JOIN teams ht ON m.home_team_id = ht.team_id
            JOIN teams at ON m.away_team_id = at.team_id
            WHERE m.status = 'finished'
              AND (m.home_goals IS NULL OR m.away_goals IS NULL)
            ORDER BY m.match_date DESC
            LIMIT 20
        """)
        result["details"]["missing_score_matches"] = [dict(row) for row in cursor.fetchall()]

        cursor.execute("""
            SELECT COUNT(*) as count FROM matches
            WHERE status = 'finished'
              AND (home_goals IS NULL OR away_goals IS NULL)
        """)
        result["missing_scores"] = cursor.fetchone()['count']

        # 3. 检测缺失日期的比赛
        cursor.execute("""
            SELECT m.match_id,
                   ht.name_en as home_team, at.name_en as away_team,
                   l.name_en as league_name
            FROM matches m
            JOIN leagues l ON m.league_id = l.league_id
            JOIN teams ht ON m.home_team_id = ht.team_id
            JOIN teams at ON m.away_team_id = at.team_id
            WHERE m.match_date IS NULL OR m.match_date = ''
            LIMIT 20
        """)
        result["details"]["missing_date_matches"] = [dict(row) for row in cursor.fetchall()]

        cursor.execute("""
            SELECT COUNT(*) as count FROM matches
            WHERE match_date IS NULL OR match_date = ''
        """)
        result["missing_dates"] = cursor.fetchone()['count']

        # 4. 检测缺失规则的联赛
        cursor.execute("""
            SELECT l.league_id, l.name_en, l.name_cn, l.country
            FROM leagues l
            LEFT JOIN league_rules lr ON l.league_id = lr.league_id
            WHERE lr.league_id IS NULL
            LIMIT 20
        """)
        result["details"]["missing_rules_leagues"] = [dict(row) for row in cursor.fetchall()]

        cursor.execute("""
            SELECT COUNT(*) as count FROM leagues l
            LEFT JOIN league_rules lr ON l.league_id = lr.league_id
            WHERE lr.league_id IS NULL
        """)
        result["missing_league_rules"] = cursor.fetchone()['count']

        conn.close()
        return result

    except Exception as e:
        conn.close()
        return {"error": str(e)}


@app.post("/api/v1/data/fix-team-name")
async def fix_team_name(team_id: int, name_cn: str):
    """补充球队中文名称"""
    conn = get_db()
    cursor = conn.cursor()

    try:
        cursor.execute("""
            UPDATE teams SET name_cn = ? WHERE team_id = ?
        """, (name_cn, team_id))
        conn.commit()
        conn.close()
        return {"success": True, "message": f"已更新球队中文名"}
    except Exception as e:
        conn.close()
        return {"success": False, "error": str(e)}


@app.post("/api/v1/data/fix-match-score")
async def fix_match_score(match_id: str, home_goals: int, away_goals: int):
    """补充比赛比分"""
    conn = get_db()
    cursor = conn.cursor()

    try:
        cursor.execute("""
            UPDATE matches
            SET home_goals = ?, away_goals = ?, status = 'finished'
            WHERE match_id = ?
        """, (home_goals, away_goals, match_id))
        conn.commit()
        conn.close()
        return {"success": True, "message": f"已更新比赛比分"}
    except Exception as e:
        conn.close()
        return {"success": False, "error": str(e)}


@app.get("/api/v1/data/stats")
async def get_data_stats():
    """获取数据库统计信息"""
    conn = get_db()
    cursor = conn.cursor()

    try:
        # 联赛统计
        cursor.execute("SELECT COUNT(*) as count FROM leagues")
        leagues_count = cursor.fetchone()['count']

        # 球队统计
        cursor.execute("SELECT COUNT(*) as count FROM teams")
        teams_count = cursor.fetchone()['count']

        # 比赛统计
        cursor.execute("SELECT COUNT(*) as count FROM matches")
        matches_count = cursor.fetchone()['count']

        # 赛季统计
        cursor.execute("SELECT COUNT(DISTINCT season_name) as count FROM seasons")
        seasons_count = cursor.fetchone()['count']

        # 各联赛统计
        cursor.execute("""
            SELECT
                l.league_id,
                l.name_en,
                l.name_cn,
                l.country,
                COUNT(DISTINCT s.season_name) as seasons_count,
                COUNT(DISTINCT m.match_id) as matches_count,
                (SELECT COUNT(DISTINCT t.team_id)
                 FROM matches m2
                 JOIN teams t ON t.team_id IN (m2.home_team_id, m2.away_team_id)
                 WHERE m2.league_id = l.league_id) as teams_count,
                MAX(s.season_name) as latest_season
            FROM leagues l
            LEFT JOIN seasons s ON l.league_id = s.league_id
            LEFT JOIN matches m ON l.league_id = m.league_id
            GROUP BY l.league_id
            ORDER BY matches_count DESC
        """)
        league_stats = []
        for row in cursor.fetchall():
            league = dict(row)
            # 计算数据完整度
            completeness = 0
            if league['matches_count'] > 0:
                completeness = min(100, int(league['matches_count'] / 380 * 100))
            league['completeness'] = completeness
            league_stats.append(league)

        conn.close()

        return {
            "success": True,
            "stats": {
                "leagues": leagues_count,
                "teams": teams_count,
                "matches": matches_count,
                "seasons": seasons_count
            },
            "league_stats": league_stats
        }

    except Exception as e:
        conn.close()
        return {"error": str(e)}


@app.get("/api/v1/leagues/{league_id}/seasons-stats")
async def get_league_seasons_stats(league_id: int):
    """获取联赛各赛季的数据统计"""
    conn = get_db()
    cursor = conn.cursor()

    try:
        # 获取该联赛的所有赛季及其统计 - 通过 season_id 关联
        cursor.execute("""
            SELECT
                s.season_name as season,
                s.season_id,
                COUNT(DISTINCT m.match_id) as matches_count,
                COUNT(DISTINCT CASE WHEN m.status = 'finished' THEN m.match_id END) as finished_count,
                COUNT(DISTINCT CASE WHEN m.status = 'scheduled' THEN m.match_id END) as scheduled_count,
                COUNT(DISTINCT CASE WHEN m.status = 'finished' AND (m.home_goals IS NULL OR m.away_goals IS NULL) THEN m.match_id END) as missing_scores,
                COUNT(DISTINCT CASE WHEN m.match_date IS NULL OR m.match_date = '' THEN m.match_id END) as missing_dates,
                (SELECT COUNT(DISTINCT t.team_id)
                 FROM matches m2
                 JOIN teams t ON t.team_id IN (m2.home_team_id, m2.away_team_id)
                 WHERE m2.season_id = s.season_id) as teams_count
            FROM seasons s
            LEFT JOIN matches m ON m.season_id = s.season_id
            WHERE s.league_id = ?
            GROUP BY s.season_id
            ORDER BY s.season_name DESC
        """, (league_id,))

        seasons = []
        for row in cursor.fetchall():
            season = dict(row)
            # 计算完整度
            if season['matches_count'] and season['matches_count'] > 0:
                finished = season['finished_count'] or 0
                missing_scores = season['missing_scores'] or 0
                # 完整度 = 已结束比赛中有比分的比例
                if finished > 0:
                    season['completeness'] = max(0, int((finished - missing_scores) / finished * 100))
                else:
                    season['completeness'] = 0
            else:
                season['completeness'] = 0
            seasons.append(season)

        conn.close()
        return {"success": True, "seasons": seasons}

    except Exception as e:
        conn.close()
        return {"error": str(e)}


@app.get("/api/v1/leagues/{league_id}/detect-missing")
async def detect_league_missing(league_id: int):
    """检测联赛缺失数据"""
    conn = get_db()
    cursor = conn.cursor()

    try:
        # 检测缺失比分
        cursor.execute("""
            SELECT COUNT(*) as count
            FROM matches
            WHERE league_id = ? AND status = 'finished'
            AND (home_goals IS NULL OR away_goals IS NULL)
        """, (league_id,))
        missing_scores = cursor.fetchone()['count']

        # 检测缺失日期
        cursor.execute("""
            SELECT COUNT(*) as count
            FROM matches
            WHERE league_id = ? AND (match_date IS NULL OR match_date = '')
        """, (league_id,))
        missing_dates = cursor.fetchone()['count']

        conn.close()
        return {
            "success": True,
            "missing_scores": missing_scores,
            "missing_dates": missing_dates
        }

    except Exception as e:
        conn.close()
        return {"error": str(e)}


@app.post("/api/v1/sync/league-season")
async def sync_league_season(request: dict):
    """同步指定联赛赛季的数据"""
    league_id = request.get("league_id")
    season = request.get("season")

    if not league_id or not season:
        return {"error": "缺少参数"}

    # 这里调用同步服务
    try:
        from app.services.sync_service import SyncService
        sync = SyncService()
        result = sync.sync_league_season(league_id, season)
        return {"success": True, "updated": result.get("updated", 0)}
    except Exception as e:
        return {"success": False, "error": str(e)}
