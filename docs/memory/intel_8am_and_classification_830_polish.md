---
name: intel_8am_and_classification_830_polish
description: 8:00情报采集+8:30赛事分类打磨——伤病/疲劳现状、CompetitionRuleEngine关键断点、DB优先识别、ExtractionContext改造
metadata: 
  node_type: memory
  type: project
  originSessionId: d2e763d6-7730-4e83-a6e7-3cc8d939df30
---

## 8:00 情报采集 + 8:30 赛事分类 打磨

### 8:00 情报采集 — 现状

**PreMatchNewsScanner (fetchers/pre_match/news_scanner.py):**
- 当前是占位实现——没有真实的数据源调用
- 返回空的TeamIntel，confidence=0
- 6月4-5日翻车场分析已确认: news_scanner无法获取伤病情报是主要翻车原因

**PlayerFatigueTracker (fetchers/pre_match/fatigue_tracker.py):**
- 基于赛季比赛数估算疲劳
- 缺少球员级数据(需要阵容数据)
- 对俱乐部有效(有赛季日程)，对国家队无效

**match_injuries表: 不存在**
- 需要新建或用pre_match_snapshot表(已有schema但为空)

**apifootball API:**
- 有injuries端点: `/injuries?fixture={id}`
- 但需要fixture_id(通过source_mapping_bridge桥接)
- 友谊赛伤病数据经常为空(apifootball不覆盖友谊赛)

### 8:00 修复方案

**短期(可立即做):**
1. PreMatchNewsScanner增加apifootball injuries端点调用
2. 桥接apifootball_id到source_mapping_bridge(在7:30采集时完成)
3. 对无伤病数据的比赛: impact_level='unknown'，伤病维度权重降为0

**中期(需要更多基础设施):**
1. 采集赛前阵容(赛前1h apifootball lineups端点)
2. 球员级疲劳追踪(需要出场时间数据)
3. 新闻情感分析(爬取赛前新闻)

**关键认知: 伤病情报缺失是常态不是异常**
- 友谊赛: apifootball经常无数据(已知限制)
- 小联赛: 可能没有coverage
- 模型设计时: L6情报修正层默认权重低，有数据才增加权重

### 8:30 赛事分类 — 核心断点

**当前3处杯赛检测不一致:**
1. `cup_factors.py` CUP_LEAGUES: 20个硬编码league_standard名
2. `ComprehensiveAnalyzer`: 检查`league_name_en`是否为'friendly'/'friendlies'/'international'
3. `EnhancedLinearModel`(如果存在): 可能有另一套CUP_KEYWORDS

**DB leagues表有202条，competition_type分布:**
| competition_type | count | participant_type |
|-----------------|-------|-----------------|
| league | 120 | club |
| domestic_cup | 34 | club |
| international | 21 | national |
| continental_cup | 14 | club |
| cup | 12 | club(泛指) |
| friendly | 1 | national |

**CUP_LEAGUES只有20个 → DB有60个杯赛没被检测**
- domestic_cup 34个中，只有FA Cup/DFB-Pokal等几个在CUP_LEAGUES
- continental_cup 14个中，只有Champions League/Europa League在CUP_LEAGUES
- "cup" 12个(泛指)完全没被CUP_LEAGUES覆盖

**ExtractionContext缺少competition_type字段**
- 当前字段: match_id, home_team_id, away_team_id, league_id, match_date, db_conn, lottery_match_id, handicap_line, odds, extra
- 没有match_type/competition_type → 16个feature extractor全部无法按赛事类型分支

### 8:30 修复方案: CompetitionRuleEngine

**核心: DB优先 + 关键词兜底**

```python
class CompetitionRuleEngine:
    def classify(self, match_info: dict) -> MatchProfile:
        # 1. 识别赛事类型 — DB优先
        competition_type, participant_type, format_type = self._identify_competition(match_info)

        # 2. 检测阶段
        stage, leg, is_neutral = self._detect_stage(match_info)

        # 3. 评估赛季阶段
        season_phase, season_progress = self._assess_season_phase(match_info)

        # 4. 获取基础Profile(按类型)
        profile = self._get_base_profile(competition_type)

        # 5. 叠加规则修正
        profile = self._apply_rules(profile, match_info, stage, season_phase)

        return profile

    def _identify_competition(self, match_info) -> tuple:
        # 优先: DB leagues表(最准)
        league_id = match_info.get('league_id')
        if league_id:
            league = self._get_league_from_db(league_id)
            if league:
                return league.competition_type, league.participant_type, league.format_type

        # 兜底: 从联赛名关键词推断
        league_name = match_info.get('league_name_cn', '') or match_info.get('league_name_en', '')
        return self._infer_from_keywords(league_name)
```

**_infer_from_keywords 逻辑:**
```python
def _infer_from_keywords(self, league_name: str) -> tuple:
    name = league_name.lower()

    # 友谊赛检测(中文+英文)
    if any(kw in name for kw in ['友谊赛', '友谊', 'friendly', 'friendlies', 'international match']):
        return 'friendly', 'national', 'single_match'

    # 世预赛/欧预赛
    if any(kw in name for kw in ['世预赛', '欧预赛', 'qualifier', 'world cup qualif', 'euro qualif']):
        return 'qualifier', 'national', 'group_knockout'

    # 国际杯赛
    if any(kw in name for kw in ['世界杯', '欧洲杯', '美洲杯', '亚洲杯', 'world cup', 'euro', 'copa america']):
        return 'international_cup', 'national', 'group_knockout'

    # 洲际杯赛(俱乐部)
    if any(kw in name for kw in ['欧冠', '欧联', '解放者杯', 'champions league', 'europa league']):
        return 'continental_cup', 'club', 'group_knockout'

    # 国内杯赛
    if any(kw in name for kw in ['足总杯', '国王杯', '杯赛', 'cup', 'pokal', 'copa']):
        return 'domestic_cup', 'club', 'knockout'

    # 默认: 联赛
    return 'league', 'club', 'round_robin'
```

**但! 体彩的特殊情况:**

体彩的league_name_cn是中文简短名(如"英超"、"日职"、"友谊赛")，不是标准league_standard。
- "英超" → 需要映射到league_id → 查DB leagues表的competition_type
- "友谊赛" → 关键词匹配 → friendly
- "世预赛" → 关键词匹配 → qualifier

**league_name_cn → league_id 的映射:**
当前没有直接映射。需要:
1. 查lottery_matches的league_name_cn
2. 用name_cn或name_en模糊匹配leagues表
3. 匹配不到 → 用关键词兜底

### ExtractionContext改造

```python
@dataclass
class ExtractionContext:
    # 现有字段
    match_id: Optional[int] = None
    home_team_id: Optional[int] = None
    away_team_id: Optional[int] = None
    league_id: Optional[int] = None
    match_date: Optional[str] = None
    db_conn: Optional[sqlite3.Connection] = None
    lottery_match_id: Optional[str] = None
    handicap_line: float = 0
    odds: Optional[Dict] = None
    extra: Optional[Dict] = None

    # 新增字段
    match_profile: Optional[MatchProfile] = None  # 赛事类型画像
    competition_type: Optional[str] = None         # 快捷访问
```

这样feature extractor可以:
```python
def extract(self, context: ExtractionContext) -> FeatureResult:
    if context.competition_type == 'friendly':
        # 友谊赛专用逻辑
        ...
    elif context.competition_type == 'league':
        # 联赛专用逻辑
        ...
```

### 8:30输出 → 9:00消费

CompetitionRuleEngine.classify() 返回的MatchProfile直接传入9:00分析栈:
- profile.weights → 各层权重
- profile.use_friendly_intel → 是否启用5维度修正
- profile.use_cup_upset → 是否启用杯赛爆冷修正
- profile.use_motivation → 是否启用动机分析
- profile.use_form_filter → form过滤策略
- profile.home_advantage_base → 主场优势基线
- profile.xg_baseline → Poisson基线xG
- profile.draw_baseline → 平局概率基线
