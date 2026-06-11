"""联赛排名因素"""

from typing import Dict, Any
from fetchers.common.team_names import normalize_team_name
from .base_factor import BaseFactor


class StandingFactor(BaseFactor):
    factor = "standing"
    title = "联赛排名"
    factor_type = "numeric"

    def extract(self, match_key: str, storage) -> Dict[str, Any]:
        match = self._get_match(match_key, storage)
        if not match or not match.get("home_team"):
            return self._no_data("未找到比赛")

        league = match.get("league_standard") or match.get("league", "")
        if not league:
            return self._no_data("缺少联赛信息")

        season = self._get_season_from_date(match.get("date", ""))
        standings = self._get_standings_map(league, storage, season=season)
        if not standings:
            return self._no_data(f"无{league}积分榜")

        home = normalize_team_name(match["home_team"])
        away = normalize_team_name(match["away_team"])
        hs = standings.get(home)
        as_ = standings.get(away)

        if not hs or not as_:
            return self._no_data("积分榜缺少队伍")

        hp = int(hs.get("played", 1))
        ap = int(as_.get("played", 1))
        hgf, hga = int(hs.get("goals_for", 0)), int(hs.get("goals_against", 0))
        agf, aga = int(as_.get("goals_for", 0)), int(as_.get("goals_against", 0))

        home_pos = int(hs.get("position", hs.get("rank", 99)))
        away_pos = int(as_.get("position", as_.get("rank", 99)))

        # 归一化diff: 排名差/20 → 量级约[-1, 1]
        # higher_is_better=False 会翻转，所以传原始方向
        # home_rank=3, away_rank=7 → raw_diff=-4/20=-0.2 → 翻转后=0.2(主队更好)
        normalized_diff = (home_pos - away_pos) / 20.0

        return self._numeric(
            home_value=home_pos,
            away_value=away_pos,
            unit="排名",
            higher_is_better=False,
            confidence=0.9,
            diff=round(normalized_diff, 3),
            # 详细字段存raw，模型可以按需取用
            home_points=int(hs.get("points", 0)),
            away_points=int(as_.get("points", 0)),
            home_played=hp, away_played=ap,
            home_won=int(hs.get("won", 0)), away_won=int(as_.get("won", 0)),
            home_drawn=int(hs.get("drawn", 0)), away_drawn=int(as_.get("drawn", 0)),
            home_lost=int(hs.get("lost", 0)), away_lost=int(as_.get("lost", 0)),
            home_gf=hgf, away_gf=agf,
            home_ga=hga, away_ga=aga,
            home_ppg=round(int(hs.get("points", 0))/hp, 2) if hp else 0,
            away_ppg=round(int(as_.get("points", 0))/ap, 2) if ap else 0,
            home_gd=hgf-hga, away_gd=agf-aga,
        )