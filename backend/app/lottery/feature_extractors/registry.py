"""
特征提取器注册表 - 热插拔核心

核心功能:
1. 热插拔: 运行时添加/移除提取器
2. 故障隔离: 单个提取器失败不影响其他
3. 分类管理: 按类别组织提取器
4. 权重管理: 支持动态调整权重 (AutoTuner)
"""

from typing import Dict, List, Optional, Any
import logging
from datetime import datetime

from .base import FeatureExtractor, ExtractionContext, ExtractionResult
from ..schemas.lottery import FeatureCategory

logger = logging.getLogger(__name__)


class FeatureExtractorRegistry:
    """
    特征提取器注册表

    管理所有特征提取器，支持热插拔和故障隔离
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
        移除特征提取器 - 不影响其他提取器

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
            'lottery_match_id': context.lottery_match_id,
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

    def get_extraction_history(self, limit: int = 100) -> List[Dict]:
        """获取提取历史"""
        return self._extraction_history[-limit:]

    def clear_history(self):
        """清除历史记录"""
        self._extraction_history = []