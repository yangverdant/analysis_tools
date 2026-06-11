"""data_source_health DAO"""

import sqlite3
from datetime import datetime
from typing import Dict, List, Optional


class DataSourceHealthDAO:
    def __init__(self, db_path: str):
        self.db_path = db_path

    def get_all(self) -> List[Dict]:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            cursor = conn.execute("SELECT * FROM data_source_health ORDER BY source_name")
            return [dict(row) for row in cursor.fetchall()]
        finally:
            conn.close()

    def update_status(self, source_name: str, status: str, success: bool = True):
        conn = sqlite3.connect(self.db_path)
        try:
            now = datetime.now().isoformat()
            if success:
                conn.execute("""
                    UPDATE data_source_health
                    SET status = ?, last_success = ?, updated_at = ?,
                        success_rate = CASE WHEN success_rate = 0 THEN 1.0
                                       ELSE success_rate * 0.9 + 0.1 END
                    WHERE source_name = ?
                """, (status, now, now, source_name))
            else:
                conn.execute("""
                    UPDATE data_source_health
                    SET status = ?, last_failure = ?, updated_at = ?,
                        success_rate = success_rate * 0.9
                    WHERE source_name = ?
                """, (status, now, now, source_name))
            conn.commit()
        finally:
            conn.close()