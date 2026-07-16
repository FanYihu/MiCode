# Day 66：Tester SubAgent

## 为什么做

Reviewer 只能发现风险，不能证明代码真的能跑。

Day66 补 Tester SubAgent，让主 Agent 可以把“运行测试并返回证据”委托出去，同时继续保持权限边界：Tester 只运行测试类命令，不变成任意 shell 执行器。

## 做什么

新增 `TesterSubAgent`：

- 从 `SubAgentTask` 中提取测试命令。
- 没有明确命令时默认运行 `python3 -m pytest tests -q`。
- 只允许 `pytest`、`python -m pytest`、`python3 -m pytest`。
- 拒绝 `;`、`&&`、管道、重定向、命令替换等 shell 拼接。
- 返回测试摘要、exit code、timeout、stdout/stderr 摘要。

同时扩展默认 SubAgent executor：

- 没有 workspace 时只注册 reviewer。
- 有 workspace 时额外注册 tester，因为 tester 需要 `ShellTools(workspace)`。

## 怎么做

完整流转：

```text
Main Agent
  -> AgentAction(tool="run_subagent", role="tester")
  -> ToolRegistry.call(...)
  -> SubAgentPolicy 生成 SubAgentTask
  -> RoleBasedSubAgentExecutor.execute(task)
  -> TesterSubAgent.execute(task)
  -> ShellTools.run(command)
  -> SubAgentResult(status + summary + metadata)
  -> ToolResult
  -> Trace + observations
```

命令来源：

```text
task.metadata["command"]
  -> context 中的 command: ...
  -> 默认 python3 -m pytest tests -q
```

当前 `run_subagent` schema 还没有暴露 `metadata`，所以真实模型调用时主要通过 `context` 传：

```text
command: python3 -m pytest tests/test_subagents.py -q
```

## 做了什么

- 新增 `minicode/subagents/tester.py`。
- 新增 `TesterSubAgent` 和默认测试命令。
- `create_default_subagent_executor(workspace)` 支持注册 tester。
- `minicode/subagents/__init__.py` 暴露 `TesterSubAgent`。
- 补充 tester 成功、失败、危险命令拦截、shell 拼接拦截和 ToolRegistry metadata 测试。

## 学习重点

Tester SubAgent 的核心不是“能跑 shell”，而是“只跑被允许的测试命令”。

```text
run_shell 是底层能力
TesterSubAgent 是受控角色
SubAgentPolicy 决定角色能用什么
Trace 保存测试证据
```
