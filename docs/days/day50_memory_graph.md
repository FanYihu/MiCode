# Day 50：Memory Graph 数据结构

## 为什么做

前面已经有 Session、Message、Working Memory、Summary、Episode、Semantic 和 Procedure，但它们还是分散的 JSON 列表。

Memory Graph 的作用是把这些记忆连起来，让系统知道：

- 这个事实来自哪次经历。
- 这个流程来自哪次成功 run。
- 这个 episode 属于哪个 session。
- 哪些 procedure 未来可以被 review 成 skill。

## 做什么

新增一个轻量图索引：

- `MemoryNode`：表示 session、run、episode、semantic、procedure 等节点。
- `MemoryEdge`：表示 `derived_from_episode`、`records_run`、`belongs_to_session` 等关系。
- `MemoryGraph`：在内存中管理节点和边，并按 id 去重。
- `MemoryGraphStore`：把图保存到 `.micode/memory/graph.json`。
- CLI session 模式每次 run 结束后自动更新 graph。

## 怎么做

实现路径：

```text
Trace
  -> EpisodicMemory
  -> SemanticMemory / ProceduralMemory
  -> build_memory_graph(...)
  -> MemoryGraphStore.upsert_graph(...)
  -> .micode/memory/graph.json
```

当前 Day50 只做“来源图”和“索引结构”，不急着做复杂知识图谱：

- 先连清楚已有 memory 的来源关系。
- 先保证节点和边稳定去重。
- Day51 再从内容里抽 Entity / Relation。
- Day52 再处理 Temporal Facts / Conflict Resolution。

## 参考项目学到了什么

参考项目里长期记忆不是孤立字符串，而是要能追溯来源、支持后续检索和复盘。

Micode 这一章没有照搬复杂存储，只实现一个本地 JSON 图索引，为后续 graph traversal 和 hybrid retrieval 留接口。

## 验收标准

- 可以创建、保存、读取 Memory Graph。
- 同一个节点或边重复写入不会产生重复数据。
- Episode 能连接到 Session 和 Run。
- Semantic / Procedural Memory 能连接回来源 Episode。
- Procedure 能连接到 Skill Candidate 概念节点。
- CLI session run 后会写入 `graph.json`，并在 trace metadata 里记录图路径、节点 id、边 id 和图大小。

## 做了什么

新增 `memory/graph.py`，实现 MemoryNode、MemoryEdge、MemoryGraph、MemoryGraphStore 和 build_memory_graph。

CLI 在 session 模式下完成 episodic、semantic、procedural memory 后，会自动更新 `.micode/memory/graph.json`，把长期记忆之间的来源关系保存下来。
