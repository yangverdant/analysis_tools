---
name: future_match_collection_fix
description: "未来比赛不采集根因: DISABLE_DAILY_SCHEDULER=1禁用内部调度器, 外部tick没跑sporttery. 修复: cloud_automation_tick.sh插入sporttery sync"
metadata: 
  node_type: memory
  type: project
  originSessionId: 8bfd2936-b7d2-484e-b643-212fd61d5dce
---

# 未来比赛不采集修复 (2026-07-03)

## 发现
- 用户反馈前端"未来几天比赛"不采集了
- lottery_matches 未来7天0场, 只有今天3场(都finished)
- sporttery_daily_matches 上次成功: 2026-07-01 02:46, 之后2天没跑

## 根因
1. **football-analyst.service 设了 `DISABLE_DAILY_SCHEDULER=1`**
   - 服务启动日志: "Daily scheduler disabled by DISABLE_DAILY_SCHEDULER"
   - 这是故意的: 避免uvicorn worker卡死, 改用外部systemd timer
   - **已更新**: sporttery WAF后, tick.sh改为oddsfe为主源(sporttery改为best-effort fallback)
   - **新脆弱点**: oddsfe同步后赛事无team_id, 需跑repair脚本补, 否则分析被静默跳过(见 [[automation_loop_p0_fixes]])
2. **外部 timer (football-automation-tick.service) 跑 cloud_automation_tick.sh**
   - 脚本只跑 `run_automation_center.py --mode mixed`
   - **没有 sporttery 采集调用**
3. main.py `_run_rolling_collection` 故意跳过sporttery:
   ```python
   summary["sporttery"] = {"skipped": True, "reason": "high-frequency loop keeps to lightweight..."}
   ```
   注释说"full sporttery sync remains in daily/manual flow" 但 daily flow 已被禁用

## 修复
### 1. cloud_automation_tick.sh 插入 sporttery sync
```bash
# Sporttery future-match sync — 90min dedupe via collection_runs
"$ROOT/venv/bin/python" "$ROOT/scripts/cloud_tick_sporttery_sync.py" 2>&1 | head -10 || true
```

### 2. 新增 scripts/cloud_tick_sporttery_sync.py
- 独立Python脚本(避免shell内联转义问题)
- 检查 collection_runs 里 90分钟内是否有 sporttery_daily_matches running, 有则skip
- 否则 sync 今天/明天/后天 3天

### 3. main.py _run_rolling_collection 防御性加入 sporttery
- 万一内部调度器开了, 也能跑sporttery
- 同样90分钟dedupe

## How to apply
- 改systemd service env后必须重启: `systemctl restart football-analyst.service`
- 内部调度器禁用时, 所有定时任务都必须挂到 cloud_automation_tick.sh
- 不要在shell脚本里内联复杂Python(转义问题), 用独立.py文件
- /tmp的lock file注意权限: tick service用User=ubuntu跑, root手动测试会破坏lock ownership
- 见 [[attribution_priority_fix]] — 同期修复的归因优先级问题
