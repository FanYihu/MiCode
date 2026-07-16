# Day 51：Entity / Relation Extraction

## 为什么做

Day50 的 Memory Graph 已经能表达“某条记忆来自哪个 episode”，但还不理解记忆正文里的对象。

例如：

```text
MiniCode uses pytest
```

真正的知识图谱需要识别：

- `MiniCode` 是项目实体。
- `pytest` 是库实体。
- 两者之间存在 `uses` 关系。

## 做什么

新增实体关系抽取层：

- `KnowledgeEntity`：规范实体、类型、别名、来源 memory。
- `KnowledgeRelation`：实体间关系、置信度、来源 memory 和 episode。
- `EntityRelationExtraction`：一次抽取结果。
- LLM 优先抽取实体和关系。
- LLM 失败时把 Semantic Memory 的三元组确定性转成图。
- 把实体节点、语义关系边和 `supported_by_memory` 来源边写入 Memory Graph。

## 怎么做

完整流程：

```text
Episode + Semantic Memories
  -> extract_entities_and_relations(...)
  -> KnowledgeEntity[]
  -> KnowledgeRelation[]
  -> build_memory_graph(...)
  -> entity nodes + semantic relation edges
  -> graph.json
```

LLM 返回：

```json
{
  "entities": [
    {"name": "MiniCode", "type": "project"},
    {"name": "pytest", "type": "library"}
  ],
  "relations": [
    {
      "source": "MiniCode",
      "predicate": "uses",
      "target": "pytest",
      "confidence": 0.9,
      "source_memory_ids": ["semantic:minicode-uses-pytest"]
    }
  ]
}
```

图中会形成：

```text
entity:minicode --uses--> entity:pytest
entity:minicode --supported_by_memory--> semantic:minicode-uses-pytest
entity:pytest --supported_by_memory--> semantic:minicode-uses-pytest
```

## 关键边界

- 实体 id 按规范名称稳定生成，同名实体可以跨 episode 合并。
- LLM 只能引用已有 Semantic Memory id，不能伪造来源。
- API key、凭证和瞬时原始输出不进入实体图。
- Day51 只建立实体关系，事实的有效时间和冲突状态留给 Day52。

## 参考项目学到了什么

参考项目强调结构化状态和可追溯来源。MiniCode 在此基础上把长期记忆拆成“事实节点、实体节点、关系边、来源边”，避免把知识图谱做成无法审计的黑盒文本集合。

## 验收标准

- 能从 Semantic Memory 三元组确定性生成实体关系。
- 能解析 LLM 返回的实体、类型、别名和关系。
- LLM 返回非法内容时不会阻断记忆流程。
- 同名实体得到稳定 id。
- 关系边包含 confidence、source memory 和 source episode。
- CLI session run 后，`graph.json` 中包含 entity 节点和语义关系边。

## 做了什么

新增 `memory/entity.py`，实现 LLM 优先、确定性兜底的实体关系抽取。

扩展 Memory Graph 和 CLI 记忆管线，把实体节点、语义关系和来源关系自动写入 `.minicode/memory/graph.json`。
