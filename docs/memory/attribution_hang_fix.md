---
name: attribution_hang_fix
description: "Agent API无timeout导致归因循环挂起, 18条错误0归因. 修复: 30s timeout + 连续3次失败自动skip_agent"
metadata: 
  node_type: memory
  type: project
  originSessionId: 8bfd2936-b7d2-484e-b643-212fd61d5dce
---

# 归因挂起bug修复

## 发现 (2026-07-03)
- 2026-07-02的18条错误预测**0条归因** (前一天100%覆盖)
- daily_cycle的validate API返回200但实际卡住
- 直接调validate(state=None)运行6+分钟仍未完成
- 手动skip_agent=True: 秒级完成, 22/22=100%归因

## 根因
1. **agent/client.py Anthropic客户端无timeout**
   - `anthropic.Anthropic(api_key=..., base_url=...)` 不设timeout
   - 讯飞MaaS中转API(astron-code-latest)频繁503/429
   - 单次调用可能挂几分钟, 无限重试
2. **validate.py _attribute_failures无Agent熔断**
   - Agent失败就debug log继续, 没有累计计数
   - 22条错误 × 每条挂几分钟 = 整个归因循环几小时不结束
   - daily_cycle的automation-tick每个tick只有~11秒, 根本跑不完

## 修复
### 1. agent/client.py
```python
client_kwargs = {"api_key": api_key, "timeout": 30.0}  # 新增timeout
if base_url:
    client_kwargs["base_url"] = base_url
self._anthropic_client = anthropic.Anthropic(**client_kwargs)
```

### 2. validate.py _attribute_failures
```python
consecutive_agent_failures = 0
for failure in failures:
    # ...
    if agent:
        try:
            agent_attr = _agent_attribution(conn, agent, failure, db_path)
            if agent_attr:
                # ... 应用归因
                consecutive_agent_failures = 0  # 成功重置
            else:
                consecutive_agent_failures += 1  # fallback也算失败
        except Exception as e:
            consecutive_agent_failures += 1
            if consecutive_agent_failures >= 3:
                logger.warning('Agent连续%d次失败/超时, 自动切换到skip_agent模式', ...)
                agent = None  # 熔断
```

## How to apply
- Agent API调用必须有timeout, 不能信任中转API的可用性
- 批量循环里的Agent调用要有熔断机制, 不能让单次失败拖垮整个循环
- 归因是daily_cycle的关键环节, 不能因为Agent不稳定就完全跳过
- skip_agent模式(规则引擎only)是可靠的fallback, 100%覆盖
- 见 [[attribution_driven_learning_bridge]] — 归因数据驱动学习的前提是归因必须完成
