"""休息天数+赛程密度因素 v2

不仅看上一场到本场比赛的休息天数，
还要看赛程密度（7天/14天内打了几场比赛）：
- 一周内3场+ → 疲劳累积，实力下降约5-10%
- 密度差 = home_density - away_density（正=主队更疲劳）
- 综合diff = rest_diff - density_diff（两者方向相反）
"""

from typing import Dict, Any
from fetchers.common.team_names import normalize_team_name
from .base_factor import BaseFactor


class RestDaysFactor(BaseFactor):
    factor = "rest_days"
    title = "休息与赛程密度"
    factor_type = "numeric"

    def extract(self, match_key: str, storage) -> Dict[str, Any]:
        match = self._get_match(match_key, storage)
        if not match or not match.get("home_team"):
            return self._no_data("未找到比赛")

        home = normalize_team_name(match["home_team"])
        away = normalize_team_name(match["away_team"])
        date = match.get("date", "")

        if not date:
            return self._no_data("缺少比赛日期")

        # 休息天数
        home_rest = self._get_rest_days(home, date, storage)
        away_rest = self._get_rest_days(away, date, storage)

        # 赛程密度
        home_density_7 = self._get_density(home, date, 7, storage)
        home_density_14 = self._get_density(home, date, 14, storage)
        away_density_7 = self._get_density(away, date, 7, storage)
        away_density_14 = self._get_density(away, date, 14, storage)

        # 默认值
        hr = home_rest if home_rest is not None else 7
        ar = away_rest if away_rest is not None else 7

        # 休息天数diff: 正=主队休息更多=优势
        rest_diff = (hr - ar) / 7.0

        # 赛程密度diff: 正=主队赛程更密=劣势（更多比赛=更疲劳）
        # 归一化：每场比赛 ≈ 0.1 的疲劳信号
        density_diff = (home_density_7 - away_density_7) * 0.1

        # 综合diff：休息优势减去密度劣势
        # 正=主队更有利（休息更多+赛程更松）
        combined_diff = rest_diff - density_diff

        # 置信度
        has_rest = home_rest is not None and away_rest is not None
        has_density = home_density_7 > 0 or away_density_7 > 0
        conf = 0.8 if has_rest and has_density else 0.5 if has_rest else 0.3

        return self._numeric(
            home_value=round(hr, 1),
            away_value=round(ar, 1),
            unit="休息天数+密度",
            higher_is_better=True,
            confidence=conf,
            diff=round(combined_diff, 3),
            home_rest_days=hr,
            away_rest_days=ar,
            rest_diff=round(rest_diff, 3),
            home_density_7=home_density_7,
            away_density_7=away_density_7,
            home_density_14=home_density_14,
            away_density_14=away_density_14,
            density_diff=round(density_diff, 3),
            home_fatigue=self._fatigue_score(hr, home_density_7),
            away_fatigue=self._fatigue_score(ar, away_density_7),
        )

    def _get_rest_days(self, team: str, match_date: str, storage) -> float:
        conn = storage._conn()
        row = conn.execute(
            "SELECT m.date FROM matches m "
            "WHERE m.status='finished' AND (m.home_team=? OR m.away_team=?) "
            "AND m.date < ? ORDER BY m.date DESC LIMIT 1",
            (team, team, match_date)
        ).fetchone()
        conn.close()
        if not row:
            return None
        try:
            from datetime import datetime
            d1 = datetime.strptime(match_date, "%Y-%m-%d")
            d2 = datetime.strptime(row[0], "%Y-%m-%d")
            return (d1 - d2).days
        except:
            return None

    def _get_density(self, team: str, match_date: str, days: int, storage) -> int:
        """查询最近N天内已完赛的比赛数量"""
        from datetime import datetime, timedelta
        try:
            d = datetime.strptime(match_date, "%Y-%m-%d")
            cutoff = (d - timedelta(days=days)).strftime("%Y-%m-%d")
        except:
            return 0

        conn = storage._conn()
        count = conn.execute(
            "SELECT COUNT(*) FROM matches m "
            "WHERE m.status='finished' AND (m.home_team=? OR m.away_team=?) "
            "AND m.date > ? AND m.date < ?",
            (team, team, cutoff, match_date)
        ).fetchone()[0]
        conn.close()
        return count

    def _fatigue_score(self, rest_days: float, density_7: int) -> float:
        """疲劳评分：低=精力充沛，高=极度疲劳"""
        score = 0.0
        # 休息不足3天 → +0.3
        if rest_days < 3:
            score += 0.3
        elif rest_days < 5:
            score += 0.1
        # 一周内3场+ → +0.4
        if density_7 >= 3:
            score += 0.4
        elif density_7 >= 2:
            score += 0.15
        return round(min(1.0, score), 3)