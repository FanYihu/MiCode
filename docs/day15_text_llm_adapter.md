# Day 15：Text LLM Adapter

## 今日目标

把“返回文本的模型”接进 MiniCode 的 action 流程。

前面已经有三块：

```text
build_action_prompt(task, observations) -> prompt
parse_action(text) -> AgentAction
validate_action(action) -> 确认 action 合法
```

Day 15 要把它们串起来：

```text
task + observations
  -> build_action_prompt()
  -> client.generate(prompt)
  -> parse_action(raw_text)
  -> AgentAction
```

## 为什么先做 Adapter

真实 LLM API 会有很多细节：

- API key
- model 参数
- 网络错误
- 返回对象结构
- token 限制
- 输出格式约束

这些不是 Agent Loop 的核心。

所以我们先定义一个很薄的适配层，让 MiniCode 只依赖一个简单能力：

```python
client.generate(prompt) -> str
```

以后真实 OpenAI client、测试 fake client、本地模型 client，都可以套进来。

## 建议新增类

先放在 `agent.py`：

```python
class TextLLM:
    def __init__(self, client) -> None:
        self.client = client

    def next_action(self, task: str, observations: list[str]) -> AgentAction:
        prompt = build_action_prompt(task, observations)
        text = self.client.generate(prompt)
        return parse_action(text)
```

注意：`TextLLM` 和 `MockLLM` 一样，都提供 `next_action()`。

这意味着 `MiniCodeAgent` 不需要改：

```python
agent = MiniCodeAgent(workspace, TextLLM(client))
```

## 测试用 Fake Client

测试里可以写一个假 client：

```python
class FakeTextClient:
    def __init__(self, responses):
        self.responses = responses
        self.prompts = []
        self.index = 0

    def generate(self, prompt):
        self.prompts.append(prompt)
        response = self.responses[self.index]
        self.index += 1
        return response
```

它的作用：

- 记录收到的 prompt，方便测试 prompt 里有没有任务和观察结果。
- 按顺序返回 JSON 字符串，模拟模型输出。

## 示例

```python
client = FakeTextClient(
    [
        '{"tool":"read_file","args":{"path":"README.md"},"final":false}',
        '{"tool":"","args":{"answer":"读取完成"},"final":true}',
    ]
)

llm = TextLLM(client)
agent = MiniCodeAgent(workspace, llm)
trace = agent.run("读取 README")
```

执行链路：

```text
Agent 调用 TextLLM.next_action()
TextLLM 构造 prompt
FakeTextClient 返回 JSON 文本
TextLLM parse_action()
Agent 执行 AgentAction
```

## 你要手写的内容

建议改：

```text
minicode/src/minicode/agent.py
```

新增：

```python
class TextLLM:
    ...
```

建议新增测试：

```text
minicode/tests/test_text_llm.py
```

## 建议测试

```text
1. TextLLM 能把 client 返回的 JSON 文本转成 AgentAction
2. TextLLM 会把 task 放进 prompt
3. TextLLM 会把 observations 放进 prompt
4. client 返回非法 JSON 时，TextLLM 抛 InvalidActionText
5. MiniCodeAgent 可以使用 TextLLM 完成 read_file -> final
```

## 重要边界

`TextLLM` 只负责三件事：

```text
构造 prompt
调用 client.generate(prompt)
解析 action
```

它不负责：

- 执行工具
- 判断权限
- 记录 trace
- 管理 Run 状态

这些仍然属于 `MiniCodeAgent` 和已有模块。

## 验收标准

1. `TextLLM` 暴露 `next_action(task, observations)`。
2. `MiniCodeAgent` 可以无感使用 `TextLLM`。
3. prompt 会被发送给 client。
4. client 返回的 JSON 会被解析成合法 `AgentAction`。
5. 全量测试通过。

## 完成后运行

```bash
cd /Users/fanyihu/Desktop/技能学习/minicode
PYTHONPATH=src python3 -m pytest
```

## 思考题

为什么 `TextLLM` 不应该直接调用 `FileTools` 或 `ShellTools`？

提示：LLM 层负责“决定下一步”，Agent 层负责“执行下一步”。这两个职责分开，项目才容易测试和替换。
