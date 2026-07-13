---
name: name-service-unification
description: NameService统一队名映射+时区统一+赛事分类+预测回退修复
metadata:
  type: project
  originSessionId: 8bfd2936-b7d2-484e-b643-212fd61d5dce
---

**问题**: 用户反复要求的3个系统性问题: 队名英文(27/28场)、时区硬编码+8h(11处)、赛事分类3套系统不一致

**修复**:

1. **NameService** (`backend/app/core/name_service.py`): 统一队名映射
   - 合并6处散落的_norm_team/_norm_name函数为NameService.normalize()
   - 合并8处CN↔EN映射字典为_EN_CN_DIRECT(77个小联赛)+_CN_EN_EXTRA(150+常用)
   - /matches API集成: 英文名自动翻译为中文名
   - 7月10日: 英文27/28 → 0/28
   - 自动学习: learn()持久化到JSON+DB, sync_lottery_matches()批量翻译
   - DB加载不覆盖已有映射(JSON/硬编码优先), 防止teams.name_cn坏数据覆盖

2. **时区统一**: 11处硬编码+8h替换为time_utils.py
   - worldcup/service.py, football_data_wc_sync.py, daily_runner.py: BEIJING_TZ统一导入
   - sync_service.py: 5处timedelta(hours=8)→utc_to_beijing/beijing_to_utc
   - validate.py: utc_dt + _td(hours=8)→utc_to_beijing
   - oddsfe_event_sync.py: _beijing_time_from_event→utc_to_beijing
   - oddsfe_ou_line_sync.py: dt - timedelta(hours=8)→beijing_to_utc
   - matches.py: utcnow() + timedelta(hours=8)→now_beijing()
   - **关键bug修复**: lottery.py line 1383 beijing_time与UTC datetime('now','-6h')比较→用now_beijing()

3. **赛事分类**: _analysis_scenario_type委托CompetitionRuleEngine
   - 优先从match_profile读取participant_type(national/club)
   - national→friendly_intl/qualifier/nations_league/international_cup
   - club→league/domestic_cup/continental_cup(欧战特殊处理)
   - 关键词匹配仅作fallback

4. **预测回退**: /matches API增加lottery_predictions表fallback
   - report_row为None时从lottery_predictions读取
   - analyzed_ids也包含lottery_predictions的match_id

5. **_save_report**: logger.debug→logger.error, 防止报告保存失败静默

6. **is_stale一致性**: analyzed_ids查询增加COALESCE(is_stale,0)=0过滤

**结果**: 前端队名100%中文、时区计算正确、赛事分类统一入口
