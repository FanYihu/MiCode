# Day 56：Context Layer 设计

## 为什么做

前面已经有两类上下文会进入 Agent Prompt：

- Session Context：当前目标、约束、摘要、最近消息。
- Long-term Memory：经过召回、精排和预算裁剪后的长期记忆。

如果继续用字符串拼接，后续加入工具结果摘要、Artifact 占位符、权限警告和安全提示时，会越来越难控制优先级和长度。

Day56 的目标是把上下文变成“分层资源”，每一层都有来源、优先级和预算。

## 做什么

新增 `micode/context/layers.py`：

- `ContextLayer`：一块上下文来源。
- `ContextLayerResult`：某层是否被注入、是否截断、使用多少字符。
- `ContextAssembly`：最终拼装结果和审计信息。
- `ContextLayerAssembler`：按优先级和预算组合多层上下文。

CLI 现在不再直接拼：

```text
session_context + long_term_memory
```

而是走：

```text
ContextLayer(session)
ContextLayer(long_term_memory)
  -> ContextLayerAssembler
  -> final session_context
```

## 怎么做

当前层：

```text
session
  priority: 100
  source: session_memory

long_term_memory
  priority: 80
  source: hybrid_memory_retrieval
```

预算：

```text
context_budget_chars: 默认 4000
memory_budget_chars: 默认 1800
session layer budget = context_budget_chars - memory_budget_chars
long_term_memory layer budget = memory_budget_chars
```

CLI 参数：

```bash
micode agent "继续任务" \
  --context-budget-chars 4000 \
  --memory-budget-chars 1800
```

## 组合规则

1. required layer 优先。
2. priority 高的 layer 优先。
3. 空 layer 会被记录为 omitted，而不是静默消失。
4. 单层超预算会被截断，并加 `... [layer truncated]`。
5. 总预算耗尽时，后续 layer 会被省略。
6. 每层结果都会写入 trace metadata。

Trace metadata：

```json
{
  "context_assembly": {
    "budget_chars": 4000,
    "used_chars": 1200,
    "layers": [
      {
        "name": "session",
        "included": true,
        "truncated": false,
        "used_chars": 600
      }
    ]
  }
}
```

## 关键边界

- Context Layer 不负责生成摘要。
- Context Layer 不负责长期记忆召回。
- Context Layer 不负责模型决策。
- 当前使用字符预算，Day60 会升级为 Token Estimate。
- 现有 Session Context 和 Long-term Memory 的文本格式保持不变。

## 参考项目学到了什么

参考项目把上下文作为有层级、有预算、有审计信息的运行资源。Micode 这一章先实现最小可运行版本，让后续 Tool Result Summary、Artifact Placeholder 和 Auto Compaction 都可以接入同一套层模型。

## 验收标准

- Context Layer 能按 required 和 priority 排序。
- 能按总预算和单层预算截断内容。
- 空 layer 会留下 omitted 记录。
- CLI 运行前的 session 与 long-term memory 上下文走统一 layer assembler。
- Trace metadata 能记录 layer 注入情况。
- 现有 Agent 行为保持兼容。

## 做了什么

新增 `micode/context/layers.py`，实现上下文分层、优先级排序、字符预算和截断审计。

CLI 的 Agent 模式改为通过 Context Layer 组合 Session Context 与 Long-term Memory，并记录 `context_assembly` metadata。
