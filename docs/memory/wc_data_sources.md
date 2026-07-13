---
name: wc_data_sources
description: WC 2018/2022完整数据来源和文件路径：xG、真实赔率、阵容、阵型、统计
metadata: 
  node_type: memory
  type: project
  originSessionId: d2e763d6-7730-4e83-a6e7-3cc8d939df30
---

## WC 2018 数据文件 (64/64 场全)

| 数据 | 文件 | 来源 | 说明 |
|------|------|------|------|
| xG+比分 | `data/world_cup/wc_2018_xg.json` | StatsBomb open-data (comp=43, season=3) | 64场, key=date\|home\|away |
| 真实赔率 | `data/world_cup/wc_2018_odds.json` | Flashscore爬取 | 64/64, 1X2收盘赔率, ~3%利润率 |
| 阵容+阵型+统计 | `data/world_cup/wc_2018_statsbomb_stats.json` | StatsBomb事件聚合 | 64/64, Starting XI事件提取lineup/formation, 逐事件聚合shots/pass/foul等 |
| af_matches(不完整) | `data/world_cup/wc_2018_af_matches.json` | apifootball | 61场含预选赛, 无lineup无stats, 免费版不支持 |

**Why**: apifootball免费版不含WC 2018历史阵容/统计，改用StatsBomb事件数据提取。赔率用Playwright爬Flashscore比赛详情页的1X2收盘赔率。

**How to apply**: 分析WC 2018时用`wc_2018_statsbomb_stats.json`获取阵容/统计，用`wc_2018_odds.json`获取赔率，用`wc_2018_xg.json`获取xG。不要用af_matches。

## WC 2022 数据文件 (64/64 场全)

| 数据 | 文件 | 来源 | 说明 |
|------|------|------|------|
| xG+比分 | `data/world_cup/wc_2022_xg.json` | StatsBomb open-data (comp=43, season=106) | 64场 |
| 真实赔率 | `data/world_cup/wc_2022_odds.json` | Flashscore爬取 | 64/64, 1X2收盘赔率 |
| 阵容+阵型 | `data/world_cup/wc_2022_statsbomb_lineups.json` | StatsBomb事件 | 64/64, Starting XI |
| 比赛统计 | `data/world_cup/wc_2022_af_matches.json` | apifootball | 64/64有stats, 无lineup |

**How to apply**: WC 2022的统计用af_matches, 阵容用statsbomb_lineups, 其余同2018。

## 数据提取脚本

| 脚本 | 功能 |
|------|------|
| `fetchers/scripts/extract_wc_xg.py` | 从StatsBomb提取xG (2018+2022) |
| `fetchers/scripts/extract_wc_2018_stats.py` | 从StatsBomb提取2018阵容+阵型+统计 |
| `fetchers/scripts/scrape_wc_odds_flashscore.py` | Playwright爬Flashscore赔率 |
| `fetchers/scripts/build_wc_odds_final.py` | 清洗赔率数据, 匹配到64场正赛 |

## 关键约束

- 赔率必须是真实市场赔率，不能用Poisson推导（用户明确拒绝: "赔率怎么可能拿推理的"）
- 旧Poisson推导赔率已备份到 `wc_{year}_odds_poisson_backup.json`
- StatsBomb open-data路径: `data/open-data-master/data/events/{match_id}.json`
- Flashscore爬取: 匹配页body text中 "1X2" 后的3个赔率值

## WC 2026

尚未开赛 (2026-06-11 ~ 2026-07-19), 数据需赛后采集。
