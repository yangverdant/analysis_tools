"""
综合预测分析模块

整合所有分析维度，生成综合预测结果
"""

import sqlite3
from typing import Dict, List, Optional, Tuple
from datetime import datetime

from .elo import EloAnalyzer
from .xg import XGAnalyzer
from .poisson import PoissonPredictor
from .h2h import H2HAnalyzer
from .form import FormAnalyzer
from .home_away import HomeAwayAnalyzer
from .motivation import MotivationAnalyzer
from .news_factors import NewsFactorsAnalyzer


class ComprehensiveAnalyzer:
    """综合预测分析器"""

    # 各分析维度的权重配置
    ANALYSIS_WEIGHTS = {
        'elo': 0.20,           # Elo评分
        'poisson': 0.25,       # Poisson预测（核心）
        'h2h': 0.10,           # 交锋记录
        'form': 0.15,          # 近期状态
        'home_away': 0.10,     # 主客场优势
        'motivation': 0.10,    # 动机分析
        'news_factors': 0.10   # 利好利空
    }

    def __init__(self, db_path: str):
        self.db_path = db_path

        # 初始化各分析器
        self.elo = EloAnalyzer(db_path)
        self.xg = XGAnalyzer(db_path)
        self.poisson = PoissonPredictor(db_path)
        self.h2h = H2HAnalyzer(db_path)
        self.form = FormAnalyzer(db_path)
        self.home_away = HomeAwayAnalyzer(db_path)
        self.motivation = MotivationAnalyzer(db_path)
        self.news_factors = NewsFactorsAnalyzer(db_path)

    def get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def comprehensive_prediction(
        self,
        home_team_id: int,
        away_team_id: int,
        league_id: int = None,
        season_id: int = None,
        match_date: str = None,
        conn: sqlite3.Connection = None
    ) -> Dict:
        """
        综合预测比赛结果

        整合所有分析维度，生成最终预测
        """
        if conn is None:
            conn = self.get_connection()

        # 1. Elo预测
        elo_prediction = self.elo.calculate_match_elo_prediction(home_team_id, away_team_id, conn)

        # 2. Poisson预测（作为基础预测）
        poisson_prediction = self.poisson.predict_match(home_team_id, away_team_id, conn=conn)

        # 3. xG分析
        xg_analysis = self.xg.calculate_simple_xg(home_team_id, away_team_id, conn=conn)

        # 4. 交锋记录分析
        h2h_analysis = self.h2h.analyze_h2h(home_team_id, away_team_id, conn=conn)

        # 5. 近期状态分析
        form_comparison = self.form.compare_teams_form(home_team_id, away_team_id, conn=conn)

        # 6. 主客场优势分析
        home_away_analysis = self.home_away.analyze_home_away_performance(home_team_id, conn=conn)
        away_home_away_analysis = self.home_away.analyze_home_away_performance(away_team_id, conn=conn)

        # 7. 动机分析（需要league_id和season_id）
        motivation_comparison = None
        if league_id and season_id:
            motivation_comparison = self.motivation.compare_teams_motivation(
                home_team_id, away_team_id, league_id, season_id, conn
            )

        # 8. 利好利空分析
        factors_comparison = self.news_factors.compare_teams_factors(home_team_id, away_team_id, conn=conn)

        # 基础预测（使用Poisson）
        base_prediction = {
            'probabilities': poisson_prediction['probabilities'],
            'home_xg': poisson_prediction['home_xg'],
            'away_xg': poisson_prediction['away_xg']
        }

        # 应用各维度调整
        adjusted_prediction = base_prediction.copy()

        # 调整记录
        adjustments = []

        # H2H调整
        h2h_adjustment = self.h2h.get_h2h_prediction_adjustment(
            home_team_id, away_team_id, adjusted_prediction, conn
        )
        if h2h_adjustment['adjusted']:
            adjusted_prediction['probabilities'] = h2h_adjustment['adjusted_prediction']
            adjustments.append({
                'type': 'h2h',
                'factor': h2h_adjustment['adjustment_factor'],
                'psychological_score': h2h_adjustment['psychological_score']
            })

        # 近期状态调整
        form_adjustment = self.form.get_form_prediction_adjustment(
            home_team_id, away_team_id, adjusted_prediction, conn
        )
        if form_adjustment['adjusted']:
            adjusted_prediction['probabilities'] = form_adjustment['adjusted_prediction']
            adjustments.append({
                'type': 'form',
                'factor': form_adjustment['adjustment_factor'],
                'form_comparison': form_adjustment['form_comparison']
            })

        # 主客场优势调整
        home_away_adjustment = self.home_away.get_home_advantage_adjustment(
            home_team_id, away_team_id, adjusted_prediction, conn
        )
        if home_away_adjustment['adjusted']:
            adjusted_prediction['probabilities'] = home_away_adjustment['adjusted_prediction']
            adjustments.append({
                'type': 'home_away',
                'factor': home_away_adjustment['adjustment']['total'],
                'home_advantage': home_away_adjustment['home_team_home_advantage']
            })

        # 动机调整
        if motivation_comparison:
            motivation_adjustment = self.motivation.get_motivation_adjustment(
                home_team_id, away_team_id, league_id, season_id, adjusted_prediction, conn
            )
            if motivation_adjustment['adjusted']:
                adjusted_prediction['probabilities'] = motivation_adjustment['adjusted_prediction']
                adjustments.append({
                    'type': 'motivation',
                    'factor': motivation_adjustment['adjustment_factor'],
                    'motivation_comparison': motivation_adjustment['motivation_comparison']
                })

        # 利好利空调整
        factors_adjustment = self.news_factors.get_factors_adjustment(
            home_team_id, away_team_id, adjusted_prediction, conn=conn
        )
        if factors_adjustment['adjusted']:
            adjusted_prediction['probabilities'] = factors_adjustment['adjusted_prediction']
            adjustments.append({
                'type': 'news_factors',
                'factor': factors_adjustment['adjustment_factor'],
                'factors_comparison': factors_adjustment['factors_comparison']
            })

        # 计算最终预测（加权融合）
        final_prediction = self._calculate_final_prediction(
            elo_prediction, poisson_prediction, adjusted_prediction
        )

        # 生成预测报告
        report = self._generate_prediction_report(
            home_team_id, away_team_id,
            elo_prediction, poisson_prediction, xg_analysis,
            h2h_analysis, form_comparison, home_away_analysis,
            motivation_comparison, factors_comparison,
            adjustments, final_prediction
        )

        return {
            'home_team_id': home_team_id,
            'away_team_id': away_team_id,
            'league_id': league_id,
            'season_id': season_id,
            'match_date': match_date,
            'final_prediction': final_prediction,
            'base_prediction': {
                'elo': elo_prediction,
                'poisson': poisson_prediction
            },
            'xg_analysis': xg_analysis,
            'h2h_analysis': h2h_analysis,
            'form_comparison': form_comparison,
            'home_away_analysis': {
                'home_team': home_away_analysis,
                'away_team': away_home_away_analysis
            },
            'motivation_analysis': motivation_comparison,
            'news_factors_analysis': factors_comparison,
            'adjustments': adjustments,
            'report': report
        }

    def _calculate_final_prediction(
        self,
        elo_prediction: Dict,
        poisson_prediction: Dict,
        adjusted_prediction: Dict
    ) -> Dict:
        """
        计算最终预测（加权融合）
        """
        # Elo预测概率
        elo_probs = elo_prediction['predictions']

        # Poisson预测概率
        poisson_probs = poisson_prediction['probabilities']

        # 调整后预测概率
        adjusted_probs = adjusted_prediction['probabilities']

        # 加权融合
        # Poisson权重最高，作为基础
        # Elo作为补充
        # 调整后的预测作为最终修正

        elo_weight = self.ANALYSIS_WEIGHTS['elo']
        poisson_weight = self.ANALYSIS_WEIGHTS['poisson']
        adjusted_weight = 1 - elo_weight - poisson_weight

        final_home_win = (
            elo_probs['home_win'] * elo_weight +
            poisson_probs['home_win'] * poisson_weight +
            adjusted_probs['home_win'] * adjusted_weight
        )

        final_draw = (
            elo_probs['draw'] * elo_weight +
            poisson_probs['draw'] * poisson_weight +
            adjusted_probs['draw'] * adjusted_weight
        )

        final_away_win = (
            elo_probs['away_win'] * elo_weight +
            poisson_probs['away_win'] * poisson_weight +
            adjusted_probs['away_win'] * adjusted_weight
        )

        # 标准化
        total = final_home_win + final_draw + final_away_win
        final_home_win /= total
        final_draw /= total
        final_away_win /= total

        # 确定预测结果
        if final_home_win > final_away_win and final_home_win > final_draw:
            predicted_result = 'home_win'
            confidence = final_home_win
        elif final_away_win > final_home_win and final_away_win > final_draw:
            predicted_result = 'away_win'
            confidence = final_away_win
        else:
            predicted_result = 'draw'
            confidence = final_draw

        # 置信度等级
        if confidence >= 0.6:
            confidence_level = 'high'
        elif confidence >= 0.45:
            confidence_level = 'medium'
        else:
            confidence_level = 'low'

        return {
            'probabilities': {
                'home_win': round(final_home_win, 4),
                'draw': round(final_draw, 4),
                'away_win': round(final_away_win, 4)
            },
            'predicted_result': predicted_result,
            'confidence': round(confidence, 4),
            'confidence_level': confidence_level,
            'expected_score': {
                'home': round(poisson_prediction['expected_score']['home'], 2),
                'away': round(poisson_prediction['expected_score']['away'], 2)
            },
            'most_likely_scores': poisson_prediction['most_likely_scores'],
            'over_under_2_5': poisson_prediction['over_under_2_5'],
            'both_teams_to_score': poisson_prediction['both_teams_to_score']
        }

    def _generate_prediction_report(
        self,
        home_team_id: int,
        away_team_id: int,
        elo_prediction: Dict,
        poisson_prediction: Dict,
        xg_analysis: Dict,
        h2h_analysis: Dict,
        form_comparison: Dict,
        home_away_analysis: Dict,
        motivation_comparison: Optional[Dict],
        factors_comparison: Dict,
        adjustments: List[Dict],
        final_prediction: Dict
    ) -> str:
        """
        生成预测报告文本
        """
        report_lines = []

        # 标题
        report_lines.append(f"综合预测分析报告")
        report_lines.append("=" * 50)

        # 最终预测
        probs = final_prediction['probabilities']
        report_lines.append(f"\n最终预测：")
        report_lines.append(f"  主胜概率：{probs['home_win'] * 100:.1f}%")
        report_lines.append(f"  平局概率：{probs['draw'] * 100:.1f}%")
        report_lines.append(f"  客胜概率：{probs['away_win'] * 100:.1f}%")
        report_lines.append(f"  预测结果：{final_prediction['predicted_result']}（置信度：{final_prediction['confidence_level']}）")

        # 预期比分
        expected = final_prediction['expected_score']
        report_lines.append(f"\n预期比分：{expected['home']}-{expected['away']}")

        # 最可能比分
        top_scores = final_prediction['most_likely_scores'][:3]
        scores_str = ', '.join([f"{s['score']}({s['probability']}%)" for s in top_scores])
        report_lines.append(f"最可能比分：{scores_str}")

        # xG分析
        report_lines.append(f"\nxG分析：")
        report_lines.append(f"  主队xG：{xg_analysis['home_xg']}")
        report_lines.append(f"  客队xG：{xg_analysis['away_xg']}")

        # Elo分析
        report_lines.append(f"\nElo评分：")
        report_lines.append(f"  主队Elo：{elo_prediction['home_elo']}（调整后：{elo_prediction['home_elo_adjusted']}）")
        report_lines.append(f"  客队Elo：{elo_prediction['away_elo']}")
        report_lines.append(f"  Elo差距：{elo_prediction['elo_diff']}")

        # 交锋记录
        if h2h_analysis['total_matches'] > 0:
            overall = h2h_analysis['overall_record']
            report_lines.append(f"\n交锋记录：")
            report_lines.append(f"  历史交锋：{h2h_analysis['total_matches']}场")
            report_lines.append(f"  主队胜：{overall['team1_wins']}，客队胜：{overall['team2_wins']}，平：{overall['draws']}")
            psych = h2h_analysis['psychological_advantage']
            report_lines.append(f"  心理优势：{psych['description']}")

        # 近期状态
        report_lines.append(f"\n近期状态：")
        report_lines.append(f"  主队状态评分：{form_comparison['team1_form']['form_score']}")
        report_lines.append(f"  客队状态评分：{form_comparison['team2_form']['form_score']}")
        comparison_desc = form_comparison['comparison'].get('description')
        if comparison_desc:
            report_lines.append(f"  状态对比：{comparison_desc}")
        else:
            level = form_comparison['comparison'].get('level', 'neutral')
            advantage = form_comparison['comparison'].get('advantage', 'balanced')
            report_lines.append(f"  状态对比：{advantage}方状态更优（差距等级：{level}）")

        # 主客场优势
        home_adv = home_away_analysis['home_advantage']
        report_lines.append(f"\n主场优势：")
        report_lines.append(f"  主队主场优势：{home_adv['level']}（评分：{home_adv['score']}）")

        # 动机分析
        if motivation_comparison:
            report_lines.append(f"\n动机分析：")
            report_lines.append(f"  主队动机：{motivation_comparison['home_motivation']['type']}（紧迫度：{motivation_comparison['home_motivation']['urgency']}）")
            report_lines.append(f"  客队动机：{motivation_comparison['away_motivation']['type']}（紧迫度：{motivation_comparison['away_motivation']['urgency']}）")
            report_lines.append(f"  动机对比：{motivation_comparison['comparison']['description']}")

        # 利好利空
        report_lines.append(f"\n利好利空：")
        report_lines.append(f"  主队净影响：{factors_comparison['home_factors']['net_impact']}")
        report_lines.append(f"  客队净影响：{factors_comparison['away_factors']['net_impact']}")
        report_lines.append(f"  因素对比：{factors_comparison['comparison']['description']}")

        # 调整汇总
        if adjustments:
            report_lines.append(f"\n预测调整：")
            for adj in adjustments:
                report_lines.append(f"  {adj['type']}：调整系数 {adj['factor']}")

        return '\n'.join(report_lines)

    def quick_prediction(
        self,
        home_team_id: int,
        away_team_id: int,
        conn: sqlite3.Connection = None
    ) -> Dict:
        """
        快速预测（仅使用核心分析维度）

        适用于需要快速响应的场景
        """
        if conn is None:
            conn = self.get_connection()

        # 仅使用Elo和Poisson
        elo_prediction = self.elo.calculate_match_elo_prediction(home_team_id, away_team_id, conn)
        poisson_prediction = self.poisson.predict_match(home_team_id, away_team_id, conn=conn)

        # 简单加权
        elo_weight = 0.3
        poisson_weight = 0.7

        final_home_win = (
            elo_prediction['predictions']['home_win'] * elo_weight +
            poisson_prediction['probabilities']['home_win'] * poisson_weight
        )
        final_draw = (
            elo_prediction['predictions']['draw'] * elo_weight +
            poisson_prediction['probabilities']['draw'] * poisson_weight
        )
        final_away_win = (
            elo_prediction['predictions']['away_win'] * elo_weight +
            poisson_prediction['probabilities']['away_win'] * poisson_weight
        )

        # 标准化
        total = final_home_win + final_draw + final_away_win
        final_home_win /= total
        final_draw /= total
        final_away_win /= total

        return {
            'home_team_id': home_team_id,
            'away_team_id': away_team_id,
            'probabilities': {
                'home_win': round(final_home_win, 4),
                'draw': round(final_draw, 4),
                'away_win': round(final_away_win, 4)
            },
            'home_xg': poisson_prediction['home_xg'],
            'away_xg': poisson_prediction['away_xg'],
            'most_likely_scores': poisson_prediction['most_likely_scores'][:3],
            'elo_diff': elo_prediction['elo_diff']
        }

    def batch_prediction(
        self,
        matches: List[Dict],
        conn: sqlite3.Connection = None
    ) -> List[Dict]:
        """
        批量预测多场比赛
        """
        if conn is None:
            conn = self.get_connection()

        results = []
        for match in matches:
            try:
                prediction = self.quick_prediction(
                    match['home_team_id'],
                    match['away_team_id'],
                    conn
                )
                prediction['match_id'] = match['match_id']
                prediction['match_date'] = match['match_date']
                results.append(prediction)
            except Exception as e:
                results.append({
                    'match_id': match['match_id'],
                    'error': str(e)
                })

        return results

    def save_prediction_to_db(
        self,
        home_team_id: int,
        away_team_id: int,
        prediction: Dict,
        match_id: int = None,
        conn: sqlite3.Connection = None
    ) -> bool:
        """
        保存预测结果到数据库
        """
        if conn is None:
            conn = self.get_connection()

        cursor = conn.cursor()

        try:
            cursor.execute("""
                INSERT INTO match_preview_analysis (
                    match_id,
                    home_team_id,
                    away_team_id,
                    home_win_prob,
                    draw_prob,
                    away_win_prob,
                    home_xg,
                    away_xg,
                    predicted_result,
                    confidence_level,
                    analysis_components,
                    calculated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
            """, (
                match_id,
                home_team_id,
                away_team_id,
                prediction['probabilities']['home_win'],
                prediction['probabilities']['draw'],
                prediction['probabilities']['away_win'],
                prediction.get('home_xg'),
                prediction.get('away_xg'),
                prediction.get('predicted_result'),
                prediction.get('confidence_level'),
                json.dumps(prediction.get('analysis_components', {}))
            ))
            conn.commit()
            return True
        except Exception as e:
            print(f"Error saving prediction: {e}")
            return False


# 导入json用于保存分析组件
import json