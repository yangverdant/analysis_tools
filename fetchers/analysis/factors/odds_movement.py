"""CLV(收盘线价值)因素 — 开盘→闭盘赔率变化是市场最强信号"""

import json
from typing import Dict, Any
from .base_factor import BaseFactor


class OddsMovementFactor(BaseFactor):
    factor = "odds_movement"
    title = "赔率异动"
    factor_type = "numeric"

    def extract(self, match_key: str, storage) -> Dict[str, Any]:
        conn = storage._conn()
        rows = conn.execute(
            "SELECT source, data_type, data_json FROM match_data "
            "WHERE match_key=? AND data_type='odds'",
            (match_key,)
        ).fetchall()
        conn.close()

        # 从football-data-co-uk等源获取开盘+闭盘赔率
        opening_probs = []
        closing_probs = []
        b365_clv = None
        pinnacle_clv = None

        for r in rows:
            data = json.loads(r["data_json"])
            source = r["source"]

            # 开盘赔率
            oh = data.get("home_win") or data.get("avg_home_win")
            od = data.get("draw") or data.get("avg_draw")
            oa = data.get("away_win") or data.get("avg_away_win")
            if not (oh and od and oa):
                continue
            try:
                oh, od, oa = float(oh), float(od), float(oa)
            except (ValueError, TypeError):
                continue

            total = 1/oh + 1/od + 1/oa
            rr = 1 / total
            ohp = rr / oh
            odp = rr / od
            oap = rr / oa
            opening_probs.append((ohp, odp, oap))

            # 闭盘赔率
            ch = data.get("closing_avg_home_win")
            cd = data.get("closing_avg_draw")
            ca = data.get("closing_avg_away_win")
            if ch and cd and ca:
                try:
                    ch, cd, ca = float(ch), float(cd), float(ca)
                    ct = 1/ch + 1/cd + 1/ca
                    cr = 1 / ct
                    chp = cr / ch
                    cdp = cr / cd
                    cap = cr / ca
                    closing_probs.append((chp, cdp, cap))
                except (ValueError, TypeError):
                    pass

            # B365单独计算CLV
            bh = data.get("b365_home_win")
            bd = data.get("b365_draw")
            ba = data.get("b365_away_win")
            if bh and bd and ba and ch and cd and ca:
                try:
                    bh, bd, ba = float(bh), float(bd), float(ba)
                    bt = 1/bh + 1/bd + 1/ba
                    br = 1 / bt
                    b365_clv = {
                        "home": round(br/bh - chp, 4) if closing_probs else None,
                        "draw": round(br/bd - cdp, 4) if closing_probs else None,
                        "away": round(br/ba - cap, 4) if closing_probs else None,
                    }
                except (ValueError, TypeError):
                    pass

            # Pinnacle单独计算CLV
            ph = data.get("pinnacle_home_win")
            pd_ = data.get("pinnacle_draw")
            pa = data.get("pinnacle_away_win")
            if ph and pd_ and pa and ch and cd and ca:
                try:
                    ph, pd_, pa = float(ph), float(pd_), float(pa)
                    pt = 1/ph + 1/pd_ + 1/pa
                    pr = 1 / pt
                    pinnacle_clv = {
                        "home": round(pr/ph - chp, 4) if closing_probs else None,
                        "draw": round(pr/pd_ - cdp, 4) if closing_probs else None,
                        "away": round(pr/pa - cap, 4) if closing_probs else None,
                    }
                except (ValueError, TypeError):
                    pass

        if not opening_probs:
            return self._no_data("无赔率数据")

        # 平均开盘概率
        avg_ohp = sum(p[0] for p in opening_probs) / len(opening_probs)
        avg_odp = sum(p[1] for p in opening_probs) / len(opening_probs)
        avg_oap = sum(p[2] for p in opening_probs) / len(opening_probs)

        # 平均闭盘概率
        if closing_probs:
            avg_chp = sum(p[0] for p in closing_probs) / len(closing_probs)
            avg_cdp = sum(p[1] for p in closing_probs) / len(closing_probs)
            avg_cap = sum(p[2] for p in closing_probs) / len(closing_probs)

            # CLV信号: 闭盘概率 - 开盘概率
            # 正值=市场升了主队预期, 负值=市场降了主队预期
            home_clv = avg_chp - avg_ohp
            away_clv = avg_cap - avg_oap

            # diff: 主队CLV - 客队CLV (正值=市场看好主队)
            diff = home_clv - away_clv

            # 信号强度: CLV越大，信息量越多
            clv_magnitude = abs(home_clv) + abs(away_clv)
            confidence = min(0.95, 0.5 + clv_magnitude * 5)

            raw = {
                "opening_home_prob": round(avg_ohp, 4),
                "opening_draw_prob": round(avg_odp, 4),
                "opening_away_prob": round(avg_oap, 4),
                "closing_home_prob": round(avg_chp, 4),
                "closing_draw_prob": round(avg_cdp, 4),
                "closing_away_prob": round(avg_cap, 4),
                "home_clv": round(home_clv, 4),
                "away_clv": round(away_clv, 4),
                "has_closing": True,
            }
            if b365_clv:
                raw["b365_clv"] = b365_clv
            if pinnacle_clv:
                raw["pinnacle_clv"] = pinnacle_clv

            return self._numeric(
                home_value=round(home_clv, 4),
                away_value=round(away_clv, 4),
                unit="CLV概率变化",
                higher_is_better=True,
                confidence=round(confidence, 2),
                **raw,
            )
        else:
            # 无闭盘赔率 — 信号极弱
            return self._numeric(
                home_value=0,
                away_value=0,
                unit="CLV概率变化",
                higher_is_better=True,
                confidence=0.1,
                has_closing=False,
            )