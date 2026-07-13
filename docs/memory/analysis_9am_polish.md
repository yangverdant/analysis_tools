---
name: analysis_9am_polish
description: 9:00分析环节打磨——6层分析栈设计、与ComprehensiveAnalyzer/CupAnalyzer的关系、MatchProfile驱动路由、因子分解、冷启动
metadata: 
  node_type: memory
  type: project
  originSessionId: d2e763d6-7730-4e83-a6e7-3cc8d939df30
---

## 9:00 分析环节打磨

### 当前分析器架构

```
ComprehensiveAnalyzer.comprehensive_prediction()
├── EloAnalyzer          → Elo差 → 概率
├── PoissonPredictor     → xG → Poisson → 概率+比分 (权重0.25，核心)
├── XGAnalyzer           → 简单xG计算
├── H2HAnalyzer          → 交锋记录 → 修正
├── FormAnalyzer         → 近期战绩 → 修正
├── HomeAwayAnalyzer     → 主客场 → 修正
├── MotivationAnalyzer   → 动机 → 修正 (需要league_id+season_id)
├── NewsFactorsAnalyzer  → 利好利空 → 修正
├── RivalryAnalyzer      → 敌对关系 → 修正
└── _apply_friendly_intel() → 5维度修正 (仅当league_name='friendly'时触发)

CupAnalyzer.analyze()
├── detect_cup_context() → 是否杯赛
├── adjust_elo_for_cup() → 跨联赛Elo校准
├── calc_knockout_pressure() → 淘汰赛压力
├── calc_upset_factor() → 爆冷修正
├── calc_cup_motivation() → 杯赛动机
└── _apply_pre_match_intel() → 友谊赛修正(在杯赛语境下)
```

### 6层分析栈设计

将现有分析器重新组织为6层栈，由MatchProfile驱动:

```
L1 赔率概率 (OddsProbabilityLayer)
    输入: Pinnacle 1X2赔率 或 体彩SPF赔率
    操作: 1/odds → 去利润(margin) → 归一化
    输出: {home: 0.45, draw: 0.28, away: 0.27}
    实现: 新建(当前ComprehensiveAnalyzer没有独立的赔率→概率层)
    冷启动: 无赔率 → 跳过L1，增加后续层权重

L2 实力评估 (StrengthLayer)
    俱乐部: EloAnalyzer.calculate_match_elo_prediction()
    国家队: FIFA排名差 → 概率转换(公式不同于Elo)
    冷启动: 无Elo无FIFA → 跳过L2，增加赔率权重

L3 状态评估 (FormLayer)
    form: FormAnalyzer.compare_teams_form() (近6/10/20场)
    H2H: H2HAnalyzer.analyze_h2h()
    赛程密度: HomeAwayAnalyzer (7天内比赛数→疲劳因子)
    过滤: 按MatchProfile.use_form_filter决定用什么form
    - league_only: 只看联赛form(友谊赛结果不算)
    - same_type: 看同类型赛事form
    - all: 看所有form

L4 信号层 (SignalLayer)
    CLV: 开盘→最新赔率方向变化(需要lottery_odds多快照)
    赔率异动: 与同类赛事平均赔率偏差
    赔率区间: 不同赔率区间有不同的翻车率(从历史数据学)
    实现: 新建(当前完全没有CLV/赔率区间分析)

L5 特殊修正 (SpecialCorrectionLayer) — 由MatchProfile驱动
    友谊赛: PreMatchCollector._calculate_friendly_adjustment()
        → 5维度(雇佣/球迷/动机/疲劳/场地)
        → 赔率分级修正
        → WC vs WC规则
    杯赛: CupAnalyzer的爆冷修正+淘汰赛压力+跨联赛Elo
    联赛: MotivationAnalyzer(保级/争冠动机)
    预选赛: 出线形势动机(新建)

L6 情报修正 (IntelLayer)
    伤病: PreMatchNewsScanner → impact_level → 修正
    新闻: NewsFactorsAnalyzer → 利好利空
    阵容: 赛前1h阵容数据(可选，当前无数据源)
```

### 合并方式 — MatchProfile驱动

```python
def analyze_match(match_info, profile: MatchProfile) -> Prediction:
    """6层分析栈 — MatchProfile驱动"""

    # L1: 赔率概率
    l1 = OddsProbabilityLayer.analyze(match_info.odds)
    if not l1.available:
        # 无赔率: 增加L2权重，标记confidence='low'
        profile.adjust_weights(l1_downgrade=True)

    # L2: 实力评估
    if profile.participant_type == 'club':
        l2 = StrengthLayer.analyze_elo(match_info.team_ids)
    else:
        l2 = StrengthLayer.analyze_fifa(match_info.team_ids)

    # L3: 状态评估
    l3 = FormLayer.analyze(
        match_info.team_ids,
        form_filter=profile.use_form_filter  # 关键: 按赛事类型过滤form
    )

    # L4: 信号层
    l4 = SignalLayer.analyze(match_info.odds_snapshots)

    # L5: 特殊修正
    l5 = SpecialCorrectionLayer.analyze(match_info, profile)
    # profile.use_friendly_intel → 友谊赛5维度
    # profile.use_cup_upset → 杯赛爆冷
    # profile.use_motivation → 动机分析

    # L6: 情报修正
    l6 = IntelLayer.analyze(match_info.injuries, match_info.news)

    # 加权合并
    final_prob = {}
    for layer, result in [(L1, l1), (L2, l2), (L3, l3), (L4, l4)]:
        for outcome in ['home', 'draw', 'away']:
            final_prob[outcome] += result.prob[outcome] * profile.weights[layer]

    # 叠加修正(L5+L6是加法修正，不是加权)
    for outcome in ['home', 'draw', 'away']:
        final_prob[outcome] += l5.adjustment[outcome] + l6.adjustment[outcome]

    # 归一化 + 限制[0.01, 0.97]
    normalize(final_prob)
    clamp(final_prob, 0.01, 0.97)

    return Prediction(
        probabilities=final_prob,
        factor_breakdown=build_factor_breakdown(l1, l2, l3, l4, l5, l6),
        confidence=assess_confidence(l1, l2, l3, l4, l5, l6),
        model_version=profile.model_version
    )
```

### 因子贡献分解 — 可解释性核心

每层分析的结果都记录对最终概率的贡献:

```python
factor_breakdown = {
    'L1_odds': {
        'prob': {'home': 0.45, 'draw': 0.28, 'away': 0.27},
        'weight': 0.35,
        'contribution': {'home': +0.158, 'draw': +0.098, 'away': +0.095},
        'source': 'Pinnacle 1X2: 2.22/3.57/3.70'
    },
    'L2_elo': {
        'prob': {'home': 0.52, 'draw': 0.26, 'away': 0.22},
        'weight': 0.30,
        'contribution': {'home': +0.156, 'draw': +0.078, 'away': +0.066},
        'source': 'Elo: 1650 vs 1480, diff=170'
    },
    'L5_friendly_intel': {
        'adjustment': {'home': -0.12, 'draw': +0.08, 'away': +0.04},
        'type': 'odds_tier+employer+motivation',
        'source': '赔率<1.40推平局-0.12, 雇主试阵推平局+0.05'
    },
}
```

用户看到: "赔率推主胜+0.158, Elo推主胜+0.156, 5维度推平局+0.08 — 修正幅度大，需重视"

### 与现有代码的关系 — 不重写，复用+重构

| 6层栈组件 | 复用现有代码 | 改动 |
|-----------|-------------|------|
| L1 赔率概率 | 新建(当前没有独立层) | 从ComprehensiveAnalyzer中提取赔率→概率逻辑 |
| L2 实力评估 | EloAnalyzer + FIFA排名 | 国家队用FIFA替代Elo(当前没有) |
| L3 状态评估 | FormAnalyzer + H2HAnalyzer + HomeAwayAnalyzer | 加form_filter参数 |
| L4 信号层 | 新建 | CLV+赔率区间(当前完全没有) |
| L5 特殊修正 | PreMatchCollector + CupAnalyzer | 由MatchProfile开关驱动，不硬编码if/else |
| L6 情报修正 | NewsFactorsAnalyzer + PreMatchNewsScanner | 整合到统一接口 |

**关键改动: ComprehensiveAnalyzer.comprehensive_prediction() 入口**

当前:
```python
# 友谊赛修正 — 硬编码检测
if league_row['name_en'].lower() in ('friendly', 'friendlies', 'international'):
    pre_match_intel = self._apply_friendly_intel(...)
```

改为:
```python
# MatchProfile驱动
profile = engine.classify(match_info)
if profile.use_friendly_intel:
    l5_friendly = self._apply_friendly_intel(...)
if profile.use_cup_upset:
    l5_cup = self._apply_cup_upset(...)
if profile.use_motivation:
    l5_motivation = self._apply_motivation(...)
```

### 冷启动处理

| 场景 | 处理 |
|------|------|
| 无赔率 | L1跳过，L2权重提升，confidence='low' |
| 无Elo(俱乐部) | L2用赔率反推实力，confidence='low' |
| 无FIFA排名(国家队) | L2用赔率反推实力，confidence='low' |
| 无form(新球队) | L3跳过，增加赔率权重 |
| 无H2H(首次交锋) | L3的H2H部分跳过，正常 |
| 无伤病情报 | L6跳过，这是常态(友谊赛尤其如此) |
| 无CLV(首次赔率快照) | L4跳过，正常(开盘就是第一快照) |
| 全部缺失 | 纯赔率模型(1/odds归一化)，confidence='very_low' |

### model_version 管理

每次预测必须记录model_version:
- 格式: `v4.0-{competition_type}-{date}`
- 例: `v4.0-friendly-20260609`, `v4.0-league-20260609`
- 参数变更时版本号递增: v4.0→v4.1→v4.2
- lottery_predictions.model_version字段必须填充(当前全NULL)

### 比分预测

当前: PoissonPredictor.predict_match() → most_likely_scores
改进: 用最终xG(基础xG + L5修正 + L6修正) → Poisson → TOP3比分

```python
# xG修正
base_home_xg = poisson.home_xg
adjusted_home_xg = base_home_xg
if l5_friendly:
    adjusted_home_xg += l5_friendly.xg_adjustment.get('home', 0)
if l6_injury:
    adjusted_home_xg += l6_injury.xg_adjustment.get('home', 0)

# Poisson分布
score_probs = poisson_distribution(adjusted_home_xg, adjusted_away_xg)
top3 = sorted(score_probs.items(), key=lambda x: x[1], reverse=True)[:3]
```

### 玩法建议

| 玩法 | 逻辑 | 当前实现 |
|------|------|---------|
| SPF | argmax(概率) | ✓ (SPFAnalyzer) |
| RQSPF | 让球后概率 + 让球方向 | ✓ (HandicapAnalyzer) |
| BF | TOP3比分 + 赔率对比 | ✓ (ScorePredictor) |
| BQC | 半全场概率(基于xG时序模型) | ✓ (BQCAnalyzer) |
| 价值投注 | 模型概率 > 隐含概率 + Kelly | ✓ (_calculate_value_bets) |

### 输出: lottery_predictions + factor_breakdown

```python
lottery_predictions: {
    lottery_match_id: '202606098001',
    play_type: 'spf',
    predictions: {'home_win': 0.38, 'draw': 0.35, 'away_win': 0.27},
    recommendation: '1',  # 平局(体彩编码)
    confidence: 0.35,
    confidence_level: 'medium',
    has_value_bet: 1,
    value_bets: {'spf_draw': {'edge': 0.08, 'kelly': 0.04}},
    features_json: {  # 完整6层特征快照
        'L1_odds': {...},
        'L2_elo': {...},
        'L3_form': {...},
        'L5_friendly_intel': {...},
    },
    weights_json: {  # 使用的权重
        'odds': 0.35, 'elo': 0.30, 'form': 0.10, ...
    },
    model_version: 'v4.0-friendly',
}
```
