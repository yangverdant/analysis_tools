"""AI预测因素"""

import json
from typing import Dict, Any
from .base_factor import BaseFactor


class PredictionFactor(BaseFactor):
    factor = "prediction"
    title = "AI预测"
    factor_type = "numeric"

    def extract(self, match_key: str, storage) -> Dict[str, Any]:
        conn = storage._conn()
        rows = conn.execute(
            "SELECT data_json FROM match_data WHERE match_key=? AND data_type='prediction'",
            (match_key,)
        ).fetchall()
        conn.close()

        if not rows:
            return self._no_data("无预测数据")

        preds = []
        for r in rows:
            data = json.loads(r["data_json"])
            hp = data.get("home_win_prob")
            dp = data.get("draw_prob")
            ap = data.get("away_win_prob")
            if hp and dp and ap:
                try:
                    preds.append({
                        "source": data.get("source", "unknown"),
                        "home": float(hp), "draw": float(dp), "away": float(ap),
                        "over_2_5": float(data.get("over_2_5_prob", 0)),
                        "btts_yes": float(data.get("btts_yes_prob", 0)),
                        "advice": data.get("advice", ""),
                    })
                except (ValueError, TypeError):
                    continue

        if not preds:
            return self._no_data("预测数据解析为空")

        # 取首家
        p = preds[0]
        diff = p["home"] - p["away"]

        return self._numeric(
            home_value=round(p["home"], 2),
            away_value=round(p["away"], 2),
            unit="预测胜率%",
            higher_is_better=True,
            confidence=0.55,
            draw_prob=round(p["draw"], 2),
            over_2_5_prob=round(p.get("over_2_5", 0), 2),
            btts_yes_prob=round(p.get("btts_yes", 0), 2),
            advice=p.get("advice", ""),
            source=p["source"],
        )