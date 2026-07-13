---
name: self_perception_6am_polish
description: 6:00自感知环节打磨——DB断点诊断、修复方案、冷启动逻辑、健康检查、准确率自评
metadata: 
  node_type: memory
  type: project
  originSessionId: d2e763d6-7730-4e83-a6e7-3cc8d939df30
---

## 6:00 自感知环节打磨

### DB现状断点诊断 (2026-06-08)

| 检查项 | 期望 | 实际 | 严重度 |
|--------|------|------|--------|
| lottery_matches有今天数据 | 每天自动填充 | 最后数据5月27日，已12天没更新 | **致命** |
| lottery_matches ↔ teams关联 | match_id + team_id 都有 | match_id全NULL，但team_id有(94/94) | 中等 |
| lottery_matches ↔ elo_ratings | 两队都有Elo | 74/94两队都有Elo(79%) | 中等 |
| lottery_matches ↔ fifa_rankings | 国家队有FIFA | 0/94(因为FIFA用team_id不同体系) | **致命** |
| lottery_matches ↔ team_form | 有近期战绩 | 0/94(form表仅165队，主要是俱乐部) | **致命** |
| lottery_odds覆盖 | 每场都有SPF+RQSPF赔率 | 25/94(27%) | **致命** |
| lottery_odds多快照 | opening+midday+closing | 只有odds_data，opening_odds/latest_odds/odds_movement全NULL | 高 |
| lottery_predictions ↔ model_version | 每次预测记录版本 | model_version全NULL | 高 |
| lottery_results | 昨天的比赛有结果 | 0条(从未获取过结果) | **致命** |
| lottery_validation | 有复盘记录 | 0条(从未复盘过) | **致命** |
| data_source_health | 各源健康状态 | 0条(从未记录过) | 高 |
| source_mapping_bridge | lottery↔oddsfe/apifootball桥接 | 0条(从未桥接过) | **致命** |
| model_params_history | 参数调整有历史 | 表存在但0条 | 中等 |
| weight_adjustment_history | 权重调整有历史 | 0条 | 中等 |

### 核心断点链

```
最致命的因果链:

没有daily_runner自动采集
  → 5月27日后没新数据
    → 没有今天的比赛列表
      → 没法分析
        → 没有预测
          → 没有结果可复盘
            → 没有准确率数据
              → 系统不知道自己准不准
                → 无法自进化

根因: 缺少daily_runner.py独立入口(不依赖FastAPI)
```

### 6:00自感知完整逻辑设计

```python
class SelfPerception:
    """6:00醒来 — 系统自感知"""

    def perceive(self) -> DailyStatus:
        """执行完整自感知，返回今日状态"""

        # === 1. 时间感知 ===
        now = get_beijing_time()  # 统一用北京时间
        today = now.date()

        # === 2. 昨日未完成检查 ===
        yesterday_unanalyzed = self._check_yesterday_unanalyzed(today)
        yesterday_unvalidated = self._check_yesterday_unvalidated(today)

        # === 3. 数据源健康检查 ===
        source_health = self._check_data_source_health()

        # === 4. 近期准确率 ===
        accuracy = self._check_recent_accuracy()

        # === 5. 参数版本检查 ===
        model_status = self._check_model_status()

        # === 6. 待处理事项汇总 ===
        alerts = self._generate_alerts(
            yesterday_unanalyzed, yesterday_unvalidated,
            source_health, accuracy, model_status
        )

        return DailyStatus(
            date=today,
            yesterday_unanalyzed=yesterday_unanalyzed,
            yesterday_unvalidated=yesterday_unvalidated,
            source_health=source_health,
            accuracy=accuracy,
            model_status=model_status,
            alerts=alerts
        )
```

### 2. 昨日未完成检查 — 具体SQL

```sql
-- 昨天有多少比赛还在selling状态(没出结果)
SELECT count(*) FROM lottery_matches
WHERE match_date = date('now', '-1 day', '+8 hours')  -- 北京时间修正
  AND sell_status = 'selling';

-- 昨天有多少比赛没有预测
SELECT count(*) FROM lottery_matches lm
WHERE lm.match_date = date('now', '-1 day', '+8 hours')
  AND NOT EXISTS (
    SELECT 1 FROM lottery_predictions lp
    WHERE lp.lottery_match_id = lm.lottery_match_id
  );

-- 昨天有预测但没有复盘的
SELECT count(*) FROM lottery_predictions lp
JOIN lottery_matches lm ON lp.lottery_match_id = lm.lottery_match_id
WHERE lm.match_date = date('now', '-1 day', '+8 hours')
  AND NOT EXISTS (
    SELECT 1 FROM lottery_validation lv
    WHERE lv.prediction_id = lp.prediction_id
  );
```

### 3. 数据源健康检查 — 设计

data_source_health表已有schema，需要填入初始数据并每次采集后更新。

**初始化(首次运行):**
```python
INITIAL_SOURCES = [
    ('sporttery', 'lottery', 'unknown'),     # 体彩比赛+赔率
    ('oddsfe', 'odds', 'unknown'),            # 国际赔率(Pinnacle)
    ('apifootball', 'injury', 'unknown'),     # 伤病/阵容
    ('fifa', 'ranking', 'unknown'),           # FIFA排名
    ('football_data_uk', 'historical', 'unknown'),  # CSV历史数据
]
```

**健康评估逻辑:**
```python
def _check_data_source_health(self) -> dict:
    """检查每个数据源的健康状态"""

    # 1. 读DB: data_source_health
    # 2. 对每个源:
    #    - last_success距今 > 24h → status='degraded'
    #    - last_success距今 > 72h → status='down'
    #    - failure_count > 3(连续) → status='down'
    #    - 否则 → status='healthy'
    # 3. 冷启动: 表为空 → 全标'unknown'，不告警

    health = {}
    for source in self._get_all_sources():
        record = self._get_health_record(source.name)
        if not record:
            health[source.name] = {'status': 'cold_start', 'alert': False}
            continue

        hours_since_success = (now - record.last_success).total_seconds() / 3600
        if hours_since_success > 72:
            health[source.name] = {'status': 'down', 'alert': True}
        elif hours_since_success > 24:
            health[source.name] = {'status': 'degraded', 'alert': True}
        elif record.failure_count >= 3:
            health[source.name] = {'status': 'down', 'alert': True}
        else:
            health[source.name] = {'status': 'healthy', 'alert': False}

    return health
```

**采集后更新:**
```python
# 每次采集完成后(无论成功失败)
def update_source_health(source_name, success: bool, error_msg: str = None):
    if success:
        UPDATE data_source_health
        SET status='healthy', last_success=CURRENT_TIMESTAMP,
            failure_count=0, updated_at=CURRENT_TIMESTAMP
        WHERE source_name=? AND source_category=?
    else:
        UPDATE data_source_health
        SET last_failure=CURRENT_TIMESTAMP,
            failure_count=failure_count+1,
            status=CASE WHEN failure_count+1>=3 THEN 'down' ELSE 'degraded' END,
            updated_at=CURRENT_TIMESTAMP
        WHERE source_name=? AND source_category=?
```

### 4. 近期准确率 — 冷启动处理

**冷启动(无validation数据时):**
```python
def _check_recent_accuracy(self) -> dict:
    """检查近期准确率"""

    # 查DB: lottery_validation
    validation_count = SELECT count(*) FROM lottery_validation

    if validation_count == 0:
        # 冷启动: 没有任何复盘数据
        return {
            'status': 'cold_start',
            'recent_7d': None,
            'recent_30d': None,
            'by_competition_type': {},
            'by_odds_tier': {},
            'sample_size': 0,
            'alert': False,  # 冷启动不告警，这是正常的
            'message': '系统刚启动，暂无准确率数据，需要运行至少一个完整闭环(采集→分析→结果→复盘)'
        }

    # 正常: 有validation数据
    accuracy_7d = SELECT AVG(is_correct) FROM lottery_validation
                  WHERE validated_at >= date('now', '-7 days', '+8 hours')

    accuracy_30d = SELECT AVG(is_correct) FROM lottery_validation
                   WHERE validated_at >= date('now', '-30 days', '+8 hours')

    # 按赛事类型
    by_type = SELECT lm.league_name_cn, AVG(lv.is_correct), COUNT(*)
              FROM lottery_validation lv
              JOIN lottery_predictions lp ON lv.prediction_id = lp.prediction_id
              JOIN lottery_matches lm ON lp.lottery_match_id = lm.lottery_match_id
              WHERE lv.validated_at >= date('now', '-30 days', '+8 hours')
              GROUP BY lm.league_name_cn

    # 告警条件
    alert = False
    if accuracy_7d is not None and accuracy_7d < 0.50:
        alert = True  # 7天准确率低于50%

    return {
        'status': 'active',
        'recent_7d': accuracy_7d,
        'recent_30d': accuracy_30d,
        'by_competition_type': by_type,
        'sample_size': validation_count,
        'alert': alert,
        'message': '近期7天准确率低于50%，今日分析需标注低置信度' if alert else '准确率正常'
    }
```

### 5. 模型版本检查

```python
def _check_model_status(self) -> dict:
    """检查模型版本和参数状态"""

    # 当前活跃权重
    current = SELECT * FROM model_weights WHERE is_active=1

    # 最近参数调整
    recent_adjustments = SELECT * FROM model_params_history
                         ORDER BY changed_at DESC LIMIT 5

    # 权重调整历史
    weight_history = SELECT * FROM weight_adjustment_history
                     ORDER BY created_at DESC LIMIT 5

    return {
        'current_model_version': current.get('version', 'unknown') if current else 'cold_start',
        'current_weights': current.get('weights', {}) if current else {},
        'recent_param_changes': len(recent_adjustments),
        'last_weight_adjustment': weight_history[0] if weight_history else None,
        'total_validations': SELECT count(*) FROM lottery_validation  # 样本量
    }
```

### 6. 告警生成逻辑

```python
def _generate_alerts(self, ...): -> list:
    alerts = []

    # 致命: 今天没数据(采集可能失败)
    if not today_matches:
        alerts.append(Alert('CRITICAL', '今天没有比赛数据，采集可能未执行'))

    # 高: 数据源不健康
    for source, health in source_health.items():
        if health['status'] == 'down':
            alerts.append(Alert('HIGH', f'{source}数据源已中断>72h'))
        elif health['status'] == 'degraded':
            alerts.append(Alert('MEDIUM', f'{source}数据源不稳定'))

    # 高: 昨天有未复盘的比赛
    if yesterday_unvalidated > 0:
        alerts.append(Alert('HIGH', f'昨天有{yesterday_unvalidated}场比赛未复盘'))

    # 中: 近期准确率低
    if accuracy.get('alert'):
        alerts.append(Alert('MEDIUM', accuracy['message']))

    # 低: 参数很久没调整(可能过时)
    if model_status['total_validations'] > 100 and not model_status['recent_param_changes']:
        alerts.append(Alert('LOW', '已有100+复盘数据但参数未优化，建议运行WeightOptimizer'))

    return alerts
```

### 冷启动场景处理

系统第一次运行时，几乎所有的DB都是空的。这是正常的，不是错误。

```
冷启动时6:00自感知的输出:
{
    'date': '2026-06-09',
    'status': 'cold_start',
    'yesterday_unanalyzed': 0,       # 没有昨天的比赛(正常)
    'yesterday_unvalidated': 0,      # 没有昨天的复盘(正常)
    'source_health': {
        'sporttery': {'status': 'cold_start'},
        'oddsfe': {'status': 'cold_start'},
        'apifootball': {'status': 'cold_start'},
    },
    'accuracy': {'status': 'cold_start', 'sample_size': 0},
    'model_status': {'current_model_version': 'cold_start'},
    'alerts': [
        Alert('INFO', '系统首次运行，将执行完整采集流程')
    ]
}
```

冷启动→正常的过渡:
- 第1天: 采集→分析→存预测 (accuracy仍=cold_start)
- 第2天: 获取结果→复盘→写validation (accuracy开始有数据)
- 第7天: 7天准确率首次可用
- 第30天: 完整的30天统计可用，参数优化开始有意义

### DB Schema需要补的字段

1. **lottery_matches**: 加 `oddsfe_event_id TEXT` — 直接关联oddsfe赛事(避免每次查bridge)
2. **lottery_odds**: 加 `snapshot_type TEXT DEFAULT 'current'` — 区分opening/midday/closing
3. **lottery_predictions**: `model_version TEXT` 必须填充 — 当前全NULL
4. **data_source_health**: 需要INSERT初始记录(5个数据源)
5. **model_params_history**: 已有schema，首次调参时写入

### 6:00自感知后的决策

```
自感知完成后，系统根据结果决定今日行动:

if status == 'cold_start':
    → 执行完整采集(不跳过任何环节)
    → 使用默认参数(DEFAULT_WEIGHTS)
    → 标注confidence='low'(首次运行无历史验证)

elif yesterday_unvalidated > 0:
    → 先执行昨天的复盘(优先级高于今天的采集)
    → 因为复盘能产生validation数据，是自进化的前提

elif source_health有'down':
    → 对down的源，用备选方案:
    → sporttery down → 用oddsfe赔率替代(缺SPF/RQSPF)
    → oddsfe down → 只用体彩赔率(缺Pinnacle国际赔率)
    → apifootball down → 伤病维度权重降为0

elif accuracy.alert:
    → 今日分析时，所有预测额外标注'low_confidence_due_to_recent_performance'
    → 不自动降级模型参数(避免过度反应)

else:
    → 正常执行日循环
```

### 与日循环其他环节的接口

6:00自感知的输出(DailyStatus)被后续环节消费:
- 7:00采集: `source_health`决定哪些源可用/需要备选
- 8:30分类: `accuracy.by_competition_type`影响MatchProfile的权重微调
- 9:00分析: `model_status.current_weights`决定用哪套权重
- 次日复盘: `yesterday_unvalidated`驱动复盘优先级
