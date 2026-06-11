"""
日韩联赛历史数据补充采集脚本
补充 2021-2025 赛季的历史比赛数据
"""

import asyncio
import aiohttp
import sqlite3
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).parent.parent.parent
DATABASE_PATH = PROJECT_ROOT / "data" / "football_v2.db"
CONFIG_PATH = PROJECT_ROOT / "api_config.json"

# 历史赛季配置
HISTORICAL_SEASONS = {
    "j1_league": {
        "apifootball_id": 98,
        "local_league_id": 18,
        "seasons": ["2021", "2022", "2023", "2024", "2025"]
    },
    "j2_league": {
        "apifootball_id": 99,
        "local_league_id": 7433,
        "seasons": ["2021", "2022", "2023", "2024", "2025"]
    },
    "j3_league": {
        "apifootball_id": 100,
        "local_league_id": 7434,
        "seasons": ["2023", "2024", "2025"]
    },
    "k1_league": {
        "apifootball_id": 39,
        "local_league_id": 20,
        "seasons": ["2021", "2022", "2023", "2024", "2025"]
    },
    "k2_league": {
        "apifootball_id": 40,
        "local_league_id": 7436,
        "seasons": ["2021", "2022", "2023", "2024", "2025"]
    }
}


class HistoricalDataCollector:
    """历史数据采集器"""

    def __init__(self):
        self.db_path = str(DATABASE_PATH)
        self.config = self._load_config()
        self.api_key = self.config.get("apis", {}).get("apifootball", {}).get("api_key", "")

    def _load_config(self) -> Dict:
        if CONFIG_PATH.exists():
            with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {}

    def get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    async def collect_season_data(self, league_key: str, season: str) -> Dict:
        """采集指定赛季数据"""
        league = HISTORICAL_SEASONS.get(league_key)
        if not league:
            return {"error": f"Unknown league: {league_key}"}

        # 计算赛季日期范围
        start_year = int(season)
        if start_year == 2025:
            # 2025赛季可能还在进行
            from_date = f"{season}-01-01"
            to_date = f"{season}-12-31"
        else:
            # 历史赛季
            from_date = f"{season}-01-01"
            to_date = f"{season}-12-31"

        base_url = "https://apiv3.apifootball.com"
        results = {
            "league": league_key,
            "season": season,
            "matches_fetched": 0,
            "matches_saved": 0,
            "errors": []
        }

        try:
            async with aiohttp.ClientSession() as session:
                params = {
                    "action": "get_events",
                    "APIkey": self.api_key,
                    "league_id": league["apifootball_id"],
                    "from": from_date,
                    "to": to_date
                }

                logger.info(f"采集 {league_key} {season} 赛季 ({from_date} ~ {to_date})...")

                async with session.get(f"{base_url}/", params=params) as resp:
                    if resp.status == 200:
                        data = await resp.json()

                        if isinstance(data, list):
                            results["matches_fetched"] = len(data)
                            logger.info(f"获取 {len(data)} 场比赛")

                            # 保存到数据库
                            saved = self._save_matches(data, league, league_key)
                            results["matches_saved"] = saved

                        elif isinstance(data, dict) and data.get("error"):
                            results["errors"].append(data.get("error"))

                    else:
                        results["errors"].append(f"HTTP {resp.status}")

        except Exception as e:
            results["errors"].append(str(e))

        return results

    def _save_matches(self, matches: List[Dict], league: Dict, league_key: str) -> int:
        """保存比赛数据"""
        conn = self.get_connection()
        cursor = conn.cursor()

        saved = 0

        for match in matches:
            try:
                match_id = f"apifootball_{match.get('match_id', '')}"

                # 先获取/创建球队
                home_team_id = self._get_or_create_team(
                    cursor,
                    match.get("match_hometeam_name", ""),
                    league_key
                )
                away_team_id = self._get_or_create_team(
                    cursor,
                    match.get("match_awayteam_name", ""),
                    league_key
                )

                # 检查是否存在
                cursor.execute("SELECT match_id FROM matches WHERE match_id = ?", (match_id,))
                exists = cursor.fetchone()

                if not exists:
                    cursor.execute("""
                        INSERT INTO matches (
                            match_id, league_id, match_date, match_time, status,
                            home_team_id, away_team_id,
                            home_goals, away_goals,
                            home_goals_ht, away_goals_ht,
                            round_num, venue, referee, source, created_at, updated_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        match_id,
                        league["local_league_id"],
                        match.get("match_date"),
                        match.get("match_time"),
                        self._map_status(match.get("match_status", "")),
                        home_team_id,
                        away_team_id,
                        self._parse_int(match.get("match_hometeam_score")),
                        self._parse_int(match.get("match_awayteam_score")),
                        self._parse_int(match.get("match_hometeam_halftime_score")),
                        self._parse_int(match.get("match_awayteam_halftime_score")),
                        self._parse_int(match.get("match_round")),
                        match.get("match_stadium"),
                        match.get("match_referee"),
                        "apifootball_historical",
                        datetime.now().isoformat(),
                        datetime.now().isoformat()
                    ))
                    saved += 1

            except Exception as e:
                logger.error(f"保存比赛失败: {e}")

        conn.commit()
        conn.close()
        return saved

    def _get_or_create_team(self, cursor, team_name: str, league_key: str) -> int:
        """获取或创建球队"""
        if not team_name:
            return 0

        # 获取国家
        country_map = {
            "j1_league": "Japan",
            "j2_league": "Japan",
            "j3_league": "Japan",
            "k1_league": "South Korea",
            "k2_league": "South Korea"
        }
        country = country_map.get(league_key, "Japan")

        # 查找球队
        cursor.execute("SELECT team_id FROM teams WHERE name_en = ?", (team_name,))
        row = cursor.fetchone()
        if row:
            return row[0]

        # 创建新球队
        cursor.execute(
            "INSERT INTO teams (name_en, country, created_at) VALUES (?, ?, ?)",
            (team_name, country, datetime.now().isoformat())
        )
        return cursor.lastrowid

    def _map_status(self, status: str) -> str:
        status_map = {
            "FT": "finished", "Finished": "finished",
            "NS": "scheduled", "Not Started": "scheduled",
            "Postp.": "postponed", "Canc.": "cancelled"
        }
        return status_map.get(status, "finished")

    def _parse_int(self, value) -> int:
        if value is None:
            return None
        try:
            return int(value)
        except:
            return None

    async def collect_all_historical(self) -> Dict:
        """采集所有历史数据"""
        all_results = {}

        for league_key, config in HISTORICAL_SEASONS.items():
            all_results[league_key] = {}

            for season in config["seasons"]:
                # 先检查是否已有数据
                conn = self.get_connection()
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT COUNT(*) FROM matches
                    WHERE league_id = ?
                    AND match_date LIKE ?
                """, (config["local_league_id"], f"{season}%"))
                existing = cursor.fetchone()[0]
                conn.close()

                if existing > 50:
                    logger.info(f"{league_key} {season} 已有 {existing} 场数据，跳过")
                    all_results[league_key][season] = {"skipped": True, "existing": existing}
                    continue

                result = await self.collect_season_data(league_key, season)
                all_results[league_key][season] = result

                # 延迟避免API限制
                await asyncio.sleep(3)

        return all_results

    def show_current_coverage(self):
        """显示当前数据覆盖情况"""
        conn = self.get_connection()
        cursor = conn.cursor()

        print("\n当前日韩联赛数据覆盖情况:")
        print("=" * 70)

        for league_key, config in HISTORICAL_SEASONS.items():
            league_names = {
                "j1_league": "J1联赛",
                "j2_league": "J2联赛",
                "j3_league": "J3联赛",
                "k1_league": "K联赛1",
                "k2_league": "K联赛2"
            }

            print(f"\n{league_names.get(league_key, league_key)}:")

            for season in config["seasons"]:
                cursor.execute("""
                    SELECT COUNT(*),
                           MIN(match_date),
                           MAX(match_date)
                    FROM matches
                    WHERE league_id = ?
                    AND match_date LIKE ?
                """, (config["local_league_id"], f"{season}%"))

                row = cursor.fetchone()
                count = row[0]
                min_date = row[1] or "N/A"
                max_date = row[2] or "N/A"

                status = "[OK]" if count > 100 else ("[部分]" if count > 0 else "[缺失]")
                print(f"  {season}赛季: {count}场 ({min_date} ~ {max_date}) {status}")

        conn.close()


async def main():
    """主函数"""
    collector = HistoricalDataCollector()

    # 显示当前覆盖
    collector.show_current_coverage()

    print("\n" + "=" * 70)
    print("开始补充历史数据...")
    print("=" * 70)

    results = await collector.collect_all_historical()

    print("\n采集结果:")
    for league_key, seasons in results.items():
        print(f"\n{league_key}:")
        for season, result in seasons.items():
            if result.get("skipped"):
                print(f"  {season}: 跳过 (已有 {result['existing']} 场)")
            else:
                fetched = result.get("matches_fetched", 0)
                saved = result.get("matches_saved", 0)
                print(f"  {season}: 获取 {fetched} 场, 保存 {saved} 场")
                if result.get("errors"):
                    print(f"    错误: {result['errors']}")

    # 显示更新后覆盖
    collector.show_current_coverage()


if __name__ == "__main__":
    asyncio.run(main())