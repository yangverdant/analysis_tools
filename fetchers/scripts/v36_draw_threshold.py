"""
draw_threshold规则详情: argmax方向和准确率
"""
import sys, io, json, sqlite3
from collections import defaultdict
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.path.insert(0, 'd:/football_tools')

DB_PATH = 'd:/football_tools/data/unified_football.db'

def main():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    lines = []
    def p(s=""):
        lines.append(s)

    matches = conn.execute("""
        SELECT m.match_key, m.date, m.home_team, m.away_team,
               m.league_standard, m.home_score, m.away_score
        FROM matches m
        WHERE m.status='finished' AND m.home_score IS NOT NULL AND m.away_score IS NOT NULL
        AND EXISTS (SELECT 1 FROM match_data md WHERE md.match_key=m.match_key
                    AND md.source='model' AND md.data_type='model:enhanced_linear')
        AND EXISTS (SELECT 1 FROM match_data md WHERE md.match_key=m.match_key
                    AND md.source='factor' AND md.data_type='factor:euro_odds')
    """).fetchall()

    p("=" * 70)
    p("  draw_threshold规则argmax分析")
    p("=" * 70)

    # 有draw_threshold的规则
    dt30_matches = []  # draw_threshold_30
    dt35_matches = []  # draw_threshold_35
    no_dt_matches = []  # 无draw_threshold

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
        pred = max(['home', 'draw', 'away'], key=lambda x: {'home': hp, 'draw': dp, 'away': ap}[x])
        flags = model_data.get('scenario_flags', [])

        odds_row = conn.execute(
            "SELECT data_json FROM match_data WHERE match_key=? AND source='factor' AND data_type='factor:euro_odds'",
            (mk,)).fetchone()
        odds_data = json.loads(odds_row['data_json'])
        market_dp = float(odds_data.get('raw', {}).get('draw_prob', 0) or 0)
        market_hp = float(odds_data.get('raw', {}).get('home_prob', 0) or 0)

        info = {
            'mk': mk, 'date': m['date'],
            'home': m['home_team'], 'away': m['away_team'],
            'league': m['league_standard'],
            'actual': actual, 'score': f"{m['home_score']}-{m['away_score']}",
            'pred': pred, 'hp': hp, 'dp': dp, 'ap': ap,
            'market_dp': market_dp, 'market_hp': market_hp,
        }

        if 'draw_threshold_30' in flags:
            dt30_matches.append(info)
        elif 'draw_threshold_35' in flags:
            dt35_matches.append(info)
        else:
            no_dt_matches.append(info)

    # 分析每组
    def analyze_group(name, group):
        n = len(group)
        if n == 0:
            p(f"\n  {name}: 0场")
            return

        pred_draw = sum(1 for m in group if m['pred'] == 'draw')
        pred_home = sum(1 for m in group if m['pred'] == 'home')
        pred_away = sum(1 for m in group if m['pred'] == 'away')
        actual_draw = sum(1 for m in group if m['actual'] == 'draw')
        actual_home = sum(1 for m in group if m['actual'] == 'home')
        actual_away = sum(1 for m in group if m['actual'] == 'away')

        # argmax准确率
        correct = sum(1 for m in group if m['pred'] == m['actual'])
        draw_correct = sum(1 for m in group if m['pred'] == 'draw' and m['actual'] == 'draw')
        home_correct = sum(1 for m in group if m['pred'] == 'home' and m['actual'] == 'home')
        away_correct = sum(1 for m in group if m['pred'] == 'away' and m['actual'] == 'away')

        avg_dp = sum(m['dp'] for m in group) / n * 100
        avg_market_dp = sum(m['market_dp'] for m in group) / n * 100

        p(f"\n  {name}: {n}场")
        p(f"  赔率均平局: {avg_market_dp:.1f}% 模型均平局: {avg_dp:.1f}% 实际平局: {actual_draw/n*100:.1f}%")
        p(f"  预测方向: home={pred_home} draw={pred_draw} away={pred_away}")
        p(f"  实际结果: home={actual_home} draw={actual_draw} away={actual_away}")
        p(f"  argmax准确率: {correct}/{n}={correct/n*100:.1f}%")
        if pred_draw > 0:
            p(f"  预测draw准确率: {draw_correct}/{pred_draw}={draw_correct/pred_draw*100:.1f}%")
        if pred_home > 0:
            p(f"  预测home准确率: {home_correct}/{pred_home}={home_correct/pred_home*100:.1f}%")
        if pred_away > 0:
            p(f"  预测away准确率: {away_correct}/{pred_away}={away_correct/pred_away*100:.1f}%")

        # 如果去掉draw_threshold，argmax会变什么？
        no_dt_correct = 0
        no_dt_pred_draw = 0
        no_dt_draw_correct = 0
        for m in group:
            # 反推去掉draw_threshold后的概率
            if 'draw_threshold_30' in name.lower() or '30' in name:
                adj_hp, adj_dp, adj_ap = m['hp'] + 0.06, m['dp'] - 0.06, m['ap']
            elif '35' in name:
                adj_hp, adj_dp, adj_ap = m['hp'] + 0.08, m['dp'] - 0.08, m['ap']
            else:
                adj_hp, adj_dp, adj_ap = m['hp'], m['dp'], m['ap']
            # 归一化
            total = adj_hp + adj_dp + adj_ap
            adj_hp, adj_dp, adj_ap = adj_hp/total, adj_dp/total, adj_ap/total
            adj_pred = max(['home', 'draw', 'away'], key=lambda x: {'home': adj_hp, 'draw': adj_dp, 'away': adj_ap}[x])
            if adj_pred == m['actual']:
                no_dt_correct += 1
            if adj_pred == 'draw':
                no_dt_pred_draw += 1
                if m['actual'] == 'draw':
                    no_dt_draw_correct += 1

        p(f"  如果去掉draw_threshold: argmax准确率={no_dt_correct}/{n}={no_dt_correct/n*100:.1f}% "
          f"预测draw={no_dt_pred_draw} 正确={no_dt_draw_correct}")

        # 有draw_threshold vs 无: 净差异
        dt_net = correct - no_dt_correct
        p(f"  draw_threshold净贡献: {dt_net:+d}场")

    analyze_group("draw_threshold_30", dt30_matches)
    analyze_group("draw_threshold_35", dt35_matches)
    analyze_group("无draw_threshold", no_dt_matches)

    # 核心问题: 如果用赔率平局概率直接做argmax呢？
    p(f"\n  === 赔率隐含概率直接argmax ===")
    odds_correct = 0
    odds_pred_draw = 0
    odds_draw_correct = 0
    for m in matches:
        mk = m['match_key']
        actual = 'home' if m['home_score'] > m['away_score'] else \
                 'draw' if m['home_score'] == m['away_score'] else 'away'

        odds_row = conn.execute(
            "SELECT data_json FROM match_data WHERE match_key=? AND source='factor' AND data_type='factor:euro_odds'",
            (mk,)).fetchone()
        odds_data = json.loads(odds_row['data_json'])
        raw = odds_data.get('raw', {})
        mhp = float(raw.get('home_prob', 0) or 0)
        mdp = float(raw.get('draw_prob', 0) or 0)
        map_ = float(raw.get('away_prob', 0) or 0)

        if mhp + mdp + map_ == 0: continue

        pred = max(['home', 'draw', 'away'], key=lambda x: {'home': mhp, 'draw': mdp, 'away': map_}[x])
        if pred == actual: odds_correct += 1
        if pred == 'draw': odds_pred_draw += 1
        if pred == 'draw' and actual == 'draw': odds_draw_correct += 1

    total_with_odds = len(matches)
    p(f"  赔率直接argmax: {odds_correct}/{total_with_odds}={odds_correct/total_with_odds*100:.1f}%")
    p(f"  赔率预测draw: {odds_pred_draw} 正确={odds_draw_correct} "
      f"precision={odds_draw_correct/max(odds_pred_draw,1)*100:.1f}%")

    # 模型argmax
    model_correct = 0
    model_pred_draw = 0
    model_draw_correct = 0
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
        pred = max(['home', 'draw', 'away'], key=lambda x: {'home': hp, 'draw': dp, 'away': ap}[x])
        if pred == actual: model_correct += 1
        if pred == 'draw': model_pred_draw += 1
        if pred == 'draw' and actual == 'draw': model_draw_correct += 1

    p(f"  模型argmax: {model_correct}/{total_with_odds}={model_correct/total_with_odds*100:.1f}%")
    p(f"  模型预测draw: {model_pred_draw} 正确={model_draw_correct} "
      f"precision={model_draw_correct/max(model_pred_draw,1)*100:.1f}%")

    p(f"\n{'=' * 70}")
    p("  分析完成")
    p("=" * 70)

    OUTPUT = 'd:/football_tools/fetchers/scripts/v36_draw_threshold.txt'
    with open(OUTPUT, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))
    print(f"结果已写入 {OUTPUT}")

    conn.close()


if __name__ == "__main__":
    main()