"""伤病影响因素（数值版 v2）

量化伤病对球队实力的削弱程度：
- 每个伤停球员贡献一个impact分数（关键位置更高）
- home_impact - away_impact → diff（正=主队伤病更严重=不利）
- 数据来源: injuries表 + match_data中的lineup数据
"""

import json
from typing import Dict, Any
from fetchers.common.team_names import normalize_team_name
from .base_factor import BaseFactor


class InjuryFactor(BaseFactor):
    factor = "injury"
    title = "伤病影响"
    factor_type = "numeric"

    # 位置权重：关键位置伤缺影响更大
    POSITION_WEIGHT = {
        "Goalkeeper": 1.5,
        "Centre-Back": 1.0,
        "Defender": 0.8,
        "Defensive Midfield": 1.0,
        "Central Midfield": 0.9,
        "Attacking Midfield": 1.1,
        "Midfielder": 0.8,
        "Left Winger": 0.9,
        "Right Winger": 0.9,
        "Second Striker": 1.0,
        "Centre-Forward": 1.2,
        "Striker": 1.1,
        "Forward": 1.0,
    }
    DEFAULT_WEIGHT = 0.8

    def extract(self, match_key: str, storage) -> Dict[str, Any]:
        match = self._get_match(match_key, storage)
        if not match or not match.get("home_team"):
            return self._no_data("未找到比赛")

        home = normalize_team_name(match["home_team"])
        away = normalize_team_name(match["away_team"])

        conn = storage._conn()

        # 从injuries表获取
        home_inj = conn.execute(
            "SELECT player_name, data_json FROM injuries WHERE team_standard=?",
            (home,)
        ).fetchall()
        away_inj = conn.execute(
            "SELECT player_name, data_json FROM injuries WHERE team_standard=?",
            (away,)
        ).fetchall()

        # 从match_data中的lineup/lineup_impact数据获取
        home_lineup_impact = self._get_lineup_impact(match_key, home, "home", conn)
        away_lineup_impact = self._get_lineup_impact(match_key, away, "away", conn)

        conn.close()

        # 计算伤病impact
        home_list = [self._parse_injury(r) for r in home_inj]
        away_list = [self._parse_injury(r) for r in away_inj]

        home_impact = sum(i["weight"] for i in home_list) + home_lineup_impact
        away_impact = sum(i["weight"] for i in away_list) + away_lineup_impact

        # 归一化到0~1范围（5个关键伤停≈1.0）
        home_score = min(1.0, home_impact / 5.0)
        away_score = min(1.0, away_impact / 5.0)

        # 置信度：有伤病数据时更高
        has_data = bool(home_list or away_list or home_lineup_impact or away_lineup_impact)
        conf = 0.6 if has_data else 0.2

        # diff: 正=主队伤病更重=对主队不利
        # 但模型中正diff=主队优，所以取反
        return self._numeric(
            home_value=round(home_score, 3),
            away_value=round(away_score, 3),
            unit="伤病影响(越低越好)",
            higher_is_better=False,
            confidence=conf,
            home_injury_count=len(home_list),
            away_injury_count=len(away_list),
            home_impact_raw=round(home_impact, 2),
            away_impact_raw=round(away_impact, 2),
            home_injuries=[i["player"] for i in home_list[:5]],
            away_injuries=[i["player"] for i in away_list[:5]],
        )

    def _parse_injury(self, row) -> Dict:
        player = row["player_name"]
        try:
            d = json.loads(row["data_json"]) if row["data_json"] else {}
        except (json.JSONDecodeError, TypeError):
            d = {}

        position = d.get("position", d.get("player_position", ""))
        weight = self.POSITION_WEIGHT.get(position, self.DEFAULT_WEIGHT)

        # 某些伤病类型更严重（赛季报销 vs 轻伤）
        reason = d.get("reason", d.get("injury_type", "")).lower()
        if any(kw in reason for kw in ["acl", "cruciate", "season", "long-term", "手术"]):
            weight *= 1.5
        elif any(kw in reason for kw in ["doubtful", "minor", "轻伤", "疑问"]):
            weight *= 0.5

        return {"player": player, "position": position, "weight": weight}

    def _get_lineup_impact(self, match_key: str, team: str, side: str, conn) -> float:
        """从lineup数据中提取阵容缺失影响"""
        row = conn.execute(
            "SELECT data_json FROM match_data "
            "WHERE match_key=? AND source='factor' AND data_type='factor:lineup'",
            (match_key,)
        ).fetchone()
        if not row:
            return 0.0
        try:
            data = json.loads(row["data_json"])
        except (json.JSONDecodeError, TypeError):
            return 0.0

        # lineup因素可能有missing_players信息
        raw = data.get("raw", {})
        key = f"{side}_missing_impact"
        return float(raw.get(key, 0.0))