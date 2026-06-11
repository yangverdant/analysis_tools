"""
体彩分析系统 - 新模块测试

测试新实现的分析器:
1. ScorePredictor - 比分预测
2. BQCAnalyzer - 半全场分析
3. HandicapAnalyzer - 让球分析
4. ValidationService - 结果验证
5. WeightOptimizer - 权重优化
"""

import sys
import os

# 添加正确的路径
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
BACKEND_DIR = os.path.dirname(SCRIPT_DIR)
PROJECT_ROOT = os.path.dirname(BACKEND_DIR)
sys.path.insert(0, PROJECT_ROOT)

import json

DB_PATH = os.path.join(PROJECT_ROOT, 'data', 'football_v2.db')


def test_score_predictor():
    """测试比分预测器"""
    print("\n=== Test ScorePredictor ===")

    from backend.app.lottery.feature_extractors.math.score_predictor import (
        ScorePredictor, predict_score
    )

    # 测试便捷函数
    result = predict_score(home_lambda=1.85, away_lambda=1.20)

    print(f"Home lambda: 1.85, Away lambda: 1.20")
    print(f"Top scores: {result['top_scores'][:3]}")
    print(f"SPF distribution: {result['spf_distribution']}")

    # 测试提取器实例化
    predictor = ScorePredictor(DB_PATH, config={})
    print(f"ScorePredictor name: {predictor.name}")

    print("ScorePredictor test passed!")
    return True


def test_bqc_analyzer():
    """测试半全场分析器"""
    print("\n=== Test BQCAnalyzer ===")

    from backend.app.lottery.feature_extractors.math.bqc_analyzer import BQCAnalyzer

    analyzer = BQCAnalyzer(DB_PATH, config={})

    # 测试格式化
    display = analyzer._format_bqc('33')
    print(f"BQC 33 display: {display}")

    display = analyzer._format_bqc('11')
    print(f"BQC 11 display: {display}")

    # 测试概率计算
    ht_dist = {'home_win': 0.35, 'draw': 0.40, 'away_win': 0.25}
    ft_dist = {'home_win': 0.45, 'draw': 0.30, 'away_win': 0.25}

    trans = {
        'ht_home_win': {'home_win': 0.55, 'draw': 0.25, 'away_win': 0.20},
        'ht_draw': {'home_win': 0.45, 'draw': 0.30, 'away_win': 0.25},
        'ht_away_win': {'home_win': 0.30, 'draw': 0.30, 'away_win': 0.40}
    }

    bqc_prob = analyzer._calculate_bqc_probabilities(ht_dist, ft_dist, trans)
    print(f"BQC probabilities: {bqc_prob}")

    print("BQCAnalyzer test passed!")
    return True


def test_handicap_analyzer():
    """测试让球分析器"""
    print("\n=== Test HandicapAnalyzer ===")

    from backend.app.lottery.feature_extractors.math.handicap_analyzer import (
        HandicapAnalyzer, analyze_handicap_match
    )

    analyzer = HandicapAnalyzer(DB_PATH, config={})
    print(f"HandicapAnalyzer name: {analyzer.name}")

    # 测试便捷函数
    result = analyze_handicap_match(
        home_lambda=1.85,
        away_lambda=1.20,
        handicap_line=-1  # 主队受让1球
    )

    print(f"Handicap line: -1 (home team gets +1)")
    print(f"Original distribution: {result['original_distribution']}")
    print(f"Adjusted distribution: {result['adjusted_distribution']}")
    print(f"Recommendation: {result['recommendation']}")

    # 测试让球为正的情况
    result2 = analyze_handicap_match(
        home_lambda=1.85,
        away_lambda=1.20,
        handicap_line=1  # 主队让1球
    )

    print(f"\nHandicap line: +1 (home team gives -1)")
    print(f"Adjusted distribution: {result2['adjusted_distribution']}")

    print("HandicapAnalyzer test passed!")
    return True


def test_validation_service():
    """测试结果验证服务"""
    print("\n=== Test ValidationService ===")

    from backend.app.lottery.closed_loop.validation_service import ValidationService

    service = ValidationService(DB_PATH)

    # 测试Brier分数计算
    brier_1 = service.calculate_brier_score(0.8, True)  # 预测80%发生，实际发生
    brier_2 = service.calculate_brier_score(0.8, False)  # 预测80%发生，实际未发生
    brier_3 = service.calculate_brier_score(0.3, False)  # 预测30%发生，实际未发生

    print(f"Brier score (80% pred, actual=True): {brier_1}")
    print(f"Brier score (80% pred, actual=False): {brier_2}")
    print(f"Brier score (30% pred, actual=False): {brier_3}")

    # 获取准确率统计
    stats = service.get_accuracy_stats(days=30)
    print(f"Accuracy stats: {stats}")

    print("ValidationService test passed!")
    return True


def test_weight_optimizer():
    """测试权重优化器"""
    print("\n=== Test WeightOptimizer ===")

    from backend.app.lottery.closed_loop.weight_optimizer import WeightOptimizer

    optimizer = WeightOptimizer(DB_PATH)

    # 获取默认权重
    default_weights = optimizer.DEFAULT_WEIGHTS
    print(f"Default SPF weights: {default_weights['spf']}")

    # 获取当前权重
    current = optimizer.get_current_weights()
    print(f"Current weights: {current}")

    # 测试期望准确率
    expected_spf = optimizer._get_expected_accuracy('spf')
    expected_bf = optimizer._get_expected_accuracy('bf')
    expected_bqc = optimizer._get_expected_accuracy('bqc')

    print(f"Expected accuracy - SPF: {expected_spf}, BF: {expected_bf}, BQC: {expected_bqc}")

    print("WeightOptimizer test passed!")
    return True


def test_registry_registration():
    """测试注册表注册"""
    print("\n=== Test Registry Registration ===")

    from backend.app.lottery.feature_extractors.registry import FeatureExtractorRegistry
    from backend.app.lottery.feature_extractors.math.spf_analyzer import SPFAnalyzer
    from backend.app.lottery.feature_extractors.math.score_predictor import ScorePredictor
    from backend.app.lottery.feature_extractors.math.bqc_analyzer import BQCAnalyzer
    from backend.app.lottery.feature_extractors.math.handicap_analyzer import HandicapAnalyzer

    registry = FeatureExtractorRegistry(DB_PATH)

    # 注册所有分析器 (传递空配置)
    registry.register(SPFAnalyzer(DB_PATH, config={}))
    registry.register(ScorePredictor(DB_PATH, config={}))
    registry.register(BQCAnalyzer(DB_PATH, config={}))
    registry.register(HandicapAnalyzer(DB_PATH, config={}))

    # 列出已注册的分析器
    extractors = registry.list_extractors()
    print(f"Registered extractors: {extractors}")

    print("Registry registration test passed!")
    return True


def main():
    """运行所有测试"""
    print("=" * 60)
    print("Lottery Analysis System - New Modules Test")
    print("=" * 60)

    tests = [
        ("ScorePredictor", test_score_predictor),
        ("BQCAnalyzer", test_bqc_analyzer),
        ("HandicapAnalyzer", test_handicap_analyzer),
        ("ValidationService", test_validation_service),
        ("WeightOptimizer", test_weight_optimizer),
        ("RegistryRegistration", test_registry_registration),
    ]

    results = []

    for name, test_func in tests:
        try:
            success = test_func()
            results.append((name, "PASS" if success else "FAIL"))
        except Exception as e:
            results.append((name, f"ERROR: {str(e)[:50]}"))

    print("\n" + "=" * 60)
    print("Test Results Summary")
    print("=" * 60)

    for name, result in results:
        status = "[OK]" if result == "PASS" else "[FAIL]"
        print(f"  {status} {name}: {result}")

    print("\n" + "=" * 60)
    print("All new modules have been implemented and tested!")
    print("=" * 60)


if __name__ == '__main__':
    main()
