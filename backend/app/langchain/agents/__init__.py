"""
LangChain Agents for Football Analysis
提供智能分析代理
"""

from typing import Optional, List
from langchain.agents import AgentExecutor, create_tool_calling_agent
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain.memory import ConversationBufferMemory
from langchain_core.messages import SystemMessage

from ..config import get_llm, LLMConfig
from ..tools import (
    MatchQueryTool,
    TeamQueryTool,
    PredictionTool,
    AnalysisTool,
    StandingsTool
)


# 系统提示词
FOOTBALL_ANALYST_SYSTEM = """你是一个专业的足球数据分析助手。你可以帮助用户：

1. 查询比赛信息（即将开始的比赛、已结束的比赛、某球队的比赛历史）
2. 查询球队信息（基本信息、近期状态、统计数据）
3. 预测比赛结果（基于历史数据、球队状态）
4. 分析比赛（深度分析、战术分析）
5. 查询积分榜

请根据用户的问题，使用合适的工具来获取信息，然后给出专业、准确的回答。

回答时请注意：
- 使用中文回答
- 提供具体的数据支持
- 给出专业的分析和建议
"""

MATCH_PREVIEW_SYSTEM = """你是一个专业的足球比赛前瞻分析师。你的任务是生成详细的比赛前瞻报告。

报告应包括：
1. 比赛基本信息（时间、联赛、球队）
2. 两队近期状态分析
3. 历史交锋记录
4. 关键球员情况
5. 战术分析
6. 预测结论

请使用专业但易懂的语言，提供数据支持的分析。
"""


class FootballAnalystAgent:
    """足球分析智能代理"""

    def __init__(self, llm_config: Optional[LLMConfig] = None):
        self.llm = get_llm(llm_config)
        self.tools = [
            MatchQueryTool(),
            TeamQueryTool(),
            PredictionTool(),
            AnalysisTool(),
            StandingsTool()
        ]
        self.memory = ConversationBufferMemory(
            memory_key="chat_history",
            return_messages=True
        )
        self.agent_executor = self._create_agent()

    def _create_agent(self):
        """创建Agent"""
        prompt = ChatPromptTemplate.from_messages([
            SystemMessage(content=FOOTBALL_ANALYST_SYSTEM),
            MessagesPlaceholder(variable_name="chat_history"),
            ("user", "{input}"),
            MessagesPlaceholder(variable_name="agent_scratchpad"),
        ])

        agent = create_openai_tools_agent(self.llm, self.tools, prompt)
        return AgentExecutor(
            agent=agent,
            tools=self.tools,
            memory=self.memory,
            verbose=True,
            handle_parsing_errors=True
        )

    def chat(self, message: str) -> str:
        """与代理对话"""
        try:
            result = self.agent_executor.invoke({"input": message})
            return result.get("output", "抱歉，我无法处理这个请求。")
        except Exception as e:
            return f"处理请求时出错: {str(e)}"

    def reset_memory(self):
        """重置对话记忆"""
        self.memory.clear()


class MatchPreviewAgent:
    """比赛前瞻生成代理"""

    def __init__(self, llm_config: Optional[LLMConfig] = None):
        self.llm = get_llm(llm_config)
        self.tools = [
            TeamQueryTool(),
            PredictionTool(),
            AnalysisTool()
        ]
        self.agent_executor = self._create_agent()

    def _create_agent(self):
        """创建Agent"""
        prompt = ChatPromptTemplate.from_messages([
            SystemMessage(content=MATCH_PREVIEW_SYSTEM),
            ("user", "{input}"),
            MessagesPlaceholder(variable_name="agent_scratchpad"),
        ])

        agent = create_openai_tools_agent(self.llm, self.tools, prompt)
        return AgentExecutor(
            agent=agent,
            tools=self.tools,
            verbose=True,
            handle_parsing_errors=True
        )

    def generate_preview(self, home_team: str, away_team: str, league: str = None) -> str:
        """生成比赛前瞻"""
        prompt = f"请生成 {home_team} vs {away_team}"
        if league:
            prompt += f" ({league})"
        prompt += " 的比赛前瞻报告。"

        try:
            result = self.agent_executor.invoke({"input": prompt})
            return result.get("output", "无法生成前瞻报告。")
        except Exception as e:
            return f"生成前瞻报告时出错: {str(e)}"


__all__ = ['FootballAnalystAgent', 'MatchPreviewAgent']