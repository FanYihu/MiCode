# Day 39：Skill Router

## 今日目标

定义可升级的 Skill Router 策略入口，并把外部 Skill 路由升级成“任务意图识别 + 路由画像精排”。

Day 38 处理小规模情况：Skill 少时直接注入所有 Summary。Day 39 要把这个策略封装成 Router，让后续可以平滑升级到 LLM Router 或 Embedding Router。

## 为什么做

Skill 数量会逐步增长。

Router 不应该一开始就做复杂检索，但应该提前有一个清晰入口：

```text
task + skills -> selected skills
```

这样 Day 38 的小规模策略、未来中规模 LLM Router、大规模 Embedding Router 都能走同一个接口。

## 建议策略

- 项目级 Skill：优先级最高，直接注入 Summary，不参与筛选。
- 用户级 / 外部 Skill：必须参与筛选。
- 外部 Skill 显式点名 name：直接命中。
- 外部 Skill 其他情况：交给二阶段 LLM Router 筛选。
- 任务意图识别：用当前 LLM 从用户任务中提取 goal、task_type、keywords、tags。
- 元信息标签：直接使用 Skill 的 `tags`。
- 适用边界：从 `SKILL.md` 中解析 `## When to use` 和 `## When not to use`。
- 示例：读取 Skill 目录下的 `examples/` 子文件夹，作为路由判断材料。
- `load_skill` 加载完整内容时，项目级同名 Skill 优先，其次才查外部 Skill。
- 项目级数量较少时仍然全部返回；数量治理后续交给 Context Compression。
- 外部 Skill 小于等于 120 个时直接作为候选交给 LLM 精排；超过 120 个后再接 Embedding / Graph Router。
- `deprecated` 之类状态字段后续再加。

## 建议接口

Skill 数据契约保持简单：

```python
Skill(name, description, content, tags)
```

```python
def route_skills(task: str, skills: list[Skill], limit: int = 20) -> list[Skill]:
    ...
```

路由层派生结构不写回 Skill 本体：

```python
TaskIntent(goal, task_type, keywords, tags)
SkillRoutingProfile(name, description, tags, when_to_use, when_not_to_use, examples)
```

## 验收标准

1. 项目级 Skill 全部返回。
2. 项目级 Skill 不参与筛选，始终优先注入 Summary。
3. 用户级 / 外部 Skill 必须经过显式 name 或 LLM Router 筛选。
4. `load_skill` 项目级同名优先，其次加载外部 Skill。
5. `limit` 控制外部筛选数量。
6. 路由不修改 Skill 本体结构。
7. LLM Router 精排 prompt 可以使用 tags、When to use、When not to use 和 examples。
8. CLI agent 入口会发现项目 Skill 和用户级 Skill，并把真实 LLM client 接给外部 Skill Router。
9. 全量测试通过。

## 做了什么

- 新增 `route_skills(task, skills, limit=20)`。
- Skill 数量小于等于 20 时，直接返回全部候选并尊重 `limit`。
- 项目级 Skill 拆成 `project_skills`，进入 Agent 前直接保留，不参与筛选。
- 用户级 / 外部 Skill 拆成 `skills`，通过 `route_external_skills()` 参与筛选。
- 外部 Skill 没有 Router 且未显式点名时不注入，避免低优先级 Skill 污染 prompt。
- `load_skill` 支持项目级优先、外部 Skill 兜底。
- `limit <= 0` 或空 Skill 列表时返回空列表。
- Skill 契约收敛为 name、description、content、tags。
- 新增 `find_explicit_skills()`，只处理 name 明确命中，不做相关性猜测。
- 新增 `skill_routing.py`，把任务意图、路由画像、examples 读取和二阶段 LLM 精排从 `skills.py` 拆出。
- 新增 `TaskIntent`，用于表达用户任务的 goal、task_type、keywords、tags。
- 新增 `SkillRoutingProfile`，从 Skill 四字段、`SKILL.md` 边界段落和 `examples/` 目录派生路由材料。
- 新增 `build_task_intent_prompt()` 和 `parse_task_intent_response()`，用当前 LLM 做任务意图识别。
- 新增 `build_skill_rerank_prompt()`，让 LLM 基于任务意图和候选 Skill 画像精排。
- 新增 `parse_skill_router_response()` 和 `select_skills_by_name()`，把 LLM 返回的名称转成 Skill 列表。
- 新增 `TwoStageSkillRouter`，接收带 `generate(prompt)` 的 client，完成“意图识别 -> 候选召回 -> 精排”。
- `LLMSkillRouter` 保留为兼容旧名称，当前实现指向二阶段 Router。
- 新增 `route_skills_with_llm()`，先走确定性策略，必要时调用 `LLMSkillRouter`。
- `MicodeAgent` 支持注入 `skills` 和 `skill_router`，在 Agent loop 前完成 Skill 选择，并把选中 Summary 注入 action prompt。
- CLI `agent` 入口会扫描项目级 `.micode/skills` 和用户级 `~/.micode/skills`，并用当前 LLM 的 `client.generate(prompt)` 作为外部 Skill Router client。
- 补充测试覆盖小规模全量返回、显式点名、任务意图解析、When 边界解析、examples 读取、Router JSON 解析、按名称选择、Router client 调用、Agent 注入、CLI 入口集成、项目优先合并和外部 Skill 加载。

## 思考题

为什么 Router 不直接把 Skill 注入 prompt？

提示：Router 只负责选择候选，Prompt Injection 负责组织模型输入。
