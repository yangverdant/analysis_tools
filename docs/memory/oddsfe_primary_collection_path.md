---
name: oddsfe_primary_collection_path
description: "sporttery WAF后改用oddsfe作为主采集源. 3脚本接入tick: schedule_sync+eid_backfill+results_supplement, 白名单过滤主流联赛"
metadata: 
  node_type: memory
  type: project
  originSessionId: 8bfd2936-b7d2-484e-b643-212fd61d5dce
---

# oddsfe 作为主采集源 (2026-07-05)

## 背景
sporttery WAF封IP后(见 [[sporttery_waf_ban]]), 国内体彩官方API彻底不可用。
用户决策"那就别接sporttery了"+要"治标治本", 推动改用 oddsfe (Pinnacle全球API) 作为永久主采集源。

## 修复: 3个独立脚本接入 cloud_automation_tick.sh

### 1. scripts/oddsfe_schedule_to_lottery.py (主采集)
- 调用 `_oddsfe_fetch_schedule(date_str)` 拉未来3天赛事
- **LEAGUE_WHITELIST**: `(tournament_name, category_name)` 双键白名单, 只保留主流联赛
  - 5大联赛+欧冠/欧联/欧协联
  - 中超/中甲/中乙, 日职/韩职/韩乙/韩联杯, 瑞超/挪超/芬超
  - 美职/美乙, 巴甲/巴乙, 智利杯/厄甲
  - 世界杯/国际赛/欧洲杯/美洲杯/亚洲杯/非洲杯
- **关键**: 用 (tournament, category) 双键, 因为 "Premier League" 在斐济/哈萨克斯坦也是顶级联赛
- 联赛 CN 名统一(中超/韩职/瑞超), 不再用 oddsfe 原 tournament 名
- 队名 EN->CN 通过 teams 表 + team_aliases 三层匹配
- 测试: 318场过滤保留72场(22.6%)

### 2. scripts/oddsfe_eid_backfill.py (历史回填eid)
- 解决问题: sporttery 历史采集的 lottery_matches 没有 oddsfe_event_id, 导致 `_supplement_results_from_oddsfe` 跳过
- 学习映射: 从已有 (lm.home_team_cn, lm.oddsfe_event_id) 反查 oddsfe schedule, 建立 EN->CN 学习字典(80条)
- 3层匹配:
  - Layer 1: CN全等/前2CJK匹配(reverse_idx)
  - Layer 2: 学习映射覆盖
  - Layer 3: normalized fuzzy (lowercase, 去FC/SK/HD后缀, 首Token)
- **关键修复**: 当 home 唯一匹配但 away 因 teams 表无CN失配时, 信任 home 唯一性
- 测试: 7/4 K-League 3场全部回填上 eid

### 3. scripts/oddsfe_results_supplement.py (赛果补充)
- 调用 `LotterySyncService._supplement_results_from_oddsfe(date)` 给过去4天补结果
- 处理 FINISHED/AET/AP 状态, 解析 score_details 得 HT/FT
- 测试: 7/4 安养FC 2-3 浦项制铁, 全北现代 1-2 江原FC, 大田市民 2-2 富川FC 全部补上

## tick 调用顺序
```bash
oddsfe_schedule_to_lottery.py  # 1. 拉未来3天主流赛事
oddsfe_eid_backfill.py         # 2. 给历史缺eid的行补eid
oddsfe_results_supplement.py   # 3. 给已结束比赛补结果
cloud_tick_sporttery_sync.py   # 4. sporttery best-effort fallback (会403, 静默跳过)
run_automation_center.py       # 5. 主分析循环
```

## 数据清理
- 删除 290 条之前无过滤脚本插入的非主流联赛行
- 23组同eid重复行去重(保留CN名行, 删除EN名行)
- 7/5 数据状态: 43场42有eid, 8场已结束有结果

## How to apply
- 不要再用 sporttery 作为主源, IP被封无解
- oddsfe是稳定的Pinnacle全球API, 不受地理位置限制
- 白名单过滤必要, 否则会拉入大量Women/U20/友好赛/小国低级联赛
- (tournament, category) 双键比单tournament更可靠(同名联赛在不同国家语义不同)
- 队名映射靠 teams 表 + 历史学习, 不需要外部API
- **关键**: oddsfe只提供event_id不提供team_id, 同步后需跑repair_lottery_team_canonical_ids.py补team_id, 否则infer_action_counts会跳过这些赛事(见 [[automation_loop_p0_fixes]])
- 见 [[sporttery_waf_ban]] — sporttery封禁原因和迁移决策
- 见 [[future_match_collection_fix]] — 之前的sporttery修复(已被oddsfe路径替代)
- 见 [[oddsfe_collection_pipeline]] — oddsfe 3步采集流程详情
- 见 [[oddsfe_data_reality]] — oddsfe 数据真实状态
