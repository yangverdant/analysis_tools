---
name: window2_analysis_refactor
description: 窗口2 P2分析改进完成—8种赛事类型、俱乐部/国家队分线、NationalTeamStrengthEstimator、ComprehensiveAnalyzer MatchProfile改造、intel增强、form对手强度加权
metadata: 
  node_type: memory
  type: project
  originSessionId: d00bd7d5-0cc9-43df-9324-85bed165b15c
---

## 窗口2完成状态

### 已改文件

| 文件 | 改动 |
|------|------|
| `core/competition/engine.py` | **重写**: 8种CompetitionType + ParticipantType + MatchProfile + CompetitionRuleEngine |
| `core/competition/__init__.py` | 更新导出 |
| `core/classifier.py` | 更新: JOIN teams表获取team_type, 传给engine |
| `backend/app/analytics/national_strength.py` | **新建**: NationalTeamStrengthEstimator (FIFA→Elo→unknown三级) |
| `backend/app/analytics/comprehensive.py` | **改造**: match_profile参数、国家队FIFA评估、MatchProfile驱动修正(平局/中立场/友谊赛)、赔率基线+因子分解+model_vs_odds |
| `core/intel.py` | **新建**: IntelCollector (赔率异动/停赛/天气/轮换/国际比赛日) |
| `backend/app/analytics/form.py` | **改造**: 对手强度加权analyze_form_with_opponent_strength() |

### 8种赛事类型映射

```
俱乐部线: LEAGUE, CUP, SUPER_CUP, PLAYOFF
国家队线: WC_QUALIFIER, NATIONS_LEAGUE, FRIENDLY_INTL, TOURNAMENT_INTL
```

### 关键验证结果
- engine分类: 国际友谊赛→friendly_intl/national, EPL→league/club ✅
- NationalTeamStrengthEstimator: Japan vs Brazil → FIFA method, 36%/26%/38% ✅
- 所有模块import通过 ✅

### 待后续
- FIFA排名→概率公式需历史数据校准(当前用粗略线性)
- intel天气采集需接openweathermap
- form对手强度加权对整体准确率的影响需回测验证
- comprehensive.py中的赔率基线查询依赖lottery_odds表结构
