"""daily_cycle_state DAO — 日循环工作流状态持久化"""

import json
import sqlite3
from typing import Optional


class CycleStateDAO:
    def __init__(self, db_path: str):
        self.db_path = db_path

    def load(self, date_str: str) -> Optional[dict]:
        """加载某天的循环状态"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            cursor = conn.execute(
                "SELECT * FROM daily_cycle_state WHERE date = ?", (date_str,)
            )
            row = cursor.fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    def save(self, state: dict):
        """保存/更新循环状态"""
        conn = sqlite3.connect(self.db_path)
        try:
            conn.execute("""
                INSERT OR REPLACE INTO daily_cycle_state
                (date, current_node, perceive_result, collect_result,
                 intel_result, classify_result, analyze_result, push_result,
                 clv_result, validate_result, learn_result,
                 status, error_message, started_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
            """, (
                state.get('date'),
                state.get('current_node', 'perceive'),
                state.get('perceive_result'),
                state.get('collect_result'),
                state.get('intel_result'),
                state.get('classify_result'),
                state.get('analyze_result'),
                state.get('push_result'),
                state.get('clv_result'),
                state.get('validate_result'),
                state.get('learn_result'),
                state.get('status', 'running'),
                state.get('error_message'),
                state.get('started_at'),
            ))
            conn.commit()
        finally:
            conn.close()

    def update_node_result(self, date_str: str, node: str, result_json: str):
        """更新某节点的结果"""
        conn = sqlite3.connect(self.db_path)
        try:
            col = f"{node}_result"
            conn.execute(f"""
                UPDATE daily_cycle_state SET {col} = ?, updated_at = datetime('now')
                WHERE date = ?
            """, (result_json, date_str))
            conn.commit()
        finally:
            conn.close()