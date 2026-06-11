"""亚盘因素"""

import json
from typing import Dict, Any, List
from .base_factor import BaseFactor


class AsianHandicapFactor(BaseFactor):
    factor = "asian_handicap"
    title = "亚盘"
    factor_type = "numeric"

    def extract(self, match_key: str, storage) -> Dict[str, Any]:
        # 优先从okooo亚盘历史数据提取
        conn = storage._conn()
        rows = conn.execute(
            "SELECT source, data_json FROM match_data "
            "WHERE match_key=? AND data_type='odds_ah'",
            (match_key,)
        ).fetchall()

        if rows:
            conn.close()
            return self._extract_from_okooo(rows)

        # 从football-data-co-uk赔率数据提取亚盘
        row = conn.execute(
            "SELECT data_json FROM match_data "
            "WHERE match_key=? AND data_type='odds' "
            "AND json_extract(data_json, '$.ah_handicap') IS NOT NULL "
            "ORDER BY CASE WHEN source='odds_feed' THEN 0 ELSE 1 END LIMIT 1",
            (match_key,)
        ).fetchone()
        conn.close()

        if row:
            return self._extract_from_football_data(row[0])

        return self._no_data("无亚盘数据")

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
                "opening": self._parse_ah(opening["v"]) if opening else None,
                "closing": self._parse_ah(closing["v"]) if closing else None,
            })

        if not summaries:
            return self._no_data("亚盘数据解析为空")

        main = next((s for s in summaries if s["closing"]), summaries[0])
        cl = main["closing"]
        op = main["opening"]

        if not cl:
            return self._no_data("亚盘终盘数据为空")

        handicap_diff = 0
        if op and cl:
            handicap_diff = cl["handicap"] - op["handicap"]

        home_water = cl["home_water"]
        away_water = cl["away_water"]
        water_diff = away_water - home_water

        return self._numeric(
            home_value=round(home_water, 3),
            away_value=round(away_water, 3),
            unit="水位",
            higher_is_better=False,
            confidence=0.75,
            closing_handicap=cl["handicap"],
            opening_handicap=op["handicap"] if op else None,
            handicap_change=round(handicap_diff, 2),
            water_diff=round(water_diff, 3),
            companies={s["company"]: {
                "opening": s["opening"],
                "closing": s["closing"],
            } for s in summaries if s["closing"]},
        )

    def _extract_from_football_data(self, data_json):
        data = json.loads(data_json)
        handicap = data.get("ah_handicap")
        home_water = data.get("avg_ah_home")
        away_water = data.get("avg_ah_away")
        if handicap is None or home_water is None or away_water is None:
            return self._no_data("亚盘数据不完整")

        water_diff = away_water - home_water

        return self._numeric(
            home_value=round(home_water, 3),
            away_value=round(away_water, 3),
            unit="水位",
            higher_is_better=False,
            confidence=0.70,
            closing_handicap=handicap,
            water_diff=round(water_diff, 3),
            source="football-data-co-uk",
        )

    @staticmethod
    def _parse_ah(v_str: str) -> Dict:
        try:
            parts = v_str.split("|")
            return {
                "home_water": float(parts[0]),
                "handicap": float(parts[1]),
                "away_water": float(parts[2]),
            }
        except (ValueError, IndexError):
            return {"home_water": 0, "handicap": 0, "away_water": 0}