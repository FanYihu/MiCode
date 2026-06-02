# Day 13：Action Parser

## 今日目标

把“模型输出的文本”转换成 `AgentAction`。

前面几章里，action 是我们直接在 Python 里创建的：

```python
AgentAction(tool="read_file", args={"path": "README.md"})
```

但真实 LLM 通常会返回文本。为了让 Agent 能执行它的决定，我们需要一层解析器：

```text
JSON 字符串 -> Python dict -> AgentAction -> validate_action()
```

## 为什么需要 Parser

Agent Loop 只应该执行结构化 action，不应该直接执行模型文本。

比如模型返回：

```json
{"tool": "read_file", "args": {"path": "README.md"}, "final": false}
```

MiniCode 要做的是：

1. 用 `json.loads()` 把字符串变成 dict。
2. 从 dict 里取出 `tool / args / final`。
3. 创建 `AgentAction`。
4. 调用 `validate_action()`。

解析失败或校验失败时，不执行工具。

## 建议新增函数

先放在 `agent.py`：

```python
def parse_action(text: str) -> AgentAction:
    ...
```

后面如果 `agent.py` 变大，再拆到 `actions.py`。

## 输入格式约定

模型必须返回一个 JSON 对象：

```json
{
  "tool": "read_file",
  "args": {
    "path": "README.md"
  },
  "final": false
}
```

最终回答：

```json
{
  "tool": "",
  "args": {
    "answer": "任务完成"
  },
  "final": true
}
```

## 建议异常

新增：

```python
class InvalidActionText(ValueError):
    pass
```

它表示“文本连 action 都解析不出来”。

和 Day 12 的异常区分一下：

```text
InvalidActionText：文本格式错了，例如不是 JSON
InvalidAgentAction：解析出来了，但 action 内容不合法
```

## 建议伪代码

```python
import json


class InvalidActionText(ValueError):
    pass


def parse_action(text: str) -> AgentAction:
    try:
        data = json.loads(text)
    except json.JSONDecodeError as error:
        raise InvalidActionText("action text must be valid json") from error

    if not isinstance(data, dict):
        raise InvalidActionText("action json must be an object")

    action = AgentAction(
        tool=data.get("tool", ""),
        args=data.get("args", {}),
        final=data.get("final", False),
    )

    validate_action(action)
    return action
```

## 本章重点

这里有一个很重要的设计选择：

`parse_action()` 里要不要调用 `validate_action()`？

建议第一版调用。

原因是：外部拿到 `parse_action()` 返回值时，可以相信它已经是合法 action。

也就是：

```text
parse_action() 返回成功 = 可以交给 Agent Loop 执行
```

## 你要手写的内容

建议改一个文件：

```text
minicode/src/minicode/agent.py
```

新增：

1. `import json`
2. `InvalidActionText`
3. `parse_action(text)`

## 建议测试

新增测试文件：

```text
minicode/tests/test_action_parser.py
```

建议测试：

```text
1. 合法 read_file JSON 能解析成 AgentAction
2. 合法 final JSON 能解析成 final action
3. 非 JSON 文本会抛 InvalidActionText
4. JSON 数组会抛 InvalidActionText
5. 缺少 path 的 read_file 会抛 InvalidAgentAction
```

## 验收标准

1. `parse_action()` 能把 JSON 字符串转成 `AgentAction`。
2. 非法 JSON 不会进入 Agent Loop。
3. 内容不合法的 action 会复用 `validate_action()` 拦截。
4. 全量测试通过。

## 完成后运行

```bash
cd /Users/fanyihu/Desktop/技能学习/minicode
PYTHONPATH=src python3 -m pytest
```

## 思考题

为什么不建议让 LLM 直接输出“请帮我读取 README.md”这种自然语言，再由 Agent 猜要调用哪个工具？

提示：Agent 执行工具需要稳定、可测试、可校验的结构化输入。
