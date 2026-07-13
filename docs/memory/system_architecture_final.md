---
name: system-architecture-final
description: 足球分析师系统完整架构——从分析闭环推导的数据设计、同步管道、进化机制
metadata: 
  node_type: memory
  type: project
  originSessionId: d2e763d6-7730-4e83-a6e7-3cc8d939df30
---

# 足球分析师系统 — 完整架构

## 一、系统定位

不是"帮人分析一场比赛"，是**规模化+量化+可进化**的分析系统。

核心价值：
- 同时分析50场比赛
- 量化"友谊赛南美vs欧洲赔率1.3-1.5区间123场主胜41%"
- 每天复盘自动调整权重
- 场景知识越积累越准

## 二、分析闭环（一场比赛的完整流程）

### 赛前72小时
1. 赛事类型 → 决定分析策略
2. 双方实力 → Elo/FIFA/积分榜
3. 历史交手 → H2H（正赛权重1.0，友谊赛0.2-0.3）
4. 赔率基线 → 隐含概率
5. **相似场景历史统计** → 群体智慧（从matches场景标签聚合）

### 赛前24小时
6. 阵容完整性 → 伤病/停赛/轮换
7. 动机分析 → 争冠/保级/无欲无求（动机不对称：保级vs争冠≠保级vs中游）
8. 特殊情况 → 天气/裁判/国际比赛日/海拔
9. 赔率异动 → CLV信号，市场消化了什么信息

### 赛前1小时
10. 首发阵容确认 → 最终修正

### 综合判断
11. 最终概率 → 各因素加权（权重按赛事类型不同）
12. 价值投注 → 模型概率vs赔率隐含概率，有正edge才推荐
13. 置信度 → 数据充分+赔率模型一致=高，数据少+分歧=低

### 赛后
14. 复盘 → 预测vs实际
15. 归因 → bad_luck/close_match/correction_wrong/market_wrong/intel_missing
16. 学习 → actionable的调权重（±10%），非actionable的不调

## 三、相似场景（系统的群体智慧）

### 什么是相似比赛
- 赛事类型（友谊赛/联赛/世界杯...）
- 赔率区间（1.20-1.40 / 2.00-3.00 / 5.00+）
- 实力差距（Elo差>200 / 100-200 / <100）
- 赛程阶段（赛季初/中/末）
- 主客场（主队强/客队强/中立）
- 地区交手（同赛区/跨赛区）

### 进化逻辑
- 同场景首次 → 用默认策略
- 同场景10次 → 统计准确率，发现规律
- 同场景100次 → 规律稳定，写入场景知识库
- 同场景1000次 → 成为系统本能

## 四、三层知识体系

### 第一层：事实知识（数据）
比赛、赔率、赛果。oddsfe提供，每日同步。

### 第二层：场景规律（统计）
从事实知识统计出来的规律。例：友谊赛平局率62.5%，赔率1.3-1.5区间爆冷率X%。
系统自动统计，人只定义"什么场景值得统计"。

### 第三层：策略知识（权重）
每个场景下各因素权重。例：友谊赛赔率0.45+Elo0.15+场景0.20+情报0.15。
系统根据复盘自动调整，调整前必须回测验证。

## 五、数据源能力矩阵

| 数据源 | 能提供 | 不能提供 | 可靠性 |
|--------|--------|---------|--------|
| oddsfe | 赔率(13庄4市场)、赛果、赛程、tournament | 伤病、阵容、天气、身价 | 最高(主源) |
| apifootball | 赛程、比分、伤病、阵容、积分榜 | 赔率少、身价 | 中(API过期需替代) |
| sporttery | 体彩赔率(SPF/RQSPF/BF/BQC) | 其他 | **不可用**(WAF封禁2026-07-04起) |
| ESPN | 赛后阵容+联赛伤病 | 赔率 | 中高(免费API,见[[espn_free_api_integration]]) |
| FIFA官网 | FIFA排名 | 其他 | 最高 |
| Transfermarkt | 身价、阵容深度 | 赔率、赛果 | 高(待采集) |
| openweathermap | 天气 | 其他 | 高 |

**关键变化(2026-07-04起)**: sporttery WAF封禁后, oddsfe成为唯一主源, Pinnacle 1X2转SPF格式补lottery_odds.
oddsfe覆盖闭环7/13步。其余6步是补充性的。
**脆弱点**: oddsfe只提供event_id不提供team_id, 同步后需repair脚本补team_id(见[[automation_loop_p0_fixes]])

## 六、18张表设计

### 核心数据层（oddsfe同步）
- **matches** — 比赛记录，含场景标签（competition_type, stage, odds_range, region_matchup, season_phase）
- **match_odds** — 赔率，多庄家+多快照(opening/midday/closing)+多市场(1X2/OU/AH/BTTS)
- **teams** — 球队，team_id+英文名+中文名+国家
- **leagues** — 联赛，league_id+赛事类型分类+国家

### 衍生计算层（从matches计算，每日重算）
- **elo_ratings** — Elo评分
- **team_form** — 近期状态（含对手强度加权）
- **standings** — 积分榜
- **h2h_records** — 历史对战（分正赛/友谊赛标记）

### 临场情报层（其他数据源）
- **fifa_rankings** — FIFA排名
- **team_injuries** — 伤病/停赛
- **odds_movement** — 赔率异动记录

### 体彩系统层
- **lottery_matches** — 体彩比赛
- **lottery_odds** — 体彩赔率
- **lottery_results** — 开奖结果

### 进化闭环层（系统记忆）
- **lottery_analysis_reports** — 预测报告（含因子分解、场景标签、模型版本、is_stale标记）
- **lottery_validation** — 复盘记录（含归因attribution、赔率是否也错、is_correct）
- **prediction_error_diagnoses** — 错误诊断（error_categories + collection/model_actions）
- **model_params_history** — 权重调整历史（old→new→reason→sample_size）
- **push_history** — 推送历史（agent_report_text + stop_loss_json + channels_json）

## 七、同步管道

### oddsfe → football_v2.db 标准化规则
- status → 统一小写：finished/scheduled/live/cancelled/postponed
- time → 统一北京时间（从event_start_at UTC转换）
- 队名 → team_id映射（新队自动注册到teams表）**实际未实现**: oddsfe同步不自动注册team_id, 需跑repair脚本补(见[[automation_loop_p0_fixes]])
- tournament → league_id映射 + 赛事类型分类（新联赛自动注册）
- 赔率 → 规范化存储（多行而非378列摊开）

### 实时联动：4种同步情况

| 情况 | oddsfe | football_v2.db | 操作 |
|------|--------|---------------|------|
| 新比赛 | 新event_id | 不存在 | INSERT matches + match_odds(opening) |
| 赛果更新 | scheduled→finished | scheduled | UPDATE status+比分 + INSERT match_odds(closing) + 触发重算elo/form/standings/h2h/scenario_stats |
| 赔率变化 | 赔率值变了 | 有旧赔率 | INSERT match_odds(midday) + 检测异动 |
| 无变化 | 一样 | 一样 | 跳过 |

### 同步节奏
- 每日6:00 全量同步（新比赛+赛果+赔率）
- 每日14:00 赔率更新（只查当天scheduled比赛，变化>3%记录midday快照）
- 赛后 收盘价写入closing快照 + 计算CLV

### 赔率快照设计
```
match_odds
  match_id       TEXT
  bookmaker      TEXT       — PINNACLE/BET365/...
  snapshot_type  TEXT       — opening/midday/closing
  market         TEXT       — 1X2/over_under/asian_handicap/btts
  home           REAL       — 主胜(1X2)/主胜(亚盘)/大(大小球)
  draw           REAL       — 平局(1X2)/NULL
  away           REAL       — 客胜(1X2)/客胜(亚盘)/小(大小球)
  line           REAL       — 盘口(2.5/-0.5)
  captured_at    TIMESTAMP
  source         TEXT       — oddsfe/sporttery
```

### 赛果更新联动
```
UPDATE matches status=finished + 比分
  → 重算 elo_ratings（双方）
  → 重算 team_form（双方）
  → 重算 standings（该联赛）
  → 重算 h2h_records（双方）
  → 更新 scenario_stats（该场景）
```

## 八、进化机制

### 短期（每天）
复盘→归因→actionable的调权重(±10%)→回测验证→生效/不生效
非actionable的不调（运气差/赔率也错了/均势场）

### 中期（每周/月）
场景知识库更新→重新统计→发现新规律→新建场景标签→后续自动分类

### 长期（每季度）
全量回测→模型版本对比→场景级版本选择（友谊赛v3.9最好，联赛v4.1最好）

### 熔断机制
近7天模型argmax准确率 < 同期纯赔率argmax准确率 → 降级为odds_only模式
连续3天模型≥赔率 → 自动恢复

## 九、大闭环

```
感知(6:00) → 采集(7:00) → 情报(8:00) → 分类(8:30) → 分析(9:00) → 推送(9:30)
     ↑                                                                        ↓
     └── 学习(次日7:00) ← 归因(次日6:30) ← 复盘(次日6:00) ← 赛后同步 ←──────┘
```

## 十、世界杯特殊分析

- 赔率权重拉到最高（世界杯庄家投入最多）
- Elo/FIFA做实力基准，Form权重降到最低（友谊赛form无参考价值）
- H2H按赛事类型分级（正赛1.0，友谊赛0.2-0.3）
- 小组赛vs淘汰赛分开（淘汰赛防守优先平局多）
- 小组末轮出线形势影响动机（已出线可能轮换）
- 东道主单独加成
- 休息天数/赛程密度
- 俱乐部赛季状态（球员来源状态）
- 跨赛区交手少→风格不熟悉→冷门多

## 十一、脏数据归档

全量备份到唯一位置：`/opt/football_tools/data/_archive/football_v2_dirty_backup_20260611.db`
项目只能允许一个地方放脏数据。

## 十二、关键约束

- adapter层（field_map/normalizer/merger）设计完美但从未被调用 → 本次同步管道就是adapter的实际接入点
- oddsfe_merged.db在服务器路径：`/opt/football_tools/data/oddsfe_merged.db`
- football_v2.db在服务器路径：`/opt/football_tools/data/football_v2.db`
- 服务器：1.117.70.20, SSH key: /c/Users/Administrator/.ssh/football_server, user: root
