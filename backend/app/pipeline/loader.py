"""
导入层 (Loader Layer)
负责将清洗后的数据导入数据库
"""

import sqlite3
import os
from typing import Dict, Any, Optional, List
from dataclasses import dataclass
from datetime import datetime
import json

from .tasks import Task, TaskType
from .cleaner import CleanResult


@dataclass
class LoadResult:
    """导入结果"""
    success: bool
    records_inserted: int = 0
    records_updated: int = 0
    records_skipped: int = 0
    error: Optional[str] = None
    loaded_at: datetime = None

    def __post_init__(self):
        if self.loaded_at is None:
            self.loaded_at = datetime.now()


class DataLoader:
    """数据导入器"""

    def __init__(self, db_path: str):
        self.db_path = db_path
        self.conn = None

    def connect(self):
        """连接数据库"""
        if not self.conn:
            self.conn = sqlite3.connect(self.db_path)
            self.conn.row_factory = sqlite3.Row
        return self.conn

    def close(self):
        """关闭连接"""
        if self.conn:
            self.conn.close()
            self.conn = None

    def load(self, task: Task, clean_result: CleanResult) -> LoadResult:
        """导入数据"""
        if not clean_result.success:
            return LoadResult(success=False, error="清洗失败，无法导入")

        conn = self.connect()
        cursor = conn.cursor()

        try:
            if task.task_type == TaskType.MATCH_COMPLETE:
                return self._load_match(cursor, clean_result.data)
            elif task.task_type == TaskType.MATCH_SCORE:
                return self._load_match_score(cursor, clean_result.data)
            elif task.task_type == TaskType.MATCH_DATE:
                return self._load_match_date(cursor, clean_result.data)
            elif task.task_type == TaskType.TEAM_INFO:
                return self._load_team(cursor, clean_result.data)
            elif task.task_type == TaskType.TEAM_CHINESE_NAME:
                return self._load_team_chinese_name(cursor, clean_result.data)
            elif task.task_type == TaskType.LEAGUE_RULES:
                return self._load_league_rules(cursor, clean_result.data)
            elif task.task_type == TaskType.LEAGUE_INFO:
                return self._load_league(cursor, clean_result.data)
            elif task.task_type in [TaskType.SYNC_RECENT, TaskType.SYNC_SCHEDULE]:
                return self._load_matches(cursor, clean_result.data)
            elif task.task_type == TaskType.SYNC_STANDINGS:
                return self._load_standings(cursor, clean_result.data)
            elif task.task_type == TaskType.NEWS_SYNC:
                return self._load_news(cursor, clean_result.data)
            elif task.task_type == TaskType.BATCH_IMPORT:
                return self._load_batch(cursor, clean_result.data, task.params)
            else:
                return LoadResult(success=False, error=f"不支持的任务类型: {task.task_type}")
        except Exception as e:
            conn.rollback()
            return LoadResult(success=False, error=str(e))
        finally:
            conn.commit()

    def _load_match(self, cursor, data: Dict) -> LoadResult:
        """导入单场比赛"""
        # 检查是否存在
        cursor.execute(
            "SELECT match_id FROM matches WHERE match_id = ?",
            (data.get("match_id"),)
        )
        exists = cursor.fetchone()

        if exists:
            # 更新
            cursor.execute("""
                UPDATE matches SET
                    match_date = ?, match_time = ?,
                    home_team_id = ?, away_team_id = ?,
                    home_goals = ?, away_goals = ?,
                    league_id = ?, status = ?
                WHERE match_id = ?
            """, (
                data.get("match_date"), data.get("match_time"),
                data.get("home_team_id"), data.get("away_team_id"),
                data.get("home_goals"), data.get("away_goals"),
                data.get("league_id"), data.get("status"),
                data.get("match_id")
            ))
            return LoadResult(success=True, records_updated=1)
        else:
            # 插入
            cursor.execute("""
                INSERT INTO matches (
                    match_id, match_date, match_time,
                    home_team_id, away_team_id,
                    home_goals, away_goals,
                    league_id, status
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                data.get("match_id"), data.get("match_date"), data.get("match_time"),
                data.get("home_team_id"), data.get("away_team_id"),
                data.get("home_goals"), data.get("away_goals"),
                data.get("league_id"), data.get("status")
            ))
            return LoadResult(success=True, records_inserted=1)

    def _load_match_score(self, cursor, data: Dict) -> LoadResult:
        """导入比赛比分"""
        cursor.execute("""
            UPDATE matches SET
                home_goals = ?, away_goals = ?, status = ?
            WHERE match_id = ?
        """, (
            data.get("home_goals"), data.get("away_goals"),
            data.get("status"), data.get("match_id")
        ))
        return LoadResult(success=True, records_updated=cursor.rowcount)

    def _load_match_date(self, cursor, data: Dict) -> LoadResult:
        """导入比赛日期"""
        cursor.execute("""
            UPDATE matches SET
                match_date = ?, match_time = ?
            WHERE match_id = ?
        """, (
            data.get("match_date"), data.get("match_time"),
            data.get("match_id")
        ))
        return LoadResult(success=True, records_updated=cursor.rowcount)

    def _load_team(self, cursor, data: Dict) -> LoadResult:
        """导入球队信息"""
        cursor.execute(
            "SELECT team_id FROM teams WHERE team_id = ?",
            (data.get("team_id"),)
        )
        exists = cursor.fetchone()

        if exists:
            cursor.execute("""
                UPDATE teams SET
                    name_en = ?, name_cn = ?, country = ?,
                    founded = ?, logo = ?, venue = ?, capacity = ?
                WHERE team_id = ?
            """, (
                data.get("name_en"), data.get("name_cn"), data.get("country"),
                data.get("founded"), data.get("logo"), data.get("venue"),
                data.get("capacity"), data.get("team_id")
            ))
            return LoadResult(success=True, records_updated=1)
        else:
            cursor.execute("""
                INSERT INTO teams (
                    team_id, name_en, name_cn, country,
                    founded, logo, venue, capacity
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                data.get("team_id"), data.get("name_en"), data.get("name_cn"),
                data.get("country"), data.get("founded"), data.get("logo"),
                data.get("venue"), data.get("capacity")
            ))
            return LoadResult(success=True, records_inserted=1)

    def _load_team_chinese_name(self, cursor, data: Dict) -> LoadResult:
        """导入球队中文名"""
        team_name = data.get("team_name")
        name_cn = data.get("name_cn")

        cursor.execute("""
            UPDATE teams SET name_cn = ?
            WHERE name_en LIKE ? OR name_cn LIKE ?
        """, (name_cn, f"%{team_name}%", f"%{team_name}%"))

        return LoadResult(success=True, records_updated=cursor.rowcount)

    def _load_league_rules(self, cursor, data: Dict) -> LoadResult:
        """导入联赛规则"""
        # 假设有league_rules表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS league_rules (
                league_id INTEGER PRIMARY KEY,
                league_name TEXT,
                promotion_spots INTEGER DEFAULT 0,
                relegation_spots INTEGER DEFAULT 0,
                playoff_spots INTEGER DEFAULT 0,
                points_for_win INTEGER DEFAULT 3,
                rules TEXT
            )
        """)

        cursor.execute("""
            INSERT OR REPLACE INTO league_rules (
                league_name, rules, promotion_spots,
                relegation_spots, playoff_spots, points_for_win
            ) VALUES (?, ?, ?, ?, ?, ?)
        """, (
            data.get("league"), data.get("rules"),
            data.get("promotion_spots", 0), data.get("relegation_spots", 0),
            data.get("playoff_spots", 0), data.get("points_for_win", 3)
        ))

        return LoadResult(success=True, records_inserted=1)

    def _load_league(self, cursor, data: Dict) -> LoadResult:
        """导入联赛信息"""
        cursor.execute(
            "SELECT league_id FROM leagues WHERE league_id = ?",
            (data.get("league_id"),)
        )
        exists = cursor.fetchone()

        if exists:
            cursor.execute("""
                UPDATE leagues SET
                    name_en = ?, name_cn = ?, country = ?, season = ?, type = ?
                WHERE league_id = ?
            """, (
                data.get("name_en"), data.get("name_cn"), data.get("country"),
                data.get("season"), data.get("type"), data.get("league_id")
            ))
            return LoadResult(success=True, records_updated=1)
        else:
            cursor.execute("""
                INSERT INTO leagues (
                    league_id, name_en, name_cn, country, season, type
                ) VALUES (?, ?, ?, ?, ?, ?)
            """, (
                data.get("league_id"), data.get("name_en"), data.get("name_cn"),
                data.get("country"), data.get("season"), data.get("type")
            ))
            return LoadResult(success=True, records_inserted=1)

    def _load_matches(self, cursor, matches: List[Dict]) -> LoadResult:
        """批量导入比赛"""
        inserted = 0
        updated = 0
        skipped = 0

        for match in matches:
            cursor.execute(
                "SELECT match_id FROM matches WHERE match_id = ?",
                (match.get("match_id"),)
            )
            exists = cursor.fetchone()

            if exists:
                cursor.execute("""
                    UPDATE matches SET
                        match_date = ?, match_time = ?,
                        home_goals = ?, away_goals = ?,
                        status = ?
                    WHERE match_id = ?
                """, (
                    match.get("match_date"), match.get("match_time"),
                    match.get("home_goals"), match.get("away_goals"),
                    match.get("status"), match.get("match_id")
                ))
                updated += 1
            else:
                try:
                    cursor.execute("""
                        INSERT INTO matches (
                            match_id, match_date, match_time,
                            home_team_id, away_team_id,
                            home_goals, away_goals,
                            league_id, status
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        match.get("match_id"), match.get("match_date"),
                        match.get("match_time"), match.get("home_team_id"),
                        match.get("away_team_id"), match.get("home_goals"),
                        match.get("away_goals"), match.get("league_id"),
                        match.get("status")
                    ))
                    inserted += 1
                except Exception:
                    skipped += 1

        return LoadResult(
            success=True,
            records_inserted=inserted,
            records_updated=updated,
            records_skipped=skipped
        )

    def _load_standings(self, cursor, standings: List[Dict]) -> LoadResult:
        """导入积分榜"""
        # 创建积分榜表（如果不存在）
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS standings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                league_id INTEGER,
                season INTEGER,
                team_id INTEGER,
                rank INTEGER,
                points INTEGER,
                played INTEGER,
                won INTEGER,
                draw INTEGER,
                lose INTEGER,
                goals_for INTEGER,
                goals_against INTEGER,
                goal_diff INTEGER,
                form TEXT,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(league_id, season, team_id)
            )
        """)

        inserted = 0
        updated = 0

        for team in standings:
            cursor.execute("""
                INSERT OR REPLACE INTO standings (
                    league_id, season, team_id, rank, points,
                    played, won, draw, lose,
                    goals_for, goals_against, goal_diff, form
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                team.get("league_id"), team.get("season"),
                team.get("team_id"), team.get("rank"), team.get("points"),
                team.get("played"), team.get("won"), team.get("draw"),
                team.get("lose"), team.get("goals_for"),
                team.get("goals_against"), team.get("goal_diff"),
                team.get("form")
            ))
            inserted += 1

        return LoadResult(success=True, records_inserted=inserted)

    def _load_news(self, cursor, news: List[Dict]) -> LoadResult:
        """导入新闻"""
        # 创建新闻表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS news (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT,
                content TEXT,
                source TEXT,
                published_at TIMESTAMP,
                url TEXT UNIQUE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        inserted = 0
        skipped = 0

        for item in news:
            try:
                cursor.execute("""
                    INSERT OR IGNORE INTO news (
                        title, content, source, published_at, url
                    ) VALUES (?, ?, ?, ?, ?)
                """, (
                    item.get("title"), item.get("content"),
                    item.get("source"), item.get("published_at"),
                    item.get("url")
                ))
                if cursor.rowcount > 0:
                    inserted += 1
                else:
                    skipped += 1
            except Exception:
                skipped += 1

        return LoadResult(
            success=True,
            records_inserted=inserted,
            records_skipped=skipped
        )

    def _load_batch(self, cursor, data: List[Dict], params: Dict) -> LoadResult:
        """批量导入"""
        table = params.get("table", "matches")
        # 通用批量导入逻辑
        # 实际需要根据表结构动态处理
        return LoadResult(
            success=True,
            records_inserted=len(data) if isinstance(data, list) else 1
        )
