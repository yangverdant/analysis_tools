# 窗口2: P2 分析改进 — 俱乐部/国家队分线 + MatchProfile + 分析器改造

## 核心任务
1. 建CompetitionRuleEngine(8种赛事类型)
2. 俱乐部 vs 国家队分析分线
3. ComprehensiveAnalyzer改造为MatchProfile驱动
4. intel环节增强(停赛/轮换/比赛日)
5. form对手强度加权

---

## 核心认知: 俱乐部 vs 国家队是两条完全不同的线

### 为什么必须分线

| 维度 | 俱乐部 | 国家队 |
|------|--------|--------|
| 球员归属 | 固定合同，转会窗才变 | 征召制，每次比赛阵容不同 |
| 战术体系 | 长期训练，体系稳定 | 集训短，体系不确定 |
| 赛事时长 | 90分钟(联赛) | 90分钟+加时(淘汰赛) |
| 排兵布阵 | 主力+替补明确 | 征召+退出+伤病，赛前才确定 |
| 友谊赛意义 | 赛季前热身/考察新人 | FIFA排名积分/磨合阵容 |
| Form参考 | 近期联赛form可靠 | 近期国家队form少(一年才几场) |
| 主场优势 | 球迷+场地熟悉 | 中立场或国家荣誉加持 |
| 动机 | 保级/争冠/欧战资格 | 出线/排名/荣誉 |
| 数据覆盖 | Elo(713队) + form(3349队) | FIFA排名(423) + Elo(324) |

### DB数据现状
- teams表: club=3108, national=4379
- leagues表: club=179, national=23
- elo_ratings: club=713, national=324
- fifa_rankings: 423条
- team_form: 3349条(主要是俱乐部)

### 关键问题
国家队form几乎为空 → FormAnalyzer对国家队无效
FIFA排名和Elo是两套体系 → 不能混用
国家队友谊赛前的友谊赛 → 有特殊意义(FIFA排名积分+磨合)

---

## Step 1: CompetitionRuleEngine (1天)

**文件:** `backend/app/core/competition/engine.py`

### 8种赛事类型

```python
COMPETITION_TYPES = [
    'league',              # 联赛(俱乐部)
    'domestic_cup',        # 国内杯赛(俱乐部)
    'continental_cup',     # 洲际杯赛(俱乐部)
    'qualifier',           # 预选赛(国家队)
    'nations_league',      # 欧国联(国家队)
    'international_cup',   # 国际杯赛(国家队)
    'olympic',             # 奥运会(U23+超龄，特殊)
    'friendly',            # 友谊赛(俱乐部或国家队)
]
```

### 分类逻辑

```python
class CompetitionRuleEngine:
    def classify(self, match_info: dict) -> MatchProfile:
        # Step 1: 识别participant_type (club vs national)
        participant_type = self._identify_participant_type(match_info)

        # Step 2: 识别competition_type (DB优先+关键词兜底)
        competition_type = self._identify_competition(match_info)

        # Step 3: 如果是'international'，进一步细分
        if competition_type == 'international':
            competition_type = self._refine_international(match_info)

        # Step 4: 识别赛事阶段
        stage = self._detect_stage(match_info)

        # Step 5: 识别赛季阶段
        season_phase = self._assess_season_phase(match_info)

        # Step 6: 生成MatchProfile
        return self._build_profile(
            competition_type, participant_type, stage, season_phase, match_info
        )
```

### participant_type 识别

```python
def _identify_participant_type(self, match_info: dict) -> str:
    """识别参赛方类型: club / national / mixed"""
    home_type = self._get_team_type(match_info.get('home_team_id'))
    away_type = self._get_team_type(match_info.get('away_team_id'))

    if home_type == 'national' and away_type == 'national':
        return 'national'
    elif home_type == 'club' and away_type == 'club':
        return 'club'
    else:
        return 'mixed'  # 罕见但可能存在(俱乐部vs国家队表演赛)

def _get_team_type(self, team_id: int) -> str:
    """从teams表查team_type"""
    if not team_id:
        return 'unknown'
    # 查DB: SELECT team_type FROM teams WHERE team_id = ?
    result = self.db.execute(
        "SELECT team_type FROM teams WHERE team_id = ?", (team_id,)
    ).fetchone()
    return result['team_type'] if result else 'unknown'
```

### friendly 的 participant_type 判断

友谊赛既可能是俱乐部也可能是国家队。判断依据:
1. DB leagues表的participant_type字段
2. 两队的team_type字段
3. 赛事名称关键词("国际友谊赛" vs "俱乐部友谊赛")

**国家队友谊赛的特殊意义:**
- FIFA排名积分: 赢了加分，输了扣分 → 不是纯练兵
- 世预赛前的友谊赛: 磨合阵容 → 不会大幅轮换
- 赛季末的友谊赛: 走过场 → 大幅轮换

**俱乐部友谊赛的特殊意义:**
- 赛季前: 体能+战术演练 → 不可信
- 赛季中: 休息/轮换 → 不可信

---

## Step 2: MatchProfile — 俱乐部/国家队分线 (1天)

**文件:** `backend/app/core/competition/engine.py` (同文件)

### MatchProfile定义

```python
@dataclass
class MatchProfile:
    # 基础信息
    competition_type: str           # 8种之一
    participant_type: str           # club / national / mixed
    format_type: str                # round_robin / knockout / group_knockout / single_match
    stage: str                      # group / knockout / final / regular
    season_phase: str               # early / mid / late / playoff / off_season

    # 分析策略开关
    use_friendly_intel: bool = False
    use_cup_upset: bool = False
    use_motivation: bool = True
    use_form_filter: str = 'all'   # all / league_only / same_type / national_only

    # 实力评估方式
    strength_method: str = 'elo'    # elo / fifa / odds_only
    # club → EloAnalyzer
    # national → FIFA排名(有数据时) 或 赔率反推(无FIFA时)

    # 概率基线
    home_advantage_base: float = 0.05
    draw_baseline: float = 0.26
    xg_baseline: tuple = (1.3, 1.1)

    # 赛程/轮换
    schedule_density: float = 1.0   # 0.5(密集) - 1.5(充裕)
    rotation_risk: str = 'low'      # low / medium / high

    # 动机
    motivation_matchup: str = 'normal'  # clash / synergy / normal / irrelevant

    # 权重
    weights: dict = None

    # 模型版本
    model_version: str = 'v4.0'
```

### 俱乐部 vs 国家线 的默认Profile

```python
CLUB_PROFILES = {
    'league': MatchProfile(
        participant_type='club',
        use_motivation=True, use_form_filter='league_only',
        strength_method='elo',
        home_advantage_base=0.05, draw_baseline=0.26,
        weights={'odds': 0.35, 'elo': 0.25, 'poisson': 0.25, 'form': 0.10, 'other': 0.05}
    ),
    'domestic_cup': MatchProfile(
        participant_type='club',
        use_cup_upset=True, use_motivation=True,
        use_form_filter='all', strength_method='elo',
        rotation_risk='medium',
        weights={'odds': 0.35, 'elo': 0.20, 'poisson': 0.20, 'form': 0.10, 'cup': 0.15}
    ),
    'continental_cup': MatchProfile(
        participant_type='club',
        use_cup_upset=True, use_motivation=True,
        use_form_filter='same_type', strength_method='elo',
        rotation_risk='medium',
        weights={'odds': 0.35, 'elo': 0.20, 'poisson': 0.20, 'form': 0.10, 'cup': 0.15}
    ),
    'friendly': MatchProfile(
        participant_type='club',
        use_friendly_intel=True, use_motivation=False,
        use_form_filter='same_type', strength_method='elo',
        home_advantage_base=0.02, draw_baseline=0.33,
        rotation_risk='high',
        weights={'odds': 0.45, 'elo': 0.15, 'poisson': 0.15, 'form': 0.05, 'friendly': 0.20}
    ),
}

NATIONAL_PROFILES = {
    'qualifier': MatchProfile(
        participant_type='national',
        use_motivation=True, use_form_filter='national_only',
        strength_method='fifa',
        home_advantage_base=0.04, draw_baseline=0.27,
        weights={'odds': 0.40, 'fifa': 0.20, 'poisson': 0.15, 'form': 0.05, 'motivation': 0.20}
    ),
    'nations_league': MatchProfile(
        participant_type='national',
        use_motivation=True, use_form_filter='national_only',
        strength_method='fifa',
        weights={'odds': 0.40, 'fifa': 0.20, 'poisson': 0.15, 'form': 0.05, 'motivation': 0.20}
    ),
    'international_cup': MatchProfile(
        participant_type='national',
        use_cup_upset=True, use_motivation=True,
        use_form_filter='national_only', strength_method='fifa',
        weights={'odds': 0.35, 'fifa': 0.20, 'poisson': 0.15, 'form': 0.10, 'cup': 0.10, 'motivation': 0.10}
    ),
    'friendly': MatchProfile(
        participant_type='national',
        use_friendly_intel=True, use_motivation=False,
        use_form_filter='national_only', strength_method='fifa',
        home_advantage_base=0.02, draw_baseline=0.33,
        rotation_risk='medium',  # 国家队友谊赛轮换率中等
        weights={'odds': 0.45, 'fifa': 0.15, 'poisson': 0.10, 'form': 0.05, 'friendly': 0.25}
    ),
    'olympic': MatchProfile(
        participant_type='national',
        use_motivation=True, use_form_filter='national_only',
        strength_method='fifa',  # 但U23限制导致FIFA排名参考价值降低
        home_advantage_base=0.03, draw_baseline=0.30,
        weights={'odds': 0.45, 'fifa': 0.10, 'poisson': 0.15, 'form': 0.05, 'motivation': 0.25}
    ),
}
```

**国家队友谊赛前的友谊赛(新增场景):**

```python
def _assess_friendly_context(self, match_info: dict, profile: MatchProfile) -> MatchProfile:
    """评估国家队友谊赛的上下文"""
    date = match_info.get('match_date', '')

    # 检查是否有即将到来的预选赛/大赛
    upcoming = self._check_upcoming_national_matches(date, days=30)
    if upcoming:
        if upcoming[0]['type'] in ('qualifier', 'international_cup'):
            # 世预赛/大赛前的友谊赛 → 磨合阵容，不会大幅轮换
            profile.rotation_risk = 'medium'  # 不是high
            profile.use_motivation = True     # 有排名/磨合动机
            profile.weights['friendly'] = 0.15  # 降5维度权重(更认真)
        elif upcoming[0]['type'] == 'nations_league':
            profile.rotation_risk = 'medium'
            profile.use_motivation = True
    else:
        # 无近期大赛 → 纯练兵，大幅轮换
        profile.rotation_risk = 'high'
        profile.use_motivation = False

    # FIFA排名积分检测(友谊赛也有排名积分)
    if self._is_fifa_ranking_match(date):
        # 有FIFA排名积分的友谊赛 → 动机+1
        profile.use_motivation = True
        profile.motivation_matchup = 'ranking_points'

    return profile
```

---

## Step 3: 国家队实力评估 (1天)

### 问题: 国家队FIFA排名 → 概率转换

EloAnalyzer用Elo差→概率，但国家队用FIFA排名，公式不同。

```python
class NationalTeamStrengthEstimator:
    """国家队实力评估 — FIFA排名优先，Elo补充"""

    def estimate(self, home_team_id, away_team_id, conn) -> dict:
        # 1. 尝试FIFA排名
        home_fifa = self._get_fifa_rank(home_team_id, conn)
        away_fifa = self._get_fifa_rank(away_team_id, conn)

        if home_fifa and away_fifa:
            return self._fifa_to_probability(home_fifa, away_fifa)

        # 2. 尝试Elo
        home_elo = self._get_elo(home_team_id, conn)
        away_elo = self._get_elo(away_team_id, conn)

        if home_elo and away_elo:
            return self._elo_to_probability(home_elo, away_elo)

        # 3. 都没有 → 赔率反推
        return {'method': 'odds_only', 'confidence': 'low'}

    def _fifa_to_probability(self, home_fifa, away_fifa) -> dict:
        """FIFA排名差 → 概率"""
        # FIFA排名越低越强(1=最强)
        rank_diff = away_fifa['rank'] - home_fifa['rank']

        # 经验公式(需从历史数据校准):
        # rank_diff > 30 → 强队明显占优
        # rank_diff 10-30 → 有优势
        # rank_diff < 10 → 均势

        home_base = 0.40 + rank_diff * 0.003  # 粗略线性
        home_base = max(0.15, min(0.70, home_base))
        draw_base = 0.27 - abs(rank_diff) * 0.001
        draw_base = max(0.20, min(0.35, draw_base))
        away_base = 1 - home_base - draw_base

        return {
            'method': 'fifa',
            'probabilities': {'home_win': home_base, 'draw': draw_base, 'away_win': away_base},
            'home_fifa': home_fifa,
            'away_fifa': away_fifa,
            'rank_diff': rank_diff
        }
```

**FIFA排名→概率公式需要从历史数据校准！** 这是中期任务。短期用粗略线性。

---

## Step 4: ComprehensiveAnalyzer改造 (2天)

**文件:** `backend/app/analytics/comprehensive.py`

### 改造点1: 入口加match_profile参数

```python
def comprehensive_prediction(self, home_team_id, away_team_id,
                             league_id=None, season_id=None,
                             match_date=None, conn=None,
                             match_profile=None):  # 新增
```

### 改造点2: 实力评估分线

```python
    # 替换固定Elo评估为分线评估
    if match_profile and match_profile.strength_method == 'fifa':
        strength_prediction = NationalTeamStrengthEstimator().estimate(
            home_team_id, away_team_id, conn
        )
        elo_prediction = strength_prediction  # 复用变量名
    else:
        elo_prediction = self.elo.calculate_match_elo_prediction(
            home_team_id, away_team_id, conn
        )
```

### 改造点3: 特殊修正MatchProfile驱动

```python
    # 替换硬编码友谊赛检测
    # 旧: if league_name_en.lower() in ('friendly', 'friendlies', 'international'):
    # 新:
    if match_profile:
        if match_profile.use_friendly_intel:
            pre_match_intel = self._apply_friendly_intel(...)
        if match_profile.use_cup_upset:
            pre_match_intel = self._apply_cup_upset(...)
        if match_profile.use_motivation and match_profile.participant_type == 'national':
            # 国家队动机: 出线形势/排名积分
            pre_match_intel = self._apply_national_motivation(...)
```

### 改造点4: 赔率基线

```python
    # 每次预测记录赔率基线
    odds_baseline = self._get_odds_baseline(lottery_match_id, conn)
    prediction['odds_baseline'] = odds_baseline
    prediction['model_vs_odds'] = {
        'model_rec': argmax(final_probs),
        'odds_rec': argmax(odds_baseline) if odds_baseline else None,
        'agreement': argmax(final_probs) == argmax(odds_baseline) if odds_baseline else None
    }
```

### 改造点5: 因子分解

```python
    prediction['factor_breakdown'] = {
        'strength': {
            'method': match_profile.strength_method if match_profile else 'elo',
            'prob': elo_prediction.get('probabilities', {}),
            'weight': match_profile.weights.get('elo', 0.20) if match_profile else 0.20
        },
        'poisson': {
            'prob': poisson_prediction['probabilities'],
            'weight': match_profile.weights.get('poisson', 0.25) if match_profile else 0.25
        },
        # ... 每层的贡献
    }
```

---

## Step 5: intel环节增强 (1天)

**文件:** `backend/app/core/intel.py`

### 新增: 红黄牌停赛查询

```python
def fetch_suspensions(match_date) -> dict:
    """查询红黄牌停赛(apifootball suspensions端点)"""
    matches = match_dao.find_by_date(match_date)
    results = {}
    for match in matches:
        if match.apifootball_id:  # 需要source_mapping_bridge桥接
            suspensions = apifootball_client.get_suspensions(match.apifootball_id)
            if suspensions:
                key_players = [s for s in suspensions if s.get('is_key_player')]
                results[match.lottery_match_id] = {
                    'suspended': suspensions,
                    'key_players_missing': len(key_players),
                    'impact': 'high' if key_players else 'low'
                }
    return results
```

### 新增: 国际比赛日检测

```python
def check_international_break(match_date) -> dict:
    """检测是否在国际比赛日窗口"""
    # FIFA国际比赛日窗口: 每年3/6/9/10/11月
    # 如果match_date在窗口内 → 国家队被征召 → 俱乐部比赛轮换风险
    fifa_windows = load_fifa_calendar()  # 需要FIFA日历数据
    is_window = any(start <= match_date <= end for start, end in fifa_windows)

    if is_window:
        return {
            'is_international_break': True,
            'impact_on_club': 'rotation_risk_high',
            'detail': '国际比赛日，俱乐部主力可能被征召'
        }
    return {'is_international_break': False}
```

### 新增: 轮换率推断

```python
def estimate_rotation_risk(match_info) -> dict:
    """从历史数据推断轮换风险"""
    comp_type = match_info.get('competition_type')

    # 友谊赛轮换率(历史统计)
    FRIENDLY_ROTATION_RATE = {
        'club': 0.65,       # 俱乐部友谊赛65%概率大幅轮换
        'national_warmup': 0.40,  # 大赛前的国家队友谊赛40%
        'national_ranking': 0.25, # 有排名积分的友谊赛25%
    }

    # 杯赛轮换率
    CUP_ROTATION_RATE = {
        'domestic_cup_early': 0.45,  # 国内杯赛早期
        'domestic_cup_late': 0.15,   # 国内杯赛后期
        'continental_group': 0.30,   # 欧冠小组赛
        'continental_knockout': 0.05, # 欧冠淘汰赛
    }

    # 3天内是否有更重要的比赛?
    has_bigger_match = check_schedule_conflict(match_info, days=3)

    return {
        'rotation_probability': ...,  # 0-1
        'reason': '...',
        'key_players_at_risk': has_bigger_match
    }
```

---

## Step 6: form对手强度加权 (0.5天)

**文件:** `backend/app/analytics/form.py` 修改

```python
def compare_teams_form(self, team1_id, team2_id, recent_matches=6, conn=None):
    """带对手强度加权的form对比"""
    # 原有逻辑获取raw form
    raw_form = self._get_raw_form(team1_id, recent_matches, conn)

    # 新增: 对手强度加权
    team1_elo = self._get_team_elo(team1_id, conn)
    for match in raw_form['matches']:
        opp_elo = self._get_team_elo(match['opponent_id'], conn)
        if opp_elo and team1_elo:
            ratio = opp_elo / team1_elo
            # 对手弱→胜场打折, 对手强→胜场加权
            if match['result'] == 'W':
                match['weighted_value'] = min(1.5, ratio)  # 上限1.5
            elif match['result'] == 'L':
                match['weighted_value'] = max(0.5, 2 - ratio)  # 输给弱队更差
            else:
                match['weighted_value'] = 1.0

    # 用weighted_value重新计算form_score
    adjusted_score = sum(m.get('weighted_value', 1) for m in raw_form['matches'] if m['result'] == 'W')
    raw_form['form_score_adjusted'] = adjusted_score

    return raw_form
```

---

## 验证清单

- [ ] CompetitionRuleEngine能识别8种赛事类型
- [ ] participant_type能区分club/national
- [ ] 国家队比赛用FIFA排名而非Elo评估实力
- [ ] 友谊赛前的友谊赛有特殊profile(rotation_risk=medium而非high)
- [ ] ComprehensiveAnalyzer接受match_profile参数
- [ ] form对手强度加权后准确率有变化(对比测试)
- [ ] intel环节能查询停赛+国际比赛日
