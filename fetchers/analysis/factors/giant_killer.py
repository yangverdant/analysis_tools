"""劫富济贫因素 — 对比打强队vs打弱队的表现差异"""

import json
from typing import Dict, Any, List
from fetchers.common.team_names import normalize_team_name
from .base_factor import BaseFactor


class GiantKillerFactor(BaseFactor):
    factor = "giant_killer"
    title = "劫富济贫"
    factor_type = "categorical"

    def extract(self, match_key: str, storage) -> Dict[str, Any]:
        match = self._get_match(match_key, storage)
        if not match or not match.get("home_team"):
            return self._no_data("未找到比赛")

        home = normalize_team_name(match["home_team"])
        away = normalize_team_name(match["away_team"])
        date = match.get("date", "")
        league = match.get("league_standard", "")

        standings = self._get_standings_map(league, storage) if league else {}
        total_teams = len(standings)
        if total_teams < 6:
            return self._no_data("积分榜队伍不足")

        mid = total_teams // 2
        top_threshold = max(3, mid // 2)
        bottom_threshold = total_teams - top_threshold

        home_ana = self._analyze(home, date, standings, top_threshold, bottom_threshold, storage)
        away_ana = self._analyze(away, date, standings, top_threshold, bottom_threshold, storage)

        return self._categorical(
            home_category=home_ana["label"],
            away_category=away_ana["label"],
            confidence=0.5,
            home_vs_top=home_ana["vs_top"],
            home_vs_bottom=home_ana["vs_bottom"],
            away_vs_top=away_ana["vs_top"],
            away_vs_bottom=away_ana["vs_bottom"],
        )

    def _analyze(self, team, before_date, standings, top_line, bottom_line, storage) -> Dict:
        matches = self._get_team_recent_matches(team, before_date, storage, limit=12)
        if not matches:
            return {"label": "unknown", "vs_top": {}, "vs_bottom": {}}

        vs_top = {"w":0,"d":0,"l":0,"n":0}
        vs_bottom = {"w":0,"d":0,"l":0,"n":0}

        for m in matches:
            opp = normalize_team_name(m["away"] if m["is_home"] else m["home"])
            opp_s = standings.get(opp)
            if not opp_s:
                continue
            opp_rank = int(opp_s.get("rank", 99))
            gf = m["home_score"] if m["is_home"] else m["away_score"]
            ga = m["away_score"] if m["is_home"] else m["home_score"]

            bucket = vs_top if opp_rank <= top_line else vs_bottom if opp_rank >= bottom_line else None
            if bucket is None:
                continue
            bucket["n"] += 1
            if gf > ga: bucket["w"] += 1
            elif gf == ga: bucket["d"] += 1
            else: bucket["l"] += 1

        top_rate = vs_top["w"] / vs_top["n"] if vs_top["n"] else 0.5
        bottom_rate = vs_bottom["w"] / vs_bottom["n"] if vs_bottom["n"] else 0.5
        diff = top_rate - bottom_rate

        if diff >= 0.15:
            label = "giant_killer"
        elif diff <= -0.15:
            label = "flat_track_bully"
        else:
            label = "normal"

        return {"label": label, "vs_top": vs_top, "vs_bottom": vs_bottom,
                "top_win_rate": round(top_rate,3), "bottom_win_rate": round(bottom_rate,3)}
