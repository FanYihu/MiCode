# Day 59：Runtime Stability：Idempotent Writes / Prompt Cache / Decision Freeze

## 为什么做

Day58 已经能把超大工具结果外置成 Artifact。下一步如果直接做读取工具，会漏掉三个更底层的问题：

- 同一大结果重复写入，会生成多份 artifact。
- 稳定上下文没有 cache key，后续无法判断哪些 prompt 前缀可复用。
- 模型决策前的输入没有冻结快照，复盘时难以解释“模型当时基于什么做了决定”。

所以本章先补运行稳定层。

## 做什么

本章完成三件事：

1. Artifact 幂等写入。
2. Prompt Cache 本地指纹。
3. Decision Freeze 决策冻结。

## 怎么做

### 1. 幂等 Artifact 写入

Artifact id 从内容 hash 派生：

```text
artifact:tool-result:{sha256[:24]}
```

同一工具输出重复保存时：

- 返回同一个 artifact id。
- 返回同一个 path。
- 不覆盖第一次写入的 metadata。

这保证重复执行、重试或并行调用不会制造一堆内容相同的 artifact。

### 2. Prompt Cache

新增 `context/prompt_cache.py`。

Context Assembly 完成后，会写入：

```text
.minicode/prompt-cache/{cache-key}.json
```

cache key 同样由内容 hash 派生：

```text
prompt-cache:{sha256[:24]}
```

保存内容：

```json
{
  "key": "prompt-cache:...",
  "content": "最终 session_context",
  "size_chars": 1234,
  "sha256": "...",
  "metadata": {
    "task": "...",
    "session_id": "...",
    "context_assembly": {}
  }
}
```

当前这是本地 prompt cache 指纹，不直接调用供应商 cache API。后续如果 provider 支持 prompt cache，可以用这个 key 映射过去。

### 3. Decision Freeze

新增 `context/decision.py`。

每次模型决策前冻结：

- `task_hash`
- `observations_hash`
- `session_context_hash`
- `prompt_cache_key`
- `turn_index`

写入：

```text
trace["run"]["metadata"]["decision_freezes"]
```

这样复盘时可以知道每一轮模型决策看到的上下文是否变化，而不用把完整 prompt 再复制一遍。

## 当前流程

```text
ContextLayerAssembler
  -> PromptCacheStore.put(...)
  -> prompt_cache_key
  -> MiniCodeAgent
  -> before each model turn:
       freeze_decision(...)
  -> ToolResult
  -> ArtifactStore.save_tool_result(...)
       idempotent by content hash
```

## 关键边界

- Artifact 幂等按内容 hash，不按 tool_call_id。
- Prompt Cache 当前只做本地稳定指纹，不做远端 API cache。
- Decision Freeze 存 hash，不存完整 prompt，避免再次膨胀 trace。
- Artifact Read Tool 顺延到下一章。

## 参考项目学到了什么

参考项目强调运行过程的可复现与可审计。MiniCode 在本章把“写入产物”和“模型决策输入”都变成稳定可追踪对象，为后续上下文读取、缓存复用和错误复盘打基础。

## 验收标准

- 相同工具输出重复保存得到同一个 artifact。
- artifact 不覆盖第一次写入的 metadata。
- 相同 prompt context 得到同一个 cache key。
- 不同 prompt context 得到不同 cache key。
- 每轮模型调用前都会生成 decision freeze。
- decision freeze 关联 prompt cache key。
- CLI trace metadata 记录 prompt cache 和 decision freeze。

## 做了什么

新增 `context/prompt_cache.py` 和 `context/decision.py`。

Artifact 写入改为内容 hash 幂等；CLI 在 Agent run 前写入 Prompt Cache；Agent 每轮模型决策前写入 Decision Freeze。
