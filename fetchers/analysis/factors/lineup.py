"""阵型/阵容因素 — 检测阵型变化对大小球的影响"""

import json
from typing import Dict, Any
from fetchers.common.team_names import normalize_team_name
from .base_factor import BaseFactor


class LineupFactor(BaseFactor):
    factor = "lineup"
    title = "阵型阵容"
    factor_type = "categorical"

    # 常见阵型分类
    ATTACKING = {"4-3-3", "4-2-3-1", "3-4-3", "4-1-4-1"}
    DEFENSIVE = {"5-4-1", "5-3-2", "4-5-1", "6-3-1"}
    BALANCED = {"4-4-2", "4-3-2-1", "3-5-2", "4-2-2-2"}

    def extract(self, match_key: str, storage) -> Dict[str, Any]:
        match = self._get_match(match_key, storage)
        if not match or not match.get("home_team"):
            return self._no_data("未找到比赛")

        home = normalize_team_name(match["home_team"])
        away = normalize_team_name(match["away_team"])

        # 从已完赛的detail数据中提取最近阵型
        home_formation = self._get_recent_formation(home, storage)
        away_formation = self._get_recent_formation(away, storage)

        home_cat = self._classify(home_formation)
        away_cat = self._classify(away_formation)

        # 阵型组合对大小球的影响
        both_attacking = home_cat == "attacking" and away_cat == "attacking"
        both_defensive = home_cat == "defensive" and away_cat == "defensive"
        over_tendency = "high" if both_attacking else "low" if both_defensive else "normal"

        return self._categorical(
            home_category=home_cat,
            away_category=away_cat,
            confidence=0.3,
            home_usual_formation=home_formation,
            away_usual_formation=away_formation,
            over_tendency=over_tendency,
            note="基于历史阵型推算，非赛前预告阵容",
        )

    def _get_recent_formation(self, team: str, storage) -> str:
        """从match_detail中获取最近使用的阵型"""
        conn = storage._conn()
        rows = conn.execute(
            "SELECT md.data_json FROM matches m "
            "JOIN match_data md ON m.match_key=md.match_key "
            "WHERE md.data_type='detail' AND (m.home_team=? OR m.away_team=?) "
            "ORDER BY m.date DESC LIMIT 1",
            (team, team)
        ).fetchall()
        conn.close()

        for r in rows:
            data = json.loads(r["data_json"])
            lineup = data.get("lineup", {})
            side = "home" if normalize_team_name(
                data.get("home_team","")) == team else "away"
            formation = lineup.get(side, {}).get("formation", "")
            if formation:
                return formation
        return ""

    def _classify(self, formation: str) -> str:
        if not formation:
            return "unknown"
        f = formation.lower().replace(" ", "")
        if f in {x.replace("-","") for x in self.ATTACKING} or formation in self.ATTACKING:
            return "attacking"
        if f in {x.replace("-","") for x in self.DEFENSIVE} or formation in self.DEFENSIVE:
            return "defensive"
        return "balanced"
