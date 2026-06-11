"""
日韩联赛数据采集模块
支持: J1 League, J2 League, J3 League, K League 1, K League 2
数据源: API-Football, FBref, Sportmonks, 365Scores
"""

import asyncio
import sqlite3
import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Any

# 设置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# 项目根目录
PROJECT_ROOT = Path(__file__).parent.parent.parent
DATABASE_PATH = PROJECT_ROOT / "data" / "football_v2.db"
CONFIG_PATH = PROJECT_ROOT / "api_config.json"

# 日韩联赛配置
JAPAN_KOREA_LEAGUES = {
    # 日本联赛
    "j1_league": {
        "name_en": "J1 League",
        "name_cn": "J1联赛",
        "country": "Japan",
        "country_cn": "日本",
        "league_id": 18,
        "apifootball_id": 98,
        "sportmonks_id": 151,
        "fbref_url": "https://fbref.com/en/comps/51/J1-League-Stats",
        "tier": 1,
        "season": "2024"
    },
    "j2_league": {
        "name_en": "J2 League",
        "name_cn": "J2联赛",
        "country": "Japan",
        "country_cn": "日本",
        "league_id": 7433,
        "apifootball_id": 99,
        "sportmonks_id": 152,
        "fbref_url": "https://fbref.com/en/comps/52/J2-League-Stats",
        "tier": 2,
        "season": "2024"
    },
    "j3_league": {
        "name_en": "J3 League",
        "name_cn": "J3联赛",
        "country": "Japan",
        "country_cn": "日本",
        "league_id": 7434,
        "apifootball_id": 100,
        "sportmonks_id": 153,
        "fbref_url": None,  # FBref 可能不覆盖 J3
        "tier": 3,
        "season": "2024"
    },
    # 韩国联赛
    "k1_league": {
        "name_en": "K League 1",
        "name_cn": "K联赛1",
        "country": "South Korea",
        "country_cn": "韩国",
        "league_id": 20,
        "apifootball_id": 39,
        "sportmonks_id": 55,
        "fbref_url": "https://fbref.com/en/comps/55/K-League-1-Stats",
        "tier": 1,
        "season": "2024"
    },
    "k2_league": {
        "name_en": "K League 2",
        "name_cn": "K联赛2",
        "country": "South Korea",
        "country_cn": "韩国",
        "league_id": 7436,
        "apifootball_id": 40,
        "sportmonks_id": 56,
        "fbref_url": "https://fbref.com/en/comps/56/K-League-2-Stats",
        "tier": 2,
        "season": "2024"
    },
    # 杯赛
    "emperor_cup": {
        "name_en": "Emperor's Cup",
        "name_cn": "天皇杯",
        "country": "Japan",
        "country_cn": "日本",
        "league_id": 7498,
        "apifootball_id": 126,
        "sportmonks_id": None,
        "fbref_url": None,
        "tier": 0,
        "season": "2024"
    },
    "j_league_cup": {
        "name_en": "J.League Cup",
        "name_cn": "J联赛杯",
        "country": "Japan",
        "country_cn": "日本",
        "league_id": 7499,
        "apifootball_id": 127,
        "sportmonks_id": None,
        "fbref_url": None,
        "tier": 0,
        "season": "2024"
    },
    "korean_fa_cup": {
        "name_en": "Korean FA Cup",
        "name_cn": "韩国足协杯",
        "country": "South Korea",
        "country_cn": "韩国",
        "league_id": 7501,
        "apifootball_id": 41,
        "sportmonks_id": None,
        "fbref_url": None,
        "tier": 0,
        "season": "2024"
    }
}


class JapanKoreaCollector:
    """日韩联赛数据采集器"""

    def __init__(self):
        self.db_path = str(DATABASE_PATH)
        self.config = self._load_config()
        self.apifootball_key = self.config.get("apifootball", {}).get("api_key", "")
        self.sportmonks_token = self.config.get("sportmonks", {}).get("api_token", "")

    def _load_config(self) -> Dict:
        """加载API配置"""
        if CONFIG_PATH.exists():
            with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {}

    def get_connection(self) -> sqlite3.Connection:
        """获取数据库连接"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    async def collect_from_apifootball(self, league_key: str, days: int = 30) -> Dict:
        """从API-Football采集数据"""
        import aiohttp

        league_config = JAPAN_KOREA_LEAGUES.get(league_key)
        if not league_config:
            return {"success": False, "error": f"Unknown league: {league_key}"}

        api_id = league_config["apifootball_id"]
        base_url = "https://apiv3.apifootball.com"

        today = datetime.now()
        from_date = (today - timedelta(days=days)).strftime("%Y-%m-%d")
        to_date = (today + timedelta(days=days)).strftime("%Y-%m-%d")

        results = {
            "league": league_key,
            "source": "apifootball",
            "matches_fetched": 0,
            "matches_inserted": 0,
            "matches_updated": 0,
            "errors": []
        }

        try:
            async with aiohttp.ClientSession() as session:
                # 获取比赛数据
                url = f"{base_url}/"
                params = {
                    "action": "get_events",
                    "APIkey": self.apifootball_key,
                    "league_id": api_id,
                    "from": from_date,
                    "to": to_date
                }

                async with session.get(url, params=params) as response:
                    if response.status == 200:
                        data = await response.json()

                        if isinstance(data, list):
                            results["matches_fetched"] = len(data)

                            conn = self.get_connection()
                            cursor = conn.cursor()

                            for match in data:
                                try:
                                    insert_result = self._insert_match_from_api(cursor, match, league_config)
                                    if insert_result == "inserted":
                                        results["matches_inserted"] += 1
                                    elif insert_result == "updated":
                                        results["matches_updated"] += 1
                                except Exception as e:
                                    results["errors"].append(f"Match {match.get('match_id')}: {str(e)}")

                            conn.commit()
                            conn.close()
                    else:
                        results["errors"].append(f"API error: {response.status}")

        except Exception as e:
            results["errors"].append(str(e))

        return results

    def _insert_match_from_api(self, cursor, match: Dict, league_config: Dict) -> str:
        """插入或更新比赛数据"""
        match_id = f"apifootball_{match.get('match_id', '')}"

        # 检查是否存在
        cursor.execute("SELECT match_id FROM matches WHERE match_id = ?", (match_id,))
        if cursor.fetchone():
            # 更新
            cursor.execute("""
                UPDATE matches SET
                    match_date = ?, match_time = ?, status = ?,
                    home_goals = ?, away_goals = ?,
                    home_goals_ht = ?, away_goals_ht = ?,
                    venue = ?, referee = ?, updated_at = ?
                WHERE match_id = ?
            """, (
                match.get("match_date"),
                match.get("match_time"),
                self._map_status(match.get("match_status", "")),
                self._parse_int(match.get("match_hometeam_score")),
                self._parse_int(match.get("match_awayteam_score")),
                self._parse_int(match.get("match_hometeam_halftime_score")),
                self._parse_int(match.get("match_awayteam_halftime_score")),
                match.get("match_stadium"),
                match.get("match_referee"),
                datetime.now().isoformat(),
                match_id
            ))
            return "updated"
        else:
            # 插入新记录
            cursor.execute("""
                INSERT INTO matches (
                    match_id, league_id, match_date, match_time, status,
                    home_team_id, away_team_id, home_team, away_team,
                    home_goals, away_goals, home_goals_ht, away_goals_ht,
                    venue, referee, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                match_id,
                league_config["league_id"],
                match.get("match_date"),
                match.get("match_time"),
                self._map_status(match.get("match_status", "")),
                self._get_or_create_team(cursor, match.get("match_hometeam_name", ""), league_config["country"]),
                self._get_or_create_team(cursor, match.get("match_awayteam_name", ""), league_config["country"]),
                match.get("match_hometeam_name"),
                match.get("match_awayteam_name"),
                self._parse_int(match.get("match_hometeam_score")),
                self._parse_int(match.get("match_awayteam_score")),
                self._parse_int(match.get("match_hometeam_halftime_score")),
                self._parse_int(match.get("match_awayteam_halftime_score")),
                match.get("match_stadium"),
                match.get("match_referee"),
                datetime.now().isoformat(),
                datetime.now().isoformat()
            ))
            return "inserted"

    def _get_or_create_team(self, cursor, team_name: str, country: str) -> int:
        """获取或创建球队"""
        if not team_name:
            return 0

        # 尝试查找
        cursor.execute("SELECT team_id FROM teams WHERE name_en = ? OR name_cn = ?", (team_name, team_name))
        row = cursor.fetchone()
        if row:
            return row[0]

        # 创建新球队
        cursor.execute("""
            INSERT INTO teams (name_en, country, created_at)
            VALUES (?, ?, ?)
        """, (team_name, country, datetime.now().isoformat()))

        return cursor.lastrowid

    def _map_status(self, status: str) -> str:
        """映射比赛状态"""
        status_map = {
            "FT": "finished",
            "Finished": "finished",
            "1H": "live",
            "2H": "live",
            "HT": "live",
            "NS": "scheduled",
            "Not Started": "scheduled",
            "Postp.": "postponed",
            "Postponed": "postponed",
            "Canc.": "cancelled",
            "Cancelled": "cancelled"
        }
        return status_map.get(status, "scheduled")

    def _parse_int(self, value: Any) -> Optional[int]:
        """解析整数"""
        if value is None:
            return None
        try:
            return int(value)
        except (ValueError, TypeError):
            return None

    async def collect_from_fbref(self, league_key: str) -> Dict:
        """从FBref采集数据"""
        import requests
        from bs4 import BeautifulSoup
        import os

        league_config = JAPAN_KOREA_LEAGUES.get(league_key)
        if not league_config or not league_config.get("fbref_url"):
            return {"success": False, "error": f"FBref not available for {league_key}"}

        results = {
            "league": league_key,
            "source": "fbref",
            "matches_fetched": 0,
            "standings_fetched": 0,
            "errors": []
        }

        try:
            # 禁用代理
            os.environ['HTTP_PROXY'] = ''
            os.environ['HTTPS_PROXY'] = ''
            os.environ['http_proxy'] = ''
            os.environ['https_proxy'] = ''

            session = requests.Session()
            session.trust_env = False  # 忽略系统代理设置
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.5',
                'Connection': 'keep-alive',
            }

            response = session.get(league_config["fbref_url"], headers=headers, timeout=30, proxies={'http': None, 'https': None})

            if response.status_code == 200:
                soup = BeautifulSoup(response.text, 'html.parser')

                # 解析积分榜
                standings = self._parse_fbref_standings(soup, league_config)
                results["standings_fetched"] = len(standings)

                # 解析赛程
                matches = self._parse_fbref_fixtures(soup, league_config)
                results["matches_fetched"] = len(matches)

                # 保存到数据库
                conn = self.get_connection()
                cursor = conn.cursor()

                for standing in standings:
                    self._insert_standing(cursor, standing)

                conn.commit()
                conn.close()

        except Exception as e:
            results["errors"].append(str(e))

        return results

    def _parse_fbref_standings(self, soup, league_config: Dict) -> List[Dict]:
        """解析FBref积分榜"""
        standings = []

        tables = soup.find_all('table')
        for table in tables:
            if 'stats' in table.get('id', '').lower() or 'table' in table.get('class', []):
                rows = table.find_all('tr')
                for row in rows[1:]:
                    cols = row.find_all(['th', 'td'])
                    if len(cols) >= 10:
                        try:
                            team_name = cols[1].get_text(strip=True)
                            standings.append({
                                "team": team_name,
                                "league_id": league_config["league_id"],
                                "position": self._parse_int(cols[0].get_text(strip=True)),
                                "played": self._parse_int(cols[2].get_text(strip=True)),
                                "won": self._parse_int(cols[3].get_text(strip=True)),
                                "drawn": self._parse_int(cols[4].get_text(strip=True)),
                                "lost": self._parse_int(cols[5].get_text(strip=True)),
                                "goals_for": self._parse_int(cols[6].get_text(strip=True)),
                                "goals_against": self._parse_int(cols[7].get_text(strip=True)),
                                "points": self._parse_int(cols[9].get_text(strip=True)),
                                "source": "fbref"
                            })
                        except:
                            continue

        return standings

    def _parse_fbref_fixtures(self, soup, league_config: Dict) -> List[Dict]:
        """解析FBref赛程"""
        matches = []

        tables = soup.find_all('table')
        for table in tables:
            if 'schedule' in table.get('id', '').lower():
                rows = table.find_all('tr')
                for row in rows[1:]:
                    cols = row.find_all('td')
                    if len(cols) >= 6:
                        try:
                            date = cols[0].get_text(strip=True)
                            home = cols[2].get_text(strip=True)
                            away = cols[4].get_text(strip=True)
                            score = cols[3].get_text(strip=True)

                            home_score, away_score = None, None
                            if score and '–' in score:
                                parts = score.split('–')
                                home_score = self._parse_int(parts[0].strip())
                                away_score = self._parse_int(parts[1].strip())

                            matches.append({
                                "date": date,
                                "home_team": home,
                                "away_team": away,
                                "home_goals": home_score,
                                "away_goals": away_score,
                                "league_id": league_config["league_id"],
                                "source": "fbref"
                            })
                        except:
                            continue

        return matches

    def _insert_standing(self, cursor, standing: Dict):
        """插入积分榜数据"""
        # 简化实现 - 可根据实际表结构完善
        pass

    async def collect_all_japan_korea(self, days: int = 30) -> Dict:
        """采集所有日韩联赛数据"""
        results = {}

        # 先采集联赛数据
        for league_key in ["j1_league", "j2_league", "j3_league", "k1_league", "k2_league"]:
            logger.info(f"采集 {league_key} 数据...")

            # API-Football
            api_result = await self.collect_from_apifootball(league_key, days)
            results[f"{league_key}_apifootball"] = api_result

            # FBref (延迟避免被封)
            await asyncio.sleep(2)
            fbref_result = await self.collect_from_fbref(league_key)
            results[f"{league_key}_fbref"] = fbref_result

        return results

    def get_japan_korea_stats(self) -> Dict:
        """获取日韩联赛数据统计"""
        conn = self.get_connection()
        cursor = conn.cursor()

        stats = {}

        for league_key, config in JAPAN_KOREA_LEAGUES.items():
            league_id = config["league_id"]

            # 比赛数
            cursor.execute("SELECT COUNT(*) FROM matches WHERE league_id = ?", (league_id,))
            match_count = cursor.fetchone()[0]

            # 球队数
            cursor.execute("""
                SELECT COUNT(DISTINCT team_id) FROM (
                    SELECT home_team_id as team_id FROM matches WHERE league_id = ?
                    UNION
                    SELECT away_team_id as team_id FROM matches WHERE league_id = ?
                )
            """, (league_id, league_id))
            team_count = cursor.fetchone()[0]

            # 日期范围
            cursor.execute("""
                SELECT MIN(match_date), MAX(match_date)
                FROM matches WHERE league_id = ?
            """, (league_id,))
            date_range = cursor.fetchone()

            stats[league_key] = {
                "name": config["name_cn"],
                "matches": match_count,
                "teams": team_count,
                "date_range": {
                    "from": date_range[0],
                    "to": date_range[1]
                }
            }

        conn.close()
        return stats


# 命令行入口
async def main():
    """主函数"""
    collector = JapanKoreaCollector()

    print("=" * 60)
    print("日韩联赛数据采集器")
    print("=" * 60)

    # 显示当前统计
    stats = collector.get_japan_korea_stats()
    print("\n当前数据统计:")
    for league, data in stats.items():
        print(f"  {data['name']}: {data['matches']} 场比赛, {data['teams']} 支球队")
        if data['date_range']['from']:
            print(f"    日期范围: {data['date_range']['from']} ~ {data['date_range']['to']}")

    print("\n开始采集数据...")
    results = await collector.collect_all_japan_korea(days=60)

    print("\n采集结果:")
    for key, result in results.items():
        if "error" in result and result.get("error"):
            print(f"  {key}: 失败 - {result['error']}")
        else:
            print(f"  {key}: 获取 {result.get('matches_fetched', 0)} 场比赛")

    # 显示更新后统计
    stats = collector.get_japan_korea_stats()
    print("\n更新后统计:")
    for league, data in stats.items():
        print(f"  {data['name']}: {data['matches']} 场比赛, {data['teams']} 支球队")


if __name__ == "__main__":
    asyncio.run(main())
