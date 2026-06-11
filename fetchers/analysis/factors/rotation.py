"""轮换预警因素 — 检测是否可能轮换主力"""

import json
from typing import Dict, Any
from fetchers.common.team_names import normalize_team_name
from .base_factor import BaseFactor


class RotationFactor(BaseFactor):
    factor = "rotation"
    title = "轮换预警"
    factor_type = "categorical"

    def extract(self, match_key: str, storage) -> Dict[str, Any]:
        match = self._get_match(match_key, storage)
        if not match or not match.get("home_team"):
            return self._no_data("未找到比赛")

        home = normalize_team_name(match["home_team"])
        away = normalize_team_name(match["away_team"])
        league = match.get("league_standard", "")

        standings = self._get_standings_map(league, storage) if league else {}

        home_risk = self._check_rotation_risk(home, standings)
        away_risk = self._check_rotation_risk(away, standings)

        return self._categorical(
            home_category=home_risk["level"],
            away_category=away_risk["level"],
            confidence=0.4,
            home_reasons=home_risk["reasons"],
            away_reasons=away_risk["reasons"],
            note="基于排名+动机推算，非实际阵容信息",
        )

    def _check_rotation_risk(self, team: str, standings: Dict) -> Dict:
        reasons = []
        level = "unlikely"

        s = standings.get(team)
        if not s:
            return {"level": "unknown", "reasons": ["无积分榜数据"]}

        rank = int(s.get("rank", 99))
        played = int(s.get("played", 0))
        total = len(standings)

        # 1. 无欲无求 → 大概率轮换
        euro_line = 6 if total >= 18 else 4
        relegation_line = total - 3 if total >= 18 else total - 2
        if rank > euro_line and rank <= relegation_line:
            # 中游无欲无求
            # 粗略判断：离欧战区差多少分
            pts = int(s.get("points", 0))
            sorted_pts = sorted([int(x.get("points",0)) for x in standings.values()], reverse=True)
            euro_pts = sorted_pts[min(euro_line, len(sorted_pts))-1] if sorted_pts else 999
            safety_pts = sorted_pts[min(relegation_line, len(sorted_pts))-1] if sorted_pts else 0
            remaining = 30 - played  # rough
            if pts + remaining*3 < euro_pts and pts > safety_pts + 6:
                level = "likely"
                reasons.append("中游无欲无求，可能轮换")

        # 2. 已提前夺冠/保级 → 可能轮换
        if rank == 1:
            sorted_pts = sorted([int(x.get("points",0)) for x in standings.values()], reverse=True)
            if len(sorted_pts) > 1 and int(s.get("points",0)) - sorted_pts[1] > 6:
                level = "likely"
                reasons.append("已大幅领先，可能轮换主力")

        if not reasons:
            reasons.append("无明确轮换信号")

        return {"level": level, "reasons": reasons}
