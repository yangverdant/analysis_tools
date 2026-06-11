# 窗口3: P3 Agent决策层 + P4 完善

## 核心任务
1. Claude Agent SDK封装(5个决策点)
2. 参数学习闭环(Agent+回测)
3. 热启动回测
4. CLV赔率更新
5. 前端分析详情页+可视化
6. 部署方案

---

## Step 1: Claude Agent封装 (1天)

**目录:** `backend/app/core/agent/`

### client.py

```python
"""Claude Agent SDK封装 — 只在5个推理场景调用"""
import json
import logging
import anthropic
from typing import Optional

logger = logging.getLogger(__name__)

class AnalystAgent:
    """足球分析师Agent"""

    def __init__(self, api_key: str, base_url: str = None):
        kwargs = {'api_key': api_key}
        if base_url:
            kwargs['base_url'] = base_url
        self.client = anthropic.Anthropic(**kwargs)

    def run(self, prompt: str, system: str = None, model: str = 'claude-haiku-4-5-20251001',
            max_tokens: int = 1024) -> dict:
        """调用Claude，返回结构化JSON"""
        try:
            response = self.client.messages.create(
                model=model,
                max_tokens=max_tokens,
                system=system or self._default_system_prompt(),
                messages=[{'role': 'user', 'content': prompt}],
            )

            # 提取文本内容
            text = response.content[0].text

            # 尝试解析JSON
            try:
                # 找到JSON部分(可能包裹在```json```中)
                if '```json' in text:
                    text = text.split('```json')[1].split('```')[0]
                elif '```' in text:
                    text = text.split('```')[1].split('```')[0]
                return json.loads(text.strip())
            except json.JSONDecodeError:
                return {'raw_response': text}

        except Exception as e:
            logger.error(f"Agent call failed: {e}")
            return {'error': str(e)}

    def error_attribution(self, prediction, result, features) -> dict:
        """翻车归因 — Haiku"""
        from config.config_loader import load_agent_prompt
        system = load_agent_prompt('error_attribution')
        prompt = f"""
预测: 主胜{prediction['home_win']:.0%} 平{prediction['draw']:.0%} 客胜{prediction['away_win']:.0%}
推荐: {prediction['recommendation']} (置信度{prediction['confidence_level']})
实际: {result['spf_result']} ({result['home_goals_ft']}-{result['away_goals_ft']})
赔率基线推荐: {prediction.get('odds_baseline_rec', 'unknown')}
模型与赔率{''一致' if prediction.get('model_vs_odds', {}).get('agreement') else '不一致'}
赛事类型: {features.get('competition_type', 'unknown')}
5维度修正: {features.get('friendly_adjustment', 'none')}
修正方向: {features.get('correction_direction', 'none')}
"""
        return self.run(prompt, system=system, model='claude-haiku-4-5-20251001')

    def param_adjustment(self, scene_accuracy: dict, current_weights: dict) -> dict:
        """参数调整 — Sonnet"""
        from config.config_loader import load_agent_prompt
        system = load_agent_prompt('param_adjustment')
        prompt = f"""
场景准确率(30天):
{json.dumps(scene_accuracy, indent=2, ensure_ascii=False)}

当前权重:
{json.dumps(current_weights, indent=2, ensure_ascii=False)}

请分析哪些场景的权重需要调整，给出方向和理由。
"""
        return self.run(prompt, system=system, model='claude-sonnet-4-6', max_tokens=2048)

    def anomaly_diagnosis(self, error_info: dict, source_health: dict) -> dict:
        """异常诊断 — Haiku"""
        from config.config_loader import load_agent_prompt
        system = load_agent_prompt('anomaly_diagnosis')
        prompt = f"""
异常信息: {json.dumps(error_info, ensure_ascii=False)}
数据源健康: {json.dumps(source_health, ensure_ascii=False)}
请诊断异常原因并给出降级方案。
"""
        return self.run(prompt, system=system, model='claude-haiku-4-5-20251001')

    def strategy_select(self, today_matches: dict, accuracy: dict) -> dict:
        """策略选择 — Haiku"""
        from config.config_loader import load_agent_prompt
        system = load_agent_prompt('strategy_select')
        prompt = f"""
今日赛事构成: {json.dumps(today_matches, ensure_ascii=False)}
近期准确率: {json.dumps(accuracy, ensure_ascii=False)}
请推荐今日应该使用哪套权重/策略。
"""
        return self.run(prompt, system=system, model='claude-haiku-4-5-20251001')

    def new_scenario(self, features: dict, similar_historical: list) -> dict:
        """新场景识别 — Sonnet"""
        from config.config_loader import load_agent_prompt
        system = load_agent_prompt('new_scenario')
        prompt = f"""
新场景特征: {json.dumps(features, ensure_ascii=False)}
相似历史: {json.dumps(similar_historical[:5], ensure_ascii=False)}
请识别这是什么类型的新场景，应该如何归类。
"""
        return self.run(prompt, system=system, model='claude-sonnet-4-6')

    def _default_system_prompt(self) -> str:
        return "你是一名专业的足球分析师AI助手。你的输出必须是JSON格式。"
```

### tools.py — Agent可用工具(未来扩展)

```python
"""Agent工具定义 — 未来版本可传给Claude tool_use"""

AGENT_TOOLS = [
    {
        'name': 'read_db',
        'description': '查询football_v2.db数据库(只读)',
        'input_schema': {
            'type': 'object',
            'properties': {
                'sql': {'type': 'string', 'description': 'SQL查询(SELECT only)'}
            },
            'required': ['sql']
        }
    },
    {
        'name': 'backtest_query',
        'description': '查询历史回测结果',
        'input_schema': {
            'type': 'object',
            'properties': {
                'factor': {'type': 'string', 'description': '因子名'},
                'scene': {'type': 'string', 'description': '场景类型'},
                'date_range': {'type': 'string', 'description': '日期范围'}
            }
        }
    }
]
```

---

## Step 2: Agent提示词模板 (1天)

**目录:** `config/agent_prompts/`

### error_attribution.md

```markdown
你是一名足球分析师，负责归因预测错误。

归因框架(按优先级):
1. bad_luck: 运气差(红牌/点球miss/伤停补时进球)，小概率事件发生了
2. close_match: 均势场(最高概率<40%)，预测方向本身就不确定
3. correction_wrong: 模型修正方向反了(5维度或杯赛修正把正确方向修错了)
4. market_wrong: 赔率基线也判断错了(连市场都错了→真正的不可预测)
5. model_bias: 模型系统偏差(某个场景反复出错)

注意:
- 如果模型和赔率基线推荐不一致，且赔率对了→更偏向correction_wrong
- 如果模型和赔率基线都错了→更偏向market_wrong或bad_luck
- 友谊赛翻车→优先考虑correction_wrong(5维度修正可能过度)

输出JSON:
{
    "attribution_type": "bad_luck|close_match|correction_wrong|market_wrong|model_bias",
    "confidence": 0.0-1.0,
    "detail": "一句话说明为什么归因为此类型",
    "actionable": true/false,
    "suggested_action": "如果actionable，建议做什么调整"
}
```

### param_adjustment.md

```markdown
你是一名足球分析师，负责参数调整决策。

核心原则:
1. 数据驱动: 只有统计数据支持的方向才调整
2. 小幅微调: ±10%以内，不大幅改动
3. 回测优先: 每个调整必须在历史数据上验证
4. 场景区分: 俱乐部赛事和国家队的参数应该分开调整

注意:
- 如果某个场景模型准确率 > 赔率基线+5% → 不需要调(已经好)
- 如果模型准确率 < 赔率基线 → 建议降模型权重
- 国家队场景form数据少 → form权重应该更低
- 友谊赛5维度修正如果准确率低 → 降低friendly权重

输出JSON:
{
    "adjustments": [
        {
            "scene": "场景名",
            "factor": "因子名",
            "current_weight": 0.XX,
            "suggested_weight": 0.XX,
            "direction": "increase|decrease",
            "reason": "原因",
            "backtest_required": true,
            "confidence": 0.0-1.0
        }
    ],
    "overall_assessment": "一段话总结当前模型状态"
}
```

### anomaly_diagnosis.md

```markdown
你是一名系统运维分析师，负责诊断数据采集异常。

可能的异常:
1. sporttery采集失败 → 体彩API变更/网络问题/开售延迟
2. oddsfe桥接失败 → 认证过期/赛事ID变更
3. 赔率异常(某场SPF赔率>15) → 数据源错误/比赛取消

输出JSON:
{
    "diagnosis": "异常原因描述",
    "severity": "low|medium|high|critical",
    "fallback_plan": "降级方案",
    "auto_recoverable": true/false,
    "estimated_recovery": "预计恢复时间"
}
```

### strategy_select.md

```markdown
你是一名足球策略分析师，负责选择今日分析策略。

考虑因素:
1. 今日赛事构成(多少联赛/杯赛/友谊赛/国家队)
2. 近期各类型准确率
3. 是否有熔断
4. 俱乐部赛事 vs 国家队赛事的占比

输出JSON:
{
    "recommended_mode": "normal|conservative|aggressive|odds_only",
    "weight_preset": "balanced|odds_heavy|model_heavy",
    "special_notes": "今日需要注意的事项",
    "confidence": 0.0-1.0
}
```

### new_scenario.md

```markdown
你是一名足球分析师，负责识别和归类新场景。

场景归类维度:
1. 赛事类型(8种)
2. 参赛方类型(俱乐部/国家队)
3. 赛季阶段(early/mid/late/playoff)
4. 特殊条件(德比/保级生死战/大赛前友谊赛)

输出JSON:
{
    "scenario_type": "归类结果",
    "similarity_to_known": 0.0-1.0,
    "recommended_handling": "建议如何处理",
    "rule_suggestion": "建议新增的规则"
}
```

---

## Step 3: learn.py 参数学习闭环 (2天)

**文件:** `backend/app/core/learn.py`

```python
"""参数学习 — 数据驱动 + 回测验证 + Agent确认"""

def learn(state) -> LearnResult:
    # 1. 按场景+参赛方类型统计准确率
    scene_stats = compute_scene_accuracy(
        days=30,
        min_samples=10,
        group_by=['competition_type', 'participant_type']  # 俱乐部/国家队分线
    )

    adjustments = []
    for (scene, p_type), stats in scene_stats.items():
        if stats.total < 10:
            continue

        # 2. 熔断检测
        if stats.model_accuracy < stats.odds_baseline - 0.03:
            adjustments.append({
                'scene': scene, 'participant_type': p_type,
                'action': 'reduce_model_weight',
                'reason': f'模型{stats.model_accuracy:.0%} < 赔率{stats.odds_baseline:.0%}'
            })
            continue

        # 3. 找问题因子
        problem_factors = identify_problem_factors(scene, p_type, stats)
        for factor, current_weight in problem_factors:
            direction = determine_direction(factor, stats)
            new_weight = current_weight * (1 + direction * 0.10)

            # 4. 回测验证(必须!)
            bt = backtest(factor, current_weight, new_weight, scene, p_type)
            if bt.improved:
                # 5. Agent确认(可选，只在调整幅度>5%时)
                if abs(new_weight - current_weight) / current_weight > 0.05:
                    decision = agent.param_adjustment(
                        {scene: stats},
                        get_current_weights(scene, p_type)
                    )
                    if not decision.get('approved', True):
                        continue  # Agent否决

                apply_weight_change(factor, current_weight, new_weight, scene, p_type)
                record_param_history(factor, current_weight, new_weight,
                                    scene=scene, participant_type=p_type,
                                    reason=f'{scene}({p_type})场景准确率低',
                                    backtest=bt)

    return LearnResult(adjustments=len(adjustments))
```

### 回测引擎

```python
def backtest(factor, old_weight, new_weight, scene, participant_type, sample_days=365) -> dict:
    """历史数据回测"""
    # 1. 取历史数据(按scene+participant_type过滤)
    # 2. 用old_weight跑一遍 → 算准确率
    # 3. 用new_weight跑一遍 → 算准确率
    # 4. 对比: new_accuracy > old_accuracy → improved=True
    # 5. 同时比较Brier分数

    return {
        'improved': new_accuracy > old_accuracy,
        'old_accuracy': old_accuracy,
        'new_accuracy': new_accuracy,
        'old_brier': old_brier,
        'new_brier': new_brier,
        'sample_size': count
    }
```

---

## Step 4: 热启动回测 (1天)

**文件:** `backend/app/core/warmup.py`

```python
"""冷启动热启动 — 用oddsfe历史数据做离线回测"""

def run_warmup(db_path: str) -> dict:
    """
    用oddsfe的8492场友谊赛历史数据做离线回测
    确定初始权重: 赔率为主还是模型为主
    """
    conn = sqlite3.connect(db_path)

    # 1. 从oddsfe历史数据中取友谊赛
    # oddsfe_prematch表有249797场，其中友谊赛约8492场
    friendlies = conn.execute("""
        SELECT op.* FROM oddsfe_prematch op
        JOIN leagues l ON op.league_id = l.league_id
        WHERE l.competition_type = 'friendly'
        AND op.home_score IS NOT NULL
        LIMIT 5000
    """).fetchall()

    if not friendlies:
        # fallback: 没有oddsfe数据 → 用默认权重
        return {
            'odds_accuracy': 0,
            'model_accuracy': 0,
            'initial_weights': 'default',
            'mode': 'default'
        }

    # 2. 纯赔率基线: 1/odds归一化 → argmax → 准确率
    odds_correct = 0
    model_correct = 0
    total = 0

    for match in friendlies:
        # 赔率基线
        if match['pinnacle_home'] and match['pinnacle_draw'] and match['pinnacle_away']:
            odds_probs = {
                'home_win': 1 / match['pinnacle_home'],
                'draw': 1 / match['pinnacle_draw'],
                'away_win': 1 / match['pinnacle_away'],
            }
            total_val = sum(odds_probs.values())
            for k in odds_probs:
                odds_probs[k] /= total_val

            odds_rec = max(odds_probs, key=odds_probs.get)
            actual = 'home_win' if match['home_score'] > match['away_score'] else \
                     'away_win' if match['home_score'] < match['away_score'] else 'draw'

            if odds_rec == actual:
                odds_correct += 1

            total += 1

    odds_accuracy = odds_correct / total if total else 0

    # 3. 模型准确率: 用ComprehensiveAnalyzer在同样数据上跑
    # (简化版: 不跑完整模型，只对比Elo)
    # 这部分可以后续完善

    # 4. 确定初始权重
    if odds_accuracy > 0.50:
        mode = 'odds_heavy'
        initial_weights = {'odds': 0.50, 'model': 0.50}
    else:
        mode = 'model_heavy'
        initial_weights = {'odds': 0.40, 'model': 0.60}

    return {
        'odds_accuracy': odds_accuracy,
        'model_accuracy': 0,  # TODO: 需要跑模型
        'initial_weights': initial_weights,
        'mode': mode,
        'sample_size': total
    }
```

---

## Step 5: CLV赔率更新 (1天)

**文件:** `backend/app/core/clv_update.py`

逻辑见plan文件14:00节。关键点:
- 14:00重新采集体彩赔率
- 对比opening vs midday
- >5%异动标记信号
- 写入lottery_odds(snapshot_type='midday')
- CLV信号: 赔率向模型方向移动 → 增强信心

---

## Step 6: 前端分析详情页 (2天)

### 新增页面: AnalysisDetail.vue

展示内容:
1. **因子分解饼图** — 每层分析对最终概率的贡献占比
2. **赔率vs模型对比** — 赔率说3模型说1，谁对了？
3. **翻车归因** — bad_luck/close_match/correction_wrong/market_wrong
4. **准确率趋势图** — 7天/30天/全部

### 新增组件: AccuracyTrend.vue

```vue
<template>
  <div class="accuracy-trend">
    <h3>准确率趋势</h3>
    <div class="chart">
      <!-- 用Chart.js或ECharts画折线图 -->
      <Line :data="chartData" :options="chartOptions" />
    </div>
    <div class="stats">
      <span>7天: {{ accuracy7d }}%</span>
      <span>30天: {{ accuracy30d }}%</span>
      <span>赔率基线: {{ oddsBaseline }}%</span>
    </div>
  </div>
</template>
```

### 新增组件: FactorBreakdown.vue

```vue
<template>
  <div class="factor-breakdown">
    <h3>因子贡献分解</h3>
    <!-- 饼图: 赔率35% + Elo25% + Poisson25% + Form10% + 其他5% -->
    <Pie :data="factorData" />
    <!-- 详细列表 -->
    <div v-for="(factor, name) in factors" :key="name">
      <span>{{ name }}</span>
      <span>推荐: {{ factor.recommendation }}</span>
      <span>贡献: +{{ factor.contribution }}</span>
    </div>
  </div>
</template>
```

---

## Step 7: 部署方案 (1天)

### docker-compose.yml

```yaml
version: '3.8'
services:
  analyst:
    build: .
    ports:
      - "8000:8000"
    environment:
      - DB_PATH=/app/data/football_v2.db
      - ANTHROPIC_API_KEY=${ANTHROPIC_API_KEY}
      - ANTHROPIC_BASE_URL=${ANTHROPIC_BASE_URL:-}
      - TZ=Asia/Shanghai
    volumes:
      - ./data:/app/data
      - ./config:/app/config
      - ./logs:/app/logs
    restart: unless-stopped
```

### Dockerfile

```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
EXPOSE 8000
CMD ["uvicorn", "backend.app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### .env.template

```
ANTHROPIC_API_KEY=sk-your-key-here
ANTHROPIC_BASE_URL=
```

### 一键启动

```bash
# 启动
cp .env.template .env
# 编辑 .env 填入API Key
docker-compose up -d

# 查看日志
docker-compose logs -f analyst

# 首次运行(热启动)
docker-compose exec analyst python -m backend.app.core.daily_runner --mode full
```

---

## 验证清单

- [ ] Agent 5个决策点都能调用成功
- [ ] Agent输出是结构化JSON
- [ ] 提示词模板加载正确
- [ ] 参数学习有回测验证步骤
- [ ] Agent可以否决参数调整
- [ ] 热启动能算出初始权重
- [ ] CLV更新能检测>5%异动
- [ ] 前端分析详情页能展示因子分解
- [ ] 准确率趋势图可看7天/30天
- [ ] docker-compose up能启动
- [ ] 首次运行自动热启动
