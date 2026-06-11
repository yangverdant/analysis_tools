# 体彩分析系统 - 完整代码架构设计

## 一、系统分层架构总览

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              表现层 (Presentation)                           │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐              │
│  │  Router/Controller │  │  Request/Response  │  │  Validation    │              │
│  │  (lottery.py)      │  │  (schemas.py)      │  │  (validators.py)│              │
│  └─────────────────┘  └─────────────────┘  └─────────────────┘              │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                              服务层 (Service)                                │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐              │
│  │ LotteryService   │  │ AnalysisService │  │ SchedulerService │              │
│  │ (业务编排)        │  │ (分析编排)       │  │ (任务调度)        │              │
│  └─────────────────┘  └─────────────────┘  └─────────────────┘              │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐              │
│  │ SyncService      │  │ ValidationService│  │ ReportService   │              │
│  │ (数据同步)        │  │ (结果验证)       │  │ (报告生成)       │              │
│  └─────────────────┘  └─────────────────┘  └─────────────────┘              │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                              业务逻辑层 (Business Logic)                     │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │                     分析器工厂 (AnalyzerFactory)                      │    │
│  │  ┌───────────┐ ┌───────────┐ ┌───────────┐ ┌───────────┐ ┌───────────┐│   │
│  │  │ SPFAnalyzer│ │ScorePredictor│ │BQCAnalyzer│ │HandicapAnalyzer│ │OUAnalyzer││   │
│  │  │(胜平负)    │ │(比分预测)   │ │(半全场)   │ │(让球分析)      │ │(大小球)  ││   │
│  │  └───────────┘ └───────────┘ └───────────┘ └───────────┘ └───────────┘│   │
│  └─────────────────────────────────────────────────────────────────────┘    │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │                     计算引擎 (CalculationEngine)                      │    │
│  │  ┌───────────┐ ┌───────────┐ ┌───────────┐ ┌───────────┐ ┌───────────┐│   │
│  │  │PoissonCalc │ │EloCalc    │ │XGCalc    │ │FormCalc   │ │ValueBetCalc││   │
│  │  │(泊松分布)  │ │(Elo评分)  │ │(预期进球) │ │(状态计算) │ │(价值计算)  ││   │
│  │  └───────────┘ └───────────┘ └───────────┘ └───────────┘ └───────────┘│   │
│  └─────────────────────────────────────────────────────────────────────┘    │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │                     上下文分析器 (ContextAnalyzer)                    │    │
│  │  ┌───────────┐ ┌───────────┐ ┌───────────┐ ┌───────────┐ ┌───────────┐│   │
│  │  │Motivation │ │NewsImpact │ │Fatigue    │ │Rivalry    │ │InjuryImpact││   │
│  │  │(动机分析) │ │(新闻影响) │ │(疲劳分析) │ │(敌对关系) │ │(伤病影响)  ││   │
│  │  └───────────┘ └───────────┘ └───────────┘ └───────────┘ └───────────┘│   │
│  └─────────────────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                              数据访问层 (DAO)                                │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐              │
│  │ LotteryMatchDAO │  │ LotteryOddsDAO  │  │ LotteryResultDAO │              │
│  │ (体彩比赛)       │  │ (体彩赔率)       │  │ (开奖结果)       │              │
│  └─────────────────┘  └─────────────────┘  └─────────────────┘              │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐              │
│  │ TeamMappingDAO  │  │ PredictionDAO   │  │ ValidationDAO   │              │
│  │ (球队映射)       │  │ (预测记录)       │  │ (验证结果)       │              │
│  └─────────────────┘  └─────────────────┘  └─────────────────┘              │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐              │
│  │ MatchDAO        │  │ TeamDAO         │  │ PlayerDAO       │              │
│  │ (比赛数据-现有)  │  │ (球队数据-现有)  │  │ (球员数据-现有)  │              │
│  └─────────────────┘  └─────────────────┘  └─────────────────┘              │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                              数据采集层 (Data Collection)                    │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐              │
│  │ LotteryCrawler  │  │ OddsCrawler     │  │ ResultCrawler   │              │
│  │ (体彩官网爬虫)   │  │ (赔率爬虫)       │  │ (开奖爬虫)       │              │
│  └─────────────────┘  └─────────────────┘  └─────────────────┘              │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐              │
│  │ NewsCrawler     │  │ InjuryCrawler   │  │ LineupCrawler   │              │
│  │ (新闻爬虫)       │  │ (伤病爬虫)       │  │ (阵容爬虫)       │              │
│  └─────────────────┘  └─────────────────┘  └─────────────────┘              │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                              基础设施层 (Infrastructure)                     │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐              │
│  │ DatabaseManager │  │ CacheManager    │  │ LogManager      │              │
│  │ (数据库管理)     │  │ (缓存管理)       │  │ (日志管理)       │              │
│  └─────────────────┘  └─────────────────┘  └─────────────────┘              │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐              │
│  │ ConfigManager   │  │ SchedulerManager│  │ MetricsManager  │              │
│  │ (配置管理)       │  │ (调度管理)       │  │ (指标管理)       │              │
│  └─────────────────┘  └─────────────────┘  └─────────────────┘              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 二、目录结构设计

```
d:\football_tools\
├── backend\
│   ├── app\
│   │   ├── lottery\                          # 体彩模块 (新增)
│   │   │   ├── __init__.py                   # 模块入口
│   │   │   │
│   │   │   ├── routers\                      # 路由层
│   │   │   │   ├── __init__.py
│   │   │   │   ├── lottery.py                # 体彩主路由
│   │   │   │   ├── analysis.py               # 分析路由
│   │   │   │   ├── sync.py                   # 同步路由
│   │   │   │   └── validation.py             # 验证路由
│   │   │   │
│   │   │   ├── schemas\                      # 数据模型层
│   │   │   │   ├── __init__.py
│   │   │   │   ├── request.py                # 请求模型
│   │   │   │   ├── response.py               # 响应模型
│   │   │   │   ├── lottery.py                # 体彩数据模型
│   │   │   │   └── analysis.py               # 分析数据模型
│   │   │   │
│   │   │   ├── services\                     # 服务层
│   │   │   │   ├── __init__.py
│   │   │   │   ├── lottery_service.py        # 体彩业务服务
│   │   │   │   ├── analysis_service.py       # 分析编排服务
│   │   │   │   ├── sync_service.py           # 数据同步服务
│   │   │   │   ├── validation_service.py     # 结果验证服务
│   │   │   │   └── report_service.py         # 报告生成服务
│   │   │   │
│   │   │   ├── analyzers\                    # 分析器层
│   │   │   │   ├── __init__.py
│   │   │   │   ├── base.py                   # 分析器基类
│   │   │   │   ├── factory.py                # 分析器工厂
│   │   │   │   │
│   │   │   │   ├── outcomes\                 # 结果预测分析器
│   │   │   │   │   ├── __init__.py
│   │   │   │   │   ├── spf_analyzer.py       # 胜平负分析
│   │   │   │   │   ├── score_predictor.py    # 比分预测
│   │   │   │   │   ├── bqc_analyzer.py       # 半全场分析
│   │   │   │   │   ├── handicap_analyzer.py  # 让球分析
│   │   │   │   │   └── over_under_analyzer.py# 大小球分析
│   │   │   │   │
│   │   │   │   ├── calculations\             # 计算引擎
│   │   │   │   │   ├── __init__.py
│   │   │   │   │   ├── poisson_calc.py       # 泊松分布计算
│   │   │   │   │   ├── elo_calc.py           # Elo评分计算
│   │   │   │   │   ├── xg_calc.py            # 预期进球计算
│   │   │   │   │   ├── form_calc.py          # 状态评分计算
│   │   │   │   │   └── value_bet_calc.py     # 价值投注计算
│   │   │   │   │
│   │   │   │   └── context\                  # 上下文分析器
│   │   │   │       ├── __init__.py
│   │   │   │       ├── motivation_analyzer.py# 动机分析
│   │   │   │       ├── news_impact.py        # 新闻影响分析
│   │   │   │       ├── fatigue_analyzer.py   # 疲劳分析
│   │   │   │       ├── rivalry_analyzer.py   # 敌对关系分析
│   │   │   │       └── injury_impact.py      # 伤病影响分析
│   │   │   │
│   │   │   ├── dao\                          # 数据访问层
│   │   │   │   ├── __init__.py
│   │   │   │   ├── base.py                   # DAO基类
│   │   │   │   ├── lottery_match_dao.py      # 体彩比赛DAO
│   │   │   │   ├── lottery_odds_dao.py       # 体彩赔率DAO
│   │   │   │   ├── lottery_result_dao.py     # 开奖结果DAO
│   │   │   │   ├── prediction_dao.py         # 预测记录DAO
│   │   │   │   ├── validation_dao.py         # 验证结果DAO
│   │   │   │   └── team_mapping_dao.py       # 球队映射DAO
│   │   │   │
│   │   │   ├── crawlers\                     # 爬虫层
│   │   │   │   ├── __init__.py
│   │   │   │   ├── base.py                   # 爬虫基类
│   │   │   │   ├── lottery_crawler.py        # 体彩官网爬虫
│   │   │   │   ├── odds_crawler.py           # 赔率爬虫
│   │   │   │   ├── result_crawler.py         # 开奖爬虫
│   │   │   │   └── team_mapper.py            # 球队名称映射
│   │   │   │
│   │   │   ├── scheduler\                    # 调度层
│   │   │   │   ├── __init__.py
│   │   │   │   ├── task_manager.py           # 任务管理器
│   │   │   │   ├── lottery_tasks.py          # 体彩定时任务
│   │   │   │   └── scheduler_service.py      # 调度服务
│   │   │   │
│   │   │   └── utils\                        # 工具层
│   │   │       ├── __init__.py
│   │   │       ├── validators.py             # 数据验证
│   │   │       ├── converters.py             # 数据转换
│   │   │       └── constants.py              # 常量定义
│   │   │
│   │   ├── core\                             # 核心基础设施 (新增)
│   │   │   ├── __init__.py
│   │   │   ├── database.py                   # 数据库管理
│   │   │   ├── cache.py                      # 缓存管理
│   │   │   ├── config.py                     # 配置管理
│   │   │   ├── logging.py                    # 日志管理
│   │   │   └── metrics.py                    # 指标管理
│   │   │
│   │   └── ... (现有模块)
│   │
│   └── scripts\
│       ├── lottery_sync.py                   # 体彩同步脚本
│       └── scheduler_daemon.py               # 调度守护进程
│
├── frontend\
│   └── src\
│       └── views\
│           └── lottery\                      # 体彩前端 (新增)
│               ├── LotteryCenter.vue         # 体彩中心
│               ├── LotteryMatchList.vue      # 比赛列表
│               ├── LotteryMatchDetail.vue    # 比赛详情
│               ├── AnalysisReport.vue        # 分析报告
│               └── AccuracyTracker.vue       # 准确率追踪
│
└── data\
    ├── football_v2.db                        # 数据库
    └── lottery_config.json                   # 体彩配置
```

---

## 三、核心接口设计

### 3.1 分析器接口 (Analyzer Interface)

```python
# backend/app/lottery/analyzers/base.py

from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from enum import Enum


class PlayType(str, Enum):
    """体彩玩法类型"""
    SPF = "spf"           # 胜平负
    BF = "bf"             # 比分
    BQC = "bqc"           # 半全场
    RQSPF = "rqspf"       # 让球胜平负
    OVER_UNDER = "ou"     # 大小球


class AnalysisType(str, Enum):
    """分析类型"""
    DATA_DRIVEN = "data_driven"      # 数据驱动 (SQL查询)
    CALCULATION = "calculation"       # 计算驱动 (数学模型)
    CONTEXT = "context"               # 上下文驱动 (思考分析)
    HYBRID = "hybrid"                 # 混合分析


@dataclass
class AnalysisContext:
    """分析上下文 - 包含分析所需的所有数据"""
    # 比赛基础信息
    lottery_match_id: str
    home_team_id: Optional[int]
    away_team_id: Optional[int]
    home_team_cn: str
    away_team_cn: str
    match_date: str
    match_time: Optional[str]
    league_id: Optional[int]
    
    # 体彩信息
    play_types: List[PlayType]
    handicap_line: float = 0.0
    
    # 赔率信息
    odds: Dict[str, Any] = None
    
    # 数据库连接
    db_conn: Any = None
    
    # 额外参数
    extra: Dict[str, Any] = None


@dataclass
class AnalysisResult:
    """分析结果"""
    play_type: PlayType
    analysis_type: AnalysisType
    
    # 预测结果
    predictions: Dict[str, float]      # 各选项概率
    recommendation: str                 # 推荐选项
    confidence: float                   # 置信度 0-1
    confidence_level: str               # high/medium/low
    
    # 价值投注
    value_bets: List[Dict]              # 价值投注列表
    
    # 分析详情
    details: Dict[str, Any]             # 详细分析数据
    
    # 元信息
    model_version: str = "1.0"
    analysis_time: str = None


class BaseAnalyzer(ABC):
    """分析器基类"""
    
    def __init__(self, db_path: str, config: Dict = None):
        self.db_path = db_path
        self.config = config or {}
        self._init_dependencies()
    
    @property
    @abstractmethod
    def name(self) -> str:
        """分析器名称"""
        pass
    
    @property
    @abstractmethod
    def play_type(self) -> PlayType:
        """支持的玩法类型"""
        pass
    
    @property
    @abstractmethod
    def analysis_type(self) -> AnalysisType:
        """分析类型"""
        pass
    
    @abstractmethod
    def analyze(self, context: AnalysisContext) -> AnalysisResult:
        """执行分析"""
        pass
    
    def _init_dependencies(self):
        """初始化依赖 (依赖注入)"""
        pass
    
    def validate_context(self, context: AnalysisContext) -> bool:
        """验证上下文是否满足分析条件"""
        return True


class DataDrivenAnalyzer(BaseAnalyzer):
    """数据驱动分析器基类 - 基于SQL查询"""
    
    @property
    def analysis_type(self) -> AnalysisType:
        return AnalysisType.DATA_DRIVEN
    
    @abstractmethod
    def get_analysis_queries(self) -> Dict[str, str]:
        """返回分析所需的SQL查询"""
        pass
    
    def execute_queries(self, context: AnalysisContext) -> Dict[str, Any]:
        """执行SQL查询"""
        results = {}
        queries = self.get_analysis_queries()
        cursor = context.db_conn.cursor()
        
        for name, query in queries.items():
            cursor.execute(query, self._get_query_params(context, name))
            results[name] = cursor.fetchall()
        
        return results
    
    @abstractmethod
    def _get_query_params(self, context: AnalysisContext, query_name: str) -> tuple:
        """获取查询参数"""
        pass


class CalculationAnalyzer(BaseAnalyzer):
    """计算驱动分析器基类 - 基于数学模型"""
    
    @property
    def analysis_type(self) -> AnalysisType:
        return AnalysisType.CALCULATION
    
    @abstractmethod
    def get_required_data(self) -> List[str]:
        """返回计算所需的数据字段"""
        pass
    
    @abstractmethod
    def calculate(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """执行计算"""
        pass


class ContextAnalyzer(BaseAnalyzer):
    """上下文分析器基类 - 基于思考分析"""
    
    @property
    def analysis_type(self) -> AnalysisType:
        return AnalysisType.CONTEXT
    
    @abstractmethod
    def gather_context(self, context: AnalysisContext) -> Dict[str, Any]:
        """收集上下文信息"""
        pass
    
    @abstractmethod
    def evaluate_impact(self, context_data: Dict[str, Any]) -> Dict[str, Any]:
        """评估影响"""
        pass
```

### 3.2 分析器工厂 (Analyzer Factory)

```python
# backend/app/lottery/analyzers/factory.py

from typing import Dict, List, Type, Optional
from .base import BaseAnalyzer, PlayType, AnalysisType
from .outcomes import (
    SPFAnalyzer, ScorePredictor, BQCAnalyzer,
    HandicapAnalyzer, OverUnderAnalyzer
)
from .calculations import (
    PoissonCalculator, EloCalculator, XGCalculator,
    FormCalculator, ValueBetCalculator
)
from .context import (
    MotivationAnalyzer, NewsImpactAnalyzer,
    FatigueAnalyzer, RivalryAnalyzer, InjuryImpactAnalyzer
)


class AnalyzerFactory:
    """分析器工厂 - 创建和管理分析器实例"""
    
    # 注册的分析器类
    _outcome_analyzers: Dict[PlayType, Type[BaseAnalyzer]] = {
        PlayType.SPF: SPFAnalyzer,
        PlayType.BF: ScorePredictor,
        PlayType.BQC: BQCAnalyzer,
        PlayType.RQSPF: HandicapAnalyzer,
        PlayType.OVER_UNDER: OverUnderAnalyzer,
    }
    
    _calculation_engines: Dict[str, Type] = {
        'poisson': PoissonCalculator,
        'elo': EloCalculator,
        'xg': XGCalculator,
        'form': FormCalculator,
        'value_bet': ValueBetCalculator,
    }
    
    _context_analyzers: Dict[str, Type] = {
        'motivation': MotivationAnalyzer,
        'news_impact': NewsImpactAnalyzer,
        'fatigue': FatigueAnalyzer,
        'rivalry': RivalryAnalyzer,
        'injury': InjuryImpactAnalyzer,
    }
    
    def __init__(self, db_path: str, config: Dict = None):
        self.db_path = db_path
        self.config = config or {}
        
        # 缓存实例
        self._instances: Dict[str, BaseAnalyzer] = {}
        self._calc_instances: Dict[str, Any] = {}
        self._context_instances: Dict[str, Any] = {}
    
    def get_outcome_analyzer(self, play_type: PlayType) -> BaseAnalyzer:
        """获取结果预测分析器"""
        key = f"outcome_{play_type.value}"
        
        if key not in self._instances:
            analyzer_class = self._outcome_analyzers.get(play_type)
            if analyzer_class:
                self._instances[key] = analyzer_class(
                    self.db_path, 
                    self._get_analyzer_config(play_type)
                )
        
        return self._instances.get(key)
    
    def get_calculation_engine(self, name: str) -> Any:
        """获取计算引擎"""
        if name not in self._calc_instances:
            engine_class = self._calculation_engines.get(name)
            if engine_class:
                self._calc_instances[name] = engine_class(self.db_path)
        
        return self._calc_instances.get(name)
    
    def get_context_analyzer(self, name: str) -> Any:
        """获取上下文分析器"""
        if name not in self._context_instances:
            analyzer_class = self._context_analyzers.get(name)
            if analyzer_class:
                self._context_instances[name] = analyzer_class(self.db_path)
        
        return self._context_instances.get(name)
    
    def get_all_outcome_analyzers(self) -> Dict[PlayType, BaseAnalyzer]:
        """获取所有结果预测分析器"""
        return {
            play_type: self.get_outcome_analyzer(play_type)
            for play_type in self._outcome_analyzers.keys()
        }
    
    def get_all_context_analyzers(self) -> Dict[str, Any]:
        """获取所有上下文分析器"""
        return {
            name: self.get_context_analyzer(name)
            for name in self._context_analyzers.keys()
        }
    
    def _get_analyzer_config(self, play_type: PlayType) -> Dict:
        """获取分析器配置"""
        return self.config.get('analyzers', {}).get(play_type.value, {})
    
    def register_analyzer(self, play_type: PlayType, analyzer_class: Type[BaseAnalyzer]):
        """注册新的分析器 (扩展点)"""
        self._outcome_analyzers[play_type] = analyzer_class
    
    def register_calculation_engine(self, name: str, engine_class: Type):
        """注册新的计算引擎 (扩展点)"""
        self._calculation_engines[name] = engine_class
    
    def register_context_analyzer(self, name: str, analyzer_class: Type):
        """注册新的上下文分析器 (扩展点)"""
        self._context_analyzers[name] = analyzer_class
```

### 3.3 DAO接口 (Data Access Object)

```python
# backend/app/lottery/dao/base.py

from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any, TypeVar, Generic
from dataclasses import dataclass
import sqlite3

T = TypeVar('T')


@dataclass
class QueryOptions:
    """查询选项"""
    filters: Dict[str, Any] = None
    order_by: str = None
    limit: int = None
    offset: int = None


class BaseDAO(ABC, Generic[T]):
    """DAO基类"""
    
    def __init__(self, db_path: str):
        self.db_path = db_path
    
    @property
    @abstractmethod
    def table_name(self) -> str:
        """表名"""
        pass
    
    @abstractmethod
    def from_row(self, row: sqlite3.Row) -> T:
        """从数据库行转换为实体"""
        pass
    
    @abstractmethod
    def to_params(self, entity: T) -> Dict[str, Any]:
        """实体转换为参数"""
        pass
    
    def get_connection(self) -> sqlite3.Connection:
        """获取数据库连接"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn
    
    def find_by_id(self, id: Any) -> Optional[T]:
        """根据ID查找"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute(
            f"SELECT * FROM {self.table_name} WHERE {self._get_pk_column()} = ?",
            (id,)
        )
        row = cursor.fetchone()
        conn.close()
        
        return self.from_row(row) if row else None
    
    def find_all(self, options: QueryOptions = None) -> List[T]:
        """查找所有"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        query = f"SELECT * FROM {self.table_name}"
        params = []
        
        if options and options.filters:
            where_clause, params = self._build_where(options.filters)
            query += f" WHERE {where_clause}"
        
        if options and options.order_by:
            query += f" ORDER BY {options.order_by}"
        
        if options and options.limit:
            query += f" LIMIT {options.limit}"
            if options.offset:
                query += f" OFFSET {options.offset}"
        
        cursor.execute(query, params)
        rows = cursor.fetchall()
        conn.close()
        
        return [self.from_row(row) for row in rows]
    
    def insert(self, entity: T) -> int:
        """插入"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        params = self.to_params(entity)
        columns = ', '.join(params.keys())
        placeholders = ', '.join(['?' for _ in params])
        
        cursor.execute(
            f"INSERT INTO {self.table_name} ({columns}) VALUES ({placeholders})",
            list(params.values())
        )
        
        last_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        return last_id
    
    def update(self, entity: T, id: Any) -> bool:
        """更新"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        params = self.to_params(entity)
        set_clause = ', '.join([f"{k} = ?" for k in params.keys()])
        
        cursor.execute(
            f"UPDATE {self.table_name} SET {set_clause} WHERE {self._get_pk_column()} = ?",
            list(params.values()) + [id]
        )
        
        success = cursor.rowcount > 0
        conn.commit()
        conn.close()
        
        return success
    
    def delete(self, id: Any) -> bool:
        """删除"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute(
            f"DELETE FROM {self.table_name} WHERE {self._get_pk_column()} = ?",
            (id,)
        )
        
        success = cursor.rowcount > 0
        conn.commit()
        conn.close()
        
        return success
    
    def _get_pk_column(self) -> str:
        """获取主键列名"""
        return "id"
    
    def _build_where(self, filters: Dict[str, Any]) -> tuple:
        """构建WHERE子句"""
        conditions = []
        params = []
        
        for key, value in filters.items():
            if value is not None:
                conditions.append(f"{key} = ?")
                params.append(value)
        
        return ' AND '.join(conditions), params
```

### 3.4 服务层接口 (Service Layer)

```python
# backend/app/lottery/services/analysis_service.py

from typing import Dict, List, Optional
from dataclasses import dataclass
from datetime import datetime

from ..analyzers.factory import AnalyzerFactory
from ..analyzers.base import AnalysisContext, AnalysisResult, PlayType
from ..dao import (
    LotteryMatchDAO, LotteryOddsDAO, 
    PredictionDAO, TeamMappingDAO
)


@dataclass
class FullAnalysisResult:
    """完整分析结果"""
    lottery_match_id: str
    match_info: Dict
    analyses: Dict[PlayType, AnalysisResult]
    context_impacts: Dict[str, Any]
    summary: Dict
    generated_at: datetime
    
    def to_dict(self) -> Dict:
        """转换为字典"""
        return {
            'lottery_match_id': self.lottery_match_id,
            'match_info': self.match_info,
            'analyses': {
                pt.value: result.__dict__ 
                for pt, result in self.analyses.items()
            },
            'context_impacts': self.context_impacts,
            'summary': self.summary,
            'generated_at': self.generated_at.isoformat()
        }


class AnalysisService:
    """分析服务 - 编排分析流程"""
    
    def __init__(self, db_path: str, config: Dict = None):
        self.db_path = db_path
        self.config = config or {}
        
        # 初始化工厂
        self.analyzer_factory = AnalyzerFactory(db_path, config)
        
        # 初始化DAO
        self.match_dao = LotteryMatchDAO(db_path)
        self.odds_dao = LotteryOddsDAO(db_path)
        self.prediction_dao = PredictionDAO(db_path)
        self.team_mapping_dao = TeamMappingDAO(db_path)
    
    def analyze_match(
        self, 
        lottery_match_id: str,
        play_types: List[PlayType] = None,
        include_context: bool = True,
        force_refresh: bool = False
    ) -> FullAnalysisResult:
        """
        分析单场比赛
        
        Args:
            lottery_match_id: 体彩比赛ID
            play_types: 要分析的玩法列表，None表示全部
            include_context: 是否包含上下文分析
            force_refresh: 是否强制刷新缓存
        """
        # 1. 获取比赛信息
        match = self.match_dao.find_by_id(lottery_match_id)
        if not match:
            raise ValueError(f"Match not found: {lottery_match_id}")
        
        # 2. 获取赔率信息
        odds = self.odds_dao.find_by_match(lottery_match_id)
        
        # 3. 构建分析上下文
        context = self._build_context(match, odds)
        
        # 4. 确定要分析的玩法
        if play_types is None:
            play_types = [PlayType(pt) for pt in match.play_types]
        
        # 5. 执行各玩法分析
        analyses = {}
        for play_type in play_types:
            analyzer = self.analyzer_factory.get_outcome_analyzer(play_type)
            if analyzer:
                analyses[play_type] = analyzer.analyze(context)
        
        # 6. 执行上下文分析
        context_impacts = {}
        if include_context:
            context_impacts = self._analyze_context(context)
        
        # 7. 生成汇总
        summary = self._generate_summary(analyses, context_impacts)
        
        # 8. 保存预测记录
        self._save_predictions(lottery_match_id, analyses)
        
        return FullAnalysisResult(
            lottery_match_id=lottery_match_id,
            match_info=self._match_to_dict(match),
            analyses=analyses,
            context_impacts=context_impacts,
            summary=summary,
            generated_at=datetime.now()
        )
    
    def batch_analyze(
        self,
        match_ids: List[str],
        play_types: List[PlayType] = None
    ) -> List[FullAnalysisResult]:
        """批量分析多场比赛"""
        results = []
        for match_id in match_ids:
            try:
                result = self.analyze_match(match_id, play_types)
                results.append(result)
            except Exception as e:
                results.append({
                    'lottery_match_id': match_id,
                    'error': str(e)
                })
        return results
    
    def _build_context(
        self, 
        match: Any, 
        odds: Dict
    ) -> AnalysisContext:
        """构建分析上下文"""
        # 球队映射
        home_team_id = self.team_mapping_dao.get_team_id(match.home_team_cn)
        away_team_id = self.team_mapping_dao.get_team_id(match.away_team_cn)
        
        return AnalysisContext(
            lottery_match_id=match.lottery_match_id,
            home_team_id=home_team_id,
            away_team_id=away_team_id,
            home_team_cn=match.home_team_cn,
            away_team_cn=match.away_team_cn,
            match_date=match.match_date,
            match_time=match.match_time,
            league_id=match.league_id,
            play_types=[PlayType(pt) for pt in match.play_types],
            handicap_line=match.handicap_line,
            odds=odds,
            db_conn=self.match_dao.get_connection()
        )
    
    def _analyze_context(self, context: AnalysisContext) -> Dict[str, Any]:
        """执行上下文分析"""
        impacts = {}
        
        # 获取所有上下文分析器
        context_analyzers = self.analyzer_factory.get_all_context_analyzers()
        
        for name, analyzer in context_analyzers.items():
            try:
                # 收集上下文
                context_data = analyzer.gather_context(context)
                # 评估影响
                impact = analyzer.evaluate_impact(context_data)
                impacts[name] = impact
            except Exception as e:
                impacts[name] = {'error': str(e)}
        
        return impacts
    
    def _generate_summary(
        self,
        analyses: Dict[PlayType, AnalysisResult],
        context_impacts: Dict[str, Any]
    ) -> Dict:
        """生成汇总"""
        summary = {
            'recommendations': {},
            'value_bets': [],
            'confidence_scores': {},
            'risk_level': 'medium'
        }
        
        # 汇总各玩法推荐
        for play_type, result in analyses.items():
            summary['recommendations'][play_type.value] = {
                'recommendation': result.recommendation,
                'confidence': result.confidence,
                'confidence_level': result.confidence_level
            }
            
            # 汇总价值投注
            if result.value_bets:
                summary['value_bets'].extend([
                    {'play_type': play_type.value, **vb}
                    for vb in result.value_bets
                ])
        
        # 计算整体置信度
        confidences = [r.confidence for r in analyses.values()]
        if confidences:
            avg_confidence = sum(confidences) / len(confidences)
            summary['overall_confidence'] = avg_confidence
            summary['confidence_level'] = (
                'high' if avg_confidence >= 0.6 else
                'medium' if avg_confidence >= 0.45 else 'low'
            )
        
        # 风险评估
        summary['risk_level'] = self._assess_risk(analyses, context_impacts)
        
        return summary
    
    def _assess_risk(
        self,
        analyses: Dict[PlayType, AnalysisResult],
        context_impacts: Dict[str, Any]
    ) -> str:
        """风险评估"""
        # 基于上下文影响评估风险
        risk_score = 0
        
        # 伤病影响
        if 'injury' in context_impacts:
            injury_impact = context_impacts['injury'].get('total_impact', 0)
            risk_score += abs(injury_impact) * 2
        
        # 疲劳影响
        if 'fatigue' in context_impacts:
            fatigue_level = context_impacts['fatigue'].get('level', 'normal')
            if fatigue_level == 'high':
                risk_score += 1
        
        # 置信度影响
        for result in analyses.values():
            if result.confidence_level == 'low':
                risk_score += 1
        
        if risk_score >= 3:
            return 'high'
        elif risk_score >= 1:
            return 'medium'
        else:
            return 'low'
    
    def _save_predictions(
        self,
        lottery_match_id: str,
        analyses: Dict[PlayType, AnalysisResult]
    ):
        """保存预测记录"""
        for play_type, result in analyses.items():
            self.prediction_dao.insert({
                'lottery_match_id': lottery_match_id,
                'play_type': play_type.value,
                'predictions': result.predictions,
                'recommendation': result.recommendation,
                'confidence': result.confidence,
                'confidence_level': result.confidence_level,
                'value_bets': result.value_bets,
                'details': result.details
            })
    
    def _match_to_dict(self, match: Any) -> Dict:
        """比赛信息转字典"""
        return {
            'lottery_match_id': match.lottery_match_id,
            'home_team_cn': match.home_team_cn,
            'away_team_cn': match.away_team_cn,
            'match_date': match.match_date,
            'match_time': match.match_time,
            'league_name_cn': match.league_name_cn,
            'sell_status': match.sell_status,
            'handicap_line': match.handicap_line
        }
```

### 3.5 爬虫接口 (Crawler Interface)

```python
# backend/app/lottery/crawlers/base.py

from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from enum import Enum
import asyncio
import aiohttp


class CrawlerStatus(str, Enum):
    """爬虫状态"""
    IDLE = "idle"
    RUNNING = "running"
    ERROR = "error"
    SUCCESS = "success"


@dataclass
class CrawlerResult:
    """爬虫结果"""
    success: bool
    data: List[Any]
    error: Optional[str] = None
    count: int = 0
    duration: float = 0.0


class BaseCrawler(ABC):
    """爬虫基类"""
    
    def __init__(self, config: Dict = None):
        self.config = config or {}
        self.status = CrawlerStatus.IDLE
        self._session: Optional[aiohttp.ClientSession] = None
    
    @property
    @abstractmethod
    def name(self) -> str:
        """爬虫名称"""
        pass
    
    @property
    @abstractmethod
    def base_url(self) -> str:
        """基础URL"""
        pass
    
    @abstractmethod
    async def crawl(self, *args, **kwargs) -> CrawlerResult:
        """执行爬取"""
        pass
    
    @abstractmethod
    def parse(self, response: str) -> List[Any]:
        """解析响应"""
        pass
    
    async def _get_session(self) -> aiohttp.ClientSession:
        """获取HTTP会话"""
        if self._session is None or self._session.closed:
            timeout = aiohttp.ClientTimeout(total=30)
            self._session = aiohttp.ClientSession(
                timeout=timeout,
                headers=self._get_headers()
            )
        return self._session
    
    def _get_headers(self) -> Dict[str, str]:
        """获取请求头"""
        return {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'application/json, text/plain, */*',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
        }
    
    async def _request(
        self,
        url: str,
        method: str = 'GET',
        params: Dict = None,
        data: Dict = None
    ) -> str:
        """发送请求"""
        session = await self._get_session()
        
        try:
            if method == 'GET':
                async with session.get(url, params=params) as response:
                    return await response.text()
            else:
                async with session.post(url, params=params, data=data) as response:
                    return await response.text()
        except Exception as e:
            raise Exception(f"Request failed: {e}")
    
    async def close(self):
        """关闭会话"""
        if self._session and not self._session.closed:
            await self._session.close()
    
    def rate_limit(self, interval: float = 3.0):
        """请求限流"""
        import time
        if hasattr(self, '_last_request_time'):
            elapsed = time.time() - self._last_request_time
            if elapsed < interval:
                time.sleep(interval - elapsed)
        self._last_request_time = time.time()
```

### 3.6 体彩官网爬虫 (Lottery Crawler)

```python
# backend/app/lottery/crawlers/lottery_crawler.py

from typing import Dict, List, Optional
from datetime import datetime, date
import json
import re

from .base import BaseCrawler, CrawlerResult
from ..schemas.lottery import LotteryMatch, LotteryOdds


class LotteryCrawler(BaseCrawler):
    """
    体彩官网爬虫
    
    数据源: webapi.sporttery.cn
    - 比赛列表: /gateway/jc/football/getMatchCalculatorV1.qry
    - 开奖结果: /gateway/jc/football/getMatchResultV1.qry
    """
    
    BASE_URL = "https://webapi.sporttery.cn"
    
    @property
    def name(self) -> str:
        return "lottery_official"
    
    @property
    def base_url(self) -> str:
        return self.BASE_URL
    
    async def crawl_matches(
        self,
        match_date: date = None,
        play_type: str = None
    ) -> CrawlerResult:
        """
        爬取开售比赛
        
        Args:
            match_date: 比赛日期，默认今天
            play_type: 玩法类型 (spf/bf/bqc)
        """
        if match_date is None:
            match_date = date.today()
        
        self.status = "running"
        start_time = datetime.now()
        
        try:
            # 构建请求参数
            params = {
                'sellStatus': 'on',
                'date': match_date.strftime('%Y-%m-%d')
            }
            
            if play_type:
                params['playType'] = play_type
            
            # 发送请求
            url = f"{self.BASE_URL}/gateway/jc/football/getMatchCalculatorV1.qry"
            response = await self._request(url, params=params)
            
            # 解析响应
            matches = self.parse_matches(response)
            
            duration = (datetime.now() - start_time).total_seconds()
            self.status = "success"
            
            return CrawlerResult(
                success=True,
                data=matches,
                count=len(matches),
                duration=duration
            )
            
        except Exception as e:
            self.status = "error"
            return CrawlerResult(
                success=False,
                data=[],
                error=str(e)
            )
    
    async def crawl_odds(
        self,
        lottery_match_id: str,
        play_type: str = 'spf'
    ) -> CrawlerResult:
        """爬取赔率"""
        try:
            # 构建请求
            params = {
                'matchId': lottery_match_id,
                'playType': play_type
            }
            
            url = f"{self.BASE_URL}/gateway/jc/football/getOddsV1.qry"
            response = await self._request(url, params=params)
            
            odds = self.parse_odds(response, play_type)
            
            return CrawlerResult(
                success=True,
                data=odds,
                count=len(odds)
            )
            
        except Exception as e:
            return CrawlerResult(
                success=False,
                data=[],
                error=str(e)
            )
    
    async def crawl_results(
        self,
        match_date: date = None
    ) -> CrawlerResult:
        """爬取开奖结果"""
        if match_date is None:
            match_date = date.today()
        
        try:
            params = {
                'date': match_date.strftime('%Y-%m-%d')
            }
            
            url = f"{self.BASE_URL}/gateway/jc/football/getMatchResultV1.qry"
            response = await self._request(url, params=params)
            
            results = self.parse_results(response)
            
            return CrawlerResult(
                success=True,
                data=results,
                count=len(results)
            )
            
        except Exception as e:
            return CrawlerResult(
                success=False,
                data=[],
                error=str(e)
            )
    
    def parse_matches(self, response: str) -> List[LotteryMatch]:
        """解析比赛列表"""
        matches = []
        
        try:
            data = json.loads(response)
            match_list = data.get('value', {}).get('matchInfo', [])
            
            for item in match_list:
                match = LotteryMatch(
                    lottery_match_id=item.get('matchId', ''),
                    match_num=item.get('matchNum', ''),
                    home_team_cn=item.get('homeTeam', ''),
                    away_team_cn=item.get('awayTeam', ''),
                    league_name_cn=item.get('leagueName', ''),
                    match_date=item.get('matchDate', ''),
                    match_time=item.get('matchTime', ''),
                    beijing_time=item.get('beijingTime', ''),
                    sell_status=item.get('sellStatus', 'selling'),
                    sell_end_time=item.get('sellEndTime', ''),
                    play_types=self._parse_play_types(item),
                    handicap_line=float(item.get('handicapLine', 0))
                )
                matches.append(match)
                
        except Exception as e:
            print(f"Parse error: {e}")
        
        return matches
    
    def parse_odds(self, response: str, play_type: str) -> List[LotteryOdds]:
        """解析赔率"""
        odds_list = []
        
        try:
            data = json.loads(response)
            odds_data = data.get('value', {}).get('oddsInfo', [])
            
            for item in odds_data:
                odds = LotteryOdds(
                    play_type=play_type,
                    odds_data=item
                )
                odds_list.append(odds)
                
        except Exception as e:
            print(f"Parse odds error: {e}")
        
        return odds_list
    
    def parse_results(self, response: str) -> List[Dict]:
        """解析开奖结果"""
        results = []
        
        try:
            data = json.loads(response)
            result_list = data.get('value', {}).get('matchResult', [])
            
            for item in result_list:
                result = {
                    'lottery_match_id': item.get('matchId'),
                    'home_goals_ft': item.get('homeScore'),
                    'away_goals_ft': item.get('awayScore'),
                    'home_goals_ht': item.get('homeScoreHt'),
                    'away_goals_ht': item.get('awayScoreHt'),
                    'spf_result': item.get('spfResult'),
                    'bf_result': item.get('bfResult'),
                    'bqc_result': item.get('bqcResult'),
                    'rqspf_result': item.get('rqspfResult'),
                    'draw_time': item.get('drawTime')
                }
                results.append(result)
                
        except Exception as e:
            print(f"Parse results error: {e}")
        
        return results
    
    def _parse_play_types(self, item: Dict) -> List[str]:
        """解析开售玩法"""
        play_types = []
        
        # 根据字段判断开售玩法
        if item.get('spfStatus') == 'on':
            play_types.append('spf')
        if item.get('bfStatus') == 'on':
            play_types.append('bf')
        if item.get('bqcStatus') == 'on':
            play_types.append('bqc')
        if item.get('rqspfStatus') == 'on':
            play_types.append('rqspf')
        
        return play_types
    
    async def crawl(self, *args, **kwargs) -> CrawlerResult:
        """默认爬取今日比赛"""
        return await self.crawl_matches()
```

### 3.7 调度服务 (Scheduler Service)

```python
# backend/app/lottery/scheduler/scheduler_service.py

from typing import Dict, List, Optional
from datetime import datetime, timedelta
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
import logging

from ..services.sync_service import SyncService
from ..services.analysis_service import AnalysisService
from ..services.validation_service import ValidationService


logger = logging.getLogger(__name__)


class SchedulerService:
    """
    调度服务 - 管理定时任务
    
    任务类型:
    - 数据同步: 每日08:00同步开售比赛
    - 分析生成: 每日09:00生成分析报告
    - 赔率更新: 每2小时更新最新赔率
    - 结果验证: 每日02:00验证预测结果
    - 权重优化: 每日03:00优化模型权重
    """
    
    def __init__(self, db_path: str, config: Dict = None):
        self.db_path = db_path
        self.config = config or {}
        
        # 初始化服务
        self.sync_service = SyncService(db_path)
        self.analysis_service = AnalysisService(db_path, config)
        self.validation_service = ValidationService(db_path)
        
        # 初始化调度器
        self.scheduler = AsyncIOScheduler()
        
        # 任务状态
        self.task_status: Dict[str, Dict] = {}
    
    def start(self):
        """启动调度器"""
        # 注册定时任务
        self._register_tasks()
        
        # 启动调度器
        self.scheduler.start()
        logger.info("Scheduler started")
    
    def stop(self):
        """停止调度器"""
        self.scheduler.shutdown()
        logger.info("Scheduler stopped")
    
    def _register_tasks(self):
        """注册定时任务"""
        
        # 1. 数据同步 - 每日08:00
        self.scheduler.add_job(
            self._task_sync_matches,
            CronTrigger(hour=8, minute=0),
            id='sync_matches',
            name='同步体彩比赛',
            replace_existing=True
        )
        
        # 2. 分析生成 - 每日09:00
        self.scheduler.add_job(
            self._task_generate_analysis,
            CronTrigger(hour=9, minute=0),
            id='generate_analysis',
            name='生成分析报告',
            replace_existing=True
        )
        
        # 3. 赔率更新 - 每2小时
        self.scheduler.add_job(
            self._task_update_odds,
            CronTrigger(hour='*/2'),
            id='update_odds',
            name='更新赔率',
            replace_existing=True
        )
        
        # 4. 结果验证 - 每日02:00
        self.scheduler.add_job(
            self._task_validate_results,
            CronTrigger(hour=2, minute=0),
            id='validate_results',
            name='验证预测结果',
            replace_existing=True
        )
        
        # 5. 权重优化 - 每日03:00
        self.scheduler.add_job(
            self._task_optimize_weights,
            CronTrigger(hour=3, minute=0),
            id='optimize_weights',
            name='优化模型权重',
            replace_existing=True
        )
        
        logger.info(f"Registered {len(self.scheduler.get_jobs())} tasks")
    
    async def _task_sync_matches(self):
        """任务: 同步体彩比赛"""
        task_id = 'sync_matches'
        self._update_task_status(task_id, 'running')
        
        try:
            result = await self.sync_service.sync_daily_matches()
            self._update_task_status(task_id, 'success', result)
            logger.info(f"Sync matches completed: {result}")
        except Exception as e:
            self._update_task_status(task_id, 'error', {'error': str(e)})
            logger.error(f"Sync matches failed: {e}")
    
    async def _task_generate_analysis(self):
        """任务: 生成分析报告"""
        task_id = 'generate_analysis'
        self._update_task_status(task_id, 'running')
        
        try:
            result = await self.sync_service.generate_pending_analysis()
            self._update_task_status(task_id, 'success', result)
            logger.info(f"Generate analysis completed: {result}")
        except Exception as e:
            self._update_task_status(task_id, 'error', {'error': str(e)})
            logger.error(f"Generate analysis failed: {e}")
    
    async def _task_update_odds(self):
        """任务: 更新赔率"""
        task_id = 'update_odds'
        self._update_task_status(task_id, 'running')
        
        try:
            result = await self.sync_service.update_latest_odds()
            self._update_task_status(task_id, 'success', result)
            logger.info(f"Update odds completed: {result}")
        except Exception as e:
            self._update_task_status(task_id, 'error', {'error': str(e)})
            logger.error(f"Update odds failed: {e}")
    
    async def _task_validate_results(self):
        """任务: 验证预测结果"""
        task_id = 'validate_results'
        self._update_task_status(task_id, 'running')
        
        try:
            result = await self.validation_service.validate_all_pending()
            self._update_task_status(task_id, 'success', result)
            logger.info(f"Validate results completed: {result}")
        except Exception as e:
            self._update_task_status(task_id, 'error', {'error': str(e)})
            logger.error(f"Validate results failed: {e}")
    
    async def _task_optimize_weights(self):
        """任务: 优化模型权重"""
        task_id = 'optimize_weights'
        self._update_task_status(task_id, 'running')
        
        try:
            result = await self.validation_service.optimize_weights()
            self._update_task_status(task_id, 'success', result)
            logger.info(f"Optimize weights completed: {result}")
        except Exception as e:
            self._update_task_status(task_id, 'error', {'error': str(e)})
            logger.error(f"Optimize weights failed: {e}")
    
    def _update_task_status(self, task_id: str, status: str, result: Dict = None):
        """更新任务状态"""
        self.task_status[task_id] = {
            'status': status,
            'result': result,
            'updated_at': datetime.now().isoformat()
        }
    
    def get_task_status(self) -> Dict[str, Dict]:
        """获取所有任务状态"""
        return self.task_status
    
    def get_jobs(self) -> List[Dict]:
        """获取所有任务"""
        jobs = []
        for job in self.scheduler.get_jobs():
            jobs.append({
                'id': job.id,
                'name': job.name,
                'next_run': job.next_run_time.isoformat() if job.next_run_time else None,
                'trigger': str(job.trigger)
            })
        return jobs
    
    async def run_task_now(self, task_id: str) -> Dict:
        """立即执行任务"""
        job = self.scheduler.get_job(task_id)
        if not job:
            return {'error': f'Task not found: {task_id}'}
        
        # 触发任务执行
        job.modify(next_run_time=datetime.now())
        
        return {'success': True, 'message': f'Task {task_id} triggered'}
```

---

## 四、数据模型设计

### 4.1 体彩数据模型

```python
# backend/app/lottery/schemas/lottery.py

from dataclasses import dataclass, field
from typing import Dict, List, Optional
from datetime import datetime
from enum import Enum


class SellStatus(str, Enum):
    """销售状态"""
    SELLING = "selling"      # 销售中
    STOPPED = "stopped"      # 已停售
    CLOSED = "closed"        # 已截止


@dataclass
class LotteryMatch:
    """体彩比赛"""
    lottery_match_id: str                    # 体彩比赛ID
    home_team_cn: str                        # 主队中文名
    away_team_cn: str                        # 客队中文名
    match_date: str                          # 比赛日期
    sell_status: SellStatus = SellStatus.SELLING
    
    # 可选字段
    match_id: Optional[int] = None           # 关联系统match_id
    home_team_id: Optional[int] = None       # 主队ID
    away_team_id: Optional[int] = None       # 客队ID
    match_num: Optional[str] = None          # 场次号
    league_name_cn: Optional[str] = None     # 联赛中文名
    league_id: Optional[int] = None          # 联赛ID
    match_time: Optional[str] = None         # 比赛时间
    beijing_time: Optional[str] = None       # 北京时间
    sell_end_time: Optional[str] = None      # 截止销售时间
    play_types: List[str] = field(default_factory=list)  # 开售玩法
    handicap_line: float = 0.0               # 让球数
    
    # 时间戳
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


@dataclass
class LotteryOdds:
    """体彩赔率"""
    lottery_match_id: str
    play_type: str                           # spf/bf/bqc/rqspf
    odds_data: Dict[str, float]              # 赔率数据
    
    updated_at: Optional[datetime] = None
    
    def get_odds(self, option: str) -> Optional[float]:
        """获取指定选项的赔率"""
        return self.odds_data.get(option)
    
    def get_implied_prob(self, option: str) -> Optional[float]:
        """获取隐含概率"""
        odds = self.get_odds(option)
        if odds and odds > 0:
            return 1 / odds
        return None


@dataclass
class LotteryPrediction:
    """体彩预测"""
    prediction_id: Optional[int]
    lottery_match_id: str
    play_type: str
    
    predictions: Dict[str, float]            # 各选项概率
    recommendation: str                       # 推荐选项
    confidence: float                         # 置信度
    confidence_level: str                     # high/medium/low
    
    value_bets: List[Dict] = field(default_factory=list)  # 价值投注
    
    model_version: str = "1.0"
    weights_used: Dict = field(default_factory=dict)
    
    created_at: Optional[datetime] = None


@dataclass
class LotteryResult:
    """体彩开奖结果"""
    result_id: Optional[int]
    lottery_match_id: str
    
    home_goals_ft: Optional[int] = None      # 全场主队进球
    away_goals_ft: Optional[int] = None      # 全场客队进球
    home_goals_ht: Optional[int] = None      # 半场主队进球
    away_goals_ht: Optional[int] = None      # 半场客队进球
    
    spf_result: Optional[str] = None         # 胜平负结果 3/1/0
    bf_result: Optional[str] = None          # 比分结果
    bqc_result: Optional[str] = None         # 半全场结果
    rqspf_result: Optional[str] = None       # 让球胜平负结果
    
    draw_time: Optional[datetime] = None
    created_at: Optional[datetime] = None


@dataclass
class LotteryValidation:
    """预测验证结果"""
    validation_id: Optional[int]
    prediction_id: int
    lottery_match_id: str
    play_type: str
    
    predicted_result: str
    actual_result: str
    
    is_correct: bool                          # 是否正确
    predicted_prob: float                     # 预测概率
    brier_score: float                        # 布莱尔分数
    
    validated_at: Optional[datetime] = None


@dataclass
class TeamMapping:
    """球队名称映射"""
    mapping_id: Optional[int]
    lottery_name: str                         # 体彩名称
    team_id: Optional[int]                    # 系统team_id
    
    aliases: List[str] = field(default_factory=list)  # 别名
    match_confidence: float = 1.0             # 匹配置信度
    match_method: str = "exact"               # exact/fuzzy/manual
    
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
```

---

## 五、分析器详细设计

### 5.1 胜平负分析器 (SPF Analyzer)

```python
# backend/app/lottery/analyzers/outcomes/spf_analyzer.py

from typing import Dict, List, Any
import sqlite3

from ..base import (
    BaseAnalyzer, AnalysisContext, AnalysisResult,
    PlayType, AnalysisType
)


class SPFAnalyzer(BaseAnalyzer):
    """
    胜平负分析器
    
    分析流程:
    1. 获取基础概率 (Poisson预测)
    2. 应用Elo评分调整
    3. 应用主客场优势调整
    4. 应用近期状态调整
    5. 应用上下文因素调整
    6. 计算价值投注
    """
    
    @property
    def name(self) -> str:
        return "spf_analyzer"
    
    @property
    def play_type(self) -> PlayType:
        return PlayType.SPF
    
    @property
    def analysis_type(self) -> AnalysisType:
        return AnalysisType.HYBRID
    
    def _init_dependencies(self):
        """初始化依赖"""
        # 计算引擎
        from ..calculations import PoissonCalculator, EloCalculator, ValueBetCalculator
        self.poisson_calc = PoissonCalculator(self.db_path)
        self.elo_calc = EloCalculator(self.db_path)
        self.value_bet_calc = ValueBetCalculator(self.db_path)
        
        # 上下文分析器
        from ..context import FormAnalyzer, HomeAwayAnalyzer
        self.form_analyzer = FormAnalyzer(self.db_path)
        self.home_away_analyzer = HomeAwayAnalyzer(self.db_path)
    
    def analyze(self, context: AnalysisContext) -> AnalysisResult:
        """执行分析"""
        # 1. 基础概率 (Poisson)
        base_probs = self._get_base_probabilities(context)
        
        # 2. Elo调整
        elo_adjustment = self._get_elo_adjustment(context)
        
        # 3. 主客场调整
        home_away_adjustment = self._get_home_away_adjustment(context)
        
        # 4. 近期状态调整
        form_adjustment = self._get_form_adjustment(context)
        
        # 5. 上下文调整
        context_adjustment = self._get_context_adjustment(context)
        
        # 6. 综合调整
        final_probs = self._apply_adjustments(
            base_probs,
            [elo_adjustment, home_away_adjustment, form_adjustment, context_adjustment]
        )
        
        # 7. 确定推荐
        recommendation, confidence = self._determine_recommendation(final_probs)
        
        # 8. 计算价值投注
        value_bets = self._calculate_value_bets(context, final_probs)
        
        return AnalysisResult(
            play_type=self.play_type,
            analysis_type=self.analysis_type,
            predictions=final_probs,
            recommendation=recommendation,
            confidence=confidence,
            confidence_level=self._get_confidence_level(confidence),
            value_bets=value_bets,
            details={
                'base_probs': base_probs,
                'elo_adjustment': elo_adjustment,
                'home_away_adjustment': home_away_adjustment,
                'form_adjustment': form_adjustment,
                'context_adjustment': context_adjustment
            }
        )
    
    def _get_base_probabilities(self, context: AnalysisContext) -> Dict[str, float]:
        """获取基础概率"""
        if not context.home_team_id or not context.away_team_id:
            return {'home_win': 0.33, 'draw': 0.33, 'away_win': 0.33}
        
        # 使用Poisson预测
        result = self.poisson_calc.calculate(
            context.home_team_id,
            context.away_team_id,
            context.db_conn
        )
        
        return result['probabilities']
    
    def _get_elo_adjustment(self, context: AnalysisContext) -> Dict:
        """获取Elo调整"""
        if not context.home_team_id or not context.away_team_id:
            return {'factor': 1.0, 'adjustment': {}}
        
        result = self.elo_calc.calculate_match_prediction(
            context.home_team_id,
            context.away_team_id,
            context.db_conn
        )
        
        return {
            'factor': 1.05,  # Elo权重
            'adjustment': result['predictions']
        }
    
    def _get_home_away_adjustment(self, context: AnalysisContext) -> Dict:
        """获取主客场调整"""
        if not context.home_team_id:
            return {'factor': 1.0, 'adjustment': {}}
        
        # 分析主队主场优势
        home_perf = self.home_away_analyzer.analyze_home_performance(
            context.home_team_id,
            context.db_conn
        )
        
        return {
            'factor': 1.02,
            'adjustment': home_perf
        }
    
    def _get_form_adjustment(self, context: AnalysisContext) -> Dict:
        """获取近期状态调整"""
        if not context.home_team_id or not context.away_team_id:
            return {'factor': 1.0, 'adjustment': {}}
        
        # 对比两队近期状态
        form_comparison = self.form_analyzer.compare_teams_form(
            context.home_team_id,
            context.away_team_id,
            context.db_conn
        )
        
        return {
            'factor': 1.03,
            'adjustment': form_comparison
        }
    
    def _get_context_adjustment(self, context: AnalysisContext) -> Dict:
        """获取上下文调整"""
        adjustments = {}
        
        # 从上下文获取已分析的影响
        if context.extra and 'context_impacts' in context.extra:
            impacts = context.extra['context_impacts']
            
            # 伤病影响
            if 'injury' in impacts:
                adjustments['injury'] = impacts['injury']
            
            # 疲劳影响
            if 'fatigue' in impacts:
                adjustments['fatigue'] = impacts['fatigue']
            
            # 动机影响
            if 'motivation' in impacts:
                adjustments['motivation'] = impacts['motivation']
        
        return {
            'factor': 1.0,
            'adjustment': adjustments
        }
    
    def _apply_adjustments(
        self,
        base_probs: Dict[str, float],
        adjustments: List[Dict]
    ) -> Dict[str, float]:
        """应用调整"""
        probs = base_probs.copy()
        
        for adj in adjustments:
            if adj and adj.get('adjustment'):
                # 根据调整因子修正概率
                factor = adj.get('factor', 1.0)
                adjustment = adj['adjustment']
                
                if 'home_win' in adjustment:
                    probs['home_win'] = probs['home_win'] * factor + adjustment['home_win'] * (1 - factor)
                if 'draw' in adjustment:
                    probs['draw'] = probs['draw'] * factor + adjustment['draw'] * (1 - factor)
                if 'away_win' in adjustment:
                    probs['away_win'] = probs['away_win'] * factor + adjustment['away_win'] * (1 - factor)
        
        # 标准化
        total = probs['home_win'] + probs['draw'] + probs['away_win']
        probs['home_win'] /= total
        probs['draw'] /= total
        probs['away_win'] /= total
        
        return probs
    
    def _determine_recommendation(
        self,
        probs: Dict[str, float]
    ) -> tuple:
        """确定推荐"""
        if probs['home_win'] > probs['draw'] and probs['home_win'] > probs['away_win']:
            return 'home_win', probs['home_win']
        elif probs['away_win'] > probs['draw'] and probs['away_win'] > probs['home_win']:
            return 'away_win', probs['away_win']
        else:
            return 'draw', probs['draw']
    
    def _calculate_value_bets(
        self,
        context: AnalysisContext,
        probs: Dict[str, float]
    ) -> List[Dict]:
        """计算价值投注"""
        value_bets = []
        
        if not context.odds:
            return value_bets
        
        # 获取胜平负赔率
        spf_odds = context.odds.get('spf', {})
        
        for option, prob in probs.items():
            odds = spf_odds.get(option)
            if odds and odds > 0:
                implied_prob = 1 / odds
                edge = prob - implied_prob
                
                # 价值阈值: 5%
                if edge > 0.05:
                    value_bets.append({
                        'option': option,
                        'probability': prob,
                        'odds': odds,
                        'implied_prob': implied_prob,
                        'edge': edge,
                        'value_rating': 'high' if edge > 0.1 else 'medium'
                    })
        
        return value_bets
    
    def _get_confidence_level(self, confidence: float) -> str:
        """获取置信度等级"""
        if confidence >= 0.6:
            return 'high'
        elif confidence >= 0.45:
            return 'medium'
        else:
            return 'low'
```

### 5.2 比分预测器 (Score Predictor)

```python
# backend/app/lottery/analyzers/outcomes/score_predictor.py

from typing import Dict, List, Any
import math

from ..base import (
    BaseAnalyzer, AnalysisContext, AnalysisResult,
    PlayType, AnalysisType
)


class ScorePredictor(BaseAnalyzer):
    """
    比分预测器
    
    基于Poisson分布预测比分概率
    体彩比分玩法支持27种比分:
    - 1:0, 2:0, 2:1, 3:0, 3:1, 3:2, 4:0, 4:1, 4:2, 5:0, 5:1, 5:2, 5:3, 5:4 (主胜)
    - 0:0, 1:1, 2:2, 3:3, 4:4 (平局)
    - 0:1, 0:2, 1:2, 0:3, 1:3, 2:3, 0:4, 1:4, 2:4, 0:5, 1:5, 2:5, 3:5, 4:5 (客胜)
    - 其他比分 (胜其他/平其他/负其他)
    """
    
    # 体彩标准比分
    LOTTERY_SCORES = {
        'home_win': [
            (1, 0), (2, 0), (2, 1), (3, 0), (3, 1), (3, 2),
            (4, 0), (4, 1), (4, 2), (5, 0), (5, 1), (5, 2),
            (5, 3), (5:4),  # 注意: 5:4是特殊比分
        ],
        'draw': [
            (0, 0), (1, 1), (2, 2), (3, 3), (4, 4)
        ],
        'away_win': [
            (0, 1), (0, 2), (1, 2), (0, 3), (1, 3), (2, 3),
            (0, 4), (1, 4), (2, 4), (0, 5), (1, 5), (2, 5),
            (3, 5), (4, 5)
        ]
    }
    
    @property
    def name(self) -> str:
        return "score_predictor"
    
    @property
    def play_type(self) -> PlayType:
        return PlayType.BF
    
    @property
    def analysis_type(self) -> AnalysisType:
        return AnalysisType.CALCULATION
    
    def _init_dependencies(self):
        from ..calculations import PoissonCalculator
        self.poisson_calc = PoissonCalculator(self.db_path)
    
    def analyze(self, context: AnalysisContext) -> AnalysisResult:
        """执行分析"""
        # 1. 计算预期进球
        home_xg, away_xg = self._calculate_expected_goals(context)
        
        # 2. 生成比分矩阵
        score_matrix = self._generate_score_matrix(home_xg, away_xg, max_goals=6)
        
        # 3. 计算体彩比分概率
        lottery_probs = self._calculate_lottery_probs(score_matrix)
        
        # 4. 确定推荐比分
        top_scores = sorted(lottery_probs.items(), key=lambda x: x[1], reverse=True)[:5]
        recommendation = top_scores[0][0]
        confidence = top_scores[0][1]
        
        # 5. 计算价值投注
        value_bets = self._calculate_value_bets(context, lottery_probs)
        
        return AnalysisResult(
            play_type=self.play_type,
            analysis_type=self.analysis_type,
            predictions=lottery_probs,
            recommendation=recommendation,
            confidence=confidence,
            confidence_level=self._get_confidence_level(confidence),
            value_bets=value_bets,
            details={
                'home_xg': home_xg,
                'away_xg': away_xg,
                'score_matrix': score_matrix,
                'top_scores': [{'score': s, 'prob': p} for s, p in top_scores]
            }
        )
    
    def _calculate_expected_goals(
        self,
        context: AnalysisContext
    ) -> tuple:
        """计算预期进球"""
        if context.home_team_id and context.away_team_id:
            result = self.poisson_calc.calculate(
                context.home_team_id,
                context.away_team_id,
                context.db_conn
            )
            return result['home_xg'], result['away_xg']
        
        # 默认值
        return 1.3, 1.1
    
    def _generate_score_matrix(
        self,
        home_xg: float,
        away_xg: float,
        max_goals: int = 6
    ) -> Dict[tuple, float]:
        """
        生成比分概率矩阵
        
        使用Poisson分布:
        P(X=k) = (λ^k * e^-λ) / k!
        """
        matrix = {}
        
        for home_goals in range(max_goals):
            for away_goals in range(max_goals):
                prob = (
                    self._poisson_prob(home_xg, home_goals) *
                    self._poisson_prob(away_xg, away_goals)
                )
                matrix[(home_goals, away_goals)] = prob
        
        return matrix
    
    def _poisson_prob(self, lambda_val: float, k: int) -> float:
        """Poisson概率"""
        return (lambda_val ** k * math.exp(-lambda_val)) / math.factorial(k)
    
    def _calculate_lottery_probs(
        self,
        score_matrix: Dict[tuple, float]
    ) -> Dict[str, float]:
        """计算体彩比分概率"""
        probs = {}
        
        # 主胜比分
        for score in self.LOTTERY_SCORES['home_win']:
            score_str = f"{score[0]}:{score[1]}"
            probs[score_str] = score_matrix.get(score, 0)
        
        # 平局比分
        for score in self.LOTTERY_SCORES['draw']:
            score_str = f"{score[0]}:{score[1]}"
            probs[score_str] = score_matrix.get(score, 0)
        
        # 客胜比分
        for score in self.LOTTERY_SCORES['away_win']:
            score_str = f"{score[0]}:{score[1]}"
            probs[score_str] = score_matrix.get(score, 0)
        
        # 计算其他比分概率
        home_other = sum(
            score_matrix.get(score, 0)
            for score in score_matrix.keys()
            if score[0] > score[1] and f"{score[0]}:{score[1]}" not in probs
        )
        draw_other = sum(
            score_matrix.get(score, 0)
            for score in score_matrix.keys()
            if score[0] == score[1] and f"{score[0]}:{score[1]}" not in probs
        )
        away_other = sum(
            score_matrix.get(score, 0)
            for score in score_matrix.keys()
            if score[0] < score[1] and f"{score[0]}:{score[1]}" not in probs
        )
        
        probs['home_other'] = home_other
        probs['draw_other'] = draw_other
        probs['away_other'] = away_other
        
        return probs
    
    def _calculate_value_bets(
        self,
        context: AnalysisContext,
        probs: Dict[str, float]
    ) -> List[Dict]:
        """计算价值投注"""
        value_bets = []
        
        if not context.odds:
            return value_bets
        
        bf_odds = context.odds.get('bf', {})
        
        for score, prob in probs.items():
            if score in ['home_other', 'draw_other', 'away_other']:
                continue
            
            odds = bf_odds.get(score)
            if odds and odds > 0:
                implied_prob = 1 / odds
                edge = prob - implied_prob
                
                if edge > 0.03:  # 价值阈值 3%
                    value_bets.append({
                        'score': score,
                        'probability': prob,
                        'odds': odds,
                        'implied_prob': implied_prob,
                        'edge': edge
                    })
        
        return sorted(value_bets, key=lambda x: x['edge'], reverse=True)
    
    def _get_confidence_level(self, confidence: float) -> str:
        if confidence >= 0.15:  # 比分预测置信度通常较低
            return 'high'
        elif confidence >= 0.10:
            return 'medium'
        else:
            return 'low'
```

---

## 六、数据库表设计

详见计划文件中的数据库设计部分。

---

## 七、API接口设计

详见计划文件中的API接口设计部分。

---

## 八、扩展点设计

### 8.1 新增分析器

```python
# 注册新的分析器
factory = AnalyzerFactory(db_path)
factory.register_analyzer(PlayType.CUSTOM, CustomAnalyzer)
```

### 8.2 新增数据源

```python
# 注册新的爬虫
crawler_manager.register_crawler('custom', CustomCrawler)
```

### 8.3 新增计算引擎

```python
# 注册新的计算引擎
factory.register_calculation_engine('custom_calc', CustomCalculator)
```

---

## 九、总结

本架构设计遵循以下原则:

1. **模块化**: 每个模块独立，可单独开发测试
2. **解耦性**: 通过接口/抽象类解耦，依赖注入
3. **扩展性**: 工厂模式+注册机制，方便扩展
4. **分层清晰**: Router -> Service -> Analyzer -> DAO -> Database
5. **数据驱动**: 区分SQL查询分析、数学计算分析、AI思考分析
6. **多维度**: 支持联赛交叉、球员伤病、历史情怀等多维度分析
