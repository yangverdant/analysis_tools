---
name: system_dashboard_status
description: "驾驶舱(系统驾驶舱)实现状态: 4标签页+12个API+默认首页"
metadata: 
  node_type: memory
  type: project
  originSessionId: 8bfd2936-b7d2-484e-b643-212fd61d5dce
---

## 驾驶舱实现状态 (2026-07-08)

### 已完成

**4个标签页全部实装** (`SystemDashboard.vue`, 650行):
1. **实时运转** — 系统健康(5卡片)、日循环节点流、定时任务、24h时间线、AI分析师早报
2. **模型表现** — 30天准确率曲线(MultiLineChart)、玩法目标vs实际(进度条)、模型版本/权重
3. **学习进度** — 参数变更记录、熔断事件、场景×玩法热力图、发现场景偏差(20个segments)、概率校准回测
4. **投注ROI** — ROI走势(7d/30d/cum, MultiLineChart)、ROI概况、止损状态、近期投注记录

**12个API全部可用** (backend port 8000, nginx proxy `/api/`):
- `automation-dashboard`, `automation-timeline`, `model-status`
- `accuracy-trend`, `scene-accuracy`, `learning-history`
- `roi`, `roi-trend`, `discovered-segments`
- `push-history`, `calibration-backtest`, `scheduler/status`

**默认首页**: `currentPage = '驾驶舱'` (2026-07-08 commit b7022e9), 用户打开系统第一眼看到运转状态

### 数据验证
- push_history: 3条记录(7/1, 7/7, 7/8), agent_report_text 有内容, agent_decision_json 有决策
- discovered-segments: 20个自动发现的场景偏差
- timeline: 100个最近24h事件
- 所有API在nginx proxy下正常工作

### 待改进
- 情报采集基本未运行(`match_intelligence_reports`只有1条), 驾驶舱"缺情报"数字会较高
- 准确率趋势图目前只有单线(整体), 可分玩法画多线
- 可加"系统告警"标签页集中展示WARNING级别消息
