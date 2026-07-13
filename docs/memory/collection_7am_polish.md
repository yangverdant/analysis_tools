---
name: collection_7am_polish
description: 7:00采集环节打磨——sporttery采集流程、队名映射3层修复、oddsfe桥接、赔率多快照、异常处理
metadata: 
  node_type: memory
  type: project
  originSessionId: d2e763d6-7730-4e83-a6e7-3cc8d939df30
---

## 7:00 采集环节打磨

### 整体流程

```
7:00  sporttery采集 → 比赛列表 + SPF/RQSPF赔率
7:30  oddsfe采集   → Pinnacle赔率 + source_mapping_bridge桥接
      同时执行      → 队名映射(中→英→team_id)
```

### 环节1: sporttery采集

**已有基础设施:**
- `LotteryCrawlerSync` (backend/app/lottery/data_sources/scrapers/lottery_crawler.py) — 完整的同步爬虫
- API: `https://webapi.sporttery.cn/gateway/jc/football/getMatchCalculatorV1.qry?sellStatus=on&date={date}`
- 解析: matchInfoList → subMatchList → 队名+赔率+让球+玩法
- 已跑通: 5月24-27日94场比赛成功采集

**需要修复的问题:**

1. **采集后自动入库**: 当前 `SyncService.sync_daily_matches()` 能入库lottery_matches，但赔率没入库lottery_odds
   - 修复: 在sync_daily_matches()中，对每场比赛的odds_data也写入lottery_odds表
   - 关键: `_extract_odds()`已经返回了spf/rqspf/bf/bqc赔率，但SyncService没有保存

2. **赔率快照**: 当前lottery_odds只有odds_data字段有值，opening_odds/latest_odds/odds_movement全NULL
   - 修复: 首次采集时，odds_data=opening_odds=当前赔率
   - 14:00二次采集时，odds_data=最新赔率，latest_odds=最新赔率，可计算odds_movement
   - 需要在lottery_odds表加 `snapshot_type TEXT DEFAULT 'opening'`

3. **sell_status更新**: 比赛可能从'selling'变为'sold_out'或'finished'
   - 修复: 每次采集时更新已入库比赛的sell_status

4. **data_source_health更新**: 采集成功/失败后更新data_source_health表

### 环节2: 队名映射 — 3层修复

**核心断点: 国家队中文名无法映射到英文名**

当前映射路径:
```
体彩中文名 "日本" → ??? → team_id=484(Japan in teams表)
```

3层映射机制:
1. **team_name_mapping表** (105条，主要是5大联赛俱乐部) — 精确匹配
2. **EntityMapper._fuzzy_match_team()** (SequenceMatcher, 阈值0.8) — 模糊匹配
3. **fetchers/common/team_names.py** normalize_team_name() — 多源别名

**问题诊断:**

`normalize_team_name("日本")` 返回 "日本" 而不是 "Japan"

原因: team_names.py第164行 — `if en_name in _standard_to_info`
- team_chinese_names.json有 "Japan"→"日本" 映射
- 但 "Japan" 不在 _standard_to_info 中（因为team_aliases.json只有5大联赛俱乐部，没有国家队）
- 所以 "日本"→"Japan" 的映射永远不会建立

**3层修复方案:**

**修复层1: team_names.py — 直接将chinese_names的映射加入索引(无论英文名是否已知)**

```python
# 第4步的修复: 不仅映射到已知标准名，也直接建立中→英映射
chinese = _load_chinese_names()
for en_name, cn_name in chinese.items():
    cn_key = cn_name.lower()
    # 新增: 直接建立中文→英文映射（不论英文是否已知标准名）
    if cn_key not in _name_to_standard:
        _name_to_standard[cn_key] = en_name

    # 原有逻辑: 如果英文名是已知标准名，补充别名
    if en_name in _standard_to_info:
        if cn_name not in _standard_to_all_names.get(en_name, []):
            _standard_to_all_names.setdefault(en_name, [en_name]).append(cn_name)
    elif en_name.lower() in _name_to_standard:
        standard = _name_to_standard[en_name.lower()]
        if cn_key not in _name_to_standard:
            _name_to_standard[cn_key] = standard
```

这样修复后:
- `normalize_team_name("日本")` → "Japan" ✓
- `normalize_team_name("巴西")` → "Brazil" ✓
- `normalize_team_name("韩国")` → "Korea Republic" ✓（需确认team_chinese_names.json的值）

**修复层2: EntityMapper — 增强_lot_team_mappings()**

当前从teams表加载name_cn，但teams表的name_cn可能有编码问题或缺失。
补充: 也从team_chinese_names.json反向加载

```python
def _load_team_mappings(self):
    # 现有: team_name_mapping表 + teams表name_cn
    # ...

    # 新增: 从team_chinese_names.json加载国家队映射
    from fetchers.common.team_names import _load_chinese_names
    chinese = _load_chinese_names()
    for en_name, cn_name in chinese.items():
        # 查teams表获取team_id
        cursor.execute(
            "SELECT team_id FROM teams WHERE name_en = ? LIMIT 1",
            (en_name,)
        )
        row = cursor.fetchone()
        if row:
            self._team_name_cache[cn_name] = row[0]
```

**修复层3: sporttery采集时自动注册新映射**

当匹配成功但team_name_mapping表中没有记录时，自动注册:

```python
# 在sync_daily_matches()中
if home_team_id and home_team_cn not in team_name_cache:
    self.mapper.register_team_mapping(home_team_cn, home_team_id, 'auto')
```

这样，第一次遇到"日本"时通过修复层2匹配成功，然后自动写入team_name_mapping，下次直接查表。

### 环节3: oddsfe桥接 — source_mapping_bridge

**目标:** 将lottery_match与oddsfe的event_id关联，后续可用oddsfe获取Pinnacle赔率、比赛结果

**匹配逻辑:**
1. 用normalize_team_name()将中文名转为英文名
2. 查oddsfe schedule API获取当天所有赛事
3. 用英文名+日期窗口(±12h，考虑时区)匹配
4. 匹配成功 → 写入source_mapping_bridge

**时区处理(核心!):**
```
oddsfe: 2026-06-08 19:00 UTC
北京时间: 2026-06-09 03:00 (UTC+8)
体彩日期: 2026-06-09 (按北京日期归档)

匹配: oddsfe UTC时间 +8h → 北京时间 → 取日期部分 → 与体彩日期比较
容差: ±12h (覆盖跨日场次)
```

**桥接数据结构:**
```python
bridge = {
    'system_match_id': None,  # lottery系统没有match_id，暂留空
    'lottery_issue_num': '202606098001',  # lottery_match_id
    'apifootball_id': None,  # 后续补
    'sportmonks_id': None,
    'bet365_id': None,
    'fbref_id': None,
    'statsbomb_id': None,
    'sofascore_id': None,
    'home_team_lottery_name': '日本',
    'away_team_lottery_name': '澳大利亚',
    'match_confidence': 0.95,  # 匹配置信度
    'match_method': 'name+date'  # 匹配方式
}
```

**oddsfe_event_id存储:** 当前source_mapping_bridge没有oddsfe_event_id字段
- 方案A: 加字段 `oddsfe_event_id VARCHAR(50)`
- 方案B: 复用 `bet365_id` 字段(不优雅但少改表)
- **选方案A**: 更清晰，oddsfe是主要赔率源，应该有独立字段

### 环节4: 赔率多快照设计

```
7:00  首次采集  → snapshot_type='opening'  → lottery_odds写入
14:00 二次采集  → snapshot_type='midday'   → lottery_odds追加(新行)
赛后  闭盘采集  → snapshot_type='closing'   → lottery_odds追加(新行)
```

lottery_odds表需要改造:
- 加 `snapshot_type TEXT DEFAULT 'opening'`
- 同一场比赛可以有3行(odds_id不同，lottery_match_id相同，snapshot_type不同)
- CLV计算: opening vs midday 的赔率变化方向

### 环节5: 异常场景处理

**sporttery采集失败:**
- 超时 → 重试3次(间隔10s/30s/60s)
- 返回空 → 可能今天没开售，等1h后重试(体彩开售时间不固定)
- 返回success=false → 检查日期格式，换前一天试试
- 3次都失败 → 更新data_source_health为'degraded'，用缓存数据

**队名映射失败:**
- 标记 `mapped=False`，confidence='low'
- 写入unmapped_teams列表
- 不阻止分析流程——赔率基础模型仍然可用
- 自动学习: 下次用同一个中文名查mapping，如果有手动补充的记录就直接用

**oddsfe桥接失败:**
- 一场体彩比赛匹配到oddsfe多场 → 用联赛名+时间窗口辅助筛选
- 完全匹配不到 → 记录未桥接，后续人工处理
- oddsfe API 401 → 自动刷新auth(get_schedule_auth())

**赔率获取失败:**
- 某场比赛没有SPF赔率 → 该场比赛不进入分析(赔率是最低要求)
- 有SPF没有RQSPF → 只做SPF分析
- oddsfe没有Pinnacle赔率 → 用体彩赔率替代(准确度降低)

### 7:00采集后的数据状态

```
采集完成后，DB应有:

lottery_matches:    今天的比赛(N场)，team_id已填充
lottery_odds:       每场SPF赔率(snapshot_type='opening')，部分有RQSPF
source_mapping_bridge: 部分比赛已桥接到oddsfe
data_source_health: sporttery=healthy, oddsfe=healthy(或degraded)
team_name_mapping:  新遇到的队名已自动注册

统计指标:
- 采集率: 入库数/爬取数
- 映射率: 有team_id的/总数
- 桥接率: 有oddsfe_event_id的/总数
- 赔率覆盖: 有SPF赔率的/总数
```
