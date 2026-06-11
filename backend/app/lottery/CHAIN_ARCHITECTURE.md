# 体彩分析系统 - 完整串联架构

## 一、系统串联图

```
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                              用户请求流程                                            │
└─────────────────────────────────────────────────────────────────────────────────────┘

用户 → POST /api/v1/lottery/sync
       │
       ▼
┌─────────────────┐
│  Router 层      │  lottery.py
│  lottery.py     │  - 定义API接口
└────────┬────────┘  - 调用 BackgroundTasks
         │
         ▼
┌─────────────────┐
│  Service 层     │  sync_service.py
│  SyncService    │  - 编排整个同步流程
└────────┬────────┘
         │
    ┌────┴────┐
    ▼         ▼
┌────────┐ ┌────────┐
│Crawler │ │ Mapper │
│ 爬虫   │ │ 映射   │
└───┬────┘ └───┬────┘
    │          │
    └────┬─────┘
         ▼
┌─────────────────┐
│    DAO 层       │  lottery_dao.py
│ LotteryMatchDAO │  - 数据库CRUD操作
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│    Database     │  football_v2.db
│ lottery_matches │  - 体彩比赛表
└─────────────────┘


┌─────────────────────────────────────────────────────────────────────────────────────┐
│                              分析请求流程                                            │
└─────────────────────────────────────────────────────────────────────────────────────┘

用户 → POST /api/v1/lottery/analyze/{match_id}
       │
       ▼
┌─────────────────┐
│  Router 层      │
│  lottery.py     │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Service 层     │  analysis_service.py
│ AnalysisService │  - 编排整个分析流程
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│    Registry     │  registry.py
│  (提取器注册表)  │  - 管理所有提取器
└────────┬────────┘
         │
    ┌────┴────┬────────────┐
    ▼         ▼            ▼
┌────────┐ ┌────────┐ ┌────────┐
│  SPF   │ │ Score  │ │  BQC   │
│Analyzer│ │Predict │ │Analyzer│
└───┬────┘ └───┬────┘ └───┬────┘
    │          │          │
    └────┬─────┴──────────┘
         ▼
┌─────────────────┐
│ ExtractionCtx   │  - 分析上下文
│  (team_id等)    │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│    Database     │
│ matches, teams  │  - 查询历史数据
└─────────────────┘
         │
         ▼
┌─────────────────┐
│  ReportDAO      │  - 保存分析报告
│ lottery_reports │
└─────────────────┘
```

---

## 二、各层级职责与串联关系

### 1. Router 层 (`routers/lottery.py`)

**职责:**
- 定义API接口 (GET/POST)
- 参数验证
- 调用Service层
- 返回响应

**串联:**
```
Router → BackgroundTasks → Service
```

**关键代码:**
```python
@router.post("/sync")
async def sync_lottery_data(background_tasks: BackgroundTasks):
    background_tasks.add_task(run_sync_task)  # 调用服务层
```

### 2. Service 层 (`services/`)

**职责:**
- 编排业务流程
- 协调多个组件
- 异常处理
- 事务管理

**串联:**
```
SyncService → Crawler + Mapper + DAO
AnalysisService → Registry + Extractor + DAO
```

**关键代码:**
```python
class SyncService:
    def __init__(self, db_path):
        self.crawler = LotteryCrawlerSync()    # 爬虫
        self.mapper = EntityMapper(db_path)    # 映射器
        self.match_dao = LotteryMatchDAO(db_path)  # DAO

    def sync_daily_matches(self):
        # 1. 爬取
        raw_matches = self.crawler.crawl_matches_sync()
        # 2. 映射
        team_id = self.mapper.get_team_id(name)
        # 3. 入库
        self.match_dao.insert(match_data)
```

### 3. DAO 层 (`dao/lottery_dao.py`)

**职责:**
- 数据库CRUD操作
- SQL查询封装
- 事务管理

**串联:**
```
DAO → Database
```

**关键代码:**
```python
class LotteryMatchDAO:
    def insert(self, match: Dict) -> bool:
        cursor.execute("INSERT INTO lottery_matches ...")
        conn.commit()

    def find_by_id(self, lottery_match_id: str) -> Optional[Dict]:
        cursor.execute("SELECT * FROM lottery_matches WHERE ...")
        return dict(row) if row else None
```

### 4. ETL 层 (`etl/entity_mapper.py`)

**职责:**
- 字段映射 (不同数据源 → 标准字段)
- 球队名称映射 (体彩名 → team_id)
- 数据类型转换

**串联:**
```
Crawler → EntityMapper → DAO
```

**关键代码:**
```python
class EntityMapper:
    def map_to_standard(self, source_name, raw_data):
        # 字段映射
        mapping = FIELD_MAPPINGS[source_name]
        return {target: raw_data[source] for source, target in mapping}

    def get_team_id(self, lottery_name):
        # 球队映射
        return self._team_name_cache.get(lottery_name)
```

### 5. 特征提取层 (`feature_extractors/`)

**职责:**
- 单一职责: 每个提取器只负责一个特征
- 故障隔离: 单个失败不影响其他
- 热插拔: 可动态添加/移除

**串联:**
```
Registry → Extractor → Database
```

**关键代码:**
```python
class FeatureExtractorRegistry:
    def register(self, extractor):
        self._extractors[name] = extractor

    def extract_all(self, context):
        results = {}
        for name, extractor in self._extractors.items():
            try:
                results[name] = extractor.extract(context)
            except:
                results[name] = ExtractionResult(error=...)
        return results
```

### 6. 数据采集层 (`data_sources/scrapers/`)

**职责:**
- 从外部获取数据
- 请求限流
- 错误重试

**串联:**
```
SyncService → Crawler
```

---

## 三、数据流完整示例

### 示例: 同步今日比赛

```
1. 用户请求: POST /api/v1/lottery/sync

2. Router 接收:
   - 参数验证
   - 添加后台任务

3. 后台任务执行:
   run_sync_task()

4. SyncService.sync_daily_matches():
   │
   ├─► Crawler.crawl_matches_sync(today)
   │   └─► 返回: [{matchId, homeTeam, awayTeam, ...}, ...]
   │
   ├─► EntityMapper.get_team_id("曼联")
   │   └─► 返回: 585
   │
   ├─► LotteryMatchDAO.insert({
   │     lottery_match_id: "20260524001",
   │     home_team_id: 585,
   │     away_team_id: 561,
   │     ...
   │   })
   │
   └─► 数据写入 lottery_matches 表

5. 返回结果:
   {success: true, saved: 10}
```

### 示例: 分析比赛

```
1. 用户请求: POST /api/v1/lottery/analyze/20260524001

2. Router 接收:
   - 检查缓存 (ReportDAO.find_by_match)
   - 如果无缓存，添加后台任务

3. 后台任务执行:
   run_analysis_task("20260524001")

4. AnalysisService.analyze_match():
   │
   ├─► LotteryMatchDAO.find_by_id("20260524001")
   │   └─► 获取比赛信息
   │
   ├─► 构建分析上下文:
   │   context = ExtractionContext(
   │     home_team_id=585,
   │     away_team_id=561,
   │     db_conn=conn
   │   )
   │
   ├─► Registry.extract_all(context)
   │   │
   │   ├─► SPFAnalyzer.extract(context)
   │   │   ├─► 查询历史进球 (Database)
   │   │   ├─► 计算 Poisson 概率
   │   │   └─► 返回 ExtractionResult
   │   │
   │   └─► (其他分析器...)
   │
   ├─► 生成报告:
   │   report = {
   │     match_info: {...},
   │     analyses: {spf: {...}},
   │     recommendations: {...}
   │   }
   │
   └─► ReportDAO.insert(report)

5. 返回报告给用户
```

---

## 四、关键设计决策

### 1. 为什么用 Registry 而不是直接调用?

```python
# ❌ 错误: 直接调用，耦合度高
analyzer = SPFAnalyzer(db_path)
result = analyzer.extract(context)

# ✅ 正确: 通过 Registry，支持热插拔
registry.register(SPFAnalyzer(db_path))
registry.register(ScorePredictor(db_path))  # 新增分析器，不影响其他
results = registry.extract_all(context)  # 所有分析器独立执行
```

### 2. 为什么用 DAO 而不是直接 SQL?

```python
# ❌ 错误: SQL 散落在各处，难维护
cursor.execute("SELECT * FROM lottery_matches WHERE ...")

# ✅ 正确: 封装在 DAO，统一管理
match = match_dao.find_by_id(lottery_match_id)
```

### 3. 为什么用 EntityMapper?

```python
# 问题: 不同数据源字段名不同
api_football: {"teams": {"home": {"name": "Man United"}}}
sportmonks: {"participants": [{"name": "Manchester United"}]}
lottery: {"homeTeam": "曼联"}

# 解决: 统一映射
standardized = mapper.map_to_standard(source_name, raw_data)
# 结果: {"home_team_name": "Manchester United"}
```

---

## 五、当前实现状态

| 层级 | 文件 | 状态 | 说明 |
|------|------|------|------|
| Router | `routers/lottery.py` | ✅ 完成 | 13个API端点 |
| DAO | `dao/lottery_dao.py` | ✅ 完成 | 5个DAO类 |
| ETL | `etl/entity_mapper.py` | ✅ 完成 | 字段映射+球队映射 |
| Crawler | `scrapers/lottery_crawler.py` | ✅ 完成 | 需配置网络 |
| Service | `services/sync_service.py` | ✅ 完成 | 同步服务 |
| Service | `services/analysis_service.py` | ✅ 完成 | 分析服务 |
| Service | `services/scheduler_service.py` | ✅ 完成 | 调度服务 |
| Extractor | `math/spf_analyzer.py` | ✅ 完成 | SPF分析器 |
| Extractor | `math/score_predictor.py` | ⏳ 待实现 | 比分预测 |
| Extractor | `math/bqc_analyzer.py` | ⏳ 待实现 | 半全场 |
| Extractor | `math/handicap_analyzer.py` | ⏳ 待实现 | 让球分析 |
| Registry | `feature_extractors/registry.py` | ✅ 完成 | 热插拔核心 |
| Database | `data/football_v2.db` | ✅ 完成 | 10张新表 |

---

## 六、测试验证

运行测试脚本:
```bash
python backend/scripts/test_lottery_chain.py
```

预期输出:
- 数据库表检查通过
- DAO层CRUD测试通过
- EntityMapper映射测试通过
- Service层串联测试通过
- Router层API端点检查通过
