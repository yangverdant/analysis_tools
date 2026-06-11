"""赛季动机因素（数值版 v2）

量化动机强度，不只是分类：
- 争冠/保级 = 强动机（+0.8~+1.0）
- 争欧战 = 中等动机（+0.5~+0.7）
- 中游 = 无额外动机（0）
- 无欲无求 = 负动机（-0.5）
- 赛季末段紧迫度 × 1.5
- diff = home_strength - away_strength（正=主队更有战意）
"""

from typing import Dict, Any
from fetchers.common.team_names import normalize_team_name
from .base_factor import BaseFactor


class MotivationFactor(BaseFactor):
    factor = "motivation"
    title = "赛季动机"
    factor_type = "numeric"

    # 分类 → 基础动机值
    CATEGORY_STRENGTH = {
        "title_race":       1.0,
        "relegation":       0.8,
        "relegation_battle":0.9,
        "european":         0.6,
        "mid_table":        0.0,
        "dead_rubber":     -0.5,
    }

    def extract(self, match_key: str, storage) -> Dict[str, Any]:
        match = self._get_match(match_key, storage)
        if not match or not match.get("home_team"):
            return self._no_data("未找到比赛")

        league = match.get("league_standard", "")
        if not league:
            return self._no_data("缺少联赛信息")

        standings = self._get_standings_map(league, storage)
        if not standings:
            return self._no_data("无积分榜")

        home = normalize_team_name(match["home_team"])
        away = normalize_team_name(match["away_team"])
        hs = standings.get(home)
        as_ = standings.get(away)
        if not hs or not as_:
            return self._no_data("积分榜缺队伍")

        total_teams = len(standings)
        total_rounds = self._get_total_rounds(league)
        home_played = int(hs.get("played", 0))
        away_played = int(as_.get("played", 0))

        title_line = 1
        euro_line = self._get_euro_spots(total_teams)
        relegation_line = total_teams - self._get_relegation_spots(total_teams)

        home_rank = int(hs.get("rank", 99))
        away_rank = int(as_.get("rank", 99))
        home_pts = int(hs.get("points", 0))
        away_pts = int(as_.get("points", 0))

        home_ana = self._analyze_team(home_rank, home_pts, home_played,
                                       total_rounds, total_teams,
                                       title_line, euro_line, relegation_line,
                                       standings)
        away_ana = self._analyze_team(away_rank, away_pts, away_played,
                                       total_rounds, total_teams,
                                       title_line, euro_line, relegation_line,
                                       standings)

        # 基础动机值
        home_base = self.CATEGORY_STRENGTH.get(home_ana["category"], 0.0)
        away_base = self.CATEGORY_STRENGTH.get(away_ana["category"], 0.0)

        # 紧迫度修正：赛季末段（剩余<8轮），争冠/保级战意翻倍
        urgency = 1.0
        home_remaining = home_ana["remaining"]
        if home_remaining <= 8:
            urgency = 1.5
        # 更极端：最后3轮
        if home_remaining <= 3:
            urgency = 2.0

        home_strength = home_base * urgency
        away_strength = away_base * urgency

        # 置信度：赛季越靠后、数据越充分，置信度越高
        progress = home_played / total_rounds if total_rounds > 0 else 0
        conf = round(min(0.85, 0.4 + progress * 0.5), 2)

        return self._numeric(
            home_value=round(home_strength, 3),
            away_value=round(away_strength, 3),
            unit="动机强度",
            higher_is_better=True,
            confidence=conf,
            home_category=home_ana["category"],
            away_category=away_ana["category"],
            home_rank=home_rank,
            away_rank=away_rank,
            home_remaining=home_remaining,
            away_remaining=away_ana["remaining"],
            home_pts_to_safety=home_ana["pts_to_safety"],
            away_pts_to_safety=away_ana["pts_to_safety"],
            home_is_dead=home_ana["is_dead"],
            away_is_dead=away_ana["is_dead"],
            urgency_factor=urgency,
        )

    def _analyze_team(self, rank, pts, played, total_rounds,
                      total_teams, title_line, euro_line, relegation_line,
                      standings) -> Dict:
        remaining = max(0, total_rounds - played)
        max_pts = pts + remaining * 3

        sorted_pts = sorted(
            [int(s.get("points", 0)) for s in standings.values()],
            reverse=True)

        title_pts = sorted_pts[0] if sorted_pts else 0
        euro_pts = sorted_pts[min(euro_line, len(sorted_pts)) - 1] if sorted_pts else 0
        safety_idx = min(relegation_line, len(sorted_pts))
        safety_pts = sorted_pts[safety_idx - 1] if safety_idx <= len(sorted_pts) else 0

        can_still = []
        if max_pts >= title_pts:
            can_still.append("title")
        if max_pts >= euro_pts:
            can_still.append("european")
        if rank > relegation_line:
            can_still.append("survival")
        if not can_still:
            can_still.append("nothing")

        pts_to_safety = safety_pts - pts + 1 if rank > relegation_line else 0

        is_dead = False
        if rank > euro_line and max_pts < euro_pts:
            if rank <= relegation_line or pts > safety_pts + remaining * 3:
                is_dead = True

        if is_dead:
            category = "dead_rubber"
        elif rank <= title_line:
            category = "title_race"
        elif rank <= euro_line:
            category = "european"
        elif rank > relegation_line:
            category = "relegation"
        elif pts_to_safety <= 3:
            category = "relegation_battle"
        else:
            category = "mid_table"

        return {
            "category": category,
            "remaining": remaining,
            "max_possible_pts": max_pts,
            "can_still": can_still,
            "pts_to_safety": pts_to_safety,
            "pts_to_title": title_pts - pts if max_pts >= title_pts else -1,
            "pts_to_european": euro_pts - pts if max_pts >= euro_pts else -1,
            "is_dead": is_dead,
        }

    @staticmethod
    def _get_total_rounds(league: str) -> int:
        rounds = {
            "Premier League": 38, "La Liga": 38, "Bundesliga": 34,
            "Serie A": 38, "Ligue 1": 34, "Championship": 46,
            "Eliteserien": 30, "Allsvenskan": 30,
            "Eredivisie": 34, "Primeira Liga": 34,
        }
        return rounds.get(league, 38)

    @staticmethod
    def _get_euro_spots(total_teams: int) -> int:
        return 6 if total_teams >= 18 else 4

    @staticmethod
    def _get_relegation_spots(total_teams: int) -> int:
        return 3 if total_teams >= 18 else 2