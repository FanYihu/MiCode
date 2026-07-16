# Day 45：Working Memory

## 今日目标

为每个 Session 维护一份短期工作状态。

Working Memory 不是长期记忆，也不是完整消息历史。它只回答一个问题：当前这段会话进行到哪里了？

## 为什么做

Message History 记录“发生过什么”，但 Agent 每次继续工作时更需要一个可快速读取的状态：

```text
当前目标是什么？
哪些事情已经完成？
还有哪些待办？
本会话有什么约束？
最近发生了什么？
```

如果每次都从完整消息流重新推理，成本高，而且容易丢掉重点。

## 做什么

新增 `WorkingMemory`：

```python
WorkingMemory(
    session_id,
    current_goal,
    completed,
    todo,
    constraints,
    recent_messages,
    updated_at,
    metadata,
)
```

新增 `WorkingMemoryStore`：

- `load()`：读取当前 Session 的工作记忆，不存在时返回空状态。
- `save()`：保存工作记忆。
- `update_from_messages()`：用新增 SessionMessage 更新工作记忆。

## 怎么做

- Working Memory 保存为 `.micode/sessions/{session_id}.working_memory.json`。
- CLI agent 在 session 模式下，先写入 Message History，再用本次新增消息更新 Working Memory。
- 当前实现先用确定性规则：
  - `user` 消息更新 `current_goal`。
  - `assistant` 文本进入 `completed`。
  - `error` 事件进入 `todo`。
  - 最近消息进入 `recent_messages`，并做长度限制。
- 后续 Day46 再做压缩摘要，Day54 再做更精细的注入策略。

## 验收标准

1. WorkingMemory 可以创建、序列化、反序列化。
2. 可以显式设置 goal、todo、completed、constraints。
3. 可以从 SessionMessage 更新当前目标、完成项、错误待办和最近消息。
4. WorkingMemoryStore 可以保存和读取 `.working_memory.json`。
5. CLI agent session 模式会生成 working memory 文件。
6. Session 列表不会把 working memory 文件当成 session。
7. 全量测试通过。

## 做了什么

- 新增 `working_memory.py`。
- 实现 `WorkingMemory` 和 `WorkingMemoryStore`。
- 支持显式状态更新：`set_goal()`、`add_todo()`、`complete_item()`、`add_constraint()`。
- CLI agent 在 `--session-id` 模式下会更新 `{session_id}.working_memory.json`。
- 补充 Working Memory 单元测试和 CLI 集成测试。

## 思考题

为什么 Working Memory 不直接保存所有消息？

提示：所有消息属于 Message History；Working Memory 是给下一次推理快速读取的短期状态。
