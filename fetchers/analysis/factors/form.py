"""近期状态因素 — 多窗口(6/10/20场)"""

from typing import Dict, Any, List
from fetchers.common.team_names import normalize_team_name
from .base_factor import BaseFactor


class FormFactor(BaseFactor):
    factor = "form"
    title = "近期状态"
    factor_type = "numeric"

    WINDOWS = [6, 10, 20]

    def extract(self, match_key: str, storage) -> Dict[str, Any]:
        match = self._get_match(match_key, storage)
        if not match or not match.get("home_team"):
            return self._no_data("未找到比赛")

        home = normalize_team_name(match["home_team"])
        away = normalize_team_name(match["away_team"])
        date = match.get("date", "")

        # 取最近20场（最大窗口），小窗口从中截取
        max_n = max(self.WINDOWS)
        hm_all = self._get_team_recent_matches(home, date, storage, max_n)
        am_all = self._get_team_recent_matches(away, date, storage, max_n)

        if not hm_all and not am_all:
            return self._no_data("无历史赛果")

        # 各窗口计算
        home_windows = {}
        away_windows = {}
        for w in self.WINDOWS:
            home_windows[w] = self._calc(hm_all[:w])
            away_windows[w] = self._calc(am_all[:w])

        # 主信号用6场（和之前一致），10场和20场作为补充维度
        hf6 = home_windows[6]
        af6 = away_windows[6]
        hf10 = home_windows[10]
        af10 = away_windows[10]
        hf20 = home_windows[20]
        af20 = away_windows[20]

        # 综合得分: 6场*0.5 + 10场*0.3 + 20场*0.2
        h_combined = (hf6["score"] * 0.5 + hf10["score"] * 0.3 + hf20["score"] * 0.2)
        a_combined = (af6["score"] * 0.5 + af10["score"] * 0.3 + af20["score"] * 0.2)

        # 置信度：有10场数据时更高
        has_10 = len(hm_all) >= 10 and len(am_all) >= 10
        has_20 = len(hm_all) >= 20 and len(am_all) >= 20
        base_conf = 0.7 if (hm_all and am_all) else 0.4
        conf = min(1.0, base_conf + (0.1 if has_10 else 0) + (0.1 if has_20 else 0))

        return self._numeric(
            home_value=round(h_combined, 2),
            away_value=round(a_combined, 2),
            unit="状态分(6/10/20场加权)",
            higher_is_better=True,
            confidence=conf,
            # 6场详情
            home_form=hf6["form_str"],
            away_form=af6["form_str"],
            home_w6=hf6["w"], home_d6=hf6["d"], home_l6=hf6["l"],
            away_w6=af6["w"], away_d6=af6["d"], away_l6=af6["l"],
            home_gf6=hf6["gf"], home_ga6=hf6["ga"],
            away_gf6=af6["gf"], away_ga6=af6["ga"],
            home_trend6=hf6["trend"], away_trend6=af6["trend"],
            home_score6=hf6["score"], away_score6=af6["score"],
            # 10场详情
            home_form10=hf10["form_str"],
            away_form10=af10["form_str"],
            home_w10=hf10["w"], home_d10=hf10["d"], home_l10=hf10["l"],
            away_w10=af10["w"], away_d10=af10["d"], away_l10=af10["l"],
            home_gf10=hf10["gf"], home_ga10=hf10["ga"],
            away_gf10=af10["gf"], away_ga10=af10["ga"],
            home_trend10=hf10["trend"], away_trend10=af10["trend"],
            home_score10=hf10["score"], away_score10=af10["score"],
            # 20场详情
            home_form20=hf20["form_str"],
            away_form20=af20["form_str"],
            home_w20=hf20["w"], home_d20=hf20["d"], home_l20=hf20["l"],
            away_w20=af20["w"], away_d20=af20["d"], away_l20=af20["l"],
            home_gf20=hf20["gf"], home_ga20=hf20["ga"],
            away_gf20=af20["gf"], away_ga20=af20["ga"],
            home_trend20=hf20["trend"], away_trend20=af20["trend"],
            home_score20=hf20["score"], away_score20=af20["score"],
        )

    def _calc(self, matches: List[Dict]) -> Dict:
        if not matches:
            return {"score": 0, "w": 0, "d": 0, "l": 0,
                    "gf": 0, "ga": 0, "form_str": "", "trend": "unknown"}

        w = d = l = gf = ga = 0
        chars = []
        for m in matches:
            tgf = m["home_score"] if m["is_home"] else m["away_score"]
            tga = m["away_score"] if m["is_home"] else m["home_score"]
            gf += tgf; ga += tga
            if tgf > tga:   w += 1; chars.append("W")
            elif tgf == tga: d += 1; chars.append("D")
            else:            l += 1; chars.append("L")

        n = len(matches)
        # 近期加权得分
        score = 0
        for i, c in enumerate(chars):
            wt = 1.0 + i * 0.15
            if c == "W": score += 3 * wt
            elif c == "D": score += 1 * wt
        score = round(score / n, 2) if n else 0

        # 趋势
        if n >= 4:
            r3 = sum(3 if c == "W" else 1 if c == "D" else 0 for c in chars[:3])
            o3 = sum(3 if c == "W" else 1 if c == "D" else 0 for c in chars[3:])
            trend = "rising" if r3 > o3 else "declining" if r3 < o3 else "stable"
        else:
            trend = "unknown"

        return {"score": score, "w": w, "d": d, "l": l,
                "gf": gf, "ga": ga, "form_str": "".join(chars), "trend": trend}