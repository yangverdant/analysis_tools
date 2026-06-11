# 体彩分析系统 - 企业级完整架构设计 v2.0

## 一、系统分层架构总览

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           5. 展示层 (API & Frontend)                         │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐              │
│  │ FastAPI Routers │  │ Pydantic Schema │  │ Vue3 Frontend   │              │
│  │ (路由接口)       │  │ (数据验证)       │  │ (前端组件)       │              │
│  └─────────────────┘  └─────────────────┘  └─────────────────┘              │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                           4. 模型层 (Prediction Models)                      │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐              │
│  │ BaseStatsModel  │  │ MarketModel     │  │ EnsembleMeta    │              │
│  │ (统计模型)       │  │ (盘口资金模型)   │  │ (集成元模型)     │              │
│  └─────────────────┘  └─────────────────┘  └─────────────────┘              │
│  ┌─────────────────┐                                                        │
│  │ ValueBetFinder  │  ← 对比体彩赔率，寻找价值下注点                          │
│  └─────────────────┘                                                        │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                     3. 特征层 (Feature Engineering)                          │
│                         【核心护城河 - 热插拔设计】                           │
│  ┌───────────────────────────────────────────────────────────────────────┐  │
│  │                    extractors_math (数学特征)                          │  │
│  │  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐    │  │
│  │  │Poisson   │ │ Elo      │ │ xG       │ │ Form     │ │ H2H      │    │  │
│  │  │Extractor │ │ Extractor│ │ Extractor│ │ Extractor│ │ Extractor│    │  │
│  │  └──────────┘ └──────────┘ └──────────┘ └──────────┘ └──────────┘    │  │
│  └───────────────────────────────────────────────────────────────────────┘  │
│  ┌───────────────────────────────────────────────────────────────────────┐  │
│  │                    extractors_tactics (战术特征)                        │  │
│  │  ┌──────────┐ ┌──────────┐ ┌──────────┐                               │  │
│  │  │Formation │ │ Control  │ │ Pressing │                               │  │
│  │  │Extractor │ │ Extractor│ │ Extractor│                               │  │
│  │  └──────────┘ └──────────┘ └──────────┘                               │  │
│  └───────────────────────────────────────────────────────────────────────┘  │
│  ┌───────────────────────────────────────────────────────────────────────┐  │
│  │                    extractors_context (上下文特征)                      │  │
│  │  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐    │  │
│  │  │Motivation│ │ Fatigue  │ │ Rivalry  │ │ Weather  │ │ Referee  │    │  │
│  │  │Extractor │ │ Extractor│ │ Extractor│ │ Extractor│ │ Extractor│    │  │
│  │  └──────────┘ └──────────┘ └──────────┘ └──────────┘ └──────────┘    │  │
│  └───────────────────────────────────────────────────────────────────────┘  │
│  ┌───────────────────────────────────────────────────────────────────────┐  │
│  │                    extractors_market (市场特征)                         │  │
│  │  ┌──────────┐ ┌──────────┐ ┌──────────┐                               │  │
│  │  │OddsMove  │ │ WaterDrop│ │ HotCold  │                               │  │
│  │  │Extractor │ │ Extractor│ │ Extractor│                               │  │
│  │  └──────────┘ └──────────┘ └──────────┘                               │  │
│  └───────────────────────────────────────────────────────────────────────┘  │
│  ┌───────────────────────────────────────────────────────────────────────┐  │
│  │                    llm_sentiment (AI情绪分析)                           │  │
│  │  ┌──────────────────────────────────────────────────────────────┐     │  │
│  │  │  DeepSeek/GPT → 新闻利好/利空情绪提取                          │     │  │
│  │  └──────────────────────────────────────────────────────────────┘     │  │
│  └───────────────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                     2. ETL清洗层 (ETL Pipeline)                              │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐              │
│  │ EntityMapper    │  │ DataCleaner     │  │ Loaders         │              │
│  │ (实体映射转换)   │  │ (数据清洗)       │  │ (数据加载)       │              │
│  │ 【核心:字段转换】 │  │                 │  │                 │              │
│  └─────────────────┘  └─────────────────┘  └─────────────────┘              │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                     1. 数据采集层 (Data Acquisition)                         │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │                       APIs (第三方API客户端)                          │    │
│  │  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐               │    │
│  │  │API-Football│ │Sportmonks│ │Odds API │ │TheSportsDB│               │    │
│  │  └──────────┘ └──────────┘ └──────────┘ └──────────┘               │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │                       Scrapers (爬虫模块)                             │    │
│  │  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐               │    │
│  │  │体彩官网   │ │FBref     │ │虎扑新闻   │ │微博舆情   │               │    │
│  │  │Crawler   │ │ Scraper  │ │ Crawler  │ │ Crawler  │               │    │
│  │  └──────────┘ └──────────┘ └──────────┘ └──────────┘               │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │                       故障切换机制 (Failover)                         │    │
│  │  ┌──────────────────────────────────────────────────────────────┐   │    │
│  │  │  数据源A失败 → 自动切换数据源B → 不影响整体系统运行             │   │    │
│  │  └──────────────────────────────────────────────────────────────┘   │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                     6. 闭环学习层 (Closed Loop)                              │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐              │
│  │ ResultValidator │  │ BrierScore      │  │ AutoTuner       │              │
│  │ (结果验证)       │  │ (布莱尔分数)     │  │ (自动权重优化)   │              │
│  └─────────────────┘  └─────────────────┘  └─────────────────┘              │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │                    预测 → 验证 → 优化 → 迭代 (无限闭环)               │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 二、核心设计原则

### 2.1 热插拔设计 (Hot-Pluggable)

```python
# 特征提取器注册表 - 支持运行时添加/删除

class FeatureExtractorRegistry:
    """特征提取器注册表 - 热插拔核心"""
    
    def __init__(self):
        self._extractors: Dict[str, FeatureExtractor] = {}
        self._weights: Dict[str, float] = {}
    
    def register(self, name: str, extractor: FeatureExtractor, weight: float = 1.0):
        """注册新的特征提取器 - 不影响已有提取器"""
        self._extractors[name] = extractor
        self._weights[name] = weight
    
    def unregister(self, name: str):
        """移除特征提取器 - 不影响其他提取器"""
        if name in self._extractors:
            del self._extractors[name]
            del self._weights[name]
    
    def get_features(self, context: AnalysisContext) -> Dict[str, Any]:
        """获取所有特征 - 每个提取器独立运行"""
        features = {}
        for name, extractor in self._extractors.items():
            try:
                features[name] = extractor.extract(context)
            except Exception as e:
                # 单个提取器失败不影响其他
                features[name] = {'error': str(e)}
        return features
```

**优势:**
- 新增分析器：只需register()，不影响现有分析
- 删除分析器：只需unregister()，其他分析继续工作
- 单个故障：异常隔离，不影响整体

### 2.2 数据源故障切换 (Failover)

```python
# 数据源管理器 - 自动故障切换

class DataSourceManager:
    """数据源管理器 - 多源冗余 + 自动切换"""
    
    def __init__(self):
        self._sources: Dict[str, List[DataSource]] = {}
        # 例如: 'fixtures' → [APIFootball, Sportmonks, TheSportsDB]
        self._source_status: Dict[str, str] = {}  # healthy/degraded/down
    
    def register_source(self, category: str, source: DataSource, priority: int = 10):
        """注册数据源 - 同一类数据可有多个来源"""
        if category not in self._sources:
            self._sources[category] = []
        self._sources[category].append((priority, source))
        self._sources[category].sort(key=lambda x: x[0])
    
    async def fetch(self, category: str, **params) -> Any:
        """获取数据 - 自动尝试所有来源"""
        sources = self._sources.get(category, [])
        errors = []
        
        for priority, source in sources:  # 按优先级排序
            try:
                result = await source.fetch(**params)
                self._source_status[source.name] = 'healthy'
                return result
            except Exception as e:
                errors.append((source.name, str(e)))
                self._source_status[source.name] = 'degraded'
                continue  # 自动切换到下一个数据源
        
        # 所有数据源都失败
        raise DataSourceError(f"All sources failed: {errors}")
```

**优势:**
- API-Football挂了 → 自动切换Sportmonks
- 数据源A字段变更 → 只需修改对应的Mapper
- 多数据源冗余，保证系统稳定

### 2.3 字段映射转换 (Field Mapping)

```python
# 实体映射器 - 统一不同数据源的字段差异

class EntityMapper:
    """
    实体映射器 - 数据源字段 → 系统标准字段
    
    解决问题:
    - API-Football返回 homeTeam.name
    - Sportmonks返回 home_team.name
    - 体彩官网返回 主队名称
    → 统一映射为系统标准字段 home_team_name
    """
    
    # 字段映射配置 (可配置化)
    FIELD_MAPPINGS = {
        'api_football': {
            'fixture.id': 'match_id',
            'fixture.date': 'match_date',
            'teams.home.name': 'home_team_name',
            'teams.away.name': 'away_team_name',
            'goals.home': 'home_goals',
            'goals.away': 'away_goals',
        },
        'sportmonks': {
            'id': 'match_id',
            'starting_at': 'match_datetime',
            'participants.0.name': 'home_team_name',  # 根据meta.location判断
            'participants.1.name': 'away_team_name',
            'score.home': 'home_goals',
            'score.away': 'away_goals',
        },
        'lottery': {
            'matchId': 'lottery_match_id',
            'homeTeam': 'home_team_cn',
            'awayTeam': 'away_team_cn',
            'matchDate': 'match_date',
            'matchTime': 'match_time',
        }
    }
    
    def map_to_standard(self, source_name: str, raw_data: Dict) -> Dict:
        """将任意数据源的数据转换为系统标准格式"""
        mapping = self.FIELD_MAPPINGS.get(source_name, {})
        standard_data = {}
        
        for source_path, target_field in mapping.items():
            value = self._get_nested_value(raw_data, source_path)
            if value is not None:
                standard_data[target_field] = value
        
        return standard_data
    
    def _get_nested_value(self, data: Dict, path: str) -> Any:
        """获取嵌套字段值"""
        keys = path.split('.')
        value = data
        for key in keys:
            if isinstance(value, dict):
                value = value.get(key)
            elif isinstance(value, list) and key.isdigit():
                value = value[int(key)]
            else:
                return None
        return value
```

**优势:**
- 新增数据源：只需添加字段映射配置
- 字段变更：只修改一处映射，不影响其他
- 数据格式统一：所有分析器使用标准字段

---

## 三、详细目录结构

```
d:\football_tools\
├── backend\
│   ├── app\
│   │   ├── core\                              # 核心基础设施
│   │   │   ├── __init__.py
│   │   │   ├── database.py                    # 数据库管理
│   │   │   ├── config.py                      # 配置管理
│   │   │   ├── exceptions.py                  # 异常定义
│   │   │   └── registry.py                    # 组件注册表
│   │   │
│   │   ├── lottery\                           # 体彩模块
│   │   │   ├── __init__.py
│   │   │   │
│   │   │   ├── routers\                       # 路由层
│   │   │   │   ├── __init__.py
│   │   │   │   ├── lottery.py                 # 体彩主路由
│   │   │   │   ├── analysis.py                # 分析路由
│   │   │   │   └── validation.py              # 验证路由
│   │   │   │
│   │   │   ├── services\                      # 服务层
│   │   │   │   ├── __init__.py
│   │   │   │   ├── lottery_service.py         # 体彩业务服务
│   │   │   │   ├── analysis_service.py        # 分析编排服务
│   │   │   │   ├── validation_service.py      # 结果验证服务
│   │   │   │   └── report_service.py          # 报告生成服务
│   │   │   │
│   │   │   ├── feature_extractors\            # 特征提取层 (热插拔)
│   │   │   │   ├── __init__.py
│   │   │   │   ├── registry.py                # 提取器注册表
│   │   │   │   ├── base.py                    # 提取器基类
│   │   │   │   │
│   │   │   │   ├── math\                      # 数学特征
│   │   │   │   │   ├── __init__.py
│   │   │   │   │   ├── poisson_extractor.py   # 泊松分布
│   │   │   │   │   ├── elo_extractor.py       # Elo评分
│   │   │   │   │   ├── xg_extractor.py        # 预期进球
│   │   │   │   │   ├── form_extractor.py      # 近期状态
│   │   │   │   │   └── h2h_extractor.py       # 交锋记录
│   │   │   │   │
│   │   │   │   ├── tactics\                   # 战术特征
│   │   │   │   │   ├── __init__.py
│   │   │   │   │   ├── formation_extractor.py # 阵型分析
│   │   │   │   │   ├── control_extractor.py   # 控球区域
│   │   │   │   │   └── pressing_extractor.py  # 施压强度
│   │   │   │   │
│   │   │   │   ├── context\                   # 上下文特征
│   │   │   │   │   ├── __init__.py
│   │   │   │   │   ├── motivation_extractor.py# 动机分析
│   │   │   │   │   ├── fatigue_extractor.py   # 疲劳分析
│   │   │   │   │   ├── rivalry_extractor.py   # 德比/敌对
│   │   │   │   │   ├── weather_extractor.py   # 天气影响
│   │   │   │   │   └── referee_extractor.py   # 裁判因素
│   │   │   │   │
│   │   │   │   ├── market\                    # 市场特征
│   │   │   │   │   ├── __init__.py
│   │   │   │   │   ├── odds_move_extractor.py # 赔率变动
│   │   │   │   │   ├── water_drop_extractor.py# 临场降水
│   │   │   │   │   └── hot_cold_extractor.py  # 冷热指数
│   │   │   │   │
│   │   │   │   └── llm\                       # AI分析
│   │   │   │       ├── __init__.py
│   │   │   │       └── sentiment_extractor.py # 情绪分析
│   │   │   │
│   │   │   ├── predictors\                    # 预测模型层
│   │   │   │   ├── __init__.py
│   │   │   │   ├── base_predictor.py          # 预测器基类
│   │   │   │   ├── spf_predictor.py           # 胜平负预测
│   │   │   │   ├── score_predictor.py         # 比分预测
│   │   │   │   ├── bqc_predictor.py           # 半全场预测
│   │   │   │   ├── handicap_predictor.py      # 让球预测
│   │   │   │   └── value_bet_finder.py        # 价值投注
│   │   │   │
│   │   │   ├── etl\                           # ETL层
│   │   │   │   ├── __init__.py
│   │   │   │   ├── entity_mapper.py           # 实体映射 (核心)
│   │   │   │   ├── field_mapping.py           # 字段映射配置
│   │   │   │   ├── data_cleaner.py            # 数据清洗
│   │   │   │   └── loaders\                   # 数据加载器
│   │   │   │       ├── __init__.py
│   │   │   │       ├── match_loader.py
│   │   │   │       └── odds_loader.py
│   │   │   │
│   │   │   ├── data_sources\                  # 数据采集层
│   │   │   │   ├── __init__.py
│   │   │   │   ├── source_manager.py          # 数据源管理 (故障切换)
│   │   │   │   ├── base_source.py             # 数据源基类
│   │   │   │   │
│   │   │   │   ├── apis\                      # API数据源
│   │   │   │   │   ├── __init__.py
│   │   │   │   │   ├── api_football.py
│   │   │   │   │   ├── sportmonks.py
│   │   │   │   │   └── odds_api.py
│   │   │   │   │
│   │   │   │   ├── scrapers\                  # 爬虫数据源
│   │   │   │   │   ├── __init__.py
│   │   │   │   │   ├── lottery_crawler.py     # 体彩官网
│   │   │   │   │   ├── fbref_scraper.py       # FBref
│   │   │   │   │   └── news_crawler.py        # 新闻爬虫
│   │   │   │   │
│   │   │   │   └── mappers\                   # 数据映射
│   │   │   │       ├── __init__.py
│   │   │   │       └── team_mapper.py         # 球队名称映射
│   │   │   │
│   │   │   ├── dao\                           # 数据访问层
│   │   │   │   ├── __init__.py
│   │   │   │   ├── base_dao.py
│   │   │   │   ├── lottery_match_dao.py
│   │   │   │   ├── lottery_odds_dao.py
│   │   │   │   ├── prediction_dao.py
│   │   │   │   └── validation_dao.py
│   │   │   │
│   │   │   ├── scheduler\                     # 调度层
│   │   │   │   ├── __init__.py
│   │   │   │   ├── scheduler_service.py
│   │   │   │   └── tasks.py
│   │   │   │
│   │   │   ├── closed_loop\                   # 闭环学习层
│   │   │   │   ├── __init__.py
│   │   │   │   ├── result_validator.py        # 结果验证
│   │   │   │   ├── brier_score.py             # 布莱尔分数
│   │   │   │   └── auto_tuner.py              # 自动权重优化
│   │   │   │
│   │   │   └── schemas\                       # 数据模型
│   │   │       ├── __init__.py
│   │   │       ├── lottery.py
│   │   │       ├── analysis.py
│   │   │       └── validation.py
│   │   │
│   │   └── ... (现有模块)
│   │
│   └── scripts\
│       ├── lottery_sync.py
│       └── scheduler_daemon.py
│
├── frontend\
│   └── src\
│       └── views\lottery\
│           ├── LotteryCenter.vue
│           ├── MatchList.vue
│           ├── AnalysisReport.vue
│           └── AccuracyTracker.vue
│
└── data\
    ├── football_v2.db
    └── lottery_config.json
```

---

## 四、核心代码设计

### 4.1 特征提取器基类与注册表

```python
# backend/app/lottery/feature_extractors/base.py

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
from dataclasses import dataclass
from enum import Enum


class FeatureCategory(str, Enum):
    """特征类别"""
    MATH = "math"           # 数学特征
    TACTICS = "tactics"     # 战术特征
    CONTEXT = "context"     # 上下文特征
    MARKET = "market"       # 市场特征
    LLM = "llm"             # AI分析


@dataclass
class ExtractionContext:
    """特征提取上下文"""
    match_id: Optional[int]
    home_team_id: Optional[int]
    away_team_id: Optional[int]
    league_id: Optional[int]
    match_date: str
    db_conn: Any
    
    # 体彩信息
    lottery_match_id: Optional[str] = None
    handicap_line: float = 0.0
    odds: Dict[str, Any] = None
    
    # 额外参数
    extra: Dict[str, Any] = None


@dataclass
class ExtractionResult:
    """特征提取结果"""
    feature_name: str
    category: FeatureCategory
    
    # 核心特征值
    value: float                           # 归一化特征值 [-1, 1]
    raw_data: Dict[str, Any]               # 原始数据
    
    # 元信息
    confidence: float = 1.0                # 置信度
    impact_direction: str = "neutral"      # positive/negative/neutral
    impact_magnitude: float = 0.0          # 影响幅度
    
    # 说明
    description: str = ""


class FeatureExtractor(ABC):
    """
    特征提取器基类
    
    设计原则:
    1. 单一职责: 每个提取器只负责一个特征维度
    2. 故障隔离: 单个提取器失败不影响其他
    3. 可配置: 权重、阈值等参数可配置
    4. 可观测: 输出详细的提取过程数据
    """
    
    def __init__(self, db_path: str, config: Dict = None):
        self.db_path = db_path
        self.config = config or {}
        self._initialized = False
    
    @property
    @abstractmethod
    def name(self) -> str:
        """提取器名称"""
        pass
    
    @property
    @abstractmethod
    def category(self) -> FeatureCategory:
        """特征类别"""
        pass
    
    @property
    def weight(self) -> float:
        """权重 (可被AutoTuner调整)"""
        return self.config.get('weight', 1.0)
    
    @weight.setter
    def weight(self, value: float):
        """设置权重 (AutoTuner调用)"""
        self.config['weight'] = value
    
    def initialize(self):
        """初始化 (可选实现)"""
        if not self._initialized:
            self._do_initialize()
            self._initialized = True
    
    def _do_initialize(self):
        """实际初始化逻辑"""
        pass
    
    @abstractmethod
    def extract(self, context: ExtractionContext) -> ExtractionResult:
        """
        提取特征
        
        注意: 子类必须实现此方法，且要处理异常
        """
        pass
    
    def validate_context(self, context: ExtractionContext) -> bool:
        """验证上下文是否满足提取条件"""
        return True
    
    def get_required_data(self) -> list:
        """返回所需的数据字段"""
        return []
```

```python
# backend/app/lottery/feature_extractors/registry.py

from typing import Dict, List, Any, Optional
import logging
from .base import FeatureExtractor, ExtractionContext, ExtractionResult, FeatureCategory

logger = logging.getLogger(__name__)


class FeatureExtractorRegistry:
    """
    特征提取器注册表
    
    核心功能:
    1. 热插拔: 运行时添加/移除提取器
    2. 故障隔离: 单个提取器失败不影响其他
    3. 分类管理: 按类别组织提取器
    4. 权重管理: 支持动态调整权重
    """
    
    def __init__(self, db_path: str):
        self.db_path = db_path
        self._extractors: Dict[str, FeatureExtractor] = {}
        self._categories: Dict[FeatureCategory, List[str]] = {
            cat: [] for cat in FeatureCategory
        }
        self._extraction_history: List[Dict] = []
    
    def register(self, extractor: FeatureExtractor, weight: float = None):
        """
        注册特征提取器
        
        Args:
            extractor: 提取器实例
            weight: 权重 (覆盖提取器默认权重)
        """
        name = extractor.name
        
        if name in self._extractors:
            logger.warning(f"Overwriting existing extractor: {name}")
        
        # 设置权重
        if weight is not None:
            extractor.weight = weight
        
        # 初始化
        extractor.initialize()
        
        # 注册
        self._extractors[name] = extractor
        self._categories[extractor.category].append(name)
        
        logger.info(f"Registered extractor: {name} (category={extractor.category.value}, weight={extractor.weight})")
    
    def unregister(self, name: str) -> bool:
        """
        移除特征提取器
        
        Returns:
            是否成功移除
        """
        if name not in self._extractors:
            return False
        
        extractor = self._extractors[name]
        category = extractor.category
        
        del self._extractors[name]
        self._categories[category].remove(name)
        
        logger.info(f"Unregistered extractor: {name}")
        return True
    
    def get_extractor(self, name: str) -> Optional[FeatureExtractor]:
        """获取提取器"""
        return self._extractors.get(name)
    
    def get_extractors_by_category(self, category: FeatureCategory) -> List[FeatureExtractor]:
        """按类别获取提取器"""
        return [
            self._extractors[name]
            for name in self._categories[category]
            if name in self._extractors
        ]
    
    def extract_all(self, context: ExtractionContext) -> Dict[str, ExtractionResult]:
        """
        执行所有特征提取
        
        设计:
        - 每个提取器独立运行
        - 单个失败不影响其他
        - 记录所有提取结果 (包括失败)
        """
        results = {}
        
        for name, extractor in self._extractors.items():
            try:
                # 验证上下文
                if not extractor.validate_context(context):
                    results[name] = ExtractionResult(
                        feature_name=name,
                        category=extractor.category,
                        value=0.0,
                        raw_data={},
                        confidence=0.0,
                        description="Context validation failed"
                    )
                    continue
                
                # 执行提取
                result = extractor.extract(context)
                results[name] = result
                
            except Exception as e:
                logger.error(f"Extractor {name} failed: {e}")
                results[name] = ExtractionResult(
                    feature_name=name,
                    category=extractor.category,
                    value=0.0,
                    raw_data={'error': str(e)},
                    confidence=0.0,
                    description=f"Extraction failed: {e}"
                )
        
        # 记录历史
        self._extraction_history.append({
            'match_id': context.match_id,
            'timestamp': datetime.now().isoformat(),
            'results': {k: v.value for k, v in results.items()}
        })
        
        return results
    
    def get_weights(self) -> Dict[str, float]:
        """获取所有提取器权重"""
        return {name: ext.weight for name, ext in self._extractors.items()}
    
    def update_weights(self, weights: Dict[str, float]):
        """
        更新提取器权重 (AutoTuner调用)
        
        Args:
            weights: {提取器名称: 新权重}
        """
        for name, weight in weights.items():
            if name in self._extractors:
                self._extractors[name].weight = weight
                logger.info(f"Updated weight for {name}: {weight}")
    
    def list_extractors(self) -> List[Dict]:
        """列出所有提取器信息"""
        return [
            {
                'name': name,
                'category': ext.category.value,
                'weight': ext.weight,
                'initialized': ext._initialized
            }
            for name, ext in self._extractors.items()
        ]
```

### 4.2 数据源管理器 (故障切换)

```python
# backend/app/lottery/data_sources/source_manager.py

from typing import Dict, List, Any, Optional, Type
from dataclasses import dataclass
from enum import Enum
import asyncio
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


class SourceStatus(str, Enum):
    """数据源状态"""
    HEALTHY = "healthy"       # 正常
    DEGRADED = "degraded"     # 降级
    DOWN = "down"             # 故障
    UNKNOWN = "unknown"       # 未知


@dataclass
class SourceHealth:
    """数据源健康状态"""
    name: str
    status: SourceStatus
    last_success: Optional[datetime]
    last_failure: Optional[datetime]
    failure_count: int
    success_rate: float       # 最近100次请求的成功率


class DataSourceManager:
    """
    数据源管理器
    
    核心功能:
    1. 多源冗余: 同一数据可有多个来源
    2. 自动切换: 主源失败自动切换备源
    3. 健康监控: 实时监控数据源状态
    4. 负载均衡: 可配置优先级和权重
    """
    
    def __init__(self):
        # 按数据类别组织的数据源
        # {category: [(priority, source), ...]}
        self._sources: Dict[str, List[tuple]] = {}
        
        # 数据源健康状态
        self._health: Dict[str, SourceHealth] = {}
        
        # 请求历史 (用于计算成功率)
        self._request_history: Dict[str, List[bool]] = {}
    
    def register_source(
        self,
        category: str,
        source: 'BaseDataSource',
        priority: int = 10
    ):
        """
        注册数据源
        
        Args:
            category: 数据类别 (fixtures/odds/news等)
            source: 数据源实例
            priority: 优先级 (数字越小越优先)
        """
        if category not in self._sources:
            self._sources[category] = []
        
        self._sources[category].append((priority, source))
        self._sources[category].sort(key=lambda x: x[0])
        
        # 初始化健康状态
        self._health[source.name] = SourceHealth(
            name=source.name,
            status=SourceStatus.UNKNOWN,
            last_success=None,
            last_failure=None,
            failure_count=0,
            success_rate=1.0
        )
        self._request_history[source.name] = []
        
        logger.info(f"Registered source: {source.name} for {category} (priority={priority})")
    
    async def fetch(
        self,
        category: str,
        params: Dict = None,
        prefer_source: str = None
    ) -> Any:
        """
        获取数据 (自动故障切换)
        
        Args:
            category: 数据类别
            params: 请求参数
            prefer_source: 首选数据源 (可选)
        
        Returns:
            数据结果
        
        Raises:
            DataSourceError: 所有数据源都失败时抛出
        """
        sources = self._sources.get(category, [])
        if not sources:
            raise DataSourceError(f"No sources registered for category: {category}")
        
        errors = []
        
        # 如果指定了首选数据源，先尝试它
        if prefer_source:
            sources = sorted(
                sources,
                key=lambda x: (0 if x[1].name == prefer_source else 1, x[0])
            )
        
        for priority, source in sources:
            # 检查健康状态
            health = self._health.get(source.name)
            if health and health.status == SourceStatus.DOWN:
                logger.warning(f"Skipping down source: {source.name}")
                continue
            
            try:
                result = await source.fetch(params or {})
                
                # 更新健康状态
                self._record_success(source.name)
                
                return result
                
            except Exception as e:
                # 记录失败
                self._record_failure(source.name)
                errors.append((source.name, str(e)))
                logger.warning(f"Source {source.name} failed: {e}")
                
                # 继续尝试下一个数据源
                continue
        
        # 所有数据源都失败
        raise DataSourceError(
            f"All sources failed for {category}",
            errors=errors
        )
    
    def _record_success(self, source_name: str):
        """记录成功"""
        health = self._health.get(source_name)
        if health:
            health.last_success = datetime.now()
            health.failure_count = 0
        
        self._request_history[source_name].append(True)
        self._update_success_rate(source_name)
        self._update_status(source_name)
    
    def _record_failure(self, source_name: str):
        """记录失败"""
        health = self._health.get(source_name)
        if health:
            health.last_failure = datetime.now()
            health.failure_count += 1
        
        self._request_history[source_name].append(False)
        self._update_success_rate(source_name)
        self._update_status(source_name)
    
    def _update_success_rate(self, source_name: str):
        """更新成功率"""
        history = self._request_history.get(source_name, [])
        if len(history) > 100:
            history = history[-100:]
            self._request_history[source_name] = history
        
        if history:
            success_rate = sum(history) / len(history)
            self._health[source_name].success_rate = success_rate
    
    def _update_status(self, source_name: str):
        """更新状态"""
        health = self._health.get(source_name)
        if not health:
            return
        
        if health.success_rate >= 0.95:
            health.status = SourceStatus.HEALTHY
        elif health.success_rate >= 0.7:
            health.status = SourceStatus.DEGRADED
        else:
            health.status = SourceStatus.DOWN
    
    def get_health_status(self) -> Dict[str, Dict]:
        """获取所有数据源健康状态"""
        return {
            name: {
                'status': health.status.value,
                'last_success': health.last_success.isoformat() if health.last_success else None,
                'last_failure': health.last_failure.isoformat() if health.last_failure else None,
                'failure_count': health.failure_count,
                'success_rate': health.success_rate
            }
            for name, health in self._health.items()
        }
    
    def get_sources_by_category(self, category: str) -> List[str]:
        """获取某类数据的所有数据源"""
        sources = self._sources.get(category, [])
        return [s[1].name for s in sources]


class DataSourceError(Exception):
    """数据源错误"""
    def __init__(self, message: str, errors: List[tuple] = None):
        super().__init__(message)
        self.errors = errors or []
```

### 4.3 实体映射器 (字段转换)

```python
# backend/app/lottery/etl/entity_mapper.py

from typing import Dict, Any, List, Optional
import json
import logging

logger = logging.getLogger(__name__)


class EntityMapper:
    """
    实体映射器
    
    核心功能:
    1. 字段映射: 不同数据源字段 → 系统标准字段
    2. 值转换: 数据类型转换、格式标准化
    3. 实体关联: 体彩名称 → 系统team_id
    4. 数据合并: 多源数据合并
    """
    
    # 字段映射配置 (从配置文件加载)
    FIELD_MAPPINGS = {
        # API-Football 数据源
        'api_football': {
            # 比赛数据
            'fixture.id': 'match_id',
            'fixture.date': 'match_date',
            'fixture.time': 'match_time',
            'fixture.status.short': 'status',
            'league.id': 'league_id',
            'league.name': 'league_name',
            'teams.home.id': 'home_team_id',
            'teams.home.name': 'home_team_name',
            'teams.away.id': 'away_team_id',
            'teams.away.name': 'away_team_name',
            'goals.home': 'home_goals',
            'goals.away': 'away_goals',
            'score.halftime.home': 'home_goals_ht',
            'score.halftime.away': 'away_goals_ht',
            
            # 统计数据
            'statistics.0.type': 'stat_type',
            'statistics.0.home': 'home_stat_value',
            'statistics.0.away': 'away_stat_value',
        },
        
        # Sportmonks 数据源
        'sportmonks': {
            'id': 'match_id',
            'starting_at': 'match_datetime',
            'result_info': 'result_info',
            'league_id': 'league_id',
            'season_id': 'season_id',
            # 参与者需要特殊处理 (根据location判断主客)
            'participants': '_participants_special',
            'scores.localteam_score': 'home_goals',
            'scores.visitorteam_score': 'away_goals',
        },
        
        # 体彩官网数据源
        'lottery': {
            'matchId': 'lottery_match_id',
            'matchNum': 'match_num',
            'homeTeam': 'home_team_cn',
            'awayTeam': 'away_team_cn',
            'leagueName': 'league_name_cn',
            'matchDate': 'match_date',
            'matchTime': 'match_time',
            'beijingTime': 'beijing_time',
            'sellStatus': 'sell_status',
            'sellEndTime': 'sell_end_time',
            'handicapLine': 'handicap_line',
            
            # 赔率数据
            'spfOdds': 'spf_odds',
            'bfOdds': 'bf_odds',
            'bqcOdds': 'bqc_odds',
            'rqspfOdds': 'rqspf_odds',
        },
        
        # FBref 数据源
        'fbref': {
            'match_id': 'match_id',
            'date': 'match_date',
            'home_team': 'home_team_name',
            'away_team': 'away_team_name',
            'home_goals': 'home_goals',
            'away_goals': 'away_goals',
            'home_xg': 'home_xg',
            'away_xg': 'away_xg',
        }
    }
    
    # 值转换器
    VALUE_CONVERTERS = {
        'match_date': lambda v: v[:10] if v else None,  # 截取日期部分
        'match_time': lambda v: v[11:16] if v and len(v) > 11 else v,  # 截取时间部分
        'sell_status': lambda v: {'on': 'selling', 'off': 'stopped'}.get(v, v),
        'home_goals': lambda v: int(v) if v is not None else None,
        'away_goals': lambda v: int(v) if v is not None else None,
    }
    
    def __init__(self, db_path: str, config: Dict = None):
        self.db_path = db_path
        self.config = config or {}
        
        # 球队名称映射缓存
        self._team_name_cache: Dict[str, int] = {}
        self._load_team_mappings()
    
    def map_to_standard(
        self,
        source_name: str,
        raw_data: Dict,
        extra_mappings: Dict = None
    ) -> Dict[str, Any]:
        """
        将任意数据源的数据转换为系统标准格式
        
        Args:
            source_name: 数据源名称
            raw_data: 原始数据
            extra_mappings: 额外的字段映射
        
        Returns:
            标准化后的数据
        """
        mapping = self.FIELD_MAPPINGS.get(source_name, {})
        if extra_mappings:
            mapping = {**mapping, **extra_mappings}
        
        result = {}
        
        for source_path, target_field in mapping.items():
            # 特殊处理
            if target_field.startswith('_') and target_field.endswith('_special'):
                special_result = self._handle_special_mapping(
                    source_name, source_path, raw_data
                )
                result.update(special_result)
                continue
            
            # 获取值
            value = self._get_nested_value(raw_data, source_path)
            
            if value is not None:
                # 值转换
                if target_field in self.VALUE_CONVERTERS:
                    value = self.VALUE_CONVERTERS[target_field](value)
                
                result[target_field] = value
        
        # 添加数据源标识
        result['_source'] = source_name
        
        return result
    
    def map_lottery_to_system(
        self,
        lottery_match: Dict,
        team_mapping: Dict[str, int] = None
    ) -> Dict[str, Any]:
        """
        体彩比赛数据 → 系统比赛数据
        
        包含球队名称映射
        """
        # 基础字段映射
        result = self.map_to_standard('lottery', lottery_match)
        
        # 球队名称映射
        home_team_cn = result.get('home_team_cn')
        away_team_cn = result.get('away_team_cn')
        
        if team_mapping:
            result['home_team_id'] = team_mapping.get(home_team_cn)
            result['away_team_id'] = team_mapping.get(away_team_cn)
        else:
            result['home_team_id'] = self._team_name_cache.get(home_team_cn)
            result['away_team_id'] = self._team_name_cache.get(away_team_cn)
        
        return result
    
    def merge_multi_source(
        self,
        sources_data: Dict[str, Dict]
    ) -> Dict[str, Any]:
        """
        合并多数据源数据
        
        策略:
        1. 按数据源优先级填充
        2. 冲突时保留最完整的值
        """
        merged = {}
        filled_fields = set()
        
        # 按优先级顺序 (可配置)
        source_priority = self.config.get('source_priority', [
            'api_football', 'sportmonks', 'fbref', 'lottery'
        ])
        
        for source_name in source_priority:
            if source_name not in sources_data:
                continue
            
            data = sources_data[source_name]
            if isinstance(data, dict):
                standardized = self.map_to_standard(source_name, data)
                
                for field, value in standardized.items():
                    if field not in filled_fields and value is not None:
                        merged[field] = value
                        filled_fields.add(field)
        
        return merged
    
    def _get_nested_value(self, data: Dict, path: str) -> Any:
        """获取嵌套字段值"""
        keys = path.split('.')
        value = data
        
        for key in keys:
            if value is None:
                return None
            
            if isinstance(value, dict):
                value = value.get(key)
            elif isinstance(value, list) and key.isdigit():
                idx = int(key)
                if 0 <= idx < len(value):
                    value = value[idx]
                else:
                    return None
            else:
                return None
        
        return value
    
    def _handle_special_mapping(
        self,
        source_name: str,
        path: str,
        data: Dict
    ) -> Dict:
        """处理特殊映射逻辑"""
        result = {}
        
        if source_name == 'sportmonks' and path == 'participants':
            # Sportmonks参与者特殊处理
            participants = data.get('participants', [])
            for p in participants:
                if p.get('meta', {}).get('location') == 'home':
                    result['home_team_id'] = p.get('id')
                    result['home_team_name'] = p.get('name')
                elif p.get('meta', {}).get('location') == 'away':
                    result['away_team_id'] = p.get('id')
                    result['away_team_name'] = p.get('name')
        
        return result
    
    def _load_team_mappings(self):
        """加载球队名称映射"""
        import sqlite3
        
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # 从映射表加载
            cursor.execute("""
                SELECT lottery_name, team_id FROM team_name_mapping
            """)
            
            for row in cursor.fetchall():
                self._team_name_cache[row[0]] = row[1]
            
            # 从teams表加载中文名
            cursor.execute("""
                SELECT name_cn, team_id FROM teams WHERE name_cn IS NOT NULL
            """)
            
            for row in cursor.fetchall():
                self._team_name_cache[row[0]] = row[1]
            
            conn.close()
            
            logger.info(f"Loaded {len(self._team_name_cache)} team mappings")
            
        except Exception as e:
            logger.error(f"Failed to load team mappings: {e}")
    
    def register_team_mapping(
        self,
        lottery_name: str,
        team_id: int,
        method: str = 'manual'
    ):
        """注册新的球队映射"""
        import sqlite3
        
        self._team_name_cache[lottery_name] = team_id
        
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute("""
                INSERT OR REPLACE INTO team_name_mapping
                (lottery_name, team_id, match_method, updated_at)
                VALUES (?, ?, ?, CURRENT_TIMESTAMP)
            """, (lottery_name, team_id, method))
            
            conn.commit()
            conn.close()
            
            logger.info(f"Registered team mapping: {lottery_name} -> {team_id}")
            
        except Exception as e:
            logger.error(f"Failed to register team mapping: {e}")
```

---

## 五、闭环学习设计

```python
# backend/app/lottery/closed_loop/auto_tuner.py

from typing import Dict, List, Any
import sqlite3
import logging
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class AutoTuner:
    """
    自动权重优化器
    
    核心功能:
    1. 计算各特征提取器的准确率
    2. 自动调整权重 (提升/降低)
    3. 支持回滚 (如果调整后效果变差)
    4. 记录调整历史
    """
    
    def __init__(
        self,
        db_path: str,
        registry: 'FeatureExtractorRegistry',
        config: Dict = None
    ):
        self.db_path = db_path
        self.registry = registry
        self.config = config or {
            'min_samples': 50,           # 最小样本量
            'adjustment_rate': 0.1,      # 调整幅度
            'max_weight': 2.0,           # 最大权重
            'min_weight': 0.1,           # 最小权重
            'rollback_threshold': 0.05   # 回滚阈值
        }
        
        self._adjustment_history: List[Dict] = []
    
    def tune_weights(self, days: int = 30) -> Dict[str, Any]:
        """
        执行权重优化
        
        流程:
        1. 计算各提取器的历史准确率
        2. 根据准确率调整权重
        3. 验证调整效果
        4. 必要时回滚
        """
        # 获取各提取器的验证结果
        extractor_stats = self._calculate_extractor_stats(days)
        
        adjustments = {}
        
        for name, stats in extractor_stats.items():
            if stats['sample_count'] < self.config['min_samples']:
                continue
            
            # 计算新权重
            current_weight = self.registry.get_extractor(name).weight
            accuracy = stats['accuracy']
            
            # 准确率 > 60%: 提升权重
            # 准确率 < 40%: 降低权重
            # 40-60%: 保持
            
            if accuracy > 0.6:
                adjustment = self.config['adjustment_rate']
            elif accuracy < 0.4:
                adjustment = -self.config['adjustment_rate']
            else:
                adjustment = 0
            
            new_weight = current_weight + adjustment
            
            # 限制范围
            new_weight = min(
                self.config['max_weight'],
                max(self.config['min_weight'], new_weight)
            )
            
            if new_weight != current_weight:
                adjustments[name] = {
                    'old_weight': current_weight,
                    'new_weight': new_weight,
                    'accuracy': accuracy,
                    'sample_count': stats['sample_count']
                }
        
        # 应用调整
        for name, adj in adjustments.items():
            self.registry.update_weights({name: adj['new_weight']})
        
        # 记录历史
        adjustment_record = {
            'timestamp': datetime.now().isoformat(),
            'adjustments': adjustments
        }
        self._adjustment_history.append(adjustment_record)
        
        # 保存到数据库
        self._save_adjustment_history(adjustments)
        
        logger.info(f"Tuned weights: {len(adjustments)} extractors adjusted")
        
        return {
            'adjusted': len(adjustments),
            'adjustments': adjustments
        }
    
    def _calculate_extractor_stats(self, days: int) -> Dict[str, Dict]:
        """计算各提取器的统计信息"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        stats = {}
        
        # 查询预测验证结果
        cursor.execute("""
            SELECT 
                p.model_details,
                v.is_correct,
                v.predicted_prob
            FROM lottery_predictions p
            JOIN lottery_validation v ON p.prediction_id = v.prediction_id
            WHERE v.validated_at >= date('now', ?)
        """, (f'-{days} days',))
        
        rows = cursor.fetchall()
        conn.close()
        
        # 按提取器统计
        extractor_results: Dict[str, List] = {}
        
        for row in rows:
            model_details = json.loads(row[0]) if row[0] else {}
            is_correct = row[1]
            predicted_prob = row[2]
            
            for ext_name, ext_value in model_details.get('features', {}).items():
                if ext_name not in extractor_results:
                    extractor_results[ext_name] = []
                
                extractor_results[ext_name].append({
                    'is_correct': is_correct,
                    'predicted_prob': predicted_prob,
                    'feature_value': ext_value
                })
        
        # 计算统计
        for name, results in extractor_results.items():
            correct = sum(1 for r in results if r['is_correct'])
            total = len(results)
            
            stats[name] = {
                'sample_count': total,
                'correct_count': correct,
                'accuracy': correct / total if total > 0 else 0
            }
        
        return stats
    
    def _save_adjustment_history(self, adjustments: Dict):
        """保存调整历史"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        for name, adj in adjustments.items():
            cursor.execute("""
                INSERT INTO weight_adjustment_history
                (extractor_name, old_weight, new_weight, accuracy, adjusted_at)
                VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
            """, (name, adj['old_weight'], adj['new_weight'], adj['accuracy']))
        
        conn.commit()
        conn.close()
    
    def rollback_last_adjustment(self) -> Dict:
        """回滚最近一次调整"""
        if not self._adjustment_history:
            return {'rolled_back': False, 'reason': 'No history'}
        
        last = self._adjustment_history[-1]
        rolled_back = {}
        
        for name, adj in last['adjustments'].items():
            # 恢复旧权重
            self.registry.update_weights({name: adj['old_weight']})
            rolled_back[name] = adj['old_weight']
        
        self._adjustment_history.pop()
        
        return {
            'rolled_back': True,
            'restored': rolled_back
        }
```

---

## 六、完整流水线执行

```python
# 一场比赛的完整生命周期

async def process_match_lifecycle(lottery_match_id: str):
    """
    处理单场比赛的完整生命周期
    
    时间线:
    06:00 - 数据采集
    09:00 - 特征提取
   赛前2h - 情报注入
   赛前30m - 最终预测
    赛后 - 结果验证
    次日 - 权重优化
    """
    
    # 1. 数据采集
    match_data = await source_manager.fetch(
        'lottery_match',
        {'match_id': lottery_match_id}
    )
    
    # 字段映射
    standardized = entity_mapper.map_to_standard('lottery', match_data)
    
    # 球队映射
    system_match = entity_mapper.map_lottery_to_system(match_data)
    
    # 2. 特征提取 (所有提取器并发)
    context = ExtractionContext(
        match_id=system_match.get('match_id'),
        home_team_id=system_match.get('home_team_id'),
        away_team_id=system_match.get('away_team_id'),
        match_date=system_match['match_date'],
        db_conn=db_conn
    )
    
    features = registry.extract_all(context)
    
    # 3. 预测生成
    prediction = predictor.predict(features)
    
    # 4. 价值投注计算
    value_bets = value_bet_finder.find(prediction, system_match['odds'])
    
    # 5. 保存预测
    prediction_dao.insert({
        'lottery_match_id': lottery_match_id,
        'prediction': prediction,
        'features': features,
        'value_bets': value_bets
    })
    
    # 6. 赛后验证 (定时任务)
    # result_validator.validate(lottery_match_id)
    
    # 7. 权重优化 (定时任务)
    # auto_tuner.tune_weights()
```

---

## 七、关键设计总结

| 设计原则 | 实现方式 | 效果 |
|---------|---------|------|
| **热插拔** | 注册表模式 + 依赖注入 | 新增/删除分析器不影响其他 |
| **故障切换** | 数据源管理器 + 健康监控 | 单源故障自动切换备源 |
| **字段映射** | 实体映射器 + 配置化 | 新数据源只需加映射配置 |
| **闭环学习** | AutoTuner + Brier Score | 自动优化模型权重 |
| **模块解耦** | 分层架构 + 接口抽象 | 各层独立开发测试 |
| **可观测性** | 详细日志 + 健康状态 | 便于监控和调试 |

这套架构搭建完成后，你就从一个"看数据猜比赛的球迷"，变成了一个"管理量化工厂的操盘手"。
