"""
数据访问层 - 体彩比赛DAO
"""

from typing import Dict, List, Optional, Any
import sqlite3
import json
from datetime import datetime

from ..schemas.lottery import LotteryMatch, LotteryOdds, LotteryPrediction, LotteryResult


class LotteryMatchDAO:
    """体彩比赛DAO"""

    def __init__(self, db_path: str):
        self.db_path = db_path

    def get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def find_by_id(self, lottery_match_id: str) -> Optional[Dict]:
        """根据ID查找"""
        conn = self.get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute("""
                SELECT lm.*,
                       ht.name_en as home_team_name_en,
                       ht.name_cn as home_team_name_cn,
                       at.name_en as away_team_name_en,
                       at.name_cn as away_team_name_cn
                FROM lottery_matches lm
                LEFT JOIN teams ht ON lm.home_team_id = ht.team_id
                LEFT JOIN teams at ON lm.away_team_id = at.team_id
                WHERE lm.lottery_match_id = ?
            """, (lottery_match_id,))

            row = cursor.fetchone()
            if not row:
                return None

            result = dict(row)
            if result['play_types']:
                result['play_types'] = json.loads(result['play_types'])

            return result

        finally:
            conn.close()

    def find_by_date(self, match_date: str, status: str = None) -> List[Dict]:
        """根据日期查找"""
        conn = self.get_connection()
        cursor = conn.cursor()

        try:
            query = "SELECT * FROM lottery_matches WHERE match_date = ?"
            params = [match_date]

            if status:
                query += " AND sell_status = ?"
                params.append(status)

            query += " ORDER BY match_time"

            cursor.execute(query, params)
            rows = cursor.fetchall()

            results = []
            for row in rows:
                result = dict(row)
                if result['play_types']:
                    result['play_types'] = json.loads(result['play_types'])
                results.append(result)

            return results

        finally:
            conn.close()

    def find_pending_analysis(self, limit: int = 50) -> List[Dict]:
        """查找待分析的比赛（有赔率但无分析报告）"""
        conn = self.get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute("""
                SELECT lm.* FROM lottery_matches lm
                WHERE EXISTS (
                    SELECT 1 FROM lottery_odds lo
                    WHERE lo.lottery_match_id = lm.lottery_match_id
                )
                AND NOT EXISTS (
                    SELECT 1 FROM lottery_analysis_reports lar
                    WHERE lar.lottery_match_id = lm.lottery_match_id
                )
                AND lm.match_date >= date('now')
                ORDER BY lm.match_date, lm.match_time
                LIMIT ?
            """, (limit,))

            return [dict(row) for row in cursor.fetchall()]

        finally:
            conn.close()

    def insert(self, match: Dict) -> bool:
        """插入比赛"""
        conn = self.get_connection()
        cursor = conn.cursor()

        try:
            # Dedup across sources: sporttery-era rows (match_num from sporttery)
            # and oddsfe-era rows (match_num = eid[-4:]) produce different
            # lottery_match_id values for the same real-world match. Before
            # inserting, look up by (home_team_cn, away_team_cn, match_date) —
            # if a row already exists (likely from oddsfe with correct beijing_time
            # and eid), preserve it and only refresh crawler fields. This prevents
            # the recurring "duplicate matches with wrong kickoff times" problem
            # where sporttery re-inserts rows that oddsfe already populated.
            existing_row = cursor.execute(
                """
                SELECT lottery_match_id FROM lottery_matches
                WHERE home_team_cn = ? AND away_team_cn = ? AND match_date = ?
                LIMIT 1
                """,
                (match['home_team_cn'], match['away_team_cn'], match['match_date'])
            ).fetchone()
            if existing_row:
                existing_id = existing_row['lottery_match_id'] if isinstance(existing_row, dict) else existing_row[0]
                cursor.execute("""
                    UPDATE lottery_matches SET
                        home_team_id = COALESCE(?, home_team_id),
                        away_team_id = COALESCE(?, away_team_id),
                        league_name_cn = COALESCE(?, league_name_cn),
                        match_num = ?,
                        handicap_line = ?,
                        play_types = ?,
                        sell_status = ?,
                        sell_end_time = COALESCE(?, sell_end_time),
                        match_time = COALESCE(?, match_time),
                        updated_at = CURRENT_TIMESTAMP
                    WHERE lottery_match_id = ?
                """, (
                    match.get('home_team_id'),
                    match.get('away_team_id'),
                    match.get('league_name_cn'),
                    match.get('match_num'),
                    match.get('handicap_line', 0),
                    json.dumps(match.get('play_types', [])),
                    match.get('sell_status', 'selling'),
                    match.get('sell_end_time'),
                    match.get('match_time'),
                    existing_id
                ))
                conn.commit()
                return True

            # Use INSERT OR IGNORE + UPDATE to preserve bridge fields (beijing_time, oddsfe_event_id)
            cursor.execute("""
                INSERT OR IGNORE INTO lottery_matches
                (lottery_match_id, match_id, home_team_id, away_team_id,
                 home_team_cn, away_team_cn, league_name_cn, match_num,
                 match_date, match_time, beijing_time, sell_status,
                 sell_end_time, play_types, handicap_line, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            """, (
                match['lottery_match_id'],
                match.get('match_id'),
                match.get('home_team_id'),
                match.get('away_team_id'),
                match['home_team_cn'],
                match['away_team_cn'],
                match.get('league_name_cn'),
                match.get('match_num'),
                match['match_date'],
                match.get('match_time'),
                match.get('beijing_time'),
                match.get('sell_status', 'selling'),
                match.get('sell_end_time'),
                json.dumps(match.get('play_types', [])),
                match.get('handicap_line', 0)
            ))

            if cursor.rowcount == 0:
                # Row already exists — update only crawler fields, preserve bridge fields
                cursor.execute("""
                    UPDATE lottery_matches SET
                        home_team_id = COALESCE(?, home_team_id),
                        away_team_id = COALESCE(?, away_team_id),
                        league_name_cn = COALESCE(?, league_name_cn),
                        match_num = ?,
                        handicap_line = ?,
                        play_types = ?,
                        sell_status = ?,
                        sell_end_time = COALESCE(?, sell_end_time),
                        match_time = COALESCE(?, match_time),
                        updated_at = CURRENT_TIMESTAMP
                    WHERE lottery_match_id = ?
                """, (
                    match.get('home_team_id'),
                    match.get('away_team_id'),
                    match.get('league_name_cn'),
                    match.get('match_num'),
                    match.get('handicap_line', 0),
                    json.dumps(match.get('play_types', [])),
                    match.get('sell_status', 'selling'),
                    match.get('sell_end_time'),
                    match.get('match_time'),
                    match['lottery_match_id']
                ))

            conn.commit()
            return True

        except Exception as e:
            print(f"Insert error: {e}")
            return False
        finally:
            conn.close()

    def update_team_ids(self, lottery_match_id: str, home_team_id: int, away_team_id: int) -> bool:
        """更新球队ID映射"""
        conn = self.get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute("""
                UPDATE lottery_matches
                SET home_team_id = ?, away_team_id = ?, updated_at = CURRENT_TIMESTAMP
                WHERE lottery_match_id = ?
            """, (home_team_id, away_team_id, lottery_match_id))

            conn.commit()
            return cursor.rowcount > 0

        finally:
            conn.close()

    def batch_insert(self, matches: List[Dict]) -> int:
        """批量插入"""
        success_count = 0
        for match in matches:
            if self.insert(match):
                success_count += 1
        return success_count


class LotteryOddsDAO:
    """体彩赔率DAO"""

    def __init__(self, db_path: str):
        self.db_path = db_path

    def get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def find_by_match(self, lottery_match_id: str) -> Dict[str, Dict]:
        """获取比赛的所有赔率"""
        conn = self.get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute("""
                SELECT play_type, odds_data, opening_odds, latest_odds, update_time
                FROM lottery_odds
                WHERE lottery_match_id = ?
            """, (lottery_match_id,))

            odds = {}
            for row in cursor.fetchall():
                play_type = row['play_type']
                odds[play_type] = {
                    'current': json.loads(row['odds_data']) if row['odds_data'] else {},
                    'opening': json.loads(row['opening_odds']) if row['opening_odds'] else {},
                    'latest': json.loads(row['latest_odds']) if row['latest_odds'] else {},
                    'update_time': row['update_time']
                }

            return odds

        finally:
            conn.close()

    def insert(self, lottery_match_id: str, play_type: str, odds_data: Dict) -> bool:
        """插入赔率"""
        conn = self.get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute("""
                INSERT OR REPLACE INTO lottery_odds
                (lottery_match_id, play_type, odds_data, update_time)
                VALUES (?, ?, ?, CURRENT_TIMESTAMP)
            """, (lottery_match_id, play_type, json.dumps(odds_data)))

            conn.commit()
            return True

        finally:
            conn.close()


class PredictionDAO:
    """预测记录DAO"""

    def __init__(self, db_path: str):
        self.db_path = db_path

    def get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def insert(self, prediction: Dict) -> int:
        """插入预测记录"""
        conn = self.get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute("""
                INSERT OR REPLACE INTO lottery_predictions
                (lottery_match_id, match_id, play_type, predictions,
                 recommendation, confidence, confidence_level,
                 has_value_bet, value_bets, features_json, weights_json, model_version)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                prediction['lottery_match_id'],
                prediction.get('match_id'),
                prediction['play_type'],
                json.dumps(prediction['predictions']),
                prediction.get('recommendation'),
                prediction.get('confidence'),
                prediction.get('confidence_level'),
                1 if prediction.get('value_bets') else 0,
                json.dumps(prediction.get('value_bets', [])),
                json.dumps(prediction.get('features', {})),
                json.dumps(prediction.get('weights', {})),
                prediction.get('model_version', '1.0')
            ))

            prediction_id = cursor.lastrowid
            conn.commit()
            return prediction_id

        finally:
            conn.close()

    def find_by_match(self, lottery_match_id: str) -> List[Dict]:
        """获取比赛的预测记录"""
        conn = self.get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute("""
                SELECT * FROM lottery_predictions
                WHERE lottery_match_id = ?
                ORDER BY created_at DESC
            """, (lottery_match_id,))

            results = []
            for row in cursor.fetchall():
                result = dict(row)
                result['predictions'] = json.loads(result['predictions']) if result['predictions'] else {}
                result['value_bets'] = json.loads(result['value_bets']) if result['value_bets'] else []
                results.append(result)

            return results

        finally:
            conn.close()


class ValidationDAO:
    """验证结果DAO"""

    def __init__(self, db_path: str):
        self.db_path = db_path

    def get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def insert(self, validation: Dict) -> bool:
        """插入验证结果"""
        conn = self.get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute("""
                INSERT INTO lottery_validation
                (prediction_id, lottery_match_id, play_type,
                 predicted_result, actual_result, is_correct,
                 predicted_prob, brier_score)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                validation['prediction_id'],
                validation['lottery_match_id'],
                validation['play_type'],
                validation['predicted_result'],
                validation['actual_result'],
                validation['is_correct'],
                validation.get('predicted_prob'),
                validation.get('brier_score')
            ))

            conn.commit()
            return True

        finally:
            conn.close()

    def get_accuracy_stats(self, days: int = 30, play_type: str = None) -> Dict:
        """获取准确率统计"""
        conn = self.get_connection()
        cursor = conn.cursor()

        try:
            query = """
                SELECT
                    COUNT(*) as total,
                    SUM(is_correct) as correct,
                    AVG(brier_score) as avg_brier_score
                FROM lottery_validation
                WHERE validated_at >= date('now', ?)
            """
            params = [f'-{days} days']

            if play_type:
                query += " AND play_type = ?"
                params.append(play_type)

            cursor.execute(query, params)
            row = cursor.fetchone()

            if row and row['total']:
                return {
                    'total': row['total'],
                    'correct': row['correct'],
                    'accuracy': row['correct'] / row['total'],
                    'avg_brier_score': row['avg_brier_score']
                }

            return {'total': 0, 'correct': 0, 'accuracy': 0, 'avg_brier_score': None}

        finally:
            conn.close()


class ReportDAO:
    """分析报告DAO"""

    def __init__(self, db_path: str):
        self.db_path = db_path

    def get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def find_by_match(self, lottery_match_id: str) -> Optional[Dict]:
        """获取比赛的最新报告"""
        conn = self.get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute("""
                SELECT report_data, created_at FROM lottery_analysis_reports
                WHERE lottery_match_id = ? AND report_type IN ('prediction', 'full')
                ORDER BY created_at DESC LIMIT 1
            """, (lottery_match_id,))

            row = cursor.fetchone()
            if row:
                return {
                    'report': json.loads(row['report_data']),
                    'created_at': row['created_at']
                }
            return None

        finally:
            conn.close()

    def insert(self, lottery_match_id: str, report_data: Dict, match_id: int = None) -> int:
        """插入报告"""
        conn = self.get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute("""
                INSERT INTO lottery_analysis_reports
                (lottery_match_id, match_id, report_type, report_data)
                VALUES (?, ?, 'full', ?)
            """, (lottery_match_id, match_id, json.dumps(report_data)))

            report_id = cursor.lastrowid
            columns = {row[1] for row in cursor.execute("PRAGMA table_info(lottery_analysis_reports)").fetchall()}
            if "is_stale" in columns:
                cursor.execute(
                    """
                    UPDATE lottery_analysis_reports
                    SET is_stale = CASE WHEN report_id = ? THEN 0 ELSE 1 END
                    WHERE lottery_match_id = ?
                      AND report_type IN ('prediction', 'full')
                    """,
                    (report_id, lottery_match_id),
                )
            conn.commit()
            return report_id

        finally:
            conn.close()
