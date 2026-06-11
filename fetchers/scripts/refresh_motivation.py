"""快速重提取motivation因素（从categorical→numeric升级）"""
import sys, io, json, sqlite3
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.path.insert(0, 'd:/football_tools')

from fetchers.storage.crud import UnifiedStorage
from fetchers.analysis.factors.motivation import MotivationFactor

DB = 'd:/football_tools/data/unified_football.db'

def main():
    storage = UnifiedStorage()
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row

    matches = conn.execute(
        "SELECT match_key FROM matches "
        "WHERE status='finished' AND home_score IS NOT NULL AND away_score IS NOT NULL"
    ).fetchall()
    conn.close()

    factor = MotivationFactor()
    updated = 0
    has_data = 0

    for i, m in enumerate(matches):
        mk = m['match_key']
        result = factor.extract(mk, storage)

        if result.get('confidence', 0) > 0:
            has_data += 1

        # 更新到DB (直接写match_data表)
        conn2 = storage._conn()
        conn2.execute(
            "INSERT INTO match_data (match_key,source,data_type,data_json) "
            "VALUES (?,'factor','factor:motivation',?) "
            "ON CONFLICT(match_key,source,data_type) DO UPDATE SET "
            "data_json=excluded.data_json, fetched_at=datetime('now','localtime')",
            (mk, json.dumps(result, ensure_ascii=False, default=str))
        )
        conn2.commit()
        conn2.close()
        updated += 1

        if (i + 1) % 1000 == 0:
            print(f"  {i+1}/{len(matches)} (有数据: {has_data})")

    print(f"\n完成! 更新 {updated} 场，有数据 {has_data} 场 ({has_data/updated*100:.1f}%)")


if __name__ == "__main__":
    main()