"""用户设置与收藏路由"""

from fastapi import APIRouter
import sqlite3
import os
import json

router = APIRouter(prefix="/api/v1/user", tags=["User"])

DATABASE_PATH = os.environ.get('DB_PATH',
    os.path.join(os.path.dirname(__file__), '..', '..', '..', 'data', 'football_v2.db'))

# 加载中文名称映射
LINKAGE_PATH = os.path.join(os.path.dirname(__file__), '..', '..', '..', 'data', 'linkage')

def _load_cn_names():
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

LEAGUE_CN, COUNTRY_CN = _load_cn_names()


def get_db():
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _ensure_tables(conn):
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS user_settings (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS user_favorites (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            item_type TEXT NOT NULL CHECK(item_type IN ('team','league','match')),
            item_id TEXT NOT NULL,
            item_name TEXT DEFAULT '',
            extra_json TEXT DEFAULT '{}',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(item_type, item_id)
        );
    """)
    conn.commit()


# ==================== 设置 ====================

@router.get("/settings")
async def get_settings():
    conn = get_db()
    _ensure_tables(conn)
    cursor = conn.cursor()
    cursor.execute("SELECT key, value FROM user_settings")
    rows = cursor.fetchall()
    settings = {row['key']: json.loads(row['value']) for row in rows}
    conn.close()
    return {"settings": settings}


@router.post("/settings")
async def save_settings(data: dict):
    conn = get_db()
    _ensure_tables(conn)
    cursor = conn.cursor()
    settings = data.get("settings", {})
    for key, value in settings.items():
        cursor.execute(
            "INSERT OR REPLACE INTO user_settings (key, value, updated_at) VALUES (?, ?, datetime('now'))",
            (key, json.dumps(value, ensure_ascii=False))
        )
    conn.commit()
    conn.close()
    return {"success": True, "saved": len(settings)}


# ==================== 收藏 ====================

@router.get("/favorites")
async def get_favorites(item_type: str = None):
    conn = get_db()
    _ensure_tables(conn)
    cursor = conn.cursor()
    if item_type:
        cursor.execute(
            "SELECT id, item_type, item_id, item_name, extra_json, created_at FROM user_favorites WHERE item_type = ? ORDER BY created_at DESC",
            (item_type,)
        )
    else:
        cursor.execute(
            "SELECT id, item_type, item_id, item_name, extra_json, created_at FROM user_favorites ORDER BY created_at DESC"
        )
    rows = cursor.fetchall()
    favorites = []
    for row in rows:
        item = {
            'id': row['id'],
            'item_type': row['item_type'],
            'item_id': row['item_id'],
            'item_name': row['item_name'],
            'created_at': row['created_at'],
        }
        try:
            item['extra'] = json.loads(row['extra_json'])
        except:
            item['extra'] = {}
        favorites.append(item)
    conn.close()
    return {"favorites": favorites}


@router.post("/favorites")
async def add_favorite(data: dict):
    item_type = data.get("item_type")
    item_id = str(data.get("item_id", ""))
    item_name = data.get("item_name", "")
    extra = data.get("extra", {})

    if not item_type or not item_id:
        return {"success": False, "error": "item_type and item_id required"}

    conn = get_db()
    _ensure_tables(conn)
    cursor = conn.cursor()
    try:
        cursor.execute(
            "INSERT OR IGNORE INTO user_favorites (item_type, item_id, item_name, extra_json) VALUES (?, ?, ?, ?)",
            (item_type, item_id, item_name, json.dumps(extra, ensure_ascii=False))
        )
        conn.commit()
        conn.close()
        return {"success": True}
    except Exception as e:
        conn.close()
        return {"success": False, "error": str(e)}


@router.delete("/favorites/{item_type}/{item_id}")
async def remove_favorite(item_type: str, item_id: str):
    conn = get_db()
    _ensure_tables(conn)
    cursor = conn.cursor()
    cursor.execute(
        "DELETE FROM user_favorites WHERE item_type = ? AND item_id = ?",
        (item_type, item_id)
    )
    conn.commit()
    deleted = cursor.rowcount
    conn.close()
    return {"success": True, "deleted": deleted}


# ==================== 联赛白名单管控 ====================

@router.get("/leagues-catalog")
async def get_leagues_catalog():
    """
    获取所有联赛目录（用于收藏/白名单管理）
    返回按国家分组的联赛列表，含比赛数量和收藏状态
    """
    conn = get_db()
    _ensure_tables(conn)
    cursor = conn.cursor()

    # 获取所有有比赛的联赛
    cursor.execute("""
        SELECT l.league_id, l.name_en, l.name_cn, l.country, l.country_cn,
               COUNT(m.match_id) as total_matches,
               SUM(CASE WHEN m.match_date >= date('now', '-30 days') THEN 1 ELSE 0 END) as recent_matches,
               SUM(CASE WHEN m.match_date >= date('now') THEN 1 ELSE 0 END) as upcoming_matches
        FROM leagues l
        JOIN matches m ON l.league_id = m.league_id
        WHERE l.name_en NOT IN ('League 98', 'League 99', 'League 100',
            'League 4404', 'League 4415', 'League 4724', 'League 4725', 'League 4804')
        GROUP BY l.league_id
        HAVING total_matches >= 50
        ORDER BY l.country, l.name_en
    """)
    leagues = []
    for row in cursor.fetchall():
        country = row[3] or ''
        country_cn = row[4] or COUNTRY_CN.get(country, country)
        name_en = row[1] or ''
        name_cn = row[2] or LEAGUE_CN.get(name_en, '')
        leagues.append({
            'league_id': row[0],
            'name_en': name_en,
            'name_cn': name_cn,
            'country': country,
            'country_cn': country_cn,
            'total_matches': row[5],
            'recent_matches': row[6],
            'upcoming_matches': row[7],
        })

    # 获取已收藏的联赛ID
    cursor.execute("SELECT item_id FROM user_favorites WHERE item_type = 'league'")
    fav_ids = {str(row[0]) for row in cursor.fetchall()}
    conn.close()

    # 按国家分组
    groups = {}
    for lg in leagues:
        country = lg['country'] or '其他'
        country_cn = lg['country_cn'] or '其他'
        if country not in groups:
            groups[country] = {'country': country, 'country_cn': country_cn, 'leagues': []}
        lg['is_favorite'] = str(lg['league_id']) in fav_ids
        groups[country]['leagues'].append(lg)

    # 排序：有即将比赛的排前面
    result = sorted(groups.values(), key=lambda g: max((l['upcoming_matches'] for l in g['leagues']), default=0), reverse=True)

    return {"groups": result, "total_leagues": len(leagues), "favorites_count": len(fav_ids)}


@router.get("/visible-leagues")
async def get_visible_leagues():
    """
    获取当前可见的联赛ID列表（白名单机制）
    - 如果有收藏联赛 → 只返回收藏的联赛
    - 如果没有收藏任何联赛 → 返回全部（首次使用默认显示所有）
    """
    conn = get_db()
    _ensure_tables(conn)
    cursor = conn.cursor()

    cursor.execute("SELECT item_id FROM user_favorites WHERE item_type = 'league'")
    fav_ids = [row[0] for row in cursor.fetchall()]
    conn.close()

    if fav_ids:
        return {"visible_league_ids": [int(x) for x in fav_ids], "mode": "whitelist", "count": len(fav_ids)}
    else:
        return {"visible_league_ids": [], "mode": "all", "count": 0}
