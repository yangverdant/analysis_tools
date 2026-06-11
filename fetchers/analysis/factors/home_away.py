"""主客场表现因素"""

from typing import Dict, Any, List
from fetchers.common.team_names import normalize_team_name
from .base_factor import BaseFactor


class HomeAwayFactor(BaseFactor):
    factor = "home_away"
    title = "主客场表现"
    factor_type = "numeric"

    def extract(self, match_key: str, storage) -> Dict[str, Any]:
        match = self._get_match(match_key, storage)
        if not match or not match.get("home_team"):
            return self._no_data("未找到比赛")

        home = normalize_team_name(match["home_team"])
        away = normalize_team_name(match["away_team"])
        date = match.get("date", "")

        # 主队主场战绩
        hm = self._get_home_matches(home, date, storage)
        # 客队客场战绩
        am = self._get_away_matches(away, date, storage)

        if not hm and not am:
            return self._no_data("无主客场数据")

        hf = self._calc(hm)
        af = self._calc(am)

        # 主场优势分 = 主队主场胜率 + 联赛平均主场胜率偏差
        home_adv = hf["win_rate"] if hm else 0
        away_adv = af["win_rate"] if am else 0

        return self._numeric(
            home_value=round(home_adv, 3),
            away_value=round(away_adv, 3),
            unit="主/客场胜率",
            higher_is_better=True,
            confidence=0.65 if (hm and am) else 0.35,
            home_home_w=hf["w"], home_home_d=hf["d"], home_home_l=hf["l"],
            home_home_gf=hf["gf"], home_home_ga=hf["ga"],
            away_away_w=af["w"], away_away_d=af["d"], away_away_l=af["l"],
            away_away_gf=af["gf"], away_away_ga=af["ga"],
            home_home_played=hf["total"],
            away_away_played=af["total"],
        )

    def _get_home_matches(self, team: str, before_date: str,
                          storage, limit: int = 10) -> List[Dict]:
        import json
        conn = storage._conn()
        rows = conn.execute(
            "SELECT m.date,m.home_team,m.away_team,md.data_json "
            "FROM matches m JOIN match_data md ON m.match_key=md.match_key "
            "WHERE md.data_type='match' AND md.source NOT IN ('factor','model') "
            "AND m.home_team=? AND m.date<? ORDER BY m.date DESC LIMIT ?",
            (team, before_date, limit * 2)
        ).fetchall()
        conn.close()
        results = []
        for r in rows:
            data = json.loads(r["data_json"])
            hs, aws = data.get("home_score"), data.get("away_score")
            if hs is None or aws is None: continue
            try: hs, aws = int(hs), int(aws)
            except: continue
            results.append({"home_score": hs, "away_score": aws, "is_home": True})
        return results[:limit]

    def _get_away_matches(self, team: str, before_date: str,
                          storage, limit: int = 10) -> List[Dict]:
        import json
        conn = storage._conn()
        rows = conn.execute(
            "SELECT m.date,m.home_team,m.away_team,md.data_json "
            "FROM matches m JOIN match_data md ON m.match_key=md.match_key "
            "WHERE md.data_type='match' AND md.source NOT IN ('factor','model') "
            "AND m.away_team=? AND m.date<? ORDER BY m.date DESC LIMIT ?",
            (team, before_date, limit * 2)
        ).fetchall()
        conn.close()
        results = []
        for r in rows:
            data = json.loads(r["data_json"])
            hs, aws = data.get("home_score"), data.get("away_score")
            if hs is None or aws is None: continue
            try: hs, aws = int(hs), int(aws)
            except: continue
            results.append({"home_score": hs, "away_score": aws, "is_home": False})
        return results[:limit]

    def _calc(self, matches: List[Dict]) -> Dict:
        if not matches:
            return {"w": 0, "d": 0, "l": 0, "gf": 0, "ga": 0,
                    "total": 0, "win_rate": 0}
        w = d = l = gf = ga = 0
        for m in matches:
            tgf = m["home_score"] if m["is_home"] else m["away_score"]
            tga = m["away_score"] if m["is_home"] else m["home_score"]
            gf += tgf; ga += tga
            if tgf > tga:   w += 1
            elif tgf == tga: d += 1
            else:            l += 1
        n = len(matches)
        return {"w": w, "d": d, "l": l, "gf": gf, "ga": ga,
                "total": n, "win_rate": round(w/n, 3)}