# Day 12：AgentAction 校验

## 今日目标

给 `AgentAction` 增加一层校验。

前面 Agent Loop 已经能执行 action：

```text
AgentAction -> 调用工具 -> 记录 trace
```

但真实 LLM 的输出不一定可靠。它可能会给出：

- 不存在的工具名
- 缺少参数
- 参数名写错
- final action 没有 answer
- `args` 不是字典

所以在 Agent 执行工具之前，要先确认 action 是合法的。

## 为什么要校验

Agent 项目里有一个很重要的边界：

```text
模型输出是不可信输入
```

就算模型是你自己调用的，也不能默认它一定按格式返回。

`PermissionReviewer` 负责判断“操作是否危险”，而 `AgentAction` 校验负责判断“动作格式是否正确”。

两者不是一回事：

```text
Action Validation：这个动作能不能被 MiniCode 理解
Permission Review：这个动作理解后能不能执行
```

## 本章建议设计

新增一个校验函数：

```python
def validate_action(action: AgentAction) -> None:
    ...
```

如果 action 合法，什么都不返回。

如果 action 不合法，抛出异常：

```python
class InvalidAgentAction(ValueError):
    pass
```

## 合法规则

### final action

当 `action.final is True`：

- `tool` 可以是空字符串
- `args` 必须是 dict
- `args` 里最好有 `answer`

示例：

```python
AgentAction(tool="", args={"answer": "任务完成"}, final=True)
```

### list_files

不需要参数：

```python
AgentAction(tool="list_files", args={})
```

### read_file

必须有 `path`：

```python
AgentAction(tool="read_file", args={"path": "README.md"})
```

### run_shell

必须有 `command`：

```python
AgentAction(tool="run_shell", args={"command": "python3 -m pytest"})
```

### 未知工具

不允许：

```python
AgentAction(tool="delete_everything", args={})
```

## 建议实现位置

第一版可以先放在：

```text
minicode/src/minicode/agent.py
```

因为 `AgentAction` 现在也在这个文件里。

后面如果文件变大，再拆到 `actions.py`。

## 建议伪代码

```python
class InvalidAgentAction(ValueError):
    pass


def validate_action(action: AgentAction) -> None:
    if not isinstance(action.args, dict):
        raise InvalidAgentAction("action args must be a dict")

    if action.final:
        return

    if action.tool == "list_files":
        return

    if action.tool == "read_file":
        if "path" not in action.args:
            raise InvalidAgentAction("read_file requires path")
        return

    if action.tool == "run_shell":
        if "command" not in action.args:
            raise InvalidAgentAction("run_shell requires command")
        return

    raise InvalidAgentAction(f"unknown tool: {action.tool}")
```

## 接入 Agent Loop

在拿到 action 后，执行工具前调用：

```python
action = self.llm.next_action(task, observations)

try:
    validate_action(action)
except InvalidAgentAction as error:
    step = trace.add_step(StepType.TOOL, metadata={"tool": action.tool})
    trace.add_event(step, EventType.ERROR, content=str(error))
    run.fail()
    return trace.to_dict()
```

这样非法 action 不会继续往下执行。

## 你要手写的内容

建议分三步：

1. 在 `agent.py` 新增 `InvalidAgentAction`。
2. 在 `agent.py` 新增 `validate_action()`。
3. 在 `MiniCodeAgent.run()` 里调用校验函数。

## 建议测试

新增测试文件：

```text
minicode/tests/test_action_validation.py
```

建议测试：

```text
1. list_files action 合法
2. read_file 缺少 path 会报错
3. run_shell 缺少 command 会报错
4. 未知工具会报错
5. Agent 收到非法 action 后 run failed，并记录 error event
```

## 验收标准

1. 非法 action 不会被执行。
2. 非法原因会记录到 trace event。
3. 原本合法的 Agent 流程继续通过。
4. 全量测试通过。

## 完成后运行

```bash
cd /Users/fanyihu/Desktop/技能学习/minicode
PYTHONPATH=src python3 -m pytest
```

## 思考题

为什么“未知工具”不能只依赖原来的 `else` 分支处理？

提示：校验层的目标是让错误更早、更统一地出现；工具执行层的目标是执行已经被确认过的动作。
