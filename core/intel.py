"""
8:00 临场信息 (intel.py)

赔率异动优先，伤病/停赛/天气/轮换补充。
"""
import logging
import sqlite3
from datetime import date, datetime, timedelta
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


class IntelCollector:
    """8:00 临场信息采集"""

    # 天气敏感联赛(风/雨/雪影响大)
    WEATHER_SENSITIVE = {
        "俄超", "瑞超", "挪超", "芬超", "冰岛超",
        "巴甲", "阿超", "解放者杯", "南美杯",
        "J联赛", "K联赛",
    }

    # FIFA国际比赛日窗口(2026年)
    # 来源: https://www.fifa.com/fifa-world-ranking
    FIFA_WINDOWS_2026 = [
        (date(2026, 3, 23), date(2026, 3, 31)),
        (date(2026, 6, 1), date(2026, 6, 14)),   # 世界杯前
        (date(2026, 6, 11), date(2026, 7, 19)),   # 世界杯正赛
        (date(2026, 9, 7), date(2026, 9, 15)),
        (date(2026, 10, 6), date(2026, 10, 14)),
        (date(2026, 11, 9), date(2026, 11, 17)),
    ]

    # 友谊赛轮换率(历史统计)
    FRIENDLY_ROTATION = {
        "club": 0.65,
        "national_warmup": 0.40,
        "national_ranking": 0.25,
    }

    # 杯赛轮换率
    CUP_ROTATION = {
        "domestic_early": 0.45,
        "domestic_late": 0.15,
        "continental_group": 0.30,
        "continental_knockout": 0.05,
    }

    def __init__(self, db_path: str, config: dict = None):
        self.db_path = db_path
        self.config = config or {}

    def collect(self, match_date: date = None) -> Dict:
        """采集指定日期的临场信息"""
        if match_date is None:
            match_date = date.today()

        results = {
            "date": str(match_date),
            "odds_movement": [],
            "suspensions": [],
            "weather": [],
            "rotation_risks": [],
            "international_break": self._check_international_break(match_date),
        }

        # 1. 赔率异动
        try:
            results["odds_movement"] = self._detect_odds_movement(match_date)
        except Exception as e:
            logger.warning("赔率异动检测失败: %s", e)

        # 2. 红黄牌停赛
        try:
            results["suspensions"] = self._fetch_suspensions(match_date)
        except Exception as e:
            logger.warning("停赛查询失败: %s", e)

        # 3. 天气
        try:
            results["weather"] = self._fetch_weather(match_date)
        except Exception as e:
            logger.warning("天气查询失败: %s", e)

        # 4. 轮换风险评估
        try:
            results["rotation_risks"] = self._estimate_rotation_risks(match_date)
        except Exception as e:
            logger.warning("轮换评估失败: %s", e)

        return results

    # ── 赔率异动检测 ──

    def _detect_odds_movement(self, match_date: date) -> List[Dict]:
        """对比开盘 vs 当前赔率，检测>3%异动"""
        try:
            conn = sqlite3.connect(self.db_path, timeout=10)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            # 查找有开盘和最新赔率的比赛
            cursor.execute("""
                SELECT
                    lm.lottery_match_id,
                    lm.home_team_cn,
                    lm.away_team_cn,
                    open_odds.odds_data AS opening,
                    curr_odds.odds_data AS current
                FROM lottery_matches lm
                JOIN lottery_odds open_odds
                    ON lm.lottery_match_id = open_odds.lottery_match_id
                    AND open_odds.snapshot_type = 'opening'
                JOIN lottery_odds curr_odds
                    ON lm.lottery_match_id = curr_odds.lottery_match_id
                    AND curr_odds.snapshot_type = 'latest'
                WHERE lm.match_date = ?
                AND open_odds.play_type = 'spf'
                AND curr_odds.play_type = 'spf'
            """, (str(match_date),))

            changes = []
            for row in cursor.fetchall():
                import json
                opening = json.loads(row["opening"]) if isinstance(row["opening"], str) else row["opening"]
                current = json.loads(row["current"]) if isinstance(row["current"], str) else row["current"]

                open_probs = self._odds_to_probs(opening)
                curr_probs = self._odds_to_probs(current)

                if not open_probs or not curr_probs:
                    continue

                for outcome in ["home", "draw", "away"]:
                    delta = curr_probs[outcome] - open_probs[outcome]
                    if abs(delta) > 0.03:
                        changes.append({
                            "lottery_match_id": row["lottery_match_id"],
                            "match": f"{row['home_team_cn']} vs {row['away_team_cn']}",
                            "outcome": outcome,
                            "direction": "up" if delta > 0 else "down",
                            "magnitude": round(abs(delta), 4),
                            "open_prob": round(open_probs[outcome], 4),
                            "curr_prob": round(curr_probs[outcome], 4),
                        })

            conn.close()
            return changes

        except Exception as e:
            logger.debug("赔率异动检测异常: %s", e)
            return []

    @staticmethod
    def _odds_to_probs(odds_data: dict) -> Optional[Dict]:
        """赔率 → 隐含概率"""
        try:
            h = float(odds_data.get("spf_home", odds_data.get("home", 0)))
            d = float(odds_data.get("spf_draw", odds_data.get("draw", 0)))
            a = float(odds_data.get("spf_away", odds_data.get("away", 0)))
            if h <= 1 or d <= 1 or a <= 1:
                return None
            total = 1 / h + 1 / d + 1 / a
            return {
                "home": round((1 / h) / total, 4),
                "draw": round((1 / d) / total, 4),
                "away": round((1 / a) / total, 4),
            }
        except Exception:
            return None

    # ── 红黄牌停赛 ──

    def _fetch_suspensions(self, match_date: date) -> List[Dict]:
        """
        查询停赛信息

        当前: 从DB的injuries/sidelined表查(如果有)
        中期: 从apifootball suspensions端点获取
        """
        try:
            conn = sqlite3.connect(self.db_path, timeout=10)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            # 检查是否有sidelined表
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='player_sidelined'")
            if not cursor.fetchone():
                conn.close()
                return []

            cursor.execute("""
                SELECT
                    ps.player_id,
                    ps.player_name,
                    ps.category,
                    ps.type_name,
                    t.name_en AS team_name,
                    t.team_id
                FROM player_sidelined ps
                JOIN teams t ON ps.team_id = t.team_id
                WHERE ps.category IN ('suspended', 'injury')
                AND ps.end_date >= ?
            """, (str(match_date),))

            results = []
            for row in cursor.fetchall():
                results.append({
                    "player": row["player_name"],
                    "team": row["team_name"],
                    "category": row["category"],
                    "type": row["type_name"],
                })

            conn.close()
            return results

        except Exception as e:
            logger.debug("停赛查询异常: %s", e)
            return []

    # ── 天气 ──

    def _fetch_weather(self, match_date: date) -> List[Dict]:
        """
        查询天气影响(仅天气敏感联赛)

        当前: 返回空列表(需接openweathermap)
        中期: 从openweathermap获取实时天气
        """
        # 天气采集需要venue城市+openweathermap API
        # 短期返回空, 标记为待实现
        return []

    # ── 国际比赛日检测 ──

    def _check_international_break(self, match_date: date) -> Dict:
        """检测match_date是否在FIFA国际比赛日窗口"""
        for start, end in self.FIFA_WINDOWS_2026:
            if start <= match_date <= end:
                return {
                    "is_international_break": True,
                    "window_start": str(start),
                    "window_end": str(end),
                    "impact_on_club": "rotation_risk_high",
                    "detail": "国际比赛日，俱乐部主力可能被征召",
                }
        return {"is_international_break": False}

    # ── 轮换风险评估 ──

    def _estimate_rotation_risks(self, match_date: date) -> List[Dict]:
        """评估今日比赛的轮换风险"""
        try:
            conn = sqlite3.connect(self.db_path, timeout=10)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            cursor.execute("""
                SELECT
                    lm.lottery_match_id,
                    lm.home_team_cn,
                    lm.away_team_cn,
                    l.name_en AS league_name,
                    l.competition_type
                FROM lottery_matches lm
                LEFT JOIN leagues l ON lm.league_id = l.league_id
                    OR l.name_cn = lm.league_name_cn
                WHERE lm.match_date = ?
            """, (str(match_date),))

            results = []
            for row in cursor.fetchall():
                rotation_prob = self._calc_rotation_probability(row)
                if rotation_prob > 0.15:
                    results.append({
                        "lottery_match_id": row["lottery_match_id"],
                        "match": f"{row['home_team_cn']} vs {row['away_team_cn']}",
                        "rotation_probability": round(rotation_prob, 2),
                        "league": row["league_name"],
                    })

            conn.close()
            return results

        except Exception as e:
            logger.debug("轮换评估异常: %s", e)
            return []

    def _calc_rotation_probability(self, match_row: dict) -> float:
        """计算单场比赛的轮换概率"""
        comp_type = match_row.get("competition_type", "league")
        league_name = match_row.get("league_name", "")

        # 友谊赛
        if comp_type == "friendly" or "友谊赛" in (league_name or ""):
            return self.FRIENDLY_ROTATION.get("club", 0.5)

        # 杯赛早期
        if comp_type == "cup":
            if any(kw in (league_name or "").lower() for kw in ["group", "小组赛"]):
                return self.CUP_ROTATION.get("continental_group", 0.3)
            return self.CUP_ROTATION.get("domestic_early", 0.3)

        # 国际比赛日 → 俱乐部比赛轮换风险
        match_date_str = match_row.get("match_date", "")
        if match_date_str:
            try:
                md = date.fromisoformat(match_date_str)
                break_info = self._check_international_break(md)
                if break_info.get("is_international_break") and comp_type == "league":
                    return 0.3
            except ValueError:
                pass

        return 0.0
