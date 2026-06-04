# Day 09：Mock LLM Agent Loop

## 今日目标

实现一个不依赖真实模型的 Agent Loop，让 MiniCode 从固定任务分发升级为“模型决定下一步动作”。

Day 08 的 CLI 是这样：

```text
if task == "list files":
    ...
elif task == "run tests":
    ...
```

Day 09 要变成：

```text
用户任务 -> MockLLM 产生命令 -> Agent 执行动作 -> 记录观察 -> MockLLM 决定下一步 -> 完成
```

## 为什么先用 Mock LLM

真实 LLM 有不确定性、费用、网络、模型输出格式等变量。

Mock LLM 的好处是：

- 行为稳定
- 测试容易
- 先练 Agent Loop 结构
- 后面可以平滑替换成 OpenAI Responses API

## 你要创建的文件

```text
minicode/
  src/
    minicode/
      agent.py
  tests/
    test_agent.py
```

## 建议数据结构

定义一个模型动作。第一版先保持简单：一个 action 要么表示“调用某个工具”，要么表示“最终回答”。

```python
from dataclasses import dataclass
from typing import Dict


@dataclass
class AgentAction:
    # 工具名称，例如 list_files、read_file、run_shell
    tool: str
    # 工具参数，例如 {"path": "README.md"} 或 {"command": "python3 -m pytest"}
    args: Dict[str, str]
    # 是否为最终回答；True 表示 Agent Loop 可以结束
    final: bool = False
```

约定：

- `final=False`：调用 `tool` 指定的工具
- `final=True`：不再调用工具，结束本次 Agent 运行
- 最终回答可以先放在 `args["answer"]` 里

## MockLLM

定义：

```python
class MockLLM:
    def __init__(self, actions: list[AgentAction]) -> None:
        self.actions = actions
        self.index = 0

    def next_action(self, task: str, observations: list[str]) -> AgentAction:
        ...
```

行为：

- 每次返回下一个预设 action
- 如果 action 用完，返回 final action

## MiniCodeAgent

定义：

```python
class MiniCodeAgent:
    def __init__(self, workspace: Workspace, llm: MockLLM) -> None:
        ...

    def run(self, task: str) -> dict:
        ...
```

建议内部创建：

- `Run`
- `TraceRecorder`
- `FileTools`
- `ShellTools`
- `PermissionReviewer`

## Agent Loop 流程

伪代码：

```python
run.start()
observations = []

for _ in range(max_steps):
    action = llm.next_action(task, observations)

    if action.final:
        记录 final step/event
        run.complete()
        return trace.to_dict()

    根据 action.tool 调用工具
    把结果加入 observations
    把工具调用写入 trace

run.fail()
return trace.to_dict()
```

## 第一版支持的工具

先支持三个工具：

- `list_files`
- `read_file`
- `run_shell`

工具输入示例：

```python
AgentAction(tool="read_file", args={"path": "README.md"})
AgentAction(tool="run_shell", args={"command": "python3 -m pytest"})
AgentAction(tool="", args={"answer": "任务完成"}, final=True)
```

## 权限规则

`run_shell` 必须经过 `PermissionReviewer.review_shell_command()`：

- `ALLOW`：执行
- `REVIEW`：先不要做人机交互，记录需要 review，并结束为 failed
- `DENY`：记录拒绝，并结束为 failed

## 测试提示

建议测试：

- `test_agent_can_list_files_then_finish`
- `test_agent_can_read_file_then_finish`
- `test_agent_can_run_shell_then_finish`
- `test_agent_denies_dangerous_shell_command`
- `test_agent_fails_when_max_steps_exceeded`

## 验收标准

1. Agent 能执行 MockLLM 给出的工具动作。
2. 每个工具动作都会产生 Step 和 Event。
3. observations 会保存工具结果，供下一次 `next_action()` 使用。
4. final action 会让 Run 变成 `completed`。
5. 危险 shell 命令不会被执行，Run 变成 `failed`。
6. 超过最大步数会失败，避免无限循环。

## 完成后运行

```bash
cd /Users/fanyihu/Desktop/技能学习/minicode
PYTHONPATH=src python3 -m pytest
```

## 思考题

Day 09 的 Agent Loop 和 Day 08 的 CLI 分支最大的区别是什么？

提示：Day 08 是程序员写死流程；Day 09 是外部决策器不断给出下一步动作。
