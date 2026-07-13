---
name: duplicate-match-dedup-fix
description: 体彩中心重复场次去重 — sporttery/oddsfe同场生成不同lottery_match_id导致重复显示
metadata: 
  node_type: memory
  type: project
  originSessionId: 8bfd2936-b7d2-484e-b643-212fd61d5dce
---

**问题**: 瑞士 vs 哥伦比亚在同一天出现两次(ID 202607088993和202607072096)。

**根因**: sporttery用 businessDate(07-07)+matchNum(2096)生成ID=202607072096, oddsfe用match_date(07-08)+eid[-4:]生成ID=202607088993。当sporttery的businessDate与实际match_date不同时, DAO去重(home,away,date)失败(因为sporttery先用businessDate作为match_date插入,后被oddsfe桥接修正)。

**修复**: /matches API在返回结果时新增(home_team_cn, away_team_cn, match_date)去重, 优先保留有oddsfe_event_id的记录。从前端16场→15场。

**仍需**: 根治需修改sporttery同步在插入前就用实际match_date(而非businessDate)做去重检查。
