# Day 47：Episodic Memory

## 今日目标

从一次 Run / trace 中提炼 Episodic Memory。

Episodic Memory 记录“发生过的一次具体经历”，比如某次实现 CLI 参数、某次运行测试失败、某次完成 Skill Router 重构。

## 为什么做

Session、Message History、Working Memory 都偏当前会话。

长期记忆需要先沉淀“经历”：

```text
Run / Trace
  -> EpisodicMemory
  -> 后续 Semantic / Procedural / Graph Memory 的来源
```

Episode 不复制完整 trace，只保存以后复盘和召回真正需要的核心信息。

## 做什么

新增 `EpisodicMemory`：

```python
EpisodicMemory(
    id,
    session_id,
    run_id,
    task,
    outcome,
    status,
    tool_names,
    evidence,
    source_event_ids,
    created_at,
    updated_at,
    metadata,
)
```

新增 `EpisodicMemoryStore`：

- `load_all()`：读取所有 episode。
- `save_all()`：保存 episode 列表。
- `upsert()`：按 id 新增或替换 episode。
- `find_by_session()`：按 session 查询经历。

## 怎么做

- Episode 保存为 `.micode/memory/episodes.json`。
- `episodic_memory_from_trace()` 从 trace 中提炼一次经历。
- `outcome` 优先取最终 assistant 文本；没有 final 时取 error；再没有时取最近事件内容。
- `tool_names` 从 steps metadata 提取并去重。
- `evidence` 从 tool_call、error、text 事件中提取短证据。
- CLI agent 在 session 模式下会自动写入 episodic memory。

## 验收标准

1. trace 可以提炼成 EpisodicMemory。
2. Episode 包含 session_id、run_id、task、outcome、status。
3. Episode 记录本次用过的工具和关键证据。
4. EpisodicMemoryStore 可以 upsert、读取和按 session 查询。
5. CLI agent session 模式会写入 `.micode/memory/episodes.json`。
6. 全量测试通过。

## 做了什么

- 新增 `memory/` 子包。
- 新增 `memory/episodic.py`。
- 实现 `EpisodicMemory`、`EpisodicMemoryStore`、`episodic_memory_from_trace()`。
- CLI agent 在 session 模式下会写入 episodic memory，并把 episode id/path 写入 trace metadata。
- 补充 episodic memory 单元测试和 CLI 集成测试。

## 思考题

Episodic Memory 和 Procedural Memory 有什么区别？

提示：Episode 记录“那次发生了什么”；Procedure 记录“以后遇到类似任务应该怎么做”。
