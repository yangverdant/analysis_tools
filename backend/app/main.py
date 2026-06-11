"""
足球数据分析 API - 主入口

已拆分的模块:
- routers/: 业务路由 (matches, teams, leagues, cups, sync, rankings)
- analytics/: 分析模块 (Elo, xG, 预测等)
- pipeline/: 数据流水线 (分拣/采集/清洗/导入)
- langchain/: AI 分析 (暂时禁用)
- data_sources/: 数据源管理
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import sqlite3
import os
import sys

from backend.app.core.time_utils import today_beijing, tomorrow_beijing
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

# 数据库路径 — 优先使用环境变量(云部署), 否则用相对路径(本地开发)
DATABASE_PATH = os.environ.get('DB_PATH',
    os.path.join(os.path.dirname(__file__), '..', '..', 'data', 'football_v2.db'))
LINKAGE_PATH = os.environ.get('LINKAGE_PATH',
    os.path.join(os.path.dirname(__file__), '..', '..', 'data', 'linkage'))

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
    rankings_router
)
app.include_router(matches_router)
app.include_router(teams_router)
app.include_router(leagues_router)
app.include_router(cups_router)
app.include_router(sync_router)
app.include_router(rankings_router)

from app.pipeline import pipeline_router
app.include_router(pipeline_router)

# 体彩分析路由 (新增)
from app.lottery.routers.lottery import router as lottery_router
app.include_router(lottery_router)

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

    valid_modes = ['perceive', 'collect', 'analyze', 'push', 'clv', 'validate', 'learn', 'morning', 'full']
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

        # 北京时间窗口: today + tomorrow凌晨
        from backend.app.core.time_utils import today_beijing, tomorrow_beijing
        today = date or today_beijing()
        tomorrow = tomorrow_beijing()

        cursor.execute("""
            SELECT lar.lottery_match_id, lar.report_data,
                   lm.home_team_cn, lm.away_team_cn, lm.match_date, lm.match_time,
                   lm.league_name_cn, lm.home_team_id, lm.away_team_id
            FROM lottery_analysis_reports lar
            JOIN lottery_matches lm ON lar.lottery_match_id = lm.lottery_match_id
            WHERE (
                lm.match_date = ?
                OR (lm.match_date = ? AND substr(lm.match_time, 1, 2) < '12')
            )
            AND lar.report_type = 'prediction'
            ORDER BY lm.match_date, lm.match_time
        """, (today, tomorrow))

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

        # 从预测报告中找最高置信度的推荐(北京时间窗口)
        from backend.app.core.time_utils import today_beijing, tomorrow_beijing
        _today = today_beijing()
        _tomorrow = tomorrow_beijing()
        cursor.execute("""
            SELECT lar.report_data, lm.home_team_cn, lm.away_team_cn,
                   lm.league_name_cn, lm.match_date
            FROM lottery_analysis_reports lar
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
        for report_type in ['prediction', 'full']:
            cursor = conn.execute("""
                SELECT report_data, report_type, created_at
                FROM lottery_analysis_reports
                WHERE lottery_match_id = ? AND report_type = ?
                ORDER BY created_at DESC LIMIT 1
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
    try:
        from apscheduler.schedulers.background import BackgroundScheduler
        from apscheduler.triggers.cron import CronTrigger
    except ImportError:
        logger.warning("APScheduler not installed, daily cycle scheduler disabled")
        return

    db_path = str(Path(__file__).parent.parent.parent / "data" / "football_v2.db")

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

    _scheduler.start()
    logger.info('Daily cycle scheduler started (6:05 morning, 14:05 clv, 2:05 validate)')


@app.on_event("startup")
async def _on_startup():
    _start_daily_scheduler()


@app.on_event("shutdown")
async def _on_shutdown():
    global _scheduler
    if _scheduler:
        _scheduler.shutdown()
        logger.info('Daily cycle scheduler stopped')


@app.get("/api/scheduler/status")
async def scheduler_status():
    """查看日循环调度状态"""
    if not _scheduler:
        return {"running": False}
    jobs = []
    for job in _scheduler.get_jobs():
        jobs.append({
            "id": job.id,
            "name": job.name,
            "next_run": str(job.next_run_time) if job.next_run_time else None,
        })
    return {"running": True, "jobs": jobs}


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
