# Day 70：Multi-Agent Review

## 为什么做

Reviewer、Tester、Implementer 单独存在还不是协作。

Day70 把它们编排成一个最小多 Agent 审查流程：先实现，再测试，最后审查，最终给出一个可审计的 approved / rejected 报告。

## 做什么

新增 `MultiAgentReviewPipeline`：

- implementer：执行结构化 operations。
- tester：运行白名单 pytest 命令。
- reviewer：阅读实现摘要、测试摘要和额外上下文。
- 聚合成 `MultiAgentReviewReport`。

通过规则：

- Implementer 必须成功。
- Tester 必须成功。
- Reviewer 必须完成，且没有 high severity finding。

## 怎么做

```text
MultiAgentReviewPipeline.run(...)
  -> SubAgentTask(role="implementer")
  -> SubAgentTask(role="tester")
  -> SubAgentTask(role="reviewer")
  -> MultiAgentReviewReport
```

每一步仍然走 `SubAgentExecutor.execute(task)`，所以可以替换为：

- `RoleBasedSubAgentExecutor`
- `ForkedSubAgentExecutor`
- 未来的 LLM SubAgent executor

## 做了什么

- 新增 `subagents/review.py`。
- 新增 `MultiAgentReviewReport`。
- 新增 `MultiAgentReviewPipeline`。
- `subagents/__init__.py` 暴露 review pipeline。
- 补充 clean change approval 和 tests failed stop 的测试。

## 学习重点

Multi-Agent Review 不是多个模型互相聊天，而是明确职责的流水线：

```text
Implementer：改
Tester：验
Reviewer：审
Pipeline：决定是否通过
Trace/metadata：保留证据
```
