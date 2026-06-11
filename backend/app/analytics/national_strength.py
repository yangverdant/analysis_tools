"""
国家队实力评估器

FIFA排名 → 概率转换 + Elo补充
"""
import logging
import sqlite3
from typing import Dict, Optional

logger = logging.getLogger(__name__)


class NationalTeamStrengthEstimator:
    """
    国家队实力评估 — FIFA排名优先，Elo补充

    FIFA排名→概率公式:
      rank_diff = away_rank - home_rank  (排名越低越强)
      home_base = 0.40 + rank_diff * 0.003
      draw_base = 0.27 - |rank_diff| * 0.001

    经验系数来自v3.9.2回测验证，待进一步校准。
    """

    def estimate(
        self,
        home_team_id: int,
        away_team_id: int,
        conn: sqlite3.Connection,
    ) -> Dict:
        """
        评估国家队实力，返回概率

        优先级: FIFA排名 → Elo → 赔率反推标记
        """
        # 1. 尝试FIFA排名
        home_fifa = self._get_fifa_rank(home_team_id, conn)
        away_fifa = self._get_fifa_rank(away_team_id, conn)

        if home_fifa and away_fifa:
            return self._fifa_to_probability(home_fifa, away_fifa)

        # 2. 尝试Elo
        home_elo = self._get_elo(home_team_id, conn)
        away_elo = self._get_elo(away_team_id, conn)

        if home_elo and away_elo:
            return self._elo_to_probability(home_elo, away_elo)

        # 3. 都没有
        return {
            "method": "unknown",
            "confidence": "low",
            "probabilities": {"home_win": 0.33, "draw": 0.33, "away_win": 0.33},
        }

    def _get_fifa_rank(self, team_id: int, conn: sqlite3.Connection) -> Optional[Dict]:
        """获取最近FIFA排名"""
        try:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT rank, points, rank_date
                FROM fifa_rankings
                WHERE team_id = ?
                ORDER BY rank_date DESC
                LIMIT 1
            """, (team_id,))
            row = cursor.fetchone()
            if row:
                return {"rank": row[0], "points": row[1], "date": row[2]}
        except Exception as e:
            logger.debug("FIFA排名查询失败 team_id=%s: %s", team_id, e)
        return None

    def _get_elo(self, team_id: int, conn: sqlite3.Connection) -> Optional[float]:
        """获取Elo"""
        try:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT elo_rating FROM elo_ratings WHERE team_id = ?",
                (team_id,),
            )
            row = cursor.fetchone()
            if row:
                return float(row[0])
        except Exception as e:
            logger.debug("Elo查询失败 team_id=%s: %s", team_id, e)
        return None

    def _fifa_to_probability(self, home_fifa: Dict, away_fifa: Dict) -> Dict:
        """FIFA排名差 → 概率"""
        # 排名越低越强 (1=最强)
        home_rank = float(home_fifa["rank"])
        away_rank = float(away_fifa["rank"])
        rank_diff = away_rank - home_rank

        # 线性映射 (经验公式，待从历史数据校准)
        home_base = 0.40 + rank_diff * 0.003
        home_base = max(0.15, min(0.70, home_base))

        draw_base = 0.27 - abs(rank_diff) * 0.001
        draw_base = max(0.20, min(0.35, draw_base))

        away_base = 1 - home_base - draw_base
        away_base = max(0.05, away_base)

        # 归一化
        total = home_base + draw_base + away_base

        # FIFA points作为辅助信号
        points_diff = float(home_fifa.get("points", 0) or 0) - float(away_fifa.get("points", 0) or 0)
        # points差距大 → 微调
        if abs(points_diff) > 200:
            points_adj = 0.02 if points_diff > 0 else -0.02
            home_base += points_adj
            away_base -= points_adj
            total = home_base + draw_base + away_base

        return {
            "method": "fifa",
            "confidence": "medium",
            "probabilities": {
                "home_win": round(home_base / total, 4),
                "draw": round(draw_base / total, 4),
                "away_win": round(away_base / total, 4),
            },
            "home_fifa": home_fifa,
            "away_fifa": away_fifa,
            "rank_diff": rank_diff,
        }

    def _elo_to_probability(self, home_elo: float, away_elo: float) -> Dict:
        """Elo差 → 概率 (国家队版本，与俱乐部Elo公式相同)"""
        elo_diff = home_elo - away_elo

        # 标准Elo概率公式
        import math
        exp_home = 1 / (1 + 10 ** (-elo_diff / 400))

        # 三分法: home / draw / away
        # draw概率由Elo差距决定
        draw_prob = 0.26 * math.exp(-abs(elo_diff) / 600)
        draw_prob = max(0.10, min(0.35, draw_prob))

        home_prob = exp_home * (1 - draw_prob)
        away_prob = (1 - exp_home) * (1 - draw_prob)

        return {
            "method": "elo_national",
            "confidence": "medium",
            "probabilities": {
                "home_win": round(home_prob, 4),
                "draw": round(draw_prob, 4),
                "away_win": round(away_prob, 4),
            },
            "home_elo": home_elo,
            "away_elo": away_elo,
            "elo_diff": elo_diff,
        }
