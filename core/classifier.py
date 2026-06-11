"""
8:30 赛事分类 — 日循环环节

职责:
1. 获取今日所有待分类比赛
2. 调用CompetitionRuleEngine生成MatchProfile
3. 将MatchProfile持久化
"""

import json
import logging
import sqlite3
from datetime import date
from typing import Dict, List, Optional

from .competition.engine import CompetitionRuleEngine, MatchProfile

logger = logging.getLogger(__name__)


class Classifier:
    """8:30 赛事分类模块"""

    def __init__(self, db_path: str, config: dict = None):
        self.db_path = db_path
        self.config = config or {}
        self.engine = CompetitionRuleEngine()

    def run(self, match_date: date = None) -> dict:
        """执行赛事分类"""
        if match_date is None:
            match_date = date.today()

        logger.info("赛事分类开始: %s", match_date)

        matches = self._get_matches_for_date(match_date)
        if not matches:
            logger.info("无待分类比赛")
            return {"date": str(match_date), "classified": 0, "profiles": []}

        profiles = []
        for match in matches:
            profile = self._classify_match(match)
            profiles.append({
                "lottery_match_id": match.get("lottery_match_id"),
                "match_info": match,
                "profile": profile.to_dict(),
            })
            self._save_profile(match, profile)

        type_counts = {}
        for p in profiles:
            ct = p["profile"]["competition_type"]
            line = p["profile"].get("line", "club")
            key = f"{ct}:{line}"
            type_counts[key] = type_counts.get(key, 0) + 1

        logger.info("分类完成: %s", type_counts)

        return {
            "date": str(match_date),
            "classified": len(profiles),
            "type_counts": type_counts,
            "profiles": profiles,
        }

    def classify_single(self, match: dict) -> MatchProfile:
        """分类单场比赛"""
        return self._classify_match(match)

    # ── 内部方法 ──

    def _classify_match(self, match: dict) -> MatchProfile:
        """从match字典生成MatchProfile"""
        return self.engine.classify(
            league_name=match.get("league_name", "") or match.get("league_name_cn", ""),
            competition_type_db=match.get("competition_type"),
            participant_type_db=match.get("participant_type"),
            match_phase=match.get("match_phase") or match.get("round"),
            is_neutral_venue=match.get("is_neutral_venue", False),
            home_team_type=match.get("home_team_type"),
            away_team_type=match.get("away_team_type"),
        )

    def _get_matches_for_date(self, match_date: date) -> List[dict]:
        """获取指定日期的比赛列表(含leagues JOIN)"""
        try:
            conn = sqlite3.connect(self.db_path, timeout=10)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            cursor.execute("""
                SELECT
                    lm.lottery_match_id,
                    lm.home_team_cn,
                    lm.away_team_cn,
                    lm.league_name_cn,
                    lm.match_date,
                    lm.handicap_line,
                    lm.home_team_id,
                    lm.away_team_id,
                    l.name_en       AS league_name,
                    l.league_id,
                    l.competition_type,
                    l.participant_type,
                    ht.team_type    AS home_team_type,
                    at.team_type    AS away_team_type
                FROM lottery_matches lm
                LEFT JOIN leagues l
                    ON lm.league_id = l.league_id
                    OR l.name_cn = lm.league_name_cn
                LEFT JOIN teams ht ON lm.home_team_id = ht.team_id
                LEFT JOIN teams at ON lm.away_team_id = at.team_id
                WHERE lm.match_date = ?
                ORDER BY lm.match_time
            """, (str(match_date),))

            matches = [dict(row) for row in cursor.fetchall()]
            conn.close()
            return matches

        except Exception as e:
            logger.error("获取比赛列表失败: %s", e)
            return []

    def _save_profile(self, match: dict, profile: MatchProfile):
        """将MatchProfile持久化"""
        try:
            conn = sqlite3.connect(self.db_path, timeout=10)
            cursor = conn.cursor()

            profile_json = json.dumps(profile.to_dict(), ensure_ascii=False)

            # 尝试更新lottery_matches.match_profile
            cursor.execute("PRAGMA table_info(lottery_matches)")
            columns = [row[1] for row in cursor.fetchall()]

            if "match_profile" in columns:
                cursor.execute("""
                    UPDATE lottery_matches
                    SET match_profile = ?
                    WHERE lottery_match_id = ?
                """, (profile_json, match.get("lottery_match_id")))
                conn.commit()
            else:
                # 存入analysis_reports
                cursor.execute("""
                    INSERT OR REPLACE INTO lottery_analysis_reports
                    (lottery_match_id, report_type, report_data, created_at)
                    VALUES (?, 'classification', ?, datetime('now'))
                """, (match.get("lottery_match_id"), profile_json))
                conn.commit()

            conn.close()

        except Exception as e:
            logger.debug("MatchProfile持久化失败: %s", e)
