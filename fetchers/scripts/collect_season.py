"""
批量采集历史赛季数据

按日期遍历apifootball，采集指定联赛的赛程/赛果/赔率/预测。
然后经adapter适配存入unified_football.db。

用法:
    python -m fetchers.scripts.collect_season --league 253 --season 2024 --start 2024-04-01 --end 2024-12-15
    python -m fetchers.scripts.collect_season --league 307 --season 2024 --start 2024-04-01 --end 2024-11-15
    python -m fetchers.scripts.collect_season --league 39  --season 2024 --start 2024-08-01 --end 2025-05-30
"""

import argparse
import time
import random
import json
from datetime import datetime, timedelta
from typing import List, Dict, Optional

from fetchers.apifootball.get_data import get_fixtures, get_predictions
from fetchers.adapter.adapter import adapt
from fetchers.storage.crud import UnifiedStorage
from fetchers.common.team_names import normalize_team_name
from fetchers.common.league_names import normalize_league_name
from fetchers.common.match_key import make_match_key


# 各联赛赛季时间范围
SEASON_RANGES = {
    # league_id: {season: (start_date, end_date)}
    39: {  # Premier League
        2024: ("2024-08-09", "2025-05-25"),
        2025: ("2025-08-08", "2026-05-24"),
    },
    253: {  # Eliteserien
        2024: ("2024-03-31", "2024-12-08"),
        2025: ("2025-03-30", "2025-12-07"),
    },
    307: {  # Allsvenskan
        2024: ("2024-03-30", "2024-11-10"),
        2025: ("2025-03-29", "2025-11-09"),
    },
    140: {  # La Liga
        2024: ("2024-08-15", "2025-05-25"),
    },
    135: {  # Serie A
        2024: ("2024-08-17", "2025-05-25"),
    },
    78: {  # Bundesliga
        2024: ("2024-08-23", "2025-05-17"),
    },
    61: {  # Ligue 1
        2024: ("2024-08-16", "2025-05-17"),
    },
    266: {  # Primeira Liga
        2024: ("2024-08-09", "2025-05-18"),
        2023: ("2023-08-11", "2024-05-19"),
    },
    18: {  # Copa Libertadores
        2024: ("2024-02-20", "2024-11-30"),
        2023: ("2023-03-21", "2023-11-11"),
    },
    683: {  # Conference League
        2024: ("2024-07-11", "2025-05-29"),
        2023: ("2023-07-13", "2024-05-29"),
    },
}

# apifootball免费版: 10 req/min
REQUEST_INTERVAL = 7  # 秒


def collect_season(league_id: int, season: int,
                   start_date: str = None, end_date: str = None,
                   include_predictions: bool = True,
                   include_odds: bool = False) -> Dict:
    """采集一整个赛季数据"""

    # 确定日期范围
    if not start_date or not end_date:
        league_ranges = SEASON_RANGES.get(league_id, {})
        season_range = league_ranges.get(season)
        if season_range:
            start_date = start_date or season_range[0]
            end_date = end_date or season_range[1]
        else:
            print(f"[ERROR] 未配置 league_id={league_id} season={season} 的日期范围")
            return {"collected": 0, "skipped": 0}

    storage = UnifiedStorage()

    # 按周分片采集，避免单次请求返回过多数据
    start = datetime.strptime(start_date, "%Y-%m-%d")
    end = datetime.strptime(end_date, "%Y-%m-%d")
    chunks = []
    d = start
    while d <= end:
        chunk_end = min(d + timedelta(days=6), end)
        chunks.append((d.strftime("%Y-%m-%d"), chunk_end.strftime("%Y-%m-%d")))
        d = chunk_end + timedelta(days=1)

    print(f"[collect] league={league_id} season={season}")
    print(f"  日期范围: {start_date} ~ {end_date} ({len(chunks)} 周)")

    collected = 0
    skipped = 0
    match_ids_for_pred = []

    for i, (from_d, to_d) in enumerate(chunks):
        print(f"\n--- [{i+1}/{len(chunks)}] {from_d} ~ {to_d} ---")

        try:
            fixtures = get_fixtures(league=str(league_id), from_date=from_d, to_date=to_d)
        except Exception as e:
            print(f"  [ERROR] {str(e)[:60]}")
            time.sleep(30)
            continue

        if not fixtures:
            skipped += 1
            continue

        # 过滤目标联赛
        target = [f for f in fixtures
                  if str(f.get("league_id", "")) == str(league_id)]

        if not target:
            skipped += 1
            continue

        print(f"  找到 {len(target)} 场比赛")

        # 适配并存储
        adapted = adapt("apifootball", "get_livescores", target)
        count = storage.upsert_match_data(adapted)
        collected += count

        # 收集match_id用于后续采集预测
        for f in target:
            mid = f.get("match_id")
            if mid and f.get("home_score") is not None:
                match_ids_for_pred.append(mid)

        # 速率限制
        time.sleep(REQUEST_INTERVAL)

    # 批量采集预测(已完赛比赛)
    if include_predictions and match_ids_for_pred:
        print(f"\n=== 采集预测 ({len(match_ids_for_pred)} 场) ===")
        pred_count = 0
        for j, mid in enumerate(match_ids_for_pred):
            if j % 10 == 0:
                print(f"  预测进度: {j}/{len(match_ids_for_pred)}")
            try:
                pred = get_predictions(mid)
                if pred and pred.get("home_win_prob"):
                    adapted = adapt("apifootball", "get_predictions", [pred])
                    pred_count += storage.upsert_match_data(adapted)
            except Exception:
                pass
            time.sleep(REQUEST_INTERVAL)

        print(f"  预测存储: {pred_count}")

    print(f"\n[完成] league={league_id} season={season}")
    print(f"  比赛: {collected}, 跳过: {skipped}")
    return {"collected": collected, "skipped": skipped, "predictions": len(match_ids_for_pred)}


def collect_standings(league_id: int, season: int) -> int:
    """采集积分榜"""
    from fetchers.apifootball.get_data import get_standings

    print(f"\n[standings] league={league_id} season={season}")
    standings = get_standings(league=str(league_id), season=str(season))

    if not standings:
        print("  无数据")
        return 0

    storage = UnifiedStorage()
    adapted = adapt("apifootball", "get_standings", standings)
    count = storage.upsert_match_data(adapted)
    print(f"  存储: {count} 条")
    return count


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="采集历史赛季数据")
    parser.add_argument("--league", type=int, required=True, help="apifootball league_id")
    parser.add_argument("--season", type=int, required=True, help="赛季年份")
    parser.add_argument("--start", type=str, help="开始日期 YYYY-MM-DD")
    parser.add_argument("--end", type=str, help="结束日期 YYYY-MM-DD")
    parser.add_argument("--no-pred", action="store_true", help="跳过预测采集")
    args = parser.parse_args()

    # 先采集积分榜
    collect_standings(args.league, args.season)

    # 再采集赛程/赛果
    result = collect_season(
        league_id=args.league,
        season=args.season,
        start_date=args.start,
        end_date=args.end,
        include_predictions=not args.no_pred,
    )
    print(f"\n结果: {result}")
