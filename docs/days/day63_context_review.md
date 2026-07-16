# Day 63：Context Review

## 为什么做

Day56-Day62 已经逐步完成 Context Layer、Tool Result Summary、Artifact、Prompt Cache、Decision Freeze、Token Estimate 和 Auto Compaction。

但这些 metadata 分散在 trace 的不同位置。Context Review 的目标是把它们串起来体检，判断一次 Agent run 的上下文链路是否健康。

## 做什么

新增 Context Review：

- 检查 `context_assembly` 是否存在。
- 检查 assembled context 是否超出字符预算。
- 检查 `compaction` metadata 是否完整、自洽。
- 检查 `context_token_estimate` 是否包含 assembled context。
- 检查 prompt cache 文件是否存在、hash 是否匹配。
- 检查 decision freeze 的 `prompt_cache_key` 是否和 run prompt cache 一致。
- 检查 artifact 引用文件是否存在、hash 是否匹配、placeholder 是否写入 event。
- 新增 `context-review` CLI。

## 怎么做

核心流程：

```text
trace.json
  -> review_context_trace_file()
  -> review_context_trace()
  -> review_context_assembly()
  -> review_context_token_estimate()
  -> review_prompt_cache()
  -> review_decision_freezes()
  -> review_artifact_references()
  -> ContextReviewReport
```

CLI：

```bash
python3 -m micode.cli context-review .micode/traces/xxx.json
```

## 做了什么

- 新增 `micode/context/review.py`。
- 新增 `ContextReviewIssue` 和 `ContextReviewReport`。
- CLI 新增 `context-review` 子命令。
- 增加健康 trace、预算超限、prompt cache hash mismatch、decision freeze mismatch、artifact hash mismatch 测试。

## 学习重点

Context Review 是上下文系统的体检入口，不直接改变上下文。

它回答的是：

```text
这次 run 的上下文有没有超预算？
压缩记录是否完整？
prompt cache 是否还能复用？
decision freeze 是否指向同一个上下文？
artifact 引用是否还能读回来？
```
