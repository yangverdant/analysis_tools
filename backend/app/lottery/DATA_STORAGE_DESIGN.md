# 体彩分析系统 - 数据存储与串联设计

## 一、核心设计理念：星型拓扑模型 (Star Schema)

全局唯一的 `match_id` 是串联一切的灵魂。所有数据围绕比赛这一核心实体组织。

```
                         ┌─────────────────┐
                         │    matches      │
                         │  (比赛核心表)    │
                         │  match_id (PK)  │
                         └────────┬────────┘
                                  │
        ┌─────────────┬───────────┼───────────┬─────────────┐
        │             │           │           │             │
        ▼             ▼           ▼           ▼             ▼
┌─────────────┐ ┌─────────────┐ ┌─────────────┐ ┌─────────────┐ ┌─────────────┐
│ match_stats │ │ match_odds  │ │match_lineups│ │match_events │ │predictions  │
│ (深度统计)  │ │ (赔率数据)  │ │ (首发阵容)  │ │ (比赛事件)  │ │ (预测记录)  │
└─────────────┘ └─────────────┘ └─────────────┘ └─────────────┘ └─────────────┘
```

---

## 二、核心骨架表设计

### 2.1 比赛基础骨架表 (matches) - 绝对枢纽

```sql
CREATE TABLE matches (
    -- 主键 (系统灵魂)
    match_id INTEGER PRIMARY KEY,
    
    -- 赛事关联
    league_id INTEGER NOT NULL,          -- 关联 leagues 表
    season_id INTEGER,                   -- 关联 seasons 表
    round_num INTEGER,                   -- 轮次
    
    -- 时间信息
    match_date DATE NOT NULL,            -- 比赛日期
    match_time VARCHAR(10),              -- 开球时间 (如: "22:00")
    beijing_time VARCHAR(20),            -- 北京时间 (计算后)
    timezone VARCHAR(50),                -- 时区
    
    -- 球队关联 (核心外键)
    home_team_id INTEGER NOT NULL,       -- 主队ID → teams.team_id
    away_team_id INTEGER NOT NULL,       -- 客队ID → teams.team_id
    
    -- 比赛状态
    status VARCHAR(20) DEFAULT 'scheduled', -- scheduled/live/finished/postponed/cancelled
    match_status VARCHAR(50),            -- 详细状态 (如: "第35分钟")
    
    -- 比赛结果 (完场后写入)
    home_goals INTEGER,                  -- 全场主队进球
    away_goals INTEGER,                  -- 全场客队进球
    home_goals_ht INTEGER,               -- 半场主队进球
    away_goals_ht INTEGER,               -- 半场客队进球
    
    -- 结果标识
    result VARCHAR(1),                   -- H/D/A (主胜/平/客胜)
    total_goals INTEGER,                 -- 总进球数
    
    -- 场地信息
    venue VARCHAR(100),                  -- 球场名称
    referee_id INTEGER,                  -- 裁判ID → referees 表
    attendance INTEGER,                  -- 观众人数
    
    -- 元信息
    source VARCHAR(50),                  -- 数据来源
    last_sync TIMESTAMP,                 -- 最后同步时间
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    -- 外键约束
    FOREIGN KEY (league_id) REFERENCES leagues(league_id),
    FOREIGN KEY (home_team_id) REFERENCES teams(team_id),
    FOREIGN KEY (away_team_id) REFERENCES teams(team_id),
    
    -- 索引
    UNIQUE (match_date, home_team_id, away_team_id)
);

-- 索引设计
CREATE INDEX idx_matches_date ON matches(match_date);
CREATE INDEX idx_matches_league ON matches(league_id, season_id);
CREATE INDEX idx_matches_team ON matches(home_team_id, away_team_id);
CREATE INDEX idx_matches_status ON matches(status);
```

### 2.2 数据源桥接映射表 (source_mapping_bridge) - 串联钥匙

```sql
CREATE TABLE source_mapping_bridge (
    -- 主键
    bridge_id INTEGER PRIMARY KEY AUTOINCREMENT,
    
    -- 系统核心ID
    system_match_id INTEGER NOT NULL,    -- 关联 matches.match_id
    
    -- 各数据源ID映射
    lottery_issue_num VARCHAR(50),       -- 体彩场次号 (如: "20260524001")
    apifootball_id INTEGER,              -- API-Football ID
    sportmonks_id INTEGER,               -- Sportmonks ID
    bet365_id VARCHAR(50),               -- Bet365 ID
    fbref_id VARCHAR(50),                -- FBref ID
    statsbomb_id VARCHAR(50),            -- StatsBomb ID
    sofascore_id INTEGER,                -- Sofascore ID
    
    -- 球队ID映射 (冗余，加速查询)
    home_team_lottery_name VARCHAR(50),  -- 体彩主队名称
    away_team_lottery_name VARCHAR(50),  -- 体彩客队名称
    
    -- 映射置信度
    match_confidence REAL DEFAULT 1.0,   -- 0-1，表示映射可信度
    match_method VARCHAR(20),            -- exact/fuzzy/manual
    
    -- 时间戳
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    -- 外键
    FOREIGN KEY (system_match_id) REFERENCES matches(match_id),
    
    -- 唯一约束
    UNIQUE (system_match_id),
    UNIQUE (lottery_issue_num)
);

-- 索引
CREATE INDEX idx_bridge_lottery ON source_mapping_bridge(lottery_issue_num);
CREATE INDEX idx_bridge_api ON source_mapping_bridge(apifootball_id);
```

### 2.3 完场深度统计表 (match_stats_detailed)

```sql
CREATE TABLE match_stats_detailed (
    stat_id INTEGER PRIMARY KEY AUTOINCREMENT,
    
    -- 关联比赛
    match_id INTEGER NOT NULL,           -- → matches.match_id
    team_id INTEGER NOT NULL,            -- 区分主队/客队统计
    
    -- 进攻数据
    shots_total INTEGER DEFAULT 0,
    shots_on_target INTEGER DEFAULT 0,
    shots_off_target INTEGER DEFAULT 0,
    shots_blocked INTEGER DEFAULT 0,
    
    -- 预期进球 (核心指标)
    expected_goals REAL,                 -- xG (核心指标)
    expected_goals_on_target REAL,       -- xGOT
    expected_goals_first_half REAL,      -- 半场xG
    
    -- 控球与传球
    possession REAL,                     -- 控球率 (如: 65.5)
    passes_total INTEGER,
    passes_completed INTEGER,
    passes_accuracy REAL,
    passes_final_third INTEGER,          -- 进入进攻三区传球
    passes_penalty_area INTEGER,         -- 进入禁区传球
    
    -- 定位球
    corners INTEGER DEFAULT 0,
    corner_taken INTEGER DEFAULT 0,
    free_kicks INTEGER DEFAULT 0,
    penalties_won INTEGER DEFAULT 0,
    
    -- 防守数据
    fouls_committed INTEGER DEFAULT 0,
    fouls_drawn INTEGER DEFAULT 0,
    yellow_cards INTEGER DEFAULT 0,
    red_cards INTEGER DEFAULT 0,
    offsides INTEGER DEFAULT 0,
    
    -- 高级战术数据
    tackles INTEGER,
    tackles_won INTEGER,
    interceptions INTEGER,
    clearances INTEGER,
    blocks INTEGER,
    aerial_duels_won INTEGER,
    aerial_duels_total INTEGER,
    
    -- 跑动数据 (如果有)
    distance_covered REAL,               -- 跑动距离 (km)
    sprints INTEGER,                     -- 冲刺次数
    
    -- 数据来源
    source VARCHAR(50),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    FOREIGN KEY (match_id) REFERENCES matches(match_id),
    FOREIGN KEY (team_id) REFERENCES teams(team_id),
    
    UNIQUE (match_id, team_id)
);

-- 索引
CREATE INDEX idx_stats_match ON match_stats_detailed(match_id);
CREATE INDEX idx_stats_team ON match_stats_detailed(team_id);
```

### 2.4 实时赔率表 (match_odds) - 体彩核心

```sql
CREATE TABLE match_odds (
    odds_id INTEGER PRIMARY KEY AUTOINCREMENT,
    
    -- 关联比赛
    match_id INTEGER NOT NULL,           -- → matches.match_id
    lottery_match_id VARCHAR(50),        -- 体彩比赛ID
    
    -- 玩法类型
    play_type VARCHAR(20) NOT NULL,      -- spf/bf/bqc/rqspf/ou
    
    -- 赔率数据
    odds_json TEXT NOT NULL,             -- JSON格式赔率
    /*
    SPF: {"3": 2.15, "1": 3.20, "0": 3.05}
    BF: {"10": 12.0, "20": 8.5, ...}
    BQC: {"33": 3.5, "31": 6.0, ...}
    */
    
    -- 隐含概率 (计算后)
    implied_prob_json TEXT,              -- JSON格式隐含概率
    
    -- 临场变化追踪
    opening_odds_json TEXT,              -- 初盘赔率
    latest_odds_json TEXT,               -- 最新赔率
    odds_movement TEXT,                  -- 赔率变动历史 (JSON数组)
    
    -- 降水指数 (核心监控指标)
    water_drop_index REAL,               -- 临场降水指数
    hot_cold_index REAL,                 -- 冷热指数
    
    -- 时间戳
    update_time TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    FOREIGN KEY (match_id) REFERENCES matches(match_id)
);

-- 索引
CREATE INDEX idx_odds_match ON match_odds(match_id, play_type);
CREATE INDEX idx_odds_lottery ON match_odds(lottery_match_id);
CREATE INDEX idx_odds_time ON match_odds(update_time);
```

### 2.5 比赛阵容表 (match_lineups)

```sql
CREATE TABLE match_lineups (
    lineup_id INTEGER PRIMARY KEY AUTOINCREMENT,
    
    -- 关联比赛
    match_id INTEGER NOT NULL,
    team_id INTEGER NOT NULL,
    
    -- 阵型信息
    formation VARCHAR(20),               -- 如: "4-3-3"
    
    -- 阵容详情 (JSON)
    starting_xi TEXT,                    -- 首发11人 JSON
    /*
    [
        {
            "position": "GK",
            "player_id": 123,
            "player_name": "Onana",
            "shirt_number": 1
        },
        ...
    ]
    */
    
    substitutes TEXT,                    -- 替补席 JSON
    
    -- 战术信息
    captain_id INTEGER,                  -- 队长ID
    formation_changed INTEGER DEFAULT 0, -- 是否变阵
    formation_notes TEXT,                -- 阵型备注
    
    -- 状态
    confirmed INTEGER DEFAULT 0,         -- 是否确认 (1=官方确认)
    
    source VARCHAR(50),
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    FOREIGN KEY (match_id) REFERENCES matches(match_id),
    FOREIGN KEY (team_id) REFERENCES teams(team_id),
    
    UNIQUE (match_id, team_id)
);
```

### 2.6 比赛事件时间线表 (match_timeline_events)

```sql
CREATE TABLE match_timeline_events (
    event_id INTEGER PRIMARY KEY AUTOINCREMENT,
    
    -- 关联比赛
    match_id INTEGER NOT NULL,
    
    -- 事件信息
    minute INTEGER NOT NULL,             -- 发生时间 (如: 35)
    minute_stoppage INTEGER,             -- 补时分钟
    event_type VARCHAR(30) NOT NULL,     -- Goal/Card/Substitution/Var/Penalty
    event_detail VARCHAR(100),           -- 详细描述
    
    -- 关联球队和球员
    team_id INTEGER,
    player_id INTEGER,                   -- 主角球员
    player_assist_id INTEGER,            -- 助攻球员
    player_related_id INTEGER,           -- 相关球员 (换下球员等)
    
    -- 事件详情 (JSON)
    detail_json TEXT,
    /*
    {
        "goal_type": "header",
        "distance": 12,
        "body_part": "head",
        "situation": "corner"
    }
    */
    
    -- VAR信息
    var_review INTEGER DEFAULT 0,        -- 是否经过VAR
    var_result VARCHAR(50),              -- VAR结果
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    FOREIGN KEY (match_id) REFERENCES matches(match_id),
    FOREIGN KEY (team_id) REFERENCES teams(team_id),
    FOREIGN KEY (player_id) REFERENCES players(player_id)
);

-- 索引
CREATE INDEX idx_events_match ON match_timeline_events(match_id);
CREATE INDEX idx_events_type ON match_timeline_events(event_type);
CREATE INDEX idx_events_player ON match_timeline_events(player_id);
```

### 2.7 预测记录表 (predictions_log)

```sql
CREATE TABLE predictions_log (
    prediction_id INTEGER PRIMARY KEY AUTOINCREMENT,
    
    -- 关联比赛
    match_id INTEGER NOT NULL,
    lottery_match_id VARCHAR(50),
    
    -- 玩法
    play_type VARCHAR(20) NOT NULL,
    
    -- 预测结果
    prediction_json TEXT NOT NULL,       -- 完整预测JSON
    predicted_result VARCHAR(20),        -- 预测结果
    confidence REAL,                     -- 置信度
    confidence_level VARCHAR(20),        -- high/medium/low
    
    -- 特征数据 (用于追溯)
    features_json TEXT,                  -- 提取的所有特征
    weights_json TEXT,                   -- 使用的权重
    
    -- 价值投注
    value_bets_json TEXT,                -- 价值投注列表
    
    -- 验证结果 (赛后填写)
    actual_result VARCHAR(20),           -- 实际结果
    is_correct INTEGER,                  -- 是否正确 0/1
    brier_score REAL,                    -- 布莱尔分数
    
    -- 元信息
    model_version VARCHAR(20),
    predicted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    validated_at TIMESTAMP,
    
    FOREIGN KEY (match_id) REFERENCES matches(match_id)
);

-- 索引
CREATE INDEX idx_predictions_match ON predictions_log(match_id);
CREATE INDEX idx_predictions_play ON predictions_log(play_type);
CREATE INDEX idx_predictions_validated ON predictions_log(validated_at);
```

---

## 三、数据串联逻辑

### 3.1 纵向串联：时间线维度

```
[Match ID: 999888] (曼联 vs 阿森纳)
 │
 ├── 赛前状态 (status = 'scheduled')
 │    ├── match_odds (WHERE match_id = 999888)
 │    │    → 获取实时体彩赔率与盘口
 │    │
 │    ├── match_lineups (WHERE match_id = 999888)
 │    │    → 获取双方首发11人与阵型
 │    │
 │    └── predictions_log (WHERE match_id = 999888)
 │         → 获取系统预测结果
 │
 ├── 比赛进行中 (status = 'live')
 │    └── match_timeline_events (WHERE match_id = 999888 ORDER BY minute)
 │         → 精确还原第35分钟红牌、第78分钟进球等事件
 │
 └── 完场后复盘 (status = 'finished')
      ├── match_stats_detailed (WHERE match_id = 999888)
      │    → 拿到xG、角球、控球率等深度数据
      │
      └── predictions_log (WHERE match_id = 999888)
           → 提取赛前预测，计算准确率
```

### 3.2 横向串联：球队历史轨迹

**查询示例：曼联最近10场主场比赛的进球能力**

```sql
-- Step 1: 获取最近10场主场比赛的 match_id
SELECT match_id, match_date, home_goals, away_goals
FROM matches
WHERE home_team_id = (SELECT team_id FROM teams WHERE name_en = 'Manchester United')
  AND status = 'finished'
ORDER BY match_date DESC
LIMIT 10;

-- Step 2: 获取这10场比赛的深度统计 (xG等)
SELECT m.match_date, m.home_goals, ms.expected_goals, ms.shots_on_target
FROM matches m
JOIN match_stats_detailed ms ON m.match_id = ms.match_id
WHERE m.match_id IN (上一步的结果)
  AND ms.team_id = (SELECT team_id FROM teams WHERE name_en = 'Manchester United');

-- Step 3: 结合阵容信息 (核心球员缺阵影响)
SELECT m.match_date, m.home_goals, ml.formation, ml.starting_xi
FROM matches m
JOIN match_lineups ml ON m.match_id = ml.match_id
WHERE m.match_id IN (第一步的结果)
  AND ml.team_id = (SELECT team_id FROM teams WHERE name_en = 'Manchester United');
```

### 3.3 数据源ID映射串联

**问题：体彩官网的"周三001"和API-Football的 match_id=999888 是同一场比赛，如何关联？**

```python
# EntityMapper 核心逻辑

def link_lottery_to_system(lottery_data: Dict) -> int:
    """
    体彩数据 → 系统match_id
    
    流程:
    1. 体彩比赛: "周三001 曼联 vs 阿森纳"
    2. 球队映射: "曼联" → team_id=33, "阿森纳" → team_id=42
    3. 时间匹配: 查找 matches 表中 match_date=2026-05-24 且主客队ID匹配的记录
    4. 返回: match_id = 999888
    """
    
    # 1. 球队名称映射
    home_team_id = team_mapper.get_team_id(lottery_data['home_team_cn'])  # 33
    away_team_id = team_mapper.get_team_id(lottery_data['away_team_cn'])  # 42
    
    # 2. 查找已存在的比赛
    cursor.execute("""
        SELECT match_id FROM matches
        WHERE match_date = ?
          AND home_team_id = ?
          AND away_team_id = ?
    """, (lottery_data['match_date'], home_team_id, away_team_id))
    
    row = cursor.fetchone()
    
    if row:
        # 3a. 已存在，写入桥接表
        match_id = row[0]
        cursor.execute("""
            INSERT OR REPLACE INTO source_mapping_bridge
            (system_match_id, lottery_issue_num, match_confidence, match_method)
            VALUES (?, ?, 1.0, 'exact')
        """, (match_id, lottery_data['lottery_match_id']))
        
        return match_id
    
    else:
        # 3b. 不存在，创建新比赛记录
        cursor.execute("""
            INSERT INTO matches
            (match_date, home_team_id, away_team_id, status, source)
            VALUES (?, ?, ?, 'scheduled', 'lottery')
        """, (lottery_data['match_date'], home_team_id, away_team_id))
        
        match_id = cursor.lastrowid
        
        # 写入桥接表
        cursor.execute("""
            INSERT INTO source_mapping_bridge
            (system_match_id, lottery_issue_num, match_method)
            VALUES (?, ?, 'created')
        """, (match_id, lottery_data['lottery_match_id']))
        
        return match_id
```

---

## 四、ETL数据流转生命周期

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         完整数据流转生命周期                                  │
└─────────────────────────────────────────────────────────────────────────────┘

06:00 - 数据采集
    │
    ├── 爬虫扫到体彩开售 "周三001 曼联 vs 阿森纳"
    │
    ├── EntityMapper 解析:
    │    ├── 体彩"曼联" → team_id = 33
    │    ├── 体彩"阿森纳" → team_id = 42
    │    └── 查找已存在比赛 → match_id = 999888
    │
    └── 写入 source_mapping_bridge:
         └── lottery_issue_num = "20260524001" ↔ system_match_id = 999888

09:00 - 特征提取
    │
    ├── 泊松提取器:
    │    └── SELECT * FROM matches WHERE home_team_id = 33 ... (最近20场)
    │
    ├── 伤停提取器:
    │    └── SELECT * FROM player_status WHERE team_id IN (33, 42) ...
    │
    └── 赔率提取器:
         └── SELECT * FROM match_odds WHERE match_id = 999888

赛前2h - 情报注入
    │
    ├── 获取首发阵容 → 写入 match_lineups
    │
    └── AI分析新闻 → 更新 match_narratives

赛前30m - 最终预测
    │
    ├── 集成所有特征 → 生成预测
    │
    └── 写入 predictions_log:
         └── match_id = 999888, prediction = {...}

赛后 - 结果验证
    │
    ├── 获取赛果 → 更新 matches (home_goals, away_goals, result)
    │
    ├── 获取详细统计 → 写入 match_stats_detailed
    │
    └── 对比预测 → 更新 predictions_log (is_correct, brier_score)

次日03:00 - 权重优化
    │
    └── 分析最近30天验证结果 → 调整提取器权重
```

---

## 五、核心原则

### 5.1 绝对规则

```
1. 系统内部绝对不允许通过队名 ("Manchester Utd") 匹配数据
   → 一切外部数据抓取后，第一件事就是转换为 team_id

2. 所有表的外键全部使用数字ID
   → match_id, team_id, player_id, league_id

3. 历史数据不可变
   → 完场比赛数据只写入一次，永不修改
   → Update 仅用于更新热区表 (实时赔率) 和状态字段

4. 错误数据不删除
   → 通过追加负向补丁记录，或标记 status = 'invalid'
   → 保证数据溯源完整
```

### 5.2 查询优化

```sql
-- 使用覆盖索引加速查询
CREATE INDEX idx_matches_cover ON matches(match_date, home_team_id, away_team_id, status);

-- 使用物化视图 (SQLite不支持，可用定时任务生成缓存表)
-- 预计算球队最近N场数据
CREATE TABLE team_form_cache (
    team_id INTEGER,
    period_days INTEGER,
    matches_played INTEGER,
    wins INTEGER,
    draws INTEGER,
    losses INTEGER,
    goals_for INTEGER,
    goals_against INTEGER,
    xg_for REAL,
    xg_against REAL,
    updated_at TIMESTAMP,
    PRIMARY KEY (team_id, period_days)
);
```

---

## 六、串联查询示例

### 6.1 获取比赛完整信息

```sql
-- 一条SQL获取比赛的所有关联数据
SELECT 
    m.match_id,
    m.match_date,
    m.match_time,
    ht.name_en as home_team,
    at.name_en as away_team,
    m.home_goals,
    m.away_goals,
    o.odds_json as spf_odds,
    p.prediction_json,
    p.predicted_result,
    p.confidence
FROM matches m
JOIN teams ht ON m.home_team_id = ht.team_id
JOIN teams at ON m.away_team_id = at.team_id
LEFT JOIN match_odds o ON m.match_id = o.match_id AND o.play_type = 'spf'
LEFT JOIN predictions_log p ON m.match_id = p.match_id AND p.play_type = 'spf'
WHERE m.match_id = 999888;
```

### 6.2 球队历史战绩 + xG趋势

```sql
SELECT 
    m.match_date,
    CASE WHEN m.home_team_id = 33 THEN 'H' ELSE 'A' END as venue,
    CASE WHEN m.home_team_id = 33 THEN ht.name_en ELSE at.name_en END as opponent,
    CASE WHEN m.home_team_id = 33 THEN m.home_goals ELSE m.away_goals END as goals_for,
    CASE WHEN m.home_team_id = 33 THEN m.away_goals ELSE m.home_goals END as goals_against,
    ms.expected_goals as xg,
    ms.possession,
    ms.shots_on_target
FROM matches m
JOIN teams ht ON m.home_team_id = ht.team_id
JOIN teams at ON m.away_team_id = at.team_id
LEFT JOIN match_stats_detailed ms ON m.match_id = ms.match_id 
    AND ms.team_id = 33
WHERE (m.home_team_id = 33 OR m.away_team_id = 33)
  AND m.status = 'finished'
ORDER BY m.match_date DESC
LIMIT 20;
```

### 6.3 体彩赔率变化追踪

```sql
SELECT 
    sm.lottery_issue_num,
    o.play_type,
    o.opening_odds_json,
    o.latest_odds_json,
    o.water_drop_index,
    o.update_time
FROM source_mapping_bridge sm
JOIN match_odds o ON sm.system_match_id = o.match_id
WHERE sm.lottery_issue_num = '20260524001'
ORDER BY o.update_time DESC;
```

---

## 七、总结

| 核心概念 | 说明 |
|---------|------|
| **match_id** | 系统灵魂，一切数据围绕它组织 |
| **source_mapping_bridge** | 串联钥匙，连接各数据源的ID |
| **星型拓扑** | matches为中心，其他表通过match_id关联 |
| **数字ID原则** | 系统内部只使用数字ID，禁止队名匹配 |
| **历史不可变** | 完场数据只写一次，错误数据标记而非删除 |

这套设计确保了：
1. **数据一致性**: 唯一match_id确保数据不重复、不冲突
2. **数据可追溯**: 所有预测、赔率、统计都可追溯到具体比赛
3. **系统解耦**: 新增数据源只需写入桥接表，不影响现有逻辑
4. **高效查询**: 索引优化 + 缓存表确保查询性能
