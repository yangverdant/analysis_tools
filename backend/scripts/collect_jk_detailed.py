"""
日韩联赛详细数据采集脚本
采集内容: 赔率数据、球员信息、球队详情(城市/球场)、比赛统计
"""

import asyncio
import aiohttp
import sqlite3
import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).parent.parent.parent
DATABASE_PATH = PROJECT_ROOT / "data" / "football_v2.db"
CONFIG_PATH = PROJECT_ROOT / "api_config.json"

# 联赛配置
LEAGUES = {
    "j1_league": {"api_id": 98, "local_id": 18, "country": "Japan"},
    "j2_league": {"api_id": 99, "local_id": 7433, "country": "Japan"},
    "k1_league": {"api_id": 39, "local_id": 20, "country": "South Korea"},
    "k2_league": {"api_id": 40, "local_id": 7436, "country": "South Korea"}
}


class DetailedDataCollector:
    """详细数据采集器"""

    def __init__(self):
        self.db_path = str(DATABASE_PATH)
        self.config = self._load_config()
        self.api_key = self.config.get("apis", {}).get("apifootball", {}).get("api_key", "")
        self.base_url = "https://apiv3.apifootball.com"

    def _load_config(self) -> Dict:
        if CONFIG_PATH.exists():
            with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {}

    def get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    async def collect_odds_data(self, days: int = 30) -> Dict:
        """采集赔率数据"""
        results = {"fetched": 0, "saved": 0, "errors": []}

        today = datetime.now()
        from_date = (today - timedelta(days=days)).strftime("%Y-%m-%d")
        to_date = (today + timedelta(days=days)).strftime("%Y-%m-%d")

        async with aiohttp.ClientSession() as session:
            for league_key, config in LEAGUES.items():
                logger.info(f"采集 {league_key} 赔率数据...")

                params = {
                    "action": "get_odds",
                    "APIkey": self.api_key,
                    "league_id": config["api_id"],
                    "from": from_date,
                    "to": to_date
                }

                try:
                    async with session.get(f"{self.base_url}/", params=params) as resp:
                        if resp.status == 200:
                            data = await resp.json()

                            if isinstance(data, list) and data:
                                results["fetched"] += len(data)
                                saved = self._save_odds(data)
                                results["saved"] += saved
                                logger.info(f"  获取 {len(data)} 条赔率，保存 {saved} 条")
                        elif isinstance(data, dict) and data.get("error"):
                            # 没有赔率数据
                            pass
                except Exception as e:
                    results["errors"].append(f"{league_key}: {str(e)}")

                await asyncio.sleep(2)

        return results

    def _save_odds(self, odds_data: List[Dict]) -> int:
        """保存赔率数据"""
        conn = self.get_connection()
        cursor = conn.cursor()
        saved = 0

        for odds in odds_data:
            try:
                match_id = f"apifootball_{odds.get('match_id', '')}"

                # 更新比赛的赔率信息
                cursor.execute("""
                    UPDATE matches SET
                        odds_home = ?,
                        odds_draw = ?,
                        odds_away = ?,
                        odds_home_closing = ?,
                        odds_draw_closing = ?,
                        odds_away_closing = ?,
                        updated_at = ?
                    WHERE match_id = ?
                """, (
                    self._parse_float(odds.get("odd_1")),
                    self._parse_float(odds.get("odd_x")),
                    self._parse_float(odds.get("odd_2")),
                    self._parse_float(odds.get("odd_1")),
                    self._parse_float(odds.get("odd_x")),
                    self._parse_float(odds.get("odd_2")),
                    datetime.now().isoformat(),
                    match_id
                ))

                if cursor.rowcount > 0:
                    saved += 1

            except Exception as e:
                logger.error(f"保存赔率失败: {e}")

        conn.commit()
        conn.close()
        return saved

    async def collect_team_details(self) -> Dict:
        """采集球队详细信息 (城市、球场等)"""
        results = {"fetched": 0, "updated": 0, "errors": []}

        conn = self.get_connection()
        cursor = conn.cursor()

        # 获取所有日韩球队
        cursor.execute("""
            SELECT team_id, name_en, country
            FROM teams
            WHERE country IN ('Japan', 'South Korea')
            AND stadium IS NULL
        """)
        teams = cursor.fetchall()
        conn.close()

        logger.info(f"需要补充详细信息的球队: {len(teams)}")

        async with aiohttp.ClientSession() as session:
            for team in teams[:50]:  # 限制数量避免API限制
                team_name = team["name_en"]

                # 尝试从API获取球队信息
                params = {
                    "action": "get_teams",
                    "APIkey": self.api_key,
                    "team_name": team_name
                }

                try:
                    async with session.get(f"{self.base_url}/", params=params) as resp:
                        if resp.status == 200:
                            data = await resp.json()

                            if isinstance(data, list) and data:
                                results["fetched"] += 1
                                self._save_team_details(data[0], team["team_id"])
                                results["updated"] += 1

                except Exception as e:
                    results["errors"].append(f"{team_name}: {str(e)}")

                await asyncio.sleep(2)

        return results

    def _save_team_details(self, team_data: Dict, team_id: int):
        """保存球队详细信息"""
        conn = self.get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute("""
                UPDATE teams SET
                    stadium = ?,
                    stadium_capacity = ?,
                    founded_year = ?,
                    logo_url = ?,
                    updated_at = ?
                WHERE team_id = ?
            """, (
                team_data.get("team_stadium"),
                self._parse_int(team_data.get("team_stadium_capacity")),
                self._parse_int(team_data.get("team_founded")),
                team_data.get("team_badge"),
                datetime.now().isoformat(),
                team_id
            ))
            conn.commit()
        except Exception as e:
            logger.error(f"保存球队详情失败: {e}")

        conn.close()

    async def collect_match_statistics(self, match_id: str) -> Dict:
        """采集单场比赛统计数据"""
        params = {
            "action": "get_statistics",
            "APIkey": self.api_key,
            "match_id": match_id.replace("apifootball_", "")
        }

        async with aiohttp.ClientSession() as session:
            try:
                async with session.get(f"{self.base_url}/", params=params) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        return data
            except Exception as e:
                logger.error(f"获取比赛统计失败: {e}")

        return {}

    async def collect_player_data(self, team_id: int, team_name: str) -> Dict:
        """采集球队球员数据"""
        results = {"fetched": 0, "saved": 0, "errors": []}

        # 首先获取API中的球队ID
        async with aiohttp.ClientSession() as session:
            params = {
                "action": "get_teams",
                "APIkey": self.api_key,
                "team_name": team_name
            }

            try:
                async with session.get(f"{self.base_url}/", params=params) as resp:
                    if resp.status == 200:
                        data = await resp.json()

                        if isinstance(data, list) and data:
                            api_team_id = data[0].get("team_id")

                            if api_team_id:
                                # 获取球队阵容
                                params = {
                                    "action": "get_squad",
                                    "APIkey": self.api_key,
                                    "team_id": api_team_id
                                }

                                await asyncio.sleep(2)

                                async with session.get(f"{self.base_url}/", params=params) as resp2:
                                    if resp2.status == 200:
                                        squad_data = await resp2.json()

                                        if isinstance(squad_data, list):
                                            results["fetched"] = len(squad_data)
                                            saved = self._save_players(squad_data, team_id)
                                            results["saved"] = saved

            except Exception as e:
                results["errors"].append(str(e))

        return results

    def _save_players(self, players: List[Dict], team_id: int) -> int:
        """保存球员数据"""
        conn = self.get_connection()
        cursor = conn.cursor()
        saved = 0

        for player in players:
            try:
                player_name = player.get("player_name", "")
                if not player_name:
                    continue

                # 检查是否存在
                cursor.execute("SELECT player_id FROM players WHERE name_en = ?", (player_name,))
                if cursor.fetchone():
                    continue

                cursor.execute("""
                    INSERT INTO players (
                        player_code, name_en, position_main,
                        nationality, birth_date, height, weight,
                        created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    f"apifootball_{player.get('player_id', '')}",
                    player_name,
                    player.get("player_type"),
                    player.get("player_country"),
                    player.get("player_birthday"),
                    self._parse_int(player.get("player_height")),
                    self._parse_int(player.get("player_weight")),
                    datetime.now().isoformat(),
                    datetime.now().isoformat()
                ))
                saved += 1

            except Exception as e:
                logger.error(f"保存球员失败: {e}")

        conn.commit()
        conn.close()
        return saved

    async def collect_all_details(self) -> Dict:
        """采集所有详细数据"""
        results = {
            "odds": {},
            "teams": {},
            "players": {}
        }

        print("=" * 60)
        print("日韩联赛详细数据采集")
        print("=" * 60)

        # 1. 采集赔率数据
        print("\n[1/3] 采集赔率数据...")
        results["odds"] = await self.collect_odds_data(days=60)
        print(f"  获取 {results['odds']['fetched']} 条，保存 {results['odds']['saved']} 条")

        # 2. 采集球队详情
        print("\n[2/3] 采集球队详细信息...")
        results["teams"] = await self.collect_team_details()
        print(f"  获取 {results['teams']['fetched']} 条，更新 {results['teams']['updated']} 条")

        # 3. 采集球员数据 (选取部分球队)
        print("\n[3/3] 采集球员数据...")
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT team_id, name_en
            FROM teams
            WHERE country IN ('Japan', 'South Korea')
            LIMIT 20
        """)
        teams = cursor.fetchall()
        conn.close()

        total_players = 0
        for team in teams:
            result = await self.collect_player_data(team["team_id"], team["name_en"])
            total_players += result.get("saved", 0)
            print(f"  {team['name_en']}: {result.get('saved', 0)} 名球员")
            await asyncio.sleep(3)

        results["players"]["total_saved"] = total_players

        return results

    def _parse_int(self, value) -> Optional[int]:
        if value is None:
            return None
        try:
            return int(value)
        except:
            return None

    def _parse_float(self, value) -> Optional[float]:
        if value is None:
            return None
        try:
            return float(value)
        except:
            return None

    def show_data_quality(self):
        """显示数据质量报告"""
        conn = self.get_connection()
        cursor = conn.cursor()

        print("\n" + "=" * 60)
        print("数据质量报告")
        print("=" * 60)

        # 比赛数据
        cursor.execute('''
            SELECT
                COUNT(*) as total,
                SUM(CASE WHEN match_time IS NOT NULL AND match_time != '' THEN 1 ELSE 0 END) as with_time,
                SUM(CASE WHEN venue IS NOT NULL AND venue != '' THEN 1 ELSE 0 END) as with_venue,
                SUM(CASE WHEN referee IS NOT NULL AND referee != '' THEN 1 ELSE 0 END) as with_referee,
                SUM(CASE WHEN odds_home IS NOT NULL THEN 1 ELSE 0 END) as with_odds,
                SUM(CASE WHEN home_xg IS NOT NULL THEN 1 ELSE 0 END) as with_xg
            FROM matches
            WHERE league_id IN (18, 7433, 7434, 20, 7436)
        ''')
        row = cursor.fetchone()

        print("\n比赛数据:")
        print(f"  总数: {row[0]}")
        print(f"  有开球时间: {row[1]} ({row[1]*100//row[0]}%)")
        print(f"  有场地: {row[2]} ({row[2]*100//row[0]}%)")
        print(f"  有裁判: {row[3]} ({row[3]*100//row[0]}%)")
        print(f"  有赔率: {row[4]} ({row[4]*100//row[0] if row[0] else 0}%)")
        print(f"  有xG: {row[5]} ({row[5]*100//row[0] if row[0] else 0}%)")

        # 球队数据
        cursor.execute('''
            SELECT
                COUNT(*) as total,
                SUM(CASE WHEN stadium IS NOT NULL AND stadium != '' THEN 1 ELSE 0 END) as with_stadium,
                SUM(CASE WHEN stadium_capacity IS NOT NULL THEN 1 ELSE 0 END) as with_capacity,
                SUM(CASE WHEN logo_url IS NOT NULL AND logo_url != '' THEN 1 ELSE 0 END) as with_logo
            FROM teams
            WHERE country IN ('Japan', 'South Korea')
        ''')
        row = cursor.fetchone()

        print("\n球队数据:")
        print(f"  总数: {row[0]}")
        print(f"  有球场: {row[1]}")
        print(f"  有容量: {row[2]}")
        print(f"  有Logo: {row[3]}")

        # 球员数据
        cursor.execute('''
            SELECT COUNT(*) FROM players
            WHERE nationality IN ('Japan', 'South Korea', 'Japanese', 'Korean')
        ''')
        player_count = cursor.fetchone()[0]
        print(f"\n球员数据:")
        print(f"  日韩球员: {player_count}人")

        conn.close()


async def main():
    collector = DetailedDataCollector()

    # 显示当前数据质量
    collector.show_data_quality()

    # 采集详细数据
    results = await collector.collect_all_details()

    # 显示更新后的数据质量
    collector.show_data_quality()

    print("\n采集完成!")


if __name__ == "__main__":
    asyncio.run(main())
