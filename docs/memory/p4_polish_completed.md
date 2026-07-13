---
name: p4-polish-completed
description: "P4完善完成: 一键回测API+脚本+前端按钮+Docker前端nginx+一键启动脚本"
metadata: 
  node_type: memory
  type: project
  originSessionId: d2e763d6-7730-4e83-a6e7-3cc8d939df30
---

# P4 完善 — 已完成

## 一键回测
- `backend/app/core/backtest.py` — 核心回测逻辑
  - 从lottery_validation+lottery_odds计算虚拟投注收益
  - 赔率3级fallback: lottery_odds→report赔率基线反推→模型概率推导
  - 按场景(scene)和日期分组统计
  - 输出: ROI, 胜率, Brier, 盈亏, 逐场明细
- `GET /api/backtest?days=30&stake=100` — API端点
- `scripts/backtest.py` — 命令行入口, 支持--days/--stake/--json参数
- 前端AccuracyDashboard.vue新增"回测收益"按钮

## Docker + 一键启动
- `docker-compose.yml` 新增frontend服务(nginx:alpine)
- `nginx.conf` — 前端静态+API反向代理(/api/ → analyst:8000)
- `start.bat` / `start.sh` — Windows/Linux一键启动脚本
  - 自动检测Docker
  - 自动创建.env模板
  - docker-compose build + up

## 数据覆盖现状
- 3条验证记录(6/8), 156条赔率, 13条结果
- 赔率与结果的match_id无重叠(数据管道缺口)
- 回测赔率fallback到模型概率推导(8-12% margin)
