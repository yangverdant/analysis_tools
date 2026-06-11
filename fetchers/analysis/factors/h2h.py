"""历史交锋因素"""

import json
from typing import Dict, Any
from fetchers.common.team_names import normalize_team_name
from .base_factor import BaseFactor


class H2HFactor(BaseFactor):
    factor = "h2h"
    title = "历史交锋"
    factor_type = "numeric"

    def extract(self, match_key: str, storage) -> Dict[str, Any]:
        match = self._get_match(match_key, storage)
        if not match or not match.get("home_team"):
            return self._no_data("未找到比赛")

        home = normalize_team_name(match["home_team"])
        away = normalize_team_name(match["away_team"])
        date = match.get("date", "")

        conn = storage._conn()
        rows = conn.execute(
            "SELECT m.match_key, m.date, m.home_team, m.away_team, md.data_json "
            "FROM matches m JOIN match_data md ON m.match_key=md.match_key "
            "WHERE md.data_type='match' AND md.source NOT IN ('factor','model') "
            "AND ((m.home_team=? AND m.away_team=?) OR (m.home_team=? AND m.away_team=?)) "
            "AND m.date<? ORDER BY m.date DESC LIMIT 10",
            (home, away, away, home, date)
        ).fetchall()
        conn.close()

        if not rows:
            return self._no_data("无交锋记录")

        hw = dw = aw = 0
        total_gf = total_ga = 0
        results = []
        for r in rows:
            data = json.loads(r["data_json"])
            hs = data.get("home_score")
            aws = data.get("away_score")
            if hs is None or aws is None: continue
            try: hs, aws = int(hs), int(aws)
            except: continue

            is_home_perspective = (normalize_team_name(r["home_team"]) == home)
            gf = hs if is_home_perspective else aws
            ga = aws if is_home_perspective else hs
            total_gf += gf; total_ga += ga

            if gf > ga:   hw += 1
            elif gf == ga: dw += 1
            else:          aw += 1

            results.append({"date": r["date"], "home": r["home_team"],
                           "away": r["away_team"], "score": f"{hs}-{aws}"})

        n = len(results)
        home_win_rate = hw / n if n else 0

        return self._numeric(
            home_value=round(home_win_rate, 3),
            away_value=round(aw/n, 3) if n else 0,
            unit="交锋胜率",
            higher_is_better=True,
            confidence=min(0.8, 0.3 + n * 0.1),
            h2h_count=n,
            home_wins=hw, draws=dw, away_wins=aw,
            avg_goals=round((total_gf + total_ga) / n, 2) if n else 0,
            recent=results[:5],
        )