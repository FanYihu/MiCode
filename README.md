# MiniCode 学习项目

这是一个本人用于手写 Coding Agent 的学习项目。

模仿 Claude Code 架构。

目标不是一次性写出完整工具，而是在引导下逐步实现：

- Run / Step / Event 状态模型
- CLI 任务入口
- 文件读取、搜索、补丁应用工具
- 命令执行工具
- 人工确认与危险操作拦截
- 执行 trace 与测试

## 当前完成状态

MiniCode 目前已经从最小 Agent Loop，推进到可扩展的 Coding Agent Runtime：

- 基础 Runtime：Run / Step / Event、Trace、CLI、Trace 持久化与查看。
- 工具系统：文件工具、Shell 工具、Git 只读工具、统一 `ToolRegistry`、工具 metadata 契约。
- LLM 接入：OpenAI-compatible client、`config.toml` 配置、原生 tool calls、批量工具调用。
- Skill 系统：项目级 / 用户级 Skill 加载、路由、按需加载和候选沉淀。
- 长短期 Memory：Session、Working Memory、Summary、Episodic / Semantic / Procedural Memory、Memory Graph、Temporal Facts、Hybrid Retrieval、Ranking Injection、Review。
- Context 系统：Context Layer、Tool Result Summary、Artifact Placeholder、Artifact Read Tool、Prompt Cache、Decision Freeze。

## Skill 系统

Skill 部分已经形成完整闭环：

```text
项目级 / 用户级 Skill
  -> Skill Loader
  -> Skill Summary Injection
  -> Skill Router
  -> load_skill Tool
  -> ToolRegistry.call(...)
  -> Trace + observations
```

当前 Skill 契约保持简单：

```python
Skill(name, description, content, tags)
```

已完成能力：

- 项目级 Skill：读取 `.minicode/skills/*/SKILL.md`。
- 用户级 Skill：读取 `~/.minicode/skills/*/SKILL.md`。
- 项目级 Skill 优先级最高，直接注入 Summary，不参与筛选。
- 用户级 / 外部 Skill 通过显式 name 命中或 LLM Router 筛选。
- 路由画像从 `tags`、`When to use / When not to use` 和 `examples/` 派生，不污染 Skill 四字段契约。
- `load_skill` 已注册进默认 Tool Registry，模型需要完整 Skill 时再按需读取。
- Procedural Memory 可以生成 Skill Candidate，但不会直接污染正式 Skill。
- `skill-candidate-review` 支持 generate / list / approve / reject / promote。

Skill 的定位是“告诉模型怎么做一类任务”，不是新的工具分发系统。真正执行动作仍然走 `ToolRegistry`。

## 长短期 Memory 系统

Memory 部分已经完成从短期会话到长期记忆的主线：

```text
Session
  -> Message History
  -> Working Memory
  -> Session Summary
  -> Episodic Memory
  -> Semantic Memory
  -> Procedural Memory
  -> Skill Candidate
  -> Memory Graph
  -> Temporal Facts
  -> Hybrid Retrieval
  -> Ranking / Injection
  -> Memory Review
```

短期记忆：

- `Session`：组织多次 Run，保存会话边界。
- `SessionMessage`：从 Trace 提取用户任务、工具结果、错误和最终回答。
- `WorkingMemory`：维护当前目标、完成项、待办、约束和最近消息。
- `SessionSummary`：压缩较早消息，保留最近消息原文。
- Agent session 模式会在下一次运行前恢复紧凑上下文。

长期记忆：

- `EpisodicMemory`：记录一次具体经历。
- `SemanticMemory`：从经历中提炼稳定事实。
- `ProceduralMemory`：从成功经历中提炼可复用流程。
- `SkillCandidate`：把流程经验变成候选 Skill，经 review 后才可提升。
- `MemoryGraph`：连接 Session、Run、Episode、Semantic、Procedure、实体和关系。
- `Temporal Facts`：为事实关系记录时间、来源、active / superseded / conflicting 状态。
- `Hybrid Retrieval`：组合 keyword、vector-ready 表示和 graph traversal。
- `MemoryRankingPolicy`：按相关性、置信度、时效性、Session 归属和冲突状态精排。
- `memory-review`：只读体检 Session、Memory、Graph、Temporal 和 Retrieval 链路。

Memory 的定位是“让 Agent 记住发生过什么、事实是什么、以后怎么做”。正式 Skill 只接收经过 review 的稳定流程。

## 学习方式

1. 先读 `docs/SDD.md`，明确为什么做、做什么、怎么做。
2. 每次只完成一个很小的模块。
3. 你先手写代码，我再帮你 review、纠错、补测试。
4. 每次修改后，在 `docs/SDD.md` 的“做了什么”里补一句自然语言记录。

## 主要文档

- `docs/SDD.md`：总路线和每次变更记录。
- `docs/stage1/README.md`：第一阶段基础闭环。
- `docs/stage2/README.md`：第二阶段 Skill、Memory、Context、多 Agent、安全和 MCP 路线。
- `docs/stage2/roadmap.md`：Day 31 之后的学习章节安排。
