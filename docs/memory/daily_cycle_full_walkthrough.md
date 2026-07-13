---
name: daily_cycle_full_walkthrough
description: 分析师完整日循环走查——每个环节的具体操作、数据流、异常处理、记忆写入
metadata: 
  node_type: memory
  type: project
  originSessionId: d2e763d6-7730-4e83-a6e7-3cc8d939df30
---

## 分析师完整日循环走查

以6月9日(周一)为例，从系统"醒来"到"入睡"的完整过程。

---

### 6:00 醒来 — 自感知

**做什么：** 检查自己的状态，了解今天的环境

**具体操作：**
1. 读系统时间 → 2026-06-09 06:00 北京时间
2. 查记忆：昨天有什么未完成的事？
   - DB: lottery_matches WHERE match_date='2026-06-08' AND sell_status='selling' → 检查昨天有没有没分析的比赛
   - DB: lottery_predictions WHERE date(created_at)='2026-06-08' → 昨天分析了几场
   - DB: lottery_validation WHERE date(validated_at)='2026-06-08' → 昨天复盘了几场
3. 查数据源健康：
   - DB: data_source_health → oddsfe上次成功是什么时候? sporttery呢? apifootball呢?
   - 如果oddsfe连续3天失败 → 告警 "oddsfe数据源异常，赔率数据可能缺失"
4. 查近期表现：
   - DB: lottery_validation → 最近7天/30天准确率
   - 如果最近7天准确率<50% → 标记 "近期表现异常，今日分析需标注低置信度"

**记忆写入(短期)：**
```
today_status = {
    'date': '2026-06-09',
    'yesterday_unanalyzed': 2,  # 昨天有2场没分析(缺赔率)
    'data_source_health': {'oddsfe': 'ok', 'sporttery': 'ok', 'apifootball': 'degraded'},
    'recent_accuracy_7d': 0.647,
    'recent_accuracy_30d': 0.583,
    'alerts': ['apifootball连续2天部分失败，伤病情报可能不完整']
}
```

**异常场景：**
- DB连接失败 → 写日志，跳过此步骤，用缓存状态
- data_source_health表为空 → 首次运行，不告警，标记"冷启动"

---

### 7:00 采集第一轮 — 体彩开售数据

**做什么：** 获取今天体彩开售的比赛列表+赔率

**具体操作：**
1. 调sporttery API: getMatchCalculatorV1.qry?sellStatus=on&date=2026-06-09
2. 解析返回 → 得到比赛列表(中文队名+SPF赔率+RQSPF赔率+让球数+联赛名)
3. 对每场比赛：
   a. 生成lottery_match_id (如"202606098001")
   b. 中文队名 → 查team_name_mapping表 → 得到team_id和英文队名
   c. 映射失败? → 存入unmapped_teams列表，confidence=0，后续人工补
   d. 写入lottery_matches表
   e. 写入lottery_odds表(snapshot_type='opening', snapshot_time=当前时间)
4. 同时: 用英文名查oddsfe，看有没有对应的赛事 → 写入source_mapping_bridge

**数据流：**
```
sporttery API → 解析 → 队名映射 → lottery_matches + lottery_odds
                        ↓ 映射失败
                    unmapped_teams → 人工补映射入口
```

**记忆写入(短期)：**
```
today_matches = [
    {'lottery_match_id': '202606098001', 'home_cn': '日本', 'away_cn': '澳大利亚',
     'home_en': 'Japan', 'away_en': 'Australia', 'league': '友谊赛',
     'spf': '1.45/3.80/5.50', 'handicap': -1, 'mapped': True},
    {'lottery_match_id': '202606098002', 'home_cn': '韩国', 'away_cn': '伊拉克',
     'home_en': 'South Korea', 'away_en': 'Iraq', 'league': '世预赛',
     'spf': '1.30/4.50/8.00', 'handicap': -1, 'mapped': True},
    {'lottery_match_id': '202606098003', 'home_cn': '横滨水手', 'away_cn': '川崎前锋',
     'home_en': None, 'away_en': 'Kawasaki Frontale', 'league': '日职',
     'spf': '2.35/3.10/2.75', 'handicap': 1, 'mapped': False},  # 横滨水手映射失败
]
today_stats = {'total': 3, 'mapped': 2, 'unmapped': 1}
```

**异常场景：**
- sporttery API返回空 → 可能今天还没开售，1小时后重试
- sporttery API超时 → 标记data_source_health.sporttery='timeout'，用oddsfe的赔率代替
- 队名映射失败 → 存入unmapped列表，该场比赛仍可分析(用赔率基础模型)，但标注confidence='low'
- 一场体彩比赛匹配到oddsfe多场(同一天两场同对阵) → 用联赛名+时间窗口辅助验证

**队名映射的具体逻辑：**
1. 精确匹配: team_name_mapping表(lottery_name → team_id)
2. 模糊匹配: EntityMapper._fuzzy_match_team() (SequenceMatcher, 阈值0.8)
3. team_names.py: normalize_team_name() (4个数据源, 1169条CN→EN)
4. 都匹配不到 → 存入unmapped，系统自学习：下次遇到同样中文名直接用之前的映射

---

### 7:30 采集第二轮 — oddsfe赔率

**做什么：** 用oddsfe获取Pinnacle赔率(更准的国际赔率)

**为什么不用体彩赔率做分析：**
- 体彩赔率受国内投注偏好影响(散户追强队)
- Pinnacle赔率是全球最精算的，隐含概率最接近真实
- 体彩赔率只用于SPF/RQSPF/BF玩法建议

**具体操作：**
1. 调oddsfe schedule API: 获取2026-06-09所有赛事
2. 对每场赛事: 匹配到已入库的lottery_matches
   - 匹配方式: 英文队名 + 日期(±12h窗口，oddsfe用UTC，体彩用北京时间)
   - 匹配成功 → 写source_mapping_bridge(记录oddsfe event_id)
   - 匹配失败 → 记录，后续人工桥接
3. 对匹配成功的赛事: 调oddsfe detail API获取Pinnacle赔率
4. 写入match_odds表(bookmaker='pinnacle', 包含1X2/O-U/AH/BTTS)

**时区转换逻辑(核心！)：**
```
oddsfe: 2026-06-08 19:00 UTC
北京时间: 2026-06-09 03:00 UTC+8
体彩日期: 2026-06-09 (按北京日期归档)

匹配窗口: oddsfe UTC时间 ±12h 转换为北京时间后，与体彩日期匹配
```

**记忆写入(短期)：**
```
oddsfe_sync = {
    'fetched_events': 15,
    'matched_to_lottery': 3,
    'unmatched': 12,  # 非体彩开售的比赛，oddsfe有但体彩没开
    'pinnacle_odds_available': True,
    'bridge_ids_saved': 3
}
```

---

### 8:00 采集第三轮 — 伤病情报

**做什么：** 获取今天比赛的伤停信息

**数据源：** apifootball API (injuries endpoint)

**具体操作：**
1. 对每场已映射的lottery_match:
   - 用source_mapping_bridge.apifootball_id查询
   - 如果没有apifootball_id → 用队名搜索apifootball teams表 → 获取ID → 回写bridge
2. 调apifootball /injuries?fixture={id}
3. 解析: 缺阵球员列表 + 缺阵原因(伤病/停赛/国家队征召)
4. 写入match_injuries表
5. 评估impact_level:
   - 主力缺阵≥2人 → impact='high'
   - 主力缺阵1人 → impact='medium'
   - 无主力缺阵 → impact='low'
   - 无数据 → impact='unknown'

**记忆写入(短期)：**
```
injury_status = {
    '202606098001': {'home_impact': 'unknown', 'away_impact': 'unknown', 'source': 'apifootball', 'status': 'no_data'},
    '202606098002': {'home_impact': 'low', 'away_impact': 'medium', 'source': 'apifootball', 'status': 'ok'},
}
# apifootball经常拿不到友谊赛伤病数据 → 这是已知限制
# 友谊赛伤病的缺失意味着5维度修正中"伤病修正"项confidence低
```

**异常场景：**
- apifootball无数据 → impact='unknown'，5维度修正中伤病维度权重降为0
- apifootball ID没桥接 → 跳过，标注"需补桥接"
- 返回数据但全是替补球员 → 仍标'low'(替补缺阵影响小)

---

### 8:30 分析 — 赛事分类 + 选模型

**做什么：** 对每场比赛分类，决定用哪套分析逻辑

**具体操作：**
1. 对每场lottery_match:
   a. 调CompetitionRuleEngine.classify(match_info)
   b. match_info包含: league_name(中文), league_id(DB), match_date, home/away_team
   c. 引擎返回MatchProfile

2. 分类逻辑:
   ```
   联赛名含"日职"/"英超"/"西甲"等 → 查DB leagues表 → competition_type='league'
   联赛名含"友谊赛"/"国际赛"     → competition_type='friendly'
   联赛名含"世预赛"/"欧预赛"     → competition_type='qualifier'
   DB有league_id → 直接用DB的competition_type(最准)
   ```

3. 根据MatchProfile决定分析路径:
   - friendly → 5维度修正 + 赔率分级修正
   - league → Elo + form + 动机(保级/争冠) + Poisson
   - qualifier → FIFA排名 + 出线形势动机 + 赔率
   - cup → 爆冷修正 + 淘汰赛压力 + 跨联赛Elo

**记忆写入(短期)：**
```
match_profiles = {
    '202606098001': MatchProfile(
        competition_type='friendly', participant_type='national',
        use_friendly_intel=True, use_cup_upset=False, use_motivation=True,
        weights={'odds': 0.35, 'fifa_ranking': 0.20, 'friendly_intel': 0.25, ...},
        classification_reason='友谊赛,WC热身期,日本vs澳大利亚'
    ),
    '202606098002': MatchProfile(
        competition_type='qualifier', participant_type='national',
        use_friendly_intel=False, use_cup_upset=False, use_motivation=True,
        weights={'odds': 0.30, 'fifa_ranking': 0.25, 'motivation': 0.20, ...},
        classification_reason='世预赛亚洲区,韩国主场,出线关键战'
    ),
}
```

---

### 9:00 分析 — 6层分析栈

**做什么：** 逐场执行6层分析，生成预测

**6层分析栈：**

**L1 赔率概率(所有比赛都做)**
- 输入: Pinnacle 1X2赔率
- 操作: 1/odds → 去利润 → 归一化 → 基础概率
- 输出: {home: 0.45, draw: 0.28, away: 0.27}

**L2 实力评估**
- 俱乐部: Elo差 → 概率转换
- 国家队: FIFA排名差 → 概率转换(公式不同于Elo)
- 冷启动: 无Elo无排名 → 降级到纯赔率，confidence='low'

**L3 状态评估**
- form: 近5/10场战绩(按profile.use_form_filter过滤)
- H2H: 交锋记录(同赛事类型优先)
- 赛程密度: 7天内比赛数 → 疲劳因子

**L4 信号层**
- CLV: 开盘→最新赔率方向变化(如果有多快照)
- 赔率异动: 与同类赛事平均赔率偏差
- 赔率区间: 不同赔率区间有不同的翻车率(从历史数据学)

**L5 特殊修正(按MatchProfile)**
- 友谊赛: 5维度修正(雇佣/球迷/动机/疲劳/场地)
- 杯赛: 爆冷修正 + 淘汰赛压力
- 联赛: 保级争冠动机修正
- 高原: 场地修正

**L6 情报修正**
- 伤病: match_injuries → 主力缺阵修正
- 新闻: 如果有news_aggregated数据 → 正面/负面修正
- 阵容: 如果有赛前1h阵容数据 → 最终修正(可选)

**合并方式:**
```
最终概率 = Σ(各层概率 × 权重)  # 权重来自MatchProfile.weights
修正后概率 = 最终概率 + L5修正 + L6修正
归一化 → 限制在[0.01, 0.97]
```

**因子贡献分解(存DB，可解释性核心):**
```python
factor_breakdown = {
    'L1_odds': {'home': +0.35, 'draw': -0.15, 'away': -0.20},  # 赔率推主胜
    'L2_elo': {'home': +0.10, 'draw': -0.05, 'away': -0.05},    # Elo也推主胜
    'L5_friendly_intel': {'home': -0.15, 'draw': +0.12, 'away': +0.03},  # 5维度推平局
    'L6_injury': {'home': -0.05, 'draw': +0.02, 'away': +0.03},  # 主队伤病推客
}
# 用户看到: "赔率推主胜+0.35, 5维度推平局+0.12, 修正幅度大需重视"
```

**比分预测:**
- 用最终xG(基础xG + L5修正 + L6修正) → Poisson分布 → TOP3比分
- xG计算: base_xG + (概率偏差 × 系数) + 强弱差距修正

**玩法建议:**
- SPF: 概率最高的方向
- RQSPF: 让球后概率 + 让球方向
- BF: TOP3比分 + 赔率对比
- BQC: 半全场概率(基于xG时序模型)

**记忆写入(DB):**
```
lottery_predictions: {
    lottery_match_id, play_type='spf',
    predictions: {'home': 0.38, 'draw': 0.35, 'away': 0.27},
    recommendation: '平局',
    confidence: 0.62,
    confidence_level: 'medium',
    has_value_bet: 1,
    value_bets: {'spf_draw': {'edge': 0.08, 'kelly': 0.04}},
    features_json: {...},  # 完整6层特征快照
    weights_json: {...},   # 使用的权重
    model_version: 'v4.0-friendly',
}
```

**异常场景：**
- 无赔率 → L1缺失，降级到Elo+form，confidence='low'
- 无Elo(form/H2H) → L2/L3缺失，增加赔率权重，confidence='low'
- 无伤病情报 → L6缺失，这是常态(友谊赛尤其如此)，不影响分析
- 权重归一化后某项为0 → 说明该因子不可用，合理

---

### 9:30 推送 — 初版分析

**做什么：** 把分析结果推送给用户

**推送内容(每日md文件):**
```markdown
# 6月9日体彩分析

## 概览
今日3场比赛: 友谊赛1场, 世预赛1场, 日职1场
重点关注: 日本vs澳大利亚(友谊赛5维度修正活跃)

---

## 8801 日本 vs 澳大利亚 | 友谊赛 | 让球-1
| 项目 | 数据 |
|------|------|
| SPF赔率 | 1.45/3.80/5.50 |
| 修正概率 | 主38% 平35% 客27% |
| 5维度修正 | 雇佣关系:日本是雇主,动机medium → 推平局-12pp |
| 关键洞察 | WC热身期日本试阵,澳大利亚也不拼命 |
| 建议 | SPF: 平局 | RQSPF: 让球下盘 |
| 置信度 | 62%(中) |

因子分解: 赔率推主胜+0.35 → 5维度推平局+0.12 → 修正幅度大

## 8802 韩国 vs 伊拉克 | 世预赛 | 让球-1
| 项目 | 数据 |
|------|------|
| SPF赔率 | 1.30/4.50/8.00 |
| 修正概率 | 主58% 平24% 客18% |
| 关键洞察 | 世预赛韩国必须赢,伊拉克客场弱 |
| 建议 | SPF: 主胜 | RQSPF: 让球下盘 |
| 置信度 | 75%(高) |
```

**推送方式(当前):** 写入 data/lottery/daily/2026-06-09.md
**推送方式(未来):** API + 微信/钉钉通知

---

### 14:00 二次赔率快照 — CLV信号

**做什么：** 重新采集体彩赔率，观察变化

**具体操作：**
1. 调sporttery API获取最新赔率
2. 写入lottery_odds(snapshot_type='midday', snapshot_time=14:00)
3. 对比开盘赔率 vs 当前赔率:
   - 主胜赔率下降(1.45→1.38) = 市场更看好主胜 = CLV推主胜
   - 主胜赔率上升(1.45→1.52) = 市场在远离主胜 = CLV推非主胜
4. 如果CLV信号与预测方向一致 → 提升confidence
5. 如果CLV信号与预测方向矛盾 → 标注"CLV分歧"，但不自动翻转预测

**记忆写入:**
```
clv_signal = {
    '202606098001': {'opening': '1.45/3.80/5.50', 'current': '1.48/3.70/5.60', 
                     'direction': 'away_drift', 'agrees_with_prediction': False},
}
```

---

### 20:00 比赛开始后 — 无操作

比赛进行中，系统不干预。如果有实时赔率源(未来可加)，可以监控。

---

### 次日6:00 复盘 — 拿结果

**做什么：** 获取昨天比赛的实际结果

**数据源:** oddsfe(最全) 或 sporttery结果API

**具体操作：**
1. 查lottery_matches WHERE match_date='2026-06-09' → 得到昨天的比赛列表
2. 通过source_mapping_bridge.oddsfe_event_id → 调oddsfe获取比赛结果
3. 如果oddsfe没桥接 → 调sporttery结果API(用中文名匹配)
4. 写入lottery_results: {home_goals_ft, away_goals_ft, spf_result, bf_result, ...}

**异常场景：**
- oddsfe结果延迟(有些比赛结果要几小时后才更新) → 6点拿不到就12点重试
- 体彩和oddsfe结果不一致(加时赛进球归属) → 以体彩官方结果为准
- 结果拿不到 → 标记pending，不强制复盘

---

### 次日6:30 复盘 — 对比预测

**做什么：** 把预测和实际结果对比，记录对错

**具体操作：**
1. 对每场有结果的比赛:
   a. 查lottery_predictions → 得到预测方向和概率
   b. 查lottery_results → 得到实际结果
   c. 预测方向 == 实际结果? → is_correct=1/0
   d. 计算Brier Score: (预测概率 - 实际指示变量)² 的平均
   e. 写入lottery_validation

2. 翻车归因(最重要的环节！):
   ```
   如果预测错了:
   ├→ 赔率本身就接近(最大概率<40%)? → 归因: "均势场,低置信度正常"
   ├→ 5维度修正方向反了? → 归因: "修正方向错误"
   │   └→ 哪个维度反了? → 雇佣/球迷/动机/疲劳/场地 → 记录具体维度
   ├→ 伤病情报缺失? → 归因: "情报不足"
   │   └→ 比赛后才知道姆巴佩不上 → 记录"赛后信息:姆巴佩缺阵"
   ├→ 赔率区间已知翻车区? → 归因: "已知高翻车率区间"
   └→ 新场景? → 归因: "首次遇到", 记录特征供未来学习
   ```

3. 更新场景准确率:
   ```
   按维度统计:
   - 友谊赛: 最近30场准确率=X%
   - 友谊赛+赔率<1.30: 最近30场准确率=Y%
   - 有伤病情报: 最近30场准确率=Z%
   - 无伤病情报: 最近30场准确率=W%
   ```

**记忆写入(中期):**
```
validation_20260609 = {
    'total': 3, 'correct': 2, 'accuracy': 0.667,
    'details': [
        {'match': '日本vs澳大利亚', 'predicted': '平局', 'actual': '主胜(2-1)',
         'brier': 0.245, 'attribution': '修正方向错误:5维度推平局但日本认真打赢了',
         'attribution_detail': '动机判断:日本medium→实际must_win(WC东道主效应强于预期)'},
        {'match': '韩国vs伊拉克', 'predicted': '主胜', 'actual': '主胜(3-0)',
         'brier': 0.082, 'attribution': '预测正确'},
    ],
    'scenario_accuracy': {
        'friendly_30d': 0.647,
        'friendly_odds_lt_1.40_30d': 0.500,  # 赔率<1.40的友谊赛只有50%准
        'qualifier_30d': 0.750,
    }
}
```

---

### 次日7:00 学习 — 参数评估与微调

**做什么：** 根据复盘结果决定是否调参

**核心原则:**
- 不凭直觉调参(数据驱动规则验证 [[feedback_data_driven_rules]] )
- 小幅微调(±10%)，不大幅改动
- 先回测历史数据验证方向，再应用到实战
- 每次调参记录old→new→reason→效果

**具体操作：**
1. 检查: 最近30场整体准确率 vs 赔率基线准确率
   - 如果模型 > 赔率 → 不调(模型有效)
   - 如果模型 < 赔率 → 进入调参流程

2. 定位问题场景:
   - 按赛事类型分: 友谊赛/联赛/杯赛，哪个类型拖后腿?
   - 按赔率区间分: <1.30/1.30-1.80/>1.80，哪个区间拖后腿?
   - 按修正维度分: 5维度哪个维度的贡献是负的?

3. 调参方式(以友谊赛赔率分级为例):
   ```
   当前: odds<1.20 → home_adj=-0.18
   
   步骤1: 查DB — odds<1.20的友谊赛最近30场，主胜率多少?
   步骤2: 如果主胜率>80% → -0.18修正过度 → 尝试-0.15
   步骤3: 用8492场历史友谊赛回测 -0.18 vs -0.15
   步骤4: 如果-0.15更好 → 采纳，记录到model_params_history
   步骤5: 如果-0.15更差 → 回退，记录"此方向不通"
   ```

4. 写入model_params_history:
   ```python
   {
       'param_name': 'friendly_odds_lt_1.20_home_adj',
       'old_value': -0.18,
       'new_value': -0.15,
       'reason': 'odds<1.20友谊赛主胜率81%，-0.18过度修正',
       'backtest_result': 'accuracy +1.2pp, brier -0.003',
       'approved': True
   }
   ```

**异常场景：**
- 样本太小(某场景<10场) → 不调(不靠谱)
- 回测变好但实战变差 → 过拟合信号，回退参数
- 多个参数需要同时调 → 一次只调一个(控制变量)

---

### 记忆的持久化

**短期记忆(今天):** 每次daily_runner运行时在内存中维护，运行结束写入DB
- 存储位置: lottery_matches/lottery_odds/lottery_predictions 表
- 生命周期: 当天有效

**中期记忆(近30天):** DB中的聚合统计
- 存储位置: lottery_validation + model_accuracy 表
- 查询: SELECT ... WHERE validated_at > date('now', '-30 days')

**长期记忆(历史):** DB中的规则和版本历史
- 存储位置: league_rules + model_params_history + source_mapping_bridge
- 不删除，只追加

**球队画像(特殊长期记忆):**
- France: 友谊赛近10场，赔率<1.40时翻车率60% → "法国友谊赛不认真"
- Bolivia: 主场La Paz 3640m，近5场主胜率80% → "高原主场强"
- 这类画像从历史数据自动计算，不是硬编码
- 存储位置: team_status_summary 或 新建 team_matchup_profiles 表

---

### 完整数据流图

```
sporttery API ──→ lottery_matches + lottery_odds(开售)
oddsfe API   ──→ match_odds(pinnacle) + source_mapping_bridge(桥接)
apifootball  ──→ match_injuries

                        ↓ 数据齐了

CompetitionRuleEngine.classify() ──→ MatchProfile

                        ↓ 分类完成

6层分析栈(L1→L6) ──→ lottery_predictions + factor_breakdown
                   ──→ 比分预测 + SPF/RQSPF/BF建议

                        ↓ 分析完成

推送: data/lottery/daily/{date}.md + API

                        ↓ 比赛结束

oddsfe/sporttery结果 ──→ lottery_results

                        ↓ 结果入库

复盘对比 ──→ lottery_validation + 翻车归因

                        ↓ 复盘完成

场景准确率统计 ──→ model_accuracy

                        ↓ 发现问题

参数微调 ──→ model_params_history(回测验证)

                        ↓ 调参完成

明天用新参数 → 闭环
```

---

## 2026-07-07 更正：实际调度已从daily_runner单进程改为3个独立timer

| Timer | 频率 | 对应原文节点 |
|-------|------|------------|
| football-automation-tick (~15min) | 采集+补缺+分析+验证 | 6:00自感知→9:00分析→14:00CLV→复盘 |
| football-learning-refresh (每日02:53) | 归因+学习+重分析 | 复盘→参数微调 |
| football-daily-push (每日09:00) | TOP3推送+Agent早报+止损 | 9:30推送 |

**关键偏移**:
- 原文"lottery_predictions"→实际表名"lottery_analysis_reports"
- 原文"sporttery: ok"→实际sporttery WAF封禁(2026-07-04), oddsfe是唯一主源
- 原文假设daily_runner单进程跑完整循环→实际3个timer独立触发, 不走daily_runner
- 见 [[automation_loop_design_philosophy]] — timer分工和脆弱点
- 见 [[automation_loop_p0_fixes]] — 3个P0断点修复
