"""lottery_predictions DAO"""

import json
import sqlite3
from typing import Dict, List, Optional


class PredictionDAO:
    def __init__(self, db_path: str):
        self.db_path = db_path

    def insert(self, prediction: Dict) -> int:
        conn = sqlite3.connect(self.db_path)
        try:
            cursor = conn.execute("""
                INSERT INTO lottery_predictions
                (lottery_match_id, match_id, play_type, predictions,
                 recommendation, confidence, confidence_level,
                 has_value_bet, value_bets, features_json, weights_json, model_version)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                prediction.get('lottery_match_id'),
                prediction.get('match_id'),
                prediction.get('play_type'),
                json.dumps(prediction.get('predictions'), ensure_ascii=False) if isinstance(prediction.get('predictions'), dict) else prediction.get('predictions'),
                prediction.get('recommendation'),
                prediction.get('confidence'),
                prediction.get('confidence_level'),
                prediction.get('has_value_bet', 0),
                json.dumps(prediction.get('value_bets'), ensure_ascii=False) if isinstance(prediction.get('value_bets'), list) else prediction.get('value_bets'),
                json.dumps(prediction.get('features_json'), ensure_ascii=False) if isinstance(prediction.get('features_json'), dict) else prediction.get('features_json'),
                json.dumps(prediction.get('weights_json'), ensure_ascii=False) if isinstance(prediction.get('weights_json'), dict) else prediction.get('weights_json'),
                prediction.get('model_version', 'v3.9.2'),
            ))
            conn.commit()
            return cursor.lastrowid
        finally:
            conn.close()

    def find_by_match(self, lottery_match_id: str) -> List[Dict]:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            cursor = conn.execute("""
                SELECT * FROM lottery_predictions WHERE lottery_match_id = ?
            """, (lottery_match_id,))
            return [dict(row) for row in cursor.fetchall()]
        finally:
            conn.close()