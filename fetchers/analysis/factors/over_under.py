"""大小球因素"""

import json
from typing import Dict, Any
from .base_factor import BaseFactor


class OverUnderFactor(BaseFactor):
    factor = "over_under"
    title = "大小球"
    factor_type = "numeric"

    def extract(self, match_key: str, storage) -> Dict[str, Any]:
        # 优先从okooo大小球历史数据提取
        conn = storage._conn()
        rows = conn.execute(
            "SELECT source, data_json FROM match_data "
            "WHERE match_key=? AND data_type='odds_ou'",
            (match_key,)
        ).fetchall()

        if rows:
            conn.close()
            return self._extract_from_okooo(rows)

        # 从football-data-co-uk赔率数据提取大小球
        row = conn.execute(
            "SELECT data_json FROM match_data "
            "WHERE match_key=? AND data_type='odds' "
            "AND json_extract(data_json, '$.avg_over_2_5') IS NOT NULL "
            "ORDER BY CASE WHEN source='odds_feed' THEN 0 ELSE 1 END LIMIT 1",
            (match_key,)
        ).fetchone()
        conn.close()

        if row:
            return self._extract_from_football_data(row[0])

        return self._no_data("无大小球数据")

    def _extract_from_okooo(self, rows):
        summaries = []
        for r in rows:
            data = json.loads(r["data_json"])
            company = data.get("company", "?")
            history = data.get("data", [])
            if not history:
                continue
            opening = history[-1] if history else None
            closing = history[0] if history else None
            summaries.append({
                "company": company,
                "opening": self._parse_ou(opening["v"]) if opening else None,
                "closing": self._parse_ou(closing["v"]) if closing else None,
            })

        if not summaries:
            return self._no_data("大小球数据解析为空")

        main = next((s for s in summaries if s["closing"]), summaries[0])
        cl = main["closing"]
        op = main["opening"]
        if not cl:
            return self._no_data("大小球终盘数据为空")

        line_diff = 0
        if op and cl:
            line_diff = cl["line"] - op["line"]

        over_water = cl["over_water"]
        under_water = cl["under_water"]
        water_diff = under_water - over_water

        return self._numeric(
            home_value=round(over_water, 3),
            away_value=round(under_water, 3),
            unit="大小球水位",
            higher_is_better=False,
            confidence=0.7,
            closing_line=cl["line"],
            opening_line=op["line"] if op else None,
            line_change=round(line_diff, 2),
            water_diff=round(water_diff, 3),
            companies={s["company"]: {
                "opening": s["opening"], "closing": s["closing"],
            } for s in summaries if s["closing"]},
        )

    def _extract_from_football_data(self, data_json):
        data = json.loads(data_json)
        over_odds = data.get("avg_over_2_5")
        under_odds = data.get("avg_under_2_5")
        if over_odds is None or under_odds is None:
            return self._no_data("大小球数据不完整")

        # 计算隐含概率
        total = 1/over_odds + 1/under_odds
        rr = 1 / total
        over_prob = rr / over_odds
        under_prob = rr / under_odds

        # diff: 正=大球概率高
        diff = over_prob - under_prob

        return self._numeric(
            home_value=round(over_prob, 4),
            away_value=round(under_prob, 4),
            unit="大小球隐含概率",
            higher_is_better=True,
            confidence=0.65,
            over_2_5_prob=round(over_prob, 4),
            under_2_5_prob=round(under_prob, 4),
            water_diff=round(diff, 3),
            source="football-data-co-uk",
        )

    @staticmethod
    def _parse_ou(v_str: str) -> Dict:
        try:
            parts = v_str.split("|")
            return {"over_water": float(parts[0]), "line": float(parts[1]), "under_water": float(parts[2])}
        except (ValueError, IndexError):
            return {"over_water": 0, "line": 0, "under_water": 0}