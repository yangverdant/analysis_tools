"""主客场深挖因素 — 主场龙/虫、客场龙/虫"""

from typing import Dict, Any, List
from fetchers.common.team_names import normalize_team_name
from .base_factor import BaseFactor


class HomeAwayDeepFactor(BaseFactor):
    factor = "home_away_deep"
    title = "主客场深挖"
    factor_type = "categorical"

    def extract(self, match_key: str, storage) -> Dict[str, Any]:
        match = self._get_match(match_key, storage)
        if not match or not match.get("home_team"):
            return self._no_data("未找到比赛")

        home = normalize_team_name(match["home_team"])
        away = normalize_team_name(match["away_team"])
        date = match.get("date", "")

        home_home = self._get_home_matches(home, date, storage)
        home_away = self._get_away_matches(home, date, storage)
        away_home = self._get_home_matches(away, date, storage)
        away_away = self._get_away_matches(away, date, storage)

        hh = self._calc(home_home, is_home_perspective=True)
        ha = self._calc(home_away, is_home_perspective=False)
        ah = self._calc(away_home, is_home_perspective=True)
        aa = self._calc(away_away, is_home_perspective=False)

        home_label = self._label(hh["win_rate"], ha["win_rate"], "home")
        away_label = self._label(ah["win_rate"], aa["win_rate"], "away")

        return self._categorical(
            home_category=home_label,
            away_category=away_label,
            confidence=0.6 if (home_home and away_away) else 0.3,
            home_home_record=f'{hh["w"]}-{hh["d"]}-{hh["l"]}',
            home_home_win_rate=hh["win_rate"],
            home_away_record=f'{ha["w"]}-{ha["d"]}-{ha["l"]}',
            home_away_win_rate=ha["win_rate"],
            away_home_record=f'{ah["w"]}-{ah["d"]}-{ah["l"]}',
            away_home_win_rate=ah["win_rate"],
            away_away_record=f'{aa["w"]}-{aa["d"]}-{aa["l"]}',
            away_away_win_rate=aa["win_rate"],
            home_home_avg_gf=hh["avg_gf"],
            home_home_avg_ga=hh["avg_ga"],
            away_away_avg_gf=aa["avg_gf"],
            away_away_avg_ga=aa["avg_ga"],
        )

    def _label(self, home_rate: float, away_rate: float, side: str) -> str:
        """主队看主场率vs客场率，客队看客场率vs主场率"""
        if side == "home":
            strong, weak = home_rate, away_rate
        else:
            strong, weak = away_rate, home_rate

        if strong >= 0.6 and weak < 0.35:
            return f"{side}_dragon"
        elif strong < 0.3 and weak >= 0.4:
            return f"{side}_worm"
        elif strong >= 0.5:
            return f"{side}_solid"
        else:
            return f"{side}_neutral"

    def _get_home_matches(self, team, before_date, storage, limit=10):
        import json
        conn = storage._conn()
        rows = conn.execute(
            "SELECT md.data_json FROM matches m JOIN match_data md ON m.match_key=md.match_key "
            "WHERE md.data_type='match' AND md.source NOT IN ('factor','model') "
            "AND m.home_team=? AND m.date<? ORDER BY m.date DESC LIMIT ?",
            (team, before_date, limit*2)).fetchall()
        conn.close()
        results = []
        for r in rows:
            d = json.loads(r["data_json"])
            hs, aws = d.get("home_score"), d.get("away_score")
            if hs is None or aws is None: continue
            try: hs, aws = int(hs), int(aws)
            except: continue
            results.append({"gf": hs, "ga": aws, "is_home": True})
        return results[:limit]

    def _get_away_matches(self, team, before_date, storage, limit=10):
        import json
        conn = storage._conn()
        rows = conn.execute(
            "SELECT md.data_json FROM matches m JOIN match_data md ON m.match_key=md.match_key "
            "WHERE md.data_type='match' AND md.source NOT IN ('factor','model') "
            "AND m.away_team=? AND m.date<? ORDER BY m.date DESC LIMIT ?",
            (team, before_date, limit*2)).fetchall()
        conn.close()
        results = []
        for r in rows:
            d = json.loads(r["data_json"])
            hs, aws = d.get("home_score"), d.get("away_score")
            if hs is None or aws is None: continue
            try: hs, aws = int(hs), int(aws)
            except: continue
            results.append({"gf": aws, "ga": hs, "is_home": False})
        return results[:limit]

    def _calc(self, matches: List[Dict], is_home_perspective: bool) -> Dict:
        if not matches:
            return {"w":0,"d":0,"l":0,"win_rate":0,"avg_gf":0,"avg_ga":0}
        w=d=l=gf=ga=0
        for m in matches:
            gf+=m["gf"]; ga+=m["ga"]
            if m["gf"]>m["ga"]: w+=1
            elif m["gf"]==m["ga"]: d+=1
            else: l+=1
        n=len(matches)
        return {"w":w,"d":d,"l":l,"win_rate":round(w/n,3),
                "avg_gf":round(gf/n,2),"avg_ga":round(ga/n,2)}
