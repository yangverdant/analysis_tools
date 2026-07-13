---
name: espn_free_api_integration
description: "ESPN免费API集成: 赛后阵容+联赛伤病+18联赛映射, 已集成到external_collectors"
metadata: 
  node_type: memory
  type: project
  originSessionId: 8bfd2936-b7d2-484e-b643-212fd61d5dce
---

ESPN免费API集成 (2026-06-30)

**What:**
- `fetchers/espn/get_lineups.py`: 新模块, 免费无需认证
  - `get_match_lineup(event_id, league)`: 已完赛比赛完整阵容(11首发+替补+阵型)
  - `get_league_scoreboard(league)`: 联赛赛程+比分
  - `get_league_injuries(league)`: 联赛伤病(赛季期间有效)
  - `get_team_injuries(league, team_id)`: 球队伤病
  - `resolve_league_code(league_cn)`: 18联赛中文→ESPN代码映射

**采集链路优先级:**
1. match_lineups (本地DB) → 置信度0.85
2. apifootball (付费,已过期) → 置信度0.72
3. **ESPN match summary (免费)** → 置信度0.82 (新增)
4. legacy prematch crawler → 置信度0.58
5. football-data.org squad → 置信度0.52
6. recent lineup projection → 置信度0.48

**Why:** api_sports/apifootball key全部过期(403), bifen188网站空壳, 所有免费API(SportDB/The Odds API)不含阵容数据, 所有爬虫源(FBref/Transfermarkt/Sofascore/WhoScored)返回403/405

**Limitations:**
- ESPN只提供**已完赛**阵容, 不提供赛前预测阵容
- ESPN伤病在休赛期返回空列表
- football-data.org免费tier: 有squad但无lineup/injury, 需`?season=2025`参数

**football-data.org修复:**
- `get_team_detail()`无season返回0球员时自动重试`season=当前年`
- 7秒间隔避免10次/分钟速率限制

**数据源搜索结果 (2026-06-30):**
| Source | Lineup | Injury | Cost | Status |
|--------|--------|--------|------|--------|
| ESPN summary API | 已完赛✓ | 赛季内✓ | 免费 | **已集成** |
| football-data.org | squad✓ lineup✗ | ✗ | 免费 | 已有 |
| SportDB | ✗ | ✗ | 免费 | 无用 |
| FBref/Transfermarkt | ✗ | ✗ | 免费 | 403 |
| SofaScore | ✗ | ✗ | 免费 | 403 |
| api_sports | ✗ | ✗ | 付费 | 403过期 |
| apifootball | ✗ | ✗ | 付费 | 403过期 |
