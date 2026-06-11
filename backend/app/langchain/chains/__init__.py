"""
LangChain Chains for Football Analysis
提供预定义的分析链
"""

from langchain.chains import LLMChain
from langchain.prompts import PromptTemplate

from ..config import get_llm, LLMConfig


# 预定义的Prompt模板
MATCH_SUMMARY_TEMPLATE = """请根据以下比赛数据，生成一份简明的比赛总结：

比赛：{home_team} vs {away_team}
联赛：{league}
日期：{match_date}
比分：{home_goals} - {away_goals}
半场比分：{home_goals_ht} - {away_goals_ht}

请用中文回答，包括：
1. 比赛概述
2. 关键时刻
3. 球队表现评价
"""

TEAM_ANALYSIS_TEMPLATE = """请分析以下球队的近期表现：

球队：{team_name}
最近10场战绩：{recent_form}
进球数：{goals_scored}
失球数：{goals_conceded}

请用中文回答，包括：
1. 状态评估
2. 攻防分析
3. 改进建议
"""

PREDICTION_TEMPLATE = """基于以下数据，预测比赛结果：

主队：{home_team}
客队：{away_team}
联赛：{league}

主队近期状态：{home_form}
客队近期状态：{away_form}

历史交锋（最近5场）：
{h2h_record}

请预测：
1. 比赛结果（主胜/平局/客胜）及概率
2. 预测比分
3. 关键因素分析
"""


class MatchSummaryChain:
    """比赛总结链"""

    def __init__(self, llm_config: LLMConfig = None):
        self.llm = get_llm(llm_config)
        self.prompt = PromptTemplate(
            template=MATCH_SUMMARY_TEMPLATE,
            input_variables=[
                "home_team", "away_team", "league",
                "match_date", "home_goals", "away_goals",
                "home_goals_ht", "away_goals_ht"
            ]
        )
        self.chain = LLMChain(llm=self.llm, prompt=self.prompt)

    def run(self, **kwargs) -> str:
        return self.chain.run(**kwargs)


class TeamAnalysisChain:
    """球队分析链"""

    def __init__(self, llm_config: LLMConfig = None):
        self.llm = get_llm(llm_config)
        self.prompt = PromptTemplate(
            template=TEAM_ANALYSIS_TEMPLATE,
            input_variables=["team_name", "recent_form", "goals_scored", "goals_conceded"]
        )
        self.chain = LLMChain(llm=self.llm, prompt=self.prompt)

    def run(self, **kwargs) -> str:
        return self.chain.run(**kwargs)


class PredictionChain:
    """预测链"""

    def __init__(self, llm_config: LLMConfig = None):
        self.llm = get_llm(llm_config)
        self.prompt = PromptTemplate(
            template=PREDICTION_TEMPLATE,
            input_variables=[
                "home_team", "away_team", "league",
                "home_form", "away_form", "h2h_record"
            ]
        )
        self.chain = LLMChain(llm=self.llm, prompt=self.prompt)

    def run(self, **kwargs) -> str:
        return self.chain.run(**kwargs)


__all__ = ['MatchSummaryChain', 'TeamAnalysisChain', 'PredictionChain']