---
name: bf-bqc-period-analysis
description: "bf/bqc玩法准确率按时期分析(0701前后)及根因: bf旧报告用analysis_service未走_enhance_score_candidates, bqc 0701后回归是冷门偏态非bug"
metadata: 
  node_type: memory
  type: project
  originSessionId: 8bfd2936-b7d2-484e-b643-212fd61d5dce
---

# bf/bqc 0701前后准确率分析

## 数据 (2026-07-02)
按 validated_at < '2026-07-01' (before) vs >= (after):

| 玩法 | before | after | 变化 |
|------|--------|-------|------|
| spf  | 54.9% (90/164) | 62.5% (15/24) | +7.6pp |
| ou   | 54.3% (76/140) | 50.0% (12/24) | -4.3pp |
| rqspf| 48.9% (64/131) | 50.0% (12/24) | +1.1pp |
| bqc  | 42.2% (38/90)  | 5.3% (1/19)   | -36.9pp |
| bf   | 25.5% (35/137) | 37.5% (9/24)  | +12pp |

## bf根因 (已修复方向)
- before期: 报告由 `analysis_service.py` 生成, `analyses.bf.top_scores` 用 raw matrix probability 排序
- 验证 `_extract_score_candidates_from_report` 从 `bf.top_scores[:3]` 取候选, 经常得到 `1:1/1:0/0:1` 这种低分平局集
- after期: 报告由 `analyze.py` 生成, 已用 `_enhance_score_candidates` 做 SPF/OU/RQSPF 轴对齐
- bf准确率提升12pp印证 axis-aligned top3 比 raw top3 更准
- 仍存在的问题: top3 over-predicts 1:1 (39 cases vs 22 actual), 但候选多样性已大幅改善

## bqc根因 (非bug, 是样本偏态)
- after期19场, 10场预测"33"(胜胜)但只1场对
- 实际分布高度分散: 33(4)/03(4)/13(3)/10(2)/01(2)/00(2)/30(1)/11(1)
- after期含世界杯+国际杯赛, 半场→全场不再77.6%延续, 大量"半场冷门"出现
- before期"33"准确率51% (19/37), 证明模型在常规联赛对, 在杯赛偏不准
- 已加动态HT比例: total_goals=3+时比例0.40, =4+时0.38 (原固定0.45)
- 杯赛专项调整需要更大样本才能落地, 不能因19场就大改

## How to apply
- bf优化思路: 提升 `_enhance_score_candidates` 的候选多样性, 已通过 axis_match + structural_targets 实现
- bqc杯赛冷门: 考虑添加 `scenario_type` 加权, 但需要至少50场杯赛样本才能调
- 不要因19场小样本就激进改 bqc 转移矩阵, 会破坏before期的51%准确率
