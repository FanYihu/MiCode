# Day 46：Context Compression / Session Summary

## 今日目标

实现 Session 级上下文压缩。

这章不删除原始 Message History，而是把较早消息压缩成 Session Summary，并保留最近消息，用于下一次 Agent prompt。

## 为什么做

Message History 会越来越长，尤其工具输出可能非常大。

如果每次都把完整 messages 放进 prompt，会浪费上下文，也会让模型被旧细节干扰。

更合理的结构是：

```text
Working Memory
Session Summary
Recent Messages
  -> Compact Session Context
  -> Agent Prompt
```

## 做什么

新增 `SessionSummary`：

```python
SessionSummary(
    session_id,
    summary,
    covered_message_ids,
    source_message_count,
    updated_at,
    metadata,
)
```

新增 `ContextCompressor`：

- `split_messages()`：把消息拆成历史消息和最近消息。
- `summarize()`：把历史消息压缩进 summary，并避免重复覆盖同一条消息。
- `compact()`：返回最新 summary 和保留原文的 recent messages。

新增 `build_session_context()`：

- 合并 Working Memory。
- 合并 Session Summary。
- 合并 Recent Messages。
- 生成适合注入 prompt 的紧凑文本。

## 怎么做

- Summary 保存为 `.minicode/sessions/{session_id}.summary.json`。
- Message History 原文件不删除。
- 默认保留最近 8 条消息原文，较早消息进入 summary。
- 当前优先复用配置模型生成结构化摘要，字段包括 overview、goals、decisions、completed、errors、constraints 和 next_steps。
- LLM 摘要失败或没有 client 时，自动使用确定性结构化摘要兜底，不影响 Agent 主流程。
- 旧版只有 summary 文本的文件可以继续读取，并在下一次更新时迁移为 structured summary。
- CLI agent 在 session 模式下：
  1. run 前读取 Working Memory、Summary、Recent Messages 并注入 prompt。
  2. run 后追加 messages。
  3. 更新 Working Memory。
  4. 更新 Session Summary。

## 验收标准

1. 可以把消息拆成历史消息和最近消息。
2. Summary 只覆盖未覆盖过的消息，避免重复摘要。
3. Summary 文件可以保存和读取。
4. 可以构建包含 Working Memory、Summary、Recent Messages 的 session context。
5. CLI agent 会生成 `.summary.json`。
6. 下一次 CLI agent run 能读取并注入已有 session context。
7. 全量测试通过。

## 做了什么

- 新增 `context.py`。
- 实现 `SessionSummary`、`SessionSummaryStore`、`ContextCompressor`。
- SessionSummary 新增 `structured` 字段，保存目标、决策、完成项、错误、约束和下一步。
- ContextCompressor 支持复用 OpenAI-compatible client 生成 LLM 结构化摘要。
- 摘要模型异常时回退到确定性结构化摘要。
- `TextLLM` 支持 `set_session_context()`。
- `build_action_prompt()` 新增 Session context 区块。
- `run_agent_task()` 在 session 模式下会读写 summary，并把 compact context 注入 Agent。
- 补充 Context Compression 和 CLI 集成测试。

## 思考题

为什么压缩层不直接改写 Message History？

提示：原始消息是事实来源，summary 是派生视图；派生视图可以重建，事实来源不能随便丢。
