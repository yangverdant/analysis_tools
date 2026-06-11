"""
采集伤病数据 — 从api-sports.io获取五大联赛伤病信息，存入injuries表
"""
import sys, io, time, json, sqlite3
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.path.insert(0, 'd:/football_tools')

from fetchers.api_sports.get_data import get_injuries
from fetchers.common.team_names import normalize_team_name
from fetchers.storage.crud import UnifiedStorage

DB_PATH = 'd:/football_tools/data/unified_football.db'

# 五大联赛ID (api-sports.io)
LEAGUES = {
    39: "Premier League",
    40: "Championship",
    135: "Serie A",
    140: "La Liga",
    61: "Ligue 1",
    78: "Bundesliga",
    79: "Bundesliga 2",
    88: "Eredivisie",
}


def collect_injuries(season=2025):
    storage = UnifiedStorage()
    conn = sqlite3.connect(DB_PATH)
    total = 0

    for league_id, league_name in LEAGUES.items():
        print(f"\n采集 {league_name} (id={league_id}) 伤病数据...")
        injuries = get_injuries(league=league_id, season=season)
        if not injuries:
            print(f"  无数据")
            continue

        stored = 0
        for inj in injuries:
            team_raw = inj.get("team", "")
            team_std = normalize_team_name(team_raw) if team_raw else ""
            player = inj.get("player", "")
            reason = inj.get("reason", "")
            inj_type = inj.get("type", "")

            if not team_std or not player:
                continue

            data_json = json.dumps(inj, ensure_ascii=False, default=str)
            try:
                conn.execute("""
                    INSERT INTO injuries (team, team_standard, player_name, date, league, source, data_json)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(team_standard, player_name, source) DO UPDATE SET
                        data_json = excluded.data_json,
                        fetched_at = datetime('now', 'localtime')
                """, (team_raw, team_std, player, "", league_name, "api-sports", data_json))
                stored += 1
            except Exception as e:
                if stored <= 3:
                    print(f"  存入失败: {str(e)[:60]}")

        conn.commit()
        total += stored
        print(f"  存储 {stored} 条伤病数据")

        time.sleep(1)

    conn.close()

    # 验证
    conn2 = sqlite3.connect(DB_PATH)
    count = conn2.execute("SELECT COUNT(*) FROM injuries").fetchone()[0]
    by_league = conn2.execute("""
        SELECT league, COUNT(*) FROM injuries GROUP BY league ORDER BY COUNT(*) DESC
    """).fetchall()
    print(f"\n=== 总计: {count} 条伤病数据 ===")
    for row in by_league:
        print(f"  {row[0]}: {row[1]}条")
    conn2.close()


if __name__ == "__main__":
    collect_injuries()