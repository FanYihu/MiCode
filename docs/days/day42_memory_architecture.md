# Day 42：Memory Architecture

## 今日目标

重新设计 Micode 的 Memory 主线。

这章先不写 `MemoryEntry` 代码，而是把最终系统的记忆架构定下来，避免后面做成简单 CRUD 或纯向量库玩具。

## 为什么做

真正的 Agent Memory 不只是“保存几段文本”。

更完整的结构应该是：

```text
Session / Thread Runtime
  -> Working Memory
  -> Context Compression
  -> Episodic Memory
  -> Semantic Memory
  -> Procedural Memory
  -> Skill Candidate Review
  -> Temporal Knowledge Graph
  -> Hybrid Retrieval
  -> Injection Policy
```

如果 Micode 没有会话、事件流和压缩层，长期记忆就没有可靠来源；如果没有图结构，只靠向量召回又很难处理实体关系、时间变化和事实冲突。

## 前沿系统学到了什么

从 LangGraph / LangMem 学到：

- 先有 thread/session 级短期状态，再有跨 session 的长期记忆。
- 长期记忆常分为 semantic、episodic、procedural。

从 Letta / MemGPT 学到：

- 记忆需要分层：当前上下文里的核心记忆、可搜索的历史记忆、长期归档记忆。
- Agent 应该能通过受控工具更新记忆，而不是只被动读取。

从 Zep / Graphiti 学到：

- 记忆可以建成 temporal knowledge graph。
- 事实需要带时间、来源和更新关系，避免旧事实覆盖新状态。

从 Mem0 / Memory OS 方向学到：

- 生产级记忆系统要包含抽取、更新、合并、冲突解决、检索、重排和生命周期管理。

## 新 Memory 主线

```text
Day 42：Memory Architecture
Day 43：Session / Thread Runtime
Day 44：Event Log / Message History
Day 45：Working Memory
Day 46：Context Compression / Session Summary
Day 47：Episodic Memory
Day 48：Semantic Memory
Day 49：Procedural Memory，与 Skill 打通
Day 50：Memory Graph 数据结构
Day 51：Entity / Relation Extraction
Day 52：Temporal Facts / Conflict Resolution
Day 53：Hybrid Retrieval，keyword + vector-ready + graph traversal
Day 54：Memory Ranking / Injection Policy
Day 55：Memory Review
Memory-Skill Bridge：Skill Candidate Pipeline
```

## 承接已有能力

- Trace 已经能保存运行过程，但还不是会话。
- Skill 已经描述“怎么做”，后续 Procedural Memory 只能先生成 Skill Candidate，再经 Review 提升为正式 Skill。
- Tool Registry 已经统一工具调用，后续 Memory update / recall 也应该走工具契约。
- 当前 `persistence.py` 能保存 trace，后续 Session Store 可以复用保存/加载思路。

## 实现策略

先用本地 JSON/SQLite 形态表达 graph model，不急着接 Neo4j / Kuzu / FalkorDB。

核心原则：

- 数据模型要像真实系统，不做以后会推翻的玩具结构。
- 存储实现可以轻，但抽象边界要对。
- 先有 session 和 event，再从 event 压缩和提炼 memory。
- Graph memory 是主线能力，不是可选扩展。
- 经验到 Skill 必须经过候选层，避免把一次性经验、项目特例或错误流程直接注入长期 Skill。

## 验收标准

1. Stage 2 roadmap 改成新的 Memory 主线。
2. Stage 2 README 明确 Session、Compression、Graph Memory、Hybrid Retrieval 的边界。
3. Day 42 文档说明为什么先做架构，不直接做 MemoryEntry CRUD。
4. 全量测试通过。

## 思考题

为什么纯向量库不够做 Agent Memory？

提示：向量检索擅长语义相似，不擅长表达“谁和谁的关系何时成立、何时失效、来源是什么”。
