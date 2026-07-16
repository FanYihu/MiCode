# Day 53：Hybrid Retrieval

## 为什么做

长期记忆已经包含 Episode、Semantic、Procedure 和 Temporal Graph，但如果下一次任务不会主动查找，它们只是磁盘里的历史文件。

单一检索方式也不够：

- 关键词适合文件名、工具名和明确术语。
- 向量适合不同表达但语义相近的任务。
- 图遍历适合找到与命中事实相连的经历、实体和流程。

## 做什么

新增 `HybridMemoryRetriever`：

- 把 Episode、Semantic、Procedure 和当前 Graph Fact 转成统一 `MemoryDocument`。
- 计算 keyword score。
- 客户端支持 `embed(texts)` 时计算 cosine vector score。
- 从关键词或向量命中的节点做一跳双向 graph traversal。
- 默认过滤 `superseded` 事实，保留并标注 `conflicting` 事实。
- 返回包含各通道分数的 `MemoryRetrievalResult`。
- 在 Agent 每次运行前自动召回，并注入 Session Context。

## 怎么做

召回流程：

```text
Current Task
  -> build MemoryDocument[]
  -> keyword retrieval
  -> optional embedding retrieval
  -> select seed nodes
  -> one-hop graph traversal
  -> weighted score
  -> top-k memories
  -> Relevant Long-Term Memory
  -> Agent prompt
```

当前权重：

```text
score =
  keyword_score * 0.50
  + vector_score * 0.35
  + graph_score * 0.15
```

这些是 Day53 的基础融合权重。Day54 会进一步加入记忆类型、时效性、置信度、冲突状态和注入预算。

## 向量接口

当前 OpenAI-compatible 文本客户端只保证 `generate()`，因此不能假装已经调用 embedding 模型。

召回器使用真实可选接口：

```python
embedding_client.embed([
    "query",
    "memory document 1",
    "memory document 2",
])
```

客户端支持该接口时启用向量召回；不支持时继续运行关键词和图检索。

## 时序过滤

默认策略：

- `active`：参与召回。
- `conflicting`：参与召回，并在 prompt 中标记冲突。
- `superseded`：默认排除，只有历史查询显式开启时返回。

## 注入格式

```text
Relevant Long-Term Memory:
- [semantic] Micode uses pytest
- [procedure] update-cli Update CLI behavior and run tests.
- [graph_fact status=conflicting] Micode uses_model model-a
```

Trace metadata 会记录：

- `retrieved_memory_ids`
- 每条记忆的总分
- keyword / vector / graph 分数
- 时序状态

## 参考项目学到了什么

参考项目把上下文视为受控资源，而不是无条件塞入所有历史。Micode 因此把长期记忆先召回、再压缩注入，并保留每个检索通道的可解释分数。

## 验收标准

- 没有 embedding client 时关键词和图检索仍能工作。
- 支持 `embed(texts)` 时向量相似度参与融合。
- 图遍历可以召回不包含查询词的邻居记忆。
- superseded 事实默认不会进入上下文。
- conflicting 事实会被明确标记。
- Agent 运行前能获得相关长期记忆。
- Trace 能记录实际召回结果和分数。

## 做了什么

新增 `memory/retrieval.py`，实现统一检索文档、关键词匹配、可选向量相似度、图邻居扩展、时序过滤和结果格式化。

CLI 在 Agent run 前根据当前任务检索长期记忆，并把结果作为 `Relevant Long-Term Memory` 注入 prompt。
