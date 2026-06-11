"""
日韩联赛数据采集增强版
使用多种数据源: API-Football, 365Scores, TheSportsDB
"""

import asyncio
import aiohttp
import sqlite3
import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Any

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).parent.parent.parent
DATABASE_PATH = PROJECT_ROOT / "data" / "football_v2.db"
CONFIG_PATH = PROJECT_ROOT / "api_config.json"

# 日韩联赛配置 - 使用 API-Football ID
LEAGUE_MAPPING = {
    "j1_league": {
        "name_en": "J1 League",
        "name_cn": "J1联赛",
        "country": "Japan",
        "apifootball_id": 98,
        "thesportsdb_id": "4507",
        "local_league_id": 18,
        "tier": 1
    },
    "j2_league": {
        "name_en": "J2 League",
        "name_cn": "J2联赛",
        "country": "Japan",
        "apifootball_id": 99,
        "thesportsdb_id": "4508",
        "local_league_id": 7433,
        "tier": 2
    },
    "j3_league": {
        "name_en": "J3 League",
        "name_cn": "J3联赛",
        "country": "Japan",
        "apifootball_id": 100,
        "thesportsdb_id": "4509",
        "local_league_id": 7434,
        "tier": 3
    },
    "k1_league": {
        "name_en": "K League 1",
        "name_cn": "K联赛1",
        "country": "South Korea",
        "apifootball_id": 39,
        "thesportsdb_id": "4510",
        "local_league_id": 20,
        "tier": 1
    },
    "k2_league": {
        "name_en": "K League 2",
        "name_cn": "K联赛2",
        "country": "South Korea",
        "apifootball_id": 40,
        "thesportsdb_id": "4511",
        "local_league_id": 7436,
        "tier": 2
    }
}


class EnhancedJKLeagueCollector:
    """增强版日韩联赛数据采集器"""

    def __init__(self):
        self.db_path = str(DATABASE_PATH)
        self.config = self._load_config()

    def _load_config(self) -> Dict:
        """加载API配置"""
        if CONFIG_PATH.exists():
            with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {}

    def get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    async def collect_from_apifootball(self, league_key: str, from_date: str = None, to_date: str = None) -> Dict:
        """从 API-Football 采集数据"""
        league = LEAGUE_MAPPING.get(league_key)
        if not league:
            return {"success": False, "error": f"Unknown league: {league_key}"}

        api_key = self.config.get("apis", {}).get("apifootball", {}).get("api_key", "")
        if not api_key:
            return {"success": False, "error": "API-Football key not configured"}

        if not from_date:
            from_date = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
        if not to_date:
            to_date = (datetime.now() + timedelta(days=30)).strftime("%Y-%m-%d")

        base_url = "https://apiv3.apifootball.com"
        results = {"matches": [], "standings": [], "errors": []}

        try:
            async with aiohttp.ClientSession() as session:
                # 获取比赛数据
                params = {
                    "action": "get_events",
                    "APIkey": api_key,
                    "league_id": league["apifootball_id"],
                    "from": from_date,
                    "to": to_date
                }

                async with session.get(f"{base_url}/", params=params) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        if isinstance(data, list):
                            results["matches"] = data
                            logger.info(f"API-Football {league['name_cn']}: 获取 {len(data)} 场比赛")
                    else:
                        results["errors"].append(f"HTTP {resp.status}")

                await asyncio.sleep(1)

                # 获取积分榜
                params = {
                    "action": "get_standings",
                    "APIkey": api_key,
                    "league_id": league["apifootball_id"]
                }

                async with session.get(f"{base_url}/", params=params) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        if isinstance(data, list):
                            results["standings"] = data
                            logger.info(f"API-Football {league['name_cn']}: 获取 {len(data)} 条积分榜")

        except Exception as e:
            results["errors"].append(str(e))

        return results

    async def collect_from_thesportsdb(self, league_key: str) -> Dict:
        """从 TheSportsDB 采集数据 (免费，无需Key)"""
        league = LEAGUE_MAPPING.get(league_key)
        if not league:
            return {"success": False, "error": f"Unknown league: {league_key}"}

        base_url = "https://www.thesportsdb.com/api/v1/json/3"
        results = {"matches": [], "teams": [], "errors": []}

        try:
            async with aiohttp.ClientSession() as session:
                # 获取联赛最近比赛
                url = f"{base_url}/eventsnextleague.php?id={league['thesportsdb_id']}"
                async with session.get(url) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        events = data.get("events", [])
                        if events:
                            results["matches"].extend(events)

                await asyncio.sleep(1)

                # 获取联赛过去比赛
                url = f"{base_url}/eventspastleague.php?id={league['thesportsdb_id']}"
                async with session.get(url) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        events = data.get("events", [])
                        if events:
                            results["matches"].extend(events)

                logger.info(f"TheSportsDB {league['name_cn']}: 获取 {len(results['matches'])} 场比赛")

        except Exception as e:
            results["errors"].append(str(e))

        return results

    async def collect_from_365scores(self, league_key: str) -> Dict:
        """从 365Scores 采集数据 (免费，无需Key)"""
        league = LEAGUE_MAPPING.get(league_key)
        if not league:
            return {"success": False, "error": f"Unknown league: {league_key}"}

        # 365Scores 使用 competition ID
        # 需要先查询 competition 列表获取正确的 ID
        # 这里使用简化的方法获取比赛数据
        base_url = "https://webws.365scores.com/web"
        results = {"matches": [], "errors": []}

        try:
            async with aiohttp.ClientSession() as session:
                params = {
                    "action": "4",
                    "langId": "1",
                    "timezoneName": "Asia/Tokyo",
                    "userCountryId": "108",  # Japan
                    "appTypeId": "1",
                    "competitors": league.get("apifootball_id", "")
                }

                async with session.get(base_url, params=params) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        # 解析数据...
                        logger.info(f"365Scores {league['name_cn']}: 获取数据")

        except Exception as e:
            results["errors"].append(str(e))

        return results

    def save_matches_to_db(self, matches: List[Dict], league_key: str) -> Dict:
        """保存比赛数据到数据库"""
        league = LEAGUE_MAPPING.get(league_key)
        if not league or not matches:
            return {"inserted": 0, "updated": 0}

        conn = self.get_connection()
        cursor = conn.cursor()

        inserted = 0
        updated = 0

        for match in matches:
            try:
                # 根据数据源解析
                if "match_id" in match:  # API-Football
                    result = self._save_apifootball_match(cursor, match, league)
                elif "idEvent" in match:  # TheSportsDB
                    result = self._save_thesportsdb_match(cursor, match, league)
                else:
                    continue

                if result == "inserted":
                    inserted += 1
                elif result == "updated":
                    updated += 1

            except Exception as e:
                logger.error(f"保存比赛失败: {e}")

        conn.commit()
        conn.close()

        return {"inserted": inserted, "updated": updated}

    def _save_apifootball_match(self, cursor, match: Dict, league: Dict) -> str:
        """保存 API-Football 比赛数据"""
        match_id = f"apifootball_{match.get('match_id', '')}"
        league_id = league["local_league_id"]

        # 先获取/创建球队
        home_team_id = self._get_or_create_team(cursor, match.get("match_hometeam_name", ""), league["country"])
        away_team_id = self._get_or_create_team(cursor, match.get("match_awayteam_name", ""), league["country"])

        cursor.execute("SELECT match_id FROM matches WHERE match_id = ?", (match_id,))
        if cursor.fetchone():
            cursor.execute("""
                UPDATE matches SET
                    match_date = ?, match_time = ?, status = ?,
                    home_team_id = ?, away_team_id = ?,
                    home_goals = ?, away_goals = ?,
                    round_num = ?, venue = ?, referee = ?, source = ?, updated_at = ?
                WHERE match_id = ?
            """, (
                match.get("match_date"),
                match.get("match_time"),
                self._map_status(match.get("match_status", "")),
                home_team_id, away_team_id,
                self._parse_int(match.get("match_hometeam_score")),
                self._parse_int(match.get("match_awayteam_score")),
                self._parse_int(match.get("match_round")),
                match.get("match_stadium"),
                match.get("match_referee"),
                "apifootball",
                datetime.now().isoformat(),
                match_id
            ))
            return "updated"
        else:
            cursor.execute("""
                INSERT INTO matches (
                    match_id, league_id, match_date, match_time, status,
                    home_team_id, away_team_id,
                    home_goals, away_goals,
                    home_goals_ht, away_goals_ht,
                    round_num, venue, referee, source, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                match_id, league_id,
                match.get("match_date"),
                match.get("match_time"),
                self._map_status(match.get("match_status", "")),
                home_team_id, away_team_id,
                self._parse_int(match.get("match_hometeam_score")),
                self._parse_int(match.get("match_awayteam_score")),
                self._parse_int(match.get("match_hometeam_halftime_score")),
                self._parse_int(match.get("match_awayteam_halftime_score")),
                self._parse_int(match.get("match_round")),
                match.get("match_stadium"),
                match.get("match_referee"),
                "apifootball",
                datetime.now().isoformat(),
                datetime.now().isoformat()
            ))
            return "inserted"

    def _save_thesportsdb_match(self, cursor, match: Dict, league: Dict) -> str:
        """保存 TheSportsDB 比赛数据"""
        match_id = f"thesportsdb_{match.get('idEvent', '')}"
        league_id = league["local_league_id"]

        date_event = match.get("dateEvent", "")
        time_event = match.get("strTime", "")[:5] if match.get("strTime") else None

        home_score = self._parse_int(match.get("intHomeScore"))
        away_score = self._parse_int(match.get("intAwayScore"))

        # 先获取/创建球队
        home_team_id = self._get_or_create_team(cursor, match.get("strHomeTeam", ""), league["country"])
        away_team_id = self._get_or_create_team(cursor, match.get("strAwayTeam", ""), league["country"])

        # 判断状态
        status = "scheduled"
        if home_score is not None:
            status = "finished"

        cursor.execute("SELECT match_id FROM matches WHERE match_id = ?", (match_id,))
        if cursor.fetchone():
            cursor.execute("""
                UPDATE matches SET
                    match_date = ?, match_time = ?,
                    home_team_id = ?, away_team_id = ?,
                    home_goals = ?, away_goals = ?, status = ?, source = ?, updated_at = ?
                WHERE match_id = ?
            """, (date_event, time_event, home_team_id, away_team_id,
                  home_score, away_score, status, "thesportsdb",
                  datetime.now().isoformat(), match_id))
            return "updated"
        else:
            cursor.execute("""
                INSERT INTO matches (
                    match_id, league_id, match_date, match_time, status,
                    home_team_id, away_team_id,
                    home_goals, away_goals, source, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                match_id, league_id,
                date_event, time_event, status,
                home_team_id, away_team_id,
                home_score, away_score, "thesportsdb",
                datetime.now().isoformat(),
                datetime.now().isoformat()
            ))
            return "inserted"

    def _get_or_create_team(self, cursor, team_name: str, country: str) -> int:
        """获取或创建球队"""
        if not team_name:
            return 0

        cursor.execute("SELECT team_id FROM teams WHERE name_en = ?", (team_name,))
        row = cursor.fetchone()
        if row:
            return row[0]

        cursor.execute("INSERT INTO teams (name_en, country, created_at) VALUES (?, ?, ?)",
                      (team_name, country, datetime.now().isoformat()))
        return cursor.lastrowid

    def _map_status(self, status: str) -> str:
        status_map = {
            "FT": "finished", "Finished": "finished",
            "1H": "live", "2H": "live", "HT": "live",
            "NS": "scheduled", "Not Started": "scheduled",
            "Postp.": "postponed", "Postponed": "postponed",
            "Canc.": "cancelled", "Cancelled": "cancelled"
        }
        return status_map.get(status, "scheduled")

    def _parse_int(self, value: Any) -> Optional[int]:
        if value is None:
            return None
        try:
            return int(value)
        except:
            return None

    async def collect_all_leagues(self) -> Dict:
        """采集所有日韩联赛数据"""
        all_results = {}

        for league_key in LEAGUE_MAPPING.keys():
            logger.info(f"采集 {league_key}...")
            all_results[league_key] = {}

            # API-Football
            api_result = await self.collect_from_apifootball(league_key)
            if api_result.get("matches"):
                save_result = self.save_matches_to_db(api_result["matches"], league_key)
                all_results[league_key]["apifootball"] = {
                    "matches": len(api_result["matches"]),
                    "saved": save_result
                }
            await asyncio.sleep(2)

            # TheSportsDB
            tsdb_result = await self.collect_from_thesportsdb(league_key)
            if tsdb_result.get("matches"):
                save_result = self.save_matches_to_db(tsdb_result["matches"], league_key)
                all_results[league_key]["thesportsdb"] = {
                    "matches": len(tsdb_result["matches"]),
                    "saved": save_result
                }
            await asyncio.sleep(1)

        return all_results


async def main():
    """主函数"""
    collector = EnhancedJKLeagueCollector()

    print("=" * 60)
    print("日韩联赛数据采集器 (增强版)")
    print("=" * 60)

    print("\n开始采集...")
    results = await collector.collect_all_leagues()

    print("\n采集结果:")
    for league, sources in results.items():
        print(f"\n{league}:")
        for source, data in sources.items():
            print(f"  {source}: {data}")

    # 显示统计
    conn = collector.get_connection()
    cursor = conn.cursor()

    print("\n数据库统计:")
    for league_key, config in LEAGUE_MAPPING.items():
        cursor.execute("SELECT COUNT(*) FROM matches WHERE league_id = ?", (config["local_league_id"],))
        count = cursor.fetchone()[0]
        print(f"  {config['name_cn']}: {count} 场比赛")

    conn.close()


if __name__ == "__main__":
    asyncio.run(main())
