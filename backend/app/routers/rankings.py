"""
排名相关路由
"""

from fastapi import APIRouter
import sqlite3
import os
import json

router = APIRouter(prefix="/api/v1/rankings", tags=["Rankings"])

DATABASE_PATH = os.path.join(os.path.dirname(__file__), '..', '..', '..', 'data', 'football_v2.db')
LINKAGE_PATH = os.path.join(os.path.dirname(__file__), '..', '..', '..', 'data', 'linkage')

# 加载中文名称映射
COUNTRY_CN = {}
def load_chinese_names():
    global COUNTRY_CN
    country_file = os.path.join(LINKAGE_PATH, 'country_chinese_names.json')
    if os.path.exists(country_file):
        with open(country_file, 'r', encoding='utf-8') as f:
            COUNTRY_CN = json.load(f)

load_chinese_names()

def get_db():
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def get_chinese_country_name(name):
    return COUNTRY_CN.get(name, name)


@router.get("/fifa/national")
async def get_fifa_national_rankings(limit: int = 50):
    """获取FIFA国家队排名"""
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT r.*, t.name_en as country, t.name_cn as country_cn
        FROM fifa_rankings r
        LEFT JOIN teams t ON r.team_id = t.team_id
        WHERE t.team_type = 'national'
        ORDER BY r.rank
        LIMIT ?
    """, (limit,))
    rankings = [dict(row) for row in cursor.fetchall()]

    # 添加中文名称
    for rank in rankings:
        if not rank.get('country_cn'):
            rank['country_cn'] = get_chinese_country_name(rank.get('country', ''))

    conn.close()
    return {"data": rankings}


@router.get("/fifa/club")
async def get_fifa_club_rankings(limit: int = 50):
    """获取FIFA俱乐部排名"""
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT r.*, t.name_en as club_name, t.name_cn as club_name_cn
        FROM fifa_rankings r
        LEFT JOIN teams t ON r.team_id = t.team_id
        WHERE t.team_type = 'club'
        ORDER BY r.rank
        LIMIT ?
    """, (limit,))
    rankings = [dict(row) for row in cursor.fetchall()]

    conn.close()
    return {"data": rankings}