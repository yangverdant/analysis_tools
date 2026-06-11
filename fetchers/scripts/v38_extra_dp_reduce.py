"""
v3.8关键实验: 在2-3区间降低亚盘draw blend
核心问题: 平手盘(|AH|=0)+2-3区间, AH blend=0.50+dt30叠加导致draw概率过高
实验: AH blend 0.50→0.30/0.40, 但只在dt30触发的比赛中降低
"""
import sys, io, json, sqlite3, math
from collections import defaultdict
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.path.insert(0, 'd:/football_tools')

DB_PATH = 'd:/football_tools/data/unified_football.db'

def normalize_probs(hp, dp, ap):
    total = hp + dp + ap
    if total <= 0:
        return 0.33, 0.33, 0.34
    return hp/total, dp/total, ap/total

DT_V34 = {'draw_threshold_0.3': 0.05, 'draw_threshold_0.28': 0.03, 'draw_threshold_0.26': 0.015}

def main():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    matches = conn.execute("""
        SELECT m.match_key, m.date, m.home_team, m.away_team,
               m.league_standard, m.home_score, m.away_score
        FROM matches m
        WHERE m.status='finished' AND m.home_score IS NOT NULL AND m.away_score IS NOT NULL
        AND EXISTS (SELECT 1 FROM match_data md WHERE md.match_key=m.match_key
                    AND md.source='model' AND md.data_type='model:enhanced_linear')
        AND EXISTS (SELECT 1 FROM match_data md WHERE md.match_key=m.match_key
                    AND md.source='factor' AND md.data_type='factor:euro_odds')
        ORDER BY m.date
    """).fetchall()

    lines = []
    def p(s=""):
        lines.append(s)

    p("=" * 70)
    p("  v3.8关键实验: 在dt30触发比赛中降低亚盘draw blend")
    p("=" * 70)

    # 实验策略: v3.4中的dt30 boost=0.05包含两部分效果:
    # 1. 亚盘draw校准(blend=0.50)增加draw概率
    # 2. draw_threshold_0.3的显式boost
    # 反推: 从v3.4存储结果中去掉dt30(0.05), 然后用新dt30(0.01)
    # 亚盘blend效果已经隐含在v3.4的最终概率中，无法精确反推
    #
    # 替代方案: 从v3.4概率出发, 只改dt30
    # v3.4的dp包含了: 赔率基础 + 信号覆盖 + 亚盘blend(0.50) + dt30(0.05)
    # v3.8: 去掉dt30(0.05), 加上dt30(0.01) → dp净减0.04
    # 进一步: 如果dp减0.04还不够, 可能需要在dt30触发时降低亚盘blend
    #
    # 实验: 在dt30触发的比赛中, 进一步降低draw概率
    # 模拟降低亚盘blend: dp减去额外的X pp

    for extra_dp_reduce in [0.00, 0.01, 0.02, 0.03, 0.04, 0.05]:
        DT_V38 = {0.30: 0.01, 0.28: 0.01, 0.26: 0.005}

        total_n = 0
        correct = 0
        brier = 0.0
        net_gain = 0
        dt30_n = 0
        dt30_correct = 0

        for m in matches:
            mk = m['match_key']
            actual = 'home' if m['home_score'] > m['away_score'] else \
                     'draw' if m['home_score'] == m['away_score'] else 'away'

            model_row = conn.execute(
                "SELECT data_json FROM match_data WHERE match_key=? AND source='model' AND data_type='model:enhanced_linear'",
                (mk,)).fetchone()
            model_data = json.loads(model_row['data_json'])
            hp = model_data.get('home_win_prob', 0.33)
            dp = model_data.get('draw_prob', 0.33)
            ap = model_data.get('away_win_prob', 0.34)
            flags = model_data.get('scenario_flags', [])
            pred_v34 = max(['home', 'draw', 'away'], key=lambda x: {'home': hp, 'draw': dp, 'away': ap}[x])

            odds_row = conn.execute(
                "SELECT data_json FROM match_data WHERE match_key=? AND source='factor' AND data_type='factor:euro_odds'",
                (mk,)).fetchone()
            odds_data = json.loads(odds_row['data_json'])
            odds_h = float(odds_data.get('raw', {}).get('avg_home_odds', 0) or odds_data.get('raw', {}).get('closing_avg_home_odds', 0) or 0)

            hp_x = hp; dp_x = dp; ap_x = ap

            # 去掉v3.4 draw_threshold
            for dt_flag, old_boost in DT_V34.items():
                if dt_flag in flags:
                    dp_x -= old_boost
                    hp_x += old_boost * (hp / (hp + ap))
                    ap_x += old_boost * (ap / (hp + ap))

            # 加上v3.8 draw_threshold
            for threshold in sorted(DT_V38.keys(), reverse=True):
                boost = DT_V38[threshold]
                if dt_flag_mapping(threshold, flags):
                    if boost > 0:
                        dp_x += boost
                        non_draw = hp_x + ap_x
                        if non_draw > 0:
                            hp_x -= boost * (hp_x / non_draw)
                            ap_x -= boost * (ap_x / non_draw)
                        hp_x, dp_x, ap_x = normalize_probs(hp_x, dp_x, ap_x)
                    break

            # 额外降低: 在dt30触发的比赛中降低draw概率
            if 'draw_threshold_0.3' in flags and extra_dp_reduce > 0:
                dp_x -= extra_dp_reduce
                non_draw = hp_x + ap_x
                if non_draw > 0:
                    hp_x += extra_dp_reduce * (hp_x / non_draw)
                    ap_x += extra_dp_reduce * (ap_x / non_draw)

            hp_x, dp_x, ap_x = normalize_probs(hp_x, dp_x, ap_x)
            pred_x = max(['home', 'draw', 'away'], key=lambda x: {'home': hp_x, 'draw': dp_x, 'away': ap_x}[x])

            correct += (1 if pred_x == actual else 0)
            if actual == 'home':   brier += (hp_x-1)**2 + dp_x**2 + ap_x**2
            elif actual == 'draw': brier += hp_x**2 + (dp_x-1)**2 + ap_x**2
            else:                  brier += hp_x**2 + dp_x**2 + (ap_x-1)**2
            total_n += 1

            if 'draw_threshold_0.3' in flags:
                dt30_n += 1
                if pred_x == actual: dt30_correct += 1

            if pred_x != pred_v34:
                if pred_x == actual: net_gain += 1
                elif pred_v34 == actual: net_gain -= 1

        p(f"\n  额外dp减少={extra_dp_reduce:.2f}: argmax={correct}/{total_n}={correct/total_n*100:.2f}% "
          f"Brier={brier/total_n:.4f} dt30={dt30_correct}/{dt30_n}={dt30_correct/dt30_n*100:.1f}% net={net_gain:+d}")

    p(f"\n{'=' * 70}")
    p("  实验完成")
    p("=" * 70)

    OUTPUT = 'd:/football_tools/fetchers/scripts/v38_extra_dp_reduce.txt'
    with open(OUTPUT, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))
    print(f"结果已写入 {OUTPUT}")


def dt_flag_mapping(threshold, flags):
    """检查v3.4存储的flags中是否有对应阈值的draw_threshold"""
    if threshold == 0.30 and 'draw_threshold_0.3' in flags:
        return True
    if threshold == 0.28 and 'draw_threshold_0.28' in flags:
        return True
    if threshold == 0.26 and 'draw_threshold_0.26' in flags:
        return True
    return False


if __name__ == "__main__":
    main()