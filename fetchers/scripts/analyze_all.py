"""
对DB中所有未分析的比赛批量运行因素提取+概率模型
"""
from fetchers.analysis import run_all_factors, run_model
from fetchers.storage.crud import UnifiedStorage
from fetchers.storage.database import get_connection, get_db_path

def analyze_all(force=False):
    storage = UnifiedStorage()
    conn = get_connection(get_db_path())

    all_mks = [r[0] for r in conn.execute('SELECT DISTINCT match_key FROM matches').fetchall()]
    if not force:
        analyzed = {r[0] for r in conn.execute("SELECT DISTINCT match_key FROM match_data WHERE source='factor'").fetchall()}
        need = [mk for mk in all_mks if mk not in analyzed]
    else:
        need = all_mks

    conn.close()
    print(f"Need analysis: {len(need)} / {len(all_mks)}")

    ok = err = 0
    for i, mk in enumerate(need):
        try:
            run_all_factors(mk, storage)
            run_model('basic_linear', mk, storage)
            ok += 1
        except Exception as e:
            err += 1
            if err <= 5:
                print(f"  ERR {mk}: {str(e)[:60]}")
        if (i+1) % 50 == 0:
            print(f"  Progress: {i+1}/{len(need)} (ok={ok} err={err})")

    print(f"Done: {ok} ok, {err} err, {len(need)} total")

if __name__ == "__main__":
    analyze_all()
