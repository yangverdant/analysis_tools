"""
因素提取器基类

因素 = 从原始数据中提取的、可量化、可对比的字段。
因素是事实，不涉及推断。

每个因素输出格式：
{
    "factor": "standing",           # 因素标识
    "title": "联赛排名",            # 中文标题
    "type": "numeric",             # numeric / categorical / text

    # numeric 类型
    "home_value": 3,               # 主队数值
    "away_value": 7,               # 客队数值
    "unit": "排名",                 # 单位
    "diff": -4,                    # home - away (正=主队优)
    "higher_is_better": False,     # 数值越大是否越好（排名越小越好=False）

    # categorical 类型
    "home_category": "rising",
    "away_category": "declining",

    # text 类型 (新闻/伤病描述等，有时效性)
    "home_text": "主力前锋伤缺",
    "away_text": "无重大伤病",
    "expires_at": "2026-05-26T00:00:00",  # 过期时间，过了就降权

    # 通用
    "confidence": 0.9,             # 数据置信度 0-1
    "raw": { ... },                # 原始数据备份
}
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
from fetchers.storage.crud import UnifiedStorage
from fetchers.common.team_names import normalize_team_name


class BaseFactor(ABC):
    factor: str = ""
    title: str = ""
    factor_type: str = ""  # numeric / categorical / text

    def __init__(self):
        if not self.factor or not self.title or not self.factor_type:
            raise ValueError(
                f"{self.__class__.__name__} 必须定义 factor, title, factor_type")

    def run(self, match_key: str, storage: UnifiedStorage,
            force: bool = False) -> Dict[str, Any]:
        """提取因素并自动存储"""
        if not force:
            cached = self._load_cached(match_key, storage)
            if cached:
                return cached

        result = self.extract(match_key, storage)
        result["factor"] = self.factor
        result["title"] = self.title
        result["type"] = self.factor_type

        self._save(match_key, result, storage)
        return result

    @abstractmethod
    def extract(self, match_key: str, storage: UnifiedStorage) -> Dict[str, Any]:
        """子类实现：从原始数据提取因素"""
        pass

    # ---- 存储 ----

    def _load_cached(self, match_key: str, storage: UnifiedStorage) -> Optional[Dict]:
        import json
        conn = storage._conn()
        row = conn.execute(
            "SELECT data_json FROM match_data "
            "WHERE match_key=? AND source='factor' AND data_type=?",
            (match_key, f"factor:{self.factor}")
        ).fetchone()
        conn.close()
        return json.loads(row["data_json"]) if row else None

    def _save(self, match_key: str, result: Dict, storage: UnifiedStorage):
        import json
        conn = storage._conn()
        conn.execute(
            "INSERT INTO match_data (match_key,source,data_type,data_json) "
            "VALUES (?,'factor',?,?) "
            "ON CONFLICT(match_key,source,data_type) DO UPDATE SET "
            "data_json=excluded.data_json, "
            "fetched_at=datetime('now','localtime')",
            (match_key, f"factor:{self.factor}",
             json.dumps(result, ensure_ascii=False, default=str))
        )
        conn.commit()
        conn.close()

    # ---- 构建结果 ----

    def _numeric(self, home_value, away_value, unit: str = "",
                 higher_is_better: bool = True,
                 confidence: float = 1.0, **raw) -> Dict[str, Any]:
        """构建数值型因素"""
        diff = home_value - away_value
        if not higher_is_better:
            diff = -diff  # 翻转，让正数始终=主队优
        return {
            "home_value": home_value,
            "away_value": away_value,
            "unit": unit,
            "diff": round(diff, 4),
            "higher_is_better": higher_is_better,
            "confidence": round(confidence, 2),
            "raw": raw,
        }

    def _categorical(self, home_category: str, away_category: str,
                     confidence: float = 1.0, **raw) -> Dict[str, Any]:
        """构建分类型因素"""
        return {
            "home_category": home_category,
            "away_category": away_category,
            "confidence": round(confidence, 2),
            "raw": raw,
        }

    def _text(self, home_text: str, away_text: str,
              expires_at: str = "", confidence: float = 1.0, **raw) -> Dict[str, Any]:
        """构建文字型因素（带时效性）"""
        return {
            "home_text": home_text,
            "away_text": away_text,
            "expires_at": expires_at,
            "confidence": round(confidence, 2),
            "raw": raw,
        }

    def _no_data(self, reason: str = "") -> Dict[str, Any]:
        return {
            "confidence": 0.0,
            "summary": f"数据不足{('：'+reason) if reason else ''}",
        }

    # ---- 通用查询 ----

    def _get_match(self, match_key: str, storage: UnifiedStorage) -> Optional[Dict]:
        return storage.get_match(match_key)

    def _get_standings_map(self, league: str, storage: UnifiedStorage) -> Dict[str, Dict]:
        standings = storage.get_standings(league)
        if not standings:
            return {}
        result = {}
        for s in standings:
            team = normalize_team_name(s.get("team", ""))
            if team:
                result[team] = s
        return result

    def _get_team_recent_matches(self, team: str, before_date: str,
                                  storage: UnifiedStorage, limit: int = 6) -> list:
        import json
        conn = storage._conn()
        rows = conn.execute(
            "SELECT m.match_key,m.date,m.home_team,m.away_team,md.data_json "
            "FROM matches m JOIN match_data md ON m.match_key=md.match_key "
            "WHERE md.data_type='match' AND md.source!='factor' AND md.source!='model' "
            "AND (m.home_team=? OR m.away_team=?) AND m.date<? "
            "ORDER BY m.date DESC LIMIT ?",
            (team, team, before_date, limit * 2)
        ).fetchall()
        conn.close()
        results = []
        for r in rows:
            data = json.loads(r["data_json"])
            hs, aws = data.get("home_score"), data.get("away_score")
            if hs is None or aws is None:
                continue
            try:
                hs, aws = int(hs), int(aws)
            except (ValueError, TypeError):
                continue
            is_home = normalize_team_name(r["home_team"]) == team
            results.append({
                "date": r["date"], "home": r["home_team"], "away": r["away_team"],
                "home_score": hs, "away_score": aws, "is_home": is_home,
            })
        return results[:limit]