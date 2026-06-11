# 球队动态爬虫汇总

## 已开发的爬虫

### 1. 新闻资讯爬虫 (`team_news_crawler.py`)

**数据源**: 直播吧 (zhibo8.cc)

**功能**:
- 爬取足球新闻列表
- 自动识别新闻类型 (伤病/停赛/转会/复出/主帅变动)
- 自动判断正负面 (利好/坏消息)
- 计算影响程度 (1-5级)
- 自动匹配球队ID

**使用**:
```bash
python d:\football_tools\backend\scripts\team_news_crawler.py
```

**入库数据**:
- 表: `team_news`
- 字段: team_id, title, news_type, category, impact_level, impact_type, news_date, source

---

### 2. 综合资讯爬虫 (`comprehensive_news_crawler.py`)

**数据源**:
- 直播吧新闻
- 188比分阵容预测
- apifootball API (可选)

**功能**:
- 多数据源整合
- 新闻去重
- 阵容预测入库

**使用**:
```bash
python d:\football_tools\backend\scripts\comprehensive_news_crawler.py
```

---

### 3. 赛前资讯爬虫 (`prematch_crawler.py`)

**数据源**:
- 直播吧比赛列表
- 188比分阵容预测
- 英超官方伤病名单
- 西甲官方伤病名单

**功能**:
- 获取今日比赛列表
- 爬取阵容预测
- 爬取官方伤病名单
- 更新球员状态

**使用**:
```bash
python d:\football_tools\backend\scripts\prematch_crawler.py
```

---

### 4. 定时任务脚本 (`scheduled_crawler.py`)

**功能**: 整合所有爬虫，支持按类型运行

**使用**:
```bash
# 运行所有爬虫
python d:\football_tools\backend\scripts\scheduled_crawler.py --type all

# 只运行新闻爬虫
python d:\football_tools\backend\scripts\scheduled_crawler.py --type news

# 只运行伤病爬虫
python d:\football_tools\backend\scripts\scheduled_crawler.py --type injury

# 只运行阵容爬虫
python d:\football_tools\backend\scripts\scheduled_crawler.py --type lineup
```

---

## 数据库表结构

### team_news 表
```sql
CREATE TABLE team_news (
    news_id INTEGER PRIMARY KEY,
    team_id INTEGER NOT NULL,
    title TEXT NOT NULL,
    content TEXT,
    news_type TEXT NOT NULL,      -- injury/suspension/transfer/return/coach/form/other
    category TEXT NOT NULL,       -- positive/negative/neutral
    impact_level INTEGER,         -- 1-5
    impact_type TEXT,             -- key_player_injury/star_player_return等
    affected_players TEXT,
    news_date DATE NOT NULL,
    source TEXT,
    verified INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### player_status 表
```sql
CREATE TABLE player_status (
    status_id INTEGER PRIMARY KEY,
    player_id INTEGER NOT NULL,
    team_id INTEGER NOT NULL,
    status TEXT NOT NULL,         -- available/injured/suspended/doubtful
    injury_type TEXT,
    expected_return DATE,
    appearance_probability REAL,
    team_impact_score REAL,
    source TEXT,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

---

## 新闻类型对照表

| news_type | 说明 | category |
|-----------|------|----------|
| injury | 伤病 | negative |
| suspension | 停赛 | negative |
| transfer | 转会 | positive/neutral |
| return | 复出 | positive |
| coach | 主帅变动 | positive/negative |
| form | 状态/战绩 | positive/negative |
| other | 其他 | neutral |

---

## 影响程度评分

| 级别 | 说明 | 触发关键词 |
|------|------|-----------|
| 5 | 极高影响 | 核心球员重伤、主力门将受伤 |
| 4 | 高影响 | 核心球员、主力、队长受伤 |
| 3 | 中等影响 | 重要球员、首发球员 |
| 2 | 一般影响 | 替补球员、轮换球员 |
| 1 | 轻微影响 | 边缘球员 |

---

## 定时任务配置

### Windows 任务计划程序

创建每日定时任务:
```batch
schtasks /create /tn "FootballNewsCrawler" /tr "python d:\football_tools\backend\scripts\scheduled_crawler.py --type all" /sc daily /st 08:00
```

### Linux Crontab

```bash
# 每天早上8点运行
0 8 * * * python /path/to/scheduled_crawler.py --type all

# 比赛前2小时更新阵容
0 */2 * * * python /path/to/scheduled_crawler.py --type lineup
```

---

## 当前数据统计

运行爬虫后的数据:
- team_news: 132条
- 其中利好消息: 17条
- 其中坏消息: 11条
- 伤病相关: 6条

---

## 注意事项

1. **代理设置**: 国内网站需要禁用代理，脚本已自动处理
2. **请求频率**: 避免过于频繁请求，建议间隔5秒以上
3. **数据去重**: 已实现标题+日期去重
4. **球队匹配**: 自动从标题中提取球队名称匹配team_id

---

## 后续优化

1. 添加更多数据源 (懂球帝API、足球报等)
2. 实现NLP自动分类新闻
3. 添加球员姓名识别和匹配
4. 实现实时推送功能