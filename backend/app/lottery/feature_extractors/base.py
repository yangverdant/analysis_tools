"""
特征提取器基类 - 热插拔设计核心

设计原则:
1. 单一职责: 每个提取器只负责一个特征维度
2. 故障隔离: 单个提取器失败不影响其他
3. 可配置: 权重、阈值等参数可配置
4. 可观测: 输出详细的提取过程数据
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
import sqlite3

from ..schemas.lottery import FeatureCategory


@dataclass
class ExtractionContext:
    """特征提取上下文 - 包含提取所需的所有数据"""
    # 比赛基础信息
    match_id: Optional[int]
    home_team_id: Optional[int]
    away_team_id: Optional[int]
    league_id: Optional[int]
    match_date: str
    db_conn: sqlite3.Connection

    # 体彩信息
    lottery_match_id: Optional[str] = None
    handicap_line: float = 0.0
    odds: Dict[str, Any] = None

    # 额外参数
    extra: Dict[str, Any] = None

    def get_connection(self) -> sqlite3.Connection:
        """获取数据库连接"""
        return self.db_conn


@dataclass
class ExtractionResult:
    """特征提取结果"""
    feature_name: str = ""
    category: FeatureCategory = FeatureCategory.MATH

    # 核心特征值
    value: float = 0.0                           # 归一化特征值 [-1, 1]
    raw_data: Dict[str, Any] = field(default_factory=dict)  # 原始数据

    # 元信息
    confidence: float = 1.0                # 置信度
    impact_direction: str = "neutral"      # positive/negative/neutral
    impact_magnitude: float = 0.0          # 影响幅度

    # 说明
    description: str = ""

    # 成功标志和错误信息
    success: bool = True
    error: str = ""

    # 额外数据
    data: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict:
        return {
            'feature_name': self.feature_name,
            'category': self.category.value if hasattr(self.category, 'value') else str(self.category),
            'value': self.value,
            'raw_data': self.raw_data,
            'confidence': self.confidence,
            'impact_direction': self.impact_direction,
            'impact_magnitude': self.impact_magnitude,
            'description': self.description,
            'success': self.success,
            'error': self.error,
            'data': self.data
        }


class FeatureExtractor(ABC):
    """
    特征提取器基类

    所有特征提取器必须继承此基类，并实现 extract() 方法
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

    def get_connection(self) -> sqlite3.Connection:
        """获取数据库连接"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn


class DataDrivenExtractor(FeatureExtractor):
    """
    数据驱动提取器基类 - 基于SQL查询

    适用于: 历史数据统计、交锋记录、近期状态等
    """

    @property
    def category(self) -> FeatureCategory:
        return FeatureCategory.MATH

    @abstractmethod
    def get_analysis_queries(self) -> Dict[str, str]:
        """返回分析所需的SQL查询"""
        pass

    def execute_queries(self, context: ExtractionContext) -> Dict[str, Any]:
        """执行SQL查询"""
        results = {}
        queries = self.get_analysis_queries()
        cursor = context.db_conn.cursor()

        for name, query in queries.items():
            params = self._get_query_params(context, name)
            cursor.execute(query, params)
            results[name] = [dict(row) for row in cursor.fetchall()]

        return results

    @abstractmethod
    def _get_query_params(self, context: ExtractionContext, query_name: str) -> tuple:
        """获取查询参数"""
        pass


class CalculationExtractor(FeatureExtractor):
    """
    计算驱动提取器基类 - 基于数学模型

    适用于: 泊松分布、Elo评分、xG计算等
    """

    @property
    def category(self) -> FeatureCategory:
        return FeatureCategory.MATH

    @abstractmethod
    def get_required_data(self) -> List[str]:
        """返回计算所需的数据字段"""
        pass

    @abstractmethod
    def calculate(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """执行计算"""
        pass


class ContextExtractor(FeatureExtractor):
    """
    上下文提取器基类 - 基于思考分析

    适用于: 动机分析、疲劳分析、德比关系、伤病影响等
    """

    @property
    def category(self) -> FeatureCategory:
        return FeatureCategory.CONTEXT

    @abstractmethod
    def gather_context(self, context: ExtractionContext) -> Dict[str, Any]:
        """收集上下文信息"""
        pass

    @abstractmethod
    def evaluate_impact(self, context_data: Dict[str, Any]) -> Dict[str, Any]:
        """评估影响"""
        pass

    def extract(self, context: ExtractionContext) -> ExtractionResult:
        """执行提取"""
        # 收集上下文
        context_data = self.gather_context(context)

        # 评估影响
        impact = self.evaluate_impact(context_data)

        # 构建结果
        return ExtractionResult(
            feature_name=self.name,
            category=self.category,
            value=impact.get('value', 0),
            raw_data=context_data,
            confidence=impact.get('confidence', 1.0),
            impact_direction=impact.get('direction', 'neutral'),
            impact_magnitude=impact.get('magnitude', 0),
            description=impact.get('description', '')
        )


class MarketExtractor(FeatureExtractor):
    """
    市场提取器基类 - 基于赔率分析

    适用于: 赔率变动、临场降水、冷热指数等
    """

    @property
    def category(self) -> FeatureCategory:
        return FeatureCategory.MARKET

    @abstractmethod
    def analyze_market(self, context: ExtractionContext) -> Dict[str, Any]:
        """分析市场数据"""
        pass

    def extract(self, context: ExtractionContext) -> ExtractionResult:
        """执行提取"""
        if not context.odds:
            return ExtractionResult(
                feature_name=self.name,
                category=self.category,
                value=0,
                raw_data={},
                confidence=0,
                description="无赔率数据"
            )

        market_data = self.analyze_market(context)

        return ExtractionResult(
            feature_name=self.name,
            category=self.category,
            value=market_data.get('value', 0),
            raw_data=market_data,
            confidence=market_data.get('confidence', 1.0),
            impact_direction=market_data.get('direction', 'neutral'),
            description=market_data.get('description', '')
        )