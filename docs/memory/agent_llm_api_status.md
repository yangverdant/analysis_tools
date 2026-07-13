---
name: agent-llm-api-status
description: Agent LLM后端: 已接入讯飞MaaS中转(astron-code-latest), DeepSeek过期作废
metadata:
  node_type: memory
  type: project
  originSessionId: 8bfd2936-b7d2-484e-b643-212fd61d5dce
---

Agent Analyst LLM后端状态（2026-07-01 更新）：

**已接入**: 讯飞MaaS Anthropic兼容中转 — 见 [[agent-llm-backend-iflytek]]
- base_url: `https://maas-coding-api.cn-huawei-1.xf-yun.com/anthropic`
- model: `astron-code-latest`
- 测试通过: `a.run("回复OK")` → `{'raw_response': 'OK'}`
- **503频繁**: 2026-07-07实测3次503(Service Unavailable), Agent早报/止损决策都降级到规则化兜底
  Anthropic SDK自动retry 2次(0.5s+1s间隔), 3次失败后fallback
- 止损决策仍依赖LLM成功, 早报已有规则化兜底, 止损也应加兜底(当前只reduce)

**已废弃**:
- `anthropic.api_key`: 曾是 `ANTHROPIC_API_KEY_PLACEHOLDER`, 现已替换为讯飞中转key
- `deepseek.api_key`: `sk-0Uj6...` 401过期, 作废
- DeepSeek通过 `https://spanagent.xyz/v1` 代理已弃用

**Why**: 用户提供了讯飞MaaS的Anthropic兼容中转API, 替代过期的DeepSeek和占位符Anthropic, 让Agent能真正调用LLM生成自然语言内容。

**How to apply**:
- `AnalystAgent._get_backend()` 读取 `anthropic.base_url` 和 `anthropic.model`, 用 anthropic SDK 创建兼容客户端
- `_run_anthropic()` 用 model override (astron-code-latest) 替代 claude-sonnet/haiku
- `_rule_based_daily_report()` 仍作为 fallback (503系统繁忙时降级)
- push.py 即使 `fallback=True` 也使用 `text` 写入 push_history
- 参见 [[system-architecture-final]]
