"""
概率模型基类

模型 = 拿因素算概率。权重可调，模型可替换。
模型输出不影响因素数据，可以反复跑。

输出格式：
{
    "model": "basic_linear",
    "model_version": "1.0",
    "home_win_prob": 0.45,
    "draw_prob": 0.28,
    "away_win_prob": 0.27,
    "over_2_5_prob": 0.52,
    "under_2_5_prob": 0.48,
    "btts_yes_prob": 0.58,
    "btts_no_prob": 0.42,
    "confidence": 0.72,
    "factor_weights_used": { "standing": 0.15, "form": 0.12, ... },
    "factor_contributions": { "standing": +0.05, "form": -0.02, ... },
}
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List
from fetchers.storage.crud import UnifiedStorage


class BaseModel(ABC):
    model_name: str = ""
    model_version: str = "1.0"

    def __init__(self):
        if not self.model_name:
            raise ValueError(f"{self.__class__.__name__} 必须定义 model_name")

    def run(self, match_key: str, storage: UnifiedStorage,
            force: bool = False) -> Dict[str, Any]:
        """运行模型并自动存储"""
        if not force:
            cached = self._load_cached(match_key, storage)
            if cached:
                return cached

        # 加载所有因素
        factors = self._load_factors(match_key, storage)
        if not factors:
            return self._no_factors()

        result = self.predict(match_key, factors, storage)
        result["model"] = self.model_name
        result["model_version"] = self.model_version

        self._save(match_key, result, storage)
        return result

    @abstractmethod
    def predict(self, match_key: str, factors: Dict[str, Dict],
                storage: UnifiedStorage) -> Dict[str, Any]:
        """子类实现：拿因素算概率"""
        pass

    def _load_factors(self, match_key: str, storage: UnifiedStorage) -> Dict[str, Dict]:
        """从DB加载该比赛的所有因素"""
        import json
        conn = storage._conn()
        rows = conn.execute(
            "SELECT data_type, data_json FROM match_data "
            "WHERE match_key=? AND source='factor' AND data_type LIKE 'factor:%'",
            (match_key,)
        ).fetchall()
        conn.close()
        factors = {}
        for r in rows:
            name = r["data_type"].replace("factor:", "")
            data = json.loads(r["data_json"])
            if data.get("confidence", 0) > 0:
                factors[name] = data
        return factors

    def _load_cached(self, match_key: str, storage: UnifiedStorage) -> Optional[Dict]:
        import json
        conn = storage._conn()
        row = conn.execute(
            "SELECT data_json FROM match_data "
            "WHERE match_key=? AND source='model' AND data_type=?",
            (match_key, f"model:{self.model_name}")
        ).fetchone()
        conn.close()
        return json.loads(row["data_json"]) if row else None

    def _save(self, match_key: str, result: Dict, storage: UnifiedStorage):
        import json
        conn = storage._conn()
        conn.execute(
            "INSERT INTO match_data (match_key,source,data_type,data_json) "
            "VALUES (?,'model',?,?) "
            "ON CONFLICT(match_key,source,data_type) DO UPDATE SET "
            "data_json=excluded.data_json, "
            "fetched_at=datetime('now','localtime')",
            (match_key, f"model:{self.model_name}",
             json.dumps(result, ensure_ascii=False, default=str))
        )
        conn.commit()
        conn.close()

    def _no_factors(self) -> Dict[str, Any]:
        return {
            "home_win_prob": 0.33, "draw_prob": 0.33, "away_win_prob": 0.34,
            "confidence": 0.0,
            "summary": "无因素数据，使用均匀分布",
        }

    def _normalize_probs(self, home: float, draw: float, away: float) -> tuple:
        """归一化概率"""
        total = home + draw + away
        if total <= 0:
            return 0.33, 0.33, 0.34
        return round(home/total, 4), round(draw/total, 4), round(away/total, 4)