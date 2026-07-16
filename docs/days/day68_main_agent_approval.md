# Day 68：Main Agent Approval

## 为什么做

Implementer SubAgent 已经能写文件，但写入发生在 `run_subagent` 内部。

如果只审普通 `write_file` / `replace_text` 工具，就会漏掉子 Agent 的内部写入。Day68 给主 Agent 增加审批点：在 `run_subagent(role="implementer")` 执行前审查 operations。

## 做什么

新增 `SubAgentApprovalHook`：

- 只处理 `run_subagent`。
- reviewer/tester 不需要写入审批。
- implementer 必须提供可审计 `operations`。
- 每个 operation 的 path 复用 `PermissionReviewer.review_file_write()`。
- 普通文本代码文件允许，敏感文件或需要人工 review 的路径阻断。

## 怎么做

```text
ToolRegistry.call("run_subagent", role="implementer")
  -> BEFORE_TOOL_CALL
  -> PermissionHook
  -> SubAgentApprovalHook
  -> 解析 context.operations
  -> PermissionReviewer.review_file_write(path)
  -> approved: 继续执行 Implementer
  -> blocked: 返回 ToolResult(ok=False)
```

审批结果进入 ToolResult metadata：

```text
metadata.details.subagent_approval
```

## 做了什么

- 新增 `hooks/subagent_approval.py`。
- 默认 Hook Manager 注册 `subagent_approval`。
- `hooks/__init__.py` 暴露 `SubAgentApprovalHook`。
- CLI agent 模式默认注入 `create_default_subagent_executor(workspace)`。
- 补充安全写入允许、敏感写入阻断和默认 Hook 统计测试。

## 学习重点

审批不应该放在 Implementer 自己里面。

```text
Implementer：执行结构化写入
Main Agent Approval：决定这次写入是否允许发生
ToolRegistry + Hook：保证审批发生在副作用之前
```
