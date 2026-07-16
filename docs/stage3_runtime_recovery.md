# Stage 3: Runtime 与恢复

## Runtime 主干

`MicodeAgent` 仍负责模型决策、ToolRegistry 调用和 Trace。`AgentRuntime` 不复制
Agent loop，而是在后台线程中执行同步 Agent，并实时输出 `RuntimeEvent`：

```text
run_started
  -> model_started (explore)
  -> tool_batch_started (act)
  -> tool_batch_completed (act)
  -> run_stopped (finish/waiting)
  -> runtime_result
```

`RuntimeProfile` 控制最大轮次、有限模型重试、widening 标记和证据门禁。
每次停止都写入明确的 `StopReason`，调用方不再需要只靠 `RunStatus` 猜原因。

## Session 恢复

- `micode session inspect <id>`：检查会话、消息数量、摘要和可恢复状态。
- `micode session replay <id>`：按持久化顺序回放 SessionMessage。
- `micode session summary <id>`：读取压缩摘要。
- `micode agent ... --session-id <id>`：加载已有消息、Working Memory 和摘要后继续。

## Checkpoint 与 Rewind

默认 ToolRegistry 会在路径明确的 workspace 写工具执行前创建 checkpoint：

1. 写入前内容按 SHA-256 保存到 blob，重复内容不会重复保存。
2. 工具成功后记录 after SHA-256。
3. `checkpoint preview` 比较当前哈希和 after 哈希。
4. 只有没有后续冲突时，`checkpoint rewind` 才恢复旧 blob 或删除原本不存在的文件。

Shell 和其他无法可靠枚举影响路径的工具明确标记 `reversible=false`，不能伪装成
可自动回退。
