---
name: intelligence_gap_pipeline_fix
description: "情报采集管道断点修复: fill_gaps前先调generate_jobs确保intelligence_jobs存在"
metadata: 
  node_type: memory
  type: project
  originSessionId: 8bfd2936-b7d2-484e-b643-212fd61d5dce
---

## 情报采集管道断点修复 (2026-07-08, commit f6ddabf)

### 问题: 7/4 WAF封禁后情报任务不再生成

auto_gap_runner检测到`collect_intelligence`缺口→automation_center创建intelligence任务→
run_automation_task调用`fill_gaps_logged()`→但`fill_gaps`只查询**已存在的**intelligence_jobs。

**关键断点**: `generate_jobs_for_date()`是唯一INSERT到intelligence_jobs的方法,
但它只通过HTTP API(`/intelligence/generate`)和`run_daily`可达, 不在自动化管道中。
自动化管道假设intelligence_jobs行已存在, 但没有步骤创建它们。

7/4 WAF封禁后旧的sporttery驱动流程中断, 新的oddsfe流程没有调用generate_jobs。

### Fix: `fill_gaps_logged`开头调`generate_jobs_for_date_range`

新增方法`generate_jobs_for_date_range(start, end)`, 遍历日期范围调`generate_jobs_for_date`。
`fill_gaps_logged`在调`fill_gaps`前先调用它, 确保目标日期范围内有intelligence_jobs行。

效果: 7/8数据完整度从20/20缺情报 → 6/20缺情报(14场已有情报), 剩余6场后续tick自动填充。

### Why: 自动化闭环完整性

之前"缺情报19"是前端可见的最大缺口, 根因是自动化管道只消费不生产intelligence_jobs。
修复后, 每次tick跑intelligence任务时都会先确保目标日期有jobs行, 再fill gaps。

### How to apply

无需额外操作, tick自动调用`fill_gaps_logged`, 其中已集成generate_jobs。
如果需要手动触发生成: `IntelligenceService(db).generate_jobs_for_date_range(start, end)`.

### 依赖

- [[automation_loop_p0_fixes]] — team_id修复后分析全覆盖, 但情报是独立层
- [[automation_loop_design_philosophy]] — tick的intelligence步骤在wave 1执行
