"""
清洗层 (Cleaner Layer)
负责数据清洗、转换、标准化，将 API 字段映射到数据库字段
"""

from typing import Dict, Any, Optional, List, Callable
from dataclasses import dataclass
from datetime import datetime
import re
import json

from .tasks import Task, TaskType
from .collector import CollectResult
from .schema import API_SPORTS_FIELD_MAP, get_table_def


@dataclass
class CleanResult:
    """清洗结果"""
    success: bool
    data: Optional[Any] = None
    error: Optional[str] = None
    cleaned_at: datetime = None
    records_processed: int = 0
    records_cleaned: int = 0
    records_skipped: int = 0

    def __post_init__(self):
        if self.cleaned_at is None:
            self.cleaned_at = datetime.now()


def extract_nested_value(data: Dict, path: str) -> Any:
    """
    从嵌套字典中提取值
    path: "fixture.date[:10]" 或 "teams.home.id"
    """
    try:
        # 处理切片语法
        if '[' in path:
            base_path, slice_part = path.split('[')
            slice_part = slice_part.rstrip(']')

            # 获取基础值
            value = _get_nested_value(data, base_path)

            # 应用切片
            if ':' in slice_part:
                parts = slice_part.split(':')
                start = int(parts[0]) if parts[0] else 0
                end = int(parts[1]) if parts[1] else None
                return value[start:end] if value else None
            else:
                idx = int(slice_part)
                return value[idx] if value else None
        else:
            return _get_nested_value(data, path)
    except (KeyError, IndexError, TypeError):
        return None


def _get_nested_value(data: Dict, path: str) -> Any:
    """获取嵌套字典的值"""
    keys = path.split('.')
    value = data
    for key in keys:
        if isinstance(value, dict):
            value = value.get(key)
        else:
            return None
    return value


class DataCleaner:
    """数据清洗器"""

    def __init__(self):
        self.field_maps = {
            "api_sports": API_SPORTS_FIELD_MAP,
        }

        self.cleaners: Dict[TaskType, Callable] = {
            TaskType.MATCH_COMPLETE: self._clean_match,
            TaskType.MATCH_SCORE: self._clean_match_score,
            TaskType.MATCH_DATE: self._clean_match_date,
            TaskType.TEAM_INFO: self._clean_team,
            TaskType.TEAM_CHINESE_NAME: self._clean_team_chinese_name,
            TaskType.LEAGUE_RULES: self._clean_league_rules,
            TaskType.LEAGUE_INFO: self._clean_league_info,
            TaskType.SYNC_RECENT: self._clean_matches,
            TaskType.SYNC_SCHEDULE: self._clean_matches,
            TaskType.SYNC_STANDINGS: self._clean_standings,
            TaskType.NEWS_SYNC: self._clean_news,
            TaskType.BATCH_IMPORT: self._clean_batch,
        }

    def clean(self, task: Task, collect_result: CollectResult) -> CleanResult:
        """清洗数据"""
        if not collect_result.success:
            return CleanResult(
                success=False,
                error="采集失败，无法清洗"
            )

        cleaner = self.cleaners.get(task.task_type)
        if not cleaner:
            return CleanResult(
                success=False,
                error=f"不支持的任务类型：{task.task_type}"
            )

        try:
            return cleaner(task, collect_result)
        except Exception as e:
            return CleanResult(
                success=False,
                error=str(e)
            )

    def _clean_match(self, task: Task, result: CollectResult) -> CleanResult:
        """
        清洗单场比赛数据
        将 API-Sports 返回的字段映射到数据库字段
        """
        raw_data = result.data
        if not raw_data:
            return CleanResult(success=False, error="无数据")

        if isinstance(raw_data, list) and len(raw_data) > 0:
            match_data = raw_data[0]
        else:
            match_data = raw_data

        # 使用字段映射
        cleaned = self._map_fields(match_data, "matches", result.source_id)

        # 补充额外字段
        cleaned.update({
            "status": cleaned.get("status", "scheduled"),
            "time_type": "beijing" if result.source_id == "dongqiudi_scraper"
                         else "utc" if result.source_id in ("apifootball", "football_data_org", "thesportsdb")
                         else "beijing" if result.source_id == "365scores"
                         else "local",
        })

        return CleanResult(
            success=True,
            data=cleaned,
            records_processed=1,
            records_cleaned=1
        )

    def _map_fields(self, data: Dict, table: str, source: str) -> Dict:
        """
        将 API 字段映射到数据库字段
        这是核心方法，确保前端拿到的字段名和数据库一致
        """
        field_map = self.field_maps.get(source, {}).get(table, {})
        if not field_map:
            return data  # 无映射则直接返回

        mapped = {}
        for api_path, db_field in field_map.items():
            value = extract_nested_value(data, api_path)
            if value is not None:
                # 处理 team_name -> 需要 JOIN teams 表获取 team_id
                if db_field.endswith("_name") and "team" in db_field:
                    # 球队名暂存，后续通过 JOIN 获取 ID
                    mapped[db_field] = value
                else:
                    mapped[db_field] = value

        return mapped

    def _clean_match_score(self, task: Task, result: CollectResult) -> CleanResult:
        """清洗比赛比分"""
        clean_result = self._clean_match(task, result)
        if clean_result.success:
            # 只保留比分相关字段
            data = clean_result.data
            clean_result.data = {
                "match_id": data.get("match_id"),
                "home_goals": data.get("home_goals"),
                "away_goals": data.get("away_goals"),
                "home_goals_ht": data.get("home_goals_ht"),
                "away_goals_ht": data.get("away_goals_ht"),
                "status": data.get("status"),
                "result": data.get("result"),
            }
        return clean_result

    def _clean_match_date(self, task: Task, result: CollectResult) -> CleanResult:
        """清洗比赛日期"""
        clean_result = self._clean_match(task, result)
        if clean_result.success:
            data = clean_result.data
            clean_result.data = {
                "match_id": data.get("match_id"),
                "match_date": data.get("match_date"),
                "match_time": data.get("match_time"),
                "time_type": data.get("time_type"),
            }
        return clean_result

    def _clean_team(self, task: Task, result: CollectResult) -> CleanResult:
        """清洗球队数据"""
        raw_data = result.data
        if not raw_data:
            return CleanResult(success=False, error="无数据")

        if isinstance(raw_data, list) and len(raw_data) > 0:
            team_data = raw_data[0]
        else:
            team_data = raw_data

        # 映射字段
        cleaned = self._map_fields(team_data, "teams", result.source_id)

        # 补充字段
        cleaned.update({
            "name_en": cleaned.get("name_en") or team_data.get("team", {}).get("name"),
            "team_type": "club",
        })

        return CleanResult(
            success=True,
            data=cleaned,
            records_processed=1,
            records_cleaned=1
        )

    def _clean_team_chinese_name(self, task: Task, result: CollectResult) -> CleanResult:
        """清洗球队中文名"""
        raw_data = result.data
        if not raw_data:
            return CleanResult(success=False, error="无数据")

        # 从懂球帝等来源获取中文名
        cleaned = {
            "name_cn": raw_data.get("name_cn"),
            "name_en": raw_data.get("team_name"),
        }

        return CleanResult(
            success=True,
            data=cleaned,
            records_processed=1,
            records_cleaned=1
        )

    def _clean_league_rules(self, task: Task, result: CollectResult) -> CleanResult:
        """清洗联赛规则"""
        raw_data = result.data
        if not raw_data:
            return CleanResult(success=False, error="无数据")

        cleaned = {
            "league_id": raw_data.get("league_id"),
            "season": raw_data.get("season"),
            "teams_count": raw_data.get("teams_count"),
            "points_for_win": 3,
            "champions_league_spots": raw_data.get("champions_league_spots", 0),
            "europa_league_spots": raw_data.get("europa_league_spots", 0),
            "relegation_spots": raw_data.get("relegation_spots", 0),
            "promotion_spots": raw_data.get("promotion_spots", 0),
        }

        return CleanResult(
            success=True,
            data=cleaned,
            records_processed=1,
            records_cleaned=1
        )

    def _clean_league_info(self, task: Task, result: CollectResult) -> CleanResult:
        """清洗联赛信息"""
        raw_data = result.data
        if not raw_data:
            return CleanResult(success=False, error="无数据")

        if isinstance(raw_data, list) and len(raw_data) > 0:
            league_data = raw_data[0]
        else:
            league_data = raw_data

        cleaned = {
            "league_id": league_data.get("league", {}).get("id"),
            "name_en": league_data.get("league", {}).get("name"),
            "country": league_data.get("country", {}).get("name"),
            "competition_type": "league",
            "participant_type": "club",
            "format_type": "round_robin",
        }

        return CleanResult(
            success=True,
            data=cleaned,
            records_processed=1,
            records_cleaned=1
        )

    def _clean_matches(self, task: Task, result: CollectResult) -> CleanResult:
        """清洗多场比赛数据"""
        raw_data = result.data
        if not raw_data or not isinstance(raw_data, list):
            return CleanResult(success=False, error="无数据或数据格式错误")

        cleaned_matches = []
        skipped = 0

        for match in raw_data:
            try:
                cleaned = self._map_fields(match, "matches", result.source_id)
                if cleaned:
                    cleaned_matches.append(cleaned)
                else:
                    skipped += 1
            except Exception:
                skipped += 1

        return CleanResult(
            success=True,
            data=cleaned_matches,
            records_processed=len(raw_data),
            records_cleaned=len(cleaned_matches),
            records_skipped=skipped
        )

    def _clean_standings(self, task: Task, result: CollectResult) -> CleanResult:
        """清洗积分榜数据"""
        raw_data = result.data
        if not raw_data:
            return CleanResult(success=False, error="无数据")

        cleaned_standings = []

        try:
            # API-Sports 返回格式
            if isinstance(raw_data, list) and len(raw_data) > 0:
                standings_data = raw_data[0].get("league", {}).get("standings", [[]])[0]
                for team in standings_data:
                    cleaned = {
                        "position": team.get("rank"),
                        "team_id": team.get("team", {}).get("id"),
                        "team_name": team.get("team", {}).get("name"),  # 需要 JOIN
                        "points": team.get("points"),
                        "played": team.get("games", {}).get("played"),
                        "won": team.get("games", {}).get("won"),
                        "drawn": team.get("games", {}).get("draw"),
                        "lost": team.get("games", {}).get("lose"),
                        "goals_for": team.get("goals", {}).get("for"),
                        "goals_against": team.get("goals", {}).get("against"),
                        "goal_diff": team.get("goalsDiff"),
                        "form": team.get("form"),
                    }
                    cleaned_standings.append(cleaned)
        except (IndexError, KeyError, TypeError) as e:
            return CleanResult(success=False, error=f"数据格式错误：{e}")

        return CleanResult(
            success=True,
            data=cleaned_standings,
            records_processed=len(cleaned_standings),
            records_cleaned=len(cleaned_standings)
        )

    def _clean_news(self, task: Task, result: CollectResult) -> CleanResult:
        """清洗新闻数据"""
        raw_data = result.data
        if not raw_data:
            return CleanResult(success=False, error="无数据")

        cleaned_news = []
        for item in raw_data if isinstance(raw_data, list) else [raw_data]:
            cleaned = {
                "title": item.get("title"),
                "content": item.get("content"),
                "news_type": "general",
                "category": item.get("category", "general"),
                "news_date": datetime.now().strftime("%Y-%m-%d"),
            }
            cleaned_news.append(cleaned)

        return CleanResult(
            success=True,
            data=cleaned_news,
            records_processed=len(cleaned_news),
            records_cleaned=len(cleaned_news)
        )

    def _clean_batch(self, task: Task, result: CollectResult) -> CleanResult:
        """清洗批量数据"""
        raw_data = result.data
        if not raw_data:
            return CleanResult(success=False, error="无数据")

        return CleanResult(
            success=True,
            data=raw_data,
            records_processed=len(raw_data) if isinstance(raw_data, list) else 1,
            records_cleaned=len(raw_data) if isinstance(raw_data, list) else 1
        )

    def validate_data(self, data: Dict[str, Any], required_fields: List[str]) -> tuple:
        """验证数据完整性"""
        missing = []
        for field in required_fields:
            if field not in data or data[field] is None:
                missing.append(field)
        return len(missing) == 0, missing

    def normalize_team_name(self, name: str) -> str:
        """标准化球队名称"""
        if not name:
            return ""
        name = " ".join(name.split())
        return name.strip()

    def normalize_date(self, date_str: str) -> str:
        """标准化日期格式"""
        if not date_str:
            return ""
        formats = ["%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y"]
        for fmt in formats:
            try:
                dt = datetime.strptime(date_str[:10], fmt)
                return dt.strftime("%Y-%m-%d")
            except ValueError:
                continue
        return date_str[:10] if len(date_str) >= 10 else ""
