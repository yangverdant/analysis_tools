---
name: injury-lineup-data-pipeline-fix
description: "修复伤停/阵容数据链路: player_status team_name桥接 + injury_delta/lineup_delta + bifen188降级"
metadata: 
  node_type: memory
  type: project
  originSessionId: 8bfd2936-b7d2-484e-b643-212fd61d5dce
---

## 问题

expected_lineup和injuries_suspensions全是fallback(126+3=0条真实数据)。
外部API全过期: apifootball=403(需付费), api_sports=403(未订阅), bifen188=空壳网站。
**已替代**: ESPN免费API已集成(见[[espn_free_api_integration]]), 提供赛后阵容+联赛伤病, 但赛前阵容仍是gap。
分析时injury/lineup因子等于零影响，是bqc=38.3%和ou=53.9%的重要原因。

## 修复

### 1. player_status team_name桥接

- `_resolve_team_id_for_player_status()`: 先直接匹配team_id, 不行则通过teams.name_cn匹配
- 79/90个队可通过中文名匹配到teams表
- 15个队有player_status数据(7 injured + 8 suspended + 9 doubtful)

### 2. intelligence overlay新增delta函数

- `_add_injury_delta()`: 伤停→概率偏移(缺席1人→-1.2pp胜率, 核心→额外-2pp)
- `_add_lineup_delta()`: 无阵容→draw boost(+1.5pp)
- 总delta上限: 7.5pp→10pp(6因子)

### 3. 数据源降级

- bifen188: enabled=False(网站空壳), probe返回disabled
- apifootball/api_sports: status=degraded(需付费)
- DB data_source_health已更新

## 当前限制

- player_status数据是历史测试数据(2002世界杯球员), 需要持续刷新
- 真正的伤停数据需要免费API或爬虫持续采集
- 下一步: zhibo8新闻→player_status自动提取
