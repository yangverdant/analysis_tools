---
name: rqspf-integer-handicap-fix
description: "RQSPF整数盘口让平低估修复: 市场校准+投注门控+赔率fallback修复"
metadata: 
  node_type: memory
  type: project
  originSessionId: 8bfd2936-b7d2-484e-b643-212fd61d5dce
---

# 2026-07-13 RQSPF整数盘口让平修复

## 根因分析
- RQSPF让平(1)在handicap=1.0时严重低估: 模型预测让平13次(16.5%), 实际让平21次(26.3%)
- 根因: Poisson score_matrix条件化后, 让平概率(=主队恰好赢1球)产生极端值(0.01-0.45), 而市场始终在0.22-0.27
- 回测发现: 翻转为让平反而降低准确率(40%→33%), 因为让负(0)实际40%最高
- 真正问题不在预测方向, 而在投注选择: 让胜(3)赔率极低(0.745-1.78), EV为负

## 修复1: 市场校准让平概率 (analyze.py)
- `_compute_rqspf`新增: 整数盘口时, 若model_draw < max(0.18, market_draw-0.05), 校准至该下限
- 从top两个方向按比例扣除deficit, 保持概率归一化
- 校准后direction可能改变(若让平成为最高概率)
- 结果存入`market_calibrated_draw`字段(before/after/market_draw)

## 修复2: RQSPF投注门控 (push.py)
- `_rank_value_bets`: 整数盘口+让平概率>=0.20+预测非让平时, edge×0.3, confidence降为0.2
- 防止让平概率显著时仍投注让胜/让负(历史-92利润的根因)
- RQSPF play_accuracy从0.48降至0.40(反映实际40.3%准确率)

## 修复3: RQSPF赔率fallback修复 (push.py)
- `_get_real_odds`: RQSPF无实际赔率时返回0, 不再fallback到1/model_prob
- `_record_bets`: RQSPF无实际赔率时跳过, 不记录投注
- 修复了0.745荒谬赔率bug(来自1/0.738=1.35但实际记录0.745)

## IBA阈值保持不变
- 回测证明放宽integer_boundary_adjustment阈值反而降低准确率
- standard_probability_condition(draw>=0.22, gap<=0.08)和market_supports_draw(draw>=0.23, gap<=0.16, top<=0.39)保持原值
