# Day 48：Semantic Memory

## 今日目标

从 Episodic Memory 中提炼稳定事实。

Episodic Memory 记录“那次发生了什么”；Semantic Memory 记录“可复用的事实是什么”。

## 为什么做

Episode 仍然偏经历，未来检索时不一定需要整段经历。

比如：

```text
Episode：某次给 cli.py 增加 --session-id，并跑通测试。
Semantic：project uses_test_runner pytest。
Semantic：task had_outcome 测试通过。
```

语义事实后续可以进入 Hybrid Retrieval 和 Knowledge Graph。

## 做什么

新增 `SemanticMemory`：

```python
SemanticMemory(
    id,
    fact,
    subject,
    predicate,
    object,
    confidence,
    source_episode_ids,
    source_run_ids,
    tags,
    metadata,
)
```

新增 `SemanticMemoryStore`：

- `load_all()`：读取所有事实。
- `save_all()`：保存所有事实。
- `upsert_many()`：按稳定 fact id 合并事实来源。
- `search()`：轻量关键词搜索，后续替换成 hybrid retrieval。

## 怎么做

- Semantic Memory 保存为 `.micode/memory/semantic.json`。
- `semantic_memories_from_episode()` 优先调用当前 LLM client 抽取结构化 facts。
- LLM 抽取失败或返回空时，使用确定性兜底。
- 同一事实的 id 由 `subject + predicate + object` 生成，跨 episode 重复出现时合并来源。
- CLI agent 在 session 模式下会自动写入 semantic memory。

## 验收标准

1. 可以从 episode 提炼 semantic memories。
2. LLM extractor 可以返回结构化 facts。
3. LLM 失败时能回退到确定性提炼。
4. 相同事实跨 episode 会合并 source episode / run。
5. SemanticMemoryStore 可以保存、upsert、search。
6. CLI session run 会写入 `.micode/memory/semantic.json`。
7. 全量测试通过。

## 做了什么

- 新增 `memory/semantic.py`。
- 实现 `SemanticMemory` 和 `SemanticMemoryStore`。
- 实现 LLM 优先的 `semantic_memories_from_episode()`。
- 实现确定性兜底 `deterministic_semantic_memories_from_episode()`。
- CLI agent 在 session 模式下会写入 semantic memory，并记录 ids/path。
- 补充 semantic memory 单元测试和 CLI 集成测试。

## 思考题

Semantic Memory 和 Episodic Memory 的边界是什么？

提示：Episode 是一次经历；Semantic 是从经历中提炼出来、未来可独立复用的事实。
