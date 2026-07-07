"""
综合预测分析模块

整合所有分析维度，生成综合预测结果
"""

import sqlite3
import math
from typing import Dict, List, Optional, Tuple
from datetime import datetime

from .elo import EloAnalyzer
from .xg import XGAnalyzer
from .poisson import PoissonPredictor
from .h2h import H2HAnalyzer
from ..core.cn_labels import (
    predicted_result_cn, confidence_level_cn, advantage_cn, level_cn,
    motivation_type_cn,
)
from .form import FormAnalyzer
from .home_away import HomeAwayAnalyzer
from .motivation import MotivationAnalyzer
from .news_factors import NewsFactorsAnalyzer
from .rivalry import RivalryAnalyzer
from .national_strength import NationalTeamStrengthEstimator


class ComprehensiveAnalyzer:
    """综合预测分析器"""

    # 各赛事类型的权重配置(硬编码默认值，model_weights表优先)
    WEIGHT_PROFILES = {
        'league':          {'elo': 0.25, 'poisson': 0.25, 'adjusted': 0.50},
        'cup':             {'elo': 0.20, 'poisson': 0.20, 'adjusted': 0.60},
        'super_cup':       {'elo': 0.25, 'poisson': 0.20, 'adjusted': 0.55},
        'playoff':         {'elo': 0.20, 'poisson': 0.20, 'adjusted': 0.60},
        'wc_qualifier':    {'elo': 0.20, 'poisson': 0.20, 'adjusted': 0.60},
        'nations_league':  {'elo': 0.20, 'poisson': 0.20, 'adjusted': 0.60},
        'friendly_intl':   {'elo': 0.15, 'poisson': 0.15, 'adjusted': 0.70},
        'tournament_intl': {'elo': 0.25, 'poisson': 0.25, 'adjusted': 0.50},
    }
    DEFAULT_WEIGHTS = {'elo': 0.20, 'poisson': 0.25, 'adjusted': 0.55}

    # 7因子权重配置 — learn.py调整的每个因子实际生效
    WEIGHT_PROFILES_7 = {
        'league':          {'elo': 0.20, 'poisson': 0.20, 'h2h': 0.08, 'form': 0.15, 'home_away': 0.10, 'motivation': 0.10, 'news_factors': 0.07},
        'domestic_cup':    {'elo': 0.15, 'poisson': 0.15, 'h2h': 0.08, 'form': 0.12, 'home_away': 0.10, 'motivation': 0.15, 'news_factors': 0.10},
        'continental_cup': {'elo': 0.20, 'poisson': 0.20, 'h2h': 0.08, 'form': 0.12, 'home_away': 0.08, 'motivation': 0.12, 'news_factors': 0.08},
        'qualifier':       {'elo': 0.20, 'poisson': 0.20, 'h2h': 0.08, 'form': 0.12, 'home_away': 0.10, 'motivation': 0.12, 'news_factors': 0.08},
        'nations_league':  {'elo': 0.20, 'poisson': 0.20, 'h2h': 0.08, 'form': 0.12, 'home_away': 0.10, 'motivation': 0.12, 'news_factors': 0.08},
        'friendly':        {'elo': 0.15, 'poisson': 0.15, 'h2h': 0.05, 'form': 0.10, 'home_away': 0.08, 'motivation': 0.05, 'news_factors': 0.20},
        'international_cup':{'elo': 0.20, 'poisson': 0.20, 'h2h': 0.08, 'form': 0.12, 'home_away': 0.08, 'motivation': 0.12, 'news_factors': 0.08},
        'olympic':         {'elo': 0.15, 'poisson': 0.15, 'h2h': 0.05, 'form': 0.10, 'home_away': 0.08, 'motivation': 0.15, 'news_factors': 0.15},
        'super_cup':       {'elo': 0.25, 'poisson': 0.20, 'h2h': 0.08, 'form': 0.12, 'home_away': 0.08, 'motivation': 0.10, 'news_factors': 0.07},
        'playoff':         {'elo': 0.20, 'poisson': 0.20, 'h2h': 0.08, 'form': 0.12, 'home_away': 0.10, 'motivation': 0.12, 'news_factors': 0.08},
        'wc_qualifier':    {'elo': 0.20, 'poisson': 0.20, 'h2h': 0.08, 'form': 0.12, 'home_away': 0.10, 'motivation': 0.12, 'news_factors': 0.08},
        'friendly_intl':   {'elo': 0.15, 'poisson': 0.15, 'h2h': 0.05, 'form': 0.10, 'home_away': 0.08, 'motivation': 0.05, 'news_factors': 0.20},
        'tournament_intl': {'elo': 0.25, 'poisson': 0.25, 'h2h': 0.06, 'form': 0.10, 'home_away': 0.06, 'motivation': 0.10, 'news_factors': 0.08},
    }
    DEFAULT_WEIGHTS_7 = {'elo': 0.20, 'poisson': 0.20, 'h2h': 0.08, 'form': 0.15, 'home_away': 0.10, 'motivation': 0.10, 'news_factors': 0.07}

    # model_weights缓存(避免每场预测都查DB)
    _model_weights_cache = {}
    _model_weights_cache_time = {}

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
        self.rivalry = RivalryAnalyzer(db_path)
        self.national_strength = NationalTeamStrengthEstimator()

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
        conn: sqlite3.Connection = None,
        match_profile=None,
    ) -> Dict:
        """
        综合预测比赛结果

        match_profile: 可选的MatchProfile对象(来自CompetitionRuleEngine)
        如果提供，将按分线(俱乐部/国家队)选择实力评估方式和特殊修正
        """
        if conn is None:
            conn = self.get_connection()

        # 1. 实力预测 — 分线选择评估方式
        # 国家队线: FIFA排名优先 → Elo补充
        # 俱乐部线: Elo(原有逻辑)
        is_national = (
            match_profile is not None
            and hasattr(match_profile, 'is_national')
            and match_profile.is_national
        )

        if is_national:
            try:
                strength_result = self.national_strength.estimate(
                    home_team_id, away_team_id, conn
                )
                # 统一为elo_prediction格式(后续代码复用)
                elo_prediction = {
                    'home_elo': strength_result.get('home_elo', 1500),
                    'away_elo': strength_result.get('away_elo', 1500),
                    'elo_diff': strength_result.get('elo_diff', 0),
                    'home_elo_adjusted': strength_result.get('home_elo', 1500),
                    'predictions': strength_result['probabilities'],
                    'strength_method': strength_result.get('method', 'fifa'),
                }
            except Exception as e:
                elo_prediction = {
                    'home_elo': 1500, 'away_elo': 1500, 'elo_diff': 0,
                    'home_elo_adjusted': 1500,
                    'predictions': {'home_win': 0.33, 'draw': 0.33, 'away_win': 0.33},
                    'strength_method': 'unknown',
                }
        else:
            try:
                elo_prediction = self.elo.calculate_match_elo_prediction(home_team_id, away_team_id, conn)
                elo_prediction['strength_method'] = 'elo'
            except Exception as e:
                elo_prediction = {
                    'home_elo': 1500, 'away_elo': 1500, 'elo_diff': 0,
                    'home_elo_adjusted': 1500,
                    'predictions': {'home_win': 0.33, 'draw': 0.33, 'away_win': 0.33},
                    'strength_method': 'unknown',
                }

        # 2. Poisson预测（作为基础预测）
        is_neutral = match_profile is not None and hasattr(match_profile, 'is_neutral_venue') and match_profile.is_neutral_venue
        try:
            poisson_prediction = self.poisson.predict_match(home_team_id, away_team_id, conn=conn, league_id=league_id, is_neutral_venue=is_neutral)
        except Exception as e:
            poisson_prediction = {'probabilities': {'home_win': 0.33, 'draw': 0.33, 'away_win': 0.33}, 'home_xg': 1.3, 'away_xg': 1.1, 'expected_score': {'home': 1.3, 'away': 1.1}, 'most_likely_scores': [{'score': '1-1', 'probability': 10}], 'over_under_2_5': {'probability': 0.48}, 'both_teams_to_score': {'probability': 0.5}}

        # 3. xG分析
        try:
            xg_analysis = self.xg.calculate_simple_xg(home_team_id, away_team_id, conn=conn)
        except Exception as e:
            xg_analysis = {'home_xg': 1.3, 'away_xg': 1.1}

        # 4. 交锋记录分析
        try:
            h2h_analysis = self.h2h.analyze_h2h(home_team_id, away_team_id, conn=conn)
        except Exception as e:
            h2h_analysis = {'total_matches': 0, 'overall_record': {'team1_wins': 0, 'draws': 0, 'team2_wins': 0}, 'psychological_advantage': {'description': '无交锋记录', 'advantage': 'none', 'score': 0}, 'matches': []}

        # 5. 近期状态分析（返回三个时段的数据）
        # 用对手强度加权版本替代普通form
        form_comparison = {}
        try:
            for period, n in [('last6', 6), ('last10', 10), ('last20', 20)]:
                try:
                    period_form = self.form.compare_teams_form(home_team_id, away_team_id, recent_matches=n, conn=conn)
                    # 追加对手强度加权版
                    home_weighted = self.form.analyze_form_with_opponent_strength(home_team_id, recent_matches=n, conn=conn)
                    away_weighted = self.form.analyze_form_with_opponent_strength(away_team_id, recent_matches=n, conn=conn)
                    if home_weighted.get('opponent_strength_weighted'):
                        period_form['team1_form']['form_score_raw'] = period_form['team1_form'].get('form_score', 0)
                        period_form['team1_form']['form_score'] = home_weighted.get('form_score', period_form['team1_form'].get('form_score', 0))
                        period_form['team1_form']['form_score_adjusted'] = home_weighted.get('form_score_adjusted')
                    if away_weighted.get('opponent_strength_weighted'):
                        period_form['team2_form']['form_score_raw'] = period_form['team2_form'].get('form_score', 0)
                        period_form['team2_form']['form_score'] = away_weighted.get('form_score', period_form['team2_form'].get('form_score', 0))
                        period_form['team2_form']['form_score_adjusted'] = away_weighted.get('form_score_adjusted')
                except Exception:
                    period_form = self.form.compare_teams_form(home_team_id, away_team_id, recent_matches=n, conn=conn)
                form_comparison[period] = period_form
        except Exception as e:
            form_comparison = {
                'last6': {'team1_form': {'form_score': 0, 'wins': 0, 'draws': 0, 'losses': 0, 'goals_for': 0, 'goals_against': 0, 'matches': 0}, 'team2_form': {'form_score': 0, 'wins': 0, 'draws': 0, 'losses': 0, 'goals_for': 0, 'goals_against': 0, 'matches': 0}, 'comparison': {'description': '数据不足', 'level': 'neutral', 'advantage': 'balanced'}},
                'last10': {'team1_form': {'form_score': 0, 'wins': 0, 'draws': 0, 'losses': 0, 'goals_for': 0, 'goals_against': 0, 'matches': 0}, 'team2_form': {'form_score': 0, 'wins': 0, 'draws': 0, 'losses': 0, 'goals_for': 0, 'goals_against': 0, 'matches': 0}, 'comparison': {'description': '数据不足', 'level': 'neutral', 'advantage': 'balanced'}},
                'last20': {'team1_form': {'form_score': 0, 'wins': 0, 'draws': 0, 'losses': 0, 'goals_for': 0, 'goals_against': 0, 'matches': 0}, 'team2_form': {'form_score': 0, 'wins': 0, 'draws': 0, 'losses': 0, 'goals_for': 0, 'goals_against': 0, 'matches': 0}, 'comparison': {'description': '数据不足', 'level': 'neutral', 'advantage': 'balanced'}}
            }

        # 6. 主客场优势分析（返回三个时段的数据）
        home_away_analysis = {}
        try:
            for period, n in [('last6', 6), ('last10', 10), ('last20', 20)]:
                home_perf = self.home_away.analyze_home_away_performance(home_team_id, recent_matches=n, conn=conn)
                away_perf = self.home_away.analyze_home_away_performance(away_team_id, recent_matches=n, conn=conn)
                home_away_analysis[period] = {
                    'home_team': home_perf,
                    'away_team': away_perf
                }
        except Exception as e:
            home_away_analysis = {
                'last6': {'home_team': {'home': {'matches': 0, 'wins': 0, 'draws': 0, 'losses': 0, 'goals_scored': 0, 'goals_conceded': 0}, 'away': {'matches': 0, 'wins': 0, 'draws': 0, 'losses': 0, 'goals_scored': 0, 'goals_conceded': 0}, 'home_advantage': {'level': 'unknown', 'score': 50}}, 'away_team': {'home': {'matches': 0, 'wins': 0, 'draws': 0, 'losses': 0, 'goals_scored': 0, 'goals_conceded': 0}, 'away': {'matches': 0, 'wins': 0, 'draws': 0, 'losses': 0, 'goals_scored': 0, 'goals_conceded': 0}, 'home_advantage': {'level': 'unknown', 'score': 50}}},
                'last10': {'home_team': {'home': {'matches': 0, 'wins': 0, 'draws': 0, 'losses': 0, 'goals_scored': 0, 'goals_conceded': 0}, 'away': {'matches': 0, 'wins': 0, 'draws': 0, 'losses': 0, 'goals_scored': 0, 'goals_conceded': 0}, 'home_advantage': {'level': 'unknown', 'score': 50}}, 'away_team': {'home': {'matches': 0, 'wins': 0, 'draws': 0, 'losses': 0, 'goals_scored': 0, 'goals_conceded': 0}, 'away': {'matches': 0, 'wins': 0, 'draws': 0, 'losses': 0, 'goals_scored': 0, 'goals_conceded': 0}, 'home_advantage': {'level': 'unknown', 'score': 50}}},
                'last20': {'home_team': {'home': {'matches': 0, 'wins': 0, 'draws': 0, 'losses': 0, 'goals_scored': 0, 'goals_conceded': 0}, 'away': {'matches': 0, 'wins': 0, 'draws': 0, 'losses': 0, 'goals_scored': 0, 'goals_conceded': 0}, 'home_advantage': {'level': 'unknown', 'score': 50}}, 'away_team': {'home': {'matches': 0, 'wins': 0, 'draws': 0, 'losses': 0, 'goals_scored': 0, 'goals_conceded': 0}, 'away': {'matches': 0, 'wins': 0, 'draws': 0, 'losses': 0, 'goals_scored': 0, 'goals_conceded': 0}, 'home_advantage': {'level': 'unknown', 'score': 50}}}
            }

        # 7. 动机分析
        motivation_comparison = None
        if league_id and season_id:
            try:
                motivation_comparison = self.motivation.compare_teams_motivation(
                    home_team_id, away_team_id, league_id, season_id, conn
                )
            except Exception:
                pass
        else:
            # 无积分榜 → 简化动机评估(国家队/友谊赛)
            try:
                motivation_comparison = self.motivation.analyze_motivation_simplified(
                    home_team_id, away_team_id,
                    match_date=match_date,
                    match_profile=match_profile,
                    conn=conn
                )
            except Exception:
                pass

        # 8. 利好利空分析
        try:
            factors_comparison = self.news_factors.compare_teams_factors(home_team_id, away_team_id, conn=conn)
        except Exception as e:
            factors_comparison = {'home_factors': {'net_impact': 0}, 'away_factors': {'net_impact': 0}, 'comparison': {'description': '数据不足'}}

        # 9. 敌对关系分析
        rivalry_analysis = None
        try:
            # 获取球队名称
            cursor = conn.cursor()
            cursor.execute("SELECT name_en, name_cn FROM teams WHERE team_id = ?", (home_team_id,))
            home_team_data = cursor.fetchone()
            cursor.execute("SELECT name_en, name_cn FROM teams WHERE team_id = ?", (away_team_id,))
            away_team_data = cursor.fetchone()

            if home_team_data and away_team_data:
                rivalry_analysis = self.rivalry.analyze_match_rivalry(
                    home_team_data['name_en'],
                    away_team_data['name_en'],
                    home_team_data.get('name_cn'),
                    away_team_data.get('name_cn')
                )
        except Exception:
            pass

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
        try:
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
        except Exception:
            pass

        # 近期状态调整
        try:
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
        except Exception:
            pass

        # 主客场优势调整
        try:
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
        except Exception:
            pass

        # 动机调整
        if motivation_comparison:
            try:
                if league_id and season_id:
                    # 联赛动机 → 使用完整调整
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
                else:
                    # 简化动机 → 直接用urgency_diff调整
                    comp = motivation_comparison.get('comparison', {})
                    urgency_diff = comp.get('urgency_difference', 0)
                    if abs(urgency_diff) >= 10:
                        adj = urgency_diff / 500
                        probs = adjusted_prediction['probabilities']
                        if urgency_diff > 0:
                            probs['home_win'] += adj
                            probs['away_win'] -= adj * 0.5
                        else:
                            probs['away_win'] += abs(adj)
                            probs['home_win'] -= abs(adj) * 0.5
                        total = sum(probs.values())
                        for k in probs:
                            probs[k] /= total
                        adjustments.append({
                            'type': 'motivation_simplified',
                            'urgency_diff': urgency_diff,
                            'advantage': comp.get('advantage'),
                        })
            except Exception:
                pass

        # 利好利空调整
        try:
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
        except Exception:
            pass

        # 计算最终预测（加权融合）
        weights = self._get_weights(match_profile, league_id=league_id)
        final_prediction = self._calculate_final_prediction(
            elo_prediction, poisson_prediction, adjusted_prediction, weights
        )

        # ── 赔率异动修正(从intel环节) ──
        odds_movement_signals = self._load_odds_movement(home_team_id, away_team_id, match_date, conn)
        if odds_movement_signals:
            probs = final_prediction['probabilities']
            for sig in odds_movement_signals:
                outcome = sig['outcome']
                magnitude = sig['magnitude']
                direction = sig['direction']
                # 赔率异动 → 市场信号, 向异动方向微调
                # market moving toward X → 增加X的概率
                if direction == 'up':
                    probs[outcome] += magnitude * 0.3
                else:
                    probs[outcome] -= magnitude * 0.3
                total = sum(probs.values())
                for k in probs:
                    probs[k] /= total
            adjustments.append({
                'type': 'odds_movement',
                'signals': odds_movement_signals,
            })

        # ── MatchProfile驱动的特殊修正 ──
        pre_match_intel = None

        if match_profile is not None:
            # 1) 平局增幅
            if match_profile.draw_boost != 0:
                probs = final_prediction['probabilities']
                probs['draw'] += match_profile.draw_boost
                probs['draw'] = max(0.05, min(0.60, probs['draw']))
                total = sum(probs.values())
                for k in probs:
                    probs[k] /= total

            # 2) 中立场削弱主场优势
            if match_profile.is_neutral_venue:
                probs = final_prediction['probabilities']
                home_redist = probs['home_win'] * 0.05
                probs['home_win'] -= home_redist
                probs['draw'] += home_redist * 0.4
                probs['away_win'] += home_redist * 0.6
                total = sum(probs.values())
                for k in probs:
                    probs[k] /= total

            # 3) 友谊赛5维度修正(仅FRIENDLY_INTL类型)
            if match_profile.competition_type.value == 'friendly_intl':
                try:
                    cursor = conn.cursor()
                    cursor.execute("SELECT name_en FROM teams WHERE team_id = ?", (home_team_id,))
                    home_row = cursor.fetchone()
                    cursor.execute("SELECT name_en FROM teams WHERE team_id = ?", (away_team_id,))
                    away_row = cursor.fetchone()
                    if home_row and away_row:
                        probs = final_prediction['probabilities']
                        implied_odds = {
                            'home': round(1 / max(0.01, probs['home_win']), 2),
                            'draw': round(1 / max(0.01, probs['draw']), 2),
                            'away': round(1 / max(0.01, probs['away_win']), 2),
                        }
                        pre_match_intel = self._apply_friendly_intel(
                            home_row['name_en'], away_row['name_en'],
                            match_profile.league_name, match_date or '',
                            final_prediction, implied_odds
                        )
                except Exception:
                    pass

        else:
            # 兼容旧调用: 无match_profile时保留原逻辑
            if league_id and match_date:
                try:
                    cursor = conn.cursor()
                    cursor.execute("SELECT name_en FROM leagues WHERE league_id = ?", (league_id,))
                    league_row = cursor.fetchone()
                    if league_row and league_row['name_en'] and league_row['name_en'].lower() in ('friendly', 'friendlies', 'international'):
                        cursor.execute("SELECT name_en FROM teams WHERE team_id = ?", (home_team_id,))
                        home_row = cursor.fetchone()
                        cursor.execute("SELECT name_en FROM teams WHERE team_id = ?", (away_team_id,))
                        away_row = cursor.fetchone()
                        if home_row and away_row:
                            probs = final_prediction['probabilities']
                            implied_odds = None
                            try:
                                implied_odds = {
                                    'home': round(1/max(0.01, probs['home_win']), 2),
                                    'draw': round(1/max(0.01, probs['draw']), 2),
                                    'away': round(1/max(0.01, probs['away_win']), 2),
                                }
                            except:
                                pass
                            pre_match_intel = self._apply_friendly_intel(
                                home_row['name_en'], away_row['name_en'],
                                league_row['name_en'], match_date,
                                final_prediction, implied_odds
                            )
                except Exception:
                    pass

        # ── 杯赛/友谊赛轮换修正 ──
        rotation_adjustment = None
        if match_profile and match_profile.competition_type.value in ('cup', 'friendly_intl', 'super_cup'):
            try:
                rotation_adjustment = self._apply_rotation_adjustment(
                    home_team_id, away_team_id, match_profile, match_date,
                    final_prediction, conn
                )
                if rotation_adjustment and rotation_adjustment.get('adjusted'):
                    adjustments.append({
                        'type': 'rotation',
                        'home_rotation': rotation_adjustment.get('home_rotation'),
                        'away_rotation': rotation_adjustment.get('away_rotation'),
                    })
            except Exception:
                pass

        # 生成预测报告
        weights = self._get_weights(match_profile, league_id=league_id)
        report = self._generate_prediction_report(
            home_team_id, away_team_id,
            elo_prediction, poisson_prediction, xg_analysis,
            h2h_analysis, form_comparison, home_away_analysis,
            motivation_comparison, factors_comparison,
            adjustments, final_prediction, weights
        )

        # 赔率基线(纯赔率概率, 用于对比)
        odds_baseline = None
        odds_source = None
        try:
            cursor = conn.cursor()
            # Try SPF first, then RQSPF as fallback
            for play_type in ['spf', 'rqspf']:
                cursor.execute("""
                    SELECT lo.odds_data, lo.play_type
                    FROM lottery_odds lo
                    JOIN lottery_matches lm ON lo.lottery_match_id = lm.lottery_match_id
                    WHERE lm.home_team_id = ? AND lm.away_team_id = ? AND lm.match_date = ?
                    AND lo.play_type = ?
                    ORDER BY lo.created_at DESC LIMIT 1
                """, (home_team_id, away_team_id, match_date, play_type))
                odds_row = cursor.fetchone()
                if odds_row and odds_row[0]:
                    import json as _json
                    odds_data = _json.loads(odds_row[0]) if isinstance(odds_row[0], str) else odds_row[0]
                    h = float(odds_data.get('3', odds_data.get('spf_home', odds_data.get('home', 0))))
                    d = float(odds_data.get('1', odds_data.get('spf_draw', odds_data.get('draw', 0))))
                    a = float(odds_data.get('0', odds_data.get('spf_away', odds_data.get('away', 0))))
                    if h > 1 and d > 1 and a > 1:
                        total_i = 1/h + 1/d + 1/a
                        odds_baseline = {
                            'home_win': round((1/h)/total_i, 4),
                            'draw': round((1/d)/total_i, 4),
                            'away_win': round((1/a)/total_i, 4),
                        }
                        odds_source = play_type
                        break
        except Exception:
            pass

        # 模型 vs 赔率对比
        model_vs_odds = None
        if odds_baseline:
            probs = final_prediction['probabilities']
            model_rec = max(probs, key=probs.get)
            odds_rec = max(odds_baseline, key=odds_baseline.get)
            model_vs_odds = {
                'model_rec': model_rec,
                'odds_rec': odds_rec,
                'agreement': model_rec == odds_rec,
                'source': odds_source or 'unknown',
            }

        # 因子分解
        w = weights or self.DEFAULT_WEIGHTS
        factor_breakdown = {
            'strength': {
                'method': elo_prediction.get('strength_method', 'elo'),
                'prob': elo_prediction['predictions'],
                'weight': w.get('elo', 0.20),
            },
            'poisson': {
                'prob': poisson_prediction['probabilities'],
                'weight': w.get('poisson', 0.25),
            },
        }

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
            'home_away_analysis': home_away_analysis,
            'motivation_analysis': motivation_comparison,
            'news_factors_analysis': factors_comparison,
            'rivalry_analysis': rivalry_analysis,
            'adjustments': adjustments,
            'odds_baseline': odds_baseline,
            'model_vs_odds': model_vs_odds,
            'factor_breakdown': factor_breakdown,
            'weight_source': weights.get('_source', 'hardcoded') if weights else 'hardcoded',
            'weights_used': {k: v for k, v in (weights or {}).items() if not k.startswith('_')},
            'match_profile': match_profile.to_dict() if match_profile else None,
            'report': report
        }

    def _get_weights(self, match_profile=None, league_id=None) -> Dict:
        """根据MatchProfile获取融合权重 — model_weights表优先(按联赛)，WEIGHT_PROFILES兜底

        查找顺序: model_weights(league_id) → model_weights(global) → WEIGHT_PROFILES_7
        """
        # 尝试从model_weights表读取(按联赛优先)
        db_weights = self._load_model_weights(league_id=league_id)
        if db_weights:
            total = sum(db_weights.values())
            if total > 0:
                return {k: round(v / total, 4) for k, v in db_weights.items()} | {'_source': 'model_weights'}

        # 兜底: WEIGHT_PROFILES_7 (7因子版本)
        if match_profile is not None and hasattr(match_profile, 'competition_type'):
            ct = match_profile.competition_type.value
            return self.WEIGHT_PROFILES_7.get(ct, self.DEFAULT_WEIGHTS_7).copy()
        return self.DEFAULT_WEIGHTS_7.copy()

    def _load_model_weights(self, league_id=None) -> Dict:
        """从model_weights表加载活跃权重(5分钟缓存)

        优先查找league_id匹配的行, 否则使用全局(is_active=1且league_id IS NULL)的行
        """
        import time
        now = time.time()
        # 缓存key包含league_id
        cache_key = f'league_{league_id}' if league_id else 'global'
        cache = getattr(self, '_model_weights_cache', None) or {}
        cache_time = getattr(self, '_model_weights_cache_time', None) or {}

        if cache_key in cache and cache_key in cache_time and (now - cache_time[cache_key]) < 300:
            return cache[cache_key]

        try:
            conn = sqlite3.connect(self.db_path, timeout=10)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            # 先尝试按league_id查找
            if league_id:
                try:
                    cursor.execute("SELECT * FROM model_weights WHERE is_active = 1 AND league_id = ? LIMIT 1", (league_id,))
                    row = cursor.fetchone()
                    if row:
                        weights = self._extract_weights_from_row(row)
                        cache[cache_key] = weights
                        cache_time[cache_key] = now
                        self._model_weights_cache = cache
                        self._model_weights_cache_time = cache_time
                        conn.close()
                        return weights
                except Exception:
                    pass  # league_id列可能不存在

            # 全局权重(league_id IS NULL或无league_id列)
            cursor.execute("SELECT * FROM model_weights WHERE is_active = 1 LIMIT 1")
            row = cursor.fetchone()
            conn.close()

            if row:
                weights = self._extract_weights_from_row(row)
                cache[cache_key] = weights
                cache_time[cache_key] = now
                self._model_weights_cache = cache
                self._model_weights_cache_time = cache_time
                return weights
        except Exception:
            pass

        return {}

    def _extract_weights_from_row(self, row) -> Dict:
        """从model_weights行提取7因子权重dict"""
        return {
            'elo': row['elo_weight'],
            'poisson': row['poisson_weight'],
            'h2h': row['h2h_weight'],
            'form': row['form_weight'],
            'home_away': row['home_away_weight'],
            'motivation': row['motivation_weight'],
            'news_factors': row['news_factors_weight'],
        }

    def _load_odds_movement(self, home_team_id, away_team_id, match_date, conn) -> list:
        """从intel报告加载该比赛的赔率异动信号"""
        try:
            cursor = conn.cursor()
            # 找该日期的intel报告
            report_id = f"intel_{match_date}"
            cursor.execute("""
                SELECT report_data FROM lottery_analysis_reports
                WHERE lottery_match_id = ? AND report_type = 'intel'
                ORDER BY created_at DESC LIMIT 1
            """, (report_id,))
            row = cursor.fetchone()
            if not row:
                return []
            import json as _json
            intel_data = _json.loads(row[0]) if isinstance(row[0], str) else row[0]
            movements = intel_data.get('odds_movements', [])
            if not movements:
                return []
            # 过滤出与本场相关的异动
            cursor.execute("""
                SELECT lottery_match_id FROM lottery_matches
                WHERE home_team_id = ? AND away_team_id = ? AND match_date = ?
                LIMIT 1
            """, (home_team_id, away_team_id, match_date))
            match_row = cursor.fetchone()
            if not match_row:
                return []
            lm_id = match_row['lottery_match_id']
            return [m for m in movements if m.get('lottery_match_id') == lm_id]
        except Exception:
            return []

    def _apply_rotation_adjustment(
        self, home_team_id, away_team_id, match_profile, match_date,
        final_prediction, conn
    ) -> Optional[Dict]:
        """杯赛/友谊赛轮换修正

        轮换 → 实力打折 → 弱队概率上升
        轮换概率由赛事类型+赛程密度+联赛排名安全度决定
        """
        cursor = conn.cursor()

        def _get_rotation_prob(team_id):
            """估算单队轮换概率"""
            # 基础轮换概率(赛事类型决定)
            ct = match_profile.competition_type.value
            if ct == 'friendly_intl':
                base_rot = 0.55
            elif ct == 'cup':
                base_rot = 0.30
            elif ct == 'super_cup':
                base_rot = 0.10
            else:
                base_rot = 0.15

            # 赛程密度修正: 近7天比赛数
            density = 0
            if match_date:
                try:
                    cursor.execute("""
                        SELECT COUNT(*) as cnt FROM matches
                        WHERE (home_team_id = ? OR away_team_id = ?)
                        AND match_date > date(?, '-7 days')
                        AND match_date < ?
                        AND status = 'finished'
                    """, (team_id, team_id, match_date, match_date))
                    row = cursor.fetchone()
                    density = int(row['cnt']) if row else 0
                except Exception:
                    pass

            if density >= 3:
                base_rot += 0.15  # 密集赛程更可能轮换
            elif density >= 2:
                base_rot += 0.05

            # 联赛排名安全度修正(仅联赛球队有积分榜)
            # 安全 → 更可能轮换; 保级 → 不轮换
            try:
                cursor.execute("""
                    SELECT s.position, s.points,
                           (SELECT COUNT(*) FROM standings s2
                            WHERE s2.league_id = s.league_id
                            AND s2.season_id = s.season_id) as total_teams
                    FROM standings s
                    WHERE s.team_id = ?
                    ORDER BY s.updated_at DESC LIMIT 1
                """, (team_id,))
                standing = cursor.fetchone()
                if standing and standing['total_teams'] > 0:
                    pos = standing['position'] or 0
                    total = standing['total_teams']
                    # 排名前30% → 安全 → 轮换+
                    if pos > 0 and pos <= total * 0.3:
                        base_rot += 0.10
                    # 排名后30% → 保级 → 轮换-
                    elif pos > total * 0.7:
                        base_rot -= 0.15
            except Exception:
                pass

            return max(0.0, min(0.80, base_rot))

        home_rot = _get_rotation_prob(home_team_id)
        away_rot = _get_rotation_prob(away_team_id)

        # 轮换差异 → 概率调整
        # 轮换多的队实力打折, 对手概率上升
        rot_diff = away_rot - home_rot  # 正值=客队轮换更多→利好主队
        probs = final_prediction['probabilities']

        if abs(rot_diff) < 0.05:
            return {'adjusted': False, 'home_rotation': home_rot, 'away_rotation': away_rot}

        # 轮换差异转概率调整: 每差0.1 → 调整0.02
        adj = rot_diff * 0.2
        probs['home_win'] += adj
        probs['away_win'] -= adj
        total = sum(probs.values())
        for k in probs:
            probs[k] /= total

        return {
            'adjusted': True,
            'home_rotation': round(home_rot, 2),
            'away_rotation': round(away_rot, 2),
            'rotation_diff': round(rot_diff, 2),
            'adjustment': round(adj, 4),
        }

    def _calculate_final_prediction(
        self,
        elo_prediction: Dict,
        poisson_prediction: Dict,
        adjusted_prediction: Dict,
        weights: Dict = None
    ) -> Dict:
        """
        计算最终预测（3路对数线性融合: elo + poisson + adjusted）

        使用log-linear而非线性加权:
        - 概率不能直接线性组合(不满足概率公理)
        - log-linear: log(p_final) = sum(w_i * log(p_i)), 再exp归一化
        - 当所有因子一致时结果与线性相同, 分歧时强化共识方向
        """
        if weights is None:
            weights = self.DEFAULT_WEIGHTS_7

        # Elo预测概率
        elo_probs = elo_prediction['predictions']

        # Poisson预测概率
        poisson_probs = poisson_prediction['probabilities']

        # 调整后预测概率
        adjusted_probs = adjusted_prediction['probabilities']

        elo_weight = weights.get('elo', 0.20)
        poisson_weight = weights.get('poisson', 0.20)
        adjusted_weight = 1.0 - elo_weight - poisson_weight

        # Log-linear fusion
        outcomes = ['home_win', 'draw', 'away_win']
        factor_probs = [
            (elo_probs, elo_weight),
            (poisson_probs, poisson_weight),
            (adjusted_probs, adjusted_weight),
        ]

        final = {}
        for outcome in outcomes:
            log_sum = 0.0
            for probs, w in factor_probs:
                p = max(probs.get(outcome, 0.01), 0.01)  # clamp to avoid log(0)
                log_sum += w * math.log(p)
            final[outcome] = math.exp(log_sum)

        # Normalize
        total = sum(final.values())
        if total > 0:
            final = {k: v / total for k, v in final.items()}

        # Clip to valid range
        final = {k: max(0.01, v) for k, v in final.items()}
        total = sum(final.values())
        final = {k: v / total for k, v in final.items()}

        # 确定预测结果
        predicted_result = max(final, key=final.get)
        confidence = final[predicted_result]

        # 置信度等级
        if confidence >= 0.6:
            confidence_level = 'high'
        elif confidence >= 0.45:
            confidence_level = 'medium'
        else:
            confidence_level = 'low'

        return {
            'probabilities': {
                'home_win': round(final['home_win'], 4),
                'draw': round(final['draw'], 4),
                'away_win': round(final['away_win'], 4)
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

    def _apply_friendly_intel(self, home_team, away_team, league, date, final_prediction, odds=None) -> Optional[dict]:
        """友谊赛赛前情报修正"""
        try:
            from fetchers.pre_match import PreMatchCollector
            collector = PreMatchCollector()
            report = collector.collect(home_team, away_team, date, league, odds=odds)

            adj = report.friendly_adjustment
            if adj.get('friendly_type') == 'not_friendly':
                return None

            probs = final_prediction['probabilities']
            adjusted = {
                'home_win': probs['home_win'] + adj.get('home_win_adj', 0),
                'draw': probs['draw'] + adj.get('draw_adj', 0),
                'away_win': probs['away_win'] + adj.get('away_win_adj', 0),
            }

            for k in adjusted:
                adjusted[k] = max(0.01, min(0.97, adjusted[k]))

            total = sum(adjusted.values())
            for k in adjusted:
                adjusted[k] /= total

            final_prediction['probabilities'] = adjusted
            final_prediction['pre_match_intel'] = {
                'key_insights': report.key_insights,
                'friendly_type': adj.get('friendly_type', ''),
                'home_advantage_net': report.context.home_advantage_net if report.context else 0,
            }

            # 更新预测结果
            if adjusted['home_win'] > adjusted['away_win'] and adjusted['home_win'] > adjusted['draw']:
                final_prediction['predicted_result'] = 'home_win'
                final_prediction['confidence'] = adjusted['home_win']
            elif adjusted['away_win'] > adjusted['home_win'] and adjusted['away_win'] > adjusted['draw']:
                final_prediction['predicted_result'] = 'away_win'
                final_prediction['confidence'] = adjusted['away_win']
            else:
                final_prediction['predicted_result'] = 'draw'
                final_prediction['confidence'] = adjusted['draw']

            return {
                'key_insights': report.key_insights,
                'friendly_type': adj.get('friendly_type', ''),
                'adjusted': True,
            }
        except Exception:
            return None

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
        final_prediction: Dict,
        weights: Dict = None
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
        report_lines.append(f"  预测结果：{predicted_result_cn(final_prediction['predicted_result'])}（置信度：{confidence_level_cn(final_prediction['confidence_level'])}）")

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

        # 近期状态（使用last10作为报告默认值）
        report_lines.append(f"\n近期状态：")
        form_last10 = form_comparison.get('last10', {})
        report_lines.append(f"  主队状态评分：{form_last10.get('team1_form', {}).get('form_score', 0)}")
        report_lines.append(f"  客队状态评分：{form_last10.get('team2_form', {}).get('form_score', 0)}")
        comparison_desc = form_last10.get('comparison', {}).get('description')
        if comparison_desc:
            report_lines.append(f"  状态对比：{comparison_desc}")
        else:
            level = form_last10.get('comparison', {}).get('level', 'neutral')
            advantage = form_last10.get('comparison', {}).get('advantage', 'balanced')
            report_lines.append(f"  状态对比：{advantage_cn(advantage)}方状态更优（差距等级：{level_cn(level)}）")

        # 主客场优势（使用last10作为报告默认值）
        ha_last10 = home_away_analysis.get('last10', {})
        home_team_ha = ha_last10.get('home_team', {})
        home_adv = home_team_ha.get('home_advantage', {'level': 'unknown', 'score': 50})
        report_lines.append(f"\n主场优势：")
        report_lines.append(f"  主队主场优势：{level_cn(home_adv['level'])}（评分：{home_adv['score']}）")

        # 动机分析
        if motivation_comparison:
            report_lines.append(f"\n动机分析：")
            hm = motivation_comparison.get('home_motivation', {})
            am = motivation_comparison.get('away_motivation', {})
            # 两种格式: standard用'type', simplified用'motivation_type'
            hm_type = hm.get('motivation_type', hm.get('type', '?'))
            am_type = am.get('motivation_type', am.get('type', '?'))
            hm_urgency = hm.get('urgency', '?')
            am_urgency = am.get('urgency', '?')
            report_lines.append(f"  主队动机：{motivation_type_cn(hm_type)}（紧迫度：{hm_urgency}）")
            report_lines.append(f"  客队动机：{motivation_type_cn(am_type)}（紧迫度：{am_urgency}）")
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
                adj_type = adj.get('type', '?')
                adj_factor = adj.get('factor', adj.get('urgency_diff', adj.get('rotation_diff', '')))
                report_lines.append(f"  {adj_type}：调整系数 {adj_factor}")

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
        poisson_prediction = self.poisson.predict_match(home_team_id, away_team_id, conn=conn, is_neutral_venue=False)

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