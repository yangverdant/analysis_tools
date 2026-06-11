# 窗口B：分析质量提升 — MatchProfile驱动 + intel实现 + 赔率基线

## 目标
让分析器根据赛事类型（联赛/杯赛/友谊赛/世预赛等）使用不同策略和权重，赔率作为对比基线

## 当前状态
- analyze.py: 108行，调ComprehensiveAnalyzer但没传入MatchProfile
- classify.py: 已生成classification报告写入lottery_analysis_reports
- intel.py: 23行空壳，只返回占位信息
- CompetitionRuleEngine: 已在core/competition/engine.py实现，8种类型+俱乐部/国家队分线
- ComprehensiveAnalyzer: 6层分析栈已有，但不区分赛事类型
- collect.py: 已有oddsfe Pinnacle赔率写入lottery_odds

---

## 任务1: analyze接入MatchProfile — 赛事类型驱动分析路由

### 问题
analyze.py第77行调`analyzer.comprehensive_prediction()`时没传match_profile，所有比赛用同一套权重。

### 修改文件
1. `backend/app/core/analyze.py`
2. `backend/app/analytics/comprehensive.py`

### 修改方案

#### analyze.py
在`_analyze_single()`中：
1. 从`lottery_analysis_reports`读取该场比赛的classification报告
2. 反序列化为MatchProfile（或dict）
3. 传入`comprehensive_prediction(match_profile=profile)`

```python
def _analyze_single(db_path, match):
    # ... 现有代码 ...

    # 读取分类结果
    profile = _load_match_profile(db_path, match['lottery_match_id'])

    result = analyzer.comprehensive_prediction(
        home_team_id=home_id,
        away_team_id=away_id,
        league_id=match.get('league_id'),
        match_date=match.get('match_date'),
        match_profile=profile,  # 新增
    )
    # ...
```

#### comprehensive.py
在`comprehensive_prediction()`中：
1. 接受`match_profile`参数
2. 根据match_profile调整权重：
   - FRIENDLY_INTL: odds权重↑, form权重↓, 加draw_boost=0.08
   - CUP: 加upset_risk修正
   - WC_QUALIFIER/NATIONS_LEAGUE: 动机分析权重↑
3. 将match_profile写入报告

### 权重表（来自MatchProfile设计）
```python
WEIGHT_PROFILES = {
    'league':        {'odds': 0.35, 'elo': 0.25, 'poisson': 0.25, 'form': 0.10, 'other': 0.05},
    'cup':           {'odds': 0.35, 'elo': 0.20, 'poisson': 0.20, 'form': 0.10, 'cup': 0.15},
    'super_cup':     {'odds': 0.35, 'elo': 0.25, 'poisson': 0.20, 'form': 0.10, 'other': 0.10},
    'playoff':       {'odds': 0.40, 'elo': 0.20, 'poisson': 0.20, 'form': 0.10, 'motivation': 0.10},
    'wc_qualifier':  {'odds': 0.40, 'elo': 0.20, 'poisson': 0.20, 'form': 0.10, 'motivation': 0.10},
    'nations_league':{'odds': 0.40, 'elo': 0.20, 'poisson': 0.20, 'form': 0.10, 'motivation': 0.10},
    'friendly_intl': {'odds': 0.45, 'elo': 0.15, 'poisson': 0.15, 'form': 0.05, 'friendly': 0.20},
    'tournament_intl':{'odds': 0.35, 'elo': 0.25, 'poisson': 0.25, 'form': 0.10, 'motivation': 0.05},
}
```

### 特殊修正逻辑
1. **友谊赛**: draw_boost=0.08, rotation_risk=0.4, 如果赔率<1.40强队全翻车规则
2. **杯赛**: upset_risk=0.3, 两回合制修正
3. **世预赛**: motivation_weight=0.8, 两回合制修正

### 验证
```bash
python -c "
import sys; sys.path.insert(0, 'd:/football_tools')
# 清除今日预测重新分析
import sqlite3
conn = sqlite3.connect('d:/football_tools/data/football_v2.db')
conn.execute('DELETE FROM lottery_analysis_reports WHERE lottery_match_id LIKE \"20260608%\" AND report_type=\"prediction\"')
conn.commit(); conn.close()

from backend.app.core.analyze import analyze
r = analyze({}, 'd:/football_tools/data/football_v2.db')
print(f'analyzed={r[\"analyzed\"]}')

# 检查报告中有match_profile
conn = sqlite3.connect('d:/football_tools/data/football_v2.db')
import json
row = conn.execute('SELECT report_data FROM lottery_analysis_reports WHERE report_type=\"prediction\" LIMIT 1').fetchone()
data = json.loads(row[0])
print(f'match_profile: {data.get(\"match_profile\")}')
print(f'weights: {data.get(\"weights_used\")}')
conn.close()
"
```

---

## 任务2: 实现intel模块 — 赔率异动优先 + 伤停/天气补充

### 问题
intel.py只有23行占位代码。

### 修改文件
`backend/app/core/intel.py`

### 实现方案

#### 优先级1: 赔率异动检测（最有价值信息）
```python
def _detect_odds_movement(db_path, match_date):
    """对比opening vs 当前赔率"""
    conn = sqlite3.connect(db_path)
    # 获取今日比赛的开盘赔率
    # 获取oddsfe当前赔率
    # 计算3%+异动 → 标记信号
    # 返回: [{match_id, direction, magnitude, outcome}, ...]
```

#### 优先级2: 伤停信息（可能空）
```python
def _fetch_injuries(db_path, match_date):
    """查询apifootball injuries端点"""
    try:
        from fetchers.api_football.apifootball_client import get_injuries
        # ...
    except:
        return []
```

#### 优先级3: 天气（条件采集）
```python
def _fetch_weather(db_path, match_date):
    """只对露天+北欧/南美赛事采集"""
    WEATHER_SENSITIVE = ['俄超', '瑞超', '挪超', '芬超', '巴甲', '阿超']
    # ...
```

### 输出格式
```python
{
    'route': 'normal',
    'odds_movements': [...],
    'injuries': [...],
    'weather': [...],
    'rotations': [...],  # 友谊赛轮换风险评估
    'summary': '2场赔率异动, 0场伤病, 0场天气影响'
}
```

### 验证
```bash
python -c "
import sys; sys.path.insert(0, 'd:/football_tools')
from backend.app.core.intel import intel
r = intel({}, 'd:/football_tools/data/football_v2.db')
print(r)
"
```

---

## 任务3: 赔率基线对比 — model_vs_odds

### 问题
分析报告中`odds_baseline=None, model_vs_odds=None`，没有赔率对比基线。

### 修改文件
`backend/app/core/analyze.py`

### 修改方案
在`_analyze_single()`中，分析完成后：
1. 从`lottery_odds`读取该场的Pinnacle赔率
2. 计算隐含概率: `1/odds / sum(1/odds)`
3. 对比模型预测 vs 赔率基线
4. 写入`odds_baseline`和`model_vs_odds`字段

```python
# 在_save_report之前
odds_data = _get_match_odds(db_path, match['lottery_match_id'])
if odds_data:
    implied = _odds_to_implied_prob(odds_data)
    result['odds_baseline'] = implied
    result['model_vs_odds'] = {
        'model_rec': result['final_prediction']['predicted_result'],
        'odds_rec': max(implied, key=implied.get),
        'agreement': result['final_prediction']['predicted_result'] == max(implied, key=implied.get),
    }
```

### 验证
检查预测报告中有odds_baseline和model_vs_odds字段

---

## 任务4: 集成验证

### 步骤
1. 清除今日预测
2. 运行完整morning cycle
3. 检查预测报告包含:
   - match_profile（赛事分类信息）
   - odds_baseline（赔率基线概率）
   - model_vs_odds（模型vs赔率对比）
   - weights_used（使用的权重配置）
4. 友谊赛预测应有draw_boost和rotation_risk

### 成功标准
- 3场比赛预测都有match_profile
- 有赔率的2场有odds_baseline和model_vs_odds
- 友谊赛的draw_baseline > 0.26（默认联赛值）
