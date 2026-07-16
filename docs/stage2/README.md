# Stage 2：从基础 Runtime 到可扩展 Coding Agent

## 阶段边界

Stage 2 承接 Stage 1 已经完成的最小 runtime，不推倒重来。

Stage 2 的目标是把 MiniCode 从“能跑通 agent loop”升级为“可扩展、可复盘、可受控的 coding-agent runtime”。

这一阶段从当前 Day 31 继续：

1. Day 31-Day 35：平滑过渡，把现有能力整理成可扩展工具 runtime。
2. Day 36-Day 77：围绕 Skill、Memory、Context、多 Agent、安全审查五条技术主线推进。
3. Day 78-Day 84：在工具、权限和上下文稳定后接入 MCP。

## 当前工具 Runtime 边界

Day 31-Day 34 已经完成基础过渡层：

- `MiniCodeAgent` 不再按工具名写硬编码分支，而是统一走 `ToolRegistry.call(...)`。
- 新增工具只需要注册 `ToolDefinition`，并提供 `handler`。
- Hook Runtime 提供 `before_tool_call`、`after_tool_call`、`tool_error` 生命周期。
- 权限通过高优先级 `PermissionHook` 接入 `before_tool_call`，ToolDefinition 不再保存权限字段。
- `ToolResult` 是 Agent、Trace 和 observations 之间的统一结果对象。
- 工具 trace metadata 顶层字段统一为 `tool`、`args`、`ok`、`result_summary`、`error`、`details`。
- 默认工具集合包含 `list_files`、`read_file`、`replace_text`、`write_file`、`run_shell`、`git_status`、`git_diff`、`load_skill`、`read_artifact`。

这意味着后续 Skill、Memory、Context、SubAgent 和 MCP 都应该复用 Tool Registry；权限、审计和参数治理等横切逻辑复用 Hook Runtime。

## 当前 Skill 边界

Day 36-Day 41 已经完成最小 Skill 闭环：

```text
discover_project_skills
  -> route_skills
  -> format_skill_summaries_for_prompt
  -> AgentAction(tool="load_skill")
  -> ToolRegistry.call(...)
  -> ToolResult
  -> Trace + observations
```

Skill 是“模型应该如何完成一类任务”的流程说明，不是真正执行动作的入口。真正执行仍然交给 Tool Registry 中注册的 Tool。

## 参考项目

参考仓库固定放在：

```text
references/MiniCode-Python
```

参考规则：

- 只读学习，不复制源码。
- 每章只吸收一个概念，重写成适合当前 MiniCode 的小版本。
- 每章文档必须写“参考项目学到了什么”。

## 当前 MiniCode 到参考项目的映射

| 当前模块 | 参考模块 | 学习重点 |
| --- | --- | --- |
| `agent.py` | `minicode/agent_loop.py` | Agent loop、任务推进、工具结果处理、错误恢复 |
| `tools/file.py` | `minicode/tools/edit_file.py`、`modify_file.py`、`patch_file.py` | 结构化编辑、patch、安全修改 |
| `tools/shell.py` | `minicode/tools/run_command.py`、`test_runner.py` | 命令执行、测试运行、输出摘要 |
| `tools/registry.py`、`tools/default.py` | `minicode/tools/*`、`tool_registry` 类似组织 | 工具契约、默认工具装配、统一调用 |
| `hooks/` | `minicode/hooks.py` | 生命周期事件、注册派发、权限和审计扩展点 |
| `permissions.py` | `minicode/permissions.py`、`safe_execution.py` | 分层权限、危险命令识别、人工确认 |
| `persistence.py` | `minicode/history.py`、`session.py`、`memory.py` | trace、session、memory 的持久化边界 |
| `cli.py` | `minicode/main.py`、`cli_commands.py`、`headless.py` | CLI 子命令、headless 入口 |
| `trace.py` | `agent_metrics.py`、`decision_audit.py` | 执行审计、指标与决策记录 |

## Stage 2 技术主线

### Tool Registry 与工具契约

承接现有 `list_files`、`read_file`、`run_shell` action 分发逻辑，并已经完成从硬编码分支到 Registry 的过渡。

目标：

- 轻量工具注册表已经建立。
- 工具 trace metadata 已统一。
- 下一步要支撑 Skill、MCP、SubAgent 在同一入口上扩展。

参考：

```text
minicode/tooling.py
minicode/tools/*
minicode/hooks.py
```

### Skill 能力体系

目标：

- 把原子 Tool、高层 Skill、Skill 目录分层组织。
- 根据 Skill 数量分级选择路由策略：项目级直接注入，外部 Skill 显式 name 命中或二阶段 LLM Router 筛选，大规模再启用 Embedding / Graph Index。
- 项目级 Skill 优先级最高，直接注入 Summary，不参与筛选。
- 用户级 / 外部 Skill 必须参与筛选，先显式 name 命中，再交给“任务意图识别 + 路由画像精排”。
- 路由画像从 `tags`、`SKILL.md` 的 `When to use / When not to use` 和 `examples/` 目录派生，不增加 Skill 本体字段。
- 中规模以后通过 Skill Router 选择外部候选 Summary，并按需调用 `load_skill` 加载完整 Skill。
- `load_skill` 项目级同名优先，外部 Skill 兜底。
- Skill Router 不手写关键词打分；显式点名用 name 直接命中，其余交给 LLM Router 或后续 Embedding / Graph Router。
- Skill 只负责能力组织和 prompt 注入，不替代 Tool Registry。
- Skill 不直接从单次经验自动生成，必须经过 Skill Candidate 和 Review，避免把临时经验污染成长期能力。

参考：

```text
minicode/skills.py
minicode/skill_routing.py
minicode/tools/skill.py
```

### 自进化记忆沉淀

目标：

- 先建立 Session / Thread Runtime，让多轮会话和事件流成为记忆来源。
- Session 是多次 Run 的组织容器，当前保存在 `.minicode/sessions/{session_id}.json`。
- Message History 是从 trace 提取的会话级消息流，当前保存在 `.minicode/sessions/{session_id}.messages.json`。
- Working Memory 表达当前会话状态，当前保存在 `.minicode/sessions/{session_id}.working_memory.json`。
- Context Compression 优先用当前模型生成结构化 Session Summary，失败时确定性兜底，结果保存在 `.minicode/sessions/{session_id}.summary.json`。
- Agent session 模式会把 Working Memory、Session Summary 和 Recent Messages 合成紧凑上下文注入 prompt。
- Episodic Memory 从一次 Run / trace 提炼具体经历，当前保存在 `.minicode/memory/episodes.json`。
- Semantic Memory 从 Episode 提炼稳定事实，当前保存在 `.minicode/memory/semantic.json`。
- Procedural Memory 从成功 Episode 提炼可复用流程，当前保存在 `.minicode/memory/procedures.json`。
- Procedure 可以转换成 Skill Candidate，但不会自动写入项目 Skill。
- Procedural Memory 要能和 Skill 体系打通，让成功流程沉淀成可复用能力。
- Skill Candidate 是 Memory 和 Skill 之间的缓冲层，用于承接“有复用价值但还没稳定到能进入 prompt 的经验”。
- Skill Candidate 默认保存到 `.minicode/skill-candidates/{candidate_id}.json`，只在人工或 review 流程确认后才提升为 `.minicode/skills/{name}/SKILL.md`。
- Memory Graph 把 Session、Run、Episode、Semantic Memory 和 Procedural Memory 连成来源图，当前保存在 `.minicode/memory/graph.json`。
- Entity / Relation Extraction 从 Episode 和 Semantic Memory 中识别规范实体、别名和语义关系，并把来源可追溯的 entity 节点与关系边写入 Memory Graph。
- Temporal Facts 为关系记录观测时间、有效时间和状态；单值事实按时间与置信度解析为 active、superseded 或 conflicting，多值事实允许并存。
- Hybrid Retrieval 已组合 keyword、可选 embedding 和 graph traversal；Agent run 前会召回相关长期记忆，默认排除 superseded 事实并标记 conflicting 事实。
- Memory Ranking 根据召回相关性、记忆类型、置信度、时效性、Session 归属和冲突状态精排，并用字符预算控制最终注入 Agent Prompt 的内容。
- Memory Review 提供只读体检，检查 Session、长期记忆、Graph、Temporal Facts 和 Retrieval Injection 是否断链。
- 建立 Temporal Knowledge Graph，表达实体、关系、时间、来源和事实更新。
- 检索采用 hybrid retrieval：keyword + vector-ready 表示 + graph traversal + ranking。
- 建立“执行-会话记录-压缩-反思-抽取-图更新-冲突解决-召回注入”闭环。

#### Experience -> Skill Candidate -> Skill

这条链路解决一个边界问题：经验不一定立刻是 Skill。

```text
Trace / Episode
  -> Procedural Memory
  -> Skill Candidate
  -> Candidate Review
  -> Project Skill / User Skill
```

四层含义不同：

- `Episode`：一次具体经历，记录“那次发生了什么”。
- `ProceduralMemory`：从成功经历中提炼出的流程，记录“以后遇到类似问题可以怎么做”。
- `SkillCandidate`：接近 Skill 的候选稿，记录“这条流程可能值得沉淀成能力，但还需要确认”。
- `Skill`：正式进入 Skill Loader、Router 和 Prompt 的能力说明。

候选层的核心规则：

- 不从失败 run 自动生成候选，除非后续有明确“失败排查流程”的章节。
- 不因为一次成功就自动提升为 Skill；单次经验最多生成 candidate。
- 候选要带来源：`source_procedure_ids`、`source_episode_ids`、`source_run_ids`。
- 候选要带状态：`draft`、`approved`、`rejected`、`promoted`。
- 候选要保留 review 结论：为什么保留、为什么拒绝、是否需要合并到已有 Skill。
- 提升后的 Skill 仍然遵守四字段契约：`name`、`description`、`content`、`tags`。
- 如果候选和已有 Skill 同名或相似，默认生成 review issue，不直接覆盖。

建议数据结构：

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

当前实现：

- `memory/skill_candidate.py`：候选数据结构、存储、从 Procedure 生成候选。
- `skill-candidate-review` CLI：列出候选、显示来源、批准、拒绝、合并建议。
- `promote_skill_candidate()`：把 approved candidate 写入 `.minicode/skills/{name}/SKILL.md`。
- Memory Review 扩展检查 candidate 是否丢失来源、是否和已有 Skill 冲突。

参考：

```text
minicode/memory/session.py
minicode/memory/working.py
minicode/memory/context.py
minicode/memory/episodic.py
minicode/memory/entity.py
minicode/memory/graph.py
minicode/memory/temporal.py
minicode/memory/retrieval.py
minicode/memory/ranking.py
minicode/memory/review.py
minicode/memory/skill_candidate.py
```

### 分层上下文压缩

目标：

- 通过 Context Layer 管理不同来源的上下文，当前已支持 session 和 long-term memory 两层的优先级、字符预算和截断审计。
- Tool Result Summary 区分完整 Trace 输出和模型 observation 摘要，并按工具类型保留关键首尾内容。
- Artifact Placeholder 已将超大完整工具结果外置到 `.minicode/artifacts`，Prompt 和 Trace 只保留摘要、占位符和可验证引用。
- Runtime Stability 已为 artifact 写入增加内容 hash 幂等性，为 assembled context 增加 prompt cache key，并在每轮模型决策前记录 Decision Freeze。
- Artifact Read Tool 支持通过 `read_artifact` 按 id/path 安全读回外置结果，并用默认限长预览防止上下文再次膨胀。
- Token Estimate 已为 Context Layer、assembled context 和每轮 Agent 决策记录稳定的 token 成本估算。
- Auto Compaction 已让 Context Layer 根据字符/token 预算自动记录 keep、truncate、omit 和节省量。
- Context Review 已提供只读体检入口，检查预算、压缩审计、prompt cache、decision freeze 和 artifact 引用是否断链。
- 用摘要预览、artifact 占位、按需检索治理长上下文。
- 提升长会话稳定性，降低 Token 成本。

参考：

```text
minicode/context_manager.py
minicode/context_compactor.py
minicode/layered_context.py
minicode/tooling.py
minicode/context/layers.py
minicode/context/tool_results.py
minicode/context/artifacts.py
minicode/context/prompt_cache.py
minicode/context/decision.py
minicode/context/tokens.py
minicode/context/review.py
minicode/tools/artifact.py
```

### 中心化多 Agent 协作

目标：

- 主 Agent 统一规划、审批和质量控制。
- 子 Agent 作为受控 Tool Call 执行，不移交控制权。
- 通过路径边界、权限约束和最小结果传递保证安全。
- SubAgent Tool Contract 已定义 `SubAgentTask`、`SubAgentResult`、`SubAgentExecutor` 和 `SubAgentPolicy`。
- `run_subagent` 只有在提供 executor 时才进入默认 Tool Registry，并完整复用 Hook、ToolResult、Trace 和 observations 链路。
- Reviewer SubAgent 已能作为只读 executor 运行，输出结构化 finding；`RoleBasedSubAgentExecutor` 负责按 role 分发，后续 Tester 和 Implementer 复用同一入口。
- Tester SubAgent 已能在 workspace 内运行白名单 pytest 命令，并把测试通过/失败、exit code、timeout 和输出摘要写入 Trace metadata。
- Implementer SubAgent 已能执行结构化 `replace_text` / `write_file` operations，写入 changed_paths、operation 列表和 diff 摘要。
- Main Agent Approval 已通过 `SubAgentApprovalHook` 接入工具生命周期，在 implementer 写入前审批 operations。
- Fork Mode 已支持在临时 workspace 副本中执行子 Agent，默认不污染原工作区。
- Multi-Agent Review 已提供 implementer -> tester -> reviewer 的最小审批流水线，并输出 `MultiAgentReviewReport`。

参考：

```text
minicode/subagents/models.py
minicode/subagents/tool.py
minicode/agent_router.py
minicode/task_object.py
minicode/task_tracker.py
minicode/pipeline_engine.py
```

### 权限与安全审查

目标：

- 扩展现有 `PermissionDecision.ALLOW / REVIEW / DENY`。
- 构建规则过滤、工具自检、prompt injection 防御、人工确认和 trace 审计链路。
- Permission Rule 分层已完成，当前按 `deny -> allow -> review` 执行，并把命中的 rule/layer 写入 trace metadata。
- Tool Failure Handling 已统一失败分类、可恢复标记和 retry_hint。
- Tool Self-Check 已接入 before/after Hook，检查参数契约和关键结果 metadata。

参考：

```text
minicode/permissions.py
minicode/safe_execution.py
minicode/file_review.py
```

### MCP

MCP 放在 Tool Registry、Permission、Context 基础稳定之后接入。

目标：

- 本地 stdio mock server。
- MCP tool discovery。
- MCP tool call。
- MCP permission 和 trace。

参考：

```text
minicode/mcp.py
```

## Stage 2 文档

- `roadmap.md`：Day 31-Day 84 章节路线。
- `rules.md`：后续每章必须遵守的开发规则。
