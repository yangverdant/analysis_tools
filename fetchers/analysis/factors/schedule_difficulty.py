"""赛程难度推演因素

分析两队剩余赛程的难度：
- 剩余对手的平均排名
- 还要打几场强队（前6）、几场弱队（降级区）
- 推算预期可拿分数
- 关键：和当前对手这场是否"必须拿下"
"""

import json
from typing import Dict, Any, List
from fetchers.common.team_names import normalize_team_name
from .base_factor import BaseFactor


class ScheduleDifficultyFactor(BaseFactor):
    factor = "schedule_difficulty"
    title = "赛程难度"
    factor_type = "numeric"

    def extract(self, match_key: str, storage) -> Dict[str, Any]:
        match = self._get_match(match_key, storage)
        if not match or not match.get("home_team"):
            return self._no_data("未找到比赛")

        league = match.get("league_standard", "")
        if not league:
            return self._no_data("缺少联赛")

        standings = self._get_standings_map(league, storage)
        if not standings:
            return self._no_data("无积分榜")

        home = normalize_team_name(match["home_team"])
        away = normalize_team_name(match["away_team"])
        date = match.get("date", "")

        # 获取已安排的后续比赛
        home_future = self._get_future_matches(home, date, storage)
        away_future = self._get_future_matches(away, date, storage)

        if not home_future and not away_future:
            # 没有后续赛程数据，用积分榜推算
            home_future = self._estimate_remaining(home, standings, league, storage)
            away_future = self._estimate_remaining(away, standings, league, storage)

        home_diff = self._calc_difficulty(home, home_future, standings)
        away_diff = self._calc_difficulty(away, away_future, standings)

        # 当前对手排名
        hs = standings.get(home)
        as_ = standings.get(away)
        away_rank = int(as_.get("rank", 99)) if as_ else 99
        home_rank = int(hs.get("rank", 99)) if hs else 99

        # 这场是否"必须拿下"：如果对手是弱队且自己在争冠/保级
        home_must_win = False
        away_must_win = False
        if hs and as_:
            home_rank_self = int(hs.get("rank", 99))
            away_rank_self = int(as_.get("rank", 99))
            # 自己争冠/保级 + 对手弱 → 必须赢
            if home_rank_self <= 6 and away_rank_self > 10:
                home_must_win = True
            if home_rank_self > 10 and away_rank_self <= 6:
                away_must_win = True
            # 保级队打弱队
            total = len(standings)
            if home_rank_self > total - 4 and away_rank_self > 10:
                home_must_win = True
            if away_rank_self > total - 4 and home_rank_self > 10:
                away_must_win = True

        # diff 越小 = 赛程越难
        return self._numeric(
            home_value=round(home_diff["avg_opponent_rank"], 1),
            away_value=round(away_diff["avg_opponent_rank"], 1),
            unit="对手平均排名(越低越难)",
            higher_is_better=True,
            confidence=0.55,
            home_remaining=home_diff["remaining"],
            away_remaining=away_diff["remaining"],
            home_top6_games=home_diff["top6_games"],
            away_top6_games=away_diff["top6_games"],
            home_relegation_games=home_diff["relegation_games"],
            away_relegation_games=away_diff["relegation_games"],
            home_estimated_pts=home_diff["estimated_pts"],
            away_estimated_pts=away_diff["estimated_pts"],
            home_must_win=home_must_win,
            away_must_win=away_must_win,
        )

    def _get_future_matches(self, team: str, after_date: str, storage) -> List[Dict]:
        """获取后续已安排比赛"""
        conn = storage._conn()
        rows = conn.execute(
            "SELECT m.match_key, m.date, m.home_team, m.away_team "
            "FROM matches m "
            "WHERE (m.home_team=? OR m.away_team=?) AND m.date>? "
            "ORDER BY m.date LIMIT 10",
            (team, team, after_date)
        ).fetchall()
        conn.close()
        return [{"date": r["date"], "home": r["home_team"], "away": r["away_team"]}
                for r in rows]

    def _estimate_remaining(self, team: str, standings: Dict, league: str,
                            storage) -> List[Dict]:
        """当没有后续赛程数据时，用积分榜推算剩余对手"""
        team_data = standings.get(team)
        if not team_data:
            return []
        played = int(team_data.get("played", 0))
        total_rounds = self._get_total_rounds(league)
        remaining = total_rounds - played

        # 从所有球队中排除自己，作为假想对手
        opponents = [t for t in standings.keys() if t != team]
        # 简单循环
        result = []
        for i in range(min(remaining, len(opponents))):
            opp = opponents[i % len(opponents)]
            result.append({"home": team, "away": opp, "date": "estimated"})
        return result

    def _calc_difficulty(self, team: str, future_matches: List[Dict],
                         standings: Dict) -> Dict:
        total = len(standings)
        opponent_ranks = []
        top6 = 0
        relegation = 0
        total_teams = total

        for m in future_matches:
            opp = m["away"] if m["home"] == team else m["home"]
            opp_data = standings.get(opp)
            if opp_data:
                rank = int(opp_data.get("rank", total))
                opponent_ranks.append(rank)
                if rank <= 6:
                    top6 += 1
                if rank > total_teams - 3:
                    relegation += 1

        avg_rank = sum(opponent_ranks) / len(opponent_ranks) if opponent_ranks else total / 2

        # 推算可拿分数：打排名前6 预期0.8分，7-10 预期1.3分，10以下 预期1.8分
        estimated = 0
        for r in opponent_ranks:
            if r <= 6:
                estimated += 0.8
            elif r <= 10:
                estimated += 1.3
            else:
                estimated += 1.8

        return {
            "remaining": len(future_matches),
            "avg_opponent_rank": round(avg_rank, 1),
            "top6_games": top6,
            "relegation_games": relegation,
            "estimated_pts": round(estimated, 1),
        }

    @staticmethod
    def _get_total_rounds(league: str) -> int:
        rounds = {
            "Premier League": 38, "La Liga": 38, "Bundesliga": 34,
            "Serie A": 38, "Ligue 1": 34, "Championship": 46,
            "Eliteserien": 30, "Allsvenskan": 30,
        }
        return rounds.get(league, 38)
