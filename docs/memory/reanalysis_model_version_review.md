---
name: reanalysis-model-version-review
description: P1-2重分析变化复核+P1-3模型版本回退复核+P0-6.9.3因子溯源+P0-6.9.5分玩法目标+P0-6.9.7.7前端不过载
metadata: 
  node_type: memory
  type: project
  originSessionId: 8bfd2936-b7d2-484e-b643-212fd61d5dce
---

## P1-2 重分析变化可见化复核

- prediction_reanalysis_changes表: 232条记录, 68条有推荐变化, 12条已结算
- 16种trigger_source, 前端映射完整中文名(LotteryCenter.vue triggerMap对象)
- API: `/lottery/reanalysis-changes/{lottery_match_id}` 返回change列表+diff
- 前端: "重分析历史" section显示trigger+时间+推荐变化badge+结算状态+字段diff(before→after)
- 只重分析未开赛比赛: `_select_unstarted_reanalysis_targets()` 排除kickoff <= now的比赛

## P1-3 模型版本与回退复核

- model_weights表: 32条记录, 当前active=3.9.2-learn-20260625060902741420
- model_params_history表: 88条记录(权重调整+O/U阈值+断路器+回滚事件)
- gate rollback: `_gate_check()` 阈值1pp(accuracy drop > 1pp → rollback)
- `_restore_active_weights()`: deactivate current + re-insert backup with -rollback suffix + record in params_history
- model-status API: `/lottery/model-status` 返回version+weights+accuracy+changes+gate+play_accuracy_targets
- 前端: 模型strip显示版本+30日准确率+Gate ON+最近变更+玩法达标dot

## P0-6.9.3 因子溯源

- `_build_factor_provenance()`: 每个factor标注source/captured_at/confidence/fallback/stale
- `_FACTOR_SOURCE_MAP`: elo→elo_history, poisson→matches_history, h2h→matches_history, form→matches_history, home_away→matches_history, motivation→classify_rules, news→intelligence, odds→lottery_odds
- 前端: 证据溯源grid显示因子+来源标签+置信度+兜底/过期badge+采集时间

## P0-6.9.5 分玩法准确率目标

- 目标: spf>=60%, ou>=56%, rqspf>=54%, bqc>=45%, bf>=25%
- 当前: spf=60.0%(达标), ou=53.9%(-2.1pp), rqspf=56.1%(达标), bqc=38.3%(-6.7pp), bf=20.8%
- API: model-status新增play_accuracy_targets{current/target/gap_pp/met}
- 前端: 玩法达标dot(绿色met/红色miss, tooltip显示差距)

## P0-6.9.7.7 前端不过载

- 卡片只显示: 推荐+信心+情报状态+数据状态徽章
- 详情弹窗显示: match_script+证据溯源+玩法联动+重分析历史+AI解读+competition_context
- 卡片无详细证据/脚本/归因泄漏
