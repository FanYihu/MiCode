# Day 11：LLM Action Provider

## 今日目标

把 Agent Loop 里的“下一步动作从哪里来”单独抽出来。

前面 Day 09 里，`MiniCodeAgent` 只关心一件事：

```text
拿到 AgentAction -> 执行工具 -> 记录 observation -> 再拿下一个 AgentAction
```

但它不应该关心这个 `AgentAction` 是谁生成的：

- 可以是测试里的 `SequenceLLM`
- 可以是现在占位的 `MockLLM`
- 也可以是未来真实 LLM

所以 Day 11 的重点不是立刻联网调用大模型，而是先设计一个稳定接口。

## 为什么先做这一层

如果直接把真实 LLM 调用写进 `MiniCodeAgent`，Agent 会变得很难测试。

更好的结构是：

```text
MiniCodeAgent
  -> action_provider.next_action(task, observations)
  -> AgentAction
```

这样以后替换模型时，只改 action provider，不动 Runtime、Trace、Tools、Permission。

## 核心概念

### AgentAction

这是 Agent Loop 真正吃进去的数据结构：

```python
AgentAction(tool="read_file", args={"path": "README.md"})
AgentAction(tool="", args={"answer": "任务完成"}, final=True)
```

它代表“下一步要做什么”。

### Action Provider

Action Provider 是“产生 AgentAction 的对象”。

它只需要提供一个方法：

```python
def next_action(self, task: str, observations: list[str]) -> AgentAction:
    ...
```

只要实现这个方法，就可以被 `MiniCodeAgent` 使用。

## 你要理解的关系

```text
用户任务
  |
  v
MiniCodeAgent.run(task)
  |
  v
ActionProvider.next_action(task, observations)
  |
  v
AgentAction
  |
  v
调用工具 / 最终回答
```

注意：`MiniCodeAgent` 不需要知道 provider 里面是固定列表、规则判断，还是 LLM API。

## 本章建议改造

### 1. 保留原来的 AgentAction

不要换结构，继续使用你现在的版本：

```python
@dataclass
class AgentAction:
    tool: str
    args: Dict[str, str]
    final: bool = False
```

### 2. 让 MockLLM 真正按顺序返回 action

它现在应该像测试里的 `SequenceLLM` 一样：

```python
class MockLLM:
    def __init__(self, actions: list[AgentAction]) -> None:
        self.actions = actions
        self.index = 0

    def next_action(self, task: str, observations: list[str]) -> AgentAction:
        if self.index >= len(self.actions):
            return AgentAction(tool="", args={"answer": "任务完成"}, final=True)

        action = self.actions[self.index]
        self.index += 1
        return action
```

这个版本有两个关键点：

- 有 action 时，按顺序返回。
- action 用完时，自动返回 final，避免 Agent 卡住。

### 3. 暂时不接真实 LLM

真实 LLM 后面要解决三个问题：

- prompt 怎么写
- 模型输出怎么转成 `AgentAction`
- 输出格式错了怎么办

Day 11 先把接口稳定下来，下一章再做 action schema 校验。

## 你要手写的内容

这章建议只改一个文件：

```text
minicode/src/minicode/agent.py
```

改 `MockLLM.next_action()`，让它按顺序返回预设 actions。

## 建议测试

新增或确认这些测试：

```text
1. MockLLM 第一次返回第一个 action
2. MockLLM 第二次返回第二个 action
3. actions 用完后返回 final action
4. MiniCodeAgent 可以直接使用 MockLLM 完成 read_file -> final
```

## 验收标准

1. `MockLLM` 不再返回空 action。
2. `MockLLM` 可以驱动 `MiniCodeAgent` 正常执行。
3. action 用完后，Agent 能自然结束。
4. 不修改 Tools、Trace、Permission 的结构。

## 完成后运行

```bash
cd /Users/fanyihu/Desktop/技能学习/minicode
PYTHONPATH=src python3 -m pytest
```

## 思考题

为什么 `MiniCodeAgent` 不应该直接依赖真实 LLM API？

提示：如果 Agent 只依赖 `next_action()`，测试和真实模型就可以共用同一套执行循环。
