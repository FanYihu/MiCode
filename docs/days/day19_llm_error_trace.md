# Day 19：LLM Error Handling 与 Trace

## 今日目标

让真实模型调用失败时，MiniCode 也能返回 trace。

现在 Agent Loop 里有一个风险点：

```python
action = self.llm.next_action(task, observations)
```

如果这里发生异常，比如：

- API key 没设置
- 网络错误
- 模型返回非 JSON
- 模型返回未知工具
- provider 返回结构不符合预期

程序可能直接崩掉，CLI 就只剩 traceback。

Day 19 要做的是：把 LLM 相关失败记录进 trace，让用户能看到“哪一步失败、为什么失败”。

## 为什么要做

真实模型不像 `MockLLM` 那样稳定。

一个能用于真实场景的 Agent，不应该只在成功时有 trace。

失败时更需要 trace：

```text
Run failed
Step: model
Event: error
Content: action text must be valid json
```

这样你才能复盘问题是 prompt、模型输出、配置，还是工具执行导致的。

## 建议异常分类

目前已经有：

```python
class InvalidActionText(ValueError):
    pass

class InvalidAgentAction(ValueError):
    pass
```

可以新增一个更通用的 LLM 异常：

```python
class LLMError(RuntimeError):
    pass
```

它表示“模型客户端调用失败”。

区别：

```text
LLMError：调用模型失败
InvalidActionText：模型返回文本不是合法 JSON
InvalidAgentAction：JSON 能解析，但 action 内容不合法
```

## TextLLM 是否要捕获异常

第一版建议：

- `TextLLM` 不吞异常
- `MiniCodeAgent.run()` 统一捕获

原因是 Agent 才有 `Run` 和 `TraceRecorder`，只有它能把错误写进 trace。

## Agent Loop 改造点

当前：

```python
action = self.llm.next_action(task, observations)
try:
    validate_action(action)
except InvalidAgentAction as error:
    ...
```

建议改成：

```python
try:
    action = self.llm.next_action(task, observations)
    validate_action(action)
except (LLMError, InvalidActionText, InvalidAgentAction) as error:
    step = trace.add_step(StepType.MODEL)
    trace.add_event(step, EventType.ERROR, content=str(error))
    run.fail()
    return trace.to_dict()
```

注意：这里用 `StepType.MODEL` 更合适，因为错误发生在“模型产出 action”阶段。

## Client 层错误包装

`OpenAICompatibleTextClient.generate()` 可以把底层 SDK 异常包装成 `LLMError`：

```python
def generate(self, prompt: str) -> str:
    try:
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
        )
    except Exception as error:
        raise LLMError(f"llm request failed: {error}") from error

    return response.choices[0].message.content or ""
```

这样 Agent 不需要知道底层是 OpenAI、Mimo，还是其他兼容服务。

## 配置错误也要友好

如果 `config.toml` 里没有 `api_key`，或者 key 是空字符串，建议抛出清楚的 `LLMError`。

示例：

```python
if not config.api_key:
    raise LLMError("missing api key in config.toml")
```

这样 CLI 里看到的是清楚的错误，而不是底层 SDK 的模糊报错。

## 你要手写的内容

建议改：

```text
minicode/src/minicode/agent.py
```

新增：

1. `LLMError`
2. `OpenAICompatibleTextClient` 包装请求错误
3. `MiniCodeAgent.run()` 捕获 `LLMError / InvalidActionText / InvalidAgentAction`
4. 缺少 API key 时抛出清晰的 `LLMError`

建议改：

```text
minicode/tests/test_agent_integration.py
minicode/tests/test_llm_config.py
```

## 建议测试

```text
1. llm.next_action 抛 InvalidActionText 时，run failed
2. llm.next_action 抛 LLMError 时，run failed
3. 错误 event 使用 EventType.ERROR
4. 缺少 API key 时抛 LLMError
5. OpenAICompatibleTextClient.generate 包装底层异常为 LLMError
```

## 验收标准

1. LLM 失败不会让 Agent 直接崩溃。
2. LLM 失败会写入 trace。
3. CLI agent mode 能输出失败 trace JSON。
4. 缺少 API key 时错误信息清楚。
5. 全量测试通过。

## 完成后运行

```bash
cd /Users/fanyihu/Desktop/技能学习/minicode
PYTHONPATH=src python3 -m pytest
```

## 思考题

为什么模型输出解析失败应该记录为 `MODEL` step，而不是 `TOOL` step？

提示：工具还没被执行，错误发生在“模型决定下一步动作”的阶段。
