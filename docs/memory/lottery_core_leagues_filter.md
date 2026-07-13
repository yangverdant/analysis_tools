---
name: lottery_core_leagues_filter
description: "体彩中心只展示31个核心在售联赛, 非核心(oddsfe采集的智杯/厄甲/瑞甲等)作后端养料不展示"
metadata: 
  node_type: memory
  type: project
  originSessionId: 8bfd2936-b7d2-484e-b643-212fd61d5dce
---

# 体彩中心核心联赛白名单 (2026-07-06)

## 背景
oddsfe 采集 73 个联赛(白名单见 oddsfe_schedule_to_lottery.py:LEAGUE_WHITELIST), 但体彩真正在售的只有约 31 个。智杯/厄甲/瑞甲/挪甲/芬甲/韩乙/中乙/美乙/巴乙等联赛体彩通常不开售, 但 oddsfe 有数据。

之前 /matches API 返回所有 lottery_matches 行, 体彩中心被这些非体彩比赛"淹没"。

## 修复
`backend/app/lottery/routers/lottery.py` 新增 `LOTTERY_CORE_LEAGUES` 常量(31 个联赛):
- 国际赛: 世界杯/欧洲杯/亚洲杯/非洲杯/美洲杯/国际赛
- 五大联赛: 英超/西甲/德甲/意甲/法甲
- 五大次级: 英冠/西乙/德乙/意乙/法乙
- 欧洲主流: 荷甲/比甲/葡超/苏超
- 欧洲杯赛: 欧冠/欧联/欧协联
- 美洲主流: 美职/巴甲/阿超
- 亚洲主流: 日职/韩职/沙特联
- 国内: 中超/中甲

`/matches` API 默认 `league_name_cn IN (...)` 过滤, 加 `?include_all=true` 查看全部。

## 关键设计
- **非核心不删除**: lottery_matches 表保留全部 oddsfe 采集数据, 后端 tick 的 analyze/validate/learn 任务继续覆盖, 作为模型训练养料
- **只过滤 API 展示层**: 前端体彩中心调 /matches 自动跟随, 无需改前端
- **白名单可演化**: 后续若体彩新增/移除联赛, 改 LOTTERY_CORE_LEAGUES 一处即可
- **历史数据保留**: sporttery 时期的老数据(无 oddsfe_event_id)若 league_name_cn 在白名单内仍展示

## 验证(2026-07-06)
- 7/6: DB 18 场 → API 4 场(全世界杯), 非核心 14 场保留, 其中 1 场已分析
- 7/7: DB 8 场 → API 5 场(全世界杯), 非核心 3 场保留

## How to apply
- 体彩中心展示 = LOTTERY_CORE_LEAGUES 过滤后的 lottery_matches
- 后端分析覆盖 = 全部 lottery_matches(含非核心), 不受过滤影响
- 想看全部: `/matches?include_all=true`
- 见 [[oddsfe_primary_collection_path]] — oddsfe 采集白名单更宽(73个联赛)
- 见 [[sporttery_waf_ban]] — 为什么不直接用 sporttery 的真实在售清单
