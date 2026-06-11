"""
补充清水鼓动和大阪钢巴的历史比赛数据

从API Football获取:
1. 历史比赛列表
2. 比赛详细统计（射门、控球等）
3. 进球事件详情
"""

import asyncio
import aiohttp
import sqlite3
import json
from datetime import datetime, timedelta
import time

# API配置
API_URL = "https://apiv3.apifootball.com"
API_KEY = "bf82d62ee5412d32a95362699389583fdbefa113f4efb371b87b585f12d64443"

# 数据库路径
DB_PATH = "data/football_v2.db"

# 球队ID映射
TEAMS = {
    821: {"name": "Shimizu S-Pulse", "api_name": "Shimizu S-Pulse"},
    374: {"name": "Gamba Osaka", "api_name": "Gamba Osaka"}
}

# J1联赛ID
J1_LEAGUE_ID = 98


async def fetch_matches(session, from_date, to_date, league_id=None):
    """获取日期范围内的比赛"""
    params = {
        "action": "get_events",
        "APIkey": API_KEY,
        "from": from_date,
        "to": to_date
    }
    if league_id:
        params["league_id"] = league_id

    url = f"{API_URL}/"

    async with session.get(url, params=params) as response:
        if response.status == 200:
            data = await response.json()
            return data if isinstance(data, list) else []
        else:
            print(f"API error: {response.status}")
            return []


async def fetch_match_details(session, match_id):
    """获取单场比赛详情"""
    params = {
        "action": "get_events",
        "APIkey": API_KEY,
        "match_id": match_id
    }

    url = f"{API_URL}/"

    async with session.get(url, params=params) as response:
        if response.status == 200:
            data = await response.json()
            if isinstance(data, list) and len(data) > 0:
                return data[0]
        return None


def parse_team_name(team_name):
    """解析球队名称，返回team_id"""
    name_lower = team_name.lower() if team_name else ""

    if "shimizu" in name_lower:
        return 821
    elif "gamba" in name_lower:
        return 374

    return None


def parse_statistics(match_data):
    """解析比赛统计数据"""
    stats = match_data.get("statistics", [])
    if not stats:
        return None

    result = {}
    for stat in stats:
        stat_type = stat.get("type")
        home_val = stat.get("home")
        away_val = stat.get("away")

        if stat_type:
            result[f"home_{stat_type.lower().replace(' ', '_')}"] = home_val
            result[f"away_{stat_type.lower().replace(' ', '_')}"] = away_val

    return result


def parse_goalscorer(goalscorer_data, home_team_id, away_team_id):
    """解析进球数据"""
    if not goalscorer_data:
        return []

    goals = []
    for goal in goalscorer_data:
        goals.append({
            "minute": goal.get("time"),
            "score": goal.get("score"),
            "player": goal.get("scorer"),
            "team": home_team_id if goal.get("home_scorer") else away_team_id,
            "assist": goal.get("home_assist") or goal.get("away_assist")
        })

    return goals


def update_match_in_db(conn, match_id, stats, goals):
    """更新比赛统计数据"""
    cursor = conn.cursor()

    # 更新统计字段
    if stats:
        update_fields = []
        update_values = []

        # 映射统计字段
        field_mapping = {
            "home_shots_total": "home_shots",
            "away_shots_total": "away_shots",
            "home_shots_on_target": "home_shots_on_target",
            "away_shots_on_target": "away_shots_on_target",
            "home_ball_possession": "home_possession",
            "away_ball_possession": "away_possession",
            "home_corner_kicks": "home_corners",
            "away_corner_kicks": "away_corners",
            "home_fouls": "home_fouls",
            "away_fouls": "away_fouls",
            "home_yellow_cards": "home_yellow",
            "away_yellow_cards": "away_yellow",
            "home_red_cards": "home_red",
            "away_red_cards": "away_red"
        }

        for api_field, db_field in field_mapping.items():
            if api_field in stats and stats[api_field] is not None:
                val = stats[api_field]
                # 处理控球率格式 (如 "55%")
                if "possession" in db_field and isinstance(val, str):
                    val = val.replace("%", "").strip()
                    try:
                        val = float(val)
                    except:
                        continue

                update_fields.append(f"{db_field} = ?")
                update_values.append(val)

        if update_fields:
            update_values.append(match_id)
            sql = f"UPDATE matches SET {', '.join(update_fields)} WHERE match_id = ?"
            cursor.execute(sql, update_values)
            print(f"  Updated stats for {match_id}: {len(update_fields)} fields")

    conn.commit()


async def main():
    """主函数"""
    print("=" * 60)
    print("补充清水鼓动和大阪钢巴历史数据")
    print("=" * 60)

    conn = sqlite3.connect(DB_PATH)

    async with aiohttp.ClientSession() as session:
        # 获取最近6个月的比赛数据
        end_date = datetime.now()
        start_date = end_date - timedelta(days=180)

        print(f"\n获取 {start_date.strftime('%Y-%m-%d')} 至 {end_date.strftime('%Y-%m-%d')} 的比赛...")

        # 分段获取，避免API限制
        all_matches = []
        current = start_date
        while current < end_date:
            chunk_end = min(current + timedelta(days=30), end_date)

            print(f"  获取 {current.strftime('%Y-%m-%d')} 至 {chunk_end.strftime('%Y-%m-%d')}...")
            matches = await fetch_matches(
                session,
                current.strftime("%Y-%m-%d"),
                chunk_end.strftime("%Y-%m-%d"),
                J1_LEAGUE_ID
            )

            # 过滤目标球队的比赛
            for match in matches:
                home_team = match.get("match_hometeam_name", "")
                away_team = match.get("match_awayteam_name", "")

                home_id = parse_team_name(home_team)
                away_id = parse_team_name(away_team)

                if home_id in TEAMS or away_id in TEAMS:
                    all_matches.append(match)

            current = chunk_end + timedelta(days=1)
            time.sleep(2)  # 避免API限制

        print(f"\n找到 {len(all_matches)} 场相关比赛")

        # 获取每场比赛的详细数据
        updated_count = 0
        for i, match in enumerate(all_matches):
            match_id_api = match.get("match_id")
            home_team = match.get("match_hometeam_name", "")
            away_team = match.get("match_awayteam_name", "")

            print(f"\n[{i+1}/{len(all_matches)}] {home_team} vs {away_team} (API ID: {match_id_api})")

            # 获取详情
            details = await fetch_match_details(session, match_id_api)
            if not details:
                print("  无法获取详情")
                continue

            # 解析统计
            stats = parse_statistics(details)
            goalscorer = details.get("goalscorer", [])

            # 查找数据库中的对应比赛
            home_id = parse_team_name(home_team)
            away_id = parse_team_name(away_team)
            match_date = match.get("match_date")

            cursor = conn.cursor()
            cursor.execute("""
                SELECT match_id FROM matches
                WHERE (home_team_id = ? AND away_team_id = ?)
                   OR (home_team_id = ? AND away_team_id = ?)
                AND match_date = ?
            """, (home_id, away_id, away_id, home_id, match_date))

            row = cursor.fetchone()
            if row:
                db_match_id = row[0]
                update_match_in_db(conn, db_match_id, stats, goalscorer)
                updated_count += 1
            else:
                print(f"  数据库中未找到对应比赛")
                # 如果有统计，考虑插入新记录
                if stats:
                    print(f"  统计数据: {list(stats.keys())}")

            time.sleep(2)  # 避免API限制

        print(f"\n更新了 {updated_count} 场比赛的统计数据")

    conn.close()
    print("\n完成!")


if __name__ == "__main__":
    asyncio.run(main())
