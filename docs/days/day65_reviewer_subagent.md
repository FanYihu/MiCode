# Day 65：Reviewer SubAgent

## 为什么做

Day64 只定义了 SubAgent 契约，还没有真正能执行的子 Agent。

Day65 先补 Reviewer SubAgent：主 Agent 把一个明确审查任务交出去，Reviewer 只读上下文、发现风险、返回摘要和证据，不直接修改项目。

## 做什么

新增两个能力：

- `ReviewerSubAgent`：执行只读审查，输出结构化 finding。
- `RoleBasedSubAgentExecutor`：按 `role` 分发给 reviewer / tester / implementer，后续章节可以继续扩展。

Reviewer 当前检查四类风险：

- 疑似密钥、token、password 泄露。
- 危险 shell/git 命令。
- `TODO`、`FIXME`、`NotImplementedError` 等占位实现。
- 实现类任务缺少测试或验证证据。

## 怎么做

完整流转：

```text
Main Agent
  -> AgentAction(tool="run_subagent", role="reviewer")
  -> ToolRegistry.call("run_subagent", ...)
  -> SubAgentPolicy 生成受控 SubAgentTask
  -> RoleBasedSubAgentExecutor.execute(task)
  -> ReviewerSubAgent.execute(task)
  -> ReviewerFinding[]
  -> SubAgentResult(summary + metadata.findings)
  -> ToolResult.output 给主 Agent observation
  -> ToolResult.metadata 写入 Trace
```

关键边界：

- Reviewer 不写文件。
- Reviewer 不扩大工具和路径权限。
- Reviewer 的完整 findings 放在 metadata，主 Agent observation 只拿短摘要。
- 找不到对应 role executor 时返回失败结果，而不是抛异常打断主 Agent。

## 做了什么

- 新增 `micode/subagents/reviewer.py`。
- 新增 `ReviewerFinding` 和 `ReviewerSubAgent`。
- 新增 `micode/subagents/router.py`。
- 新增 `RoleBasedSubAgentExecutor` 和 `create_default_subagent_executor()`。
- 更新 `micode/subagents/__init__.py` 暴露默认入口。
- 补充 Reviewer、角色分发、默认 executor 和 ToolRegistry metadata 测试。
- 确认 `tests/test_subagents.py` 全部通过。

## 学习重点

Reviewer SubAgent 的重点不是“比主 Agent 更聪明”，而是把审查职责拆出来：

```text
主 Agent：决定什么时候需要审查，以及审查后怎么处理
Reviewer：只负责发现风险、给证据、保持只读
Trace：保存审查摘要、finding、证据和父 run 关系
```
