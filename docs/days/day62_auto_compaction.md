# Day 62：Auto Compaction

## 为什么做

Day61 已经能估算上下文 token 成本，但只有估算还不够。

当 Session、长期记忆、工具摘要越来越多时，Micode 需要自动决定哪些内容保留、哪些内容截断、哪些内容省略，并且把决策原因写进 trace，方便复盘。

## 做什么

新增自动压缩审计：

- `ContextLayerAssembler` 支持字符预算和可选 token 预算。
- token 预算会转换成更保守的有效字符预算。
- 每层上下文记录 `keep`、`truncate`、`omit` 或 `skip`。
- 记录压缩前后字符数、token 数和节省量。
- CLI 新增 `--context-budget-tokens`。

## 怎么做

核心流程：

```text
ContextLayer[]
  -> 按 required / priority 排序
  -> 计算 raw context token
  -> budget_chars + budget_tokens 得到 effective_budget_chars
  -> 逐层组装
  -> 超出层预算则 truncate
  -> 总预算不足则 omit
  -> ContextAssembly.compaction 写入审计信息
```

压缩动作：

```text
keep      层完整进入 prompt
truncate  层进入 prompt，但内容被截断
omit      层有内容，但因为预算不足没有进入 prompt
skip      空层或天然无内容
```

## 做了什么

- `ContextAssembly` 增加 `compaction` metadata。
- `ContextLayerAssembler` 增加 `budget_tokens` 和 `chars_per_token`。
- `ContextLayerAssembler` 会记录 raw / used / saved 的字符和 token 成本。
- CLI `agent` 增加 `--context-budget-tokens`。
- 增加 Context Layer 和 CLI 自动压缩测试。

## 学习重点

Auto Compaction 不是替代 Context Layer，而是 Context Layer 的自动决策审计层。

后续 Day63 Context Review 可以直接检查：

```text
是否压缩过？
压缩了哪一层？
为什么压缩？
压缩后是否仍超预算？
```
