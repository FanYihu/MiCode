# Day 14：Prompt Builder

## 今日目标

设计一个稳定的 prompt，让未来的 LLM 按 MiniCode 需要的格式输出 JSON action。

前面 Day 13 已经有了这条链路：

```text
JSON 字符串 -> parse_action() -> AgentAction -> validate_action()
```

但 LLM 为什么会输出这种 JSON？

答案是：我们要清楚地告诉它工具有哪些、参数怎么写、只能输出什么格式。

## 为什么需要 Prompt Builder

不要把 prompt 散落在 Agent 代码里。

Prompt 本身也是工程逻辑：

- 它定义模型能看到哪些工具。
- 它定义模型必须输出什么结构。
- 它决定 observation 如何反馈给模型。
- 它影响后续 parser 是否稳定。

所以建议把 prompt 构造单独封装成函数。

## 建议新增函数

先放在 `agent.py`：

```python
def build_action_prompt(task: str, observations: list[str]) -> str:
    ...
```

它负责返回一个完整 prompt 字符串。

## Prompt 应该包含什么

### 1. Agent 角色

告诉模型它不是聊天助手，而是 MiniCode 的 action generator。

```text
You are MiniCode's action generator.
```

### 2. 可用工具

列出当前支持的工具：

```text
Available tools:
- list_files: list workspace files, args={}
- read_file: read a file, args={"path": "..."}
- run_shell: run a shell command, args={"command": "..."}
```

### 3. 输出格式

要求只能输出 JSON，不要解释。

```json
{"tool":"read_file","args":{"path":"README.md"},"final":false}
```

最终回答：

```json
{"tool":"","args":{"answer":"任务完成"},"final":true}
```

### 4. 用户任务

把 `task` 放进去。

### 5. 历史观察

把 `observations` 放进去，模型才能根据上一步工具结果决定下一步。

## 建议伪代码

```python
def build_action_prompt(task: str, observations: list[str]) -> str:
    observation_text = "\n\n".join(observations) if observations else "None"

    return f"""
You are MiniCode's action generator.

Available tools:
- list_files: list workspace files, args={{}}
- read_file: read a file, args={{"path": "..."}}
- run_shell: run a shell command, args={{"command": "..."}}

Return exactly one JSON object.
Do not return markdown.
Do not explain.

Tool action example:
{{"tool":"read_file","args":{{"path":"README.md"}},"final":false}}

Final answer example:
{{"tool":"","args":{{"answer":"任务完成"}},"final":true}}

Task:
{task}

Observations:
{observation_text}
""".strip()
```

注意：f-string 里如果要写 JSON 的 `{}`，需要用双花括号 `{{` 和 `}}` 转义。

## 本章先不接真实模型

Day 14 只做 prompt builder。

不要急着调用 OpenAI API。

原因是我们还缺一层：

```text
TextLLM：调用模型拿到文本 -> parse_action(text)
```

这一层下一章再做。

## 你要手写的内容

建议改一个文件：

```text
minicode/src/minicode/agent.py
```

新增：

1. `import json`
2. `build_action_prompt(task, observations)`
3. `test_action_parser.py` 里补 `parse_action()` 测试
4. `test_prompt_builder.py` 里测试 prompt 包含工具、任务、观察结果、JSON 输出要求

这里把 `import json` 放进本章，是因为你 Day 13 的 `parse_action()` 已经用到了它。

## 建议测试

新增：

```text
minicode/tests/test_prompt_builder.py
```

建议测试：

```text
1. prompt 包含用户任务
2. prompt 包含 list_files/read_file/run_shell
3. prompt 包含已有 observations
4. prompt 明确要求只返回 JSON
```

同时建议补上：

```text
minicode/tests/test_action_parser.py
```

至少覆盖：

```text
1. 合法 read_file JSON
2. 非 JSON 文本
3. read_file 缺少 path
```

## 验收标准

1. `parse_action()` 的测试覆盖到。
2. `build_action_prompt()` 能生成包含工具说明、任务和观察结果的 prompt。
3. prompt 明确要求只输出 JSON。
4. 全量测试通过。

## 完成后运行

```bash
cd /Users/fanyihu/Desktop/技能学习/minicode
PYTHONPATH=src python3 -m pytest
```

## 思考题

为什么 prompt 里要写工具参数格式，而不是只写工具名字？

提示：parser 和 validator 只接受固定结构；prompt 越明确，模型输出越容易被程序处理。
