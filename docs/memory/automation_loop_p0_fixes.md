---
name: automation_loop_p0_fixes
description: "自动化闭环3个P0断点修复: team_id缺失+learning exit 1+推送缺失, 修复后全链路恢复"
metadata: 
  node_type: memory
  type: project
  originSessionId: 8bfd2936-b7d2-484e-b643-212fd61d5dce
---

## 3个P0断点及修复 (2026-07-07)

### P0-1: lottery_matches.team_id 大面积NULL → 分析被跳过

**Why**: sporttery WAF永久封禁(2026-07-04)后, oddsfe接管主采集, 但oddsfe只提供event_id不提供team_id.
`infer_action_counts` 的SQL有 `WHERE home_team_id IS NOT NULL AND away_team_id IS NOT NULL`,
导致95%的赛事被过滤, "analyze"动作不生成, tick跑完但0场分析.

**Fix**: `repair_lottery_team_canonical_ids.py` 扩展(3次迭代, commit 1275e9b):
1. `candidate_rows` 加EN_LABEL_COLUMNS精确匹配(原只查CN列, "Ponte Preta"等EN名球队无法匹配)
2. `label_score` 加norm_en比较(处理accented/variant拼写)
3. `unambiguous_label_match` rescue: 空team_id时,只要1个精确标签匹配(score>=4)就接受
   (原要求候选数==1,但"智利"score=3前缀匹配不应阻止"智利大学"score=5)
4. `sample_advantage`保护: 当前team_id有精确标签匹配时,不允许高样本候选覆盖
   (历史误分配的样本不是正确性证据,如Avaí#1248有106场但全是错配)
5. `mismatch_override`: 当前team_id标签完全不匹配(score=0)时,无论样本数都覆盖
6. `context_mismatch`: 联赛上下文消歧,当当前team国家与联赛冲突时覆盖
   (如"兰格斯"在智利杯中,746=Scotland Rangers→136740=Chilean Rangers)
7. `LEAGUE_COUNTRY_HINTS`映射(40+联赛→国家), sort_key加country_bonus维度

**How to apply**: tick.sh已集成自动修复(2026-07-07 commit a630ffe). 修复脚本现在能:
- 处理EN标签匹配(oddsfe提供的英文名)
- 联赛上下文消歧(同名不同国家球队)
- 保护正确team_id不被历史误配的高样本数覆盖
唯一限制: U20等青年队无法链接到成年队ID(正确行为).

### P0-2: football_data_wc_sync 空API响应 → learning-refresh exit 1

**Why**: football_data_org对2026 WC赛季返回0场(赛季未上线), 但本地有2行lottery_rows.
原逻辑标记 `success=False`, 导致learning-refresh整个pipeline exit 1, 连续2天(7/6-7/7)学习不跑.
所有后续学习步骤(归因/相似案例/重分析)全部跳过.

**Fix**: 空响应降级为warning: `success=True` + `source_health="empty_api_response"` + warning文本.
WC数据是补充非关键, oddsfe是主源. 学习管道继续执行.

**How to apply**: 当football_data_org API上线2026 WC赛季后, 此warning会自动消失.
如果其他补充源也有类似"API未就绪"场景, 同理降级为warning不要fail整个pipeline.

### P0-3: push_channels.py语法错误 + 无推送timer

**Why1**: `push_channels.py:163` 的 `f'{\" | \".join(alt_strs)}'` 是Python语法错误,
f-string内不能有反斜杠转义. 每次format_daily_push都崩溃, push节点failed.

**Why2**: push.py的push()节点无调度器触发. 7/1后再无push_history记录.
日循环的push步骤只在morning/full模式下触发, 但tick.sh用mixed模式跑automation_center,
不走daily_runner, 所以push从未被调用.

**Fix1**: 改为先算 `sep = ' | '` 再f-string插值 `f'{sep.join(alt_strs)}'`.
**Fix2**: 新增 `cloud_daily_push.sh` + `football-daily-push.timer`(09:00 Asia/Shanghai) +
`football-daily-push.service`, 调用 `daily_runner --mode push`.

**How to apply**: timer已enable. 如果push时间需调整, 改timer的OnCalendar.
如果推送渠道(Server酱/邮件)要启用, 配置环境变量即可.

### P0-4(附带): automation_center日期窗口太窄

**Why**: mixed模式 `(-1, 0, 1, 2)` 只覆盖today-1到today+2, today+3的赛事永远不在tick范围.
7/10的26场0分析.

**Fix**: 扩展到 `(-1, 0, 1, 2, 3)` 覆盖today+3.

### 验证结果

| 日期 | 修复前分析 | 修复后分析 |
|------|-----------|-----------|
| 7/6  | 2/15      | 15/15     |
| 7/7  | 4/11      | 10/11     |
| 7/8  | 2/19      | 19/19     |
| 7/9  | 0/10      | 10/10     |
| 7/10 | 0/26      | 26/26     |

learning-refresh: exit 1 → exit 0, 165条新错误诊断.
push: 0记录 → 7/7记录(24场+261字Agent早报).
