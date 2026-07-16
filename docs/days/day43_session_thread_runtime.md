# Day 43：Session / Thread Runtime

## 今日目标

实现 MiniCode 的最小会话层。

这章不做长期记忆抽取，而是先让多次 Run 能归属于同一个 Session。

## 为什么做

Trace 只能描述“一次任务怎么执行”。

Memory 需要知道“这些任务属于同一段连续对话”。如果没有 Session，后面的 Working Memory、Session Summary、长期记忆和图谱更新都没有可靠边界。

关系如下：

```text
Session / Thread
  -> Run
    -> Step
      -> Event
```

## 做什么

新增 `Session`：

```python
Session(
    id,
    title,
    created_at,
    updated_at,
    run_ids,
    metadata,
)
```

新增 `SessionStore`：

- create：创建 Session。
- save：保存为 JSON。
- load：按 id 读取。
- get_or_create：CLI 入口复用已有会话或创建新会话。
- add_run：把一次 Run 追加到 Session。
- list_sessions：列出最近会话。

## 怎么做

- `Agent` 只把 `session_id` 写入 Run metadata。
- `CLI` 负责 Session 持久化。
- Session 文件先保存在 `.minicode/sessions/{session_id}.json`。
- 后续 Day44 再把 Event Log / Message History 接到 Session 上。

## 验收标准

1. `Session` 可以创建、序列化、反序列化。
2. `Session.add_run()` 可以追加 run id，且不会重复追加。
3. `SessionStore` 可以保存、读取、更新和列出 Session。
4. `agent` CLI 可以通过 `--session-id` 把 run 归入 Session。
5. trace 的 run metadata 中记录 `session_id` 和 `session_path`。
6. 全量测试通过。

## 做了什么

- 新增 `session.py`，实现 `Session` 和 `SessionStore`。
- `MiniCodeAgent` 支持 `session_id`，并写入 Run metadata。
- `run_agent_task()` 支持 `session_id`、`session_dir` 和 `session_title`。
- CLI `agent` 子命令新增 `--session-id`、`--session-dir`、`--session-title`。
- 补充 Session 单元测试和 CLI 集成测试。

## 思考题

为什么 Session 不直接保存完整 Event 内容？

提示：Session 是组织边界，Event Log 是事件明细，后面要分层保存，避免一个对象无限膨胀。
