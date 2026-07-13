---
name: windowb-analyze-intel-odds
description: 窗口B完成—analyze MatchProfile驱动+赔率基线对比+intel赔率异动/伤停/轮换/国际比赛日
metadata: 
  node_type: memory
  type: project
  originSessionId: d00bd7d5-0cc9-43df-9324-85bed165b15c
---

## 窗口B完成状态

### 已改文件

| 文件 | 改动 |
|------|------|
| `backend/app/core/analyze.py` | **重写**: MatchProfile驱动路由+赔率基线+model_vs_odds+weights_used |
| `backend/app/core/intel.py` | **重写**: 赔率异动(opening vs latest)+伤停+轮换风险+国际比赛日+天气占位 |

### analyze.py关键改动

1. `_get_pending` JOIN teams获取team_type
2. `_load_match_profile`: 从lottery_analysis_reports加载classification报告
3. `_build_profile_on_the_fly`: 无分类报告时实时生成
4. `_dict_to_profile`: dict→MatchProfile反序列化(支持roundtrip)
5. `_get_match_odds_baseline`: 从lottery_odds读Pinnacle赔率→隐含概率
6. `_compute_model_vs_odds`: 模型推荐 vs 赔率推荐 + edge差值
7. `_get_weights_used`: 8种赛事类型对应权重表

### intel.py关键改动

1. `_detect_odds_movement`: opening vs latest赔率>3%异动(含fallback)
2. `_fetch_injuries`: 从player_sidelined表查(短期可能空)
3. `_estimate_rotation_risks`: 友谊赛0.4-0.65、杯赛0.3、国际比赛日0.3
4. `_check_international_break`: 2026年FIFA窗口检测
5. 保存intel报告到lottery_analysis_reports(report_type='intel')

### 验证结果
- 所有模块import通过 ✅
- engine分类→weights→analyze链路完整 ✅
- _dict_to_profile roundtrip正确 ✅
- WC_QUALIFIER优先于TOURNAMENT_INTL关键词匹配修复 ✅ ("世界杯预选赛"→wc_qualifier, 非tournament_intl)

### 待后续
- intel天气需接openweathermap
- 伤停数据依赖apifootball injuries端点(当前DB可能无数据)
- _detect_odds_movement依赖lottery_odds有opening+latest两种snapshot_type