"""
近期状态分析

分析两队最近N场比赛的胜负走势、进球失球趋势。
"""

from typing import Dict, Any, List
from fetchers.storage.crud import UnifiedStorage
from fetchers.common.team_names import normalize_team_name
from .base import BaseAnalyzer


class FormAnalysis(BaseAnalyzer):
    name = "form_analysis"
    title = "近期状态"

    # 分析最近N场
    RECENT_N = 6

    def analyze(self, match_key: str, storage: UnifiedStorage) -> Dict[str, Any]:
        match = self._get_match_info(match_key, storage)
        if not match:
            return self._no_data("未找到比赛信息")

        home = normalize_team_name(match.get("home_team", ""))
        away = normalize_team_name(match.get("away_team", ""))
        date = match.get("date", "")

        if not home or not away:
            return self._no_data("缺少队名")

        # 获取两队历史比赛
        home_matches = self._get_team_recent_matches(home, date, storage)
        away_matches = self._get_team_recent_matches(away, date, storage)

        if not home_matches and not away_matches:
            return self._no_data("无历史赛果数据")

        # 计算状态指标
        home_form = self._calc_form(home_matches, home)
        away_form = self._calc_form(away_matches, away)

        # 信号判断
        home_score = home_form["form_score"]
        away_score = away_form["form_score"]
        diff = home_score - away_score

        if abs(diff) >= 2.0:
            signal = "home" if diff > 0 else "away"
            strength = min(0.85, 0.4 + abs(diff) * 0.1)
        elif abs(diff) >= 1.0:
            signal = "home" if diff > 0 else "away"
            strength = 0.3 + abs(diff) * 0.1
        else:
            signal = "neutral"
            strength = 0.1

        summary = (
            f"主队近{home_form['total']}场{home_form['w']}-{home_form['d']}-{home_form['l']}"
            f"(得分{home_score:.1f})，"
            f"客队近{away_form['total']}场{away_form['w']}-{away_form['d']}-{away_form['l']}"
            f"(得分{away_score:.1f})"
        )

        return self._result(
            confidence=0.7 if (home_matches and away_matches) else 0.4,
            signal=signal,
            signal_strength=strength,
            summary=summary,
            home_form=home_form,
            away_form=away_form,
        )

    def _get_team_recent_matches(self, team: str, before_date: str,
                                  storage: UnifiedStorage) -> List[Dict]:
        """获取某队在指定日期前的最近N场比赛"""
        conn = storage._conn()
        rows = conn.execute("""
            SELECT m.match_key, m.date, m.home_team, m.away_team, md.data_json
            FROM matches m
            JOIN match_data md ON m.match_key = md.match_key
            WHERE md.data_type = 'match'
            AND (m.home_team = ? OR m.away_team = ?)
            AND m.date < ?
            ORDER BY m.date DESC
            LIMIT ?
        """, (team, team, before_date, self.RECENT_N * 2)).fetchall()
        conn.close()

        import json
        results = []
        for r in rows:
            data = json.loads(r["data_json"])
            hs = data.get("home_score")
            aws = data.get("away_score")
            if hs is None or aws is None:
                continue
            try:
                hs = int(hs)
                aws = int(aws)
            except (ValueError, TypeError):
                continue

            is_home = (normalize_team_name(r["home_team"]) == team)
            results.append({
                "date": r["date"],
                "home": r["home_team"],
                "away": r["away_team"],
                "home_score": hs,
                "away_score": aws,
                "is_home": is_home,
            })

        return results[:self.RECENT_N]

    def _calc_form(self, matches: List[Dict], team: str) -> Dict:
        """计算状态指标"""
        if not matches:
            return {"total": 0, "w": 0, "d": 0, "l": 0, "gf": 0, "ga": 0,
                    "form_score": 0, "form_str": "", "trend": "unknown"}

        w = d = l = gf = ga = 0
        form_chars = []

        for m in matches:
            team_gf = m["home_score"] if m["is_home"] else m["away_score"]
            team_ga = m["away_score"] if m["is_home"] else m["home_score"]
            gf += team_gf
            ga += team_ga

            if team_gf > team_ga:
                w += 1
                form_chars.append("W")
            elif team_gf == team_ga:
                d += 1
                form_chars.append("D")
            else:
                l += 1
                form_chars.append("L")

        total = len(matches)
        # 加权得分: 胜3 平1 负0，近期权重更高
        form_score = 0
        for i, fc in enumerate(form_chars):
            weight = 1.0 + (i * 0.15)  # 越近权重越高
            if fc == "W":
                form_score += 3 * weight
            elif fc == "D":
                form_score += 1 * weight
        form_score /= total

        # 趋势判断
        if total >= 3:
            recent_3 = form_chars[:3]
            older = form_chars[3:] if len(form_chars) > 3 else []
            recent_pts = sum(3 if c == "W" else 1 if c == "D" else 0 for c in recent_3)
            older_pts = sum(3 if c == "W" else 1 if c == "D" else 0 for c in older) if older else recent_pts
            if recent_pts > older_pts:
                trend = "rising"
            elif recent_pts < older_pts:
                trend = "declining"
            else:
                trend = "stable"
        else:
            trend = "unknown"

        return {
            "total": total,
            "w": w, "d": d, "l": l,
            "gf": gf, "ga": ga,
            "gf_pg": round(gf / total, 2),
            "ga_pg": round(ga / total, 2),
            "form_score": round(form_score, 2),
            "form_str": "".join(form_chars),
            "trend": trend,
        }