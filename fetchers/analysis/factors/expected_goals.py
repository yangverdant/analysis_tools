"""xG预期进球因素"""

import json
from typing import Dict, Any
from fetchers.common.team_names import normalize_team_name
from .base_factor import BaseFactor


class ExpectedGoalsFactor(BaseFactor):
    factor = "expected_goals"
    title = "预期进球xG"
    factor_type = "numeric"

    def extract(self, match_key: str, storage) -> Dict[str, Any]:
        match = self._get_match(match_key, storage)
        if not match or not match.get("home_team"):
            return self._no_data("未找到比赛")

        home = normalize_team_name(match["home_team"])
        away = normalize_team_name(match["away_team"])
        league = match.get("league_standard", "")

        # 尝试从 standings 获取进球数据做简化xG
        standings = self._get_standings_map(league, storage) if league else {}
        hs = standings.get(home)
        as_ = standings.get(away)

        if not hs or not as_:
            return self._no_data("无积分榜数据用于推算xG")

        hp = int(hs.get("played", 1))
        ap = int(as_.get("played", 1))
        if hp == 0 or ap == 0:
            return self._no_data("比赛场次为0")

        # 简化xG = 场均进球 × 对手场均失球 / 联赛场均进球
        hgf = int(hs.get("goals_for", 0))
        hga = int(hs.get("goals_against", 0))
        agf = int(as_.get("goals_for", 0))
        aga = int(as_.get("goals_against", 0))

        home_xg = round((hgf/hp) * (aga/ap) / max((hgf+hga)/(hp*2), 0.5) * (hgf/hp), 2) if hp and ap else 0
        away_xg = round((agf/ap) * (hga/hp) / max((agf+aga)/(ap*2), 0.5) * (agf/ap), 2) if hp and ap else 0

        return self._numeric(
            home_value=home_xg,
            away_value=away_xg,
            unit="xG(简化推算)",
            higher_is_better=True,
            confidence=0.4,
            method="standing_based_estimate",
            home_avg_gf=round(hgf/hp, 2),
            home_avg_ga=round(hga/hp, 2),
            away_avg_gf=round(agf/ap, 2),
            away_avg_ga=round(aga/ap, 2),
        )