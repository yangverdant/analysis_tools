"""控球率与反击偏好因素

基于比赛数据推算球队的控球/反击风格：
- 高进球+低失球+主场优势明显 → 控球型
- 低进球+客场成绩不差+低失球 → 防反型
- 其他 → 平衡型
"""

from typing import Dict, Any
from fetchers.common.team_names import normalize_team_name
from .base_factor import BaseFactor


class PossessionCounterFactor(BaseFactor):
    factor = "possession_counter"
    title = "控球率与反击偏好"
    factor_type = "categorical"

    CATEGORIES = ["possession", "counter_attack", "balanced"]

    def extract(self, match_key: str, storage) -> Dict[str, Any]:
        match = self._get_match(match_key, storage)
        if not match or not match.get("home_team"):
            return self._no_data("未找到比赛")

        league = match.get("league_standard") or match.get("league", "")
        season = self._get_season_from_date(match.get("date", ""))
        home = normalize_team_name(match["home_team"])
        away = normalize_team_name(match["away_team"])

        standings = self._get_standings_map(league, storage, season=season)

        hs = standings.get(home, {})
        as_ = standings.get(away, {})

        if not hs and not as_:
            return self._no_data("无积分榜数据")

        home_cat = self._classify(hs, is_home=True)
        away_cat = self._classify(as_, is_home=False)

        # 风格相克分析
        advantage = self._style_advantage(home_cat, away_cat)

        return self._categorical(
            home_category=home_cat,
            away_category=away_cat,
            confidence=0.6 if (hs and as_) else 0.3,
            home_style=home_cat,
            away_style=away_cat,
            style_advantage=advantage,  # "home"/"away"/"neutral"
        )

    def _classify(self, standing: dict, is_home: bool) -> str:
        """根据积分榜数据判断风格"""
        played = standing.get("played", 0) or 0
        if played < 5:
            return "balanced"

        gf = standing.get("goals_for", 0) or 0
        ga = standing.get("goals_against", 0) or 0
        gd = gf - ga
        won = standing.get("won", 0) or 0
        drawn = standing.get("drawn", 0) or 0
        lost = standing.get("lost", 0) or 0

        # 主场数据
        h_played = standing.get("home_played", 0) or 0
        h_won = standing.get("home_won", 0) or 0
        a_played = standing.get("away_played", 0) or 0
        a_won = standing.get("away_won", 0) or 0

        home_wr = h_won / h_played if h_played > 0 else 0.5
        away_wr = a_won / a_played if a_played > 0 else 0.5

        goals_per_game = gf / played if played > 0 else 0
        concede_per_game = ga / played if played > 0 else 0

        # 控球型特征: 进球多+主场胜率高+客场也不差+净胜球大
        if goals_per_game > 1.5 and gd > 10 and home_wr > 0.6:
            return "possession"

        # 防反型特征: 失球少+客场胜率不低+进球不多+主场依赖不强
        if concede_per_game < 1.2 and away_wr >= home_wr * 0.7 and goals_per_game < 1.5:
            return "counter_attack"

        return "balanced"

    def _style_advantage(self, home_style: str, away_style: str) -> str:
        """风格相克分析
        控球 vs 防反: 防反克制控球(客场有利)
        控球 vs 控球: 主场有利
        防反 vs 防反: 中性
        """
        if home_style == "possession" and away_style == "counter_attack":
            return "away"  # 防反克制控球
        if home_style == "counter_attack" and away_style == "possession":
            return "home"
        if home_style == "possession" and away_style == "possession":
            return "home"  # 对攻主场优势
        return "neutral"