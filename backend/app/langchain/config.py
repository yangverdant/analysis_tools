"""
LLM Configuration
支持 OpenAI, Claude, Ollama 等多种模型
"""

import os
from typing import Optional, Literal
from pydantic import BaseModel
from langchain_openai import ChatOpenAI
from langchain_anthropic import ChatAnthropic
from langchain_community.llms import Ollama

# 加载API配置
import json
CONFIG_PATH = os.path.join(os.path.dirname(__file__), '..', '..', '..', 'api_config.json')

def load_api_config():
    """加载API配置"""
    try:
        with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
            return json.load(f)
    except:
        return {}

API_CONFIG = load_api_config()


class LLMConfig(BaseModel):
    """LLM配置"""
    provider: Literal['openai', 'anthropic', 'ollama'] = 'openai'
    model_name: str = 'gpt-4o-mini'
    temperature: float = 0.7
    max_tokens: int = 2048
    api_key: Optional[str] = None
    base_url: Optional[str] = None

    def __post_init__(self):
        # 从配置文件加载API Key
        if not self.api_key:
            if self.provider == 'openai':
                self.api_key = API_CONFIG.get('openai', {}).get('api_key') or os.getenv('OPENAI_API_KEY')
            elif self.provider == 'anthropic':
                self.api_key = API_CONFIG.get('anthropic', {}).get('api_key') or os.getenv('ANTHROPIC_API_KEY')


def get_llm(config: Optional[LLMConfig] = None) -> any:
    """
    获取LLM实例

    Args:
        config: LLM配置，默认使用OpenAI GPT-4o-mini

    Returns:
        LangChain LLM实例
    """
    if config is None:
        config = LLMConfig()

    if config.provider == 'openai':
        return ChatOpenAI(
            model=config.model_name,
            temperature=config.temperature,
            max_tokens=config.max_tokens,
            api_key=config.api_key,
            base_url=config.base_url
        )

    elif config.provider == 'anthropic':
        return ChatAnthropic(
            model=config.model_name or 'claude-3-5-sonnet-20241022',
            temperature=config.temperature,
            max_tokens=config.max_tokens,
            api_key=config.api_key
        )

    elif config.provider == 'ollama':
        return Ollama(
            model=config.model_name or 'llama3',
            temperature=config.temperature,
            base_url=config.base_url or 'http://localhost:11434'
        )

    else:
        raise ValueError(f"Unsupported LLM provider: {config.provider}")


# 预定义的模型配置
MODEL_CONFIGS = {
    'gpt-4o': LLMConfig(provider='openai', model_name='gpt-4o'),
    'gpt-4o-mini': LLMConfig(provider='openai', model_name='gpt-4o-mini'),
    'gpt-3.5-turbo': LLMConfig(provider='openai', model_name='gpt-3.5-turbo'),
    'claude-3-opus': LLMConfig(provider='anthropic', model_name='claude-3-opus-20240229'),
    'claude-3-sonnet': LLMConfig(provider='anthropic', model_name='claude-3-5-sonnet-20241022'),
    'claude-3-haiku': LLMConfig(provider='anthropic', model_name='claude-3-haiku-20240307'),
    'llama3': LLMConfig(provider='ollama', model_name='llama3'),
    'qwen2': LLMConfig(provider='ollama', model_name='qwen2'),
}


def get_model(model_name: str) -> any:
    """
    根据模型名称获取预配置的LLM

    Args:
        model_name: 模型名称，如 'gpt-4o', 'claude-3-sonnet', 'llama3'

    Returns:
        LangChain LLM实例
    """
    if model_name in MODEL_CONFIGS:
        return get_llm(MODEL_CONFIGS[model_name])

    # 尝试自动识别
    if 'gpt' in model_name.lower():
        return get_llm(LLMConfig(provider='openai', model_name=model_name))
    elif 'claude' in model_name.lower():
        return get_llm(LLMConfig(provider='anthropic', model_name=model_name))
    else:
        return get_llm(LLMConfig(provider='ollama', model_name=model_name))