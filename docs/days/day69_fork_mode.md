# Day 69：Fork Mode

## 为什么做

SubAgent 能写文件后，还需要一种试错模式：先在隔离副本里执行，确认结果可用后再由主 Agent 决定是否采纳。

Day69 增加 Fork Mode，让子 Agent 可以在临时 workspace 中运行，不污染原工作区。

## 做什么

新增 `ForkedSubAgentExecutor`：

- 复制当前 workspace 到临时目录。
- 跳过 `.git`、`.micode`、`.pytest_cache`、`__pycache__`。
- 在 fork workspace 中创建新的默认 SubAgent executor。
- 执行原始 `SubAgentTask`。
- 把 `fork_root`、原始 workspace 和是否保留 fork 写入 metadata。

## 怎么做

```text
SubAgentTask
  -> ForkedSubAgentExecutor
  -> copy workspace to /tmp/micode-subagent-fork-...
  -> create_default_subagent_executor(fork_workspace)
  -> inner_executor.execute(task)
  -> SubAgentResult(metadata.fork_mode)
```

当前默认不自动合并 fork 结果。合并属于更高风险操作，后续应该通过主 Agent 审批和普通文件写工具完成。

## 做了什么

- 新增 `subagents/fork.py`。
- 新增 `ForkedSubAgentExecutor`。
- `subagents/__init__.py` 暴露 fork executor。
- 补充 fork 执行 implementer 时原 workspace 不被修改的测试。

## 学习重点

Fork Mode 解决的是“试错隔离”，不是“自动合并”。

```text
原 workspace：保持干净
fork workspace：允许子 Agent 尝试修改和测试
主 Agent：根据 metadata 决定下一步
```
