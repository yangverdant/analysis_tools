"""比赛上下文构建器 — 5维度分析核心

5大维度:
1. 雇佣关系 — 友谊赛谁花钱请谁
2. 球迷效应 — 客场球迷数量影响
3. 动机需求 — 球队当前需要什么结果
4. 疲劳临界 — 球员级赛季负荷(由fatigue_tracker处理)
5. 场地特殊 — 高原/气候/时差
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional
from fetchers.pre_match.config import (
    WC_HOSTS_2026, HIGH_ALTITUDE_CITIES, CROSS_BORDER_FAN_PAIRS,
    FRIENDLY_TYPE_RULES, FATIGUE_THRESHOLDS
)
from fetchers.fifa_ranking import get_team_ranking, get_ranking_diff


@dataclass
class EmployerInfo:
    """雇佣关系信息"""
    employer: str  # 'home' / 'away' / 'mutual' / 'unknown'
    employee: str  # 被雇方
    confidence: float  # 0.0-1.0
    reason: str  # 推断理由


@dataclass
class FanEffect:
    """球迷效应"""
    home_advantage_level: str  # 'strong' / 'moderate' / 'neutral' / 'weakened' / 'reversed'
    away_fan_ratio: float  # 客场球迷占比估计
    cross_border_boost: bool  # 是否有跨境球迷加成
    reason: str


@dataclass
class MotivationInfo:
    """动机需求"""
    level: str  # 'must_win' / 'high' / 'medium' / 'low' / 'exhibition'
    need: str  # 'confidence' / 'display' / 'trial' / 'rest' / 'none'
    reason: str


@dataclass
class VenueSpecial:
    """场地特殊性"""
    altitude_m: Optional[int]
    altitude_effect: str  # 'extreme' / 'high' / 'moderate' / 'none'
    climate: Optional[str]
    timezone_diff: Optional[int]
    is_home_familiar: bool  # 主队是否熟悉场地


@dataclass
class MatchContext:
    """完整比赛上下文"""
    home_team: str
    away_team: str
    date: str
    league: str
    friendly_type: str  # 'wc_warmup' / 'post_season' / 'pre_season' / 'mid_season' / 'not_friendly'

    employer: Optional[EmployerInfo] = None
    fan_effect: Optional[FanEffect] = None
    home_motivation: Optional[MotivationInfo] = None
    away_motivation: Optional[MotivationInfo] = None
    venue_special: Optional[VenueSpecial] = None

    # 综合评估
    home_advantage_net: float = 0.0  # -1.0 ~ 1.0, 正值=主队优势
    key_factors: list = field(default_factory=list)  # 关键因素列表


class MatchContextBuilder:
    """比赛上下文构建器"""

    def __init__(self):
        self.wc_hosts = set(WC_HOSTS_2026)
        self.altitude_cities = HIGH_ALTITUDE_CITIES
        self.fan_pairs = CROSS_BORDER_FAN_PAIRS

    def build_context(
        self,
        home_team: str,
        away_team: str,
        date: str,
        league: str,
        venue_city: Optional[str] = None,
        recent_form: Optional[dict] = None
    ) -> MatchContext:
        """构建完整比赛上下文"""

        friendly_type = self._infer_friendly_type(league, date)

        context = MatchContext(
            home_team=home_team,
            away_team=away_team,
            date=date,
            league=league,
            friendly_type=friendly_type
        )

        # 1. 雇佣关系推断
        context.employer = self.infer_employer(
            home_team, away_team, league, date, recent_form
        )

        # 2. 球迷效应
        context.fan_effect = self.estimate_fan_effect(
            home_team, away_team, venue_city
        )

        # 3. 动机分析
        context.home_motivation = self.analyze_motivation(
            home_team, league, date, recent_form, is_home=True,
            employer_info=context.employer
        )
        context.away_motivation = self.analyze_motivation(
            away_team, league, date, recent_form, is_home=False,
            employer_info=context.employer
        )

        # 4. 场地特殊性
        context.venue_special = self.get_venue_specials(
            venue_city, home_team, away_team
        )

        # 5. 综合评估
        context.home_advantage_net = self._calculate_net_advantage(context)
        context.key_factors = self._extract_key_factors(context)

        return context

    def _infer_friendly_type(self, league: str, date: str) -> str:
        """推断友谊赛类型"""
        league_lower = league.lower()

        if 'friendly' not in league_lower and 'international' not in league_lower:
            return 'not_friendly'

        try:
            month = datetime.strptime(date, '%Y-%m-%d').month
        except:
            return 'mid_season'

        # 世界杯前热身(5-6月)
        if month in [5, 6]:
            return 'wc_warmup'
        # 赛季结束友谊赛(5-7月)
        elif month in [5, 6, 7]:
            return 'post_season'
        # 赛季前热身(7-8月)
        elif month in [7, 8]:
            return 'pre_season'
        # 赛季中友谊赛
        else:
            return 'mid_season'

    def infer_employer(
        self,
        home_team: str,
        away_team: str,
        league: str,
        date: str,
        recent_form: Optional[dict] = None
    ) -> EmployerInfo:
        """推断友谊赛雇佣关系

        规则:
        1. WC东道主主场 → 东道主是雇主,且会认真打
        2. 主场强队(排名高) → 主队是雇主(安排比赛),客队是被请来陪练的
        3. 主场连败 → 主队是雇主(找自信)
        4. 无明显特征 → mutual(双方都需要热身)
        """

        if 'friendly' not in league.lower():
            return EmployerInfo('unknown', 'unknown', 0.0, '非友谊赛')

        # 规则1: WC东道主主场
        if home_team in self.wc_hosts:
            return EmployerInfo(
                employer='home',
                employee=away_team,
                confidence=0.9,
                reason=f'{home_team}是WC东道主,主场友谊赛必认真打'
            )

        # 规则2: 排名差距 — 主场强队是雇主(安排比赛邀请弱队来热身)
        try:
            home_rank_data = get_team_ranking(home_team)
            away_rank_data = get_team_ranking(away_team)
            home_rank = home_rank_data['rank'] if isinstance(home_rank_data, dict) else home_rank_data
            away_rank = away_rank_data['rank'] if isinstance(away_rank_data, dict) else away_rank_data
            rank_diff = abs(home_rank - away_rank)

            if rank_diff > 20:
                if home_rank < away_rank:  # 主队排名高(强) → 主队是雇主
                    return EmployerInfo(
                        employer='home',
                        employee=away_team,
                        confidence=0.7,
                        reason=f'{home_team}(#{home_rank})主场安排热身,请{away_team}(#{away_rank})陪练'
                    )
                else:  # 客队排名高(强) → 客队被请来陪练,但强队也会认真打
                    return EmployerInfo(
                        employer='home',
                        employee=away_team,
                        confidence=0.6,
                        reason=f'{home_team}(#{home_rank})主场请{away_team}(#{away_rank})来热身,强队也有动机'
                    )
        except:
            pass  # 排名获取失败,继续其他规则

        # 规则3: 主场连败找自信
        if recent_form and recent_form.get('home_consecutive_losses', 0) >= 4:
            return EmployerInfo(
                employer='home',
                employee=away_team,
                confidence=0.8,
                reason=f'{home_team}连败{recent_form["home_consecutive_losses"]}场,花钱找自信'
            )

        # 规则4: 默认互惠
        return EmployerInfo(
            employer='mutual',
            employee='mutual',
            confidence=0.5,
            reason='双方都需要热身,互惠安排'
        )

    def estimate_fan_effect(
        self,
        home_team: str,
        away_team: str,
        venue_city: Optional[str] = None
    ) -> FanEffect:
        """估算球迷效应

        规则:
        1. 跨境球迷配对 → 客场球迷占比提升
        2. 历史移民国家 → 大量客场球迷
        """

        # 查找跨境球迷配对
        away_fan_ratio = 0.05  # 默认5%客场球迷
        cross_border_boost = False
        reason = '常规主场优势'

        # 检查是否有跨境球迷配对
        pair_key = (home_team, away_team)
        if pair_key in self.fan_pairs:
            away_fan_ratio = self.fan_pairs[pair_key]
            cross_border_boost = True
            reason = f'{away_team}球迷跨境支持,占比约{away_fan_ratio*100:.0f}%'

        # 判断主场优势级别
        if away_fan_ratio >= 0.30:
            level = 'reversed'
        elif away_fan_ratio >= 0.20:
            level = 'weakened'
        elif away_fan_ratio >= 0.10:
            level = 'neutral'
        elif away_fan_ratio >= 0.05:
            level = 'moderate'
        else:
            level = 'strong'

        return FanEffect(
            home_advantage_level=level,
            away_fan_ratio=away_fan_ratio,
            cross_border_boost=cross_border_boost,
            reason=reason
        )

    def analyze_motivation(
        self,
        team: str,
        league: str,
        date: str,
        recent_form: Optional[dict],
        is_home: bool,
        employer_info: Optional[EmployerInfo] = None
    ) -> MotivationInfo:
        """分析球队动机

        规则(按优先级):
        1. WC东道主 → must_win, 需要展示
        2. WC热身期(5-6月) → medium, 试阵热身(不是度假!)
        3. 连败找自信 → high, 需要信心
        4. 被雇方陪练 → low, 不拼命赢
        5. 赛季结束非热身期 → low
        """

        if 'friendly' not in league.lower():
            return MotivationInfo('medium', 'none', '非友谊赛,正常动机')

        # 规则1: WC东道主
        if team in self.wc_hosts:
            return MotivationInfo(
                level='must_win',
                need='display',
                reason=f'{team}是WC东道主,必须认真打展示实力'
            )

        # 规则2: WC热身期 → medium(不是度假!)
        friendly_type = self._infer_friendly_type(league, date)
        if friendly_type == 'wc_warmup':
            # WC级别球队 → medium(认真试阵)
            wc_teams = set(WC_HOSTS_2026) | {
                'France', 'Germany', 'Spain', 'England', 'Italy', 'Portugal',
                'Netherlands', 'Belgium', 'Croatia', 'Brazil', 'Argentina',
                'Uruguay', 'Colombia', 'Denmark', 'Switzerland', 'Austria',
                'Serbia', 'Poland', 'Sweden', 'Ukraine', 'Turkey', 'Morocco',
                'Japan', 'South Korea', 'United States', 'Mexico', 'Canada',
            }
            if team in wc_teams:
                return MotivationInfo(
                    level='medium',
                    need='trial',
                    reason=f'{team}WC热身期,认真试阵磨合'
                )
            else:
                return MotivationInfo(
                    level='low',
                    need='trial',
                    reason=f'{team}WC热身期陪练,不会全力'
                )

        # 规则3: 连败找自信
        if recent_form:
            losses = recent_form.get(f'{"home" if is_home else "away"}_consecutive_losses', 0)
            if losses >= 4:
                return MotivationInfo(
                    level='high',
                    need='confidence',
                    reason=f'{team}连败{losses}场,急需找回自信'
                )

        # 规则4: 被雇方
        if employer_info:
            if employer_info.employer == 'home' and not is_home:
                return MotivationInfo(
                    level='low',
                    need='none',
                    reason=f'{team}是被雇陪练方,不会拼命赢雇主'
                )
            elif employer_info.employer == 'away' and is_home:
                return MotivationInfo(
                    level='low',
                    need='none',
                    reason=f'{team}是被雇陪练方,不会拼命赢雇主'
                )

        # 规则5: 赛季结束非热身期
        try:
            month = datetime.strptime(date, '%Y-%m-%d').month
            if month in [5, 6, 7]:
                return MotivationInfo(
                    level='low',
                    need='rest',
                    reason='赛季结束,度假心理'
                )
        except:
            pass

        # 规则5: 大赛前试阵
        friendly_type = self._infer_friendly_type(league, date)
        if friendly_type == 'wc_warmup':
            return MotivationInfo(
                level='medium',
                need='trial',
                reason='世界杯前试阵热身'
            )

        return MotivationInfo('medium', 'trial', '常规友谊赛动机')

    def get_venue_specials(
        self,
        venue_city: Optional[str],
        home_team: str,
        away_team: str
    ) -> VenueSpecial:
        """获取场地特殊性

        主要关注高原效应
        """

        if not venue_city:
            return VenueSpecial(
                altitude_m=None,
                altitude_effect='none',
                climate=None,
                timezone_diff=None,
                is_home_familiar=True
            )

        altitude = self.altitude_cities.get(venue_city)

        if altitude is None:
            # 尝试模糊匹配
            for city, alt in self.altitude_cities.items():
                if city.lower() in venue_city.lower() or venue_city.lower() in city.lower():
                    altitude = alt
                    break

        # 判断高原效应级别
        if altitude and altitude >= 2000:
            effect = 'extreme'
        elif altitude and altitude >= 1500:
            effect = 'high'
        elif altitude and altitude >= 1000:
            effect = 'moderate'
        else:
            effect = 'none'

        # 判断主队是否熟悉高原
        home_familiar = False
        if altitude and altitude >= 1500:
            # 主队来自高原国家则熟悉
            high_altitude_teams = ['Mexico', 'Bolivia', 'Colombia', 'Ecuador', 'Peru']
            if home_team in high_altitude_teams:
                home_familiar = True

        return VenueSpecial(
            altitude_m=altitude,
            altitude_effect=effect,
            climate=None,
            timezone_diff=None,
            is_home_familiar=home_familiar
        )

    def _calculate_net_advantage(self, context: MatchContext) -> float:
        """计算净主场优势 (-1.0 ~ 1.0)"""

        advantage = 0.0

        # 球迷效应
        if context.fan_effect:
            level_map = {
                'strong': 0.3,
                'moderate': 0.2,
                'neutral': 0.0,
                'weakened': -0.15,
                'reversed': -0.3
            }
            advantage += level_map.get(context.fan_effect.home_advantage_level, 0.0)

        # 动机差异
        if context.home_motivation and context.away_motivation:
            level_map = {'must_win': 0.25, 'high': 0.15, 'medium': 0.0, 'low': -0.1, 'exhibition': -0.15}
            home_m = level_map.get(context.home_motivation.level, 0.0)
            away_m = level_map.get(context.away_motivation.level, 0.0)
            advantage += (home_m - away_m) * 0.5

        # 高原效应
        if context.venue_special and context.venue_special.altitude_effect != 'none':
            if context.venue_special.is_home_familiar:
                advantage += 0.2  # 主队熟悉高原
            else:
                advantage -= 0.1  # 客队不适应高原

        # 雇佣关系
        if context.employer and context.employer.employer == 'home':
            if context.home_motivation and context.home_motivation.level in ['must_win', 'high']:
                advantage += 0.15  # 雇主认真打
            else:
                advantage -= 0.1  # 雇主只是试阵

        return max(-1.0, min(1.0, advantage))

    def _extract_key_factors(self, context: MatchContext) -> list:
        """提取关键因素列表"""

        factors = []

        if context.employer and context.employer.confidence >= 0.7:
            factors.append(f"雇佣关系: {context.employer.reason}")

        if context.fan_effect and context.fan_effect.away_fan_ratio >= 0.15:
            factors.append(f"球迷效应: {context.fan_effect.reason}")

        if context.home_motivation and context.home_motivation.level in ['must_win', 'high']:
            factors.append(f"主队动机: {context.home_motivation.reason}")

        if context.away_motivation and context.away_motivation.level in ['must_win', 'high']:
            factors.append(f"客队动机: {context.away_motivation.reason}")

        if context.venue_special and context.venue_special.altitude_effect in ['extreme', 'high']:
            factors.append(f"高原效应: 海拔{context.venue_special.altitude_m}m")

        return factors
