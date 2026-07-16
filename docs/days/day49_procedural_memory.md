# Day 49：Procedural Memory，与 Skill 打通

## 今日目标

从成功经历中提炼可复用流程，并建立它和 Skill 的转换边界。

Episodic Memory 记录“那次发生了什么”，Semantic Memory 记录“事实是什么”，Procedural Memory 记录“以后怎么做”。

## 为什么做

Agent 不能只记住事件和事实，还应该从成功经历中沉淀方法。

比如：

```text
Episode：某次修改 CLI 参数并跑通测试。
Procedure：修改 CLI 行为时，先读入口，再改参数解析，再补测试，最后运行 pytest。
```

这类流程后续可以变成 Skill Candidate，让模型在类似任务中复用之前，先经过 review。

这里不能直接自动生成正式 Skill。因为一次成功经验可能只是项目特例，也可能只是临时修复步骤；如果直接写进 Skill 目录，后续 Skill Router 会把它当成稳定能力注入 prompt，反而污染模型决策。

## 做什么

新增 `ProceduralMemory`：

```python
ProceduralMemory(
    id,
    name,
    description,
    steps,
    when_to_use,
    when_not_to_use,
    tags,
    source_episode_ids,
    source_run_ids,
    metadata,
)
```

新增 `ProceduralMemoryStore`：

- `load_all()`：读取所有流程记忆。
- `save_all()`：保存所有流程记忆。
- `upsert_many()`：按稳定 procedure id 合并来源和步骤。
- `search()`：轻量关键词搜索。

补充设计 `SkillCandidate`：

```python
SkillCandidate(
    id,
    name,
    description,
    content,
    tags,
    status,
    confidence,
    source_procedure_ids,
    source_episode_ids,
    source_run_ids,
    review_notes,
    created_at,
    updated_at,
)
```

候选状态：

- `draft`：刚从 Procedure 生成，还没有确认。
- `approved`：review 通过，可以提升为正式 Skill。
- `rejected`：不适合沉淀为 Skill，保留来源但不再推荐。
- `promoted`：已经写入正式 Skill 目录。

## 怎么做

- Procedure 保存为 `.micode/memory/procedures.json`。
- Skill Candidate 保存为 `.micode/skill-candidates/{candidate_id}.json`。
- 只有成功 episode 才会提炼 procedure。
- `procedural_memories_from_episode()` 优先调用当前 LLM client 抽取可复用步骤。
- LLM 失败或返回空时，用确定性兜底。
- `procedural_memory_to_skill()` 可以把 Procedure 转成 Skill 候选对象，但不能直接写入正式 Skill 目录。
- Skill 本体仍然只有 `name`、`description`、`content`、`tags`。

候选生成规则：

- 单次成功经验最多生成 `draft` candidate。
- Candidate 必须记录来源 procedure / episode / run，后续 review 可以追溯。
- Candidate 的 `content` 应该写成可执行流程，而不是复述某次 trace。
- Candidate 不允许默认进入 `format_skill_summaries_for_prompt()`。
- Candidate 不允许被 `load_skill` 当成正式 Skill 加载。
- Candidate 提升为 Skill 时，才写入 `.micode/skills/{name}/SKILL.md`。

推荐提升流程：

```text
ProceduralMemory
  -> SkillCandidate(status=draft)
  -> skill-candidate-review
  -> approved
  -> promote_skill_candidate()
  -> .micode/skills/{name}/SKILL.md
  -> Skill Loader / Router / load_skill
```

## 验收标准

1. 成功 episode 可以提炼 procedural memory。
2. 失败 episode 不提炼 procedure。
3. LLM extractor 可以返回结构化 procedure。
4. LLM 失败时能回退到确定性提炼。
5. Procedure 可以转换成 Skill Candidate，且不破坏 Skill 四字段契约。
6. ProceduralMemoryStore 可以保存、upsert、search。
7. CLI session run 会写入 `.micode/memory/procedures.json`。
8. Candidate 不会自动进入正式 Skill Loader。
9. Candidate 提升为 Skill 前必须经过 review 状态。
10. 全量测试通过。

## 做了什么

- 新增 `memory/procedural.py`。
- 实现 `ProceduralMemory` 和 `ProceduralMemoryStore`。
- 实现 LLM 优先的 `procedural_memories_from_episode()`。
- 实现确定性兜底 `deterministic_procedural_memories_from_episode()`。
- 实现 `procedural_memory_to_skill()`，把流程记忆转成 Skill 候选。
- CLI agent 在 session 模式下会写入 procedural memory，并记录 ids/path。
- 补充 procedural memory 单元测试和 CLI 集成测试。

## Skill Candidate Pipeline

`procedural_memory_to_skill()` 是兼容旧测试的最小桥接函数。当前正式闭环使用 `Skill Candidate Pipeline`：

- 已定义 `SkillCandidate` 数据结构和 store。
- Session Agent run 写入 ProceduralMemory 后会生成 draft candidate。
- 已增加 `skill-candidate-review` 命令。
- 支持 approve / reject / promote。
- promote 时生成正式 `SKILL.md`。
- Memory Review 检查 candidate 来源、状态和 promoted Skill 文件。

## 思考题

为什么 Procedure 不直接自动写成项目 Skill？

提示：Procedure 是经验候选，Skill 是会进入模型上下文的操作说明，中间应该有 Skill Candidate 和 review 流程确认。
