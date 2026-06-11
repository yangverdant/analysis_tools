# API Football V3 文档

## 基本信息

- **API基础URL**: `https://apiv3.apifootball.com/`
- **认证方式**: Query参数 `APIkey`
- **版本**: 3.0.2
- **更新日期**: 2023-07-22

## 通用参数

| 参数 | 描述 |
|------|------|
| action | API方法名称 |
| APIkey | 授权码（从apifootball账户生成） |

## API端点

### 1. 获取国家列表 (get_countries)

返回当前订阅计划支持的国家列表。

**请求URL**:
```
https://apiv3.apifootball.com/?action=get_countries&APIkey=YOUR_KEY
```

**响应示例**:
```json
[
    {
        "country_id": "44",
        "country_name": "England",
        "country_logo": "https://apiv3.apifootball.com/badges/logo_country/44_england.png"
    },
    {
        "country_id": "6",
        "country_name": "Spain",
        "country_logo": "https://apiv3.apifootball.com/badges/logo_country/6_spain.png"
    }
]
```

---

### 2. 获取联赛列表 (get_leagues)

返回当前订阅计划支持的联赛列表。

**参数**:
| 参数 | 描述 | 必填 |
|------|------|------|
| country_id | 国家ID，设置后只返回该国家的联赛 | 否 |

**请求URL**:
```
https://apiv3.apifootball.com/?action=get_leagues&country_id=6&APIkey=YOUR_KEY
```

**响应示例**:
```json
[
    {
        "country_id": "6",
        "country_name": "Spain",
        "league_id": "302",
        "league_name": "La Liga",
        "league_season": "2020/2021",
        "league_logo": "https://apiv3.apifootball.com/badges/logo_leagues/302_la-liga.png",
        "country_logo": "https://apiv3.apifootball.com/badges/logo_country/6_spain.png"
    }
]
```

---

### 3. 获取球队信息 (get_teams)

返回可用的球队列表。

**参数**:
| 参数 | 描述 | 必填 |
|------|------|------|
| team_id | 球队ID | 如果未设置league_id则必填 |
| league_id | 联赛ID | 如果未设置team_id则必填 |

**请求URL**:
```
https://apiv3.apifootball.com/?action=get_teams&league_id=302&APIkey=YOUR_KEY
```

**响应包含**:
- 球队基本信息（名称、国家、成立年份、队徽）
- 球场信息（名称、地址、容量、场地类型）
- 球员列表（含详细统计）
- 教练信息

---

### 4. 获取球员信息 (get_players)

返回可用的球员信息。

**参数**:
| 参数 | 描述 | 必填 |
|------|------|------|
| player_id | 球员ID | 如果未设置player_name则必填 |
| player_name | 球员名称 | 如果未设置player_id则必填 |

**请求URL**:
```
https://apiv3.apifootball.com/?action=get_players&player_name=Benzema&APIkey=YOUR_KEY
```

---

### 5. 获取积分榜 (get_standings)

返回联赛积分榜。

**参数**:
| 参数 | 描述 | 必填 |
|------|------|------|
| league_id | 联赛ID | 是 |

**请求URL**:
```
https://apiv3.apifootball.com/?action=get_standings&league_id=152&APIkey=YOUR_KEY
```

**响应示例**:
```json
[
    {
        "country_name": "England",
        "league_id": "152",
        "league_name": "Premier League",
        "team_id": "141",
        "team_name": "Arsenal",
        "overall_league_position": "1",
        "overall_league_payed": "0",
        "overall_league_W": "0",
        "overall_league_D": "0",
        "overall_league_L": "0",
        "overall_league_GF": "0",
        "overall_league_GA": "0",
        "overall_league_PTS": "0"
    }
]
```

---

### 6. 获取赛事/赛程 (get_events) ⭐核心接口

返回比赛结果和赛程。

**参数**:
| 参数 | 描述 | 必填 |
|------|------|------|
| from | 开始日期 (yyyy-mm-dd) | 否 |
| to | 结束日期 (yyyy-mm-dd) | 否 |
| country_id | 国家ID | 否 |
| league_id | 联赛ID | 否 |
| match_id | 比赛ID | 否 |
| team_id | 球队ID | 否 |
| match_live | 实时比分 (1=仅直播) | 否 |
| withPlayerStats | 包含球员统计 (任意值) | 否 |
| timezone | 时区 (如: America/New_York) | 否 |

**请求URL**:
```
https://apiv3.apifootball.com/?action=get_events&from=2023-04-05&to=2023-04-05&league_id=152&APIkey=YOUR_KEY
```

**响应包含**:
- 比赛基本信息（ID、日期、时间、状态）
- 比分（全场、半场、加时、点球）
- 进球详情（时间、球员、助攻）
- 红黄牌
- 换人记录
- 阵容（首发、替补、教练）
- 比赛统计

**比赛状态值**:
| 状态 | 含义 |
|------|------|
| 数字+' | 比赛进行中（如 "45'"） |
| Half Time | 半场休息 |
| Finished | 常规时间结束 |
| After ET | 加时赛结束 |
| After Pen. | 点球大战结束 |
| Postponed | 推迟 |
| Cancelled | 取消 |
| Awarded | 判定结果 |

---

### 7. 获取赔率 (get_odds) ⭐赔率接口

返回比赛赔率（1x2、大小球、亚盘等）。

**参数**:
| 参数 | 描述 | 必填 |
|------|------|------|
| from | 开始日期 (yyyy-mm-dd) | 否 |
| to | 结束日期 (yyyy-mm-dd) | 否 |
| match_id | 比赛ID | 否 |

**请求URL**:
```
https://apiv3.apifootball.com/?action=get_odds&from=2023-05-16&to=2023-05-16&APIkey=YOUR_KEY
```

**响应示例**:
```json
[
    {
        "match_id": "58819",
        "odd_bookmakers": "bwin",
        "odd_date": "2023-05-16 19:28:36",
        "odd_1": "10",          // 主胜赔率
        "odd_x": "6.5",         // 平局赔率
        "odd_2": "1.24",        // 客胜赔率
        "odd_1x": "4",          // 主胜或平局
        "odd_12": "1.11",       // 主胜或客胜
        "odd_x2": "1.05",       // 平局或客胜
        "ah0_1": "",            // 亚盘 0 主
        "ah0_2": "",            // 亚盘 0 客
        "o+2.5": "1.32",        // 大2.5球
        "u+2.5": "3.1",         // 小2.5球
        "bts_yes": "1.7",       // 两队都进球-是
        "bts_no": "2"           // 两队都进球-否
    }
]
```

**赔率字段说明**:
| 字段 | 含义 |
|------|------|
| odd_1 | 主队胜 |
| odd_x | 平局 |
| odd_2 | 客队胜 |
| odd_1x | 主队胜或平局 |
| odd_12 | 主队胜或客队胜 |
| odd_x2 | 平局或客队胜 |
| ah-X_Y | 亚盘（X为盘口，Y为1=主/2=客） |
| o+X | 大球X |
| u+X | 小球X |
| bts_yes | 两队都进球-是 |
| bts_no | 两队都进球-否 |

---

### 8. 获取实时赔率和评论 (get_live_odds_commnets)

返回正在进行的比赛的实时赔率和评论。

**参数**:
| 参数 | 描述 | 必填 |
|------|------|------|
| country_id | 国家ID | 否 |
| league_id | 联赛ID | 否 |
| match_id | 比赛ID | 否 |

---

### 9. 获取阵容 (get_lineups)

返回单场比赛的阵容信息。

**参数**:
| 参数 | 描述 | 必填 |
|------|------|------|
| match_id | 比赛ID | 是 |

---

### 10. 获取统计 (get_statistics)

返回单场比赛的统计数据。

**参数**:
| 参数 | 描述 | 必填 |
|------|------|------|
| match_id | 比赛ID | 是 |

**响应包含**:
- 比赛统计（射门、犯规、角球、控球率等）
- 球员个人统计

---

### 11. 获取对决记录 (get_H2H)

返回两队历史交锋记录。

**参数**:
| 参数 | 描述 | 必填 |
|------|------|------|
| firstteam | 第一支球队ID | 是 |
| secondteam | 第二支球队ID | 是 |
| match_id | 比赛ID（可替代firstteam/secondteam） | 否 |

---

### 12. 获取预测 (get_predictions)

返回比赛预测数据。

**参数**:
| 参数 | 描述 | 必填 |
|------|------|------|
| match_id | 比赛ID | 是 |

---

### 13. 获取最佳射手 (get_topscorers)

返回联赛射手榜。

**参数**:
| 参数 | 描述 | 必填 |
|------|------|------|
| league_id | 联赛ID | 是 |

---

### 14. 获取实时比分 (Livescore)

使用 `get_events` 接口，设置 `match_live=1` 参数。

---

## 主要联赛ID参考

| 联赛 | league_id |
|------|-----------|
| 英超 | 152 |
| 西甲 | 302 |
| 德甲 | 207 |
| 意甲 | 207 |
| 法甲 | 168 |
| 英冠 | 153 |
| 欧冠 | 3 |

## 使用示例

### Python示例

```python
import aiohttp
import asyncio

async def get_fixtures():
    url = "https://apiv3.apifootball.com/"
    params = {
        "action": "get_events",
        "APIkey": "YOUR_API_KEY",
        "from": "2026-05-21",
        "to": "2026-05-24",
        "league_id": "152"  # 英超
    }
    
    async with aiohttp.ClientSession() as session:
        async with session.get(url, params=params) as response:
            data = await response.json()
            return data

# 运行
fixtures = asyncio.run(get_fixtures())
```

### 获取赔率示例

```python
async def get_odds():
    url = "https://apiv3.apifootball.com/"
    params = {
        "action": "get_odds",
        "APIkey": "YOUR_API_KEY",
        "from": "2026-05-21",
        "to": "2026-05-24"
    }
    
    async with aiohttp.ClientSession() as session:
        async with session.get(url, params=params) as response:
            data = await response.json()
            return data
```

## 速率限制

- 免费计划：10请求/分钟
- 建议请求间隔：2秒以上

## 错误处理

API返回空数组 `[]` 通常表示：
1. 无数据（该日期/联赛没有比赛）
2. 参数错误
3. 超出订阅范围

## 注意事项

1. 日期格式必须为 `yyyy-mm-dd`
2. 时间默认为欧洲/柏林时区，可通过 `timezone` 参数调整
3. 赔率数据来自多个博彩公司，`odd_bookmakers` 字段标识来源
4. 实时比分更新频率约1分钟
