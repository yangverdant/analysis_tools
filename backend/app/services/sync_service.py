"""
数据同步服务
使用项目已有的数据源管理器自动同步数据
"""

import os
import json
import sqlite3
from datetime import datetime, timedelta
from typing import List, Dict, Optional

# 导入数据源管理器
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from data_sources.manager import DataSourceManager
from data_sources.base import DataCategory


class SyncService:
    """数据同步服务 - 自动使用项目数据源"""

    def __init__(self, db_path: str = None):
        if db_path:
            self.db_path = db_path
        else:
            current_dir = os.path.dirname(os.path.abspath(__file__))
            backend_dir = os.path.dirname(os.path.dirname(current_dir))
            project_root = os.path.dirname(backend_dir)
            self.db_path = os.path.join(project_root, 'data', 'football_v2.db')

        # 初始化数据源管理器
        self.manager = DataSourceManager()

    def _get_db(self) -> sqlite3.Connection:
        """获取数据库连接"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    # ==================== 主入口 ====================

    def start_sync(self, leagues: List[str] = None) -> Dict:
        """
        启动同步服务（前端打开时调用）
        自动使用数据源管理器获取数据

        Args:
            leagues: 要同步的联赛列表，默认同步所有联赛
        """
        print(f"[{datetime.now()}] 开始同步服务...")

        results = {
            "started_at": datetime.now().isoformat(),
            "finished_matches": None,
            "future_matches": None,
            "success": True
        }

        # 1. 同步已结束的比赛
        print("[1/2] 同步已结束比赛...")
        finished_result = self.sync_finished_matches()
        results["finished_matches"] = finished_result

        # 2. 同步未来赛程
        print("[2/2] 同步未来赛程...")
        future_result = self.sync_future_matches()
        results["future_matches"] = future_result

        results["completed_at"] = datetime.now().isoformat()
        print(f"[{datetime.now()}] 同步完成")

        return results

    # ==================== 已结束比赛同步 ====================

    def sync_finished_matches(self, hours_ago: int = 2) -> Dict:
        """
        同步已结束的比赛
        使用数据源管理器自动获取结果
        """
        conn = self._get_db()
        cursor = conn.cursor()

        now = datetime.now()
        cutoff_time = now - timedelta(hours=hours_ago)

        # 查找需要更新的比赛
        cursor.execute('''
            SELECT m.match_id, m.match_date, m.match_time,
                   m.home_team_id, m.away_team_id,
                   ht.name_en as home_team, at.name_en as away_team,
                   l.name_en as league, l.league_code
            FROM matches m
            JOIN teams ht ON m.home_team_id = ht.team_id
            JOIN teams at ON m.away_team_id = at.team_id
            JOIN leagues l ON m.league_id = l.league_id
            WHERE m.status = 'scheduled'
            AND (
                m.match_date < ?
                OR (m.match_date = ? AND m.match_time < ?)
            )
            ORDER BY m.match_date DESC
        ''', (now.date().isoformat(), now.date().isoformat(), now.strftime('%H:%M')))

        matches_to_update = cursor.fetchall()
        conn.close()

        if not matches_to_update:
            return {"success": True, "message": "没有需要更新的比赛", "checked": 0, "updated": 0, "matches": []}

        print(f"  找到 {len(matches_to_update)} 场需要检查的比赛")

        # 使用数据源管理器获取比赛结果
        updated_matches = []
        for match in matches_to_update:
            result = self._fetch_result_from_sources(match)
            if result:
                updated_matches.append(result)

        return {
            "success": True,
            "message": f"检查了 {len(matches_to_update)} 场比赛，更新了 {len(updated_matches)} 场",
            "checked": len(matches_to_update),
            "updated": len(updated_matches),
            "matches": updated_matches
        }

    def _fetch_result_from_sources(self, match: sqlite3.Row) -> Optional[Dict]:
        """使用数据源管理器获取比赛结果"""
        match_date = match['match_date']
        home_team = match['home_team']
        away_team = match['away_team']

        # 方法1: 直接调用Sportmonks API获取历史比赛结果（最可靠）
        try:
            result = self._fetch_from_sportmonks(match_date, home_team, away_team)
            if result:
                self._update_match_in_db(match['match_id'], result)
                print(f"    ✓ 从 Sportmonks API 获取成功: {home_team} {result['home_goals']}-{result['away_goals']} {away_team}")
                return result
        except Exception as e:
            print(f"    × Sportmonks API: {str(e)[:40]}")

        # 方法2: 使用数据源管理器获取比赛结果
        try:
            import asyncio
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

            # 尝试从实时比分数据源获取
            sources = self.manager.get_sources_by_category(DataCategory.LIVESCORES)

            for source in sources:
                try:
                    matches = loop.run_until_complete(
                        source.get_livescores(date=match_date)
                    )

                    for m in matches:
                        if (self._team_names_match(home_team, m.home_team) and
                            self._team_names_match(away_team, m.away_team)):
                            if m.home_score is not None and m.away_score is not None:
                                result = {
                                    "home_goals": m.home_score,
                                    "away_goals": m.away_score,
                                    "status": "finished",
                                    "source": source.config.name
                                }
                                self._update_match_in_db(match['match_id'], result)
                                print(f"    ✓ 从 {source.config.name} 获取成功")
                                loop.close()
                                return result
                except Exception as e:
                    print(f"    × {source.config.name}: {str(e)[:40]}")
                    continue

            # 方法3: 尝试从赛程数据源按日期获取
            from datetime import datetime, timedelta
            date_obj = datetime.strptime(match_date, '%Y-%m-%d')
            date_from = date_obj.strftime('%Y-%m-%d')
            date_to = (date_obj + timedelta(days=1)).strftime('%Y-%m-%d')

            fixture_sources = self.manager.get_sources_by_category(DataCategory.FIXTURES)
            for source in fixture_sources:
                try:
                    matches = loop.run_until_complete(
                        source.get_fixtures(league=None, from_date=date_from, to_date=date_to)
                    )

                    for m in matches:
                        if (self._team_names_match(home_team, m.home_team) and
                            self._team_names_match(away_team, m.away_team)):
                            if m.home_score is not None and m.away_score is not None:
                                result = {
                                    "home_goals": m.home_score,
                                    "away_goals": m.away_score,
                                    "status": "finished",
                                    "source": source.config.name
                                }
                                self._update_match_in_db(match['match_id'], result)
                                print(f"    ✓ 从 {source.config.name} (fixtures) 获取成功")
                                loop.close()
                                return result
                except Exception as e:
                    print(f"    × {source.config.name} (fixtures): {str(e)[:40]}")
                    continue

            loop.close()
        except Exception as e:
            print(f"    数据源管理器错误: {e}")

        return None

    def _fetch_from_sportmonks(self, match_date: str, home_team: str, away_team: str) -> Optional[Dict]:
        """直接调用Sportmonks API获取比赛结果"""
        import requests

        # Sportmonks API配置
        api_token = "4iBqABzPSz3JX65i166agPqQiliD4f79vD7o2NrJX1OmMBt7wHJ2ttvxdQoq"
        base_url = "https://api.sportmonks.com/v3/football"

        # 查询指定日期的比赛
        endpoint = f"/fixtures/date/{match_date}"
        params = {
            "api_token": api_token,
            "include": "participants;scores;league"
        }

        try:
            session = requests.Session()
            session.trust_env = False
            response = session.get(f"{base_url}{endpoint}", params=params, timeout=30)

            if response.status_code == 200:
                data = response.json()
                for item in data.get("data", []):
                    participants = item.get("participants", [])
                    if len(participants) >= 2:
                        # 获取主客队
                        api_home = ""
                        api_away = ""
                        for p in participants:
                            if p.get("meta", {}).get("location") == "home":
                                api_home = p.get("name", "")
                            else:
                                api_away = p.get("name", "")

                        # 检查队名匹配
                        if self._team_names_match(home_team, api_home) and self._team_names_match(away_team, api_away):
                            # 获取比分
                            scores = item.get("scores", [])
                            home_score = None
                            away_score = None
                            for s in scores:
                                if s.get("type") == "FT":
                                    home_score = s.get("home_score")
                                    away_score = s.get("away_score")

                            if home_score is not None and away_score is not None:
                                return {
                                    "home_goals": home_score,
                                    "away_goals": away_score,
                                    "status": "finished",
                                    "source": "sportmonks"
                                }
        except Exception as e:
            print(f"    Sportmonks API错误: {e}")

        return None

    def _update_match_in_db(self, match_id: str, result: Dict) -> bool:
        """更新数据库中的比赛"""
        conn = self._get_db()
        cursor = conn.cursor()

        try:
            cursor.execute('''
                UPDATE matches
                SET home_goals = ?, away_goals = ?, status = ?, updated_at = ?
                WHERE match_id = ?
            ''', (result['home_goals'], result['away_goals'], result['status'],
                  datetime.now().isoformat(), match_id))
            conn.commit()
            return True
        except Exception as e:
            print(f"    更新失败: {e}")
            return False
        finally:
            conn.close()

    # ==================== 未来赛程同步 ====================

    def sync_future_matches(self, months: int = 3) -> Dict:
        """同步未来赛程"""
        # 使用数据源管理器获取赛程
        try:
            import asyncio
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

            sources = self.manager.get_sources_by_category(DataCategory.FIXTURES)

            total_inserted = 0
            total_updated = 0

            for source in sources:
                try:
                    # 获取未来赛程
                    fixtures = loop.run_until_complete(
                        source.get_fixtures(from_date=datetime.now().date().isoformat())
                    )

                    for fixture in fixtures:
                        result = self._save_fixture(fixture)
                        if result == 'inserted':
                            total_inserted += 1
                        elif result == 'updated':
                            total_updated += 1

                except Exception as e:
                    print(f"    {source.config.name}: {str(e)[:40]}")
                    continue

            loop.close()

            return {
                "success": True,
                "message": f"新增 {total_inserted} 场，更新 {total_updated} 场",
                "inserted": total_inserted,
                "updated": total_updated
            }
        except Exception as e:
            return {"success": False, "message": str(e), "inserted": 0, "updated": 0}

    def sync_recent_finished_matches(self, days: int = 7) -> Dict:
        """同步最近已结束的比赛结果"""
        conn = self._get_db()
        cursor = conn.cursor()

        now = datetime.now()
        cutoff_date = now - timedelta(days=days)

        # 查找需要更新的比赛
        cursor.execute('''
            SELECT m.match_id, m.match_date, m.match_time,
                   m.home_team_id, m.away_team_id,
                   ht.name_en as home_team, at.name_en as away_team,
                   l.name_en as league, l.league_code
            FROM matches m
            JOIN teams ht ON m.home_team_id = ht.team_id
            JOIN teams at ON m.away_team_id = at.team_id
            JOIN leagues l ON m.league_id = l.league_id
            WHERE m.status = 'scheduled'
            AND m.match_date >= ?
            AND m.match_date < ?
            ORDER BY m.match_date DESC
        ''', (cutoff_date.date().isoformat(), now.date().isoformat()))

        matches_to_update = cursor.fetchall()
        conn.close()

        if not matches_to_update:
            return {"success": True, "message": "没有需要更新的比赛", "checked": 0, "updated": 0, "matches": []}

        print(f"  找到 {len(matches_to_update)} 场需要检查的比赛")

        # 使用数据源管理器获取比赛结果
        updated_matches = []
        for match in matches_to_update:
            result = self._fetch_result_from_sources(match)
            if result:
                updated_matches.append(result)

        return {
            "success": True,
            "message": f"检查了 {len(matches_to_update)} 场比赛，更新了 {len(updated_matches)} 场",
            "checked": len(matches_to_update),
            "updated": len(updated_matches),
            "matches": updated_matches
        }

    def sync_upcoming_fixtures(self, months: int = 3) -> Dict:
        """同步未来N个月的赛程"""
        return self.sync_future_matches(months=months)

    def _save_fixture(self, fixture) -> Optional[str]:
        """保存赛程到数据库"""
        conn = self._get_db()
        cursor = conn.cursor()

        try:
            # 获取队伍ID
            cursor.execute('SELECT team_id FROM teams WHERE name_en = ? OR name_cn = ?',
                          (fixture.home_team, fixture.home_team))
            home = cursor.fetchone()
            cursor.execute('SELECT team_id FROM teams WHERE name_en = ? OR name_cn = ?',
                          (fixture.away_team, fixture.away_team))
            away = cursor.fetchone()

            if not home or not away:
                return None

            # 检查是否已存在
            cursor.execute('''
                SELECT match_id, status FROM matches
                WHERE match_date = ? AND home_team_id = ? AND away_team_id = ?
            ''', (fixture.date, home[0], away[0]))
            existing = cursor.fetchone()

            if existing:
                # 如果状态是scheduled但有结果，更新
                if existing['status'] == 'scheduled' and fixture.home_score is not None:
                    cursor.execute('''
                        UPDATE matches SET home_goals = ?, away_goals = ?, status = 'finished', updated_at = ?
                        WHERE match_id = ?
                    ''', (fixture.home_score, fixture.away_score, datetime.now().isoformat(), existing['match_id']))
                    conn.commit()
                    return 'updated'
                return None

            # 插入新比赛
            match_id = f"sync_{fixture.date}_{home[0]}_{away[0]}"
            cursor.execute('''
                INSERT INTO matches (match_id, match_date, match_time, home_team_id, away_team_id, status, source)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (match_id, fixture.date, fixture.time or '15:00', home[0], away[0],
                  'finished' if fixture.home_score else 'scheduled', fixture.source))
            conn.commit()
            return 'inserted'

        except Exception as e:
            return None
        finally:
            conn.close()

    # ==================== 辅助方法 ====================

    def _team_names_match(self, name1: str, name2: str) -> bool:
        """检查两个队名是否匹配"""
        if not name1 or not name2:
            return False

        n1 = name1.lower().strip()
        n2 = name2.lower().strip()

        if n1 == n2:
            return True

        if n1 in n2 or n2 in n1:
            return True

        # 常见缩写映射
        abbreviations = {
            'man city': 'manchester city',
            'man united': 'manchester united',
            'man utd': 'manchester united',
            'tottenham': 'tottenham hotspur',
            'spurs': 'tottenham hotspur',
        }

        n1_norm = abbreviations.get(n1, n1)
        n2_norm = abbreviations.get(n2, n2)

        return n1_norm == n2_norm or n1_norm in n2_norm or n2_norm in n1_norm

    # ==================== 状态查询 ====================

    def get_league_season_status(self) -> List[Dict]:
        """获取各联赛赛季的同步状态"""
        conn = self._get_db()
        cursor = conn.cursor()

        # 查询各联赛赛季的比赛统计
        cursor.execute('''
            SELECT l.league_id, l.name_cn, l.name_en,
                   s.season_id, s.season_name,
                   COUNT(m.match_id) as matches_count,
                   SUM(CASE WHEN m.status = 'finished' THEN 1 ELSE 0 END) as finished_count,
                   SUM(CASE WHEN m.status = 'scheduled' THEN 1 ELSE 0 END) as scheduled_count,
                   SUM(CASE WHEN m.home_goals IS NULL AND m.status = 'finished' THEN 1 ELSE 0 END) as missing_scores
            FROM leagues l
            LEFT JOIN seasons s ON l.league_id = s.league_id
            LEFT JOIN matches m ON s.season_id = m.season_id
            GROUP BY l.league_id, s.season_id
            ORDER BY l.name_cn, s.season_name DESC
        ''')

        results = []
        for row in cursor.fetchall():
            results.append({
                "league_id": row['league_id'],
                "league_name": row['name_cn'] or row['name_en'],
                "season": row['season_name'],
                "matches_count": row['matches_count'] or 0,
                "finished_count": row['finished_count'] or 0,
                "scheduled_count": row['scheduled_count'] or 0,
                "missing_scores": row['missing_scores'] or 0
            })

        conn.close()
        return results

    def sync_league_season(self, league_id: int, season: str) -> Dict:
        """同步指定联赛赛季的数据"""
        conn = self._get_db()
        cursor = conn.cursor()

        # 获取联赛信息
        cursor.execute('SELECT name_cn, name_en FROM leagues WHERE league_id = ?', (league_id,))
        league = cursor.fetchone()
        if not league:
            return {"success": False, "error": "联赛不存在"}

        league_name = league['name_cn'] or league['name_en']

        # 查找该赛季需要更新的比赛
        cursor.execute('''
            SELECT m.match_id, m.match_date, m.match_time,
                   m.home_team_id, m.away_team_id,
                   ht.name_en as home_team, at.name_en as away_team
            FROM matches m
            JOIN seasons s ON m.season_id = s.season_id
            JOIN teams ht ON m.home_team_id = ht.team_id
            JOIN teams at ON m.away_team_id = at.team_id
            WHERE m.league_id = ? AND s.season_name = ? AND m.status = 'scheduled'
            AND m.match_date < ?
        ''', (league_id, season, datetime.now().date().isoformat()))

        matches_to_update = cursor.fetchall()
        conn.close()

        updated_count = 0
        for match in matches_to_update:
            result = self._fetch_result_from_sources(match)
            if result:
                updated_count += 1

        return {
            "success": True,
            "league": league_name,
            "season": season,
            "checked": len(matches_to_update),
            "updated": updated_count
        }


# 创建全局实例
sync_service = SyncService()
