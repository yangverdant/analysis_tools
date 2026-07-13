# Football Analyst System - 运维交接手册

> 本文件是项目根目录的一站式入口，包含连接、部署、运维的全部关键信息。
> 详细文档见 `docs/云服务器部署文档.md` 和 `docs/项目运行同步与自动化手册.md`。

## 云服务器

| 项目 | 值 |
|------|-----|
| IP | `1.117.70.20` |
| OS | Ubuntu 24.04.4 LTS |
| 规格 | 2 CPU / 1.9 GB RAM / 50 GB 磁盘 |
| SSH Key | `~/.ssh/football_server` (Windows: `%USERPROFILE%\.ssh\football_server`) |
| 连接 | `ssh -i ~/.ssh/football_server ubuntu@1.117.70.20` |

**注意**: 服务以两个用户运行：
- `root`: football-analyst.service (API后端)
- `ubuntu`: 4个timer任务 (采集/分析/推送/学习)

## nginx + 认证

| 项目 | 值 |
|------|-----|
| 配置 | `/etc/nginx/sites-enabled/football-analyst` |
| 端口 | 80 (无HTTPS) |
| Basic Auth | 用户: `admin` / 密码: `qwer1234` |
| 前端 | `/opt/football_tools/frontend/dist` (静态文件) |
| API代理 | `/api/` → `http://127.0.0.1:8000` |
| 日志 | `/opt/football_tools/logs/nginx_access.log` |

## 数据库

| 数据库 | 路径 | 大小 |
|--------|------|------|
| 主DB | `/opt/football_tools/data/football_v2.db` | ~3.5 GB |
| oddsfe DB | `/opt/football_tools/fetchers/odds_feed_api/oddsfe_merged.db` | ~35 MB |

**手动备份**:
```bash
sqlite3 /opt/football_tools/data/football_v2.db ".backup '/opt/football_tools/backups/football_v2_$(date +%Y%m%d_%H%M%S).db'"
```

**拉到本地**:
```powershell
scp -i $HOME\.ssh\football_server ubuntu@1.117.70.20:/opt/football_tools/data/football_v2.db D:\football_tools\_server_backups\
```

## systemd 服务

| 服务 | 类型 | 用户 | 频率 | 作用 |
|------|------|------|------|------|
| `football-analyst.service` | 常驻 | root | 持续 | uvicorn API, port 8000, 2 workers |
| `football-automation-tick.timer` | 周期 | ubuntu | 每15分钟 | 采集→分析→验证 (oddsfe+sporttery) |
| `football-daily-morning.timer` | 周期 | ubuntu | 每天06:30 | 感知→学习 |
| `football-daily-push.timer` | 周期 | ubuntu | 每天09:00 | TOP3推送+Agent日报+止损 |
| `football-learning-refresh.timer` | 周期 | ubuntu | 每天02:45 | 归因→学习→重分析 |

**常用命令**:
```bash
systemctl status football-analyst --no-pager     # API状态
systemctl restart football-analyst                # 重启API
systemctl start football-automation-tick.service  # 手动触发一次tick
systemctl list-timers --all | grep football       # 查看所有timer
journalctl -u football-automation-tick -n 100     # 查看tick日志
```

**重要环境变量** (在service override中设置):
- `DB_PATH=/opt/football_tools/data/football_v2.db`
- `ODDSFE_DB_PATH=/opt/football_tools/fetchers/odds_feed_api/oddsfe_merged.db`
- `DISABLE_DAILY_SCHEDULER=1` (禁止API内部的APScheduler，用外部timer代替)
- `TZ=Asia/Shanghai`

## 部署代码

**推荐方式** — 使用同步脚本:
```powershell
.\deploy\sync_code_to_cloud.ps1              # 完整: 前端build + 上传 + 重启
.\deploy\sync_code_to_cloud.ps1 -SkipBuild   # 跳过前端build
.\deploy\sync_code_to_cloud.ps1 -NoRestart   # 只上传不重启
```

流程: `npm run build` → 打包tar.gz → scp到/tmp → 解压到/opt/football_tools → 运行`cloud_post_sync_maintenance.sh`(权限修复+DB迁移+重启)

**手动方式**:
```bash
# 1. 上传文件
scp -i ~/.ssh/football_server 文件名 ubuntu@1.117.70.20:/tmp/
# 2. 移动到目标位置
sudo cp /tmp/文件名 /opt/football_tools/backend/app/core/
# 3. 重启
sudo systemctl restart football-analyst
```

## API Keys 配置

位置: `/opt/football_tools/config/api_keys.yaml`

结构:
```yaml
anthropic:
  base_url: "https://maas-coding-api.cn-huabei-1.xf-yun.com/anthropic"
  api_key: "API_KEY_HERE"
  model: "astron-code-latest"

deepseek:  # 已过期, 仅作fallback
  base_url: "https://api.deepseek.com"
  api_key: ""
  model: "deepseek-chat"
```

当前使用讯飞MaaS中转Anthropic API。DeepSeek已过期。

## 日志

| 日志 | 路径 |
|------|------|
| tick日志 | `/opt/football_tools/logs/automation/cloud_automation_tick.log` |
| learning日志 | `/opt/football_tools/logs/automation/cloud_learning_refresh.log` |
| push日志 | `/opt/football_tools/logs/automation/cloud_daily_push.log` |
| morning日志 | `/opt/football_tools/logs/automation/cloud_daily_morning.log` |
| nginx日志 | `/opt/football_tools/logs/nginx_access.log` |
| API日志 | `journalctl -u football-analyst` |

## 日循环 (自动化流程)

```
02:45 学习 — 归因→参数学习→重分析 (football-learning-refresh.timer)
06:30 早间 — 感知→采集→分析 (football-daily-morning.timer)
09:00 推送 — TOP3价值投注+Agent日报+止损决策 (football-daily-push.timer)
每15min tick — oddsfe采集→分析→验证 (football-automation-tick.timer)
```

tick流程: oddsfe schedule sync → eid backfill → team_id repair → results supplement → SPF odds backfill → sporttery best-effort sync → automation_center(mixed, --no-learning) → 健康检查

**注意**: sporttery被WAF封禁(2026-07-04起)，当前主采集源为oddsfe。sporttery仅best-effort尝试。

## 健康检查

```bash
curl -s http://localhost:8000/api/v1/health           # API健康
curl -s -u admin:qwer1234 'http://localhost:8000/api/v1/lottery/automation-dashboard'  # 自动化面板
df -h /                                                 # 磁盘(当前87%, 需关注)
free -h                                                 # 内存
```

## 已知问题

1. **磁盘87%** — /opt/football_tools_backups/占3.6G可清理; DB占3.5G持续增长
2. **无自动备份** — 只有手动备份命令，无cron/timer
3. **无HTTPS** — nginx只监听80端口，无SSL证书
4. **sporttery WAF** — 体彩网站封禁IP，oddsfe为主采集源
5. **BQC/BF准确率低** — 20-30%，远低于赔率基线
6. **RQSPF投注亏损** — 让平低估+低赔率让胜投注EV为负，已加门控(2026-07-13)

## 项目结构 (关键文件)

```
d:\football_tools\
├── backend/app/core/
│   ├── analyze.py          # 6层分析栈 + 所有玩法计算(SPF/RQSPF/BQC/BF/O/U)
│   ├── push.py             # 推送+投注选择+止损+bet_records
│   ├── validate.py         # 验证+归因+结算
│   ├── learn.py            # 参数学习+场景准确率+归因驱动调整
│   ├── agent/client.py     # Agent决策(Anthropic/DeepSeek双后端)
│   └── name_service.py     # 球队名映射 EN↔CN + 赛事分类
├── scripts/
│   ├── oddsfe_schedule_to_lottery.py  # oddsfe采集主脚本(3层dedup+_find_team_id)
│   ├── cloud_automation_tick.sh       # tick入口
│   ├── cloud_daily_push.sh            # 推送入口
│   ├── cloud_daily_morning.sh         # 早间入口
│   └── cloud_learning_refresh.sh      # 学习入口
├── deploy/
│   ├── sync_code_to_cloud.ps1         # 一键部署脚本
│   ├── cloud_post_sync_maintenance.sh # 部署后维护(15步)
│   └── nginx-bare-metal.conf          # nginx配置参考
├── frontend/                          # Vue.js前端
├── config/agent_prompts/              # Agent prompt模板
└── docs/
    ├── 云服务器部署文档.md              # 完整部署文档(稍旧)
    └── 项目运行同步与自动化手册.md       # 运维手册(详细)
```

## 磁盘清理 (紧急时)

```bash
# 清理旧备份
sudo rm -rf /opt/football_tools_backups/runtime/football_v2_*.db
# 清理旧日志
sudo find /opt/football_tools/logs/ -name "*.log" -mtime +7 -delete
# 清理DB碎片
sqlite3 /opt/football_tools/data/football_v2.db "VACUUM;"
```
