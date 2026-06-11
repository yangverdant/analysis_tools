"""
LangChain API Routes
提供AI分析相关的API接口
"""

from fastapi import APIRouter, HTTPHeader, Depends
from pydantic import BaseModel
from typing import Optional, List
import os
import json

router = APIRouter(prefix="/api/v1/ai", tags=["AI Analysis"])

# 配置文件路径
CONFIG_PATH = os.path.join(os.path.dirname(__file__), '..', '..', '..', 'api_config.json')


def load_config():
    """加载API配置"""
    try:
        with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
            return json.load(f)
    except:
        return {}


# 请求模型
class ChatRequest(BaseModel):
    message: str
    model: Optional[str] = "gpt-4o-mini"
    reset_memory: Optional[bool] = False


class PreviewRequest(BaseModel):
    home_team: str
    away_team: str
    league: Optional[str] = None
    model: Optional[str] = "gpt-4o-mini"


class AnalysisRequest(BaseModel):
    match_id: Optional[str] = None
    home_team: Optional[str] = None
    away_team: Optional[str] = None
    model: Optional[str] = "gpt-4o-mini"


class ConfigRequest(BaseModel):
    provider: str
    api_key: str
    base_url: Optional[str] = None


# Agent实例缓存
_agents = {}


def get_analyst_agent(model: str = "gpt-4o-mini"):
    """获取分析代理"""
    from ..langchain.agents import FootballAnalystAgent
    from ..langchain.config import LLMConfig

    key = f"analyst_{model}"
    if key not in _agents:
        config = LLMConfig(
            provider='openai' if 'gpt' in model else 'anthropic',
            model_name=model
        )
        _agents[key] = FootballAnalystAgent(config)
    return _agents[key]


def get_preview_agent(model: str = "gpt-4o-mini"):
    """获取前瞻代理"""
    from ..langchain.agents import MatchPreviewAgent
    from ..langchain.config import LLMConfig

    key = f"preview_{model}"
    if key not in _agents:
        config = LLMConfig(
            provider='openai' if 'gpt' in model else 'anthropic',
            model_name=model
        )
        _agents[key] = MatchPreviewAgent(config)
    return _agents[key]


@router.post("/chat")
async def chat(request: ChatRequest):
    """
    与AI助手对话

    可以询问比赛信息、球队状态、预测等问题
    """
    try:
        agent = get_analyst_agent(request.model)

        if request.reset_memory:
            agent.reset_memory()

        response = agent.chat(request.message)
        return {"success": True, "response": response, "model": request.model}

    except Exception as e:
        return {"success": False, "error": str(e)}


@router.post("/preview")
async def generate_preview(request: PreviewRequest):
    """
    生成比赛前瞻报告

    基于历史数据和球队状态，生成详细的比赛分析
    """
    try:
        agent = get_preview_agent(request.model)
        preview = agent.generate_preview(
            home_team=request.home_team,
            away_team=request.away_team,
            league=request.league
        )
        return {
            "success": True,
            "preview": preview,
            "teams": {
                "home": request.home_team,
                "away": request.away_team
            },
            "model": request.model
        }

    except Exception as e:
        return {"success": False, "error": str(e)}


@router.post("/analyze")
async def analyze_match(request: AnalysisRequest):
    """
    深度分析比赛

    提供战术分析、球员状态、关键因素等深度分析
    """
    try:
        from ..langchain.tools import MatchQueryTool, TeamQueryTool, PredictionTool

        results = {}

        # 查询比赛信息
        if request.match_id:
            match_tool = MatchQueryTool()
            # 这里可以扩展更多分析

        # 查询球队信息
        if request.home_team and request.away_team:
            team_tool = TeamQueryTool()
            prediction_tool = PredictionTool()

            results['home_team_info'] = json.loads(
                team_tool._run(request.home_team, 'form')
            )
            results['away_team_info'] = json.loads(
                team_tool._run(request.away_team, 'form')
            )
            results['prediction'] = json.loads(
                prediction_tool._run(request.home_team, request.away_team)
            )

        return {"success": True, "analysis": results, "model": request.model}

    except Exception as e:
        return {"success": False, "error": str(e)}


@router.get("/models")
async def list_models():
    """
    列出可用的AI模型
    """
    return {
        "models": [
            {"id": "gpt-4o", "name": "GPT-4o", "provider": "OpenAI"},
            {"id": "gpt-4o-mini", "name": "GPT-4o Mini", "provider": "OpenAI"},
            {"id": "gpt-3.5-turbo", "name": "GPT-3.5 Turbo", "provider": "OpenAI"},
            {"id": "claude-3-opus", "name": "Claude 3 Opus", "provider": "Anthropic"},
            {"id": "claude-3-sonnet", "name": "Claude 3.5 Sonnet", "provider": "Anthropic"},
            {"id": "claude-3-haiku", "name": "Claude 3 Haiku", "provider": "Anthropic"},
            {"id": "llama3", "name": "Llama 3", "provider": "Ollama (本地)"},
            {"id": "qwen2", "name": "Qwen 2", "provider": "Ollama (本地)"},
        ]
    }


@router.get("/config")
async def get_ai_config():
    """
    获取AI配置状态
    """
    config = load_config()

    return {
        "openai": {
            "configured": bool(config.get('openai', {}).get('api_key')),
            "model": "gpt-4o-mini"
        },
        "anthropic": {
            "configured": bool(config.get('anthropic', {}).get('api_key')),
            "model": "claude-3-5-sonnet-20241022"
        },
        "ollama": {
            "configured": True,
            "base_url": "http://localhost:11434"
        }
    }


@router.post("/config")
async def update_ai_config(request: ConfigRequest):
    """
    更新AI配置

    设置API Key等配置信息
    """
    try:
        config = load_config()

        if request.provider not in config:
            config[request.provider] = {}

        config[request.provider]['api_key'] = request.api_key

        if request.base_url:
            config[request.provider]['base_url'] = request.base_url

        with open(CONFIG_PATH, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=2, ensure_ascii=False)

        # 清除缓存的agents
        _agents.clear()

        return {"success": True, "message": f"{request.provider} 配置已更新"}

    except Exception as e:
        return {"success": False, "error": str(e)}