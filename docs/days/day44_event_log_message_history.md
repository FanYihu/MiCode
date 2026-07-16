# Day 44：Event Log / Message History

## 今日目标

把一次 Run 的 trace 事件沉淀成 Session 级消息流。

Day 43 的 Session 只保存 `run_ids`，这一章补上会话回放和后续记忆压缩需要的 Message History。

## 为什么做

Trace 是执行明细，适合调试。

Memory 不应该直接读取一堆原始 trace，而应该先有一层更稳定的会话消息流：

```text
Trace events
  -> SessionMessage
  -> Message History
  -> Working Memory / Summary / Long-term Memory
```

这样后续压缩、召回和图谱抽取都有统一输入。

## 做什么

新增 `SessionMessage`：

```python
SessionMessage(
    id,
    session_id,
    run_id,
    role,
    type,
    content,
    created_at,
    metadata,
)
```

角色约定：

- `user`：用户任务。
- `assistant`：模型最终文本或普通文本事件。
- `tool`：工具调用结果。
- `error`：错误事件。
- `system`：状态事件。

新增 `SessionMessageStore`：

- `append_trace()`：把 trace 转成消息并追加保存。
- `append_messages()`：追加消息并按 id 去重。
- `load_messages()`：读取某个 Session 的消息流。
- `save_messages()`：保存消息流。

## 怎么做

- Session 索引仍保存在 `.minicode/sessions/{session_id}.json`。
- Message History 保存在 `.minicode/sessions/{session_id}.messages.json`。
- CLI agent 在传入 `--session-id` 时，同时更新 Session 和 Message History。
- trace metadata 记录 `session_messages_path`，方便复盘定位。

## 验收标准

1. trace 可以转换成 SessionMessage 列表。
2. 用户任务会成为 `role=user` 的消息。
3. trace event 会根据类型映射为 assistant/tool/error/system。
4. Message Store 可以追加、去重、读取消息。
5. Session 列表不会把 `.messages.json` 当成 Session。
6. CLI agent 运行后会生成 session 消息文件。
7. 全量测试通过。

## 做了什么

- 新增 `SessionMessage` 和 `SessionMessageStore`。
- 新增 `messages_from_trace()`，把 run task 和 trace events 转成会话消息。
- 新增 `role_for_event_type()`，统一 trace event 到消息角色的映射。
- `run_agent_task()` 在 session 模式下会追加 `.messages.json`。
- 补充消息转换、消息存储、CLI 集成测试。

## 思考题

为什么不直接把完整 trace 当成 Memory？

提示：trace 是调试数据，包含大量工具细节；Memory 需要先经过消息化、压缩、抽取和筛选。
