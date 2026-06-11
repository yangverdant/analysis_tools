"""批量运行所有finished比赛的因素提取+模型预测 (v3.0+CLV)"""
import sys, io, time, sqlite3
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.path.insert(0, 'd:/football_tools')

from fetchers.storage.crud import UnifiedStorage
from fetchers.analysis import run_all_factors, run_model

DB_PATH = "d:/football_tools/data/unified_football.db"


def run_batch(force=True, limit=None):
    conn = sqlite3.connect(DB_PATH)
    match_keys = conn.execute(
        "SELECT match_key FROM matches WHERE status='finished' ORDER BY date"
    ).fetchall()
    conn.close()
    match_keys = [r[0] for r in match_keys]

    if limit:
        match_keys = match_keys[:limit]

    total = len(match_keys)
    print(f"Running analysis on {total} matches (force={force})", flush=True)

    storage = UnifiedStorage()
    ok = err = skip = 0
    t0 = time.time()

    for i, mk in enumerate(match_keys):
        try:
            factors = run_all_factors(mk, storage, force=force)
            active = sum(1 for v in factors.values() if v.get("confidence", 0) > 0)
            if active == 0:
                skip += 1
                continue
            run_model("enhanced_linear", mk, storage, force=force)
            run_model("chain", mk, storage, force=force)
            ok += 1
        except Exception as e:
            err += 1
            if err <= 5:
                print(f"  ERR {mk}: {str(e)[:80]}", flush=True)

        if (i + 1) % 500 == 0:
            elapsed = time.time() - t0
            rate = (i + 1) / elapsed if elapsed > 0 else 0
            eta = (total - i - 1) / rate if rate > 0 else 0
            print(f"  [{i+1}/{total}] ok={ok} err={err} skip={skip} "
                  f"rate={rate:.1f}/s ETA={eta:.0f}s", flush=True)

    elapsed = time.time() - t0
    print(f"\n=== Done in {elapsed:.1f}s ===", flush=True)
    print(f"  ok={ok} err={err} skip={skip}", flush=True)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--force", action="store_true", default=True)
    args = parser.parse_args()
    run_batch(force=args.force, limit=args.limit)
