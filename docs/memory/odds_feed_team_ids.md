---
name: odds-feed-team-ids
description: Odds Feed API赛事ID与球队名映射（持续积累），Portal API查询方式，按联赛分类
metadata: 
  node_type: memory
  type: reference
  originSessionId: a3325eab-87ac-48a6-8496-2ff45be69cae
---

# Odds Feed API 赛事ID与球队名映射

**持续积累**：每次通过 Portal API 查到新赛事，将 event_id + 球队名追加到对应联赛下。积累越多，后续直接用 event_id 查赔率越快，不用再翻赛事列表。

## 查询方式

### 按日期查赛事（获取当天所有比赛的 event_id）
```python
headers = {'x-portal-apikey': '{key}'}
params = {'sport_id': '1', 'start_at_min': '2026-05-28 00:00:00', 'start_at_max': '2026-05-29 00:00:00'}
r = requests.get('https://{API_HOST}/api/v1/events', params=params, headers=headers)
```

### 按 event_id 查赔率
```python
params = {'event_id': '592956'}
r = requests.get('https://{API_HOST}/api/v1/events/markets', params=params, headers=headers)
```

### 按 event_ids 查赛事详情
```python
params = {'event_ids': '592956'}
r = requests.get('https://{API_HOST}/api/v1/events', params=params, headers=headers)
```

## 联赛 Tournament ID 速查

| 联赛 | tid | 联赛 | tid |
|------|-----|------|-----|
| Premier League | 430 | Championship | 431 |
| Bundesliga | 560 | Bundesliga 2 | 561 |
| Serie A | 719 | Serie B | 720 |
| LaLiga | 1146 | LaLiga2 | 1147 |
| Eredivisie | 862 | J1 League | 763 |
| MLS | 1265 | China SL | 322 |
| League One | 432 | League Two | 433 |
| Ligue 1 | 待确认 | Ligue 2 | 540(待验证) |

## 赛事记录（按联赛分类）

用户从 https://oddsfe.com/schedule/football/2026-05-24 实际页面验证的球队与event ID。

## Premier League (tid=430, season=23865)

| Event ID | Home | Away | 欧赔(主/平/客) |
|----------|------|------|---------------|
| 586704 | Brighton | Manchester Utd | 1.90 / 4.47 / 3.53 |
| 586459 | Tottenham | Everton | 1.95 / 3.58 / 4.21 |
| 586502 | Liverpool | Brentford | 1.81 / 4.18 / 4.15 |
| 589219 | Fulham | Newcastle | 2.59 / 3.70 / 2.69 |
| 586547 | Crystal Palace | Arsenal | 4.30 / 3.76 / 1.87 |
| 586548 | Manchester City | Aston Villa | 1.41 / 5.19 / 7.40 |
| 589083 | Burnley | Wolves | 2.43 / 3.54 / 3.00 |
| 589367 | Nottingham | Bournemouth | 3.59 / 3.78 / 2.06 |
| 586676 | West Ham | Leeds | 1.74 / 4.34 / 4.34 |
| 589227 | Sunderland | Chelsea | 3.47 / 3.83 / 2.09 |

## Bundesliga (tid=560, season=24025)

| Event ID | Home | Away |
|----------|------|------|
| 592628 | Paderborn | Wolfsburg |

## Serie A (tid=719, season=24090)

| Event ID | Home | Away | 欧赔 |
|----------|------|------|------|
| 589373 | Parma | Sassuolo | 3.33/3.35/2.33 |
| 589372 | Napoli | Udinese | 1.57/4.09/6.39 |
| 586683 | Torino | Juventus | 6.45/4.46/1.51 |
| 586546 | AC Milan | Cagliari | 1.38/4.76/9.34 |
| 589371 | Lecce | Genoa | 1.94/3.26/4.78 |
| 586585 | Verona | AS Roma | 10.00/5.13/1.34 |
| 586539 | Cremonese | Como | 5.81/4.34/1.57 |

## LaLiga (tid=1146, season=23862)

| Event ID | Home | Away | 欧赔 |
|----------|------|------|------|
| 586562 | Villarreal | Atl. Madrid | 2.58/3.93/2.60 |

## Eredivisie (tid=862, season=23713)

| Event ID | Home | Away |
|----------|------|------|
| 592813 | Ajax | Utrecht |

## MLS (tid=1265, season=26879)

| Event ID | Home | Away |
|----------|------|------|
| 588654 | Chicago Fire | Toronto FC |
| 588653 | Sporting Kansas City | New York Red Bulls |
| 588777 | Nashville SC | New York City |
| 588670 | San Diego FC | Vancouver Whitecaps |
| 588778 | Portland Timbers | San Jose Earthquakes |
| 588669 | Colorado Rapids | FC Dallas |
| 588673 | Los Angeles Galaxy | Houston Dynamo |
| 588780 | Columbus Crew | Atlanta Utd |
| 588781 | Inter Miami | Philadelphia Union |

## LaLiga2 (tid=1147, season=23863)

| Event ID | Home | Away |
|----------|------|------|
| 589111 | Andorra | Ceuta |
| 589126 | Albacete | Real Sociedad B |
| 589128 | Las Palmas | Zaragoza |
| 589134 | Mirandes | Granada CF |
| 589129 | Malaga | Racing Santander |
| 589131 | Huesca | Castellon |
| 589133 | Valladolid | Dep. La Coruna |
| 589127 | Cadiz CF | Leganes |
| 589110 | Gijon | Almeria |
| 589132 | Eibar | Cordoba |
| 589130 | Cultural Leonesa | Burgos CF |

## Serie B (tid=720, season=24169)

| Event ID | Home | Away |
|----------|------|------|
| 591923 | Catanzaro | Monza |

## J1 League (tid=763, season=26675)

| Event ID | Home | Away |
|----------|------|------|
| 588720 | Okayama | Cerezo Osaka |
| 588794 | Mito Hollyhock | Kawasaki Frontale |
| 588740 | Verdy | Yokohama F. Marinos |
| 588779 | Shimizu S-Pulse | Gamba Osaka |

## NPL Western Australia (tid=109, season=27080)

| Event ID | Home | Away |
|----------|------|------|
| 591074 | Perth RedStar | Perth SC |

## League One (tid=432, season=23596)

| Event ID | Home | Away |
|----------|------|------|
| 586798 | Stockport County | Bolton |

## 用途

- event_id 可直接用于 Portal API `/api/v1/events/markets?event_id={id}` 查详细赔率
- 批量查询用 RapidAPI `/api/v1/markets/feed?event_ids={csv}` (最多100个)
- 采集时用 event_id 关联 match_key（通过 date+home+away）
- **积累越多越方便**：有了 event_id 直接查赔率，跳过翻列表的步骤