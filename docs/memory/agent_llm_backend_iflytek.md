---
name: agent-llm-backend-iflytek
description: "Agent LLM后端配置: 讯飞MaaS Anthropic兼容中转, 替代过期的DeepSeek和占位符Anthropic"
metadata: 
  node_type: memory
  type: project
  originSessionId: 8bfd2936-b7d2-484e-b643-212fd61d5dce
---

云端 Agent LLM 后端已接入讯飞MaaS (Anthropic兼容中转)。

**Why:** DeepSeek key (sk-0Uj6...) 401过期, Anthropic key 是占位符 ANTHROPIC_API_KEY_PLACEHOLDER, 导致Agent一直走规则化fallback, 无法生成真正的LLM自然语言早报和规则确认。

**How to apply:**
- 配置在 `/opt/football_tools/config/api_keys.yaml` 的 `anthropic` 节:
  - `api_key`: `bb496bc08802fb04aa61f583304c5d3a:NmZiYmEwYzQzNTA3YWMxNTE4OTljM2I4`
  - `base_url`: `https://maas-coding-api.cn-huabei-1.xf-yun.com/anthropic`
  - `model`: `astron-code-latest`
- client.py `_get_backend()` 读取 base_url 和 model, 用 anthropic SDK 创建兼容客户端
- `_run_anthropic()` 用 model override 替代 claude-sonnet/haiku
- 测试: `a.run("回复OK")` → `{'raw_response': 'OK'}` ✅
- 实际推送验证: 触发push后push_history id=4 生成340字LLM早报, 内容含推理/归因/动作/建议
- 503/429 间歇错误时会走规则化 fallback, 不阻塞主流程
- 之前的 daily_report 395字是 fallback 生成, 现在LLM可用后能生成真正的自然语言早报

Git: commit 4b8db2d
