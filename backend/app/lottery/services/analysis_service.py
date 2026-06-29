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


def _table_columns(cursor, table_name: str) -> set:
    try:
        return {row[1] for row in cursor.execute(f"PRAGMA table_info({table_name})").fetchall()}
    except Exception:
        return set()


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

    # Schema mapping: analyzer name → expected raw_data keys for report assembly
    # This prevents silent data loss from key name mismatches
    ANALYZER_SCHEMA = {
        'spf_analyzer': {'final_probs'},
        'score_predictor': {'top_scores', 'score_matrix', 'home_lambda', 'away_lambda'},
        'bqc_analyzer': {'bqc_probabilities', 'top_bqc', 'value_bets'},
        'handicap_analyzer': {'handicap_line', 'adjusted_distribution', 'original_distribution', 'probability_shift', 'value_analysis', 'recommendation'},
        'over_under_analyzer': {'total_expected_goals', 'over_under_probs', 'recommendation', 'confidence', 'home_expected_goals', 'away_expected_goals'},
    }

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
        分析单场比赛 — 委托给 core/analyze.py 统一管道

        Returns:
            完整分析报告 (prediction格式, 含 final_prediction + play_predictions)
        """
        # 1. 检查缓存 (prefer prediction report)
        if not force_refresh:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            report_cols = _table_columns(cursor, "lottery_analysis_reports")
            stale_filter = "AND COALESCE(is_stale, 0) = 0" if "is_stale" in report_cols else ""
            cursor.execute(f"""
                SELECT report_data, created_at FROM lottery_analysis_reports
                WHERE lottery_match_id = ? AND report_type = 'prediction'
                {stale_filter}
                ORDER BY datetime(created_at) DESC, rowid DESC
                LIMIT 1
            """, (lottery_match_id,))
            cached = cursor.fetchone()
            conn.close()
            if cached:
                logger.info(f"Returning cached prediction report for {lottery_match_id}")
                return json.loads(cached['report_data'])

        # 2. 委托给 core/analyze.py 统一管道
        from backend.app.core.analyze import analyze_single
        result = analyze_single(self.db_path, lottery_match_id)

        if result is None:
            # Fallback: try legacy pipeline if unified fails
            logger.warning(f"Unified pipeline failed for {lottery_match_id}, trying legacy")
            return self._legacy_analyze(lottery_match_id, play_types)

        return result

    def _legacy_analyze(
        self,
        lottery_match_id: str,
        play_types: List[PlayType] = None,
    ) -> Dict:
        """Legacy pipeline (FeatureExtractorRegistry) — fallback only"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        try:
            # Get match info
            cursor.execute("""
                SELECT * FROM lottery_matches WHERE lottery_match_id = ?
            """, (lottery_match_id,))

            match_row = cursor.fetchone()
            if not match_row:
                raise ValueError(f"Match not found: {lottery_match_id}")

            match_info = dict(match_row)

            # Team mapping
            home_team_id = self.entity_mapper.get_team_id(match_info['home_team_cn'])
            away_team_id = self.entity_mapper.get_team_id(match_info['away_team_cn'])

            if home_team_id and away_team_id:
                cursor.execute("""
                    UPDATE lottery_matches
                    SET home_team_id = ?, away_team_id = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE lottery_match_id = ?
                """, (home_team_id, away_team_id, lottery_match_id))

            # Get odds
            cursor.execute("""
                SELECT play_type, odds_data FROM lottery_odds
                WHERE lottery_match_id = ?
            """, (lottery_match_id,))

            odds = {}
            for row in cursor.fetchall():
                try:
                    odds[row['play_type']] = json.loads(row['odds_data'])
                except Exception:
                    odds[row['play_type']] = {}

            # Build context and extract
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

            features = self.registry.extract_all(context)
            report = self._generate_report(match_info, features, odds)

            # Enhance
            enhancer = DetailedReportEnhancer(conn)
            enhanced_match_info = {
                'home_team_id': home_team_id,
                'away_team_id': away_team_id,
                'match_date': match_info['match_date']
            }
            report = enhancer.enhance_report(report, enhanced_match_info)

            # Save as 'full' report
            cursor.execute("""
                INSERT INTO lottery_analysis_reports
                (lottery_match_id, match_id, report_type, report_data)
                VALUES (?, ?, 'full', ?)
            """, (lottery_match_id, match_info.get('match_id'), json.dumps(report)))
            report_id = cursor.lastrowid
            columns = {row[1] for row in cursor.execute("PRAGMA table_info(lottery_analysis_reports)").fetchall()}
            if "is_stale" in columns:
                cursor.execute(
                    """
                    UPDATE lottery_analysis_reports
                    SET is_stale = CASE WHEN report_id = ? THEN 0 ELSE 1 END
                    WHERE lottery_match_id = ?
                      AND report_type IN ('prediction', 'full')
                    """,
                    (report_id, lottery_match_id),
                )

            # Save predictions
            self._save_predictions(cursor, lottery_match_id, features, report)

            conn.commit()
            return report

        except Exception as e:
            logger.error(f"Legacy analysis failed for {lottery_match_id}: {e}")
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

        # Validate analyzer outputs against expected schema
        self._validate_features(features)

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

        # 大小球分析 — 使用统一ou_calculator (Pinnacle→TTG→Poisson)
        from backend.app.lottery.services.ou_calculator import compute_ou_analysis
        ou_result = compute_ou_analysis(
            db_path=self.db_path,
            match=match_info,
            score_matrix=None,  # analysis_service没有score_matrix, Poisson由OverUnderAnalyzer兜底
            lottery_match_id=match_info.get('lottery_match_id'),
        )
        if ou_result:
            over_prob = ou_result.get('over_2_5', 0)
            under_prob = ou_result.get('under_2_5', 0)
            best_line = ou_result.get('best_line', 2.5)
            best_over = ou_result.get('best_line_over', over_prob)
            best_under = ou_result.get('best_line_under', under_prob)
            ou_confidence = max(best_over, best_under)

            ou_probs = {}
            if over_prob and over_prob > 0:
                ou_probs['over_2.5'] = over_prob
                ou_probs['under_2.5'] = under_prob or round(1 - over_prob, 4)
            over_3_5 = ou_result.get('over_3_5')
            if over_3_5 and over_3_5 > 0:
                ou_probs['over_3.5'] = over_3_5
                ou_probs['under_3.5'] = round(1 - over_3_5, 4)

            report['analyses']['ou'] = {
                'over_under_probs': ou_probs,
                'best_line': best_line,
                'best_line_probs': {
                    'over': round(best_over, 4),
                    'under': round(best_under, 4),
                },
                'recommendation': ou_result.get('recommendation', '--'),
                'confidence': round(ou_confidence, 4),
                'confidence_level': self._get_confidence_level(ou_confidence),
                'source': ou_result.get('source', 'unknown'),
            }
        else:
            # Fallback: OverUnderAnalyzer Poisson model
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
                    'away_expected': ou_data.get('away_expected_goals', 1.2),
                    'source': 'poisson',
                }

        # 半全场分析
        bqc_feature = features.get('bqc_analyzer')
        if bqc_feature:
            bqc_data = bqc_feature.raw_data
            bqc_probs = bqc_data.get('bqc_probabilities', bqc_data.get('probabilities', {}))
            top_bqc = bqc_data.get('top_bqc', [])
            bqc_rec = '--'
            if top_bqc:
                best = top_bqc[0]
                bqc_rec = best.get('display', self._format_bqc_label(best.get('bqc', '')))
            elif bqc_probs:
                best_key = max(bqc_probs, key=bqc_probs.get) if bqc_probs else ''
                bqc_rec = self._format_bqc_label(best_key)

            report['analyses']['bqc'] = {
                'probabilities': bqc_probs,
                'recommendation': bqc_rec,
                'confidence': bqc_feature.confidence,
                'confidence_level': self._get_confidence_level(bqc_feature.confidence)
            }

        # 让球分析
        handicap_feature = features.get('handicap_analyzer')
        if handicap_feature:
            handicap_data = handicap_feature.raw_data
            adjusted_dist = handicap_data.get('adjusted_distribution', handicap_data.get('adjusted_probs', {}))
            original_dist = handicap_data.get('original_distribution', {})
            prob_shift = handicap_data.get('probability_shift', {})
            value_analysis = handicap_data.get('value_analysis', {})
            handicap_rec = handicap_data.get('recommendation', '--')

            report['analyses']['rqspf'] = {
                'handicap_line': handicap_data.get('handicap_line', 0),
                'adjusted_probs': adjusted_dist,
                'original_probs': original_dist,
                'probability_shift': prob_shift,
                'value_analysis': value_analysis,
                'recommendation': handicap_rec,
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

    def _save_predictions(self, cursor, lottery_match_id: str, features: Dict, report: Dict = None):
        """保存所有玩法的预测记录"""
        # SPF
        spf_feature = features.get('spf_analyzer')
        if spf_feature:
            probs = spf_feature.raw_data.get('final_probs', {})
            cursor.execute("""
                INSERT OR REPLACE INTO lottery_predictions
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

        # Save from report analyses if available (ou, bf, bqc, rqspf)
        if not report:
            return
        analyses = report.get('analyses', {})

        # O/U
        ou = analyses.get('ou')
        if ou:
            cursor.execute("""
                INSERT OR REPLACE INTO lottery_predictions
                (lottery_match_id, play_type, predictions, recommendation,
                 confidence, confidence_level, features_json)
                VALUES (?, 'ou', ?, ?, ?, ?, ?)
            """, (
                lottery_match_id,
                json.dumps(ou.get('best_line_probs', ou.get('over_under_probs', {}))),
                ou.get('recommendation', '--'),
                ou.get('confidence', 0),
                ou.get('confidence_level', 'low'),
                json.dumps(ou)
            ))

        # BF
        bf = analyses.get('bf')
        if bf:
            cursor.execute("""
                INSERT OR REPLACE INTO lottery_predictions
                (lottery_match_id, play_type, predictions, recommendation,
                 confidence, confidence_level, features_json)
                VALUES (?, 'bf', ?, ?, ?, ?, ?)
            """, (
                lottery_match_id,
                json.dumps(bf.get('score_matrix', {})),
                bf.get('recommendation', '--'),
                bf.get('confidence', 0),
                bf.get('confidence_level', 'low'),
                json.dumps(bf)
            ))

        # BQC
        bqc = analyses.get('bqc')
        if bqc:
            cursor.execute("""
                INSERT OR REPLACE INTO lottery_predictions
                (lottery_match_id, play_type, predictions, recommendation,
                 confidence, confidence_level, features_json)
                VALUES (?, 'bqc', ?, ?, ?, ?, ?)
            """, (
                lottery_match_id,
                json.dumps(bqc.get('probabilities', {})),
                bqc.get('recommendation', '--'),
                bqc.get('confidence', 0),
                bqc.get('confidence_level', 'low'),
                json.dumps(bqc)
            ))

        # RQSPF
        rqspf = analyses.get('rqspf')
        if rqspf:
            cursor.execute("""
                INSERT OR REPLACE INTO lottery_predictions
                (lottery_match_id, play_type, predictions, recommendation,
                 confidence, confidence_level, features_json)
                VALUES (?, 'rqspf', ?, ?, ?, ?, ?)
            """, (
                lottery_match_id,
                json.dumps(rqspf.get('adjusted_probs', rqspf.get('probabilities', {}))),
                rqspf.get('recommendation', '--'),
                rqspf.get('confidence', 0),
                rqspf.get('confidence_level', 'low'),
                json.dumps(rqspf)
            ))

    def _validate_features(self, features: Dict) -> None:
        """Validate that analyzer outputs match expected schema. Log warnings for mismatches."""
        for analyzer_name, expected_keys in self.ANALYZER_SCHEMA.items():
            feature = features.get(analyzer_name)
            if not feature or not hasattr(feature, 'raw_data') or not feature.raw_data:
                continue
            actual_keys = set(feature.raw_data.keys())
            missing = expected_keys - actual_keys
            if missing:
                logger.warning(
                    f"Schema mismatch in {analyzer_name}: "
                    f"missing keys {missing}, "
                    f"actual keys={actual_keys}"
                )

    def _format_bqc_label(self, bqc: str) -> str:
        """Format BQC code like '33' to display label like '胜胜'."""
        if not bqc or len(bqc) != 2:
            return bqc or '--'
        labels = {'3': '胜', '1': '平', '0': '负'}
        return labels.get(bqc[0], '?') + labels.get(bqc[1], '?')

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

    def _get_pinnacle_ou(self, match_info: Dict) -> Optional[Dict]:
        """Get Pinnacle O/U odds for this match from oddsfe data."""
        try:
            from ..services.pinnacle_ou import get_pinnacle_ou_odds
            from fetchers.common.team_names import normalize_team_name

            home_en = normalize_team_name(match_info.get('home_team_cn', '') or match_info.get('home_team', '') or '')
            away_en = normalize_team_name(match_info.get('away_team_cn', '') or match_info.get('away_team', '') or '')
            match_date = match_info.get('match_date', '')

            if not home_en or not away_en or not match_date:
                return None

            return get_pinnacle_ou_odds(home_en, away_en, match_date, self.db_path)
        except Exception as e:
            logger.debug(f'Pinnacle O/U获取失败: {e}')
            return None

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
