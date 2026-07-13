---
name: server_access
description: 云服务器SSH连接+服务列表+关键路径+运维命令
metadata: 
  node_type: memory
  type: reference
  originSessionId: 8bfd2936-b7d2-484e-b643-212fd61d5dce
---

## SSH连接

- IP: 1.117.70.20
- 用户: root (操作服务); ubuntu (运行user)
- SSH Key: ~/.ssh/football_server
- 连接: `ssh -i ~/.ssh/football_server root@1.117.70.20`

## 项目路径

| 路径 | 用途 |
|------|------|
| /opt/football_tools | 项目根目录 |
| /opt/football_tools/data/football_v2.db | 主数据库(3.6GB) |
| /opt/football_tools/fetchers/odds_feed_api/oddsfe_merged.db | oddsfe赔率库 |
| /opt/football_tools/venv | Python虚拟环境 |
| /opt/football_tools/logs/automation/ | 自动化日志目录 |
| /opt/football_tools_backups/runtime/ | 运行时备份 |
| /opt/football_backups/team_id_repairs/ | team_id修复前备份 |

## systemd服务

| 服务 | 频率 | 入口 | 状态 |
|------|------|------|------|
| football-analyst.service | 常驻 | FastAPI (port 8000) | running |
| football-automation-tick.timer | ~15min | cloud_automation_tick.sh | active |
| football-learning-refresh.timer | 每日02:53 | cloud_learning_refresh.sh | active |
| football-daily-push.timer | 每日09:00 | cloud_daily_push.sh | active |

## 常用运维命令

```bash
# 服务状态
systemctl status football-analyst --no-pager
systemctl status football-automation-tick.timer --no-pager
systemctl status football-learning-refresh.service --no-pager
systemctl status football-daily-push.timer --no-pager

# 手动触发
systemctl start football-daily-push.service  # 手动触发推送
FOOTBALL_AUTOMATION_MAX_ANALYSIS=20 bash /opt/football_tools/scripts/cloud_automation_tick.sh  # 手动tick

# 日志
journalctl -u football-automation-tick -n 50 --no-pager
tail -100 /opt/football_tools/logs/automation/cloud_automation_tick.log
tail -50 /opt/football_tools/logs/automation/cloud_learning_refresh.log
tail -30 /opt/football_tools/logs/automation/cloud_daily_push.log

# DB查询
sqlite3 /opt/football_tools/data/football_v2.db "SELECT ..."

# team_id修复
python3 /opt/football_tools/scripts/repair_lottery_team_canonical_ids.py --date-from 2026-07-06 --date-to 2026-07-10 --all-leagues --apply
```

## 部署流程

代码修改后: `scp` 上传 → `systemctl restart football-analyst` (API层) → 其他timer下次触发时自动用新代码

## 关联

- [[automation_loop_design_philosophy]] — 3个timer的设计职责
- [[automation_loop_p0_fixes]] — 3个P0断点修复
