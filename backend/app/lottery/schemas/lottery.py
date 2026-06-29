"""
体彩数据模型定义
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from datetime import datetime
from enum import Enum


class PlayType(str, Enum):
    """体彩玩法类型"""
    SPF = "spf"           # 胜平负
    BF = "bf"             # 比分
    BQC = "bqc"           # 半全场
    RQSPF = "rqspf"       # 让球胜平负
    OVER_UNDER = "ou"     # 大小球


class SellStatus(str, Enum):
    """销售状态"""
    SELLING = "selling"      # 销售中
    STOPPED = "stopped"      # 已停售
    CLOSED = "closed"        # 已截止


class ConfidenceLevel(str, Enum):
    """置信度等级"""
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class FeatureCategory(str, Enum):
    """特征类别"""
    MATH = "math"           # 数学特征 (泊松、Elo、xG)
    TACTICS = "tactics"     # 战术特征 (阵型、控球)
    CONTEXT = "context"     # 上下文特征 (动机、疲劳、德比)
    MARKET = "market"       # 市场特征 (赔率变动、冷热)
    LLM = "llm"             # AI分析 (情绪分析)


@dataclass
class LotteryMatch:
    """体彩比赛"""
    lottery_match_id: str                    # 体彩比赛ID
    home_team_cn: str                        # 主队中文名
    away_team_cn: str                        # 客队中文名
    match_date: str                          # 比赛日期
    sell_status: SellStatus = SellStatus.SELLING

    # 可选字段
    match_id: Optional[int] = None           # 关联系统match_id
    home_team_id: Optional[int] = None       # 主队ID
    away_team_id: Optional[int] = None       # 客队ID
    match_num: Optional[str] = None          # 场次号
    league_name_cn: Optional[str] = None     # 联赛中文名
    league_id: Optional[int] = None          # 联赛ID
    match_time: Optional[str] = None         # 比赛时间
    beijing_time: Optional[str] = None       # 北京时间
    sell_end_time: Optional[str] = None      # 截止销售时间
    play_types: List[str] = field(default_factory=list)  # 开售玩法
    handicap_line: float = 0.0               # 让球数

    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    def to_dict(self) -> Dict:
        """转换为字典"""
        return {
            'lottery_match_id': self.lottery_match_id,
            'home_team_cn': self.home_team_cn,
            'away_team_cn': self.away_team_cn,
            'match_date': self.match_date,
            'sell_status': self.sell_status.value,
            'match_id': self.match_id,
            'home_team_id': self.home_team_id,
            'away_team_id': self.away_team_id,
            'match_num': self.match_num,
            'league_name_cn': self.league_name_cn,
            'match_time': self.match_time,
            'beijing_time': self.beijing_time,
            'play_types': self.play_types,
            'handicap_line': self.handicap_line
        }


@dataclass
class LotteryOdds:
    """体彩赔率"""
    lottery_match_id: str
    play_type: PlayType
    odds_data: Dict[str, float]              # 赔率数据

    # 赔率变化追踪
    opening_odds: Optional[Dict] = None
    latest_odds: Optional[Dict] = None
    odds_movement: Optional[List] = None

    updated_at: Optional[datetime] = None

    def get_odds(self, option: str) -> Optional[float]:
        """获取指定选项的赔率"""
        return self.odds_data.get(option)

    def get_implied_prob(self, option: str) -> Optional[float]:
        """获取隐含概率"""
        odds = self.get_odds(option)
        if odds and odds > 0:
            return 1 / odds
        return None

    def to_dict(self) -> Dict:
        return {
            'lottery_match_id': self.lottery_match_id,
            'play_type': self.play_type.value,
            'odds_data': self.odds_data,
            'opening_odds': self.opening_odds,
            'latest_odds': self.latest_odds
        }


@dataclass
class LotteryPrediction:
    """体彩预测"""
    prediction_id: Optional[int]
    lottery_match_id: str
    play_type: PlayType

    # 预测结果
    predictions: Dict[str, float]            # 各选项概率
    recommendation: str                       # 推荐选项
    confidence: float                         # 置信度
    confidence_level: ConfidenceLevel         # 置信度等级

    # 价值投注
    value_bets: List[Dict] = field(default_factory=list)

    # 特征追溯
    features: Dict[str, Any] = field(default_factory=dict)
    weights: Dict[str, float] = field(default_factory=dict)

    # 模型信息
    model_version: str = "1.0"

    created_at: Optional[datetime] = None

    def to_dict(self) -> Dict:
        return {
            'prediction_id': self.prediction_id,
            'lottery_match_id': self.lottery_match_id,
            'play_type': self.play_type.value,
            'predictions': self.predictions,
            'recommendation': self.recommendation,
            'confidence': self.confidence,
            'confidence_level': self.confidence_level.value,
            'value_bets': self.value_bets,
            'model_version': self.model_version
        }


@dataclass
class LotteryResult:
    """体彩开奖结果"""
    result_id: Optional[int]
    lottery_match_id: str

    # 实际比分
    home_goals_ft: Optional[int] = None      # 全场主队进球
    away_goals_ft: Optional[int] = None      # 全场客队进球
    home_goals_ht: Optional[int] = None      # 半场主队进球
    away_goals_ht: Optional[int] = None      # 半场客队进球

    # 各玩法开奖结果
    spf_result: Optional[str] = None         # 胜平负结果 3/1/0
    bf_result: Optional[str] = None          # 比分结果
    bqc_result: Optional[str] = None         # 半全场结果
    rqspf_result: Optional[str] = None       # 让球胜平负结果
    ou_result: Optional[str] = None          # 大小球结果

    draw_time: Optional[datetime] = None
    created_at: Optional[datetime] = None

    def get_actual_result(self, play_type: PlayType) -> Optional[str]:
        """获取指定玩法的开奖结果"""
        result_map = {
            PlayType.SPF: self.spf_result,
            PlayType.BF: self.bf_result,
            PlayType.BQC: self.bqc_result,
            PlayType.RQSPF: self.rqspf_result,
            PlayType.OVER_UNDER: self.ou_result
        }
        return result_map.get(play_type)

    def to_dict(self) -> Dict:
        return {
            'result_id': self.result_id,
            'lottery_match_id': self.lottery_match_id,
            'home_goals_ft': self.home_goals_ft,
            'away_goals_ft': self.away_goals_ft,
            'spf_result': self.spf_result,
            'bf_result': self.bf_result,
            'bqc_result': self.bqc_result,
            'ou_result': self.ou_result
        }


@dataclass
class LotteryValidation:
    """预测验证结果"""
    validation_id: Optional[int]
    prediction_id: int
    lottery_match_id: str
    play_type: PlayType

    predicted_result: str
    actual_result: str

    is_correct: bool                          # 是否正确
    predicted_prob: float                     # 预测概率
    brier_score: float                        # 布莱尔分数

    validated_at: Optional[datetime] = None

    def to_dict(self) -> Dict:
        return {
            'validation_id': self.validation_id,
            'prediction_id': self.prediction_id,
            'lottery_match_id': self.lottery_match_id,
            'play_type': self.play_type.value,
            'predicted_result': self.predicted_result,
            'actual_result': self.actual_result,
            'is_correct': self.is_correct,
            'predicted_prob': self.predicted_prob,
            'brier_score': self.brier_score
        }


@dataclass
class TeamMapping:
    """球队名称映射"""
    mapping_id: Optional[int]
    lottery_name: str                         # 体彩名称
    team_id: Optional[int]                    # 系统team_id

    aliases: List[str] = field(default_factory=list)  # 别名
    match_confidence: float = 1.0             # 匹配置信度
    match_method: str = "exact"               # exact/fuzzy/manual

    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    def to_dict(self) -> Dict:
        return {
            'mapping_id': self.mapping_id,
            'lottery_name': self.lottery_name,
            'team_id': self.team_id,
            'aliases': self.aliases,
            'match_confidence': self.match_confidence,
            'match_method': self.match_method
        }