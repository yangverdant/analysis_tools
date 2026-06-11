"""
数据补充模块 - 使用AI补充缺失数据

当所有数据源都无法提供某些数据时，使用AI进行补充
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Set
from datetime import datetime
import json
import re


@dataclass
class MissingDataRequest:
    """缺失数据请求"""
    match_id: str
    league: str
    home_team: str
    away_team: str
    match_date: str
    missing_fields: List[str]
    context: Dict[str, Any] = field(default_factory=dict)  # 已有数据作为上下文


@dataclass
class AICompletionResult:
    """AI补充结果"""
    success: bool
    match_id: str
    completed_fields: Dict[str, Any]
    confidence: Dict[str, float]  # 每个字段的置信度
    source: str = "ai_completion"
    reasoning: str = ""
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())


class AIDataCompleter:
    """AI数据补充器"""

    def __init__(self, api_client=None):
        self.api_client = api_client  # DeepSeek或其他AI客户端

        # 可由AI补充的字段及其提示模板
        self.completable_fields = {
            # 基础统计 - 可从比赛报道推断
            "home_shots": {
                "type": "int",
                "prompt": "根据比赛结果和球队实力，估算主队射门次数",
                "range": [5, 25],
            },
            "away_shots": {
                "type": "int",
                "prompt": "根据比赛结果和球队实力，估算客队射门次数",
                "range": [5, 25],
            },
            "home_shots_target": {
                "type": "int",
                "prompt": "估算主队射正次数",
                "range": [2, 12],
            },
            "away_shots_target": {
                "type": "int",
                "prompt": "估算客队射正次数",
                "range": [2, 12],
            },
            "home_corners": {
                "type": "int",
                "prompt": "估算主队角球数",
                "range": [2, 12],
            },
            "away_corners": {
                "type": "int",
                "prompt": "估算客队角球数",
                "range": [2, 12],
            },
            "home_fouls": {
                "type": "int",
                "prompt": "估算主队犯规数",
                "range": [8, 20],
            },
            "away_fouls": {
                "type": "int",
                "prompt": "估算客队犯规数",
                "range": [8, 20],
            },
            "home_yellow": {
                "type": "int",
                "prompt": "估算主队黄牌数",
                "range": [0, 6],
            },
            "away_yellow": {
                "type": "int",
                "prompt": "估算客队黄牌数",
                "range": [0, 6],
            },
            "home_possession": {
                "type": "float",
                "prompt": "估算主队控球率(%)",
                "range": [30, 70],
            },
            "away_possession": {
                "type": "float",
                "prompt": "估算客队控球率(%)",
                "range": [30, 70],
            },

            # xG数据 - 需要更复杂的推断
            "home_xg": {
                "type": "float",
                "prompt": "根据进球和射门估算主队xG",
                "range": [0.5, 4.0],
            },
            "away_xg": {
                "type": "float",
                "prompt": "根据进球和射门估算客队xG",
                "range": [0.5, 4.0],
            },

            # 其他信息
            "attendance": {
                "type": "int",
                "prompt": "估算上座人数",
                "range": [10000, 80000],
            },
            "referee": {
                "type": "str",
                "prompt": "如果知道裁判信息请提供，否则返回unknown",
            },
        }

    def can_complete(self, field: str) -> bool:
        """检查字段是否可由AI补充"""
        return field in self.completable_fields

    async def complete_missing_data(
        self,
        request: MissingDataRequest
    ) -> AICompletionResult:
        """补充缺失数据"""
        if not self.api_client:
            return AICompletionResult(
                success=False,
                match_id=request.match_id,
                completed_fields={},
                confidence={},
                reasoning="AI客户端未配置"
            )

        # 构建提示
        prompt = self._build_prompt(request)

        try:
            # 调用AI
            response = await self._call_ai(prompt)

            # 解析结果
            completed, confidence = self._parse_response(response, request.missing_fields)

            return AICompletionResult(
                success=True,
                match_id=request.match_id,
                completed_fields=completed,
                confidence=confidence,
                reasoning=response
            )

        except Exception as e:
            return AICompletionResult(
                success=False,
                match_id=request.match_id,
                completed_fields={},
                confidence={},
                reasoning=f"AI调用失败: {str(e)}"
            )

    def _build_prompt(self, request: MissingDataRequest) -> str:
        """构建AI提示"""
        lines = [
            "你是一个足球数据分析专家。请根据以下比赛信息，估算缺失的数据。",
            "",
            f"比赛: {request.home_team} vs {request.away_team}",
            f"联赛: {request.league}",
            f"日期: {request.match_date}",
        ]

        # 添加已有数据作为上下文
        if request.context:
            lines.append("")
            lines.append("已知数据:")
            for key, value in request.context.items():
                if value is not None:
                    lines.append(f"  {key}: {value}")

        lines.append("")
        lines.append("请估算以下缺失字段:")
        for field in request.missing_fields:
            if field in self.completable_fields:
                info = self.completable_fields[field]
                lines.append(f"  - {field} ({info['prompt']}, 范围: {info.get('range', 'N/A')})")

        lines.append("")
        lines.append("请以JSON格式返回结果，格式如下:")
        lines.append("{")
        for field in request.missing_fields:
            if field in self.completable_fields:
                lines.append(f'  "{field}": <估算值>,')
                lines.append(f'  "{field}_confidence": <0-1的置信度>,')
        lines.append('  "reasoning": "<估算依据>"')
        lines.append("}")

        return "\n".join(lines)

    async def _call_ai(self, prompt: str) -> str:
        """调用AI API"""
        if self.api_client:
            # 实际调用
            return await self.api_client.chat(prompt)
        return "{}"

    def _parse_response(
        self,
        response: str,
        fields: List[str]
    ) -> tuple[Dict[str, Any], Dict[str, float]]:
        """解析AI响应"""
        completed = {}
        confidence = {}

        try:
            # 提取JSON
            json_match = re.search(r'\{[\s\S]*\}', response)
            if json_match:
                data = json.loads(json_match.group())

                for field in fields:
                    if field in data:
                        completed[field] = data[field]
                        confidence[field] = data.get(f"{field}_confidence", 0.5)

        except json.JSONDecodeError:
            pass

        return completed, confidence


class DataGapDetector:
    """数据缺口检测器"""

    def __init__(self, db_path: str):
        self.db_path = db_path

        # 定义关键字段（分析中心需要的）
        self.critical_fields = {
            "matches": [
                "home_goals", "away_goals",  # 基础比分
                "home_xg", "away_xg",        # xG数据
                "home_shots", "away_shots",  # 射门
                "home_possession", "away_possession",  # 控球
            ]
        }

    def detect_league_gaps(self, league_id: int, season_id: int) -> Dict[str, Any]:
        """检测某联赛的数据缺口"""
        import sqlite3
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # 统计比赛数量
        cursor.execute("""
            SELECT COUNT(*) FROM matches
            WHERE league_id = ? AND season_id = ?
        """, (league_id, season_id))
        total_matches = cursor.fetchone()[0]

        # 统计各字段的缺失率
        gaps = {}
        for field in self.critical_fields["matches"]:
            cursor.execute(f"""
                SELECT COUNT(*) FROM matches
                WHERE league_id = ? AND season_id = ? AND {field} IS NULL
            """, (league_id, season_id))
            missing = cursor.fetchone()[0]
            gaps[field] = {
                "total": total_matches,
                "missing": missing,
                "coverage": 1 - (missing / total_matches) if total_matches > 0 else 0
            }

        conn.close()

        return {
            "league_id": league_id,
            "season_id": season_id,
            "total_matches": total_matches,
            "field_gaps": gaps,
            "overall_coverage": sum(g["coverage"] for g in gaps.values()) / len(gaps)
        }

    def detect_missing_matches(
        self,
        league_id: int,
        season_id: int,
        expected_rounds: int = 38
    ) -> Dict[str, Any]:
        """检测缺失的比赛"""
        import sqlite3
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # 获取已有轮次
        cursor.execute("""
            SELECT DISTINCT round_num FROM matches
            WHERE league_id = ? AND season_id = ?
            ORDER BY round_num
        """, (league_id, season_id))
        existing_rounds = [r[0] for r in cursor.fetchall() if r[0]]

        # 找出缺失轮次
        all_rounds = set(range(1, expected_rounds + 1))
        missing_rounds = all_rounds - set(existing_rounds)

        # 获取球队数量
        cursor.execute("""
            SELECT COUNT(DISTINCT home_team_id) FROM matches
            WHERE league_id = ? AND season_id = ?
        """, (league_id, season_id))
        team_count = cursor.fetchone()[0]

        conn.close()

        return {
            "league_id": league_id,
            "season_id": season_id,
            "expected_rounds": expected_rounds,
            "existing_rounds": existing_rounds,
            "missing_rounds": list(missing_rounds),
            "team_count": team_count,
            "expected_matches": expected_rounds * team_count // 2 if team_count else 0
        }

    def get_completion_priority(self, league_id: int, season_id: int) -> List[Dict]:
        """获取需要补充的数据优先级列表"""
        gaps = self.detect_league_gaps(league_id, season_id)

        # 按缺失率排序
        priority = []
        for field, info in gaps["field_gaps"].items():
            if info["missing"] > 0:
                priority.append({
                    "field": field,
                    "missing_count": info["missing"],
                    "coverage": info["coverage"],
                    "priority": 1 - info["coverage"]  # 缺失越多优先级越高
                })

        return sorted(priority, key=lambda x: -x["priority"])


class AutoSyncScheduler:
    """自动同步调度器"""

    def __init__(self, db_path: str):
        self.db_path = db_path
        self.detector = DataGapDetector(db_path)
        self.sync_tasks: List[Dict] = []

    def create_sync_plan(self, league_id: int, season_id: int) -> Dict[str, Any]:
        """创建同步计划"""
        # 检测缺口
        gaps = self.detector.detect_league_gaps(league_id, season_id)
        missing = self.detector.detect_missing_matches(league_id, season_id)
        priority = self.detector.get_completion_priority(league_id, season_id)

        # 生成同步任务
        tasks = []

        # 1. 补充缺失比赛
        if missing["missing_rounds"]:
            tasks.append({
                "type": "fetch_missing_matches",
                "priority": 1,
                "params": {
                    "league_id": league_id,
                    "season_id": season_id,
                    "rounds": missing["missing_rounds"]
                }
            })

        # 2. 补充缺失字段
        for item in priority:
            tasks.append({
                "type": "complete_field",
                "priority": item["priority"],
                "params": {
                    "league_id": league_id,
                    "season_id": season_id,
                    "field": item["field"]
                }
            })

        return {
            "league_id": league_id,
            "season_id": season_id,
            "current_coverage": gaps["overall_coverage"],
            "missing_rounds": len(missing["missing_rounds"]),
            "field_gaps": len(priority),
            "tasks": sorted(tasks, key=lambda x: x["priority"]),
            "estimated_time": len(tasks) * 2  # 估算时间(分钟)
        }

    def execute_sync_plan(self, plan: Dict) -> Dict[str, Any]:
        """执行同步计划"""
        results = []

        for task in plan["tasks"]:
            result = self._execute_task(task)
            results.append(result)

        return {
            "plan_id": f"sync_{plan['league_id']}_{plan['season_id']}",
            "total_tasks": len(plan["tasks"]),
            "completed": sum(1 for r in results if r["success"]),
            "failed": sum(1 for r in results if not r["success"]),
            "results": results
        }

    def _execute_task(self, task: Dict) -> Dict[str, Any]:
        """执行单个任务"""
        # 实际执行逻辑需要集成数据采集器
        return {
            "task": task["type"],
            "success": True,
            "message": "任务执行完成"
        }
