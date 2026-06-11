"""
分析服务 - 编排分析流程

整合所有特征提取器和预测模型，生成完整分析报告
"""

from typing import Dict, List, Any, Optional
from datetime import datetime
import sqlite3
import json
import logging
import os

from ..feature_extractors.registry import FeatureExtractorRegistry
from ..feature_extractors.base import ExtractionContext
from ..feature_extractors.math.spf_analyzer import SPFAnalyzer
from ..feature_extractors.math.score_predictor import ScorePredictor
from ..feature_extractors.math.bqc_analyzer import BQCAnalyzer
from ..feature_extractors.math.handicap_analyzer import HandicapAnalyzer
from ..etl.entity_mapper import EntityMapper
from ..schemas.lottery import PlayType, ConfidenceLevel
from .detailed_report_enhancer import DetailedReportEnhancer

logger = logging.getLogger(__name__)

# 数据库路径
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
DB_PATH = os.path.join(PROJECT_ROOT, 'data', 'football_v2.db')


class AnalysisService:
    """
    分析服务 - 编排整个分析流程

    流程:
    1. 获取比赛信息
    2. 球队名称映射
    3. 执行特征提取
    4. 执行各玩法预测
    5. 计算价值投注
    6. 生成分析报告
    7. 保存到数据库
    """

    def __init__(self, db_path: str = DB_PATH, config: Dict = None):
        self.db_path = db_path
        self.config = config or {}

        # 初始化组件
        self.registry = FeatureExtractorRegistry(db_path)
        self.entity_mapper = EntityMapper(db_path)

        # 注册默认提取器
        self._register_default_extractors()

    def _register_default_extractors(self):
        """注册默认的特征提取器"""
        # 核心分析器 (数学因素)
        self.registry.register(SPFAnalyzer(self.db_path))
        self.registry.register(ScorePredictor(self.db_path))
        self.registry.register(BQCAnalyzer(self.db_path))
        self.registry.register(HandicapAnalyzer(self.db_path))

        # 大小球分析器
        from ..feature_extractors.math.over_under_analyzer import OverUnderAnalyzer
        self.registry.register(OverUnderAnalyzer(self.db_path))

        # 上下文因素分析器
        from ..feature_extractors.context.injury_analyzer import InjuryAnalyzer
        from ..feature_extractors.context.schedule_analyzer import ScheduleAnalyzer
        from ..feature_extractors.context.psychological_analyzer import PsychologicalAnalyzer
        from ..feature_extractors.context.league_characteristics_analyzer import LeagueCharacteristicsAnalyzer
        from ..feature_extractors.context.weather_analyzer import WeatherAnalyzer

        self.registry.register(InjuryAnalyzer(self.db_path))
        self.registry.register(ScheduleAnalyzer(self.db_path))
        self.registry.register(PsychologicalAnalyzer(self.db_path))
        self.registry.register(LeagueCharacteristicsAnalyzer(self.db_path))
        self.registry.register(WeatherAnalyzer(self.db_path))

        # 技术/市场因素分析器
        from ..feature_extractors.market.goal_timing_analyzer import GoalTimingAnalyzer
        from ..feature_extractors.market.corner_analyzer import CornerAnalyzer
        from ..feature_extractors.market.possession_analyzer import PossessionAnalyzer
        from ..feature_extractors.market.shot_analyzer import ShotAnalyzer
        from ..feature_extractors.market.xg_analyzer import XGAnalyzer

        self.registry.register(GoalTimingAnalyzer(self.db_path))
        self.registry.register(CornerAnalyzer(self.db_path))
        self.registry.register(PossessionAnalyzer(self.db_path))
        self.registry.register(ShotAnalyzer(self.db_path))
        self.registry.register(XGAnalyzer(self.db_path))

        # 关键赛事因素分析器
        from ..feature_extractors.context.key_match_factors_analyzer import KeyMatchFactorsAnalyzer
        self.registry.register(KeyMatchFactorsAnalyzer(self.db_path))

    def analyze_match(
        self,
        lottery_match_id: str,
        play_types: List[PlayType] = None,
        force_refresh: bool = False
    ) -> Dict:
        """
        分析单场比赛

        Args:
            lottery_match_id: 体彩比赛ID
            play_types: 要分析的玩法列表，None表示全部
            force_refresh: 是否强制刷新缓存

        Returns:
            完整分析报告
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        try:
            # 1. 检查缓存
            if not force_refresh:
                cursor.execute("""
                    SELECT report_data, created_at FROM lottery_analysis_reports
                    WHERE lottery_match_id = ?
                    ORDER BY created_at DESC LIMIT 1
                """, (lottery_match_id,))

                cached = cursor.fetchone()
                if cached:
                    logger.info(f"Returning cached report for {lottery_match_id}")
                    return json.loads(cached['report_data'])

            # 2. 获取比赛信息
            cursor.execute("""
                SELECT * FROM lottery_matches WHERE lottery_match_id = ?
            """, (lottery_match_id,))

            match_row = cursor.fetchone()
            if not match_row:
                raise ValueError(f"Match not found: {lottery_match_id}")

            match_info = dict(match_row)

            # 3. 球队名称映射
            home_team_id = self.entity_mapper.get_team_id(match_info['home_team_cn'])
            away_team_id = self.entity_mapper.get_team_id(match_info['away_team_cn'])

            # 更新 lottery_matches 表的 team_id
            if home_team_id and away_team_id:
                cursor.execute("""
                    UPDATE lottery_matches
                    SET home_team_id = ?, away_team_id = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE lottery_match_id = ?
                """, (home_team_id, away_team_id, lottery_match_id))

            # 4. 获取赔率
            cursor.execute("""
                SELECT play_type, odds_data FROM lottery_odds
                WHERE lottery_match_id = ?
            """, (lottery_match_id,))

            odds = {}
            for row in cursor.fetchall():
                try:
                    odds[row['play_type']] = json.loads(row['odds_data'])
                except:
                    odds[row['play_type']] = {}

            # 5. 构建分析上下文
            context = ExtractionContext(
                match_id=match_info.get('match_id'),
                home_team_id=home_team_id,
                away_team_id=away_team_id,
                league_id=match_info.get('league_id'),
                match_date=match_info['match_date'],
                db_conn=conn,
                lottery_match_id=lottery_match_id,
                handicap_line=match_info.get('handicap_line', 0),
                odds=odds
            )

            # 6. 执行特征提取
            features = self.registry.extract_all(context)

            # 7. 生成分析报告
            report = self._generate_report(match_info, features, odds)

            # 8. 增强报告（添加详细数据）
            enhancer = DetailedReportEnhancer(conn)
            enhanced_match_info = {
                'home_team_id': home_team_id,
                'away_team_id': away_team_id,
                'match_date': match_info['match_date']
            }
            report = enhancer.enhance_report(report, enhanced_match_info)

            # 8. 保存报告
            cursor.execute("""
                INSERT INTO lottery_analysis_reports
                (lottery_match_id, match_id, report_type, report_data)
                VALUES (?, ?, 'full', ?)
            """, (lottery_match_id, match_info.get('match_id'), json.dumps(report)))

            # 9. 保存预测记录
            self._save_predictions(cursor, lottery_match_id, features)

            conn.commit()

            logger.info(f"Analysis completed for {lottery_match_id}")
            return report

        except Exception as e:
            logger.error(f"Analysis failed for {lottery_match_id}: {e}")
            raise
        finally:
            conn.close()

    def batch_analyze(
        self,
        match_ids: List[str],
        play_types: List[PlayType] = None
    ) -> List[Dict]:
        """批量分析多场比赛"""
        results = []
        for match_id in match_ids:
            try:
                report = self.analyze_match(match_id, play_types)
                results.append({
                    'lottery_match_id': match_id,
                    'success': True,
                    'report': report
                })
            except Exception as e:
                results.append({
                    'lottery_match_id': match_id,
                    'success': False,
                    'error': str(e)
                })

        return results

    def _generate_report(
        self,
        match_info: Dict,
        features: Dict,
        odds: Dict
    ) -> Dict:
        """生成分析报告"""

        report = {
            'match_info': {
                'lottery_match_id': match_info['lottery_match_id'],
                'home_team_cn': match_info['home_team_cn'],
                'away_team_cn': match_info['away_team_cn'],
                'match_date': match_info['match_date'],
                'match_time': match_info['match_time'],
                'league_name_cn': match_info['league_name_cn'],
                'handicap_line': match_info['handicap_line'],
                'play_types': json.loads(match_info['play_types']) if match_info['play_types'] else []
            },
            'generated_at': datetime.now().isoformat(),
            'analyses': {},
            'features': {},
            'recommendations': {},
            'summary': {}
        }

        # 提取特征数据
        for name, result in features.items():
            report['features'][name] = result.to_dict()

        # SPF 分析
        spf_feature = features.get('spf_analyzer')
        if spf_feature:
            spf_data = spf_feature.raw_data
            report['analyses']['spf'] = {
                'probabilities': spf_data.get('final_probs', {}),
                'recommendation': self._get_recommendation_label(spf_data.get('final_probs', {})),
                'confidence': spf_feature.confidence,
                'confidence_level': self._get_confidence_level(spf_feature.confidence),
                'value_bets': self._calculate_value_bets('spf', spf_data.get('final_probs', {}), odds)
            }

        # 比分预测
        score_feature = features.get('score_predictor')
        if score_feature:
            score_data = score_feature.raw_data
            top_scores = score_data.get('top_scores', [])
            report['analyses']['bf'] = {
                'top_scores': top_scores[:10],  # 显示前10个比分
                'recommendation': top_scores[0].get('display', '--') if top_scores else '--',
                'confidence': score_feature.confidence,
                'confidence_level': self._get_confidence_level(score_feature.confidence),
                'score_matrix': score_data.get('score_matrix', {}),
                'most_likely_home_goals': score_data.get('home_lambda', 1),
                'most_likely_away_goals': score_data.get('away_lambda', 1)
            }

        # 大小球分析
        over_under_feature = features.get('over_under_analyzer')
        if over_under_feature:
            ou_data = over_under_feature.raw_data
            report['analyses']['ou'] = {
                'total_expected_goals': ou_data.get('total_expected_goals', 2.5),
                'over_under_probs': ou_data.get('over_under_probs', {}),
                'total_goals_distribution': ou_data.get('total_goals_distribution', []),
                'recommendation': ou_data.get('recommendation', '--'),
                'confidence': ou_data.get('confidence', 0.5),
                'confidence_level': self._get_confidence_level(ou_data.get('confidence', 0.5)),
                'home_expected': ou_data.get('home_expected_goals', 1.2),
                'away_expected': ou_data.get('away_expected_goals', 1.2)
            }

        # 半全场分析
        bqc_feature = features.get('bqc_analyzer')
        if bqc_feature:
            bqc_data = bqc_feature.raw_data
            report['analyses']['bqc'] = {
                'probabilities': bqc_data.get('probabilities', {}),
                'recommendation': bqc_data.get('recommendation', '--'),
                'confidence': bqc_feature.confidence,
                'confidence_level': self._get_confidence_level(bqc_feature.confidence)
            }

        # 让球分析
        handicap_feature = features.get('handicap_analyzer')
        if handicap_feature:
            handicap_data = handicap_feature.raw_data
            report['analyses']['rqspf'] = {
                'handicap_line': handicap_data.get('handicap_line', 0),
                'adjusted_probs': handicap_data.get('adjusted_probs', {}),
                'recommendation': handicap_data.get('recommendation', '--'),
                'confidence': handicap_feature.confidence,
                'confidence_level': self._get_confidence_level(handicap_feature.confidence)
            }

        # 汇总推荐
        report['summary'] = {
            'main_recommendation': self._get_main_recommendation(report['analyses']),
            'confidence': self._get_overall_confidence(report['analyses']),
            'value_bets_count': self._count_value_bets(report['analyses'])
        }

        return report

    def _save_predictions(self, cursor, lottery_match_id: str, features: Dict):
        """保存预测记录"""
        spf_feature = features.get('spf_analyzer')
        if spf_feature:
            probs = spf_feature.raw_data.get('final_probs', {})
            cursor.execute("""
                INSERT INTO lottery_predictions
                (lottery_match_id, play_type, predictions, recommendation,
                 confidence, confidence_level, features_json)
                VALUES (?, 'spf', ?, ?, ?, ?, ?)
            """, (
                lottery_match_id,
                json.dumps(probs),
                self._get_recommendation_result(probs),
                spf_feature.confidence,
                self._get_confidence_level(spf_feature.confidence),
                json.dumps(spf_feature.to_dict())
            ))

    def _get_recommendation_label(self, probs: Dict) -> str:
        """获取推荐标签"""
        if not probs:
            return '未知'

        if probs.get('home_win', 0) > probs.get('draw', 0) and probs['home_win'] > probs.get('away_win', 0):
            return '主胜'
        elif probs.get('away_win', 0) > probs.get('draw', 0):
            return '客胜'
        else:
            return '平局'

    def _get_recommendation_result(self, probs: Dict) -> str:
        """获取推荐结果 (用于开奖对比)"""
        if not probs:
            return 'unknown'

        if probs.get('home_win', 0) > probs.get('draw', 0) and probs['home_win'] > probs.get('away_win', 0):
            return '3'  # 胜
        elif probs.get('away_win', 0) > probs.get('draw', 0):
            return '0'  # 负
        else:
            return '1'  # 平

    def _get_confidence_level(self, confidence: float) -> str:
        """获取置信度等级"""
        if confidence >= 0.6:
            return 'high'
        elif confidence >= 0.45:
            return 'medium'
        else:
            return 'low'

    def _calculate_value_bets(
        self,
        play_type: str,
        probs: Dict,
        odds: Dict
    ) -> List[Dict]:
        """计算价值投注"""
        value_bets = []

        play_odds = odds.get(play_type, {})
        if not play_odds or not probs:
            return value_bets

        # 价值阈值
        threshold = 0.05

        for option, prob in probs.items():
            # 映射选项到赔率键
            odds_key = self._map_option_to_odds_key(option)
            odds_value = play_odds.get(odds_key)

            if odds_value and odds_value > 0:
                implied_prob = 1 / odds_value
                edge = prob - implied_prob

                if edge > threshold:
                    value_bets.append({
                        'option': option,
                        'label': self._get_recommendation_label({option: 1}),
                        'probability': prob,
                        'odds': odds_value,
                        'implied_probability': implied_prob,
                        'edge': edge,
                        'value_rating': 'high' if edge > 0.1 else 'medium'
                    })

        return value_bets

    def _map_option_to_odds_key(self, option: str) -> str:
        """映射选项到赔率键"""
        mapping = {
            'home_win': '3',
            'draw': '1',
            'away_win': '0'
        }
        return mapping.get(option, option)

    def _get_main_recommendation(self, analyses: Dict) -> str:
        """获取主要推荐"""
        spf = analyses.get('spf')
        if spf:
            return f"胜平负: {spf['recommendation']}"
        return '暂无推荐'

    def _get_overall_confidence(self, analyses: Dict) -> float:
        """获取整体置信度"""
        confidences = []
        for analysis in analyses.values():
            if 'confidence' in analysis:
                confidences.append(analysis['confidence'])

        return sum(confidences) / len(confidences) if confidences else 0

    def _count_value_bets(self, analyses: Dict) -> int:
        """统计价值投注数量"""
        count = 0
        for analysis in analyses.values():
            if 'value_bets' in analysis:
                count += len(analysis['value_bets'])
        return count