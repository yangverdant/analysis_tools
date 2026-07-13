---
name: attribution-timeout-and-cycle-fix
description: 归因卡住根因修复+日循环7/10完成+DB清理+market_anchor阈值+score_details修正+SQL注入防护
metadata: 
  node_type: memory
  type: project
  originSessionId: 8bfd2936-b7d2-484e-b643-212fd61d5dce
---

# 2026-07-10 系统性修复

## 归因卡住根因
- _attribute_failures对734条空归因逐条调Agent, 每条5-10s, tool_use循环max_iterations=10可跑3min/条
- 修复: 回填LIMIT 500→50, 新增attribution_deadline=600s(10分钟总时限), 超时自动降级为纯规则引擎
- FOOTBALL_SKIP_AGENT_ATTRIBUTION=1环境变量可完全跳过Agent归因

## 日循环7/10完成
- 之前卡在7/8 clv_update, 原因: DB满(88%)+日循环无morning/full触发
- 手动运行morning→push→clv→validate→learn完成全链路
- validate: 60场验证50%准确率, 221场规则引擎归因
- learn: 6项调整+9项熔断+15个segment发现

## DB清理
- source_artifacts(7天前1GB) + collection_runs(14天前300MB) + 临时表(128MB)
- VACUUM: 4.0GB→2.9GB, 磁盘88%→86%
- oddsfe DB ownership: root→ubuntu

## market_anchor阈值
- MAX_MODEL_PROB: 0.52→0.60 (模型55%时不再被52%阈值挡住)
- MAX_MODEL_GAP: 0.12→0.20 (允许更大gap触发market_anchor)

## score_details格式修正
- oddsfe格式: "上半场,下半场"各自进球数(非累积)
- 2段=上半+下半, 3段=上半+下半+点球, 4段=上半+下半+加时+点球
- _parse_fulltime_from_score_details: 全场=上半+下半求和(仅取前2段)
- _parse_score_details docstring已修正

## _read_db SQL注入防护
- 拦截UNION/ATTACH/分号

## 验证准确率(截至7/10)
- SPF 53.8%, OU 50.0%, RQSPF 48.5%, BQC 31.9%, BF 27.4%
- 734条空归因全是is_correct=1(正确预测), 无需归因
