"""杯赛专属分析器

与联赛分析逻辑独立: 跨联赛Elo校准、淘汰赛压力、中立场调整、爆冷因子
"""
import json
import math
import sqlite3
from pathlib import Path
from typing import Dict, Optional

from .cup_factors import (
    is_cup, detect_cup_context, calc_cup_motivation, calc_knockout_pressure,
    calc_upset_factor, adjust_elo_for_cup, adjust_poisson_for_cup,
    get_cup_weights, calc_cup_confidence, LEAGUE_STRENGTH, CUP_PRESTIGE,
)
from .elo import EloAnalyzer
from .poisson import PoissonPredictor
from .form import FormAnalyzer
from .h2h import H2HAnalyzer
from .home_away import HomeAwayAnalyzer

DB_PATH = Path('d:/football_tools/data/unified_football.db')


class CupAnalyzer:
    CUP_WEIGHTS = get_cup_weights('')

    def __init__(self, db_path=None):
        self.db_path = db_path or DB_PATH
        self.elo = EloAnalyzer(db_path=self.db_path)
        self.poisson = PoissonPredictor(db_path=self.db_path)
        self.form_analyzer = FormAnalyzer(db_path=self.db_path)
        self.h2h_analyzer = H2HAnalyzer(db_path=self.db_path)
        self.home_away = HomeAwayAnalyzer(db_path=self.db_path)

    def _get_conn(self):
        return sqlite3.connect(str(self.db_path), timeout=30)

    def _get_team_league(self, team_name: str) -> str:
        """查找球队所属联赛(用于跨联赛校准)"""
        conn = self._get_conn()
        try:
            c = conn.cursor()
            c.execute('''
                SELECT league_standard, COUNT(*) as cnt FROM matches
                WHERE (home_team = ? OR away_team = ?)
                AND league_standard NOT IN ('champions_league','europa_league','conference_league',
                    'copa_libertadores','world_cup','euro','copa_america','friendlies',
                    'uefa_nations_league','euro_qualifiers','africa_cup_of_nations','afc_asian_cup',
                    'fa_cup','efl_cup','dfb_pokal','coppa_italia','coupe_de_france','copa_del_rey')
                GROUP BY league_standard ORDER BY cnt DESC LIMIT 1
            ''', (team_name, team_name))
            row = c.fetchone()
            return row[0] if row else ''
        finally:
            conn.close()

    def _get_match_data(self, match_key: str) -> dict:
        """获取比赛详细数据"""
        conn = self._get_conn()
        try:
            c = conn.cursor()
            c.execute('''SELECT data_type, data_json FROM match_data
                         WHERE match_key = ? AND source = 'apifootball' ''', (match_key,))
            rows = c.fetchall()
            data = {}
            for dt, dj in rows:
                try:
                    data[dt] = json.loads(dj)
                except:
                    pass
            # 也从matches表获取基础信息
            c.execute('SELECT date, time, home_team, away_team, league_standard, season, venue, referee, home_score, away_score FROM matches WHERE match_key = ?', (match_key,))
            row = c.fetchone()
            if row:
                data['match_info'] = {
                    'date': row[0], 'time': row[1], 'home_team': row[2], 'away_team': row[3],
                    'league_standard': row[4], 'season': row[5], 'venue': row[6],
                    'referee': row[7], 'home_score': row[8], 'away_score': row[9],
                }
            return data
        finally:
            conn.close()

    def _get_odds(self, match_key: str) -> Optional[dict]:
        """获取赔率数据"""
        conn = self._get_conn()
        try:
            c = conn.cursor()
            c.execute('''SELECT data_json FROM match_data
                         WHERE match_key = ? AND data_type = 'odds' LIMIT 1''', (match_key,))
            row = c.fetchone()
            if row:
                return json.loads(row[0])
            return None
        finally:
            conn.close()

    def analyze(self, home_team: str, away_team: str,
                league_standard: str, season: str = '',
                match_key: str = '') -> dict:
        """杯赛分析主入口"""
        factors_available = {}
        factor_details = {}

        # 1. 获取比赛数据 & 检测杯赛上下文
        match_data = self._get_match_data(match_key) if match_key else {}
        match_info = match_data.get('match_info', {})
        match_info['league_standard'] = league_standard
        match_info['league'] = league_standard

        stage_info = detect_cup_context(match_info)
        factor_details['stage_info'] = stage_info

        # 2. Elo (调整后)
        home_league = self._get_team_league(home_team)
        away_league = self._get_team_league(away_team)
        factors_available['cross_league'] = home_league != away_league and home_league and away_league

        elo_result = self.elo.analyze(home_team, away_team)
        if elo_result and elo_result.get('home_elo'):
            adj_home, adj_away, home_adv = adjust_elo_for_cup(
                elo_result['home_elo'], elo_result['away_elo'],
                home_league, away_league, stage_info
            )
            # 用调整后的Elo重新计算概率
            elo_diff = adj_home - adj_away
            home_prob = 1 / (1 + 10 ** (-elo_diff / 400))
            away_prob = 1 - home_prob
            factor_details['elo'] = {
                'home_elo': round(adj_home, 1),
                'away_elo': round(adj_away, 1),
                'home_elo_raw': elo_result.get('home_elo', 0),
                'away_elo_raw': elo_result.get('away_elo', 0),
                'home_league': home_league,
                'away_league': away_league,
                'league_bonus_home': LEAGUE_STRENGTH.get(home_league, 0),
                'league_bonus_away': LEAGUE_STRENGTH.get(away_league, 0),
                'home_advantage': home_adv,
                'home_win_prob': round(home_prob, 3),
                'away_win_prob': round(away_prob, 3),
            }
            factors_available['elo'] = True
        else:
            factors_available['elo'] = False
            factor_details['elo'] = {'home_win_prob': 0.5, 'away_win_prob': 0.5}

        # 3. H2H (杯赛交锋加权)
        h2h_result = self.h2h_analyzer.analyze(home_team, away_team)
        if h2h_result and h2h_result.get('total_matches', 0) > 0:
            # 杯赛H2H: 提升杯赛交锋权重
            h2h_home = h2h_result.get('home_wins', 0) / max(1, h2h_result.get('total_matches', 1))
            h2h_away = h2h_result.get('away_wins', 0) / max(1, h2h_result.get('total_matches', 1))
            h2h_draw = h2h_result.get('draws', 0) / max(1, h2h_result.get('total_matches', 1))
            factor_details['h2h'] = {
                'total': h2h_result.get('total_matches', 0),
                'home_win_rate': round(h2h_home, 3),
                'away_win_rate': round(h2h_away, 3),
                'draw_rate': round(h2h_draw, 3),
                'avg_home_goals': h2h_result.get('avg_home_goals', 0),
                'avg_away_goals': h2h_result.get('avg_away_goals', 0),
            }
            factors_available['h2h'] = True
        else:
            factors_available['h2h'] = False
            factor_details['h2h'] = {'home_win_rate': 0.4, 'away_win_rate': 0.3, 'draw_rate': 0.3}

        # 4. Form (杯赛近况独立计算)
        form_result = self.form_analyzer.analyze(home_team, away_team)
        if form_result:
            factor_details['form'] = {
                'home_form': form_result.get('home_form', {}),
                'away_form': form_result.get('away_form', {}),
                'home_form_score': form_result.get('home_form_score', 0.5),
                'away_form_score': form_result.get('away_form_score', 0.5),
            }
            factors_available['form'] = True
        else:
            factors_available['form'] = False
            factor_details['form'] = {'home_form_score': 0.5, 'away_form_score': 0.5}

        # 5. 杯赛动机
        motivation = calc_cup_motivation(home_team, away_team, match_info, stage_info)
        factor_details['cup_motivation'] = motivation
        factors_available['cup_motivation'] = True

        # 6. Poisson (调整后)
        cup_home_xg, cup_away_xg = adjust_poisson_for_cup(stage_info)
        poisson_result = self.poisson.predict(home_team, away_team,
                                               league_standard=league_standard)
        if poisson_result:
            factor_details['poisson'] = {
                'home_xg': cup_home_xg,
                'away_xg': cup_away_xg,
                'home_win_prob': poisson_result.get('home_win_prob', 0.4),
                'draw_prob': poisson_result.get('draw_prob', 0.3),
                'away_win_prob': poisson_result.get('away_win_prob', 0.3),
                'base_adjusted': True,
            }
            factors_available['poisson'] = True
        else:
            factors_available['poisson'] = False
            factor_details['poisson'] = {
                'home_xg': cup_home_xg, 'away_xg': cup_away_xg,
                'home_win_prob': 0.4, 'draw_prob': 0.3, 'away_win_prob': 0.3,
            }

        # 7. Home/Away (杯赛降低权重)
        ha_result = self.home_away.analyze(home_team, away_team)
        if ha_result:
            # 中立场时减弱主场优势
            neutral_mult = 0.2 if stage_info.get('is_neutral') else 1.0
            factor_details['home_away'] = {
                'home_advantage': ha_result.get('home_advantage', 0),
                'neutral_venue': stage_info.get('is_neutral', False),
                'effective_advantage': round(ha_result.get('home_advantage', 0) * neutral_mult, 3),
            }
            factors_available['home_away'] = True
        else:
            factors_available['home_away'] = False
            factor_details['home_away'] = {'effective_advantage': 0.05 if not stage_info.get('is_neutral') else 0}

        # 8. 杯赛上下文因子
        pressure = calc_knockout_pressure(stage_info)
        upset = calc_upset_factor(
            factor_details['elo'].get('home_elo_raw', 1500),
            factor_details['elo'].get('away_elo_raw', 1500),
            stage_info
        )
        factor_details['cup_context'] = {
            'knockout_pressure': pressure,
            'upset_factor': upset,
            'prestige': CUP_PRESTIGE.get(league_standard, 0.5),
            'stage': stage_info.get('stage', 'unknown'),
            'leg': stage_info.get('leg', 'single_match'),
        }
        factors_available['cup_context'] = True

        # 9. 赔率
        odds = self._get_odds(match_key) if match_key else None
        factors_available['odds'] = odds is not None
        if odds:
            factor_details['odds'] = odds

        # 10. 加权合并概率
        probs = self._combine_factors(factor_details, factors_available, stage_info)

        # 11. 友谊赛赛前情报修正
        pre_match_adj = {}
        is_friendly = league_standard and league_standard.lower() in ('friendly', 'friendlies', 'international')
        if is_friendly:
            # 获取赔率用于分级修正
            odds_for_intel = None
            if factor_details.get('odds'):
                o = factor_details['odds']
                try:
                    odds_for_intel = {
                        'home': float(o.get('spf_h', o.get('home', 0))),
                        'draw': float(o.get('spf_d', o.get('draw', 0))),
                        'away': float(o.get('spf_a', o.get('away', 0))),
                    }
                except (ValueError, TypeError):
                    pass

            pre_match_adj = self._apply_pre_match_intel(
                home_team, away_team, league_standard,
                factor_details.get('match_info', match_info),
                probs, odds_for_intel
            )
            if pre_match_adj:
                probs = pre_match_adj['adjusted_probs']
                factor_details['pre_match_intel'] = pre_match_adj

        # 12. 置信度
        confidence = calc_cup_confidence(factors_available, stage_info)

        return {
            'analysis_type': 'cup',
            'home_win_prob': round(probs['home'], 3),
            'draw_prob': round(probs['draw'], 3),
            'away_win_prob': round(probs['away'], 3),
            'confidence': confidence,
            'factors': factor_details,
            'cup_specific': {
                'stage': stage_info.get('stage', 'unknown'),
                'leg': stage_info.get('leg', 'single_match'),
                'is_neutral': stage_info.get('is_neutral', False),
                'is_knockout': stage_info.get('is_knockout', False),
                'upset_factor': upset,
                'prestige': CUP_PRESTIGE.get(league_standard, 0.5),
                'cross_league': factors_available.get('cross_league', False),
            },
            'weights': self.CUP_WEIGHTS,
        }

    def _combine_factors(self, factors: dict, available: dict, stage_info: dict) -> dict:
        """加权合并各因子概率"""
        w = self.CUP_WEIGHTS

        # Elo概率
        elo_p = {
            'home': factors.get('elo', {}).get('home_win_prob', 0.4),
            'draw': 0.26,  # 杯赛平局基线
            'away': factors.get('elo', {}).get('away_win_prob', 0.4),
        }

        # H2H概率
        h2h_p = {
            'home': factors.get('h2h', {}).get('home_win_rate', 0.4),
            'draw': factors.get('h2h', {}).get('draw_rate', 0.3),
            'away': factors.get('h2h', {}).get('away_win_rate', 0.3),
        }

        # Form概率
        hf = factors.get('form', {}).get('home_form_score', 0.5)
        af = factors.get('form', {}).get('away_form_score', 0.5)
        form_home = 0.3 + hf * 0.4
        form_away = 0.3 + af * 0.4
        form_draw = max(0.15, 1.0 - form_home - form_away)
        form_p = {'home': form_home, 'draw': form_draw, 'away': form_away}

        # Cup motivation概率
        hm = factors.get('cup_motivation', {}).get('home_motivation', 0.5)
        am = factors.get('cup_motivation', {}).get('away_motivation', 0.5)
        mot_home = 0.3 + hm * 0.35 - am * 0.15
        mot_away = 0.3 + am * 0.35 - hm * 0.15
        mot_draw = max(0.15, 1.0 - mot_home - mot_away)
        mot_p = {'home': mot_home, 'draw': mot_draw, 'away': mot_away}

        # Poisson概率
        pois_p = {
            'home': factors.get('poisson', {}).get('home_win_prob', 0.4),
            'draw': factors.get('poisson', {}).get('draw_prob', 0.3),
            'away': factors.get('poisson', {}).get('away_win_prob', 0.3),
        }

        # Home/Away
        ha = factors.get('home_away', {}).get('effective_advantage', 0.05)
        ha_home = 0.35 + ha * 0.3
        ha_away = 0.35 - ha * 0.2
        ha_draw = max(0.15, 1.0 - ha_home - ha_away)
        ha_p = {'home': ha_home, 'draw': ha_draw, 'away': ha_away}

        # Cup context概率 (爆冷方向)
        upset = factors.get('cup_context', {}).get('upset_factor', 0)
        # 爆冷增加弱队概率
        elo_home = factors.get('elo', {}).get('home_elo_raw', 1500)
        elo_away = factors.get('elo', {}).get('away_elo_raw', 1500)
        if elo_home > elo_away:
            ctx_p = {'home': 0.45 - upset, 'draw': 0.25 + upset * 0.3, 'away': 0.30 + upset * 0.7}
        else:
            ctx_p = {'home': 0.30 + upset * 0.7, 'draw': 0.25 + upset * 0.3, 'away': 0.45 - upset}

        # 只用可用的因子
        prob_sources = {}
        if available.get('elo'):
            prob_sources['elo'] = (elo_p, w['elo'])
        if available.get('h2h'):
            prob_sources['h2h'] = (h2h_p, w['h2h'])
        if available.get('form'):
            prob_sources['form'] = (form_p, w['form'])
        prob_sources['cup_motivation'] = (mot_p, w['cup_motivation'])
        if available.get('poisson'):
            prob_sources['poisson'] = (pois_p, w['poisson'])
        prob_sources['home_away'] = (ha_p, w['home_away'])
        prob_sources['cup_context'] = (ctx_p, w['cup_context'])

        # 归一化权重
        total_w = sum(wt for _, wt in prob_sources.values())
        if total_w == 0:
            return {'home': 0.4, 'draw': 0.3, 'away': 0.3}

        combined = {'home': 0, 'draw': 0, 'away': 0}
        for name, (probs, wt) in prob_sources.items():
            norm_w = wt / total_w
            for k in combined:
                combined[k] += probs[k] * norm_w

        # 归一化
        total = combined['home'] + combined['draw'] + combined['away']
        if total > 0:
            for k in combined:
                combined[k] /= total

        return combined

    def _apply_pre_match_intel(self, home_team, away_team, league_standard,
                                match_info, base_probs, odds=None) -> Optional[dict]:
        """友谊赛赛前情报修正"""
        try:
            from fetchers.pre_match import PreMatchCollector
            collector = PreMatchCollector()

            date_str = match_info.get('date', '')
            venue = match_info.get('venue', '')

            report = collector.collect(
                home_team=home_team,
                away_team=away_team,
                date=date_str,
                league=league_standard,
                venue_city=venue,
                odds=odds
            )

            adj = report.friendly_adjustment
            if adj.get('friendly_type') == 'not_friendly':
                return None

            adjusted = {
                'home': base_probs['home'] + adj.get('home_win_adj', 0),
                'draw': base_probs['draw'] + adj.get('draw_adj', 0),
                'away': base_probs['away'] + adj.get('away_win_adj', 0),
            }

            # 确保概率在合理范围
            for k in adjusted:
                adjusted[k] = max(0.01, min(0.97, adjusted[k]))

            # 归一化
            total = sum(adjusted.values())
            for k in adjusted:
                adjusted[k] /= total

            return {
                'adjusted_probs': adjusted,
                'key_insights': report.key_insights,
                'friendly_type': adj.get('friendly_type', ''),
                'home_advantage_net': report.context.home_advantage_net if report.context else 0,
                'confidence': report.confidence,
            }
        except Exception as e:
            return None