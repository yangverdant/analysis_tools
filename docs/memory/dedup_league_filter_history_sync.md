---
name: dedup-league-filter-history-sync
description: 重复场次根因修复+联赛白名单扩展+前端联赛筛选+历史比赛同步+球队CN映射补充
metadata: 
  node_type: memory
  type: project
  originSessionId: 8bfd2936-b7d2-484e-b643-212fd61d5dce
---

# 2026-07-12 系统性升级

## 重复场次根因修复
- 根因: sporttery INSERT OR REPLACE删除已有行(含oddsfe_event_id), oddsfe再INSERT新行→重复
- 3层dedup: ①oddsfe_event_id精确匹配 ②(home,away,date)匹配sporttery记录并桥接eid ③UNIQUE索引安全网
- sync_sporttery_matches.py: INSERT OR REPLACE→INSERT OR IGNORE+UPDATE(保留eid)
- oddsfe_schedule_to_lottery.py: 新增Layer2 (home,away,date)查找+eid桥接+_dedup_by_oddsfe_event_id清理函数
- UNIQUE INDEX idx_lottery_matches_oddsfe_eid ON (oddsfe_event_id) WHERE NOT NULL AND != ''

## 联赛白名单扩展
- oddsfe_schedule_to_lottery.py LEAGUE_WHITELIST: 31→80+联赛
- 新增: 澳超/墨超/智利甲/阿甲/哥伦甲/秘鲁甲/乌拉甲/巴拉甲/英联杯/足总杯/国王杯/德国杯/意大利杯/法国杯/荷乙/葡甲/苏冠/奥乙/瑞士甲/土甲/克甲/塞超/罗甲/匈甲/以超/亚冠/亚联杯/俱乐部友谊赛/足协杯/丹甲/沙特甲/伊朗超/泰超/泰甲/越南联/印尼甲/德丙/社区盾杯/法联杯/荷兰杯/比乙/苏联杯/欧超杯/美职联杯/墨甲/阿根廷杯
- lottery.py LOTTERY_CORE_LEAGUES: 同步扩展, /matches默认展示所有主流联赛

## 前端联赛筛选
- 新增 GET /api/v1/lottery/matches/leagues API (返回联赛名+比赛数)
- 新增 GET /api/v1/lottery/matches?league=xxx 参数
- LotteryCenter.vue: 新增league-select下拉框+fetchLeagues+onLeagueChange
- 默认include_all=true, limit=200

## 历史比赛同步
- oddsfe_schedule_to_lottery.py: 新增--history N参数回填过去N天已完成比赛
- 用法: python3 scripts/oddsfe_schedule_to_lottery.py --history 30
- 已完成比赛进入lottery_matches→validate→learn训练闭环

## 球队CN映射补充
- name_service.py: CRB→阿拉戈亚诺, Deportes Temuco→特木科体育, Magallanes→麦哲伦, PK-35→PK-35万塔
