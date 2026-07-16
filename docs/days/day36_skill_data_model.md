# Day 36：Skill 数据结构

## 今日目标

新增 Skill 的基础数据结构。

Day 35 已经确认工具 Runtime 过渡完成。Day 36 开始进入 Skill 能力体系，但第一步不做目录扫描、不做召回，只先定义“Skill 是什么”。

## 为什么做

Skill 不是一个新工具，也不是替代 Tool Registry 的分发系统。

Skill 更像“高层能力说明”：

- 什么时候适用。
- 能解决什么问题。
- 需要哪些工具配合。
- 要注入给模型的说明是什么。

先把数据结构定义清楚，后续 Loader、路由选择、Prompt Injection 和完整 Skill 加载才有稳定基础。

## Skill 路由策略分级

Skill 系统需要预留分层路由能力，但不应该一开始就做成复杂的向量检索系统。

Skill 不是 RAG 文档库，它通常是少量高价值操作流程。路由策略要根据 Skill 数量逐步升级，在实现复杂度、Token 成本和召回准确率之间做平衡。

### 小规模：不启用检索

当 Skill 数量小于等于 20 个时，不需要额外检索层。

此时可以直接把所有 Skill Summary 注入给模型，由模型根据用户任务判断是否需要调用 `load_skill` 加载完整内容。

```text
User Task
  -> PromptBuilder 注入全部 Skill Summary
  -> LLM 判断是否需要 Skill
  -> 如有需要，调用 load_skill
```

这种方式实现最简单，也适合早期学习阶段。因为 Skill 数量较少，全部摘要带来的 Token 成本和注意力干扰都在可接受范围内。

### 中规模：使用 LLM Router 筛选候选

当 Skill 数量在 20 到 120 个之间时，不建议继续把所有 Skill Summary 都直接注入主模型。

这一阶段可以使用一个轻量的 `LLM Router` 作为候选筛选层。Runtime 将 Skill Summary 分批发送给便宜模型或小模型，让它根据用户任务挑选可能相关的候选 Skill。

```text
User Task
  -> Skill Summary 分批
  -> LLM Router 选择候选 Skill
  -> 合并候选结果
  -> 注入 Top-K Skill Summary 给主模型
  -> 主模型按需调用 load_skill
```

这个方案不需要向量数据库，也不需要维护 embedding index，工程复杂度比向量检索更低。同时它比纯规则匹配更适合自然语言任务，因为用户描述通常不稳定，很难只靠关键词、标签或规则准确判断意图。

metadata 仍然可以作为辅助信号：

- `status: deprecated` 的 Skill 不主动注入。
- 用户明确点名的 Skill 直接命中。
- 当前项目语言与 Skill scope 不匹配时降权。
- 用户手写 Skill 优先级高于自动生成 Skill。

也就是说，`LLM Router` 负责语义判断，metadata 负责过滤和调权。

### 大规模：启用 Embedding Index

当 Skill 数量超过 120 个后，可以考虑启用 embedding index。

此时 Skill 数量已经较多，继续依赖 `LLM Router` 分批判断会增加模型调用次数和延迟。Embedding 检索可以先快速召回一批语义相近的 Skill，再交给 reranker 或 `LLM Router` 做精排。

```text
User Task
  -> 生成 query embedding
  -> 从 Skill embedding index 中召回 Top-N
  -> metadata 过滤和调权
  -> rerank 精排
  -> 注入 Top-K Skill Summary
  -> 主模型按需调用 load_skill
```

Embedding Index 是规模扩大后的优化手段，不是 Skill 系统的起点。只有当 Skill 数量增长到一定程度，且 `LLM Router` 的成本、延迟或准确率成为瓶颈时，才有必要引入向量化入库、索引更新和相似度检索。

Micode 当前阶段只需要先保证数据结构支持后续扩展，不需要在 Day 36 直接实现路由器。

## 承接已有能力

本章承接：

- Day 32-Day 35 的 Tool Registry。
- `TextLLM` 的工具说明注入能力。
- `docs/stage2/README.md` 中的 Skill 主线规划。

## 参考项目学到了什么

参考：

```text
references/MiniCode-Python/minicode/skills.py
references/MiniCode-Python/minicode/tools/load_skill.py
```

参考项目把 Skill 拆成：

- `SkillSummary`：只包含列表和召回需要的轻量信息。
- `LoadedSkill`：在 summary 基础上多出完整内容。

本章先实现适合当前 Micode 的最小版本。

## 建议接口

新增文件：

```text
micode/src/micode/skills.py
```

建议结构：

```python
@dataclass
class Skill:
    name: str
    description: str
    content: str
    tags: list[str]
    tools: list[str]
```

可以再加一个 helper：

```python
def format_skill_for_prompt(skill: Skill) -> str:
    ...
```

## 要修改的文件

```text
micode/src/micode/skills.py
micode/tests/test_skills.py
docs/SDD.md
```

## 验收标准

1. 可以创建 Skill 数据对象。
2. `tags` 和 `tools` 默认是空列表，且不同实例之间不共享。
3. `format_skill_for_prompt` 能输出适合注入 prompt 的文本。
4. 全量测试通过。

## 做了什么

- 新增 `skills.py`，定义最小 `Skill` 数据结构。
- `Skill` 包含 `name`、`description`、`content`、`tags`、`tools`。
- `tags` 和 `tools` 使用 `default_factory=list`，避免多个 Skill 实例共享列表。
- 新增 `format_skill_for_prompt(skill)`，把 Skill 格式化为适合注入 prompt 的文本。
- 补充 `test_skills.py`，覆盖创建对象、默认列表隔离、prompt 格式化和空可选列表。

## 思考题

为什么 Skill 需要记录 tools？

提示：Skill 是高层能力说明，但真正执行仍然要落到 Tool Registry 中的工具。
