"""天气因素"""

import json
from typing import Dict, Any
from .base_factor import BaseFactor


class WeatherFactor(BaseFactor):
    factor = "weather"
    title = "天气条件"
    factor_type = "text"

    def extract(self, match_key: str, storage) -> Dict[str, Any]:
        conn = storage._conn()
        rows = conn.execute(
            "SELECT data_json FROM weather WHERE match_key=?",
            (match_key,)
        ).fetchall()
        conn.close()

        if not rows:
            return self._no_data("无天气数据")

        data = json.loads(rows[0]["data_json"])
        temp = data.get("temp_c") or data.get("temperature")
        humidity = data.get("humidity")
        wind = data.get("wind_kph") or data.get("wind_speed")
        desc = data.get("description") or data.get("condition", "")
        date = data.get("date", "")

        home_text = desc
        away_text = desc  # 同一场比赛天气一样

        alerts = []
        try:
            if temp and float(temp) > 35: alerts.append("极端高温")
            if temp and float(temp) < -5: alerts.append("极端低温")
        except: pass
        try:
            if humidity and float(humidity) > 90: alerts.append("高湿度")
        except: pass
        try:
            if wind and float(wind) > 40: alerts.append("大风")
        except: pass
        if any(k in desc for k in ["暴", "雷", "雪"]): alerts.append("恶劣天气")

        if alerts:
            home_text += f"(注意:{'/'.join(alerts)})"
            away_text = home_text

        return self._text(
            home_text=home_text,
            away_text=away_text,
            expires_at=f"{date}T23:59:59" if date else "",
            confidence=0.7,
            temperature=temp,
            humidity=humidity,
            wind_speed=wind,
            description=desc,
            alerts=alerts,
            has_extreme_weather=len(alerts) > 0,
        )