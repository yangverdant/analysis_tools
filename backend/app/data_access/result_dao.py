"""lottery_results DAO"""

import logging
import sqlite3
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


class ResultDAO:
    def __init__(self, db_path: str):
        self.db_path = db_path

    def insert(self, result: Dict) -> bool:
        conn = sqlite3.connect(self.db_path)
        try:
            conn.execute("""
                INSERT OR REPLACE INTO lottery_results
                (lottery_match_id, home_goals_ft, away_goals_ft,
                 home_goals_ht, away_goals_ht,
                 spf_result, bf_result, bqc_result, rqspf_result)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                result['lottery_match_id'],
                result.get('home_goals_ft'),
                result.get('away_goals_ft'),
                result.get('home_goals_ht'),
                result.get('away_goals_ht'),
                result.get('spf_result'),
                result.get('bf_result'),
                result.get('bqc_result'),
                result.get('rqspf_result'),
            ))
            conn.commit()
            return True
        except Exception as e:
            logger.error(f"ResultDAO insert error: {e}")
            return False
        finally:
            conn.close()

    def find_by_match(self, lottery_match_id: str) -> Optional[Dict]:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            cursor = conn.execute("""
                SELECT * FROM lottery_results WHERE lottery_match_id = ?
            """, (lottery_match_id,))
            row = cursor.fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    def find_by_date(self, match_date: str) -> List[Dict]:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            cursor = conn.execute("""
                SELECT lr.* FROM lottery_results lr
                JOIN lottery_matches lm ON lr.lottery_match_id = lm.lottery_match_id
                WHERE lm.match_date = ?
            """, (match_date,))
            return [dict(row) for row in cursor.fetchall()]
        finally:
            conn.close()

    def find_without_validation(self, match_date: str) -> List[Dict]:
        """获取有结果但未验证的比赛"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            cursor = conn.execute("""
                SELECT lr.* FROM lottery_results lr
                JOIN lottery_matches lm ON lr.lottery_match_id = lm.lottery_match_id
                WHERE lm.match_date = ?
                AND lr.lottery_match_id NOT IN (
                    SELECT DISTINCT lottery_match_id FROM lottery_validation
                )
            """, (match_date,))
            return [dict(row) for row in cursor.fetchall()]
        finally:
            conn.close()