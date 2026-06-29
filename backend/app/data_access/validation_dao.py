"""lottery_validation DAO"""

import sqlite3
from datetime import datetime
from typing import Dict, List, Optional


class ValidationDAO:
    def __init__(self, db_path: str):
        self.db_path = db_path

    def insert(self, validation: Dict) -> bool:
        conn = sqlite3.connect(self.db_path)
        try:
            conn.execute("""
                INSERT INTO lottery_validation
                (prediction_id, lottery_match_id, play_type, predicted_result,
                 actual_result, is_correct, predicted_prob, brier_score,
                 attribution, attribution_detail, scenario_type, actionable, validated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                validation.get('prediction_id'),
                validation.get('lottery_match_id'),
                validation.get('play_type'),
                validation.get('predicted_result'),
                validation.get('actual_result'),
                validation.get('is_correct', 0),
                validation.get('predicted_prob'),
                validation.get('brier_score'),
                validation.get('attribution'),
                validation.get('attribution_detail'),
                validation.get('scenario_type'),
                validation.get('actionable', 0),
                datetime.now().isoformat(),
            ))
            conn.commit()
            return True
        except Exception:
            return False
        finally:
            conn.close()

    def get_accuracy_stats(self, days: int = 30, play_type: str = None) -> Dict:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            query = """
                SELECT play_type, COUNT(*) as total, SUM(is_correct) as correct,
                       AVG(brier_score) as avg_brier
                FROM lottery_validation
                WHERE validated_at >= date('now', ?)
                  AND predicted_result IS NOT NULL
                  AND actual_result IS NOT NULL
                  AND TRIM(predicted_result) NOT IN ('', '--', '未知', 'unknown', 'UNKNOWN')
                  AND TRIM(actual_result) NOT IN ('', '--', '未知', 'unknown', 'UNKNOWN')
            """
            params = [f'-{days} days']
            if play_type:
                query += " AND play_type = ?"
                params.append(play_type)
            query += " GROUP BY play_type"
            cursor = conn.execute(query, params)
            return {'days': days, 'stats': [dict(row) for row in cursor.fetchall()]}
        finally:
            conn.close()
