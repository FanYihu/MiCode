# Day 67：Implementer SubAgent

## 为什么做

Reviewer 能审查，Tester 能验证，但真正的多 Agent 协作还需要一个能执行代码修改的角色。

Day67 补 Implementer SubAgent，但它不能自由发挥：当前没有独立 LLM 子 Agent prompt，所以 Implementer 只执行主 Agent 提供的结构化 operations，保证每次写入都可审计。

## 做什么

新增 `ImplementerSubAgent`：

- 支持 `replace_text`：精确替换文件中的第一处文本。
- 支持 `write_file`：写入或创建文件。
- 从 `task.metadata["operations"]` 或 `context` 中的 JSON 读取操作列表。
- 校验 `task.allowed_tools`，没有授权就拒绝执行。
- 所有文件路径都通过 `Workspace` / `FileTools` 保护。
- 返回 `changed_paths`、operation 列表和 diff 摘要。

operations 示例：

```json
{
  "operations": [
    {
      "type": "replace_text",
      "path": "src/app.py",
      "old": "old text",
      "new": "new text"
    }
  ]
}
```

## 怎么做

完整流转：

```text
Main Agent
  -> AgentAction(tool="run_subagent", role="implementer")
  -> ToolRegistry.call(...)
  -> SubAgentPolicy 生成 allowed_tools / allowed_paths
  -> RoleBasedSubAgentExecutor.execute(task)
  -> ImplementerSubAgent.execute(task)
  -> 解析 operations JSON
  -> 校验 replace_text / write_file 是否被允许
  -> FileTools.replace_text / FileTools.write_file
  -> SubAgentResult(changed_paths + diffs)
  -> ToolResult
  -> Trace + observations
```

当前设计约束：

- Implementer 不自己推理改法，只执行结构化操作。
- Day67 不默认把 CLI 真实模型接入 implementer 写文件，避免绕过普通工具的 PermissionHook。
- Day68 会继续补 Main Agent Approval，把子 Agent 写入和主 Agent 验收接起来。

## 做了什么

- 新增 `minicode/subagents/implementer.py`。
- 新增 `ImplementerOperation` 和 `ImplementerSubAgent`。
- `create_default_subagent_executor(workspace)` 支持注册 implementer。
- `minicode/subagents/__init__.py` 暴露 Implementer 入口。
- 补充 replace、write、未授权工具、非法 operations 和 ToolRegistry metadata 测试。

## 学习重点

Implementer SubAgent 的本质是受控执行器：

```text
主 Agent：决定要改什么，并给出结构化 operations
Implementer：执行允许的文件操作
FileTools：负责路径保护和 diff
Trace：保存 changed_paths、operations 和 diff 证据
```
