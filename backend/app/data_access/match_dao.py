"""lottery_matches DAO"""

import sqlite3
import json
import logging
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


class LotteryMatchDAO:
    def __init__(self, db_path: str):
        self.db_path = db_path

    def find_by_id(self, lottery_match_id: str) -> Optional[Dict]:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            conn.execute("""
                SELECT lm.*, ht.name_en as home_team_name, at.name_en as away_team_name
                FROM lottery_matches lm
                LEFT JOIN teams ht ON lm.home_team_id = ht.team_id
                LEFT JOIN teams at ON lm.away_team_id = at.team_id
                WHERE lm.lottery_match_id = ?
            """, (lottery_match_id,))
            row = conn.fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    def find_by_date(self, match_date: str, status: str = None) -> List[Dict]:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            query = "SELECT * FROM lottery_matches WHERE match_date = ?"
            params = [match_date]
            if status:
                query += " AND sell_status = ?"
                params.append(status)
            cursor = conn.execute(query, params)
            return [dict(row) for row in cursor.fetchall()]
        finally:
            conn.close()

    def find_pending_analysis(self, limit: int = 50) -> List[Dict]:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            cursor = conn.execute("""
                SELECT lm.* FROM lottery_matches lm
                WHERE EXISTS (SELECT 1 FROM lottery_odds lo WHERE lo.lottery_match_id = lm.lottery_match_id)
                AND NOT EXISTS (SELECT 1 FROM lottery_analysis_reports lar WHERE lar.lottery_match_id = lm.lottery_match_id)
                AND lm.match_date >= date('now')
                ORDER BY lm.match_date, lm.match_time
                LIMIT ?
            """, (limit,))
            return [dict(row) for row in cursor.fetchall()]
        finally:
            conn.close()

    def insert(self, match: Dict) -> bool:
        conn = sqlite3.connect(self.db_path)
        try:
            conn.execute("""
                INSERT OR REPLACE INTO lottery_matches
                (lottery_match_id, match_id, home_team_id, away_team_id,
                 home_team_cn, away_team_cn, league_name_cn, match_num,
                 match_date, match_time, beijing_time, sell_status, sell_end_time,
                 play_types, handicap_line, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
            """, (
                match.get('lottery_match_id'),
                match.get('match_id'),
                match.get('home_team_id'),
                match.get('away_team_id'),
                match.get('home_team_cn'),
                match.get('away_team_cn'),
                match.get('league_name_cn'),
                match.get('match_num'),
                match.get('match_date'),
                match.get('match_time'),
                match.get('beijing_time'),
                match.get('sell_status', 'selling'),
                match.get('sell_end_time'),
                json.dumps(match.get('play_types', []), ensure_ascii=False) if isinstance(match.get('play_types'), list) else match.get('play_types'),
                match.get('handicap_line', 0),
            ))
            conn.commit()
            return True
        except Exception as e:
            logger.error(f"Match insert error: {e}")
            return False
        finally:
            conn.close()

    def update_team_ids(self, lottery_match_id: str, home_team_id: int, away_team_id: int) -> bool:
        conn = sqlite3.connect(self.db_path)
        try:
            conn.execute("""
                UPDATE lottery_matches SET home_team_id = ?, away_team_id = ?,
                updated_at = datetime('now') WHERE lottery_match_id = ?
            """, (home_team_id, away_team_id, lottery_match_id))
            conn.commit()
            return conn.total_changes > 0
        finally:
            conn.close()

    def update_sell_status(self, match_date, status: str):
        conn = sqlite3.connect(self.db_path)
        try:
            conn.execute("""
                UPDATE lottery_matches SET sell_status = ? WHERE match_date = ?
            """, (status, str(match_date)))
            conn.commit()
        finally:
            conn.close()

    def batch_insert(self, matches: List[Dict]) -> int:
        count = 0
        for m in matches:
            if self.insert(m):
                count += 1
        return count