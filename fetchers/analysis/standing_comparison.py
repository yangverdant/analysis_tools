"""联赛排名对比"""

from typing import Dict, Any
from fetchers.common.team_names import normalize_team_name
from .base import BaseAnalyzer


class StandingComparison(BaseAnalyzer):
    name = "standing_comparison"
    title = "联赛排名对比"

    def analyze(self, match_key: str, storage) -> Dict[str, Any]:
        match = self._get_match(match_key, storage)
        if not match or not match.get("home_team"):
            return self._no_data("未找到比赛信息")

        league = match.get("league_standard", "")
        if not league:
            return self._no_data("缺少联赛信息")

        standings = self._get_standings_map(league, storage)
        if not standings:
            return self._no_data(f"无{league}积分榜")

        home = normalize_team_name(match["home_team"])
        away = normalize_team_name(match["away_team"])
        home_s = standings.get(home)
        away_s = standings.get(away)

        if not home_s or not away_s:
            missing = []
            if not home_s: missing.append(f"主队({home})")
            if not away_s: missing.append(f"客队({away})")
            return self._no_data("积分榜缺少" + "/".join(missing))

        hr = int(home_s.get("rank", 99))
        ar = int(away_s.get("rank", 99))
        hp = int(home_s.get("points", 0))
        ap = int(away_s.get("points", 0))
        hpl = int(home_s.get("played", 1))
        apl = int(away_s.get("played", 1))
        hgf = int(home_s.get("goals_for", 0))
        hga = int(home_s.get("goals_against", 0))
        agf = int(away_s.get("goals_for", 0))
        aga = int(away_s.get("goals_against", 0))

        gap = ar - hr
        abs_gap = abs(gap)
        h_ppg = hp / hpl if hpl else 0
        a_ppg = ap / apl if apl else 0

        if abs_gap >= 10:
            sig = "home" if gap > 0 else "away"
            stren = min(0.9, 0.5 + abs_gap * 0.03)
        elif abs_gap >= 5:
            sig = "home" if gap > 0 else "away"
            stren = min(0.7, 0.3 + abs_gap * 0.04)
        elif abs_gap >= 2:
            sig = "home" if gap > 0 else "away"
            stren = 0.2 + abs_gap * 0.05
        else:
            sig = "neutral"
            stren = 0.1

        desc = "实力差距明显" if abs_gap >= 5 else "有一定差距" if abs_gap >= 2 else "排名接近"
        summary = f"主队第{hr}名({hp}分) vs 客队第{ar}名({ap}分)，排名差{abs_gap}位，{desc}"

        return self._ok(0.9, sig, stren, summary,
            home_rank=hr, away_rank=ar, home_points=hp, away_points=ap,
            home_played=hpl, away_played=apl,
            home_ppg=round(h_ppg, 2), away_ppg=round(a_ppg, 2),
            home_gf_pg=round(hgf/hpl, 2) if hpl else 0,
            home_ga_pg=round(hga/hpl, 2) if hpl else 0,
            away_gf_pg=round(agf/apl, 2) if apl else 0,
            away_ga_pg=round(aga/apl, 2) if apl else 0,
            rank_gap=gap)