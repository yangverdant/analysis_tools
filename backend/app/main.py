"""
足球数据分析 API - 主入口

已拆分的模块:
- routers/: 业务路由 (matches, teams, leagues, cups, sync, rankings)
- analytics/: 分析模块 (Elo, xG, 预测等)
- pipeline/: 数据流水线 (分拣/采集/清洗/导入)
- langchain/: AI 分析 (暂时禁用)
- data_sources/: 数据源管理
"""
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import sqlite3
import os
import sys
import subprocess
from datetime import datetime, timedelta
from threading import Lock

BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
PROJECT_ROOT = os.path.abspath(os.path.join(BACKEND_DIR, '..'))
for path in (PROJECT_ROOT, BACKEND_DIR):
    if path not in sys.path:
        sys.path.insert(0, path)

from backend.app.core.time_utils import today_beijing, tomorrow_beijing
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

# 数据库路径 — 优先使用环境变量(云部署), 否则用相对路径(本地开发)
DATABASE_PATH = os.environ.get('DB_PATH',
    os.path.join(PROJECT_ROOT, 'data', 'football_v2.db'))
ODDSFE_DB_PATH = os.environ.get(
    'ODDSFE_DB_PATH',
    os.path.join(PROJECT_ROOT, 'fetchers', 'odds_feed_api', 'oddsfe_merged.db')
)
LINKAGE_PATH = os.environ.get('LINKAGE_PATH',
    os.path.join(PROJECT_ROOT, 'data', 'linkage'))

# 国家中文名映射(补充DB中country_cn为空的记录)
_COUNTRY_CN = {
    'England': '英格兰', 'Scotland': '苏格兰', 'Wales': '威尔士',
    'France': '法国', 'Germany': '德国', 'Italy': '意大利', 'Spain': '西班牙',
    'Portugal': '葡萄牙', 'Netherlands': '荷兰', 'Belgium': '比利时',
    'Austria': '奥地利', 'Switzerland': '瑞士', 'Poland': '波兰',
    'Czech Republic': '捷克', 'Denmark': '丹麦', 'Sweden': '瑞典',
    'Norway': '挪威', 'Finland': '芬兰', 'Greece': '希腊', 'Turkey': '土耳其',
    'Russia': '俄罗斯', 'Ukraine': '乌克兰', 'Croatia': '克罗地亚',
    'Serbia': '塞尔维亚', 'Romania': '罗马尼亚', 'Hungary': '匈牙利',
    'China': '中国', 'Japan': '日本', 'Korea': '韩国', 'South Korea': '韩国',
    'Australia': '澳大利亚', 'Saudi Arabia': '沙特阿拉伯', 'Qatar': '卡塔尔',
    'UAE': '阿联酋', 'USA': '美国', 'Mexico': '墨西哥', 'Brazil': '巴西',
    'Argentina': '阿根廷', 'Chile': '智利', 'Colombia': '哥伦比亚',
    'Egypt': '埃及', 'South Africa': '南非', 'Morocco': '摩洛哥',
    'International': '国际', 'World': '世界', 'Asia': '亚洲',
    'Europe': '欧洲', 'South America': '南美洲', 'Africa': '非洲',
    'North America': '北美洲', 'Unknown': '其他',
}

# 时区映射（相对于北京时间的时差）
TIMEZONE_OFFSETS = {
    'England': -7, 'Scotland': -7, 'Wales': -7,
    'France': -7, 'Germany': -7, 'Italy': -7, 'Spain': -7,
    'Portugal': -7, 'Netherlands': -7, 'Belgium': -7,
    'Europe': -7, 'China': 0, 'Japan': 1, 'Korea': 1,
    'Australia': 2, 'Saudi Arabia': -5, 'Qatar': -5,
    'Asia': 0, 'USA': -13, 'Brazil': -11, 'Africa': -7,
    'International': -8, 'World': -8,
}


def get_timezone_offset(country: str) -> int:
    """获取国家相对于北京时间的时差（空country默认-8即UTC）"""
    if not country:
        return -8  # 国际赛事无国家信息时假设UTC
    return TIMEZONE_OFFSETS.get(country, -8)  # 未知国家也假设UTC


def convert_to_beijing_time(match_date: str, match_time: str, country: str, time_type: str = 'local') -> dict:
    """
    将时间转换为北京时间
    time_type: 'local'(当地时间), 'beijing'(北京时间), 'utc'(UTC 时间)
    """
    from datetime import datetime, timedelta

    if not match_time:
        return {'beijing_time': None, 'beijing_datetime': None, 'local_time': None, 'offset': 0}

    try:
        if time_type == 'utc':
            offset = -8  # UTC→Beijing: +8h, so offset = -8
        elif time_type == 'beijing':
            offset = 0  # Already Beijing time
        else:
            offset = get_timezone_offset(country)

        time_parts = match_time.split(':')
        hour, minute = int(time_parts[0]), int(time_parts[1]) if len(time_parts) > 1 else 0

        date_parts = match_date.split('-') if match_date else ['2024', '1', '1']
        year, month, day = int(date_parts[0]), int(date_parts[1]), int(date_parts[2])

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
    except Exception as e:
        return {'beijing_time': match_time, 'beijing_datetime': f"{match_date} {match_time}", 'local_time': match_time, 'offset': 0, 'error': str(e)}


def load_api_config() -> dict:
    """加载并展平 api_config.json 的嵌套结构"""
    config_path = os.path.join(os.path.dirname(__file__), '..', '..', 'api_config.json')
    if not os.path.exists(config_path):
        return {}
    with open(config_path, 'r', encoding='utf-8') as f:
        raw = json.load(f)
    apis = raw.get("apis", {})
    config = {}
    for src_name, api_cfg in apis.items():
        key = api_cfg.get("api_key") or api_cfg.get("api_token") or ""
        base_url = api_cfg.get("base_url", "")
        dest_name = src_name
        if src_name == "apifootball":
            dest_name = "api_football"
        config[dest_name] = {
            "api_key": key,
            "base_url": base_url,
            "api_token": key,
        }
    if "rapidapi" in raw:
        config["rapidapi"] = raw["rapidapi"]
    return config


def get_db():
    """获取数据库连接"""
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _table_columns(cursor, table_name: str) -> set:
    try:
        return {row[1] for row in cursor.execute(f"PRAGMA table_info({table_name})").fetchall()}
    except Exception:
        return set()


# 创建 FastAPI 应用
app = FastAPI(
    title="足球数据分析 API",
    description="提供足球数据查询、分析和预测功能",
    version="2.0.0"
)

# CORS 配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册各模块路由
from app.data_sources.routes import router as data_sources_router
app.include_router(data_sources_router, prefix="/api/v1")

from app.analytics import analytics_router
app.include_router(analytics_router)

from app.routers import (
    matches_router,
    teams_router,
    leagues_router,
    cups_router,
    sync_router,
    rankings_router,
    user_router
)
app.include_router(matches_router)
app.include_router(teams_router)
app.include_router(leagues_router)
app.include_router(cups_router)
app.include_router(sync_router)
app.include_router(rankings_router)
app.include_router(user_router)

from app.pipeline import pipeline_router
app.include_router(pipeline_router)

# 体彩分析路由 (新增)
from app.lottery.routers.lottery import router as lottery_router
app.include_router(lottery_router)

# Match intelligence orchestration route
from app.intelligence import intelligence_router
app.include_router(intelligence_router)

from app.worldcup import worldcup_router
app.include_router(worldcup_router)

# LangChain AI 路由 (暂时禁用，需要修复版本兼容)
# from app.langchain.routes import router as langchain_router
# app.include_router(langchain_router)


# ==================== 基础路由 ====================

@app.get("/")
async def root():
    """API 根路径"""
    return {
        "name": "足球数据分析 API",
        "version": "2.0.0",
        "description": "提供足球数据查询、分析和预测功能",
        "endpoints": {
            "docs": "/docs",
            "health": "/api/v1/health",
            "data_stats": "/api/v1/data/stats"
        }
    }


@app.get("/api/v1/health")
async def health_check():
    """健康检查"""
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM matches")
        match_count = cursor.fetchone()[0]
        conn.close()
        return {
            "status": "healthy",
            "database": "connected",
            "matches_count": match_count
        }
    except Exception as e:
        return {"status": "unhealthy", "error": str(e)}


# ==================== 数据概览路由 ====================

@app.get("/api/v1/data/stats")
async def get_data_stats():
    """获取数据库统计信息（匹配DataCenter前端格式）"""
    conn = get_db()
    cursor = conn.cursor()

    # 基础统计
    stats = {}
    for table in ['leagues', 'teams', 'matches', 'seasons']:
        try:
            cursor.execute(f"SELECT COUNT(*) FROM {table}")
            stats[table] = cursor.fetchone()[0]
        except:
            stats[table] = 0

    # 各联赛统计
    league_stats = []
    try:
        cursor.execute('''
            SELECT
                l.league_id,
                l.name_cn,
                l.name_en,
                l.country,
                l.country_cn,
                COUNT(DISTINCT m.match_id) as matches_count,
                COUNT(DISTINCT m.home_team_id) as teams_count,
                COUNT(DISTINCT m.season_id) as seasons_count,
                MAX(m.season_id) as latest_season
            FROM leagues l
            LEFT JOIN matches m ON m.league_id = l.league_id
            GROUP BY l.league_id
            ORDER BY matches_count DESC
        ''')
        for row in cursor.fetchall():
            league_stats.append({
                'league_id': row[0],
                'name_cn': row[1],
                'name_en': row[2],
                'country': row[3],
                'country_cn': row[4] or _COUNTRY_CN.get(row[3], row[3]) if row[3] else '国际',
                'matches_count': row[5] or 0,
                'teams_count': row[6] or 0,
                'seasons_count': row[7] or 0,
                'latest_season': row[8],
                'completeness': min(100, round((row[5] or 0) / max(1, (row[7] or 1) * 30) * 100))
            })
    except Exception as e:
        print(f"联赛统计查询失败: {e}")

    conn.close()

    return {
        "success": True,
        "stats": stats,
        "league_stats": league_stats
    }


# ==================== CSV 读写路由 ====================

@app.get("/api/v1/csv/read")
async def read_csv(file_name: str = "team_chinese_names.json"):
    """读取 linkage 目录下的文件"""
    file_path = os.path.join(LINKAGE_PATH, file_name)
    if not os.path.exists(file_path):
        return {"error": f"File not found: {file_name}"}

    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    try:
        return {"file": file_name, "data": json.loads(content)}
    except:
        return {"file": file_name, "content": content}


@app.post("/api/v1/csv/write")
async def write_csv(file_name: str, data: dict):
    """写入文件到 linkage 目录"""
    import json
    file_path = os.path.join(LINKAGE_PATH, file_name)

    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    return {"success": True, "file": file_name}


@app.get("/api/v1/csv/list")
async def list_csv_files():
    """列出 linkage 目录下的所有文件"""
    if not os.path.exists(LINKAGE_PATH):
        return {"files": []}

    files = [f for f in os.listdir(LINKAGE_PATH) if f.endswith(('.json', '.csv'))]
    return {"files": files}


# ==================== 数据检测路由 ====================

@app.get("/api/v1/data/detect-missing")
async def detect_missing_data():
    """检测数据库缺失数据"""
    conn = get_db()
    cursor = conn.cursor()

    result = {
        "missing_team_cn": 0,
        "missing_scores": 0,
        "missing_dates": 0,
        "missing_league_rules": 0,
        "details": {}
    }

    # 检测缺失中文名的球队
    cursor.execute("""
        SELECT team_id, name_en, country FROM teams
        WHERE name_cn IS NULL OR name_cn = ''
        LIMIT 20
    """)
    missing_cn_teams = [dict(row) for row in cursor.fetchall()]
    cursor.execute("SELECT COUNT(*) FROM teams WHERE name_cn IS NULL OR name_cn = ''")
    result['missing_team_cn'] = cursor.fetchone()[0]
    result['details']['missing_cn_teams'] = missing_cn_teams

    # 检测缺失比分的已结束比赛（仅统计有有效联赛关联的）
    cursor.execute("""
        SELECT m.match_id, m.match_date, m.league_id,
               ht.name_en as home_team, ht.name_cn as home_team_cn,
               at.name_en as away_team, at.name_cn as away_team_cn
        FROM matches m
        LEFT JOIN teams ht ON m.home_team_id = ht.team_id
        LEFT JOIN teams at ON m.away_team_id = at.team_id
        WHERE m.status = 'finished' AND (m.home_goals IS NULL OR m.away_goals IS NULL)
          AND m.league_id IN (SELECT league_id FROM leagues)
        ORDER BY m.match_date DESC
        LIMIT 20
    """)
    missing_score_matches = [dict(row) for row in cursor.fetchall()]
    cursor.execute("""
        SELECT COUNT(*) FROM matches m
        WHERE m.status = 'finished' AND (m.home_goals IS NULL OR m.away_goals IS NULL)
          AND m.league_id IN (SELECT league_id FROM leagues)
    """)
    result['missing_scores'] = cursor.fetchone()[0]
    result['details']['missing_score_matches'] = missing_score_matches

    # 检测缺失日期的比赛（仅统计真正缺日期的，缺时间不算）
    cursor.execute("""
        SELECT COUNT(*) FROM matches
        WHERE match_date IS NULL OR match_date = ''
    """)
    result['missing_dates'] = cursor.fetchone()[0]

    # 缺失开球时间的比赛（单独统计，不算严重缺失）
    cursor.execute("""
        SELECT COUNT(*) FROM matches
        WHERE match_date IS NOT NULL AND match_date != '' AND (match_time IS NULL OR match_time = '')
    """)
    result['missing_times'] = cursor.fetchone()[0]

    # 检测缺失规则的联赛
    cursor.execute("""
        SELECT COUNT(*) FROM leagues l
        WHERE NOT EXISTS (SELECT 1 FROM league_rules r WHERE r.league_id = l.league_id)
    """)
    result['missing_league_rules'] = cursor.fetchone()[0]

    conn.close()
    return result


# ==================== 数据修复路由 ====================

@app.post("/api/v1/data-fix/team-name")
async def fix_team_name(data: dict):
    """补充球队中文名 - 调用同步管道"""
    team_id = data.get('team_id')
    name_en = data.get('name_en')

    if not team_id and not name_en:
        return {"success": False, "error": "需要 team_id 或 name_en"}

    # 先从 linkage 文件查找
    file_path = os.path.join(LINKAGE_PATH, 'team_chinese_names.json')
    if os.path.exists(file_path):
        with open(file_path, 'r', encoding='utf-8') as f:
            names = json.load(f)
        if name_en and name_en in names:
            name_cn = names[name_en]
            conn = get_db()
            cursor = conn.cursor()
            cursor.execute("UPDATE teams SET name_cn = ? WHERE team_id = ?", (name_cn, team_id))
            conn.commit()
            conn.close()
            return {"success": True, "name_cn": name_cn, "source": "linkage"}

    # 尝试从 Sportmonks API 获取
    config = load_api_config()
    sm_token = config.get("sportmonks", {}).get("api_token", "")
    if sm_token and team_id:
        import httpx
        try:
            # 查找 sm_team_id
            conn = get_db()
            cursor = conn.cursor()
            cursor.execute("SELECT sm_team_id FROM teams WHERE team_id = ?", (team_id,))
            row = cursor.fetchone()
            sm_id = row[0] if row else None
            conn.close()

            if sm_id:
                resp = httpx.get(
                    f"https://api.sportmonks.com/v3/football/teams/{sm_id}",
                    params={"api_token": sm_token, "include": "name"},
                    timeout=10
                )
                if resp.status_code == 200:
                    tdata = resp.json().get("data", {})
                    name_cn = tdata.get("name") or tdata.get("common_name")
                    if name_cn:
                        conn = get_db()
                        cursor = conn.cursor()
                        cursor.execute("UPDATE teams SET name_cn = ? WHERE team_id = ?", (name_cn, team_id))
                        conn.commit()
                        conn.close()
                        return {"success": True, "name_cn": name_cn, "source": "sportmonks"}
        except Exception as e:
            pass

    return {"success": False, "error": "未找到中文名，请通过同步管道批量补充"}


@app.post("/api/v1/data-fix/match-score")
async def fix_match_score(data: dict):
    """补充比赛比分 - 从API-Football获取"""
    match_id = data.get('match_id')
    match_date = data.get('match_date')
    home_team = data.get('home_team')
    away_team = data.get('away_team')

    if not match_date:
        return {"success": False, "error": "需要 match_date"}

    # 从 API-Football 获取当天比赛结果
    config = load_api_config()
    api_key = config.get("api_football", {}).get("api_key", "")
    if not api_key:
        return {"success": False, "error": "API-Football key 未配置"}

    import httpx
    date_str = match_date[:10] if match_date else None
    if not date_str:
        return {"success": False, "error": "日期格式错误"}

    try:
        resp = await httpx.AsyncClient(timeout=30).get(
            "https://v3.football.api-sports.io/fixtures",
            headers={"x-apisports-key": api_key},
            params={"date": date_str, "timezone": "Europe/London"},
        )
        if resp.status_code != 200:
            return {"success": False, "error": f"API返回错误: {resp.status_code}"}

        fixtures = resp.json().get("response", [])
        for fixture in fixtures:
            goals = fixture.get("goals", {})
            teams = fixture.get("teams", {})
            api_home = teams.get("home", {}).get("name", "")
            api_away = teams.get("away", {}).get("name", "")

            # 匹配球队名
            matched = False
            if home_team and (
                api_home == home_team or
                api_home.replace(" FC", "") == home_team.replace(" FC", "")
            ):
                matched = True

            if matched and goals.get("home") is not None:
                home_goals = goals["home"]
                away_goals = goals["away"]
                conn = get_db()
                cursor = conn.cursor()
                cursor.execute(
                    "UPDATE matches SET home_goals = ?, away_goals = ? WHERE match_id = ?",
                    (home_goals, away_goals, match_id)
                )
                conn.commit()
                conn.close()
                return {
                    "success": True,
                    "home_goals": home_goals,
                    "away_goals": away_goals,
                    "source": "api-football"
                }
    except Exception as e:
        return {"success": False, "error": str(e)}

    return {"success": False, "error": "未找到比分数据或API未配置"}


# 导入 json 用于 CSV 路由
import json


# ==================== 日循环路由 ====================

@app.get("/api/cycle/status")
async def cycle_status():
    """获取日循环当前状态"""
    try:
        conn = get_db()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        # 读取daily_cycle_state (每行=一天, 各节点结果在列中)
        cursor.execute("""
            SELECT * FROM daily_cycle_state
            ORDER BY date DESC LIMIT 1
        """)
        state_row = cursor.fetchone()

        results = {}
        if state_row:
            state = dict(state_row)
            results['date'] = state.get('date')
            results['current_node'] = state.get('current_node')
            results['status'] = state.get('status')

            # 解析各节点结果列
            node_cols = ['perceive_result', 'collect_result', 'intel_result',
                         'classify_result', 'analyze_result', 'push_result',
                         'clv_result', 'validate_result', 'learn_result']
            for col in node_cols:
                node_name = col.replace('_result', '')
                raw = state.get(col)
                if raw:
                    try:
                        results[node_name] = json.loads(raw) if isinstance(raw, str) else raw
                    except:
                        results[node_name] = {'raw': raw}
        else:
            results = {'date': None, 'current_node': None, 'status': 'idle'}

        conn.close()
        return results
    except Exception as e:
        return {"error": str(e), "status": "error"}


@app.post("/api/cycle/run/{mode}")
async def cycle_run(mode: str):
    """触发日循环 (mode: perceive/collect/analyze/push/clv/validate/learn/morning/full)"""
    import subprocess
    import sys

    valid_modes = ['perceive', 'collect', 'classify', 'intel', 'analyze', 'push', 'clv', 'validate', 'learn', 'morning', 'full']
    if mode not in valid_modes:
        return {"success": False, "error": f"Invalid mode: {mode}"}

    try:
        # 后台启动daily_runner
        process = subprocess.Popen(
            [sys.executable, '-m', 'backend.app.core.daily_runner', '--mode', mode],
            cwd=os.path.join(os.path.dirname(__file__), '..', '..'),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        return {"success": True, "mode": mode, "pid": process.pid, "status": "started"}
    except Exception as e:
        return {"success": False, "error": str(e)}


@app.get("/api/cycle/predictions")
async def cycle_predictions(date: str = None):
    """获取今日预测结果"""
    try:
        conn = get_db()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        report_cols = _table_columns(cursor, "lottery_analysis_reports")
        active_report_filter = "AND COALESCE(is_stale, 0) = 0" if "is_stale" in report_cols else ""

        # 北京时间窗口: today + tomorrow凌晨
        from backend.app.core.time_utils import today_beijing, tomorrow_beijing
        today = date or today_beijing()
        tomorrow = tomorrow_beijing()

        # 只返回未开始的比赛（match_datetime > now）
        from datetime import datetime
        now = datetime.now().strftime('%Y-%m-%d %H:%M')
        cursor.execute(f"""
            SELECT lar.lottery_match_id, lar.report_data,
                   lm.home_team_cn, lm.away_team_cn, lm.match_date, lm.match_time,
                   lm.league_name_cn, lm.home_team_id, lm.away_team_id
            FROM lottery_analysis_reports lar
            JOIN (
                SELECT MAX(report_id) AS report_id
                FROM lottery_analysis_reports
                WHERE report_type = 'prediction'
                {active_report_filter}
                GROUP BY lottery_match_id
            ) latest ON latest.report_id = lar.report_id
            JOIN lottery_matches lm ON lar.lottery_match_id = lm.lottery_match_id
            WHERE (
                lm.match_date = ?
                OR (lm.match_date = ? AND substr(lm.match_time, 1, 2) < '12')
            )
            AND lar.report_type = 'prediction'
            AND (lm.match_date || ' ' || substr(lm.match_time, 1, 5)) > ?
            ORDER BY lm.match_date, lm.match_time
        """, (today, tomorrow, now))

        predictions = []
        for row in cursor.fetchall():
            r = dict(row)
            try:
                data = json.loads(r['report_data']) if r['report_data'] else {}
                fp = data.get('final_prediction', {})
                probs = fp.get('probabilities', {})
                predictions.append({
                    'match_id': r['lottery_match_id'],
                    'home': r['home_team_cn'],
                    'away': r['away_team_cn'],
                    'league': r['league_name_cn'],
                    'match_time': r['match_time'],
                    'prediction': {
                        'home_win': probs.get('home_win'),
                        'draw': probs.get('draw'),
                        'away_win': probs.get('away_win'),
                        'recommended': fp.get('predicted_result'),
                        'confidence': fp.get('confidence_level'),
                    },
                    'odds_baseline': data.get('odds_baseline'),
                    'model_vs_odds': data.get('model_vs_odds'),
                    'match_profile': data.get('match_profile'),
                    'weights_used': data.get('weights_used'),
                    'play_predictions': data.get('play_predictions', {}),
                })
            except:
                pass

        conn.close()
        return {"date": date, "predictions": predictions}
    except Exception as e:
        return {"error": str(e), "predictions": []}


@app.get("/api/cycle/top3")
async def cycle_top3():
    """获取TOP3价值投注"""
    try:
        conn = get_db()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        report_cols = _table_columns(cursor, "lottery_analysis_reports")
        active_report_filter = "AND COALESCE(is_stale, 0) = 0" if "is_stale" in report_cols else ""

        # 从预测报告中找最高置信度的推荐(北京时间窗口)
        from backend.app.core.time_utils import today_beijing, tomorrow_beijing
        _today = today_beijing()
        _tomorrow = tomorrow_beijing()
        cursor.execute(f"""
            SELECT lar.report_data, lm.home_team_cn, lm.away_team_cn,
                   lm.league_name_cn, lm.match_date
            FROM lottery_analysis_reports lar
            JOIN (
                SELECT MAX(report_id) AS report_id
                FROM lottery_analysis_reports
                WHERE report_type = 'prediction'
                {active_report_filter}
                GROUP BY lottery_match_id
            ) latest ON latest.report_id = lar.report_id
            JOIN lottery_matches lm ON lar.lottery_match_id = lm.lottery_match_id
            WHERE (
                lm.match_date = ?
                OR (lm.match_date = ? AND substr(lm.match_time, 1, 2) < '12')
            )
            AND lar.report_type = 'prediction'
        """, (_today, _tomorrow))

        bets = []
        for row in cursor.fetchall():
            r = dict(row)
            try:
                data = json.loads(r['report_data']) if r['report_data'] else {}
                fp = data.get('final_prediction', {})
                probs = fp.get('probabilities', {})
                confidence = fp.get('confidence', 0)

                if confidence > 0.6:
                    rec = fp.get('predicted_result', '')
                    rec_label = {'home_win': '主胜', 'draw': '平局', 'away_win': '客胜'}.get(rec, rec)

                    # 计算edge: 模型概率 vs 赔率隐含概率
                    odds_baseline = data.get('odds_baseline', {})
                    edge = 0
                    if odds_baseline and probs:
                        model_prob = probs.get(rec, 0)
                        odds_prob = odds_baseline.get(rec, 0)
                        edge = (model_prob - odds_prob) * 100

                    bets.append({
                        'home': r['home_team_cn'],
                        'away': r['away_team_cn'],
                        'league': r['league_name_cn'],
                        'selection': rec_label,
                        'prob': round(probs.get(rec, 0) * 100, 1),
                        'edge': round(edge, 1),
                        'confidence': round(confidence * 100, 1),
                        'reason': f"{rec_label}概率{probs.get(rec, 0)*100:.0f}%"
                    })
            except:
                pass

        # 按edge排序取前3
        bets.sort(key=lambda x: abs(x['edge']), reverse=True)
        conn.close()
        return {"top3": bets[:3]}
    except Exception as e:
        return {"error": str(e), "top3": []}


# ==================== 回测路由 ====================

@app.post("/api/bets/settle")
async def settle_bets_api():
    """手动触发投注结算"""
    try:
        from app.core.validate import _settle_bets
        db_path = str(Path(__file__).parent.parent.parent / "data" / "football_v2.db")
        result = _settle_bets(db_path)
        return result
    except Exception as e:
        return {"error": str(e), "settled": 0}

@app.get("/api/bets/roi")
async def bets_roi():
    """投注ROI统计 — 7天/30天/全部"""
    try:
        db_path = str(Path(__file__).parent.parent.parent / "data" / "football_v2.db")
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        summary = {}
        for label, days in [('7d', 7), ('30d', 30), ('all', None)]:
            if days:
                cursor.execute("""
                    SELECT count(*) as total,
                           sum(CASE WHEN result = 'win' THEN 1 ELSE 0 END) as wins,
                           sum(CASE WHEN result = 'lose' THEN 1 ELSE 0 END) as losses,
                           sum(CASE WHEN result = 'pending' THEN 1 ELSE 0 END) as pending,
                           sum(stake) as total_stake,
                           sum(payout) as total_payout,
                           sum(profit) as total_profit
                    FROM bet_records
                    WHERE created_at >= datetime('now', ?)
                """, (f'-{days} days',))
            else:
                cursor.execute("""
                    SELECT count(*) as total,
                           sum(CASE WHEN result = 'win' THEN 1 ELSE 0 END) as wins,
                           sum(CASE WHEN result = 'lose' THEN 1 ELSE 0 END) as losses,
                           sum(CASE WHEN result = 'pending' THEN 1 ELSE 0 END) as pending,
                           sum(stake) as total_stake,
                           sum(payout) as total_payout,
                           sum(profit) as total_profit
                    FROM bet_records
                """)
            row = cursor.fetchone()
            total_stake = row['total_stake'] or 0
            total_profit = row['total_profit'] or 0
            total = row['total'] or 0
            wins = row['wins'] or 0
            settled = total - (row['pending'] or 0)
            roi = (total_profit / total_stake * 100) if total_stake > 0 else 0
            win_rate = (wins / settled * 100) if settled > 0 else 0

            summary[label] = {
                'total': total,
                'settled': settled,
                'wins': wins,
                'losses': row['losses'] or 0,
                'pending': row['pending'] or 0,
                'total_stake': round(total_stake, 0),
                'total_payout': round(row['total_payout'] or 0, 0),
                'total_profit': round(total_profit, 0),
                'roi': round(roi, 1),
                'win_rate': round(win_rate, 1),
            }

        # Recent bets
        cursor.execute("""
            SELECT br.*, lm.home_team_cn, lm.away_team_cn, lm.league_name_cn
            FROM bet_records br
            LEFT JOIN lottery_matches lm ON br.lottery_match_id = lm.lottery_match_id
            ORDER BY br.created_at DESC
            LIMIT 20
        """)
        recent = []
        for row in cursor.fetchall():
            r = dict(row)
            recent.append(r)

        conn.close()
        return {'summary': summary, 'recent': recent}
    except Exception as e:
        return {"error": str(e)}

@app.get("/api/accuracy_trend")
async def accuracy_trend(days: int = 30):
    """准确率趋势 — 按天统计argmax正确率"""
    try:
        db_path = str(Path(__file__).parent.parent.parent / "data" / "football_v2.db")
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        # lottery_validation没有date列，通过join lottery_matches获取
        cursor.execute("""
            SELECT lm.match_date as date,
                   count(*) as total,
                   sum(CASE WHEN lv.is_correct = 1 THEN 1 ELSE 0 END) as correct
            FROM lottery_validation lv
            JOIN lottery_matches lm ON lv.lottery_match_id = lm.lottery_match_id
            WHERE lm.match_date >= date('now', ?)
            GROUP BY lm.match_date
            ORDER BY lm.match_date
        """, (f'-{days} days',))
        daily = []
        for row in cursor.fetchall():
            r = dict(row)
            r['accuracy'] = round(r['correct'] / r['total'] * 100, 1) if r['total'] > 0 else 0
            daily.append(r)

        conn.close()
        return {'days': days, 'daily': daily}
    except Exception as e:
        return {"error": str(e)}

@app.get("/api/backtest")
async def run_backtest_api(days: int = 30, stake: float = 100):
    """一键回测 — 验证过去N天按模型推荐投注的虚拟收益"""
    try:
        from app.core.backtest import run_backtest, backtest_to_dict
        db_path = str(Path(__file__).parent.parent.parent / "data" / "football_v2.db")
        result = run_backtest(db_path, days=days, stake_per_match=stake)
        return backtest_to_dict(result)
    except Exception as e:
        return {"error": str(e), "summary": {"total_matches": 0}}


@app.get("/api/oddsfe-backtest")
async def oddsfe_backtest_api():
    """Oddsfe大规模赔率回测 — 229K场Pinnacle赔率基线"""
    try:
        db_path = str(Path(__file__).parent.parent.parent / "data" / "football_v2.db")
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("""
            SELECT result_data, sample_size, created_at
            FROM oddsfe_backtest_results
            WHERE backtest_type = 'odds_baseline'
            ORDER BY created_at DESC LIMIT 1
        """)
        row = cursor.fetchone()
        conn.close()
        if row:
            data = json.loads(row['result_data']) if isinstance(row['result_data'], str) else row['result_data']
            data['cached_at'] = row['created_at']
            return data
        return {"error": "No backtest results found. Run: python -m backend.app.core.oddsfe_backtest"}
    except Exception as e:
        return {"error": str(e)}


@app.get("/api/validation/attribution")
async def validation_attribution():
    """翻车归因统计"""
    try:
        db_path = str(Path(__file__).parent.parent.parent / "data" / "football_v2.db")
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        # Count wrong predictions by attribution level
        cursor.execute("""
            SELECT COALESCE(attribution, 'unattributed') as level, count(*) as cnt
            FROM lottery_validation
            WHERE is_correct = 0
            GROUP BY attribution
        """)
        rows = cursor.fetchall()

        total_wrong = sum(r['cnt'] for r in rows)
        stats = []
        for r in rows:
            pct = round(r['cnt'] / total_wrong * 100, 1) if total_wrong else 0
            stats.append({
                'level': r['level'],
                'count': r['cnt'],
                'percentage': pct,
                'barWidth': f'{pct}%',
            })

        conn.close()
        return {"stats": stats}
    except Exception as e:
        return {"stats": [], "error": str(e)}


@app.get("/api/validation/trend")
async def validation_trend(days: int = 30):
    """准确率趋势(按日)"""
    try:
        db_path = str(Path(__file__).parent.parent.parent / "data" / "football_v2.db")
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute("""
            SELECT lm.match_date,
                   count(*) as total,
                   sum(lv.is_correct) as correct
            FROM lottery_validation lv
            JOIN lottery_matches lm ON lv.lottery_match_id = lm.lottery_match_id
            WHERE lm.match_date >= date('now', ?)
            GROUP BY lm.match_date
            ORDER BY lm.match_date
        """, (f'-{days} days',))
        rows = cursor.fetchall()

        trend = []
        for r in rows:
            acc = round(r['correct'] / r['total'] * 100, 1) if r['total'] else 0
            trend.append({
                'date': r['match_date'],
                'total': r['total'],
                'correct': r['correct'],
                'accuracy': acc,
            })

        conn.close()
        return {"trend": trend}
    except Exception as e:
        return {"trend": [], "error": str(e)}


# ==================== 热启动 ====================

@app.get("/api/analysis/{lottery_match_id}")
async def get_analysis_detail(lottery_match_id: str):
    """获取比赛分析详情 — 含因子分解"""
    try:
        db_path = str(Path(__file__).parent.parent.parent / "data" / "football_v2.db")
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row

        # Match info
        cursor = conn.execute("""
            SELECT lm.*, lo.odds_data as spf_odds
            FROM lottery_matches lm
            LEFT JOIN lottery_odds lo ON lm.lottery_match_id = lo.lottery_match_id
                AND lo.play_type = 'spf'
            WHERE lm.lottery_match_id = ?
            LIMIT 1
        """, (lottery_match_id,))
        match_row = cursor.fetchone()

        if not match_row:
            conn.close()
            return {"error": "Match not found"}

        match_info = dict(match_row)

        # Get prediction report (prefer prediction type, then full)
        report_cols = _table_columns(conn, "lottery_analysis_reports")
        active_report_filter = "AND COALESCE(is_stale, 0) = 0" if "is_stale" in report_cols else ""
        report_row = None
        for report_type in ['prediction', 'full']:
            cursor = conn.execute(f"""
                SELECT report_data, report_type, created_at
                FROM lottery_analysis_reports
                WHERE lottery_match_id = ? AND report_type = ?
                {active_report_filter}
                ORDER BY datetime(created_at) DESC, report_id DESC
                LIMIT 1
            """, (lottery_match_id, report_type))
            report_row = cursor.fetchone()
            if report_row:
                break

        report = None
        factor_breakdown = None
        model_vs_odds = None
        odds_baseline = None
        final_prediction = None

        if report_row:
            data = json.loads(report_row['report_data']) if isinstance(report_row['report_data'], str) else report_row['report_data']

            # Extract final prediction
            if 'final_prediction' in data:
                final_prediction = data['final_prediction']
            elif 'analyses' in data:
                spf = data.get('analyses', {}).get('spf', {})
                final_prediction = {
                    'probabilities': spf.get('probabilities', {}),
                    'predicted_result': spf.get('recommendation', ''),
                    'confidence': spf.get('confidence', 0),
                }

            # Build factor breakdown from available data
            # Old format: factor_breakdown has strength/poisson directly
            # New format: factor_breakdown has 'factors' key
            raw_fb = data.get('factor_breakdown')
            if raw_fb and isinstance(raw_fb, dict) and 'factors' in raw_fb:
                factor_breakdown = raw_fb
            else:
                factor_breakdown = _build_factor_breakdown_from_report(data)

            model_vs_odds = data.get('model_vs_odds')
            odds_baseline = data.get('odds_baseline')
            play_predictions = data.get('play_predictions', {})

        # Get result
        cursor = conn.execute("""
            SELECT * FROM lottery_results WHERE lottery_match_id = ?
        """, (lottery_match_id,))
        result_row = cursor.fetchone()
        result_info = dict(result_row) if result_row else None

        # Get validation
        cursor = conn.execute("""
            SELECT * FROM lottery_validation WHERE lottery_match_id = ?
        """, (lottery_match_id,))
        val_row = cursor.fetchone()
        validation = dict(val_row) if val_row else None

        conn.close()

        return {
            "match": match_info,
            "report": {
                "final_prediction": final_prediction,
                "factor_breakdown": factor_breakdown,
                "model_vs_odds": model_vs_odds,
                "odds_baseline": odds_baseline,
                "play_predictions": play_predictions,
            },
            "result": result_info,
            "validation": validation,
        }
    except Exception as e:
        return {"error": str(e)}


def _build_factor_breakdown_from_report(data: dict) -> dict:
    """从报告中提取因子分解 — 支持多种数据格式"""
    factors = {}
    prob_keys = ['home_win', 'draw', 'away_win']

    # 1. 从factor_breakdown直接提取(新格式)
    fb = data.get('factor_breakdown', {})
    if isinstance(fb, dict) and 'factors' in fb:
        return fb  # Already in new format

    # 2. 从factor_breakdown提取旧格式(strength/poisson with prob/weight)
    if isinstance(fb, dict):
        for key, val in fb.items():
            if isinstance(val, dict) and 'prob' in val:
                probs = val['prob']
                if isinstance(probs, dict) and 'home_win' in probs:
                    name = 'elo' if key == 'strength' else key
                    factors[name] = {k: round(probs.get(k, 0), 4) for k in prob_keys}

    # 3. 从base_prediction提取
    bp = data.get('base_prediction', {})
    if isinstance(bp, dict):
        # Elo
        elo = bp.get('elo', {})
        if isinstance(elo, dict):
            elo_probs = elo.get('predictions', elo.get('probabilities', {}))
            if elo_probs and 'home_win' in elo_probs:
                factors['elo'] = {k: round(elo_probs.get(k, 0), 4) for k in prob_keys}
        # Poisson
        poisson = bp.get('poisson', {})
        if isinstance(poisson, dict):
            p_probs = poisson.get('probabilities', {})
            if p_probs and 'home_win' in p_probs:
                factors['poisson'] = {k: round(p_probs.get(k, 0), 4) for k in prob_keys}

    # 4. 从form_comparison推导
    fc = data.get('form_comparison', {})
    if isinstance(fc, dict):
        comp = fc.get('comparison', {})
        if comp:
            level = comp.get('level', '')
            adv = comp.get('advantage', '')
            if adv == 'team1':
                factors['form'] = {'home_win': 0.45, 'draw': 0.28, 'away_win': 0.27}
            elif adv == 'team2':
                factors['form'] = {'home_win': 0.27, 'draw': 0.28, 'away_win': 0.45}
            else:
                factors['form'] = {'home_win': 0.35, 'draw': 0.32, 'away_win': 0.33}

    # 5. 从motivation_analysis推导
    ma = data.get('motivation_analysis', {})
    if isinstance(ma, dict):
        hm = ma.get('home_motivation', 0)
        am = ma.get('away_motivation', 0)
        diff = (hm if isinstance(hm, (int, float)) else 0) - (am if isinstance(am, (int, float)) else 0)
        if diff > 10:
            factors['motivation'] = {'home_win': 0.42, 'draw': 0.28, 'away_win': 0.30}
        elif diff < -10:
            factors['motivation'] = {'home_win': 0.30, 'draw': 0.28, 'away_win': 0.42}
        else:
            factors['motivation'] = {'home_win': 0.34, 'draw': 0.32, 'away_win': 0.34}

    # 6. Odds baseline
    if 'odds_baseline' in data:
        ob = data['odds_baseline']
        if isinstance(ob, dict) and 'home_win' in ob:
            factors['odds'] = {k: round(ob.get(k, 0), 4) for k in prob_keys}

    # Final
    final = None
    if 'final_prediction' in data:
        fp = data['final_prediction']
        fp_probs = fp.get('probabilities', {}) if isinstance(fp, dict) else {}
        if fp_probs:
            final = {k: round(fp_probs.get(k, 0), 4) for k in prob_keys}

    return {'factors': factors, 'final': final}

@app.post("/api/warmup")
async def run_warmup_api():
    """热启动 — 用oddsfe 229K历史数据校准初始参数"""
    try:
        from app.core.warmup import run_warmup
        db_path = str(Path(__file__).parent.parent.parent / "data" / "football_v2.db")
        result = run_warmup(db_path=db_path)
        return result
    except Exception as e:
        return {"error": str(e), "sample_size": 0, "odds_accuracy": 0}

@app.get("/api/warmup/status")
async def warmup_status():
    """热启动状态 — 当前权重+赔率校准"""
    try:
        db_path = str(Path(__file__).parent.parent.parent / "data" / "football_v2.db")
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row

        # Current weights
        c = conn.execute("SELECT * FROM model_weights WHERE is_active = 1 LIMIT 1")
        row = c.fetchone()
        weights = dict(row) if row else {}

        # Odds calibration
        c = conn.execute("SELECT cal_data FROM odds_calibration WHERE cal_key = 'odds_bucket_accuracy'")
        cal_row = c.fetchone()
        import json
        calibration = json.loads(cal_row['cal_data']) if cal_row else {}

        # Validation count (cold-start indicator)
        c = conn.execute("SELECT COUNT(*) FROM lottery_validation")
        val_count = c.fetchone()[0]

        conn.close()
        return {
            "weights": weights,
            "calibration": calibration,
            "validations": val_count,
            "is_cold_start": val_count < 10,
        }
    except Exception as e:
        return {"error": str(e)}

# ==================== APScheduler 日循环 ====================

_scheduler = None

def _start_daily_scheduler():
    """启动日循环调度器"""
    global _scheduler
    if str(os.environ.get("DISABLE_DAILY_SCHEDULER", "")).strip().lower() in {"1", "true", "yes", "on"}:
        logger.info("Daily scheduler disabled by DISABLE_DAILY_SCHEDULER")
        return
    try:
        from apscheduler.schedulers.background import BackgroundScheduler
        from apscheduler.triggers.cron import CronTrigger
        from apscheduler.triggers.interval import IntervalTrigger
    except ImportError:
        logger.warning("APScheduler not installed, daily cycle scheduler disabled")
        return

    db_path = DATABASE_PATH
    job_locks = {
        "rolling_collection": Lock(),
        "historical_backfill": Lock(),
        "intelligence_gap_fill": Lock(),
        "automation_center": Lock(),
    }

    def _ensure_data_foundation_tables():
        """Ensure durable run/evidence tables exist before background jobs start."""
        try:
            conn = sqlite3.connect(db_path, timeout=10)
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS collection_runs (
                    run_id TEXT PRIMARY KEY,
                    trigger_source TEXT NOT NULL DEFAULT 'manual',
                    run_type TEXT NOT NULL,
                    match_date TEXT,
                    status TEXT NOT NULL DEFAULT 'running',
                    started_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    finished_at TEXT,
                    summary_json TEXT NOT NULL DEFAULT '{}',
                    error TEXT
                );
                CREATE INDEX IF NOT EXISTS idx_collection_runs_date ON collection_runs(match_date);
                CREATE INDEX IF NOT EXISTS idx_collection_runs_status ON collection_runs(status);

                CREATE TABLE IF NOT EXISTS source_artifacts (
                    artifact_id TEXT PRIMARY KEY,
                    run_id TEXT,
                    source_name TEXT NOT NULL,
                    source_type TEXT,
                    entity_type TEXT,
                    entity_id TEXT,
                    payload_json TEXT NOT NULL,
                    payload_hash TEXT,
                    confidence REAL DEFAULT 0.5,
                    captured_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );
                CREATE INDEX IF NOT EXISTS idx_source_artifacts_entity ON source_artifacts(entity_type, entity_id);
                CREATE INDEX IF NOT EXISTS idx_source_artifacts_source ON source_artifacts(source_name, captured_at);

                CREATE TABLE IF NOT EXISTS source_entity_mappings (
                    mapping_id TEXT PRIMARY KEY,
                    entity_type TEXT NOT NULL,
                    canonical_id TEXT,
                    source_name TEXT NOT NULL,
                    source_entity_id TEXT,
                    source_entity_name TEXT,
                    confidence REAL DEFAULT 0.5,
                    status TEXT NOT NULL DEFAULT 'active',
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );
                CREATE UNIQUE INDEX IF NOT EXISTS idx_source_entity_mapping_unique
                    ON source_entity_mappings(entity_type, source_name, source_entity_id);

                CREATE TABLE IF NOT EXISTS match_context_snapshots (
                    snapshot_id TEXT PRIMARY KEY,
                    match_key TEXT NOT NULL,
                    snapshot_time TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    competition_context_json TEXT NOT NULL DEFAULT '{}',
                    odds_context_json TEXT NOT NULL DEFAULT '{}',
                    intel_context_json TEXT NOT NULL DEFAULT '{}',
                    data_quality_json TEXT NOT NULL DEFAULT '{}'
                );
                CREATE INDEX IF NOT EXISTS idx_context_snapshots_match
                    ON match_context_snapshots(match_key, snapshot_time);

                CREATE TABLE IF NOT EXISTS match_feature_snapshots (
                    snapshot_id TEXT PRIMARY KEY,
                    match_key TEXT NOT NULL,
                    snapshot_time TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    feature_json TEXT NOT NULL DEFAULT '{}',
                    model_version TEXT,
                    source_report_id TEXT
                );
                CREATE INDEX IF NOT EXISTS idx_feature_snapshots_match
                    ON match_feature_snapshots(match_key, snapshot_time);

                CREATE TABLE IF NOT EXISTS post_match_reviews (
                    review_id TEXT PRIMARY KEY,
                    match_key TEXT NOT NULL,
                    play_type TEXT,
                    predicted_result TEXT,
                    actual_result TEXT,
                    is_correct INTEGER,
                    attribution TEXT,
                    review_json TEXT NOT NULL DEFAULT '{}',
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );
                CREATE INDEX IF NOT EXISTS idx_post_match_reviews_match
                    ON post_match_reviews(match_key, play_type);

                CREATE TABLE IF NOT EXISTS similar_match_cases (
                    case_id TEXT PRIMARY KEY,
                    match_key TEXT NOT NULL,
                    play_type TEXT,
                    similar_match_key TEXT NOT NULL,
                    similarity_score REAL NOT NULL,
                    similarity_json TEXT NOT NULL DEFAULT '{}',
                    outcome_json TEXT NOT NULL DEFAULT '{}',
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );
                CREATE INDEX IF NOT EXISTS idx_similar_match_cases_match
                    ON similar_match_cases(match_key, similarity_score);
                CREATE INDEX IF NOT EXISTS idx_similar_match_cases_play
                    ON similar_match_cases(play_type, match_key, similarity_score);

                CREATE TABLE IF NOT EXISTS lottery_revalidation_queue (
                    queue_id TEXT PRIMARY KEY,
                    correction_id TEXT NOT NULL,
                    lottery_match_id TEXT NOT NULL,
                    reason TEXT,
                    status TEXT NOT NULL DEFAULT 'pending',
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    processed_at TEXT
                );
                CREATE INDEX IF NOT EXISTS idx_lottery_revalidation_status
                    ON lottery_revalidation_queue(status, created_at);
                """
            )
            conn.execute(
                """
                UPDATE collection_runs
                SET status = 'interrupted',
                    finished_at = COALESCE(finished_at, CURRENT_TIMESTAMP),
                    error = COALESCE(error, 'Marked interrupted during service startup')
                WHERE status = 'running'
                """
            )
            has_intelligence_runs = conn.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name='intelligence_runs'"
            ).fetchone()
            if has_intelligence_runs:
                conn.execute(
                    """
                    UPDATE intelligence_runs
                    SET status = 'interrupted',
                        finished_at = COALESCE(finished_at, CURRENT_TIMESTAMP),
                        error = COALESCE(error, 'Marked interrupted during service startup')
                    WHERE status = 'running'
                    """
                )
            conn.commit()
            conn.close()
        except Exception as e:
            logger.warning("Auto-loop foundation schema check failed: %s", e)

    _ensure_data_foundation_tables()

    def _run_locked(lock_key, job_name, fn):
        lock = job_locks[lock_key]
        if not lock.acquire(blocking=False):
            logger.info("%s skipped: previous run still active", job_name)
            return None
        try:
            return fn()
        except Exception as e:
            logger.error("%s failed: %s", job_name, e, exc_info=True)
            return None
        finally:
            lock.release()

    def _beijing_date(offset_days=0):
        from backend.app.core.time_utils import now_beijing

        return (now_beijing() + timedelta(days=offset_days)).date()

    def _collection_running(run_type, max_age_minutes=90):
        try:
            conn = sqlite3.connect(db_path, timeout=10)
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                """
                SELECT started_at
                FROM collection_runs
                WHERE run_type = ?
                  AND status = 'running'
                ORDER BY started_at DESC
                LIMIT 1
                """,
                (run_type,),
            ).fetchone()
            conn.close()
            if not row:
                return False
            started_at = str(row["started_at"] or "")[:19]
            try:
                started = datetime.strptime(started_at, "%Y-%m-%d %H:%M:%S")
                return started >= datetime.now() - timedelta(minutes=max_age_minutes)
            except ValueError:
                return True
        except Exception:
            return False

    def _run_lottery_analysis_for_dates(date_values, limit=12):
        try:
            from backend.app.core.analyze import analyze_single

            conn = sqlite3.connect(db_path, timeout=10)
            conn.row_factory = sqlite3.Row
            report_cols = {
                row[1]
                for row in conn.execute("PRAGMA table_info(lottery_analysis_reports)").fetchall()
            }
            stale_expr = (
                "COALESCE((SELECT COALESCE(ar.is_stale, 0) FROM lottery_analysis_reports ar "
                "WHERE ar.lottery_match_id = lm.lottery_match_id AND ar.report_type IN ('prediction', 'full') "
                "ORDER BY datetime(ar.created_at) DESC, ar.report_id DESC LIMIT 1), 0)"
                if "is_stale" in report_cols
                else "0"
            )
            has_intelligence_tables = (
                conn.execute(
                    "SELECT 1 FROM sqlite_master WHERE type='table' AND name='intelligence_jobs'"
                ).fetchone() is not None
                and conn.execute(
                    "SELECT 1 FROM sqlite_master WHERE type='table' AND name='intelligence_packages'"
                ).fetchone() is not None
            )
            latest_intelligence_expr = (
                """
                           (
                               SELECT MAX(ip.updated_at)
                               FROM intelligence_jobs ij
                               JOIN intelligence_packages ip ON ip.job_id = ij.job_id
                               WHERE ij.lottery_match_id = lm.lottery_match_id
                           ) AS latest_intelligence_at,
                """
                if has_intelligence_tables
                else "NULL AS latest_intelligence_at,"
            )
            placeholders = ",".join(["?"] * len(date_values))
            rows = conn.execute(
                f"""
                SELECT *
                FROM (
                    SELECT lm.lottery_match_id,
                           lm.league_name_cn,
                           lm.sell_status,
                           COALESCE((
                               SELECT COUNT(*)
                               FROM lottery_analysis_reports ar
                               WHERE ar.lottery_match_id = lm.lottery_match_id
                                 AND ar.report_type IN ('prediction', 'full')
                           ), 0) AS report_count,
                           {stale_expr} AS stale_count,
                           (
                               SELECT MAX(ar.created_at)
                               FROM lottery_analysis_reports ar
                               WHERE ar.lottery_match_id = lm.lottery_match_id
                                 AND ar.report_type IN ('prediction', 'full')
                           ) AS latest_report_at,
                           {latest_intelligence_expr}
                           (
                               SELECT ar.report_data
                               FROM lottery_analysis_reports ar
                               WHERE ar.lottery_match_id = lm.lottery_match_id
                                 AND ar.report_type IN ('prediction', 'full')
                               ORDER BY ar.created_at DESC, ar.rowid DESC
                               LIMIT 1
                           ) AS latest_report_data
                    FROM lottery_matches lm
                    WHERE lm.home_team_id IS NOT NULL
                      AND lm.away_team_id IS NOT NULL
                      AND substr(COALESCE(lm.beijing_time, lm.match_date), 1, 10) IN ({placeholders})
                ) q
                WHERE report_count = 0
                   OR stale_count > 0
                   OR (
                        latest_intelligence_at IS NOT NULL
                        AND latest_report_at IS NOT NULL
                        AND latest_intelligence_at > latest_report_at
                        AND COALESCE(sell_status, '') NOT IN ('finished')
                        AND latest_report_at < datetime('now', '-2 hours')
                      )
                   OR (
                        (league_name_cn LIKE '%世界杯%' OR league_name_cn LIKE '%World Cup%')
                        AND COALESCE(sell_status, '') NOT IN ('finished')
                        AND latest_report_at IS NOT NULL
                        AND latest_report_at < datetime('now', '-6 hours')
                      )
                   OR (
                        (league_name_cn LIKE '%世界杯%' OR league_name_cn LIKE '%World Cup%')
                        AND latest_report_data LIKE '%offline_fallback%'
                      )
                ORDER BY COALESCE(latest_report_at, '1970-01-01') ASC, lottery_match_id
                LIMIT ?
                """,
                [str(item) for item in date_values] + [limit],
            ).fetchall()
            conn.close()
            analyzed = 0
            for row in rows:
                if analyze_single(db_path, row["lottery_match_id"]):
                    analyzed += 1
                    try:
                        cleanup = sqlite3.connect(db_path, timeout=10)
                        cleanup_cols = {
                            col[1]
                            for col in cleanup.execute("PRAGMA table_info(lottery_analysis_reports)").fetchall()
                        }
                        if "is_stale" in cleanup_cols:
                            latest_report = cleanup.execute(
                                """
                                SELECT report_id
                                FROM lottery_analysis_reports
                                WHERE lottery_match_id = ?
                                  AND report_type IN ('prediction', 'full')
                                ORDER BY datetime(created_at) DESC, report_id DESC
                                LIMIT 1
                                """,
                                (row["lottery_match_id"],),
                            ).fetchone()
                            latest_report_id = latest_report[0] if latest_report else None
                            cleanup.execute(
                                """
                                UPDATE lottery_analysis_reports
                                SET is_stale = CASE WHEN report_id = ? THEN 0 ELSE 1 END
                                WHERE lottery_match_id = ?
                                  AND report_type IN ('prediction', 'full')
                                """,
                                (latest_report_id, row["lottery_match_id"]),
                            )
                            cleanup.commit()
                        cleanup.close()
                    except Exception:
                        pass
            return {"candidates": len(rows), "analyzed": analyzed, "reason": "missing/stale/world_cup_refresh"}
        except Exception as e:
            logger.error("Rolling analysis failed: %s", e)
            return {"candidates": 0, "analyzed": 0, "error": str(e)}

    def _find_historical_backfill_date(lookback_days=180):
        try:
            today = _beijing_date(0).isoformat()
            start = (_beijing_date(0) - timedelta(days=lookback_days)).isoformat()
            conn = sqlite3.connect(db_path, timeout=10)
            conn.row_factory = sqlite3.Row
            has_source_artifacts = conn.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name='source_artifacts'"
            ).fetchone() is not None
            event_cache_join = ""
            event_cache_select = "0 AS missing_event_cache"
            event_cache_having = ""
            if has_source_artifacts:
                event_cache_join = """
                LEFT JOIN (
                    SELECT DISTINCT entity_id
                    FROM source_artifacts
                    WHERE source_name = 'oddsfe'
                      AND entity_type = 'event'
                ) sea ON sea.entity_id = CAST(lm.oddsfe_event_id AS TEXT)
                """
                event_cache_select = """
                       SUM(CASE WHEN lm.oddsfe_event_id IS NOT NULL
                                 AND lm.oddsfe_event_id <> ''
                                 AND sea.entity_id IS NULL
                                THEN 1 ELSE 0 END) AS missing_event_cache
                """
                event_cache_having = " OR missing_event_cache > 0"
            row = conn.execute(
                f"""
                SELECT substr(COALESCE(lm.beijing_time, lm.match_date), 1, 10) AS d,
                       SUM(CASE WHEN lo.lottery_match_id IS NULL
                                 THEN 1 ELSE 0 END) AS missing_odds,
                       SUM(CASE WHEN lr.lottery_match_id IS NULL
                                 AND lm.oddsfe_event_id IS NOT NULL
                                 AND lm.oddsfe_event_id <> ''
                                 THEN 1 ELSE 0 END) AS missing_results,
                       SUM(CASE WHEN ar.lottery_match_id IS NULL
                                 AND lm.home_team_id IS NOT NULL
                                 AND lm.away_team_id IS NOT NULL
                                THEN 1 ELSE 0 END) AS missing_analysis,
                       SUM(CASE WHEN lr.lottery_match_id IS NOT NULL
                                 AND ar.lottery_match_id IS NOT NULL
                                 AND lv.lottery_match_id IS NULL
                                THEN 1 ELSE 0 END) AS missing_validation,
                       SUM(CASE WHEN lr.lottery_match_id IS NOT NULL
                                 AND ip.job_id IS NULL
                                THEN 1 ELSE 0 END) AS missing_intelligence,
                       {event_cache_select}
                FROM lottery_matches lm
                LEFT JOIN lottery_results lr ON lr.lottery_match_id = lm.lottery_match_id
                LEFT JOIN lottery_analysis_reports ar
                  ON ar.lottery_match_id = lm.lottery_match_id
                 AND ar.report_type IN ('prediction', 'full')
                LEFT JOIN (
                    SELECT DISTINCT lottery_match_id
                    FROM lottery_odds
                    WHERE play_type IN ('spf', 'rqspf')
                ) lo ON lo.lottery_match_id = lm.lottery_match_id
                LEFT JOIN lottery_validation lv ON lv.lottery_match_id = lm.lottery_match_id
                LEFT JOIN intelligence_jobs ij ON ij.lottery_match_id = lm.lottery_match_id
                LEFT JOIN intelligence_packages ip ON ip.job_id = ij.job_id
                {event_cache_join}
                WHERE substr(COALESCE(lm.beijing_time, lm.match_date), 1, 10) >= ?
                  AND substr(COALESCE(lm.beijing_time, lm.match_date), 1, 10) < ?
                GROUP BY d
                HAVING missing_odds > 0
                    OR missing_results > 0
                    OR missing_analysis > 0
                    OR missing_validation > 0
                    OR missing_intelligence > 0
                    {event_cache_having}
                ORDER BY d DESC
                LIMIT 1
                """,
                (start, today),
            ).fetchone()
            conn.close()
            return dict(row) if row else None
        except Exception as e:
            logger.error("Historical backfill date selection failed: %s", e)
            return None

    def _run_validation_for_date(date_value):
        try:
            from backend.app.core.validate import _validate_predictions
            from backend.app.lottery.services.auto_gap_runner import LotteryAutoGapRunner

            result = _validate_predictions(db_path, [date_value]) or {}
            result["reanalysis_change_settlement"] = LotteryAutoGapRunner(
                db_path,
                ODDSFE_DB_PATH,
            ).settle_reanalysis_changes(date_value, date_value)
            return result
        except Exception as e:
            logger.error("Validation backfill failed for %s: %s", date_value, e)
            return {"error": str(e)}

    def _run_pending_revalidations(limit=10):
        try:
            conn = sqlite3.connect(db_path, timeout=10)
            conn.row_factory = sqlite3.Row
            has_queue = conn.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name='lottery_revalidation_queue'"
            ).fetchone()
            if not has_queue:
                conn.close()
                return {"skipped": True, "reason": "queue_missing"}
            rows = conn.execute(
                """
                SELECT q.queue_id, q.lottery_match_id,
                       substr(COALESCE(lm.beijing_time, lm.match_date), 1, 10) AS match_date
                FROM lottery_revalidation_queue q
                JOIN lottery_matches lm ON lm.lottery_match_id = q.lottery_match_id
                WHERE q.status = 'pending'
                ORDER BY q.created_at ASC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
            conn.close()
            if not rows:
                return {"pending": 0, "processed": 0}

            dates = sorted({row["match_date"] for row in rows if row["match_date"]})
            results = []
            for date_value in dates:
                results.append({"date": date_value, **_run_validation_for_date(date_value)})

            conn = sqlite3.connect(db_path, timeout=10)
            conn.executemany(
                """
                UPDATE lottery_revalidation_queue
                SET status = 'processed', processed_at = CURRENT_TIMESTAMP
                WHERE queue_id = ?
                """,
                [(row["queue_id"],) for row in rows],
            )
            conn.commit()
            conn.close()
            return {"pending": len(rows), "processed": len(rows), "results": results}
        except Exception as e:
            logger.error("Pending revalidation failed: %s", e)
            return {"error": str(e)}

    def _run_cycle_mode(mode):
        """在子线程中运行日循环"""
        try:
            import subprocess
            project_root = str(Path(__file__).parent.parent.parent)
            result = subprocess.run(
                [sys.executable, '-m', 'backend.app.core.daily_runner', '--mode', mode],
                cwd=project_root,
                capture_output=True, text=True, timeout=300
            )
            logger.info('Daily cycle [%s] exit=%d', mode, result.returncode)
            if result.stderr:
                logger.debug('Daily cycle [%s] stderr: %s', mode, result.stderr[:500])
        except Exception as e:
            logger.error('Daily cycle [%s] failed: %s', mode, e)

    def _run_intelligence(offset_days=0, include_external=True, trigger_source='scheduler'):
        """Run match intelligence pipeline for today/tomorrow."""
        try:
            from app.intelligence.service import IntelligenceService
            from backend.app.core.time_utils import today_beijing, tomorrow_beijing

            if offset_days == 0:
                target_date = today_beijing()
            elif offset_days == 1:
                target_date = tomorrow_beijing()
            else:
                from datetime import datetime, timedelta

                target_date = (datetime.strptime(today_beijing(), "%Y-%m-%d") + timedelta(days=offset_days)).strftime("%Y-%m-%d")

            collectors = ['weather', 'team_news', 'injuries_suspensions', 'expected_lineup'] if include_external else None
            result = IntelligenceService(db_path).run_daily_logged(
                match_date=target_date,
                include_external=include_external,
                collectors=collectors,
                network=True,
                force=False,
                trigger_source=trigger_source,
            )
            jobs_count = len(result.get('summary', {}).get('results', []))
            logger.info('Intelligence pipeline [%s] date=%s jobs=%d', trigger_source, target_date, jobs_count)
        except Exception as e:
            logger.error('Intelligence pipeline [%s] failed: %s', trigger_source, e)

    def _run_intelligence_reviews(offset_days=-1, play_type='spf', trigger_source='scheduler_review'):
        """Create post-match intelligence reviews after results validation."""
        try:
            from datetime import datetime, timedelta
            from app.intelligence.service import IntelligenceService
            from backend.app.core.time_utils import today_beijing

            target_date = (datetime.strptime(today_beijing(), "%Y-%m-%d") + timedelta(days=offset_days)).strftime("%Y-%m-%d")
            result = IntelligenceService(db_path).auto_review_for_date(match_date=target_date, play_type=play_type)
            logger.info(
                'Intelligence reviews [%s] date=%s reviewed=%d pending=%d failed=%d',
                trigger_source,
                target_date,
                len(result.get('reviewed', [])),
                len(result.get('pending', [])),
                len(result.get('failed', [])),
            )
            return result
        except Exception as e:
            logger.error('Intelligence reviews [%s] failed: %s', trigger_source, e)
            return {"error": str(e)}

    def _run_intelligence_gap_fill(
        start_offset=-1,
        end_offset=1,
        start_date=None,
        end_date=None,
        network=True,
        force=False,
        limit=8,
        collectors=None,
        trigger_source='scheduler_intelligence_gap_fill',
    ):
        """Fill prioritized missing or low-confidence intelligence requirements in small batches."""
        def _job():
            try:
                from app.intelligence.service import IntelligenceService

                gap_start_date = start_date or _beijing_date(start_offset).isoformat()
                gap_end_date = end_date or _beijing_date(end_offset).isoformat()
                selected_collectors = collectors or [
                    'injuries_suspensions',
                    'team_news',
                    'expected_lineup',
                    'weather',
                ]
                result = IntelligenceService(db_path).fill_gaps_logged(
                    start_date=gap_start_date,
                    end_date=gap_end_date,
                    collectors=selected_collectors,
                    network=network,
                    force=force,
                    include_optional=True,
                    include_builtin=True,
                    limit=limit,
                    trigger_source=trigger_source,
                )
                summary = result.get('summary', result)
                logger.info(
                    'Intelligence gap fill [%s] range=%s..%s processed=%s planned=%s',
                    trigger_source,
                    gap_start_date,
                    gap_end_date,
                    summary.get('processed'),
                    summary.get('planned_candidates'),
                )
                return result
            except Exception as e:
                logger.error('Intelligence gap fill [%s] failed: %s', trigger_source, e)
                return {"error": str(e)}

        return _run_locked("intelligence_gap_fill", "intelligence_gap_fill", _job)

    def _run_similar_case_refresh(trigger_source='scheduler_similar_cases'):
        """Refresh rule-based similar cases from the latest feature snapshots/reviews."""
        try:
            from scripts.build_similar_match_cases import build_cases

            summary = {
                'spf': build_cases(Path(db_path), play_type='spf', top_k=5, min_score=0.68),
                'rqspf': build_cases(Path(db_path), play_type='rqspf', top_k=5, min_score=0.66),
                'bqc': build_cases(Path(db_path), play_type='bqc', top_k=5, min_score=0.64),
                'ou': build_cases(Path(db_path), play_type='ou', top_k=5, min_score=0.66),
                'bf': build_cases(Path(db_path), play_type='bf', top_k=5, min_score=0.62),
            }
            logger.info('Similar cases [%s] refreshed: %s', trigger_source, summary)
            return summary
        except Exception as e:
            logger.error('Similar cases [%s] failed: %s', trigger_source, e)
            return {"error": str(e)}

    def _run_foundation_backfill(trigger_source='scheduler_foundation_backfill', limit=500, include_mappings=False):
        """Idempotently backfill durable snapshots/reviews from existing reports and validations."""
        try:
            from scripts.backfill_data_foundation import (
                backfill_mappings,
                backfill_reviews,
                backfill_snapshots,
                connect,
            )
            from backend.app.data_access.foundation_dao import FoundationDAO

            dao = FoundationDAO(db_path)
            conn = connect(Path(db_path))
            try:
                row_limit = limit or None
                summary = {
                    "mappings": backfill_mappings(conn, dao, row_limit) if include_mappings else 0,
                    "reviews": backfill_reviews(conn, dao, row_limit),
                    "snapshots": backfill_snapshots(conn, dao, row_limit),
                }
            finally:
                conn.close()
            logger.info("Foundation backfill [%s] completed: %s", trigger_source, summary)
            return summary
        except Exception as e:
            logger.error("Foundation backfill [%s] failed: %s", trigger_source, e)
            return {"error": str(e)}

    def _run_foundation_snapshot_cleanup(trigger_source='scheduler_snapshot_cleanup'):
        """Remove duplicate durable snapshot rows without creating scheduled backups."""
        try:
            from scripts.cleanup_foundation_snapshots import cleanup_snapshots

            summary = cleanup_snapshots(Path(db_path), apply=True, backup=False, vacuum=False)
            logger.info("Foundation snapshot cleanup [%s] completed: %s", trigger_source, summary)
            return summary
        except Exception as e:
            logger.error("Foundation snapshot cleanup [%s] failed: %s", trigger_source, e)
            return {"error": str(e)}

    def _foundation_backfill_changed(summary):
        try:
            return sum(int(summary.get(key) or 0) for key in ("mappings", "reviews", "snapshots")) > 0
        except Exception:
            return False

    def _run_learning_refresh(trigger_source='scheduler_learning_refresh', limit=0):
        """Refresh the learning foundation and rebuild similar cases in one auditable job."""
        from backend.app.data_access.foundation_dao import FoundationDAO

        foundation = FoundationDAO(db_path)
        run_id = foundation.start_run(
            run_type="learning_refresh",
            match_date=today_beijing(),
            trigger_source=trigger_source,
            summary={"stage": "start"},
        )
        summary = {}
        try:
            summary["foundation_backfill"] = _run_foundation_backfill(
                trigger_source,
                limit=limit,
                include_mappings=True,
            )
            summary["snapshot_cleanup"] = _run_foundation_snapshot_cleanup(
                trigger_source + "_snapshot_cleanup"
            )
            summary["similar_cases"] = _run_similar_case_refresh(trigger_source + "_similar_cases")
            foundation.finish_run(run_id, status="success", summary=summary)
            return summary
        except Exception as e:
            foundation.finish_run(run_id, status="failed", summary=summary, error=str(e))
            logger.error("Learning refresh [%s] failed: %s", trigger_source, e)
            return {"error": str(e), **summary}

    def _run_rolling_collection():
        """Continuously refresh current live/upcoming/recent matches in small batches."""
        def _job():
            from backend.app.data_access.foundation_dao import FoundationDAO
            from backend.app.core.collect import _update_match_status
            from backend.app.lottery.services.oddsfe_event_sync import OddsfeEventDetailSync
            from backend.app.lottery.services.oddsfe_ou_line_sync import OddsfeOuLineSync

            # Yesterday settles late results, today/tomorrow drive live work, and
            # +2 days lets the cockpit prepare odds, intelligence and analysis early.
            target_dates = [_beijing_date(offset) for offset in (-1, 0, 1, 2)]
            summary = {"sporttery": [], "status": {}, "oddsfe": {}, "oddsfe_ou": {}, "analysis": {}, "intelligence": {}}
            foundation = FoundationDAO(db_path)
            run_id = foundation.start_run(
                run_type="auto_loop_cycle",
                match_date=target_dates[1].isoformat(),
                trigger_source="scheduler_rolling_collection",
                summary={"stage": "start", "window": [target.isoformat() for target in target_dates]},
            )

            try:
                summary["sporttery"] = {
                    "skipped": True,
                    "reason": "high-frequency loop keeps to lightweight status/result/intelligence work; full sporttery sync remains in daily/manual flow",
                }

                summary["status"] = _update_match_status(db_path)

                if _collection_running("oddsfe_event_details", max_age_minutes=75):
                    summary["oddsfe"] = {"skipped": True, "reason": "existing oddsfe_event_details run active"}
                else:
                    sync = OddsfeEventDetailSync(db_path)
                    summaries = []
                    for batch_index in range(2):
                        result = sync.run(
                            target_dates[0].isoformat(),
                            target_dates[-1].isoformat(),
                            apply=True,
                            refresh=False,
                            fetch_schedule=True,
                            include_schedule_only=True,
                            max_events=8,
                            schedule_padding_days=1,
                            cache_minutes=12,
                            sleep_seconds=0.12,
                            trigger_source="scheduler_rolling_collection",
                        )
                        result["batch_index"] = batch_index + 1
                        summaries.append(result)
                        if not result.get("candidates_deferred"):
                            break
                    summary["oddsfe"] = {"batches": summaries}

                if _collection_running("oddsfe_ou_lines", max_age_minutes=45):
                    summary["oddsfe_ou"] = {"skipped": True, "reason": "existing oddsfe_ou_lines run active"}
                else:
                    summary["oddsfe_ou"] = OddsfeOuLineSync(db_path).run(
                        target_dates[0].isoformat(),
                        target_dates[-1].isoformat(),
                        apply=True,
                        fetch_live=True,
                        max_events=8,
                        reanalyze=False,
                        trigger_source="scheduler_rolling_collection",
                    )

                date_values = [target.isoformat() for target in target_dates]
                summary["analysis"] = _run_lottery_analysis_for_dates(date_values, limit=12)

                try:
                    from backend.app.intelligence.service import IntelligenceService

                    summary["finished_intelligence_backfill"] = IntelligenceService(db_path).backfill_finished(
                        start_date=target_dates[0].isoformat(),
                        end_date=target_dates[1].isoformat(),
                        include_external=False,
                        network=False,
                        force=False,
                        limit=30,
                    )
                except Exception as e:
                    logger.warning("Rolling finished intelligence backfill failed: %s", e)
                    summary["finished_intelligence_backfill"] = {"error": str(e)}

                _run_intelligence(0, False, "scheduler_rolling_intelligence")
                _run_intelligence(1, False, "scheduler_rolling_tomorrow_intelligence")
                _run_intelligence(2, False, "scheduler_rolling_next2_intelligence")
                summary["intelligence_gap_fill"] = _run_intelligence_gap_fill(
                    -1,
                    2,
                    network=True,
                    force=False,
                    limit=6,
                    trigger_source="scheduler_rolling_gap_fill",
                )
                summary["post_intelligence_analysis"] = _run_lottery_analysis_for_dates(date_values, limit=8)
                summary["intelligence_review"] = _run_intelligence_reviews(-1, "spf", "scheduler_rolling_review")
                try:
                    from backend.app.lottery.services.auto_gap_runner import LotteryAutoGapRunner

                    summary["auto_gap_fill"] = LotteryAutoGapRunner(db_path, ODDSFE_DB_PATH).run(
                        date_from=date_values[0],
                        date_to=date_values[-1],
                        action_counts=None,
                        max_events=8,
                        max_analysis=8,
                        max_intelligence=6,
                        max_validation_dates=3,
                        fetch_live_ou=True,
                        network_intelligence=True,
                        trigger_source="scheduler_rolling_auto_gap",
                    )
                except Exception as e:
                    logger.warning("Rolling auto gap fill failed: %s", e)
                    summary["auto_gap_fill"] = {"error": str(e)}
                summary["foundation_backfill"] = _run_foundation_backfill(
                    "scheduler_rolling_foundation",
                    limit=500,
                    include_mappings=False,
                )
                changed_this_cycle = (
                    summary.get("analysis", {}).get("analyzed", 0) > 0
                    or summary.get("post_intelligence_analysis", {}).get("analyzed", 0) > 0
                    or any(
                        int(value or 0) > 0
                        for value in summary.get("auto_gap_fill", {}).get("action_counts", {}).values()
                    )
                    or _foundation_backfill_changed(summary.get("foundation_backfill", {}))
                )
                if changed_this_cycle:
                    summary["snapshot_cleanup"] = _run_foundation_snapshot_cleanup(
                        "scheduler_rolling_snapshot_cleanup"
                    )
                else:
                    summary["snapshot_cleanup"] = {"skipped": True, "reason": "no refreshed analysis or foundation rows"}
                if (
                    changed_this_cycle
                    or summary.get("snapshot_cleanup", {}).get("deleted_total", 0) > 0
                ):
                    summary["similar_cases"] = _run_similar_case_refresh("scheduler_rolling_similar_cases")
                else:
                    summary["similar_cases"] = {"skipped": True, "reason": "no refreshed analysis in this cycle"}
                foundation.finish_run(run_id, status="success", summary=summary)
                logger.info("Rolling collection completed: %s", summary)
                return summary
            except Exception as e:
                foundation.finish_run(run_id, status="failed", summary=summary, error=str(e))
                raise

        return _run_locked("rolling_collection", "rolling_collection", _job)

    def _run_historical_backfill():
        """Backfill older dates in reverse order without blocking the current window."""
        def _job():
            from backend.app.data_access.foundation_dao import FoundationDAO
            from backend.app.intelligence.service import IntelligenceService
            from backend.app.lottery.services.oddsfe_event_sync import OddsfeEventDetailSync
            from backend.app.lottery.services.oddsfe_ou_line_sync import OddsfeOuLineSync

            target = _find_historical_backfill_date()
            if not target:
                logger.info("Historical backfill skipped: no incomplete historical date found")
                return {"skipped": True}

            target_date = target["d"]
            summary = {"date": target_date, "target": target}
            foundation = FoundationDAO(db_path)
            run_id = foundation.start_run(
                run_type="historical_backfill",
                match_date=target_date,
                trigger_source="scheduler_historical_backfill",
                summary={"stage": "start", "target": target},
            )
            try:
                if _collection_running("oddsfe_event_details", max_age_minutes=75):
                    summary["oddsfe"] = {"skipped": True, "reason": "existing oddsfe_event_details run active"}
                else:
                    sync = OddsfeEventDetailSync(db_path)
                    summary["oddsfe"] = sync.run(
                        target_date,
                        target_date,
                        apply=True,
                        refresh=False,
                        fetch_schedule=True,
                        include_schedule_only=False,
                        max_events=8,
                        schedule_padding_days=1,
                        cache_minutes=1440,
                        sleep_seconds=0.12,
                        trigger_source="scheduler_historical_backfill",
                    )

                if _collection_running("oddsfe_ou_lines", max_age_minutes=45):
                    summary["oddsfe_ou"] = {"skipped": True, "reason": "existing oddsfe_ou_lines run active"}
                else:
                    summary["oddsfe_ou"] = OddsfeOuLineSync(db_path).run(
                        target_date,
                        target_date,
                        apply=True,
                        fetch_live=True,
                        max_events=8,
                        reanalyze=False,
                        trigger_source="scheduler_historical_backfill",
                    )

                summary["analysis"] = _run_lottery_analysis_for_dates([target_date], limit=10)
                try:
                    summary["intelligence_backfill"] = IntelligenceService(db_path).backfill_finished(
                        start_date=target_date,
                        end_date=target_date,
                        include_external=False,
                        network=False,
                        force=False,
                        limit=10,
                    )
                except Exception as e:
                    summary["intelligence_backfill"] = {"error": str(e)}
                summary["intelligence_gap_fill"] = _run_intelligence_gap_fill(
                    start_date=target_date,
                    end_date=target_date,
                    network=False,
                    force=False,
                    limit=5,
                    collectors=["team_news", "injuries_suspensions", "expected_lineup"],
                    trigger_source="scheduler_historical_gap_fill",
                )
                summary["post_intelligence_analysis"] = _run_lottery_analysis_for_dates([target_date], limit=10)
                summary["validation"] = _run_validation_for_date(target_date)
                summary["queued_revalidation"] = _run_pending_revalidations(limit=10)
                try:
                    from backend.app.lottery.services.auto_gap_runner import LotteryAutoGapRunner

                    summary["auto_gap_fill"] = LotteryAutoGapRunner(db_path, ODDSFE_DB_PATH).run(
                        date_from=target_date,
                        date_to=target_date,
                        action_counts=None,
                        max_events=8,
                        max_analysis=10,
                        max_intelligence=5,
                        max_validation_dates=1,
                        fetch_live_ou=True,
                        network_intelligence=False,
                        trigger_source="scheduler_historical_auto_gap",
                    )
                except Exception as e:
                    logger.warning("Historical auto gap fill failed: %s", e)
                    summary["auto_gap_fill"] = {"error": str(e)}
                summary["foundation_backfill"] = _run_foundation_backfill(
                    "scheduler_historical_foundation",
                    limit=500,
                    include_mappings=False,
                )
                if (
                    summary.get("analysis", {}).get("analyzed", 0) > 0
                    or summary.get("post_intelligence_analysis", {}).get("analyzed", 0) > 0
                    or summary.get("validation", {}).get("validated", 0) > 0
                    or summary.get("queued_revalidation", {}).get("processed", 0) > 0
                    or any(
                        int(value or 0) > 0
                        for value in summary.get("auto_gap_fill", {}).get("action_counts", {}).values()
                    )
                    or _foundation_backfill_changed(summary.get("foundation_backfill", {}))
                ):
                    summary["similar_cases"] = _run_similar_case_refresh("scheduler_historical_similar_cases")
                else:
                    summary["similar_cases"] = {"skipped": True, "reason": "no new analysis or validation"}
                foundation.finish_run(run_id, status="success", summary=summary)
                logger.info("Historical backfill completed: %s", summary)
                return summary
            except Exception as e:
                foundation.finish_run(run_id, status="failed", summary=summary, error=str(e))
                raise

        return _run_locked("historical_backfill", "historical_backfill", _job)

    def _run_parallel_automation_center():
        """Run the task-based automation center as the non-blocking coordinator."""
        def _job():
            from backend.app.lottery.services.automation_control import (
                automation_center_kwargs_from_state,
                get_automation_control_state,
            )
            from backend.app.lottery.services.automation_center import AutomationCenter

            control = get_automation_control_state(db_path)
            if not control.get("enabled"):
                logger.info("automation_center skipped by control state: %s", control)
                return {
                    "success": True,
                    "skipped": True,
                    "reason": "automation_control_paused",
                    "control": control,
                }
            kwargs = automation_center_kwargs_from_state(control, trigger_source="scheduler_automation_center")
            center = AutomationCenter(db_path, ODDSFE_DB_PATH)
            rescue = center.retry_recent_failed_task(
                trigger_source="scheduler_automation_retry_rescue",
                workers=1,
                task_timeout_seconds=min(int(kwargs.get("task_timeout_seconds") or 300), 300),
            )
            result = center.run(**kwargs)
            if isinstance(result, dict):
                result["failure_rescue"] = rescue
            return result

            return AutomationCenter(db_path, ODDSFE_DB_PATH).run(
                mode="mixed",
                league="世界杯",
                historical_dates=1,
                historical_lookback_days=180,
                include_learning=True,
                workers=3,
                task_timeout_seconds=300,
                max_events=6,
                max_analysis=10,
                max_intelligence=6,
                max_validation_dates=1,
                national_ou_gate=True,
                fetch_live_ou=True,
                network_intelligence=True,
                trigger_source="scheduler_automation_center",
            )

        return _run_locked("automation_center", "automation_center", _job)

    _scheduler = BackgroundScheduler()

    # 6:00 自感知 + 采集 + 情报 + 分类 + 分析 + 推送
    _scheduler.add_job(
        lambda: _run_cycle_mode('morning'),
        CronTrigger(hour=6, minute=5),
        id='morning_cycle',
        name='上午日循环(感知→推送)',
        replace_existing=True
    )

    # 14:00 CLV更新
    _scheduler.add_job(
        lambda: _run_cycle_mode('clv'),
        CronTrigger(hour=14, minute=5),
        id='clv_cycle',
        name='14:00 CLV赔率更新',
        replace_existing=True
    )

    # 次日2:00 复盘验证 + 学习
    _scheduler.add_job(
        lambda: _run_cycle_mode('validate'),
        CronTrigger(hour=2, minute=5),
        id='validate_cycle',
        name='次日复盘验证',
        replace_existing=True
    )

    # 2:35 将竞彩验证结果同步成比赛情报复盘归因
    _scheduler.add_job(
        lambda: _run_intelligence_reviews(-1, 'spf', 'scheduler_intelligence_review'),
        CronTrigger(hour=2, minute=35),
        id='intelligence_review',
        name='赛后情报复盘归因',
        replace_existing=True
    )

    # 2:50 学习底座补漏 + 相似历史案例重建
    _scheduler.add_job(
        lambda: _run_learning_refresh('scheduler_nightly_learning_refresh', limit=0),
        CronTrigger(hour=2, minute=50),
        id='learning_refresh',
        name='学习底座补漏与相似案例重建',
        replace_existing=True
    )

    # 7:10 生成今日比赛情报包，并采集本地数据 + 天气/新闻
    _scheduler.add_job(
        lambda: _run_intelligence(0, True, 'scheduler_morning_intelligence'),
        CronTrigger(hour=7, minute=10),
        id='intelligence_morning',
        name='今日比赛情报生成',
        replace_existing=True
    )

    # 12:20/18:20/22:20 刷新今日天气和新闻
    _scheduler.add_job(
        lambda: _run_intelligence(0, True, 'scheduler_refresh_intelligence'),
        CronTrigger(hour='12,18,22', minute=20),
        id='intelligence_refresh',
        name='今日情报滚动刷新',
        replace_existing=True
    )

    # 24小时小批量缺口补齐：伤停、新闻、预计阵容、天气，以及可重算的内置证据
    _scheduler.add_job(
        lambda: _run_intelligence_gap_fill(
            -1,
            2,
            network=True,
            force=False,
            limit=8,
            trigger_source='scheduler_intelligence_gap_fill',
        ),
        IntervalTrigger(minutes=45),
        id='intelligence_gap_fill',
        name='情报缺口优先级补齐',
        replace_existing=True,
        max_instances=1,
        coalesce=True,
        misfire_grace_time=300,
        next_run_time=datetime.now() + timedelta(minutes=6),
    )

    # 23:30 预生成明天比赛的本地情报包，外部天气新闻次日再刷新
    _scheduler.add_job(
        lambda: _run_intelligence(1, False, 'scheduler_tomorrow_prefetch'),
        CronTrigger(hour=23, minute=30),
        id='intelligence_tomorrow_prefetch',
        name='明日比赛情报预生成',
        replace_existing=True
    )

    # 24小时滚动采集：今天/明天/昨天的小批量赛程、赔率、赛果、分析、情报刷新
    _scheduler.add_job(
        _run_rolling_collection,
        IntervalTrigger(minutes=15),
        id='rolling_collection',
        name='24小时当前窗口滚动采集',
        replace_existing=True,
        max_instances=1,
        coalesce=True,
        misfire_grace_time=300,
        next_run_time=datetime.now() + timedelta(seconds=30),
    )

    # 历史倒序补齐：每次只处理一个日期，避免长时间大批量采集卡住服务
    _scheduler.add_job(
        _run_historical_backfill,
        IntervalTrigger(minutes=60),
        id='historical_backfill',
        name='历史比赛倒序补齐',
        replace_existing=True,
        max_instances=1,
        coalesce=True,
        misfire_grace_time=600,
        next_run_time=datetime.now() + timedelta(minutes=3),
    )

    _scheduler.add_job(
        _run_parallel_automation_center,
        IntervalTrigger(minutes=30),
        id='automation_center',
        name='并发任务中控',
        replace_existing=True,
        max_instances=1,
        coalesce=True,
        misfire_grace_time=300,
        next_run_time=datetime.now() + timedelta(minutes=2),
    )

    _scheduler.start()
    logger.info('Daily scheduler started with cycle, intelligence, rolling collection and backfill jobs')


@app.on_event("startup")
async def _on_startup():
    _start_daily_scheduler()


@app.on_event("shutdown")
async def _on_shutdown():
    global _scheduler
    if _scheduler:
        _scheduler.shutdown(wait=False)
        logger.info('Daily cycle scheduler stopped')


def _systemd_show(unit_name: str) -> dict:
    """Return systemd unit properties when running on Linux."""
    if os.name == "nt":
        return {}
    try:
        result = subprocess.run(
            ["systemctl", "show", unit_name],
            capture_output=True,
            text=True,
            timeout=2,
            check=False,
        )
    except Exception:
        return {}
    if result.returncode != 0:
        return {}
    values = {}
    for line in (result.stdout or "").splitlines():
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key] = value
    return values


def _systemd_timer_next_run(unit_name: str) -> str | None:
    if os.name == "nt":
        return None
    try:
        result = subprocess.run(
            ["systemctl", "list-timers", "--all", unit_name, "--no-legend", "--no-pager"],
            capture_output=True,
            text=True,
            timeout=2,
            check=False,
        )
    except Exception:
        return None
    if result.returncode != 0:
        return None
    line = (result.stdout or "").strip().splitlines()
    if not line:
        return None
    parts = line[0].split()
    if not parts or parts[0] == "-":
        return None
    return " ".join(parts[:4]) if len(parts) >= 4 else parts[0]


def _external_systemd_timer_status(timer_unit: str, service_unit: str, name: str) -> dict | None:
    """Expose an external systemd timer to the frontend scheduler panel."""
    timer = _systemd_show(timer_unit)
    if not timer:
        return None
    service = _systemd_show(service_unit)
    active = timer.get("ActiveState") == "active"
    service_active = service.get("ActiveState") in {"active", "activating"}
    next_run = timer.get("NextElapseUSecRealtime") or _systemd_timer_next_run(timer_unit)
    return {
        "id": timer_unit,
        "name": name,
        "running": active,
        "active": active,
        "service_active": service_active,
        "state": timer.get("ActiveState") or "unknown",
        "sub_state": timer.get("SubState") or "",
        "next_run": next_run,
        "last_trigger": timer.get("LastTriggerUSec") or None,
        "service_state": service.get("ActiveState") or "",
        "service_sub_state": service.get("SubState") or "",
        "service_result": service.get("Result") or "",
        "exec_main_status": service.get("ExecMainStatus") or "",
    }


def _external_automation_timer_status() -> dict | None:
    return _external_systemd_timer_status(
        "football-automation-tick.timer",
        "football-automation-tick.service",
        "分段自动化中控",
    )


def _external_learning_timer_status() -> dict | None:
    return _external_systemd_timer_status(
        "football-learning-refresh.timer",
        "football-learning-refresh.service",
        "夜间重学习",
    )


@app.get("/api/scheduler/status")
async def scheduler_status():
    """查看日循环调度状态"""
    if not _scheduler:
        external_timer = _external_automation_timer_status()
        learning_timer = _external_learning_timer_status()
        external_timers = [item for item in (external_timer, learning_timer) if item]
        if external_timer and external_timer.get("active"):
            jobs = [
                {
                    "id": "automation_center",
                    "name": external_timer.get("name") or "分段自动化中控",
                    "next_run": external_timer.get("next_run"),
                },
                {
                    "id": "external_automation_tick",
                    "name": external_timer.get("name") or "分段自动化中控",
                    "next_run": external_timer.get("next_run"),
                },
            ]
            if learning_timer:
                jobs.append(
                    {
                        "id": "learning_refresh",
                        "name": learning_timer.get("name") or "夜间重学习",
                        "next_run": learning_timer.get("next_run"),
                    }
                )
            return {
                "running": True,
                "active": True,
                "paused": False,
                "state": "external_timer",
                "state_label": "分段自动化中",
                "jobs": jobs,
                "auto_loop": {"collection_runs": [], "intelligence_runs": [], "revalidation_pending": 0},
                "external_automation": external_timer,
                "external_learning": learning_timer,
                "external_timers": external_timers,
            }
        return {
            "running": False,
            "active": False,
            "paused": False,
            "state": "stopped",
            "state_label": "未运行",
            "external_automation": external_timer,
            "external_learning": learning_timer,
            "external_timers": external_timers,
        }
    state_code = getattr(_scheduler, "state", None)
    paused = state_code == 2
    active = not paused
    jobs = []
    for job in _scheduler.get_jobs():
        jobs.append({
            "id": job.id,
            "name": job.name,
            "next_run": str(job.next_run_time) if job.next_run_time else None,
        })

    auto_loop = {"collection_runs": [], "intelligence_runs": [], "revalidation_pending": 0}
    try:
        conn = sqlite3.connect(DATABASE_PATH, timeout=10)
        conn.row_factory = sqlite3.Row

        def _has_table(table_name: str) -> bool:
            return conn.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name = ?",
                (table_name,),
            ).fetchone() is not None

        def _loads_summary(value):
            if not value:
                return {}
            try:
                return json.loads(value)
            except Exception:
                return {"raw": value}

        def _pick_summary_fields(value, keys):
            if not isinstance(value, dict):
                return {}
            return {key: value.get(key) for key in keys if key in value}

        def _compact_gap_steps(steps):
            if not isinstance(steps, dict):
                return {}
            step_keys = {
                "event_details": [
                    "event_api_fetched", "lottery_results_inserted", "lottery_results_updated",
                    "revalidation_queued", "candidates", "candidates_deferred", "skipped", "reason", "error",
                ],
                "ou_lines": [
                    "updated", "candidates", "from_oddsfe_merged", "live_fetched",
                    "skipped", "reason", "error",
                ],
                "analysis": ["analyzed", "candidates", "planned_candidates", "skipped", "reason", "error"],
                "intelligence": ["processed", "planned_candidates", "skipped", "reason", "error"],
                "validation": ["validated", "correct", "accuracy", "skipped", "reason", "error"],
                "learning": ["reviews", "snapshots", "skipped", "reason", "error"],
            }
            compact = {}
            for key, fields in step_keys.items():
                if key in steps:
                    compact[key] = _pick_summary_fields(steps.get(key), fields)
            return compact

        def _compact_oddsfe_summary(value):
            fields = [
                "event_api_fetched", "event_cache_used", "lottery_rows_seen",
                "lottery_results_inserted", "lottery_results_updated", "lottery_results_unchanged",
                "revalidation_queued", "candidates", "candidates_deferred", "remaining_uncached_events",
                "skipped", "reason", "error",
            ]
            if isinstance(value, dict) and isinstance(value.get("batches"), list):
                return {"batches": [_pick_summary_fields(item, fields) for item in value.get("batches", [])[:2]]}
            return _pick_summary_fields(value, fields)

        def _compact_intelligence_gap(value):
            fields = ["processed", "planned_candidates", "candidates", "updated", "skipped", "reason", "error"]
            if isinstance(value, dict) and isinstance(value.get("summary"), dict):
                return {"summary": _pick_summary_fields(value.get("summary"), fields)}
            return _pick_summary_fields(value, fields)

        def _compact_intelligence_run_summary(summary):
            if not isinstance(summary, dict):
                return {}
            compact = _pick_summary_fields(summary, ["processed", "planned_candidates", "failed", "skipped", "error"])
            generated = summary.get("generated")
            if isinstance(generated, dict):
                compact["generated"] = _pick_summary_fields(generated, ["created", "updated", "skipped"])
                jobs = generated.get("jobs")
                if isinstance(jobs, list):
                    compact["generated"]["jobs_count"] = len(jobs)
            results = summary.get("results")
            if isinstance(results, list):
                compact["results_count"] = len(results)
                compact["results"] = [
                    _pick_summary_fields(
                        item,
                        [
                            "job_id", "match", "coverage", "completeness", "strict_coverage",
                            "average_confidence", "required_missing", "status",
                        ],
                    )
                    for item in results[:8]
                    if isinstance(item, dict)
                ]
            return compact

        def _compact_automation_payload(payload):
            if not isinstance(payload, dict):
                return {}
            compact = _pick_summary_fields(
                payload,
                [
                    "task", "success", "candidates", "event_api_fetched", "lottery_results_inserted",
                    "lottery_results_updated", "updated", "from_oddsfe_merged", "live_fetched",
                    "processed", "analyzed", "validated", "correct", "accuracy", "failed",
                    "changes", "changed_reports", "prediction_rows", "delta_correct", "full_delta_correct",
                    "by_reason", "improved", "regressed", "metadata_only", "accepted", "fact_table",
                    "saved", "saved_profiles", "saved_audits", "targets", "eligible", "scored_matches",
                    "saved_patterns", "changed_candidates", "current_correct", "current_accuracy",
                    "profile_correct", "changed_improved", "changed_regressed", "half_axis_errors",
                    "full_axis_errors", "path_flips", "matches", "plays", "wrong",
                    "validation_consistency_ok", "prediction_consistency_ok", "hard_prediction_issues",
                    "prediction_parse_errors", "post_prediction_consistency_ok", "post_prediction_hard_issues",
                    "post_prediction_parse_errors", "skipped", "reason", "error",
                ],
            )
            for key in ("prediction_consistency", "post_prediction_consistency", "prediction_consistency_initial", "post_prediction_consistency_initial"):
                value = payload.get(key)
                if isinstance(value, dict):
                    compact[key] = _pick_summary_fields(
                        value,
                        [
                            "date_from", "date_to", "league", "reports_checked",
                            "consistency_adjusted_reports", "hard_issues", "parse_errors",
                            "issue_counts", "stale_filter_supported",
                        ],
                    )
            for key in ("prediction_remediation", "post_prediction_remediation"):
                value = payload.get(key)
                if isinstance(value, dict):
                    compact[key] = _pick_summary_fields(
                        value,
                        [
                            "attempted", "reason", "issue_matches", "limited", "targets",
                            "analyzed", "failed", "analyzed_ids", "failed_examples",
                        ],
                    )
            dry_run = payload.get("dry_run") if isinstance(payload.get("dry_run"), dict) else None
            if dry_run:
                compact["dry_run"] = _pick_summary_fields(
                    dry_run,
                    ["changes", "improved", "regressed", "delta_correct", "full_delta_correct"],
                )
            for key in ("top_error_categories", "top_categories", "top_tags", "collection_actions", "model_actions", "drivers", "risk_tags"):
                if isinstance(payload.get(key), list):
                    compact[key] = payload.get(key)[:5]
            return compact

        def _compact_automation_task_item(item):
            if not isinstance(item, dict):
                return {}
            task = item.get("task") if isinstance(item.get("task"), dict) else {}
            payload = item.get("payload") if isinstance(item.get("payload"), dict) else {}
            return {
                **_pick_summary_fields(item, [
                    "success", "skipped", "reason", "exit_code", "elapsed_seconds",
                    "timeout", "error", "source_run_id", "source_task_key", "source_task_index",
                ]),
                "task": _pick_summary_fields(task, ["kind", "date_from", "date_to", "wave", "reason"]),
                "payload": _compact_automation_payload(payload),
            }

        def _compact_run_summary(run_type, summary):
            if not isinstance(summary, dict):
                return {}

            compact = _pick_summary_fields(
                summary,
                ["date", "date_from", "date_to", "start_date", "end_date", "match_date", "target", "action_counts", "action_source"],
            )
            if isinstance(summary.get("range"), dict):
                compact["range"] = _pick_summary_fields(summary.get("range"), ["start_date", "end_date"])

            if run_type == "auto_gap_fill":
                compact["steps"] = _compact_gap_steps(summary.get("steps"))
                return compact

            if run_type == "automation_center":
                compact.update(_pick_summary_fields(
                    summary,
                    [
                        "mode", "league", "dates", "task_count", "by_wave", "by_kind",
                        "workers", "failed_tasks", "skipped", "reason", "error", "stage", "progress",
                        "failure_rescue",
                    ],
                ))
                waves = summary.get("waves")
                if isinstance(waves, list):
                    compact["waves"] = [
                        _pick_summary_fields(item, ["wave", "task_count", "failed", "elapsed_seconds"])
                        for item in waves[:8]
                        if isinstance(item, dict)
                    ]
                tasks = summary.get("tasks")
                if isinstance(tasks, list):
                    compact["tasks"] = [
                        _compact_automation_task_item(item)
                        for item in tasks[:32]
                        if isinstance(item, dict)
                    ]
                gate = summary.get("model_gate")
                if isinstance(gate, dict):
                    comparison = gate.get("comparison") if isinstance(gate.get("comparison"), dict) else {}
                    consistency = gate.get("consistency") if isinstance(gate.get("consistency"), dict) else {}
                    detail = gate.get("decision_detail") if isinstance(gate.get("decision_detail"), dict) else {}
                    rollback = summary.get("model_gate_rollback") if isinstance(summary.get("model_gate_rollback"), dict) else {}
                    compact["model_gate"] = {
                        "decision": gate.get("decision"),
                        "success": gate.get("success"),
                        "overall_delta_pp": comparison.get("overall_delta_pp"),
                        "hard_issues": consistency.get("hard_issues"),
                        "reasons": (detail.get("reasons") or [])[:3],
                        "warnings": (detail.get("warnings") or [])[:3],
                        "rollback_success": rollback.get("success") if rollback else None,
                        "rollback_failed": bool(summary.get("model_gate_rollback_failed")),
                    }
                return compact

            if run_type == "automation_retry":
                compact.update(_pick_summary_fields(
                    summary,
                    ["source_run_id", "task_count", "workers", "failed_tasks", "success", "stage", "progress", "error"],
                ))
                tasks = summary.get("tasks")
                if isinstance(tasks, list):
                    compact["tasks"] = [
                        _compact_automation_task_item(item)
                        for item in tasks[:32]
                        if isinstance(item, dict)
                    ]
                return compact

            if str(run_type or "").startswith("automation_"):
                task = summary.get("task") if isinstance(summary.get("task"), dict) else {}
                payload = summary.get("payload") if isinstance(summary.get("payload"), dict) else {}
                compact["task"] = _pick_summary_fields(task, ["kind", "date_from", "date_to", "wave", "reason"])
                compact.update(_pick_summary_fields(summary, ["success", "exit_code", "elapsed_seconds", "timeout", "error"]))
                compact["payload"] = _compact_automation_payload(payload)
                return compact

            if run_type in {"auto_loop_cycle", "historical_backfill"}:
                compact["oddsfe"] = _compact_oddsfe_summary(summary.get("oddsfe"))
                compact["oddsfe_ou"] = _pick_summary_fields(
                    summary.get("oddsfe_ou"),
                    [
                        "updated", "candidates", "from_oddsfe_merged", "live_fetched",
                        "skipped", "reason", "error",
                    ],
                )
                compact["analysis"] = _pick_summary_fields(
                    summary.get("analysis"),
                    ["analyzed", "candidates", "planned_candidates", "skipped", "reason", "error"],
                )
                compact["finished_intelligence_backfill"] = _compact_intelligence_gap(
                    summary.get("finished_intelligence_backfill")
                )
                compact["intelligence_gap_fill"] = _compact_intelligence_gap(summary.get("intelligence_gap_fill"))
                compact["post_intelligence_analysis"] = _pick_summary_fields(
                    summary.get("post_intelligence_analysis"),
                    ["analyzed", "candidates", "planned_candidates", "skipped", "reason", "error"],
                )
                compact["validation"] = _pick_summary_fields(
                    summary.get("validation"),
                    ["validated", "correct", "accuracy", "skipped", "reason", "error"],
                )
                compact["queued_revalidation"] = _pick_summary_fields(
                    summary.get("queued_revalidation"), ["processed", "queued", "skipped", "reason", "error"]
                )
                compact["similar_cases"] = _pick_summary_fields(
                    summary.get("similar_cases"),
                    ["cases_written", "targets_with_cases", "skipped", "reason", "error"],
                )
                return compact

            return {
                **compact,
                **_pick_summary_fields(
                    summary,
                    [
                        "event_api_fetched", "lottery_results_inserted", "lottery_results_updated",
                        "updated", "candidates", "reanalyzed", "from_oddsfe_merged", "live_fetched",
                        "validated", "accuracy", "skipped", "reason", "error",
                    ],
                ),
            }

        def _parse_run_dt(value):
            if not value:
                return None
            text = str(value).replace("T", " ")[:19]
            try:
                return datetime.strptime(text, "%Y-%m-%d %H:%M:%S")
            except ValueError:
                return None

        def _compact_run_row(row):
            item = dict(row)
            summary = _loads_summary(item.pop("summary_json", None))
            item["summary"] = _compact_run_summary(item.get("run_type"), summary)
            if item.get("status") == "running":
                started = _parse_run_dt(item.get("started_at"))
                if started:
                    age_seconds = max(0, int((datetime.utcnow() - started).total_seconds()))
                    stale_thresholds = {
                        "auto_loop_cycle": 90 * 60,
                        "historical_backfill": 90 * 60,
                        "auto_gap_fill": 45 * 60,
                        "automation_center": 60 * 60,
                        "automation_event_details": 30 * 60,
                        "automation_ou_lines": 30 * 60,
                        "automation_intelligence": 30 * 60,
                        "automation_analysis": 30 * 60,
                        "automation_play_consistency_gate": 30 * 60,
                        "automation_bqc_full_axis_gate": 30 * 60,
                        "automation_handicap_margin_gate": 30 * 60,
                        "automation_validation": 30 * 60,
                        "automation_national_ou_gate": 30 * 60,
                        "automation_bqc_half_time_profile": 30 * 60,
                        "automation_bqc_full_time_axis": 30 * 60,
                        "automation_handicap_margin_axis": 30 * 60,
                        "automation_prediction_error_review": 30 * 60,
                        "automation_learning": 45 * 60,
                        "automation_retry": 45 * 60,
                        "oddsfe_event_details": 75 * 60,
                        "oddsfe_ou_lines": 45 * 60,
                        "learning_refresh": 45 * 60,
                    }
                    item["age_seconds"] = age_seconds
                    item["is_stale"] = age_seconds >= stale_thresholds.get(item.get("run_type"), 60 * 60)
            return item

        def _compact_intelligence_run_row(row):
            item = dict(row)
            summary = _loads_summary(item.pop("summary_json", None))
            item["summary"] = _compact_intelligence_run_summary(summary)
            if item.get("status") == "running":
                started = _parse_run_dt(item.get("started_at"))
                if started:
                    age_seconds = max(0, int((datetime.utcnow() - started).total_seconds()))
                    item["age_seconds"] = age_seconds
                    item["is_stale"] = age_seconds >= 45 * 60
            return item

        if _has_table("collection_runs"):
            rows = conn.execute(
                """
                SELECT run_id, trigger_source, run_type, match_date, status,
                       started_at, finished_at, summary_json, error
                FROM collection_runs
                WHERE run_type IN (
                    'auto_loop_cycle', 'historical_backfill', 'auto_gap_fill',
                    'automation_center', 'automation_event_details', 'automation_ou_lines',
                    'automation_intelligence', 'automation_analysis', 'automation_play_consistency_gate', 'automation_bqc_full_axis_gate', 'automation_handicap_margin_gate', 'automation_validation',
                    'automation_national_ou_gate', 'automation_bqc_half_time_profile', 'automation_bqc_full_time_axis', 'automation_handicap_margin_axis', 'automation_prediction_error_review',
                    'automation_learning', 'automation_retry',
                    'oddsfe_event_details', 'oddsfe_ou_lines', 'learning_refresh'
                )
                ORDER BY started_at DESC
                LIMIT 80
                """
            ).fetchall()
            auto_loop["collection_runs"] = [_compact_run_row(row) for row in rows]

        if _has_table("intelligence_runs"):
            rows = conn.execute(
                """
                SELECT run_id, run_date, trigger_source, status, started_at,
                       finished_at, summary_json, error
                FROM intelligence_runs
                ORDER BY started_at DESC
                LIMIT 8
                """
            ).fetchall()
            auto_loop["intelligence_runs"] = [_compact_intelligence_run_row(row) for row in rows]

        if _has_table("lottery_revalidation_queue"):
            row = conn.execute(
                "SELECT COUNT(*) FROM lottery_revalidation_queue WHERE status = 'pending'"
            ).fetchone()
            auto_loop["revalidation_pending"] = int(row[0] or 0)

        conn.close()
    except Exception as e:
        auto_loop["error"] = str(e)

    try:
        from backend.app.lottery.services.automation_control import get_automation_control_state

        automation_control = get_automation_control_state(DATABASE_PATH)
    except Exception as e:
        automation_control = {"enabled": False, "state": "unknown", "error": str(e)}

    return {
        "running": True,
        "active": active,
        "paused": paused,
        "state": "paused" if paused else "active",
        "state_label": "已暂停" if paused else "自动中",
        "jobs": jobs,
        "auto_loop": auto_loop,
        "automation_control": automation_control,
    }


@app.post("/api/scheduler/pause")
async def scheduler_pause():
    """Pause automatic scheduled jobs without stopping the API service."""
    if not _scheduler:
        raise HTTPException(status_code=503, detail="scheduler is not running")
    _scheduler.pause()
    return {"success": True, "state": "paused", "state_label": "已暂停"}


@app.post("/api/scheduler/resume")
async def scheduler_resume():
    """Resume automatic scheduled jobs."""
    if not _scheduler:
        raise HTTPException(status_code=503, detail="scheduler is not running")
    _scheduler.resume()
    return {"success": True, "state": "active", "state_label": "自动中"}


@app.post("/api/scheduler/run/{job_id}")
async def scheduler_run_now(job_id: str):
    """立即触发一个调度任务，不阻塞等待任务完成。"""
    if not _scheduler:
        raise HTTPException(status_code=503, detail="scheduler is not running")
    allowed = {
        "morning_cycle",
        "clv_cycle",
        "validate_cycle",
        "intelligence_review",
        "learning_refresh",
        "intelligence_morning",
        "intelligence_refresh",
        "intelligence_gap_fill",
        "intelligence_tomorrow_prefetch",
        "rolling_collection",
        "historical_backfill",
        "automation_center",
    }
    if job_id not in allowed:
        raise HTTPException(status_code=400, detail=f"unsupported scheduler job: {job_id}")
    job = _scheduler.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"scheduler job not found: {job_id}")
    job.modify(next_run_time=datetime.now())
    return {
        "success": True,
        "job_id": job_id,
        "status": "scheduled_now",
        "next_run": str(job.next_run_time) if job.next_run_time else None,
    }


@app.get("/api/health")
async def system_health():
    """系统健康检查 — 数据量、验证、调度器、数据源"""
    try:
        db_path = str(Path(__file__).parent.parent.parent / "data" / "football_v2.db")
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        health = {}

        # Data counts
        for table in ['lottery_matches', 'lottery_odds', 'lottery_results',
                       'lottery_validation', 'bet_records']:
            c = cursor.execute(f'SELECT COUNT(*) FROM {table}')
            health[table] = c.fetchone()[0]

        # Validation accuracy
        c = cursor.execute('SELECT COUNT(*), SUM(is_correct) FROM lottery_validation')
        r = c.fetchone()
        health['validation_accuracy'] = round(r[1]/r[0]*100, 1) if r[0] and r[1] else 0

        # Bet ROI
        c = cursor.execute('SELECT COUNT(*), SUM(profit) FROM bet_records WHERE result != "pending"')
        r = c.fetchone()
        health['bet_profit'] = round(r[1] or 0, 0)
        health['bet_settled'] = r[0]

        # Upcoming matches
        c = cursor.execute("SELECT COUNT(*) FROM lottery_matches WHERE match_date >= date('now')")
        health['upcoming_matches'] = c.fetchone()[0]

        # Data sources
        c = cursor.execute('SELECT source_name, status FROM data_source_health')
        health['sources'] = {r[0]: r[1] for r in c.fetchall()}

        # Scheduler
        health['scheduler_running'] = _scheduler is not None

        # Cycle state
        c = cursor.execute('SELECT date, current_node, status FROM daily_cycle_state ORDER BY date DESC LIMIT 1')
        r = c.fetchone()
        health['cycle_date'] = r[0] if r else None
        health['cycle_node'] = r[1] if r else None
        health['cycle_status'] = r[2] if r else None

        # Model weights
        c = cursor.execute('SELECT version, is_active FROM model_weights WHERE is_active=1')
        r = c.fetchone()
        health['active_model'] = r[0] if r else None

        conn.close()
        return health
    except Exception as e:
        return {"error": str(e)}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=18888)
