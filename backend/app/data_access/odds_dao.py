"""lottery_odds DAO"""

import json
import logging
import sqlite3
from typing import Dict, Optional

logger = logging.getLogger(__name__)


class LotteryOddsDAO:
    def __init__(self, db_path: str):
        self.db_path = db_path

    def find_by_match(self, lottery_match_id: str) -> Dict[str, Dict]:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            cursor = conn.execute("""
                SELECT play_type, odds_data, opening_odds, latest_odds, update_time
                FROM lottery_odds WHERE lottery_match_id = ?
            """, (lottery_match_id,))
            result = {}
            for row in cursor.fetchall():
                pt = row['play_type']
                result[pt] = {
                    'current': json.loads(row['odds_data']) if isinstance(row['odds_data'], str) else row['odds_data'],
                    'opening': json.loads(row['opening_odds']) if row.get('opening_odds') and isinstance(row['opening_odds'], str) else row.get('opening_odds'),
                    'latest': json.loads(row['latest_odds']) if row.get('latest_odds') and isinstance(row['latest_odds'], str) else row.get('latest_odds'),
                    'update_time': row.get('update_time'),
                }
            return result
        finally:
            conn.close()

    def insert(self, lottery_match_id: str, play_type: str, odds_data: Dict) -> bool:
        conn = sqlite3.connect(self.db_path)
        try:
            conn.execute("""
                INSERT OR REPLACE INTO lottery_odds
                (lottery_match_id, play_type, odds_data, update_time)
                VALUES (?, ?, ?, datetime('now'))
            """, (
                lottery_match_id,
                play_type,
                json.dumps(odds_data, ensure_ascii=False) if isinstance(odds_data, dict) else odds_data,
            ))
            conn.commit()
            return True
        except Exception as e:
            logger.error(f"Odds insert error: {e}")
            return False
        finally:
            conn.close()