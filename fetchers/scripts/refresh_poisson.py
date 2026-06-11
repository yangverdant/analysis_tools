"""快速重提取poisson因素（升级到v2：从赔率推算lambda）"""
import sys, io, json, sqlite3
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.path.insert(0, 'd:/football_tools')

from fetchers.storage.crud import UnifiedStorage
from fetchers.analysis.factors.poisson import PoissonFactor

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

    factor = PoissonFactor()
    updated = 0
    from_odds = 0
    from_standings = 0

    for i, m in enumerate(matches):
        mk = m['match_key']
        result = factor.extract(mk, storage)

        if result.get('confidence', 0) > 0:
            src = result.get('raw', {}).get('lambda_source', '')
            if src == 'odds':
                from_odds += 1
            else:
                from_standings += 1

        storage.upsert_match_data(
            match_key=mk,
            source='factor',
            data_type='factor:poisson',
            data_json=json.dumps(result, ensure_ascii=False, default=str)
        )
        updated += 1

        if (i + 1) % 1000 == 0:
            print(f"  {i+1}/{len(matches)} (赔率源:{from_odds} 积分榜源:{from_standings})")

    print(f"\n完成! 更新 {updated} 场")
    print(f"  从赔率推算: {from_odds} 场 ({from_odds/updated*100:.1f}%)")
    print(f"  从积分榜推算: {from_standings} 场 ({from_standings/updated*100:.1f}%)")


if __name__ == "__main__":
    main()