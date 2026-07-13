---
name: architecture_final
description: 最终架构设计—三层分离(调度+工作流+Agent)、6项修正、目录结构、实施优先级
metadata: 
  node_type: memory
  type: project
  originSessionId: d2e763d6-7730-4e83-a6e7-3cc8d939df30
---

## 最终架构 — 三层分离

### L1: 调度层 (systemd timers)
- 3个独立timer触发: tick(~15min), learning-refresh(每日02:53), daily-push(每日09:00)
- 不再用APScheduler(DISABLE_DAILY_SCHEDULER=1), 避免uvicorn worker卡死
- 单进程约束仍然在( SQLite不并发写), 通过flock保证

### L2: 工作流层 (自写轻量状态机 + SQLite)
- 不用LangGraph(依赖太重，9节点线性流程不需要)
- daily_cycle_state表持久化，断点可恢复
- 条件边: perceive→normal=collect, validate_yesterday=validate, circuit_break=collect(odds模式)

### L3: Agent决策层 (Anthropic/DeepSeek双后端)
- 5个决策点: 翻车归因/参数调整/异常诊断/策略选择/新场景
- **实际**: 讯飞MaaS Anthropic中转(astron-code-latest), DeepSeek过期作废
- 503频繁, 规则化兜底作fallback, 成本~¥1-2/天
- 见 [[agent_llm_api_status]]

## 6项关键修正(对比原始方案)

1. **冷启动必须有热启动**: 用oddsfe 8492场历史做离线回测算初始权重，不从默认值冷启动
2. **不用LangGraph**: 自写状态机+SQLite持久化，0外部依赖，200行代码
3. **不重写6层栈**: 渐进改造ComprehensiveAnalyzer为MatchProfile驱动，先跑通再拆层
4. **8:00重新定义**: 不只是伤病→"临场信息"(赔率异动+阵容+天气)，赔率异动才是核心
5. **赛事分类细分**: 6种→8种(+qualifier/nations_league/olympic)，international不够细
6. **熔断机制**: 模型准确率<赔率基线时降级为纯赔率推荐

## 目录结构修正

- core/放在backend/app/core/下(非独立目录)，避免import路径问题
- 新增data_access/层(拆DAO，统一数据访问)
- 新增config/agent_prompts/(Agent提示词模板)

## 实施优先级

- P0(4天): team_names修复 + sync_odds/results + DB schema + data_access ✅ 完成
- P1(5天): 状态机 + daily_runner + perceive + collect + validate ✅ 完成
- P2(5天): CompetitionRuleEngine + Analyzer改造 + classify/intel/analyze/push ✅ 完成
- P3(4天): Agent client + 提示词 + learn.py ✅ 完成
- P4(5天): 热启动回测 + 熔断 + CLV + 前端详情页 ✅ 完成

P0-P4全部完成(2026-07-07). 当前阶段: 闭环运转+持续调优+修复脆弱点.
2026-07-07修复3个P0断点: team_id缺失/learning exit 1/推送缺失(见[[automation_loop_p0_fixes]])
后续: team_id自动解析+分析覆盖监控+推送渠道激活+Agent兜底增强(见[[automation_loop_design_philosophy]])

## 部署

Docker单容器: FastAPI + APScheduler(同进程)
不引langchain生态
国内云需Claude API代理
