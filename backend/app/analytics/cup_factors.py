"""杯赛专属分析因子

杯赛(欧冠、欧联、解放者杯、世界杯等)与联赛分析逻辑本质不同:
- 跨联赛队伍对比困难
- 淘汰赛心理/战术与联赛不同
- 中立场无主场优势
- 阵容轮换更频繁
- 两回合赛制影响策略
"""
import re
from typing import Dict, Optional, Tuple

# 杯赛定义
CUP_LEAGUES = {
    # 国际俱乐部杯赛
    'champions_league', 'europa_league', 'conference_league', 'copa_libertadores',
    # 国内杯赛
    'fa_cup', 'efl_cup', 'dfb_pokal', 'coppa_italia', 'coupe_de_france', 'copa_del_rey',
    # 国际国家队杯赛
    'world_cup', 'euro', 'copa_america', 'africa_cup_of_nations', 'afc_asian_cup',
    'uefa_nations_league', 'euro_qualifiers', 'friendlies',
    'gold_cup',
}

# 联赛强度系数 (跨联赛Elo校准)
LEAGUE_STRENGTH = {
    'premier_league': 50, 'championship': 10,
    'la_liga': 40, 'segunda_division': 5,
    'bundesliga': 35, 'bundesliga_2': 5,
    'serie_a': 30, 'serie_b': 5,
    'ligue_1': 25, 'ligue_2': 5,
    'eredivisie': 15, 'primeira_liga': 12,
    'champions_league': 45, 'europa_league': 30, 'conference_league': 20,
    'copa_libertadores': 20,
    'k_league_1': 8, 'j1_league': 10,
}

# 杯赛奖金权重 (影响动机)
CUP_PRESTIGE = {
    'champions_league': 1.5, 'europa_league': 1.0, 'conference_league': 0.7,
    'copa_libertadores': 1.2, 'world_cup': 1.5, 'euro': 1.5,
    'copa_america': 1.3, 'africa_cup_of_nations': 0.8, 'afc_asian_cup': 0.7,
    'fa_cup': 0.6, 'dfb_pokal': 0.5, 'coppa_italia': 0.5,
    'coupe_de_france': 0.4, 'copa_del_rey': 0.5, 'efl_cup': 0.3,
    'uefa_nations_league': 0.5, 'euro_qualifiers': 0.6, 'friendlies': 0.2,
    'gold_cup': 0.5,
}


def is_cup(league_standard: str) -> bool:
    return league_standard in CUP_LEAGUES


def detect_cup_context(match_data: dict) -> dict:
    """检测杯赛上下文: 阶段、回合、中立场"""
    round_name = match_data.get('round', '') or ''
    venue = match_data.get('venue', '') or match_data.get('stadium', '') or ''
    league = match_data.get('league_standard', '') or match_data.get('league', '')

    # 阶段检测
    stage = 'group_stage'
    r_lower = round_name.lower()

    knockout_keywords = {
        'final': 'final',
        'semi': 'semi_final', 'semi final': 'semi_final', 'semifinal': 'semi_final',
        'quarter': 'quarter_final', 'quarter final': 'quarter_final', 'quarterfinal': 'quarter_final',
        'round of 16': 'r16', 'last 16': 'r16', '1/8': 'r16', 'octavos': 'r16',
        'round of 8': 'quarter_final', 'last 8': 'quarter_final',
        'r16': 'r16', 'r8': 'quarter_final',
    }
    for kw, stg in knockout_keywords.items():
        if kw in r_lower:
            stage = stg
            break

    # 如果没有round信息但有league信息，用league推断可能的阶段
    if round_name == '' and league in CUP_LEAGUES:
        stage = 'unknown'

    # 回合检测
    leg = 'single_match'
    if '1st leg' in r_lower or 'first leg' in r_lower or 'leg 1' in r_lower or 'ida' in r_lower:
        leg = 'first_leg'
    elif '2nd leg' in r_lower or 'second leg' in r_lower or 'leg 2' in r_lower or 'vuelta' in r_lower:
        leg = 'second_leg'

    # 中立场检测 (决赛、中立场地关键词)
    is_neutral = False
    if stage == 'final':
        is_neutral = True
    neutral_keywords = ['neutral', 'wembley', 'olympiastadion', 'san siro', 'ataturk',
                        'estadio', 'stade de france', 'millennium']
    if any(kw in venue.lower() for kw in neutral_keywords):
        # 只在决赛或特殊场地时标记
        if stage == 'final':
            is_neutral = True

    # 国家队比赛默认中立场(大赛阶段)
    if league in ('world_cup', 'euro', 'copa_america', 'africa_cup_of_nations', 'afc_asian_cup', 'gold_cup'):
        if stage not in ('group_stage', 'unknown'):
            is_neutral = True

    return {
        'stage': stage,
        'leg': leg,
        'is_neutral': is_neutral,
        'is_knockout': stage in ('r16', 'quarter_final', 'semi_final', 'final'),
        'is_two_legged': leg in ('first_leg', 'second_leg'),
        'round_name': round_name,
    }


def calc_cup_motivation(home_team: str, away_team: str,
                        match_data: dict, stage_info: dict,
                        schedule_data: dict = None) -> dict:
    """杯赛动机因子"""
    league = match_data.get('league_standard', '') or match_data.get('league', '')
    prestige = CUP_PRESTIGE.get(league, 0.5)

    home_mot = 0.5 + prestige * 0.2
    away_mot = 0.5 + prestige * 0.2

    # 淘汰赛动机提升
    if stage_info.get('is_knockout'):
        home_mot += 0.1
        away_mot += 0.1

    # 决赛额外动力
    if stage_info.get('stage') == 'final':
        home_mot += 0.15
        away_mot += 0.15

    # 第二回合落后方追分动力
    agg = match_data.get('aggregate_score') or {}
    if stage_info.get('leg') == 'second_leg' and agg:
        home_agg = agg.get('home', 0)
        away_agg = agg.get('away', 0)
        if home_agg < away_agg:
            home_mot += 0.15  # 落后方更拼命
        elif away_agg < home_agg:
            away_mot += 0.15

    # 轮换风险 (7天内比赛数)
    rotation_risk = 0.0
    if schedule_data:
        home_games_week = schedule_data.get('home_games_7d', 1)
        away_games_week = schedule_data.get('away_games_7d', 1)
        if home_games_week >= 3:
            home_mot -= 0.1
            rotation_risk += 0.15
        if away_games_week >= 3:
            away_mot -= 0.1
            rotation_risk += 0.15

    # 小组赛轮换风险 (已出线/已淘汰)
    if stage_info.get('stage') == 'group_stage':
        group_pos = match_data.get('group_position', {})
        if group_pos:
            if group_pos.get('home') in (1, 2):
                home_mot -= 0.05  # 已出线可能轮换
            if group_pos.get('away') in (1, 2):
                away_mot -= 0.05

    # Clamp
    home_mot = max(0.1, min(1.0, home_mot))
    away_mot = max(0.1, min(1.0, away_mot))

    return {
        'home_motivation': round(home_mot, 3),
        'away_motivation': round(away_mot, 3),
        'rotation_risk': round(min(1.0, rotation_risk), 3),
        'prestige': prestige,
    }


def calc_knockout_pressure(stage_info: dict, aggregate_score: dict = None) -> dict:
    """淘汰赛压力因子"""
    result = {
        'home_attack_bias': 0.0,
        'away_attack_bias': 0.0,
        'home_defense_bias': 0.0,
        'away_defense_bias': 0.0,
        'experience_factor': 0.0,
    }

    if not stage_info.get('is_knockout'):
        return result

    # 第二回合落后方进攻倾向提升
    if stage_info.get('leg') == 'second_leg' and aggregate_score:
        home_agg = aggregate_score.get('home', 0)
        away_agg = aggregate_score.get('away', 0)
        if home_agg < away_agg:
            result['home_attack_bias'] = 0.15
            result['home_defense_bias'] = -0.10
        elif away_agg < home_agg:
            result['away_attack_bias'] = 0.15
            result['away_defense_bias'] = -0.10

    # 首回合领先方防守倾向
    if stage_info.get('leg') == 'second_leg' and aggregate_score:
        home_agg = aggregate_score.get('home', 0)
        away_agg = aggregate_score.get('away', 0)
        if home_agg > away_agg:
            result['home_defense_bias'] = 0.10
        elif away_agg > home_agg:
            result['away_defense_bias'] = 0.10

    # 半决赛/决赛经验因子
    if stage_info.get('stage') in ('semi_final', 'final'):
        result['experience_factor'] = 0.10

    return result


def calc_upset_factor(home_elo: float, away_elo: float, stage_info: dict) -> float:
    """爆冷因子: Elo差距大的淘汰赛爆冷概率调整"""
    if not stage_info.get('is_knockout'):
        return 0.0

    elo_diff = abs(home_elo - away_elo)
    if elo_diff < 100:
        return 0.0

    # Elo差越大，淘汰赛爆冷调整越大
    base = min(0.15, (elo_diff - 100) / 1000)

    # 淘汰赛阶段不同
    stage_mult = {
        'r16': 1.0,
        'quarter_final': 1.1,
        'semi_final': 0.9,
        'final': 0.7,
    }.get(stage_info.get('stage', ''), 0.8)

    return round(base * stage_mult, 3)


def adjust_elo_for_cup(home_elo: float, away_elo: float,
                       home_league: str, away_league: str,
                       stage_info: dict) -> Tuple[float, float, int]:
    """调整杯赛Elo: 中立场/跨联赛校准"""
    # 跨联赛强度校准
    home_league_bonus = LEAGUE_STRENGTH.get(home_league, 0)
    away_league_bonus = LEAGUE_STRENGTH.get(away_league, 0)

    adjusted_home = home_elo + home_league_bonus
    adjusted_away = away_elo + away_league_bonus

    # 主场优势调整
    if stage_info.get('is_neutral'):
        home_advantage = 0
    elif stage_info.get('leg') == 'first_leg':
        home_advantage = 80
    elif stage_info.get('leg') == 'second_leg':
        home_advantage = 120
    else:
        home_advantage = 100  # 默认

    adjusted_home += home_advantage / 2  # Elo公式中除以2

    return adjusted_home, adjusted_away, home_advantage


def adjust_poisson_for_cup(stage_info: dict) -> Tuple[float, float]:
    """调整杯赛Poisson基础进球率"""
    stage = stage_info.get('stage', 'group_stage')
    is_neutral = stage_info.get('is_neutral', False)

    # 基础值
    base = {
        'group_stage': (1.40, 1.00),
        'r16': (1.30, 0.90),
        'quarter_final': (1.30, 0.90),
        'semi_final': (1.20, 0.80),
        'final': (1.15, 0.80),
        'unknown': (1.30, 0.95),
    }

    home_xg, away_xg = base.get(stage, (1.30, 0.95))

    # 中立场进一步调整
    if is_neutral:
        avg = (home_xg + away_xg) / 2
        home_xg = avg + 0.05  # 微弱优势
        away_xg = avg - 0.05

    return round(home_xg, 2), round(away_xg, 2)


def get_cup_weights(league_standard: str) -> dict:
    """获取杯赛因子权重"""
    return {
        'elo': 0.25,
        'h2h': 0.20,
        'form': 0.15,
        'cup_motivation': 0.15,
        'poisson': 0.10,
        'home_away': 0.05,
        'cup_context': 0.10,
    }


def calc_cup_confidence(factors_available: dict, stage_info: dict) -> float:
    """计算杯赛分析置信度"""
    conf = 0.0

    if factors_available.get('elo'):
        conf += 0.30
    if factors_available.get('h2h'):
        conf += 0.15
    if factors_available.get('form'):
        conf += 0.15
    if factors_available.get('odds'):
        conf += 0.20

    # 淘汰赛更可预测
    if stage_info.get('is_knockout'):
        conf += 0.10
    else:
        conf += 0.05

    # 中立场降低置信度
    if stage_info.get('is_neutral'):
        conf -= 0.05

    # 跨联赛降低置信度
    if factors_available.get('cross_league'):
        conf -= 0.10

    return round(max(0.05, min(0.85, conf)), 3)
