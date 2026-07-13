---
name: system_worldview
description: 足球分析师系统完整世界观——自感知/自决策/自执行/自评估/自进化闭环
metadata: 
  node_type: memory
  type: project
  originSessionId: d2e763d6-7730-4e83-a6e7-3cc8d939df30
---

## 系统世界观：它是一个足球分析师，不是计算器

### 核心定义

系统是一个自主的足球分析师，具备五层能力：
1. **自感知** — 知道自己有什么数据、缺什么数据、数据质量如何
2. **自决策** — 自己判断今天该分析哪些比赛、用哪套模型
3. **自执行** — 自动采集、分析、存结果、推通知
4. **自评估** — 自动复盘，知道自己在哪些场景准、哪些场景不准
5. **自进化** — 根据评估结果自动调参、自动尝试新策略、自动回退坏策略

缺任何一层，系统就不是自主的，就需要人推一把。

---

### 记忆结构

```
记忆
├── 短期记忆(今天)
│   ├── 今天有哪些比赛
│   ├── 哪些已分析、哪些还没
│   ├── 赔率有没有变化(CLV信号)
│   └── 还缺什么数据(伤病?阵容?)
│
├── 中期记忆(近30天)
│   ├── 最近预测准确率(总体/按类型/按赔率区间)
│   ├── 最近翻车场(什么特征→什么结果)
│   ├── 最近参数调整记录(调了什么→效果如何)
│   └── 数据源健康状态(哪些源最近不稳定)
│
└── 长期记忆(历史)
    ├── 赛事规则(联赛/杯赛/友谊赛各用什么逻辑)
    ├── 参数版本历史(每次调整+原因+效果)
    ├── 场景准确率(友谊赛赔率<1.30→准确率XX%)
    ├── 球队画像(France友谊赛经常翻车,Bolivia高原主场强)
    └── 修正规则(5维度各维度的历史贡献度)
```

---

### 决策流程

```
醒来
  │
  ├→ 今天有比赛吗? → 没有 → 等明天
  │                    ↓ 有
  ├→ 数据齐了吗?
  │   ├→ 缺赔率 → 采集oddsfe/sporttery
  │   ├→ 缺伤病 → 采集apifootball
  │   ├→ 缺排名 → 采集FIFA
  │   └→ 齐了 → 继续
  │
  ├→ 分类(赛事引擎)
  │   ├→ 友谊赛 → 5维度修正 + 赔率修正
  │   ├→ 联赛 → Elo+form+动机+保级争冠
  │   ├→ 杯赛 → 爆冷修正+淘汰赛压力
  │   └→ 国家队正式赛 → 赛制规则+出线形势
  │
  ├→ 分析 → 存预测 → 推送
  │
  ├→ 赔率变了? → 更新预测 → 推送更新
  │
  ├→ 比赛结束了? → 拿结果 → 复盘
  │   ├→ 预测对了 → 记录(加强信心)
  │   ├→ 预测错了 → 记录+分析为什么错
  │   │   ├→ 赔率本身就接近? → 标注"均势场,低置信度正常"
  │   │   ├→ 伤病情报缺失? → 标注"情报不足导致"
  │   │   ├→ 修正方向反了? → 记录"5维度推平局但实际主胜"
  │   │   └→ 新场景? → 记录"首次遇到XX场景"
  │   └→ 更新准确率统计
  │
  ├→ 该调参了吗?
  │   ├→ 最近N场准确率 < 基线? → 尝试微调
  │   │   ├→ 调后回测历史 → 变好? → 采纳
  │   │   └→ 变差? → 回退,记录"此方向不通"
  │   └→ 准确率稳定? → 不动
  │
  └→ 明天继续
```

---

### 赛事规则引擎 (MatchProfile)

任何比赛 → CompetitionRuleEngine.classify() → MatchProfile

MatchProfile决定: 权重集、修正逻辑、因子启用、xG基线、主场优势系数

```python
@dataclass
class MatchProfile:
    # 基础分类
    competition_type: str       # league/domestic_cup/continental_cup/international_cup/friendly/qualifier
    participant_type: str       # club/national
    format_type: str            # round_robin/group_knockout/knockout/single_match

    # 赛事阶段
    stage: str                  # regular/group/r16/quarter/semi/final/3rd_place
    leg: str                    # single/first/second
    is_neutral_venue: bool
    round_num: int

    # 赛季阶段
    season_phase: str           # early/mid/late/post_season/off_season
    season_progress: float      # 0.0-1.0

    # 分析参数(核心!)
    weights: dict               # 各因子权重集(按赛事类型不同)
    home_advantage_base: float  # 主场优势基线
    xg_baseline: tuple          # (home_xg, away_xg)
    draw_baseline: float

    # 修正开关
    use_friendly_intel: bool    # 5维度友谊赛修正
    use_cup_upset: bool         # 杯赛爆冷修正
    use_motivation: bool        # 动机分析
    use_form_filter: str        # all/same_type/league_only
    rotation_risk: float        # 轮换风险基线

    # 可解释性
    classification_reason: str
    rule_sources: list
```

---

### 权重集(按赛事类型)

```python
WEIGHT_PROFILES = {
    'league': {
        'elo': 0.30, 'form': 0.25, 'h2h': 0.15, 'poisson': 0.15,
        'home_away': 0.10, 'motivation': 0.05,
    },
    'domestic_cup': {
        'elo': 0.25, 'form': 0.15, 'h2h': 0.15, 'poisson': 0.10,
        'home_away': 0.05, 'cup_motivation': 0.15, 'upset_factor': 0.15,
    },
    'continental_cup': {
        'elo': 0.25, 'form': 0.15, 'h2h': 0.20, 'poisson': 0.10,
        'home_away': 0.05, 'cup_motivation': 0.10, 'upset_factor': 0.10,
        'cross_league': 0.05,
    },
    'friendly': {
        'odds': 0.35, 'fifa_ranking': 0.20, 'friendly_intel': 0.25,
        'form': 0.10, 'h2h': 0.10,
    },
    'international_cup': {
        'elo': 0.25, 'fifa_ranking': 0.15, 'form': 0.15, 'h2h': 0.15,
        'poisson': 0.10, 'motivation': 0.10, 'stage_factor': 0.10,
    },
}
```

---

### 赛事识别: DB优先 + 关键词兜底

- DB leagues表(202条)有competition_type/format_type/participant_type → 最准
- 关键词兜底: 当league_id缺失时从联赛名推断
- 赛季阶段: 用league_rules表的season_start_month/season_end_month计算(北欧4-11月,欧洲8-5月,J联赛2-12月)

---

### 部署适配

```
同一套代码
├── 本地开发: SQLite + Windows定时 + 文件推送
├── 云服务器: PostgreSQL + cron/Docker + API推送
└── 区别只在: config.yaml + DataProvider实现
```

代码不关心跑在哪，只关心:
- 从DataProvider读数据
- 把结果写给ResultStore
- 把记忆写给MemoryStore

---

### 实施路径

**第一步: 让分析师活起来(最小闭环)**
- daily_runner.py: 醒来→采集→分析→存预测→推送
- 次日: 复盘→拿结果→对比→存准确率→微调参数

**第二步: 让分析师变聪明**
- 赛事规则引擎(让分类从硬编码变成知识)
- 参数自学习(从8492场历史数据里学)
- 场景画像("友谊赛赔率<1.30我容易错"这种自我认知)

**第三步: 让分析师上云**
- DataProvider抽象(SQLite→PostgreSQL)
- 配置中心(config.yaml)
- 容器化

---

### 待打磨细节

- 参数怎么从"拍脑袋"变成"数据学出来"(回归/网格搜索/贝叶斯优化)
- 复盘时"翻车归因"具体怎么做(归错原因比不归因更危险)
- 推送格式(md文件/API/微信/钉钉)
- "醒来"的时机(体彩开售时间不固定,oddsfe数据到的时间也不固定)
- 准确率统计维度(按赛事类型/赔率区间/修正类型/时间趋势/有情报vs无情报)
- CLV信号的具体使用方式(开盘→收盘方向变化)
- 冷启动(新球队没Elo/form/H2H怎么处理)
- 可解释性(因子贡献分解,修正幅度展示)
- 数据源容灾(oddsfe挂了→sporttery备选)
- 模型版本管理(预测存model_version,参数变更有历史,可回退)

### 已有基础设施(复用)

- backend/app/lottery/ — 完整的lottery系统(分析服务+验证+权重优化+调度+API+DAO+ETL)
- fetchers/pre_match/ — 5维度修正(雇佣/球迷/动机/疲劳/场地)
- fetchers/odds_feed_api/ — oddsfe采集(8492场友谊赛历史)
- fetchers/sporttery/ — 体彩赔率采集
- fetchers/common/team_names.py — 队名标准化(4个数据源,1169条)
- backend/app/analytics/cup.py + cup_factors.py — 杯赛分析器
- backend/app/analytics/comprehensive.py — 综合分析器
- backend/app/analytics/motivation.py — 动机分析器
- DB: football_v2.db 70表, 137K matches, 7487 teams, 269 league_rules
