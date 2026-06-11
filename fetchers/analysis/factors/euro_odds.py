"""欧赔因素 — 输出开盘+闭盘赔率、CLV变化"""

import json
from typing import Dict, Any
from fetchers.common.team_names import normalize_team_name
from .base_factor import BaseFactor


class EuroOddsFactor(BaseFactor):
    factor = "euro_odds"
    title = "欧赔"
    factor_type = "numeric"

    def extract(self, match_key: str, storage) -> Dict[str, Any]:
        match = self._get_match(match_key, storage)
        if not match:
            return self._no_data("未找到比赛")

        # 从各源收集赔率
        conn = storage._conn()
        rows = conn.execute(
            "SELECT source, data_type, data_json FROM match_data "
            "WHERE match_key=? AND data_type IN ('odds','match')",
            (match_key,)
        ).fetchall()
        conn.close()

        opening_list = []
        closing_list = []
        b365_opening = {}
        b365_closing = {}
        pinnacle_opening = {}
        ah_handicap = None
        ah_home_odds = None
        ah_away_odds = None
        ou_over_odds = None
        ou_under_odds = None

        for r in rows:
            data = json.loads(r["data_json"])
            source = r["source"]

            # 开盘赔率 (home_win/draw/away_win = 开盘均价)
            hw = data.get("home_win") or data.get("avg_home_win")
            d = data.get("draw") or data.get("avg_draw")
            aw = data.get("away_win") or data.get("avg_away_win")
            if hw and d and aw:
                try:
                    opening_list.append({
                        "source": source,
                        "home": float(hw), "draw": float(d), "away": float(aw),
                    })
                except (ValueError, TypeError):
                    pass

            # 闭盘赔率 (closing_avg_*)
            chw = data.get("closing_avg_home_win")
            cd = data.get("closing_avg_draw")
            caw = data.get("closing_avg_away_win")
            if chw and cd and caw:
                try:
                    closing_list.append({
                        "source": source,
                        "home": float(chw), "draw": float(cd), "away": float(caw),
                    })
                except (ValueError, TypeError):
                    pass

            # B365开盘
            bh = data.get("b365_home_win")
            bd = data.get("b365_draw")
            ba = data.get("b365_away_win")
            if bh and bd and ba:
                try:
                    b365_opening = {"home": float(bh), "draw": float(bd), "away": float(ba)}
                except (ValueError, TypeError):
                    pass

            # Pinnacle开盘
            ph = data.get("pinnacle_home_win")
            pd_ = data.get("pinnacle_draw")
            pa = data.get("pinnacle_away_win")
            if ph and pd_ and pa:
                try:
                    pinnacle_opening = {"home": float(ph), "draw": float(pd_), "away": float(pa)}
                except (ValueError, TypeError):
                    pass

            # 亚盘
            hc = data.get("ah_handicap")
            if hc is not None:
                try:
                    ah_handicap = float(hc)
                    ah_home_odds = float(data.get("avg_ah_home", 0))
                    ah_away_odds = float(data.get("avg_ah_away", 0))
                except (ValueError, TypeError):
                    pass

            # 大小球
            o25 = data.get("avg_over_2_5") or data.get("b365_over_2_5")
            u25 = data.get("avg_under_2_5") or data.get("b365_under_2_5")
            if o25 and u25:
                try:
                    ou_over_odds = float(o25)
                    ou_under_odds = float(u25)
                except (ValueError, TypeError):
                    pass

        if not opening_list:
            return self._no_data("无欧赔数据")

        # 开盘隐含概率
        hp, dp, ap = self._avg_implied_prob(opening_list)

        # 闭盘隐含概率 (如果有)
        chp, cdp, cap = self._avg_implied_prob(closing_list) if closing_list else (None, None, None)

        # CLV: 开盘→闭盘概率变化
        clv = {}
        if chp is not None:
            clv = {
                "home_delta": round(chp - hp, 4),
                "draw_delta": round(cdp - dp, 4),
                "away_delta": round(cap - ap, 4),
                "opening_home": hp, "opening_draw": dp, "opening_away": ap,
                "closing_home": chp, "closing_draw": cdp, "closing_away": cap,
            }

        # diff: 主胜概率 - 客胜概率 (用闭盘计算diff更准确)
        if chp is not None:
            diff = chp - cap
        else:
            diff = hp - ap

        # 使用闭盘赔率计算home/away_value (闭盘是更好的市场定价)
        home_value = chp if chp is not None else hp
        away_value = cap if cap is not None else ap
        draw_prob = cdp if cdp is not None else dp

        raw = {
            "avg_home_odds": round(sum(o["home"] for o in opening_list)/len(opening_list), 2),
            "avg_draw_odds": round(sum(o["draw"] for o in opening_list)/len(opening_list), 2),
            "avg_away_odds": round(sum(o["away"] for o in opening_list)/len(opening_list), 2),
            "source_count": len(opening_list),
            "sources": [o["source"] for o in opening_list],
        }

        # 闭盘赔率
        if closing_list:
            raw["closing_avg_home_odds"] = round(sum(o["home"] for o in closing_list)/len(closing_list), 2)
            raw["closing_avg_draw_odds"] = round(sum(o["draw"] for o in closing_list)/len(closing_list), 2)
            raw["closing_avg_away_odds"] = round(sum(o["away"] for o in closing_list)/len(closing_list), 2)
            raw["has_closing"] = True

        # CLV变化
        if clv:
            raw["clv"] = clv

        # B365开盘
        if b365_opening:
            raw["b365_opening"] = b365_opening

        # Pinnacle开盘
        if pinnacle_opening:
            raw["pinnacle_opening"] = pinnacle_opening

        # 亚盘数据
        if ah_handicap is not None:
            raw["ah_handicap"] = ah_handicap
            raw["ah_home_odds"] = ah_home_odds
            raw["ah_away_odds"] = ah_away_odds

        # 大小球数据
        if ou_over_odds is not None:
            raw["ou_over_2_5_odds"] = ou_over_odds
            raw["ou_under_2_5_odds"] = ou_under_odds

        # 信心度: 有闭盘赔率时更高
        confidence = 0.90 if closing_list else 0.85

        return self._numeric(
            home_value=round(home_value, 4),
            away_value=round(away_value, 4),
            unit="隐含胜率",
            higher_is_better=True,
            confidence=confidence,
            draw_prob=draw_prob,
            **raw,
        )

    @staticmethod
    def _avg_implied_prob(odds_list) -> tuple:
        """计算多源赔率的平均隐含概率"""
        home_probs, draw_probs, away_probs = [], [], []
        for o in odds_list:
            total = 1/o["home"] + 1/o["draw"] + 1/o["away"]
            rr = 1 / total
            home_probs.append(rr / o["home"])
            draw_probs.append(rr / o["draw"])
            away_probs.append(rr / o["away"])
        hp = round(sum(home_probs)/len(home_probs), 4)
        dp = round(sum(draw_probs)/len(draw_probs), 4)
        ap = round(sum(away_probs)/len(away_probs), 4)
        return hp, dp, ap