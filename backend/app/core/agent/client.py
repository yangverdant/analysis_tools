"""Claude Agent SDK封装 — 双后端(Anthropic/DeepSeek) + tool_use

5个决策场景:
1. error_attribution (翻车归因) — 快速模型
2. param_adjustment (参数调整) — 强模型
3. anomaly_diagnosis (异常诊断) — 快速模型
4. strategy_select (策略选择) — 快速模型
5. new_scenario (新场景识别) — 强模型

后端优先级: Anthropic > DeepSeek(OpenAI兼容) > 规则引擎降级
"""
import json
import logging
import os
import sqlite3
from pathlib import Path
from typing import Optional

import anthropic

logger = logging.getLogger(__name__)

PROMPTS_DIR = Path(__file__).parent.parent.parent.parent.parent / "config" / "agent_prompts"
DB_PATH = Path(__file__).parent.parent.parent.parent.parent / "data" / "football_v2.db"


def load_agent_prompt(name: str) -> str:
    prompt_file = PROMPTS_DIR / f"{name}.md"
    if prompt_file.exists():
        return prompt_file.read_text(encoding="utf-8")
    logger.warning(f"Prompt template not found: {prompt_file}")
    return "你是一名专业的足球分析师AI助手。你的输出必须是JSON格式。"


def _read_db(sql: str, db_path: str = None) -> str:
    """执行只读SQL查询，返回JSON结果"""
    db_path = db_path or str(DB_PATH)
    try:
        if not sql.strip().upper().startswith("SELECT"):
            return json.dumps({"error": "Only SELECT queries allowed"})
        conn = sqlite3.connect(db_path, timeout=10)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute(sql)
        rows = [dict(r) for r in cursor.fetchall()]
        conn.close()
        return json.dumps(rows[:50], ensure_ascii=False, default=str)
    except Exception as e:
        return json.dumps({"error": str(e)})


# Agent工具定义
AGENT_TOOLS_ANTHROPIC = [
    {
        "name": "read_db",
        "description": "查询football_v2.db数据库(只读SELECT)。可用表: lottery_validation, lottery_matches, lottery_odds, lottery_results, lottery_analysis_reports, model_weights, model_accuracy, model_params_history, matches, teams, fifa_rankings, standings",
        "input_schema": {
            "type": "object",
            "properties": {
                "sql": {"type": "string", "description": "SQL查询(SELECT only)"}
            },
            "required": ["sql"]
        }
    }
]

AGENT_TOOLS_OPENAI = [
    {
        "type": "function",
        "function": {
            "name": "read_db",
            "description": "查询football_v2.db数据库(只读SELECT)。可用表: lottery_validation, lottery_matches, lottery_odds, lottery_results, lottery_analysis_reports, model_weights, model_accuracy, model_params_history, matches, teams, fifa_rankings, standings",
            "parameters": {
                "type": "object",
                "properties": {
                    "sql": {"type": "string", "description": "SQL查询(SELECT only)"}
                },
                "required": ["sql"]
            }
        }
    }
]


def _load_config():
    """加载配置文件(避免import冲突)"""
    try:
        import yaml
        config_dir = Path(__file__).parent.parent.parent.parent.parent / "config"
        with open(config_dir / "config.yaml", encoding="utf-8") as f:
            cfg = yaml.safe_load(f) or {}
        with open(config_dir / "api_keys.yaml", encoding="utf-8") as f:
            keys = yaml.safe_load(f) or {}
        return cfg, keys
    except Exception:
        return {}, {}


class AnalystAgent:
    """足球分析师Agent — 双后端 + tool_use"""

    def __init__(self, db_path: str = None):
        self.db_path = db_path or str(DB_PATH)
        self._anthropic_client = None
        self._openai_client = None
        self._backend = None  # 'anthropic' or 'openai'

    def _get_backend(self) -> str:
        """检测可用后端: anthropic优先, openai(deepseek)备选"""
        if self._backend:
            return self._backend

        # 尝试Anthropic
        api_key = os.environ.get("ANTHROPIC_API_KEY", "")
        if not api_key or api_key == "ANTHROPIC_API_KEY_PLACEHOLDER":
            try:
                _, keys = _load_config()
                api_key = keys.get("anthropic", {}).get("api_key", "")
            except Exception:
                pass

        if api_key and api_key != "ANTHROPIC_API_KEY_PLACEHOLDER":
            try:
                self._anthropic_client = anthropic.Anthropic(api_key=api_key)
                self._backend = "anthropic"
                logger.info("Agent后端: Anthropic")
                return "anthropic"
            except Exception as e:
                logger.warning(f"Anthropic初始化失败: {e}")

        # 尝试DeepSeek(OpenAI兼容)
        try:
            cfg, keys = _load_config()
            ds_cfg = cfg.get("data_sources", {}).get("deepseek", {})
            ds_key = keys.get("deepseek", {}).get("api_key", "")
            if not ds_key:
                ds_key = os.environ.get("DEEPSEEK_API_KEY", "")
            if ds_key:
                import openai
                base_url = ds_cfg.get("base_url", "https://api.deepseek.com/v1")
                self._openai_client = openai.OpenAI(api_key=ds_key, base_url=base_url)
                self._backend = "openai"
                logger.info("Agent后端: DeepSeek(OpenAI兼容)")
                return "openai"
        except Exception as e:
            logger.warning(f"DeepSeek初始化失败: {e}")

        self._backend = "none"
        logger.warning("Agent: 无可用后端，将降级到规则引擎")
        return "none"

    def run(self, prompt: str, system: str = None,
            model: str = "fast", max_tokens: int = 1024,
            use_tools: bool = True) -> dict:
        """调用Agent，自动选择后端，支持tool_use

        Args:
            model: 'fast' (Haiku/DeepSeek-Chat) 或 'strong' (Sonnet/DeepSeek-Reasoner)
        """
        backend = self._get_backend()

        if backend == "none":
            return {"error": "no_backend", "fallback": True}

        if backend == "anthropic":
            return self._run_anthropic(prompt, system, model, max_tokens, use_tools)
        elif backend == "openai":
            return self._run_openai(prompt, system, model, max_tokens, use_tools)

        return {"error": "unknown_backend"}

    def _run_anthropic(self, prompt: str, system: str, model: str,
                       max_tokens: int, use_tools: bool) -> dict:
        """Anthropic后端调用"""
        model_id = "claude-haiku-4-5-20251001" if model == "fast" else "claude-sonnet-4-6"
        system_text = system or load_agent_prompt("default")
        tools = AGENT_TOOLS_ANTHROPIC if use_tools else None

        try:
            kwargs = {
                "model": model_id,
                "max_tokens": max_tokens,
                "system": system_text,
                "messages": [{"role": "user", "content": prompt}],
            }
            if tools:
                kwargs["tools"] = tools

            response = self._anthropic_client.messages.create(**kwargs)

            # 处理tool_use
            final_text = ""
            messages = [{"role": "user", "content": prompt}]

            while True:
                has_tool_use = False
                for block in response.content:
                    if block.type == "tool_use":
                        has_tool_use = True
                        tool_result = self._execute_tool_anthropic(block)
                        messages.append({"role": "assistant", "content": response.content})
                        messages.append({
                            "role": "user",
                            "content": [{
                                "type": "tool_result",
                                "tool_use_id": block.id,
                                "content": tool_result
                            }]
                        })
                        # 继续对话
                        response = self._anthropic_client.messages.create(
                            model=model_id,
                            max_tokens=max_tokens,
                            system=system_text,
                            tools=tools,
                            messages=messages,
                        )
                    elif block.type == "text":
                        final_text += block.text

                if not has_tool_use:
                    break

            return self._parse_json(final_text)

        except Exception as e:
            logger.error(f"Anthropic call failed: {e}")
            return {"error": str(e), "fallback": True}

    def _run_openai(self, prompt: str, system: str, model: str,
                    max_tokens: int, use_tools: bool) -> dict:
        """OpenAI兼容后端调用(DeepSeek)"""
        model_id = "deepseek-chat" if model == "fast" else "deepseek-reasoner"
        system_text = system or load_agent_prompt("default")
        tools = AGENT_TOOLS_OPENAI if use_tools else None

        try:
            kwargs = {
                "model": model_id,
                "max_tokens": max_tokens,
                "messages": [
                    {"role": "system", "content": system_text},
                    {"role": "user", "content": prompt},
                ],
            }
            if tools:
                kwargs["tools"] = tools

            response = self._openai_client.chat.completions.create(**kwargs)

            # 处理tool_calls
            messages = [
                {"role": "system", "content": system_text},
                {"role": "user", "content": prompt},
            ]

            while True:
                msg = response.choices[0].message
                if not msg.tool_calls:
                    break

                messages.append(msg)
                for tc in msg.tool_calls:
                    if tc.function.name == "read_db":
                        args = json.loads(tc.function.arguments)
                        result = _read_db(args.get("sql", ""), self.db_path)
                        messages.append({
                            "role": "tool",
                            "tool_call_id": tc.id,
                            "content": result,
                        })

                response = self._openai_client.chat.completions.create(
                    model=model_id,
                    max_tokens=max_tokens,
                    tools=tools,
                    messages=messages,
                )

            text = response.choices[0].message.content or ""
            return self._parse_json(text)

        except Exception as e:
            logger.error(f"OpenAI/DeepSeek call failed: {e}")
            return {"error": str(e), "fallback": True}

    def _execute_tool_anthropic(self, block) -> str:
        """执行Anthropic tool_use调用"""
        if block.name == "read_db":
            sql = block.input.get("sql", "")
            return _read_db(sql, self.db_path)
        return json.dumps({"error": f"Unknown tool: {block.name}"})

    def error_attribution(self, prediction: dict, result: dict, features: dict) -> dict:
        """翻车归因 — 快速模型"""
        system = load_agent_prompt("error_attribution")
        prompt = f"""
预测: 主胜{prediction.get('home_win',0):.0%} 平{prediction.get('draw',0):.0%} 客胜{prediction.get('away_win',0):.0%}
推荐: {prediction.get('recommendation','')} (置信度{prediction.get('confidence_level','')})
实际: {result.get('spf_result','')} ({result.get('home_goals_ft','?')}-{result.get('away_goals_ft','?')})
赔率基线推荐: {prediction.get('odds_baseline_rec', 'unknown')}
模型与赔率{'一致' if prediction.get('model_vs_odds', {}).get('agreement') else '不一致'}
赛事类型: {features.get('competition_type', 'unknown')}
5维度修正: {features.get('friendly_adjustment', 'none')}
修正方向: {features.get('correction_direction', 'none')}
赔率基线: {json.dumps(features.get('odds_baseline', {}), ensure_ascii=False)}
模型概率: {json.dumps(features.get('model_probs', {}), ensure_ascii=False)}
"""
        resp = self.run(prompt, system=system, model="fast", use_tools=True)
        if resp.get("fallback"):
            return None  # 降级到规则引擎
        return resp

    def param_adjustment(self, scene_accuracy: dict, current_weights: dict) -> dict:
        """参数调整 — 强模型"""
        system = load_agent_prompt("param_adjustment")
        prompt = f"""
场景准确率(30天):
{json.dumps(scene_accuracy, indent=2, ensure_ascii=False)}

当前权重:
{json.dumps(current_weights, indent=2, ensure_ascii=False)}

请分析哪些场景的权重需要调整，给出方向和理由。
可以用read_db工具查询lottery_validation表验证你的判断。
"""
        resp = self.run(prompt, system=system, model="strong", max_tokens=2048, use_tools=True)
        if resp.get("fallback"):
            return None
        return resp

    def anomaly_diagnosis(self, error_info: dict, source_health: dict) -> dict:
        """异常诊断 — 快速模型"""
        system = load_agent_prompt("anomaly_diagnosis")
        prompt = f"""
异常信息: {json.dumps(error_info, ensure_ascii=False)}
数据源健康: {json.dumps(source_health, ensure_ascii=False)}
请诊断异常原因并给出降级方案。
"""
        resp = self.run(prompt, system=system, model="fast", use_tools=True)
        if resp.get("fallback"):
            return None
        return resp

    def strategy_select(self, today_matches: dict, accuracy: dict) -> dict:
        """策略选择 — 快速模型"""
        system = load_agent_prompt("strategy_select")
        prompt = f"""
今日赛事构成: {json.dumps(today_matches, ensure_ascii=False)}
近期准确率: {json.dumps(accuracy, ensure_ascii=False)}
请推荐今日应该使用哪套权重/策略。
可以用read_db查询model_accuracy表了解各场景历史表现。
"""
        resp = self.run(prompt, system=system, model="fast", use_tools=True)
        if resp.get("fallback"):
            return None
        return resp

    def new_scenario(self, features: dict, similar_historical: list) -> dict:
        """新场景识别 — 强模型"""
        system = load_agent_prompt("new_scenario")
        prompt = f"""
新场景特征: {json.dumps(features, ensure_ascii=False)}
相似历史: {json.dumps(similar_historical[:5], ensure_ascii=False)}
请识别这是什么类型的新场景，应该如何归类。
"""
        resp = self.run(prompt, system=system, model="strong", use_tools=True)
        if resp.get("fallback"):
            return None
        return resp

    @staticmethod
    def _parse_json(text: str) -> dict:
        """从LLM输出中提取JSON"""
        try:
            if "```json" in text:
                text = text.split("```json")[1].split("```")[0]
            elif "```" in text:
                text = text.split("```")[1].split("```")[0]
            return json.loads(text.strip())
        except json.JSONDecodeError:
            return {"raw_response": text}


def create_agent(db_path: str = None) -> Optional[AnalystAgent]:
    """创建Agent实例 — 自动检测后端可用性"""
    agent = AnalystAgent(db_path=db_path)
    backend = agent._get_backend()
    if backend == "none":
        return None
    return agent
