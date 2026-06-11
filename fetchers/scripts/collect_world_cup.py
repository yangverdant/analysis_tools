"""
采集FIFA世界杯数据 (2018, 2022, 2026)

数据源: apifootball (league_id=28)
存入: data/unified_football.db
"""

import sys
import io
import time
import json
import sqlite3

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

from fetchers.apifootball.config import API_KEY, BASE_URL
from fetchers.common.team_names import normalize_team_name
from fetchers.common.match_key import make_match_key

import requests

DB_PATH = "data/unified_football.db"


def fetch_world_cup(league_id, from_date, to_date):
    """从apifootball获取世界杯比赛数据"""
    session = requests.Session()
    session.trust_env = False
    session.proxies = {'http': None, 'https': None}

    params = {
        'action': 'get_events',
        'APIkey': API_KEY,
        'league_id': league_id,
        'from': from_date,
        'to': to_date,
    }
    r = session.get(BASE_URL, params=params, timeout=15)
    data = r.json()
    if isinstance(data, list):
        return data
    print(f"API错误: {data}")
    return []


def parse_wc_match(raw):
    """解析单场世界杯比赛"""
    home = raw.get("match_hometeam_name", "")
    away = raw.get("match_awayteam_name", "")
    date = raw.get("match_date", "")
    home_score = raw.get("match_hometeam_score")
    away_score = raw.get("match_awayteam_score")
    ht_home = raw.get("match_hometeam_halftime_score")
    ht_away = raw.get("match_awayteam_halftime_score")
    et_home = raw.get("match_hometeam_extra_score")
    et_away = raw.get("match_awayteam_extra_score")
    pen_home = raw.get("match_hometeam_penalty_score")
    pen_away = raw.get("match_awayteam_penalty_score")
    stage = raw.get("stage_name", "") or raw.get("fk_stage_key", "")
    round_num = raw.get("match_round")
    venue = raw.get("match_stadium", "")
    match_id = raw.get("match_id", "")
    status_raw = raw.get("match_status", "")

    home_std = normalize_team_name(home)
    away_std = normalize_team_name(away)
    match_key = make_match_key(date, home_std, away_std)

    if status_raw == "Finished":
        status = "finished"
    elif status_raw and "'" in status_raw:
        status = "live"
    else:
        status = "scheduled"

    # 赛季
    year = date[:4] if date else ""

    return {
        "match_key": match_key,
        "date": date,
        "home_team": home_std,
        "away_team": away_std,
        "league": "FIFA World Cup",
        "league_standard": "world_cup",
        "league_id": raw.get("league_id", "28"),
        "season": year,
        "status": status,
        "home_score": int(home_score) if home_score not in (None, "") else None,
        "away_score": int(away_score) if away_score not in (None, "") else None,
        "home_score_ht": int(ht_home) if ht_home not in (None, "") else None,
        "away_score_ht": int(ht_away) if ht_away not in (None, "") else None,
        "home_score_et": int(et_home) if et_home not in (None, "") else None,
        "away_score_et": int(et_away) if et_away not in (None, "") else None,
        "home_score_pen": int(pen_home) if pen_home not in (None, "") else None,
        "away_score_pen": int(pen_away) if pen_away not in (None, "") else None,
        "round": round_num if isinstance(round_num, int) else (int(round_num) if round_num and str(round_num).isdigit() else round_num),
        "stage": stage,
        "venue": venue,
        # match_data原始数据
        "match_id": str(match_id),
        "home_team_raw": home,
        "away_team_raw": away,
        "time": raw.get("match_time", ""),
        "goalscorer": raw.get("goalscorer", []),
        "statistics": raw.get("statistics", []),
        "lineup": raw.get("lineup", {}),
        "cards": raw.get("cards", []),
    }


def store_matches(records):
    """存储比赛数据到数据库"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    stored = 0

    for rec in records:
        mk = rec["match_key"]
        # 写matches表 (无league_id列)
        c.execute("""
            INSERT INTO matches (match_key, date, home_team, away_team, league,
                league_standard, season, status, home_score, away_score, venue)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(match_key) DO UPDATE SET
                home_score = COALESCE(excluded.home_score, matches.home_score),
                away_score = COALESCE(excluded.away_score, matches.away_score),
                status = excluded.status,
                league_standard = COALESCE(excluded.league_standard, matches.league_standard),
                venue = COALESCE(NULLIF(excluded.venue, ''), matches.venue),
                updated_at = datetime('now', 'localtime')
        """, (
            mk, rec["date"], rec["home_team"], rec["away_team"], rec["league"],
            rec["league_standard"], rec["season"], rec["status"],
            rec["home_score"], rec["away_score"], rec.get("venue", ""),
        ))

        # 写match_data表 — 完整数据
        data_json = json.dumps({
            k: v for k, v in rec.items()
            if k not in ("match_key",) and v is not None and v != [] and v != {}
        }, ensure_ascii=False, default=str)

        c.execute("""
            INSERT INTO match_data (match_key, source, data_type, data_json)
            VALUES (?, 'apifootball', 'wc_match', ?)
            ON CONFLICT(match_key, source, data_type) DO UPDATE SET
                data_json = excluded.data_json,
                fetched_at = datetime('now', 'localtime')
        """, (mk, data_json))

        stored += 1

    conn.commit()
    conn.close()
    return stored


def collect_world_cup():
    """采集2018/2022/2026三届世界杯"""
    editions = [
        ("2018", "2018-06-01", "2018-07-31"),
        ("2022", "2022-11-01", "2022-12-31"),
        ("2026", "2026-06-01", "2026-07-31"),
    ]

    total = 0

    for edition, from_date, to_date in editions:
        print(f"\n{'='*50}")
        print(f"采集 {edition} FIFA World Cup...")
        print(f"{'='*50}")

        raw_matches = fetch_world_cup(28, from_date, to_date)
        print(f"  获取 {len(raw_matches)} 场比赛")

        if not raw_matches:
            print(f"  无数据，跳过")
            continue

        records = [parse_wc_match(m) for m in raw_matches]
        stored = store_matches(records)
        total += stored
        print(f"  存储 {stored} 条记录")

        finished = sum(1 for r in records if r["status"] == "finished")
        scheduled = sum(1 for r in records if r["status"] == "scheduled")
        print(f"  已结束: {finished}, 未开始: {scheduled}")

        for r in records[:5]:
            score = f"{r['home_score']}-{r['away_score']}" if r.get("home_score") is not None else "vs"
            stage = r.get("stage", "") or f"R{r.get('round', '?')}"
            print(f"  {r['date']} {r['home_team']} {score} {r['away_team']} [{stage}]")

        time.sleep(1)

    # 验证
    print(f"\n{'='*50}")
    print(f"总计存储 {total} 条")
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    by_season = c.execute("""
        SELECT season, COUNT(*),
               SUM(CASE WHEN status='finished' THEN 1 ELSE 0 END),
               SUM(CASE WHEN status='scheduled' THEN 1 ELSE 0 END)
        FROM matches WHERE league_standard = 'world_cup'
        GROUP BY season ORDER BY season
    """).fetchall()
    for row in by_season:
        print(f"  {row[0]}: {row[1]}场 (结束{row[2]}, 未开始{row[3]})")

    md_count = c.execute("""
        SELECT COUNT(*) FROM match_data WHERE data_type = 'wc_match'
    """).fetchone()[0]
    print(f"  match_data原始数据: {md_count} 条")
    conn.close()


if __name__ == "__main__":
    collect_world_cup()
