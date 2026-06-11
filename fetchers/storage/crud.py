"""
统一存储 CRUD 操作

核心类: UnifiedStorage
- upsert_*: 写入/更新数据
- get_*: 查询数据
- delete_*: 删除数据

设计原则:
- matches表只存锚定字段，match_data表存各源详情
- 写入时自动计算match_key
- 同一match_key+source+data_type 重复写入会覆盖(UPSERT)
"""

import json
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from fetchers.common.team_names import normalize_team_name
from fetchers.common.league_names import normalize_league_name
from fetchers.common.date_utils import normalize_date
from fetchers.common.match_key import make_match_key
from fetchers.storage.database import get_connection, get_db_path
from fetchers.storage.schema import DATA_TYPE_TO_TABLE

logger = logging.getLogger(__name__)


class UnifiedStorage:
    """统一数据存储"""

    def __init__(self, db_path: str = None):
        self.db_path = db_path or get_db_path()

    def _conn(self):
        return get_connection(self.db_path)

    # ==================== 写入操作 ====================

    def upsert_match_data(self, adapted_records: List[Dict[str, Any]]) -> int:
        """写入适配后的记录列表

        自动判断数据类型，路由到对应表。
        对于match类型，同时更新matches主表。
        """
        count = 0
        conn = self._conn()
        try:
            for record in adapted_records:
                data_type = record.get("_data_type", "unknown")
                source = record.get("source", record.get("_fetcher", "unknown"))

                if data_type in ("match", "odds", "prediction", "lineup"):
                    count += self._upsert_match_record(conn, record, source, data_type)
                elif data_type == "standing":
                    count += self._upsert_standing(conn, record, source)
                elif data_type == "player":
                    count += self._upsert_player(conn, record, source)
                elif data_type == "injury":
                    count += self._upsert_injury(conn, record, source)
                elif data_type == "news":
                    count += self._upsert_news(conn, record, source)
                elif data_type == "weather":
                    count += self._upsert_weather(conn, record, source)
                else:
                    logger.warning(f"未知数据类型: {data_type}, 跳过")

            conn.commit()
        except Exception as e:
            conn.rollback()
            logger.error(f"写入失败: {e}")
        finally:
            conn.close()
        return count

    def _upsert_match_record(self, conn, record: Dict, source: str,
                              data_type: str) -> int:
        """写入比赛相关数据（match/odds/prediction/lineup）"""
        match_key = record.get("match_key", "")
        if not match_key or match_key == "|":
            logger.debug(f"跳过无效match_key: {match_key}")
            return 0

        # 更新matches主表
        # date和time已在normalizer中拆分好，直接使用
        date = record.get("date", "")
        time_val = record.get("time", "")
        home_team = record.get("home_team", "")
        away_team = record.get("away_team", "")
        league = record.get("league", "")
        league_standard = record.get("league_standard",
                                      normalize_league_name(league) if league else "")
        season = record.get("season", "")
        home_score = record.get("home_score")
        away_score = record.get("away_score")
        venue = record.get("venue", "")
        referee = record.get("referee", "")

        conn.execute("""
            INSERT INTO matches (match_key, date, time, home_team, away_team,
                                  league, league_standard, season, status,
                                  home_score, away_score, venue, referee)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'scheduled', ?, ?, ?, ?)
            ON CONFLICT(match_key) DO UPDATE SET
                date = COALESCE(NULLIF(date, ''), excluded.date),
                time = COALESCE(NULLIF(time, ''), excluded.time),
                home_team = COALESCE(NULLIF(home_team, ''), excluded.home_team),
                away_team = COALESCE(NULLIF(away_team, ''), excluded.away_team),
                league = COALESCE(NULLIF(league, ''), excluded.league),
                league_standard = COALESCE(NULLIF(league_standard, ''), excluded.league_standard),
                home_score = COALESCE(excluded.home_score, matches.home_score),
                away_score = COALESCE(excluded.away_score, matches.away_score),
                venue = COALESCE(NULLIF(venue, ''), excluded.venue),
                referee = COALESCE(NULLIF(referee, ''), excluded.referee),
                updated_at = datetime('now', 'localtime')
        """, (match_key, date, time_val, home_team, away_team, league, league_standard,
              season, home_score, away_score, venue, referee))

        # 写入match_data
        data_json = json.dumps(record, ensure_ascii=False, default=str)
        conn.execute("""
            INSERT INTO match_data (match_key, source, data_type, data_json)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(match_key, source, data_type) DO UPDATE SET
                data_json = excluded.data_json,
                fetched_at = datetime('now', 'localtime')
        """, (match_key, source, data_type, data_json))

        return 1

    def _upsert_standing(self, conn, record: Dict, source: str) -> int:
        league = record.get("league", "")
        league_standard = record.get("league_standard",
                                      normalize_league_name(league) if league else "")
        season = record.get("season", "")
        team = record.get("team", "")
        team_standard = normalize_team_name(team) if team else ""

        if not league_standard or not team_standard:
            return 0

        data_json = json.dumps(record, ensure_ascii=False, default=str)
        conn.execute("""
            INSERT INTO standings (league, league_standard, season, team,
                                    team_standard, source, data_json)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(league_standard, season, team_standard, source) DO UPDATE SET
                data_json = excluded.data_json,
                fetched_at = datetime('now', 'localtime')
        """, (league, league_standard, season, team, team_standard, source, data_json))
        return 1

    def _upsert_player(self, conn, record: Dict, source: str) -> int:
        team = record.get("team", "")
        team_standard = normalize_team_name(team) if team else ""
        player_name = record.get("player_name", "")

        if not team_standard or not player_name:
            return 0

        data_json = json.dumps(record, ensure_ascii=False, default=str)
        conn.execute("""
            INSERT INTO players (team, team_standard, player_name, source, data_json)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(team_standard, player_name, source) DO UPDATE SET
                data_json = excluded.data_json,
                fetched_at = datetime('now', 'localtime')
        """, (team, team_standard, player_name, source, data_json))
        return 1

    def _upsert_injury(self, conn, record: Dict, source: str) -> int:
        team = record.get("team", "")
        team_standard = normalize_team_name(team) if team else ""
        player_name = record.get("player_name", "")
        date = record.get("date", "")
        league = record.get("league", "")

        if not team_standard or not player_name:
            return 0

        data_json = json.dumps(record, ensure_ascii=False, default=str)
        conn.execute("""
            INSERT INTO injuries (team, team_standard, player_name, date,
                                   league, source, data_json)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(team_standard, player_name, source) DO UPDATE SET
                data_json = excluded.data_json,
                fetched_at = datetime('now', 'localtime')
        """, (team, team_standard, player_name, date, league, source, data_json))
        return 1

    def _upsert_news(self, conn, record: Dict, source: str) -> int:
        title = record.get("title", "")
        url = record.get("url", "")
        date = record.get("date", "")
        matched_teams = record.get("matched_teams", "")

        data_json = json.dumps(record, ensure_ascii=False, default=str)
        conn.execute("""
            INSERT INTO news (source, title, url, date, matched_teams, data_json)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (source, title, url, date,
              json.dumps(matched_teams, ensure_ascii=False) if isinstance(matched_teams, list) else matched_teams,
              data_json))
        return 1

    def _upsert_weather(self, conn, record: Dict, source: str) -> int:
        match_key = record.get("match_key", "")
        city = record.get("city", "")
        date = record.get("date", "")

        data_json = json.dumps(record, ensure_ascii=False, default=str)
        conn.execute("""
            INSERT INTO weather (match_key, city, date, source, data_json)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(match_key, source) DO UPDATE SET
                data_json = excluded.data_json,
                fetched_at = datetime('now', 'localtime')
        """, (match_key, city, date, source, data_json))
        return 1

    # ==================== 查询操作 ====================

    def get_match(self, match_key: str) -> Optional[Dict]:
        """获取比赛的聚合数据（所有源）"""
        conn = self._conn()
        try:
            # 主表信息
            row = conn.execute(
                "SELECT * FROM matches WHERE match_key = ?", (match_key,)
            ).fetchone()
            if not row:
                return None

            result = dict(row)

            # 聚合各源数据
            rows = conn.execute(
                "SELECT source, data_type, data_json FROM match_data WHERE match_key = ?",
                (match_key,)
            ).fetchall()

            source_data = {}
            for r in rows:
                source_data.setdefault(r["source"], {})[r["data_type"]] = \
                    json.loads(r["data_json"])

            result["source_data"] = source_data
            result["sources"] = list(source_data.keys())
            return result
        finally:
            conn.close()

    def get_matches_by_date(self, date: str) -> List[Dict]:
        """获取某日全部比赛"""
        norm_date = normalize_date(date)
        conn = self._conn()
        try:
            rows = conn.execute(
                "SELECT * FROM matches WHERE date = ? ORDER BY league_standard, time",
                (norm_date,)
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def get_matches_by_league(self, league: str, season: str = None) -> List[Dict]:
        """获取某联赛比赛"""
        league_standard = normalize_league_name(league)
        conn = self._conn()
        try:
            if season:
                rows = conn.execute(
                    "SELECT * FROM matches WHERE league_standard = ? AND season = ? ORDER BY date",
                    (league_standard, season)
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM matches WHERE league_standard = ? ORDER BY date",
                    (league_standard,)
                ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def get_upcoming_matches(self, days: int = 7) -> List[Dict]:
        """获取未来N天未开始的比赛"""
        conn = self._conn()
        try:
            rows = conn.execute("""
                SELECT * FROM matches
                WHERE date >= date('now', 'localtime')
                  AND date <= date('now', '+' || ? || ' days', 'localtime')
                  AND status IN ('scheduled', '')
                ORDER BY date, league_standard
            """, (days,)).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def get_match_data(self, match_key: str, data_type: str = None,
                        source: str = None) -> List[Dict]:
        """获取比赛特定类型/来源的数据"""
        conn = self._conn()
        try:
            query = "SELECT * FROM match_data WHERE match_key = ?"
            params = [match_key]
            if data_type:
                query += " AND data_type = ?"
                params.append(data_type)
            if source:
                query += " AND source = ?"
                params.append(source)
            rows = conn.execute(query, params).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def get_standings(self, league: str, season: str = None) -> List[Dict]:
        """获取积分榜"""
        league_standard = normalize_league_name(league)
        conn = self._conn()
        try:
            if season:
                rows = conn.execute(
                    "SELECT * FROM standings WHERE league_standard = ? AND season = ?",
                    (league_standard, season)
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM standings WHERE league_standard = ?",
                    (league_standard,)
                ).fetchall()
            result = []
            for r in rows:
                item = json.loads(r["data_json"])
                item["_source"] = r["source"]
                item["_fetched_at"] = r["fetched_at"]
                result.append(item)
            return result
        finally:
            conn.close()

    def get_injuries(self, team: str = None, date: str = None) -> List[Dict]:
        """获取伤病数据"""
        conn = self._conn()
        try:
            query = "SELECT * FROM injuries WHERE 1=1"
            params = []
            if team:
                team_standard = normalize_team_name(team)
                query += " AND team_standard = ?"
                params.append(team_standard)
            if date:
                query += " AND date = ?"
                params.append(normalize_date(date))
            rows = conn.execute(query + " ORDER BY date", params).fetchall()
            return [json.loads(r["data_json"]) for r in rows]
        finally:
            conn.close()

    def get_weather(self, match_key: str) -> List[Dict]:
        """获取比赛天气"""
        conn = self._conn()
        try:
            rows = conn.execute(
                "SELECT * FROM weather WHERE match_key = ?", (match_key,)
            ).fetchall()
            return [json.loads(r["data_json"]) for r in rows]
        finally:
            conn.close()

    # ==================== 删除操作 ====================

    def delete_match_source(self, match_key: str, source: str,
                             data_type: str = None) -> int:
        """删除某源的某类数据"""
        conn = self._conn()
        try:
            if data_type:
                cursor = conn.execute(
                    "DELETE FROM match_data WHERE match_key = ? AND source = ? AND data_type = ?",
                    (match_key, source, data_type))
            else:
                cursor = conn.execute(
                    "DELETE FROM match_data WHERE match_key = ? AND source = ?",
                    (match_key, source))
            conn.commit()
            return cursor.rowcount
        finally:
            conn.close()

    def delete_old_news(self, days: int = 30) -> int:
        """删除N天前的新闻"""
        conn = self._conn()
        try:
            cursor = conn.execute(
                "DELETE FROM news WHERE date < date('now', '-' || ? || ' days', 'localtime')",
                (days,))
            conn.commit()
            return cursor.rowcount
        finally:
            conn.close()

    # ==================== 日志操作 ====================

    def log_fetch(self, fetcher: str, func_name: str, data_type: str,
                   status: str, record_count: int = 0, error_msg: str = None,
                   started_at: str = None):
        """记录采集日志"""
        conn = self._conn()
        try:
            conn.execute("""
                INSERT INTO fetch_log (fetcher, func_name, data_type, status,
                                        record_count, error_msg, started_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (fetcher, func_name, data_type, status, record_count, error_msg, started_at))
            conn.commit()
        finally:
            conn.close()

    # ==================== 统计 ====================

    def get_stats(self) -> Dict:
        """获取存储统计"""
        from fetchers.storage.database import get_table_stats
        return get_table_stats(self.db_path)

    def search_matches(self, team: str = None, date_from: str = None,
                        date_to: str = None, league: str = None,
                        status: str = None, limit: int = 100) -> List[Dict]:
        """搜索比赛"""
        conn = self._conn()
        try:
            query = "SELECT * FROM matches WHERE 1=1"
            params = []

            if team:
                team_standard = normalize_team_name(team)
                query += " AND (home_team = ? OR away_team = ?)"
                params.extend([team_standard, team_standard])
            if date_from:
                query += " AND date >= ?"
                params.append(normalize_date(date_from))
            if date_to:
                query += " AND date <= ?"
                params.append(normalize_date(date_to))
            if league:
                query += " AND league_standard = ?"
                params.append(normalize_league_name(league))
            if status:
                query += " AND status = ?"
                params.append(status)

            query += f" ORDER BY date DESC LIMIT {limit}"
            rows = conn.execute(query, params).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()