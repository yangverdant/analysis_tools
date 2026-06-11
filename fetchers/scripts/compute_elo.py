"""预计算Elo等级分 — 按时间顺序遍历所有比赛"""

import sys
import io
import sqlite3
import json

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

from fetchers.common.team_names import normalize_team_name

DB_PATH = "d:/football_tools/data/unified_football.db"
ELO_INIT = 1500
ELO_K = 32


def compute_elo():
    conn = sqlite3.connect(DB_PATH)

    # 获取所有finished比赛，按日期排序
    matches = conn.execute("""
        SELECT m.match_key, m.date, m.home_team, m.away_team
        FROM matches m
        WHERE m.status='finished'
        ORDER BY m.date, m.match_key
    """).fetchall()

    ratings = {}  # team → elo

    ok = 0
    for m in matches:
        mk = m[0]
        date = m[1]
        home = normalize_team_name(m[2])
        away = normalize_team_name(m[3])

        # 获取比分
        row = conn.execute(
            "SELECT data_json FROM match_data WHERE match_key=? AND source='football-data.org' AND data_type='match'",
            (mk,)
        ).fetchone()
        if not row:
            continue

        data = json.loads(row[0])
        hs = data.get("home_score")
        aws = data.get("away_score")
        if hs is None or aws is None:
            continue

        try:
            hs, aws = int(hs), int(aws)
        except:
            continue

        home_elo = ratings.get(home, ELO_INIT)
        away_elo = ratings.get(away, ELO_INIT)

        # 实际结果
        if hs > aws:
            actual_h = 1.0
        elif hs == aws:
            actual_h = 0.5
        else:
            actual_h = 0.0

        # 期望结果
        exp_h = 1.0 / (1.0 + 10 ** ((away_elo - home_elo) / 400))

        # 更新
        home_elo_new = round(home_elo + ELO_K * (actual_h - exp_h))
        away_elo_new = round(away_elo - ELO_K * (actual_h - exp_h))

        ratings[home] = home_elo_new
        ratings[away] = away_elo_new

        # 存入match_data
        elo_json = {
            "home_elo": home_elo_new,
            "away_elo": away_elo_new,
            "home_elo_before": home_elo,
            "away_elo_before": away_elo,
            "actual_h": actual_h,
            "expected_h": round(exp_h, 4),
            "date": date,
        }
        conn.execute(
            "INSERT OR REPLACE INTO match_data (match_key, source, data_type, data_json) "
            "VALUES (?, 'system', 'elo', ?)",
            (mk, json.dumps(elo_json, ensure_ascii=False))
        )
        ok += 1
        if ok % 500 == 0:
            print(f"  {ok} matches processed")

    conn.commit()

    # 保存最终ratings
    ratings_json = json.dumps(ratings, ensure_ascii=False)
    conn.execute(
        "INSERT OR REPLACE INTO match_data (match_key, source, data_type, data_json) "
        "VALUES (?, 'system', 'elo_ratings', ?)",
        ('_global', ratings_json)
    )
    conn.commit()

    print(f"\n=== Elo计算完成 ===")
    print(f"  处理了 {ok} 场比赛")
    print(f"  {len(ratings)} 队有Elo数据")

    # Top 10
    top = sorted(ratings.items(), key=lambda x: -x[1])[:10]
    print("  Top 10:")
    for t, e in top:
        print(f"    {t}: {e}")

    # Bottom 5
    bot = sorted(ratings.items(), key=lambda x: x[1])[:5]
    print("  Bottom 5:")
    for t, e in bot:
        print(f"    {t}: {e}")

    conn.close()


if __name__ == "__main__":
    compute_elo()