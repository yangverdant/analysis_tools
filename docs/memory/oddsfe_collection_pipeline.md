---
name: oddsfe-collection-pipeline
description: oddsfe_merged.db采集流程记录：3个脚本、爬取方法、认证方式、数据文件、RED LINE规则
metadata: 
  node_type: memory
  type: reference
  originSessionId: a3325eab-87ac-48a6-8496-2ff45be69cae
---

# oddsfe_merged.db 采集流程

## 数据源
- 网址: oddsfe.com
- 方法: **直接爬取oddsfe.com内部API和HTML页面**，不走RapidAPI
- 日期范围: 2024-08-16 ~ 2026-06-14 (持续更新)
- 总量: 249,797场比赛, 378列

## 三步采集流程

### 第一步: schedule数据 → oddsfe_realtime_schedule.py
- API: `https://oddsfe.com/bind/schedule/football/{YYYY-MM-DD}`
- 返回JSON: 每天所有赛事基础信息+比分+Pinnacle摘要赔率
- 认证: [[oddsfe-collection-pipeline]] auth.py自动获取 (见下)
- 输出: `oddsfe_realtime_schedule.csv`
- 频率: 每天1次, 采集过去3天+未来10天

### 第二步: 详情赔率 → oddsfe_realtime_detail_v2.py
- 页面: `https://oddsfe.com/events/{event_id}?mt={市场类型}&live={0或1}`
- 方法: BeautifulSoup解析HTML
- 每个event_id访问8次 (4市场×2时态):
  - 1X2 / OVER_UNDER / ASIAN_HANDICAP / BOTH_TEAMS_TO_SCORE
  - prematch / live
- 还从 `/bind/event/{event_id}` 获取半场比分/加时/点球
- 支持6个worker并行 (`--worker`参数)
- 输出: `oddsfe_detail_v2_all.csv` (1.99GB)

### 第三步: 合并入库 → oddsfe_clean_merge.py
- 输入: schedule CSV + detail CSV
- 方法: 按event_id合并, 展开赔率字符串为378列独立字段
- **RED LINE规则**: 历史数据(>10天)绝不修改, 只更新最近10天
- 新event_id→追加, 已存在且10天内→更新, 已存在且超过10天→跳过
- 15个bookmaker展开: 1XBET, BET365, PINNACLE, BETFAIR_EXCH, BETFAIR, BET_IN_ASIA, UNIBET, BET_AT_HOME, WILLIAM_HILL, DAFABET, BWIN_ES, BWIN, 888_SPORT, STAKE_COM, MATCHBOOK
- 输出: `oddsfe_data_full_v2.csv` → 导入 oddsfe_merged.db

## 首次全量采集 → oddsfe_collector.py
- 命令: `python oddsfe_collector.py --start 2024-08-16 --end 2026-06-09`
- 按日期遍历, 每天获取schedule再逐event抓详情
- 反爬: 随机UA, 随机延迟 (schedule 3-6s, event 4-8s, 天间 5-10s)

## 认证方式 → oddsfe_auth.py
- **不是RapidAPI Key**, 是从oddsfe.com页面自动提取的
- 步骤: 访问oddsfe.com → 找active.js → 下载JS → 正则提取32位hex key+bearer token
- 自动刷新间隔: 1小时
- 失败fallback: 硬编码的缓存值
- get_schedule_auth(): 返回schedule API的认证header dict
- get_event_auth(): 返回event详情页的认证header dict

## config.py里的备用接口 (实际全量采集未使用)
- RapidAPI Key: 36ce000ce1msh... (新账号2026-05)
- HugeAPI Key: 1bef4599c8a1... (独立配额)
- 这些是Portal API备选方案, 实际爬取直接走oddsfe.com

## 数据文件清单
| 文件 | 大小 | 用途 |
|------|------|------|
| oddsfe_merged.db | 2.38 GB | 最终SQLite数据库 |
| oddsfe_data_full_v2.csv | 2.15 GB | 全量v2格式CSV |
| oddsfe_detail_v2_all.csv | 1.99 GB | 详情赔率原始CSV |
| oddsfe_detail_v2_all_backup.csv | 1.98 GB | 备份 |
| oddsfe_merged_full.csv | 2.15 GB | DB导出CSV |

## 关键发现: prematch字段=收盘价
- 实测478场英超: 95.4%的oddsfe Pinnacle prematch更接近CSV收盘价(PSCH)
- oddsfe "close"字段全是1.00 (无意义)
- **oddsfe里没有真正的开盘价**, prematch≈临场收盘价
- 做CLV分析需用CSV的PSH(开盘) + oddsfe的prematch(收盘)
