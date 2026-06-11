"""
快速验证v3.5修正版模型 — 对动机不对称比赛做真实运行
"""
import sys, io, json
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.path.insert(0, 'd:/football_tools')

from fetchers.storage.crud import UnifiedStorage
from fetchers.analysis.models.enhanced_linear import EnhancedLinearModel

DB_PATH = 'd:/football_tools/data/unified_football.db'
import sqlite3

def main():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    storage = UnifiedStorage()
    model = EnhancedLinearModel()

    # 找几场动机不对称的比赛
    matches = conn.execute("""
        SELECT m.match_key, m.date, m.home_team, m.away_team,
               m.league_standard, m.home_score, m.away_score
        FROM matches m
        WHERE m.status='finished' AND m.home_score IS NOT NULL AND m.away_score IS NOT NULL
        AND EXISTS (SELECT 1 FROM match_data md WHERE md.match_key=m.match_key
                    AND md.source='factor' AND md.data_type='factor:motivation'
                    AND json_extract(md.data_json, '$.confidence') > 0)
        AND EXISTS (SELECT 1 FROM match_data md WHERE md.match_key=m.match_key
                    AND md.source='factor' AND md.data_type='factor:euro_odds')
        AND m.date >= '2026-04-01'
        ORDER BY m.date DESC
        LIMIT 30
    """).fetchall()

    print("=== v3.5修正版模型 — 最近30场有动机数据的比赛 ===")
    print(f"模型版本: {model.model_version}")
    print()

    for m in matches:
        mk = m['match_key']
        actual = 'home' if m['home_score'] > m['away_score'] else \
                 'draw' if m['home_score'] == m['away_score'] else 'away'

        try:
            result = model.run(mk, storage, force=True)
            hp = result.get('home_win_prob', 0)
            dp = result.get('draw_prob', 0)
            ap = result.get('away_win_prob', 0)
            pred = max(['home', 'draw', 'away'], key=lambda x: {'home': hp, 'draw': dp, 'away': ap}[x])
            flags = result.get('scenario_flags', [])
            ok = "✓" if pred == actual else "✗"

            # 加载动机和赔率
            mot_row = conn.execute(
                "SELECT data_json FROM match_data WHERE match_key=? AND source='factor' AND data_type='factor:motivation'",
                (mk,)).fetchone()
            odds_row = conn.execute(
                "SELECT data_json FROM match_data WHERE match_key=? AND source='factor' AND data_type='factor:euro_odds'",
                (mk,)).fetchone()

            mot_f = json.loads(mot_row['data_json']) if mot_row else {}
            odds_data = json.loads(odds_row['data_json']) if odds_row else {}
            raw_odds = odds_data.get('raw', {})
            odds_h = float(raw_odds.get('avg_home_odds', 0) or raw_odds.get('closing_avg_home_odds', 0) or 0)

            mot_raw = mot_f.get('raw', {})
            home_cat = mot_raw.get('home_category', '') or mot_f.get('home_category', '')
            away_cat = mot_raw.get('away_category', '') or mot_f.get('away_category', '')

            flag_str = ','.join(flags) if flags else '-'
            print(f"{m['date']} {m['home_team']} vs {m['away_team']} ({m['league_standard']})")
            print(f"  score={m['home_score']}-{m['away_score']} actual={actual} pred={pred}({ok})")
            print(f"  hp={hp*100:.1f}% dp={dp*100:.1f}% ap={ap*100:.1f}% odds_h={odds_h:.2f}")
            print(f"  mot: {home_cat} vs {away_cat} flags={flag_str}")
            print()
        except Exception as e:
            print(f"ERR {mk}: {str(e)[:80]}")
            print()

    conn.close()


if __name__ == "__main__":
    main()