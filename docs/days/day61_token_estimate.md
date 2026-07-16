# Day 61：Token Estimate

## 为什么做

前面已经有 Context Layer、Tool Result Summary、Artifact 和 Prompt Cache。

但如果不知道每一块上下文大概消耗多少 token，后续自动压缩就只能靠字符预算猜。Day61 先建立一个稳定、可审计的估算层。

## 做什么

新增 Token Estimate：

- 按字符数估算 token，默认 `4 chars ~= 1 token`。
- Context Layer 记录每层原始 token 和最终使用 token。
- Context Assembly 记录整体估算 token。
- Agent 每轮模型决策前记录 task、observations、session context、tool descriptions、skill summaries 的估算。
- CLI 记录 assembled context 的估算，并写入 prompt cache metadata。

## 怎么做

核心流程：

```text
ContextLayerAssembler
  -> trim layer content
  -> estimate_tokens(layer original / used)
  -> ContextAssembly.estimated_tokens

MiniCodeAgent.run()
  -> 每轮模型调用前
  -> estimate_text_parts(task / observations / session_context / tools / skills)
  -> run.metadata["token_estimates"]

CLI run_agent_task()
  -> ContextLayerAssembler.assemble(...)
  -> estimate_text_parts(task / assembled_context / retrieved_memory_context)
  -> prompt cache metadata + run metadata
```

## 做了什么

- 新增 `minicode/context/tokens.py`。
- `ContextLayerResult` 增加 `original_tokens`、`used_tokens`。
- `ContextAssembly` 增加 `estimated_tokens`。
- `MiniCodeAgent` 每轮记录 `token_estimates`。
- CLI 增加 `context_token_estimate`，并写入 prompt cache metadata。
- 增加 Token Estimate、Context Layer、Agent、CLI 测试。

## 学习重点

这章不是为了得到“精确 token 数”，而是先建立稳定的成本审计。

真正精确的 tokenizer 可以后面替换，但外部契约不变：

```text
chars -> estimated_tokens -> trace metadata -> 压缩/截断决策依据
```
