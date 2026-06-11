"""
DeepSeek AI数据获取

功能:
1. AI比赛分析 (综合数据生成分析文本)
2. 球员中文名批量翻译
3. 联赛/球队中文名翻译
4. 通用聊天补全 (OpenAI兼容)

数据来源: api.deepseek.com (需API Key)

使用示例:
    from fetchers.deepseek.chat import chat_completion, translate_players

    # AI分析
    result = chat_completion("分析曼城vs利物浦的胜率")

    # 球员中文名
    names = translate_players(["Mohamed Salah", "Kevin De Bruyne"])
"""

import os
import json
import logging
from typing import Dict, List, Optional
import requests

from fetchers.deepseek.config import API_KEY, BASE_URL, MODEL, REQUEST_TIMEOUT

os.environ['http_proxy'] = ''
os.environ['https_proxy'] = ''
os.environ['NO_PROXY'] = '*'

logger = logging.getLogger(__name__)

_session = None


def _get_session() -> requests.Session:
    global _session
    if _session is None:
        _session = requests.Session()
        _session.trust_env = False
    return _session


# ==================== 核心接口 ====================

def chat_completion(messages: List[Dict], model: str = None,
                    temperature: float = 0.7, max_tokens: int = 4096,
                    use_direct: bool = False) -> Dict:
    """OpenAI兼容的聊天补全

    Args:
        messages: [{"role": "system/user/assistant", "content": "..."}]
        model: 模型名 (默认deepseek-chat)
        temperature: 温度 (0-2)
        max_tokens: 最大输出token
        use_direct: 是否使用官方endpoint

    Returns:
        {"content", "model", "usage": {"prompt_tokens", "completion_tokens", "total_tokens"}, "source"}
    """
    if not API_KEY:
        print("[错误] DeepSeek API Key未配置")
        return {}

    url = f"{BASE_URL if not use_direct else 'https://api.deepseek.com/v1'}/chat/completions"
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": model or MODEL,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }

    session = _get_session()
    try:
        resp = session.post(url, headers=headers, json=payload,
                            timeout=REQUEST_TIMEOUT, proxies={'http': None, 'https': None})
        if resp.status_code == 200:
            data = resp.json()
            choice = data.get("choices", [{}])[0]
            return {
                'content': choice.get("message", {}).get("content", ""),
                'model': data.get("model", ""),
                'usage': data.get("usage", {}),
                'source': 'deepseek'
            }
        else:
            logger.error(f"DeepSeek API错误 {resp.status_code}: {resp.text[:200]}")
            print(f"[错误] DeepSeek API错误: {resp.status_code}")
    except Exception as e:
        logger.error(f"DeepSeek请求失败: {e}")
        print(f"[错误] DeepSeek请求失败: {str(e)[:60]}")

    return {}


def analyze_match(home_team: str, away_team: str, context: str = "") -> str:
    """AI分析比赛

    Args:
        home_team: 主队名
        away_team: 客队名
        context: 额外上下文 (近况/伤病/赔率等)

    Returns:
        AI生成的分析文本
    """
    system = "你是一位资深足球分析师,请根据提供的数据进行客观专业的分析。"
    user = f"请分析 {home_team} vs {away_team} 的比赛"
    if context:
        user += f"\n\n参考数据:\n{context}"

    result = chat_completion([
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ])
    return result.get('content', '')


def translate_players(player_names: List[str], batch_size: int = 20) -> Dict[str, str]:
    """批量翻译球员名为中文

    Args:
        player_names: 英文球员名列表
        batch_size: 每批处理数量

    Returns:
        {"Mohamed Salah": "萨拉赫", ...}
    """
    translations = {}

    for i in range(0, len(player_names), batch_size):
        batch = player_names[i:i + batch_size]
        names_str = "\n".join(batch)

        result = chat_completion([
            {"role": "system", "content": "你是足球专家,将球员英文名翻译为中文。只输出JSON格式,不要其他内容。"},
            {"role": "user", "content": f"将以下球员名翻译为中文:\n{names_str}\n\n输出格式: {{\"English Name\": \"中文名\"}}"},
        ], temperature=0.1, max_tokens=2048)

        content = result.get('content', '')
        try:
            # 尝试从内容中提取JSON
            start = content.find('{')
            end = content.rfind('}') + 1
            if start >= 0 and end > start:
                parsed = json.loads(content[start:end])
                translations.update(parsed)
        except json.JSONDecodeError:
            pass

        print(f"[deepseek] 翻译球员: {len(translations)}/{len(player_names)}")

    return translations


def translate_leagues(league_names: List[str]) -> Dict[str, str]:
    """批量翻译联赛名为中文

    Returns:
        {"Premier League": "英超", ...}
    """
    names_str = "\n".join(league_names)
    result = chat_completion([
        {"role": "system", "content": "你是足球专家,将联赛英文名翻译为中文常用名。只输出JSON格式。"},
        {"role": "user", "content": f"翻译联赛名:\n{names_str}\n\n输出格式: {{\"English Name\": \"中文常用名\"}}"},
    ], temperature=0.1, max_tokens=1024)

    content = result.get('content', '')
    try:
        start = content.find('{')
        end = content.rfind('}') + 1
        if start >= 0 and end > start:
            return json.loads(content[start:end])
    except:
        pass
    return {}


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("用法:")
        print("  python -m fetchers.deepseek.chat analyze '曼城 vs 利物浦'")
        print("  python -m fetchers.deepseek.chat translate_players 'Salah' 'De Bruyne'")
        sys.exit(0)

    cmd = sys.argv[1]
    if cmd == "analyze":
        teams = " ".join(sys.argv[2:])
        print(analyze_match(*teams.split(" vs ")))
    elif cmd == "translate_players":
        names = sys.argv[2:]
        result = translate_players(names)
        for en, cn in result.items():
            print(f"  {en} -> {cn}")