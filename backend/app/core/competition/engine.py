"""
CompetitionRuleEngine: 8种赛事类型分类 + 规则引擎
MatchProfile: 俱乐部/国家队分线的赛事画像

类型体系:
  俱乐部线: LEAGUE, CUP, SUPER_CUP, PLAYOFF
  国家队线: WC_QUALIFIER, NATIONS_LEAGUE, FRIENDLY_INTL, TOURNAMENT_INTL
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple


# ═══════════════════════════════════════════
# 1. 赛事类型枚举
# ═══════════════════════════════════════════

class CompetitionType(Enum):
    """8种赛事类型"""

    # ── 俱乐部线 ──
    LEAGUE = "league"                    # 联赛 (EPL, La Liga, 中超)
    CUP = "cup"                          # 杯赛 (FA Cup, 国王杯, 足协杯)
    SUPER_CUP = "super_cup"              # 超级杯 (Community Shield, 西超杯)
    PLAYOFF = "playoff"                  # 升降级附加赛 / 淘汰赛末段

    # ── 国家队线 ──
    WC_QUALIFIER = "wc_qualifier"        # 世预赛
    NATIONS_LEAGUE = "nations_league"    # 欧国联/亚国联
    FRIENDLY_INTL = "friendly_intl"      # 国际友谊赛
    TOURNAMENT_INTL = "tournament_intl"  # 大赛正赛 (世界杯/欧洲杯/美洲杯/亚洲杯)


class ParticipantType(Enum):
    """参赛方类型"""
    CLUB = "club"
    NATIONAL = "national"


class MatchPhase(Enum):
    """赛事阶段"""
    GROUP = "group"          # 小组赛
    KNOCKOUT = "knockout"    # 淘汰赛
    FINAL = "final"          # 决赛
    QUALIFYING = "qualifying"  # 预选赛
    LEAGUE_PHASE = "league_phase"  # 联赛阶段(欧国联等)


# ═══════════════════════════════════════════
# 2. 赛事画像 MatchProfile
# ═══════════════════════════════════════════

@dataclass
class MatchProfile:
    """赛事画像 — 驱动分析路由的完整上下文"""

    # ── 基础信息 ──
    competition_type: CompetitionType
    participant_type: ParticipantType
    match_phase: MatchPhase = MatchPhase.LEAGUE_PHASE

    # ── 分线标识 ──
    is_national: bool = False
    is_club: bool = True

    # ── 赛事规则属性 ──
    has_two_legs: bool = False       # 两回合制
    has_away_goals: bool = False      # 客场进球规则
    is_neutral_venue: bool = False    # 中立场
    allows_draw: bool = True         # 是否允许平局

    # ── 动机/风险因子 ──
    motivation_weight: float = 0.5   # 动机因子权重 0~1
    upset_risk: float = 0.0         # 冷门风险 0~1
    draw_boost: float = 0.0         # 平局增幅 -0.1~0.3
    rotation_risk: float = 0.0      # 轮换风险 0~1

    # ── 来源信息 ──
    league_name: str = ""
    league_id: Optional[int] = None
    home_team: str = ""
    away_team: str = ""
    match_id: Optional[int] = None

    # ── 标签(用于日志和调试) ──
    tags: List[str] = field(default_factory=list)

    @property
    def line(self) -> str:
        """分线标识: 'national' or 'club'"""
        return "national" if self.is_national else "club"

    def tag(self, tag: str) -> "MatchProfile":
        """链式添加标签"""
        self.tags.append(tag)
        return self

    def to_dict(self) -> Dict[str, Any]:
        """序列化为字典(供日志/调试)"""
        # CN translations kept in lockstep with the English enum values so the
        # user-facing report doesn't mix Chinese sentences with raw English
        # like "friendly_intl" / "national" / "league_phase".
        from ..cn_labels import (
            competition_type_cn, participant_type_cn, match_phase_cn,
        )
        return {
            "competition_type": self.competition_type.value,
            "competition_type_cn": competition_type_cn(self.competition_type.value),
            "participant_type": self.participant_type.value,
            "participant_type_cn": participant_type_cn(self.participant_type.value),
            "match_phase": self.match_phase.value,
            "match_phase_cn": match_phase_cn(self.match_phase.value),
            "line": self.line,
            "has_two_legs": self.has_two_legs,
            "is_neutral_venue": self.is_neutral_venue,
            "allows_draw": self.allows_draw,
            "motivation_weight": self.motivation_weight,
            "upset_risk": self.upset_risk,
            "draw_boost": self.draw_boost,
            "rotation_risk": self.rotation_risk,
            "tags": self.tags,
        }


# ═══════════════════════════════════════════
# 3. 分类规则引擎
# ═══════════════════════════════════════════

class CompetitionRuleEngine:
    """
    赛事分类引擎 — 从联赛名/参赛方推断赛事类型+规则

    优先级:
      1. DB字段 (leagues.competition_type / leagues.participant_type)
      2. 关键词匹配 (中英文联赛名)
      3. 参赛方推断 (team_type=NATIONAL → 国家队线)
      4. 默认回退 → LEAGUE / CLUB
    """

    # ── 关键词映射表 ──

    # 国家队大赛正赛
    TOURNAMENT_INTL_KEYWORDS = {
        "世界杯", "世杯赛", "World Cup", "FIFA World Cup",
        "欧洲杯", "Euro", "UEFA Euro",
        "美洲杯", "Copa America", "Copa América",
        "亚洲杯", "AFC Asian Cup",
        "非洲杯", "Africa Cup of Nations", "AFCON",
        "金杯赛", "Gold Cup", "CONCACAF Gold Cup",
        "奥运会", "Olympics", "Olympic",
        "欧青赛", "U21 Euro", "Under-21",
        "世青赛", "U20 World Cup", "FIFA U-20",
    }

    # 世预赛
    WC_QUALIFIER_KEYWORDS = {
        "世预赛", "世界杯预选赛", "世预", "World Cup Qualif",
        "WCQ", "World Cup Qualifying",
        "世预南美", "世预亚洲", "世预欧洲", "世预非洲", "世预中北美",
        "WC Qualif", "Qualification World Cup",
    }

    # 欧国联 / 亚国联
    NATIONS_LEAGUE_KEYWORDS = {
        "欧国联", "Nations League", "UEFA Nations League",
        "亚国联", "AFC Nations League",
    }

    # 国际友谊赛
    FRIENDLY_INTL_KEYWORDS = {
        "国际友谊赛", "友谊赛", "Friendly", "International Friendly",
        "Int. Friendly", "Friendlies",
    }

    # 杯赛 (俱乐部)
    CUP_KEYWORDS = {
        "杯赛", "足总杯", "FA Cup", "Copa del Rey", "国王杯",
        "德国杯", "DFB-Pokal", "意大利杯", "Coppa Italia",
        "法国杯", "Coupe de France", "足协杯", "CFA Cup",
        "亚冠", "AFC Champions", "欧冠", "Champions League",
        "欧联", "Europa League", "欧协联", "Conference League",
        "解放者杯", "Copa Libertadores", "南美杯", "Copa Sudamericana",
        "联赛杯", "Carabao Cup", "EFL Cup", "League Cup",
        "天皇杯", "Emperor's Cup", "荷兰杯", "KNVB Cup",
        "葡萄牙杯", "Taça de Portugal",
    }

    # 超级杯
    SUPER_CUP_KEYWORDS = {
        "超级杯", "Super Cup", "Community Shield",
        "西超杯", "Supercopa", "意超杯", "Supercoppa",
        "德超杯", "Supercup", "法超杯", "Trophée des Champions",
        "欧超杯", "UEFA Super Cup",
    }

    # 附加赛 / 淘汰末段
    PLAYOFF_KEYWORDS = {
        "附加赛", "Playoff", "Play-offs", "Playoff",
        "升降级", "Relegation", "Promotion",
    }

    # ── 两回合制杯赛 ──
    TWO_LEG_COMPETITIONS = {
        "Champions League", "Europa League", "Conference League",
        "Copa Libertadores", "Copa Sudamericana",
        "WCQ",  # 世预赛多数两回合
    }

    # ── 中立场赛事 ──
    NEUTRAL_VENUE_KEYWORDS = {
        "超级杯", "Super Cup", "Community Shield",
        "决赛", "Final",
        "世界杯", "World Cup", "欧洲杯", "Euro",
        "美洲杯", "Copa America",
        "亚洲杯", "Asian Cup",
        "奥运会", "Olympics",
    }

    # ── 国家队赛事(不允许平局的淘汰赛) ──
    NO_DRAW_PHASES = {MatchPhase.FINAL, MatchPhase.KNOCKOUT}

    def classify(
        self,
        league_name: str = "",
        competition_type_db: Optional[str] = None,
        participant_type_db: Optional[str] = None,
        match_phase: Optional[str] = None,
        is_neutral_venue: bool = False,
        home_team_type: Optional[str] = None,
        away_team_type: Optional[str] = None,
    ) -> MatchProfile:
        """
        分类一场比赛 → 返回MatchProfile

        参数:
            league_name: 联赛名称(中文或英文)
            competition_type_db: DB中leagues.competition_type字段
            participant_type_db: DB中leagues.participant_type字段
            match_phase: 比赛阶段(group/knockout/final等)
            is_neutral_venue: 是否中立场
            home_team_type: 主队team_type (club/national)
            away_team_type: 客队team_type (club/national)
        """

        # Step 1: 判断参赛方类型
        participant_type = self._infer_participant_type(
            participant_type_db, home_team_type, away_team_type, league_name
        )
        is_national = participant_type == ParticipantType.NATIONAL

        # Step 2: 判断赛事类型
        if competition_type_db and competition_type_db in [e.value for e in CompetitionType]:
            comp_type = CompetitionType(competition_type_db)
        else:
            comp_type = self._classify_by_keywords(league_name, is_national)

        # 热身赛识别: 大赛正赛应有明确match_phase, 无phase且league_name含大赛关键词
        # 数据源(sporttery/oddsfe)常把热身赛标为"世界杯", 需要此降级避免draw_boost偏低
        if (
            comp_type == CompetitionType.TOURNAMENT_INTL
            and not match_phase
            and is_national
        ):
            comp_type = CompetitionType.FRIENDLY_INTL

        # Step 3: 判断比赛阶段
        phase = self._infer_phase(match_phase, comp_type)

        # Step 4: 构建MatchProfile
        profile = MatchProfile(
            competition_type=comp_type,
            participant_type=participant_type,
            match_phase=phase,
            is_national=is_national,
            is_club=not is_national,
            is_neutral_venue=is_neutral_venue or self._is_neutral_venue(league_name, phase),
            league_name=league_name,
        )

        # Step 5: 应用赛事规则
        self._apply_rules(profile)

        return profile

    def _infer_participant_type(
        self,
        participant_type_db: Optional[str],
        home_team_type: Optional[str],
        away_team_type: Optional[str],
        league_name: str,
    ) -> ParticipantType:
        """推断参赛方类型"""

        # DB字段优先
        if participant_type_db:
            pt = participant_type_db.lower()
            if "national" in pt or "nation" in pt or "国际" in pt:
                return ParticipantType.NATIONAL
            if "club" in pt or "俱乐部" in pt:
                return ParticipantType.CLUB

        # 参赛方team_type推断
        if home_team_type and away_team_type:
            if home_team_type.lower() in ("national", "nation") or away_team_type.lower() in ("national", "nation"):
                return ParticipantType.NATIONAL

        # 关键词推断 — 国家队赛事名
        intl_indicators = {
            "世界杯", "世预赛", "欧洲杯", "美洲杯", "亚洲杯", "非洲杯",
            "欧国联", "亚国联", "国际友谊赛", "友谊赛",
            "World Cup", "Euro", "Copa America", "Asian Cup",
            "Nations League", "Friendly",
        }
        for kw in intl_indicators:
            if kw in league_name:
                return ParticipantType.NATIONAL

        return ParticipantType.CLUB

    def _classify_by_keywords(self, league_name: str, is_national: bool) -> CompetitionType:
        """通过关键词匹配赛事类型"""

        name = league_name

        # 国家队线
        if is_national:
            if self._match_keywords(name, self.TOURNAMENT_INTL_KEYWORDS):
                return CompetitionType.TOURNAMENT_INTL
            if self._match_keywords(name, self.WC_QUALIFIER_KEYWORDS):
                return CompetitionType.WC_QUALIFIER
            if self._match_keywords(name, self.NATIONS_LEAGUE_KEYWORDS):
                return CompetitionType.NATIONS_LEAGUE
            if self._match_keywords(name, self.FRIENDLY_INTL_KEYWORDS):
                return CompetitionType.FRIENDLY_INTL
            # 国家队但关键词都不匹配 → 默认友谊赛
            return CompetitionType.FRIENDLY_INTL

        # 俱乐部线
        if self._match_keywords(name, self.SUPER_CUP_KEYWORDS):
            return CompetitionType.SUPER_CUP
        if self._match_keywords(name, self.PLAYOFF_KEYWORDS):
            return CompetitionType.PLAYOFF
        if self._match_keywords(name, self.CUP_KEYWORDS):
            return CompetitionType.CUP

        return CompetitionType.LEAGUE

    def _infer_phase(self, match_phase: Optional[str], comp_type: CompetitionType) -> MatchPhase:
        """推断比赛阶段"""

        if match_phase:
            phase_map = {
                "group": MatchPhase.GROUP,
                "小组赛": MatchPhase.GROUP,
                "knockout": MatchPhase.KNOCKOUT,
                "淘汰赛": MatchPhase.KNOCKOUT,
                "round_of_16": MatchPhase.KNOCKOUT,
                "quarter_final": MatchPhase.KNOCKOUT,
                "semi_final": MatchPhase.KNOCKOUT,
                "quarter": MatchPhase.KNOCKOUT,
                "semi": MatchPhase.KNOCKOUT,
                "final": MatchPhase.FINAL,
                "决赛": MatchPhase.FINAL,
                "qualifying": MatchPhase.QUALIFYING,
                "预选赛": MatchPhase.QUALIFYING,
                "league_phase": MatchPhase.LEAGUE_PHASE,
                "联赛阶段": MatchPhase.LEAGUE_PHASE,
            }
            return phase_map.get(match_phase.lower(), MatchPhase.LEAGUE_PHASE)

        # 默认阶段
        phase_defaults = {
            CompetitionType.LEAGUE: MatchPhase.LEAGUE_PHASE,
            CompetitionType.CUP: MatchPhase.KNOCKOUT,
            CompetitionType.SUPER_CUP: MatchPhase.FINAL,
            CompetitionType.PLAYOFF: MatchPhase.KNOCKOUT,
            CompetitionType.WC_QUALIFIER: MatchPhase.LEAGUE_PHASE,
            CompetitionType.NATIONS_LEAGUE: MatchPhase.LEAGUE_PHASE,
            CompetitionType.FRIENDLY_INTL: MatchPhase.LEAGUE_PHASE,
            CompetitionType.TOURNAMENT_INTL: MatchPhase.GROUP,
        }
        return phase_defaults.get(comp_type, MatchPhase.LEAGUE_PHASE)

    def _is_neutral_venue(self, league_name: str, phase: MatchPhase) -> bool:
        """判断是否中立场"""
        if phase in (MatchPhase.FINAL,):
            return True
        return self._match_keywords(league_name, self.NEUTRAL_VENUE_KEYWORDS)

    def _apply_rules(self, profile: MatchProfile) -> None:
        """根据赛事类型设置规则属性"""

        ct = profile.competition_type
        mp = profile.match_phase

        # ── 两回合制 ──
        if self._match_keywords(profile.league_name, self.TWO_LEG_COMPETITIONS):
            profile.has_two_legs = True
        if ct == CompetitionType.WC_QUALIFIER and mp != MatchPhase.FINAL:
            # 世预赛多数两回合(除了最终轮)
            profile.has_two_legs = True

        # ── 客场进球规则(已基本废除, 保留字段) ──
        profile.has_away_goals = False

        # ── 是否允许平局 ──
        # 淘汰赛次回合+决赛: 不允许平局(需加时/点球)
        if mp in self.NO_DRAW_PHASES and ct not in (CompetitionType.LEAGUE, CompetitionType.NATIONS_LEAGUE):
            profile.allows_draw = False

        # ── 动机权重 ──
        motivation_map = {
            CompetitionType.LEAGUE: 0.7,
            CompetitionType.CUP: 0.6,
            CompetitionType.SUPER_CUP: 0.3,
            CompetitionType.PLAYOFF: 0.9,
            CompetitionType.WC_QUALIFIER: 0.8,
            CompetitionType.NATIONS_LEAGUE: 0.5,
            CompetitionType.FRIENDLY_INTL: 0.2,
            CompetitionType.TOURNAMENT_INTL: 0.9,
        }
        profile.motivation_weight = motivation_map.get(ct, 0.5)

        # 决赛阶段动机最高
        if mp == MatchPhase.FINAL:
            profile.motivation_weight = min(1.0, profile.motivation_weight + 0.1)

        # ── 冷门风险 ──
        upset_map = {
            CompetitionType.LEAGUE: 0.1,
            CompetitionType.CUP: 0.3,
            CompetitionType.SUPER_CUP: 0.15,
            CompetitionType.PLAYOFF: 0.2,
            CompetitionType.WC_QUALIFIER: 0.25,
            CompetitionType.NATIONS_LEAGUE: 0.2,
            CompetitionType.FRIENDLY_INTL: 0.35,
            CompetitionType.TOURNAMENT_INTL: 0.2,
        }
        profile.upset_risk = upset_map.get(ct, 0.1)

        # ── 平局增幅 ──
        draw_map = {
            CompetitionType.LEAGUE: 0.0,
            CompetitionType.CUP: 0.02,
            CompetitionType.SUPER_CUP: 0.0,
            CompetitionType.PLAYOFF: -0.05,
            CompetitionType.WC_QUALIFIER: 0.03,
            CompetitionType.NATIONS_LEAGUE: 0.05,
            CompetitionType.FRIENDLY_INTL: 0.08,
            CompetitionType.TOURNAMENT_INTL: 0.02,
        }
        profile.draw_boost = draw_map.get(ct, 0.0)

        # 友谊赛大幅提平局
        if ct == CompetitionType.FRIENDLY_INTL:
            profile.draw_boost = 0.08
            profile.tag("friendly_draw_boost")

        # 淘汰赛/决赛降平局
        if mp in (MatchPhase.KNOCKOUT, MatchPhase.FINAL) and not profile.allows_draw:
            profile.draw_boost = -0.1
            profile.tag("knockout_no_draw")

        # ── 轮换风险 ──
        rotation_map = {
            CompetitionType.LEAGUE: 0.0,
            CompetitionType.CUP: 0.15,
            CompetitionType.SUPER_CUP: 0.1,
            CompetitionType.PLAYOFF: 0.0,
            CompetitionType.WC_QUALIFIER: 0.0,
            CompetitionType.NATIONS_LEAGUE: 0.05,
            CompetitionType.FRIENDLY_INTL: 0.4,
            CompetitionType.TOURNAMENT_INTL: 0.0,
        }
        profile.rotation_risk = rotation_map.get(ct, 0.0)

    @staticmethod
    def _match_keywords(name: str, keywords: set) -> bool:
        """检查name是否包含关键词集合中的任一关键词"""
        if not name:
            return False
        name_lower = name.lower()
        for kw in keywords:
            if kw.lower() in name_lower:
                return True
        return False


# ═══════════════════════════════════════════
# 4. 便捷函数
# ═══════════════════════════════════════════

_engine = CompetitionRuleEngine()


def classify_match(
    league_name: str = "",
    competition_type_db: Optional[str] = None,
    participant_type_db: Optional[str] = None,
    match_phase: Optional[str] = None,
    is_neutral_venue: bool = False,
    home_team_type: Optional[str] = None,
    away_team_type: Optional[str] = None,
) -> MatchProfile:
    """便捷函数: 分类一场比赛"""
    return _engine.classify(
        league_name=league_name,
        competition_type_db=competition_type_db,
        participant_type_db=participant_type_db,
        match_phase=match_phase,
        is_neutral_venue=is_neutral_venue,
        home_team_type=home_team_type,
        away_team_type=away_team_type,
    )
