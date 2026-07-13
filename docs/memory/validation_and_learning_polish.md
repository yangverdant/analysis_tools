---
name: validation_and_learning_polish
description: 次日复盘+参数学习打磨——结果获取、翻车归因、场景准确率、参数自学习闭环、Brier分数、model_params_history
metadata: 
  node_type: memory
  type: project
  originSessionId: d2e763d6-7730-4e83-a6e7-3cc8d939df30
---

## 次日复盘 + 参数学习 打磨

### 次日6:00 结果获取

**数据源选择:**
1. oddsfe schedule API (最全) — 通过source_mapping_bridge.oddsfe_event_id查询
2. sporttery结果API — `getMatchResultV1.qry?date={date}`
3. apifootball — fixture结果

**优先级:** sporttery > oddsfe > apifootball
- 原因: 体彩官方结果决定SPF/BF/BQC/RQSPF的开奖，必须以体彩为准
- oddsfe作为补充: 确认比分一致性

**具体操作:**
```python
def fetch_results(match_date: date) -> list:
    # 1. sporttery结果API
    raw_results = LotteryCrawlerSync().crawl_results_sync(match_date)

    for result in raw_results:
        # 解析: matchId → lottery_match_id
        # 结果: homeScore, awayScore, spfResult, bfResult, bqcResult, rqspfResult
        # 写入lottery_results表

        # 异常: sporttery结果格式可能与lottery_match_id不匹配
        # sporttery返回的matchId格式可能是数字不是完整的lottery_match_id
        # 需要: matchId → 补全为 YYYYMMDD + matchNum 格式

    # 2. 更新sell_status
    # 所有昨天sell_status='selling'的 → 改为'finished'
    UPDATE lottery_matches SET sell_status='finished'
    WHERE match_date=? AND sell_status='selling'

    # 3. 更新data_source_health
    update_source_health('sporttery', success=True)
```

**异常场景:**
- oddsfe结果延迟(有些比赛结果要几小时后才更新) → 6点拿不到就12点重试
- 体彩和oddsfe比分不一致(加时赛进球归属) → 以体彩官方结果为准
- 结果拿不到 → 标记pending，不强制复盘
- 比赛取消/延期 → sell_status='postponed'，不产生结果记录

### 次日6:30 复盘对比

**已有基础设施:**
- `ValidationService` (backend/app/lottery/closed_loop/validation_service.py) — 完整的SPF/BF/BQC/RQSPF验证逻辑
- 支持Brier分数计算
- 支持批量验证(validate_date_range)

**当前断点:**
- lottery_results为空(0条) → ValidationService无法运行
- lottery_predictions的recommendation格式不一致(有'3'/'0'/'1'也有'unknown')
- 需要先有结果，才能验证

**修复: sync_results()的TODO需要完成**

当前sync_results()爬取了结果但没写入lottery_results:
```python
def sync_results(self, match_date=None):
    raw_results = self.crawler.crawl_results_sync(match_date)
    if not raw_results:
        return {'success': False, 'results': 0}
    # TODO: 写入 lottery_results 表  ← 这里！
    return {'success': True, 'results': len(raw_results)}
```

**修复方案:**
```python
def sync_results(self, match_date=None):
    raw_results = self.crawler.crawl_results_sync(match_date)
    if not raw_results:
        return {'success': False}

    saved = 0
    for result in raw_results:
        try:
            self.result_dao.insert(result)  # 新建ResultDAO
            saved += 1
        except Exception as e:
            logger.error(f"Save result error: {e}")

    return {'success': True, 'saved': saved}
```

### 翻车归因 — 最重要环节

**4级归因逻辑:**

```python
def attribute_error(prediction, result, features, profile):
    """预测错了，归因为什么错"""

    # Level 1: 赔率本身就接近? → 均势场
    max_prob = max(prediction.prob.values())
    if max_prob < 0.40:
        return {
            'attribution': 'close_match',
            'detail': f'最高概率{max_prob:.0%}, 三项接近，低置信度正常',
            'actionable': False  # 均势场不需要调整参数
        }

    # Level 2: 修正方向反了?
    if profile.use_friendly_intel:
        l5_adj = features.get('L5_friendly_intel', {})
        actual_direction = result.spf_result  # '3'/'1'/'0'
        predicted_direction = prediction.recommendation

        # 5维度推了哪个方向?
        if l5_adj.get('draw_adj', 0) > 0.05 and actual_direction != '1':
            return {
                'attribution': 'correction_direction_wrong',
                'detail': f'5维度推平局(+{l5_adj["draw_adj"]:.2f})但实际{spf_label(actual_direction)}',
                'which_dimension': identify_wrong_dimension(l5_adj, actual_direction),
                'actionable': True
            }

    # Level 3: 伤病情报缺失?
    if features.get('L6_injury', {}).get('status') == 'no_data':
        return {
            'attribution': 'intel_missing',
            'detail': '无伤病情报，可能有主力缺阵信息未捕获',
            'actionable': True  # 可以尝试改善情报采集
        }

    # Level 4: 新场景?
    return {
        'attribution': 'new_scenario',
        'detail': '首次遇到此类场景，记录特征供未来学习',
        'features_snapshot': features,  # 完整特征快照
        'actionable': True
    }
```

**5维度具体归因(当correction_direction_wrong时):**
```python
def identify_wrong_dimension(l5_adj, actual_result):
    """识别5维度中哪个维度的修正方向错了"""

    dimensions = {
        'employer': l5_adj.get('employer_adj', 0),
        'fan': l5_adj.get('fan_adj', 0),
        'motivation': l5_adj.get('motivation_adj', 0),
        'fatigue': l5_adj.get('fatigue_adj', 0),
        'venue': l5_adj.get('venue_adj', 0),
        'odds_tier': l5_adj.get('odds_tier_adj', 0),  # 赔率区间修正
    }

    # 找修正幅度最大的维度(它最有可能是错的)
    max_dim = max(dimensions, key=lambda k: abs(dimensions[k]))

    return {
        'wrong_dimension': max_dim,
        'correction_magnitude': dimensions[max_dim],
        'all_dimensions': dimensions
    }
```

### 场景准确率统计

按多个维度交叉统计:
```sql
-- 按赛事类型
SELECT lm.league_name_cn, COUNT(*), AVG(lv.is_correct), AVG(lv.brier_score)
FROM lottery_validation lv
JOIN lottery_predictions lp ON lv.prediction_id = lp.prediction_id
JOIN lottery_matches lm ON lp.lottery_match_id = lm.lottery_match_id
WHERE lv.validated_at >= date('now', '-30 days')
GROUP BY lm.league_name_cn

-- 按赔率区间(需要从lottery_odds获取)
SELECT
    CASE
        WHEN CAST(json_extract(lo.odds_data, '$.3') AS REAL) < 1.30 THEN 'hot_favorite'
        WHEN CAST(json_extract(lo.odds_data, '$.3') AS REAL) < 1.80 THEN 'favorite'
        WHEN CAST(json_extract(lo.odds_data, '$.3') AS REAL) < 2.50 THEN 'balanced'
        ELSE 'underdog'
    END as odds_tier,
    COUNT(*), AVG(lv.is_correct), AVG(lv.brier_score)
FROM lottery_validation lv
JOIN lottery_predictions lp ON lv.prediction_id = lp.prediction_id
JOIN lottery_matches lm ON lp.lottery_match_id = lm.lottery_match_id
JOIN lottery_odds lo ON lm.lottery_match_id = lo.lottery_match_id AND lo.play_type='spf'
WHERE lv.validated_at >= date('now', '-30 days')
GROUP BY odds_tier

-- 按置信度等级
SELECT lp.confidence_level, COUNT(*), AVG(lv.is_correct), AVG(lv.brier_score)
FROM lottery_validation lv
JOIN lottery_predictions lp ON lv.prediction_id = lp.prediction_id
WHERE lv.validated_at >= date('now', '-30 days')
GROUP BY lp.confidence_level
```

### 次日7:00 参数自学习

**核心原则(来自 [[feedback_data_driven_rules]] ):**
- 规则调整必须先DB数据验证方向，不能凭直觉
- 小幅微调(±10%)，不大幅改动
- 先回测历史数据验证方向，再应用到实战
- 每次调参记录old→new→reason→效果

**已有基础设施:**
- `WeightOptimizer` (backend/app/lottery/closed_loop/weight_optimizer.py) — 按准确率调整权重
- `model_params_history`表 — 已有schema，记录参数变更

**WeightOptimizer的当前问题:**
1. 无法追踪单个提取器的贡献(只能按confidence_level分组)
2. 调整幅度固定(±0.1)不考虑样本量
3. 没有回测验证步骤
4. 不区分赛事类型(联赛/杯赛/友谊赛用同一套权重)

**改进方案:**

```python
class EnhancedWeightOptimizer:
    """增强版权重优化器"""

    def optimize(self, days=30, min_samples=10):
        # 1. 按赛事类型分别统计
        for comp_type in ['league', 'domestic_cup', 'continental_cup', 'friendly', 'international_cup']:
            stats = self._get_stats_by_type(comp_type, days)

            if stats['total'] < min_samples:
                continue  # 样本不足，不调

            # 2. 对比模型 vs 赔率基线
            model_accuracy = stats['model_accuracy']
            odds_accuracy = stats['odds_accuracy']

            if model_accuracy > odds_accuracy:
                continue  # 模型比赔率好，不调

            # 3. 定位问题因子
            problem_factors = self._identify_problem_factors(stats)

            # 4. 小幅调整(±10%)
            for factor, current_weight in problem_factors:
                direction = self._determine_direction(factor, stats)
                new_weight = current_weight * (1 + direction * 0.10)

                # 5. 回测验证
                backtest_result = self._backtest(
                    factor, current_weight, new_weight,
                    comp_type, sample_days=365
                )

                if backtest_result['improved']:
                    # 6. 采纳并记录
                    self._apply_and_record(
                        factor, current_weight, new_weight,
                        reason=f'{comp_type}场景准确率{model_accuracy:.0%}<赔率{odds_accuracy:.0%}',
                        backtest=backtest_result,
                        comp_type=comp_type
                    )
                else:
                    # 记录"此方向不通"
                    self._record_dead_end(
                        factor, current_weight, new_weight,
                        reason='回测未改善',
                        comp_type=comp_type
                    )
```

**model_params_history记录格式:**
```python
{
    'model_version': 'v4.0-friendly',
    'param_name': 'friendly_odds_lt_1.20_home_adj',
    'old_value': -0.18,
    'new_value': -0.15,
    'change_reason': 'odds<1.20友谊赛主胜率81%，-0.18过度修正',
    'backtest_result': 'accuracy +1.2pp, brier -0.003',
    'accuracy_before': 0.58,
    'accuracy_after': None,  # 实战后再填
    'sample_size': 8492,  # 回测样本
    'changed_at': '2026-06-10T07:00:00'
}
```

### 复盘闭环

```
lottery_results写入
  ↓
ValidationService.validate_match() → lottery_validation写入
  ↓
翻车归因 → 写入lottery_validation.attribution字段(需加)
  ↓
场景准确率统计 → 更新model_accuracy(需建表)
  ↓
发现问题 → EnhancedWeightOptimizer.optimize()
  ↓
回测验证 → model_params_history记录
  ↓
采纳/回退 → model_weights更新
  ↓
明天用新参数 → 闭环
```

### 需要新建/修改的表

1. **lottery_validation**: 加 `attribution TEXT` — 翻车归因
2. **lottery_validation**: 加 `attribution_detail TEXT` — 归因详情JSON
3. **lottery_validation**: 加 `scenario_type TEXT` — 场景类型(友谊赛/联赛/杯赛等)
4. **model_accuracy**: 新建 — 按场景+赔率区间统计准确率
5. **lottery_results**: 需要ResultDAO + sync_results()实现
