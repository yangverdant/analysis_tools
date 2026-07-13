---
name: sporttery_waf_ban
description: "sporttery WAF封了服务器IP 1.117.70.20, 需过腾讯TCaptcha验证码. 2026-07-04起未来比赛无法采集"
metadata: 
  node_type: memory
  type: project
  originSessionId: 8bfd2936-b7d2-484e-b643-212fd61d5dce
---

# sporttery WAF封禁服务器IP (2026-07-04起)

## 发现
- 2026-07-04开始, sporttery_daily_matches 持续返回 "No matches in response"
- 直接curl `webapi.sporttery.cn/gateway/jc/football/getMatchCalculatorV1.qry` HTTP 200但返回1697字节
- 响应内容是腾讯TCaptcha验证码页:
  ```html
  <script src="https://ssl.captcha.qq.com/TCaptcha.js"></script>
  var captcha = new TencentCaptcha('2017163193', ...)
  ```
- 服务器IP `1.117.70.20` 被WAF标记为机器人

## 影响
- **未来比赛无法采集** — 7/4-7/11 全空, 只有7/3的3场(已finished)
- 历史数据和已入库比赛不受影响
- oddsfe_merged.db 也不采未来(它是历史数据库, 最新到6/28)
- okooo fetcher也需要cookie, 已过期

## 已尝试(都失败)
- 加完整浏览器headers (UA, Sec-Fetch-*, Sec-Ch-Ua, Origin, Referer)
- 用session cookie
- 不同UA (Chrome, iPhone Safari)
- 不同endpoint路径 (jc/, jcvs/, jsbf/)

## 用户决策 (2026-07-05)
用户选择"申请解封/换云厂商":
- 联系腾讯云客服申请解封1.117.70.20
- 或换台国内云服务器(阿里云/华为云)

## 服务器迁移规格参考
- OS: Ubuntu 24.04.4 LTS
- 磁盘: 50G (用了28G, 数据库3.5G)
- 内存: 1.9G (用了626M)
- Swap: 8G
- 核心数据: /opt/football_tools/data/football_v2.db (3.5G)
- 代码: /opt/football_tools/ (git仓库)
- 服务: football-analyst.service + football-automation-tick.timer

## How to apply
- sporttery是国内体彩官方API, 无完美替代源
- 国内云服务器(腾讯云/阿里云)IP段可能被sporttery重点WAF
- 海外服务器访问国内API延迟高但可能不被WAF
- 见 [[future_match_collection_fix]] — tick脚本里集成的sporttery sync逻辑(代码已就位, IP解封后即可工作)
- 见 [[fetcher_scrape_sources]] — 国内备选源都需要cookie维护
