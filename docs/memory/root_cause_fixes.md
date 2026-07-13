---
name: root-cause-fixes
description: "Three root-cause fixes: concurrent O/U collection, Pinnacle O/U analysis, 7-factor weights"
metadata: 
  node_type: memory
  type: project
  originSessionId: d2e763d6-7730-4e83-a6e7-3cc8d939df30
---

## 采集管道修复
- **oddsfe_ou_concurrent.py**: 8线程并发采集O/U+1X2, 直写oddsfe_merged.db, 454场/88秒
- **collect.py集成**: Step 3b自动触发O/U采集+同步到football_v2.db+标记stale
- **oddsfe_matches表**: football_v2.db中的快速查找表, 430条Pinnacle O/U数据
- **健康检查**: _check_oddsfe_ou_health()检测数据新鲜度, >48h标记不健康
- **DB路径修正**: oddsfe_merged.db实际在fetchers/odds_feed_api/而非data/

## 分析管道修复
- **pinnacle_ou.py**: Pinnacle O/U查询工具, 优先级: oddsfe_matches→oddsfe_merged_db→None
- **analysis_service.py**: O/U优先级改为Pinnacle O/U→TTG→Poisson
- **core/analyze.py**: _get_pinnacle_ou_baseline()优先于_get_ttg_odds_baseline()
- **get_oddsfe_ou_line()**: 优先读展开列PINNACLE_line/over/under, 再解析lines字段
- **force-refresh修复**: POST /analyze/{id}?force=true 正确传递force_refresh到AnalysisService
- **is_stale缓存失效**: O/U数据更新后标记分析报告stale, 下次请求自动重新分析

## 自动优化修复
- **7因子权重**: ComprehensiveAnalyzer._get_weights()返回7个独立key, learn.py调整实际生效
- **_calculate_final_prediction()**: 兼容3键和7键, 7键时5个调整因子求和为adjusted_weight
- **O/U验证**: validate.py新增_validate_ou_for_report(), play_type='ou'写入lottery_validation
- **硬编码基线移除**: learn.py compute_odds_baseline()不再用per-scenario硬编码值
- **权重效果验证**: learn.py apply_weight_change后调用_verify_weight_effect()确认生效
