"""Elo等级分因素 — 从预计算的Elo数据读取

Elo数据由 scripts/compute_elo.py 预先计算并按match_key存入match_data
本因素只读取，不更新
"""

import json
from typing import Dict, Any
from fetchers.common.team_names import normalize_team_name
from .base_factor import BaseFactor


ELO_INIT = 1500


class EloRatingFactor(BaseFactor):
    factor = "elo_rating"
    title = "Elo等级分"
    factor_type = "numeric"

    def extract(self, match_key: str, storage) -> Dict[str, Any]:
        match = self._get_match(match_key, storage)
        if not match or not match.get("home_team"):
            return self._no_data("未找到比赛")

        home = normalize_team_name(match["home_team"])
        away = normalize_team_name(match["away_team"])

        # 从match_data读取预计算的Elo
        conn = storage._conn()
        row = conn.execute(
            "SELECT data_json FROM match_data WHERE match_key=? AND source='system' AND data_type='elo'",
            (match_key,)
        ).fetchone()
        conn.close()

        if row:
            data = json.loads(row["data_json"])
            home_elo = data.get("home_elo", ELO_INIT)
            away_elo = data.get("away_elo", ELO_INIT)
            conf = 0.8
        else:
            # 没有预计算数据，用默认值
            home_elo = ELO_INIT
            away_elo = ELO_INIT
            conf = 0.2

        diff = (home_elo - away_elo) / 400.0  # 归一化

        return self._numeric(
            home_value=round(home_elo),
            away_value=round(away_elo),
            unit="Elo等级分",
            higher_is_better=True,
            confidence=conf,
            diff=round(diff, 3),
        )