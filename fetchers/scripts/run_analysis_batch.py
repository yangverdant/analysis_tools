"""
批量运行所有finished比赛的因素提取+模型预测
"""
import sys
import io
import time
import sqlite3

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

from fetchers.storage.crud import UnifiedStorage
from fetchers.analysis import run_all_factors, run_model

DB_PATH = "d:/football_tools/data/unified_football.db"


def get_finished_matches():
    conn = sqlite3.connect(DB_PATH)
    rows = conn.execute(
        "SELECT match_key FROM matches WHERE status='finished' ORDER BY date"
    ).fetchall()
    conn.close()
    return [r[0] for r in rows]


def count_existing():
    conn = sqlite3.connect(DB_PATH)
    f = conn.execute("SELECT COUNT(*) FROM match_data WHERE source='factor'").fetchone()[0]
    m = conn.execute("SELECT COUNT(*) FROM match_data WHERE source='model'").fetchone()[0]
    conn.close()
    return f, m


def run_batch(limit=None, force=False, model_name="enhanced_linear"):
    storage = UnifiedStorage()
    match_keys = get_finished_matches()

    if limit:
        match_keys = match_keys[:limit]

    total = len(match_keys)
    ok = err = skip = 0

    print(f"Running analysis on {total} matches (force={force})")
    f0, m0 = count_existing()
    print(f"Existing: {f0} factor, {m0} model records")
    t0 = time.time()

    for i, mk in enumerate(match_keys):
        if (i + 1) % 100 == 0:
            elapsed = time.time() - t0
            rate = (i + 1) / elapsed if elapsed > 0 else 0
            eta = (total - i - 1) / rate if rate > 0 else 0
            print(f"  [{i+1}/{total}] ok={ok} err={err} skip={skip} "
                  f"rate={rate:.1f}/s ETA={eta:.0f}s")

        try:
            factors = run_all_factors(mk, storage, force=force)
            active = sum(1 for v in factors.values()
                        if v.get("confidence", 0) > 0)
            if active == 0:
                skip += 1
                continue

            run_model(model_name, mk, storage, force=force)
            ok += 1
        except Exception as e:
            err += 1
            if err <= 5:
                print(f"  ERR {mk}: {str(e)[:80]}")

    elapsed = time.time() - t0
    fn, mn = count_existing()
    print(f"\n=== Done in {elapsed:.1f}s ===")
    print(f"  ok={ok} err={err} skip={skip}")
    print(f"  factor: {f0} → {fn} (+{fn-f0})")
    print(f"  model: {m0} → {mn} (+{mn-m0})")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--model", default="enhanced_linear")
    args = parser.parse_args()

    run_batch(limit=args.limit, force=args.force, model_name=args.model)