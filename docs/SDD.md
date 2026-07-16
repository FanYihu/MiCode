# MiniCode SDD

## 为什么做

你已经学过 Python、FastAPI、OpenAI API、Agent Runtime、工具系统和 Guardrails。MiniCode 用来把这些知识合成一个真实的小型 coding agent，让你理解“会聊天”到“能执行工程任务”的差别。

## 做什么

先实现一个 Python 版 MiniCode：

- 能接收一个代码任务
- 能建立一次 Run
- 能记录 Step 和 Event
- 能读取工作区上下文
- 能调用文件工具和命令工具
- 能在危险操作前暂停并等待人工确认
- 能保存执行轨迹，方便复盘和测试

第一阶段只做最小闭环，不接真实大模型：

```text
用户任务 -> 创建 Run -> 记录 Step/Event -> 执行本地工具 -> 输出 trace
```

## 怎么做

采用 SDD 小步开发：

1. 先写文档和验收标准。
2. 再手写最小代码。
3. 用 pytest 验证行为。
4. 最后记录“做了什么”。

## 文档结构

- `docs/README.md`：文档导航。
- `docs/SDD.md`：总路线和阶段记录。
- `docs/days/`：每日学习和开发章节。
- `docs/stage1/`：Stage 1 架构、已完成能力和遗留问题。
- `docs/stage2/`：Stage 2 边界、参考映射、路线和开发规则。

推荐节奏：

- Day 01：核心数据模型 Run / Step / Event
- Day 02：Run 状态机
- Day 03：Trace 记录器
- Day 04：Workspace 读取与搜索
- Day 05：File Tools
- Day 06：Shell Tools
- Day 07：Permission / Human Review
- Day 08：CLI 最小闭环
- Day 09：Mock LLM Agent Loop
- Day 10：综合测试与复盘
- Day 11：LLM Action Provider 抽象
- Day 12：AgentAction 校验
- Day 13：Action Parser
- Day 14：Prompt Builder
- Day 15：Text LLM Adapter
- Day 16：OpenAI Text Client
- Day 17：Provider Factory
- Day 18：CLI Agent Mode
- Day 19：LLM Error Handling 与 Trace
- Day 20：Trace Persistence
- Day 21：Trace Viewer
- Day 22：Trace List
- Day 23：Trace Cleanup
- Day 24：Run Metadata
- Day 25：Trace Metadata Filter
- Day 26：Trace Detail View
- Day 27：Trace Detail Truncation
- Day 28：Trace Markdown Report
- Day 29：Trace Export File
- Day 30：Project Capability Review
- Day 31：Structured File Edit Tool
- Day 32：Tool Registry
- Day 33：Tool Trace Contract
- Day 34：Git Tool
- Day 35：Stage 2 Bridge Review
- Day 36：Skill 数据结构
- Day 37：Skill Loader
- Day 38：Skill Summary Injection
- Day 39：Skill Router
- Day 40：Load Skill Tool
- Day 41：Skill Review
- Day 42：Memory Architecture
- Day 43：Session / Thread Runtime
- Day 44：Event Log / Message History
- Day 45：Working Memory
- Day 46：Context Compression / Session Summary
- Day 47：Episodic Memory
- Day 48：Semantic Memory
- Day 49：Procedural Memory，与 Skill 打通
- Day 50：Memory Graph 数据结构
- Day 51：Entity / Relation Extraction
- Day 52：Temporal Facts / Conflict Resolution
- Day 53：Hybrid Retrieval
- Day 54：Memory Ranking / Injection Policy
- Day 55：Memory Review
- Memory-Skill Bridge：Skill Candidate Pipeline，从经验流程生成候选 Skill，经 Review 后再提升为正式 Skill
- Day 56：Context Layer 设计
- Day 57：Tool Result Summary
- Day 58：Artifact Placeholder
- Day 59：Runtime Stability：幂等写入、Prompt Cache、Decision Freeze
- Day 60：Artifact Read Tool
- Day 61：Token Estimate
- Day 62：Auto Compaction
- Day 63：Context Review
- 补充章节：Hook Runtime 与 Permission 集成
- Day 64：SubAgent Tool Contract
- Day 65：Reviewer SubAgent
- Day 66：Tester SubAgent
- Day 67：Implementer SubAgent
- Day 68：Main Agent Approval
- Day 69：Fork Mode
- Day 70：Multi-Agent Review
- Day 71：Permission Rule 分层
- Day 72：Tool Self-Check
- Day 73：Untrusted Content 标记
- Day 74：Prompt Injection 防御
- Day 75：Human Review Flow
- Day 76：Security Trace Audit
- Day 77：Security Review
- Day 78：MCP Concept Review
- Day 79：MCP Config
- Day 80：Mock MCP Server
- Day 81：MCP Tool Discovery
- Day 82：MCP Tool Call
- Day 83：MCP Permission
- Day 84：MCP Review

## 做了什么

- 2026-05-28：创建 MiniCode 学习项目文档和第一天手写任务，明确从核心 Runtime 数据模型开始。
- 2026-05-29：进入 Day 02 Run 状态机学习，准备为 Run 增加受控状态流转和非法状态保护。
- 2026-05-29：完成 Run 状态机实现，新增非法状态流转异常，并补充状态流转测试。
- 2026-05-29：进入 Day 03 Trace 记录器学习，准备把 Run、Step、Event 组织成可复盘的执行轨迹。
- 2026-05-29：完成内存版 TraceRecorder，支持记录 Step/Event 并导出普通字典格式的 trace。
- 2026-05-29：进入 Day 04 Workspace Context 学习，准备实现目录树、文件读取和文本搜索能力。
- 2026-05-29：完成 Workspace Context，实现工作区路径保护、文件读取、文件列表和关键词搜索。
- 2026-05-29：进入 Day 05 File Tools 学习，准备基于 Workspace 实现安全文件读写和修改预览。
- 2026-05-29：完成 File Tools 基础能力，支持文件读取、写入、存在判断和 diff 修改预览。
- 2026-05-29：进入 Day 06 Shell Tools 学习，准备实现受限工作区内的命令执行、输出捕获和超时控制。
- 2026-05-29：完成 Shell Tools，支持工作区内命令执行、stdout/stderr 捕获和超时结果返回。
- 2026-05-29：进入 Day 07 Permission / Human Review 学习，准备为高风险文件和命令操作增加人工确认规则。
- 2026-05-29：完成 Permission Reviewer，支持文件写入和 shell 命令的允许、审核、拒绝决策。
- 2026-05-29：进入 Day 08 CLI 最小闭环学习，准备把 Runtime、Trace、Workspace 和工具能力串成命令行入口。
- 2026-05-30：完成 CLI 最小闭环，支持 list files 与 run tests，并能输出包含命令结果的 trace JSON。
- 2026-05-30：进入 Day 09 Mock LLM Agent Loop 学习，准备用可测试的假模型驱动观察、行动和结束流程。
- 2026-05-31：完成 MiniCodeAgent 基础 loop，支持 list_files、read_file、run_shell 和 final action 的 trace 闭环。
- 2026-05-31：进入 Day 10 综合测试与复盘，准备梳理第一阶段架构、补齐评估用例并沉淀学习总结。
- 2026-05-31：补充 Agent 综合测试，覆盖读取文件后结束、危险命令拒绝和最大步数失败。
- 2026-05-30：完成 CLI 最小闭环，支持 list files、run tests 和不支持任务的 trace 输出。
- 2026-05-30：进入 Day 09 Mock LLM Agent Loop 学习，准备用可测试的假模型驱动观察、行动、验证循环。
- 2026-05-31：进入 Day 11 LLM Action Provider 学习，准备把“产生下一步动作”的职责从 Agent 执行循环里抽象出来。
- 2026-06-01：完成 Day 11 MockLLM 顺序返回 action 的改造，并进入 Day 12 AgentAction 校验学习。
- 2026-06-01：完成 Day 12 AgentAction 校验接入，并进入 Day 13 Action Parser 学习，准备把 JSON 文本转换成可执行 action。
- 2026-06-01：进入 Day 14 Prompt Builder 学习，准备把任务、工具说明和 observations 组织成稳定的 action 生成提示词。
- 2026-06-01：完成 Day 14 Prompt Builder 基础实现，并进入 Day 15 Text LLM Adapter 学习，准备把 prompt、模型文本和 action parser 串起来。
- 2026-06-01：进入 Day 16 OpenAI Text Client 学习，准备用 Responses API 实现可替换的真实文本客户端。
- 2026-06-01：补充 MimoTextClient，并把模型密钥改为从环境变量读取，保持 TextLLM 的 client.generate(prompt) 统一接口。
- 2026-06-02：重写 Day 17 学习路线，改为使用通用 OpenAI-compatible client，并通过 config.toml 配置 provider、model、base_url 和明文 api_key。
- 2026-06-02：完成 Day 17 配置层修正，新增通用 OpenAICompatibleTextClient、LLMConfig、create_llm_from_config，并保持 config.toml 明文 api_key 读取方式。
- 2026-06-02：恢复项目 Python 3.9 兼容配置，修正 Day 17 文档中的 tomllib/tomli 说明。
- 2026-06-02：检查并修复 VS AI 插件造成的项目损坏，恢复 CLI、FileTools、Permission、ShellTools 和关键测试，确认 50 个测试通过。
- 2026-06-02：进入 Day 18 CLI Agent Mode 学习，准备把 config.toml 驱动的 Agent Loop 接入命令行入口。
- 2026-06-02：按学习项目配置方式恢复 config.toml 明文 api_key 读取逻辑，并同步修正 Day 17/Day 19 文档。
- 2026-06-02：进入 Day 19 LLM Error Handling 与 Trace 学习，准备把模型调用和 action 解析失败记录进 trace。
- 2026-06-02：完成 Day 19 LLM 错误处理，新增 LLMError、模型错误 trace 记录和客户端异常包装，确认 55 个测试通过。
- 2026-06-02：进入 Day 20 Trace Persistence 学习，准备把运行 trace 保存为本地 JSON 文件便于复盘。
- 2026-06-02：完成 Day 20 Trace Persistence，新增 save_trace、CLI --save-trace 和相关测试，确认 59 个测试通过。
- 2026-06-02：进入 Day 21 Trace Viewer 学习，准备从保存的 trace JSON 生成可读复盘摘要。
- 2026-06-02：完成 Day 21 Trace Viewer，新增 load_trace、summarize_trace 和 CLI trace 子命令，确认 63 个测试通过。
- 2026-06-02：进入 Day 22 Trace List 学习，准备在 CLI 中列出最近保存的 trace 文件。
- 2026-06-02：完成 Day 22 Trace List，新增 list_traces 和 CLI traces 子命令，确认 68 个测试通过。
- 2026-06-02：进入 Day 23 Trace Cleanup 学习，准备清理旧 trace 文件，避免运行产物无限增长。
- 2026-06-02：完成 Day 23 Trace Cleanup，新增 cleanup_traces 和 CLI cleanup-traces 子命令，确认 74 个测试通过。
- 2026-06-02：进入 Day 24 Run Metadata 学习，准备把 task、mode、workspace、provider 和 model 写入 run metadata。
- 2026-06-02：完成 Day 24 Run Metadata，新增 run metadata 导出与 fixed/agent 运行上下文记录，确认 75 个测试通过。
- 2026-06-02：进入 Day 25 Trace Metadata Filter 学习，准备按 mode、provider、model 和 task 关键词筛选 trace。
- 2026-06-02：完成 Day 25 Trace Metadata Filter，新增 filter_traces 和 CLI traces 过滤参数，确认 79 个测试通过。
- 2026-06-02：进入 Day 26 Trace Detail View 学习，准备给 trace viewer 增加详细模式。
- 2026-06-02：完成 Day 26 Trace Detail View，新增 format_trace_detail 和 CLI trace --detail，确认 81 个测试通过。
- 2026-06-02：进入 Day 27 Trace Detail Truncation 学习，准备给详细视图增加 event content 截断能力。
- 2026-06-02：完成 Day 27 Trace Detail Truncation，新增 truncate_text 和 trace --detail --max-content，确认 89 个测试通过。
- 2026-06-02：进入 Day 28 Trace Markdown Report 学习，准备把 trace 转成适合复盘笔记的 Markdown 报告。
- 2026-06-02：完成 Day 28 Trace Markdown Report，新增 format_trace_markdown 和 CLI trace --markdown，确认 93 个测试通过。
- 2026-06-02：进入 Day 29 Trace Export File 学习，准备把 Markdown trace 报告保存成文件。
- 2026-06-02：完成 Day 29 Trace Export File，新增 write_text_report 和 CLI trace --markdown --output，确认 95 个测试通过。
- 2026-06-02：进入 Day 30 Project Capability Review 学习，准备系统盘点 MiniCode 已完成能力和后续缺口。
- 2026-06-02：完成 Day 30 Project Capability Review，整理 Stage 1/Stage 2 文档边界，明确 MiniCode 已完成能力、遗留问题和下一阶段优先级。
- 2026-06-02：进入 Day 31 Structured File Edit Tool 学习，准备实现更安全的结构化文件编辑能力。
- 2026-06-02：完成 Stage 2 平滑过渡计划落地，克隆参考项目到 references/MiniCode-Python，并新增 Stage 2 复盘、参考映射、学习路线和开发规则文档。
- 2026-06-02：完成 Day 31 Structured File Edit Tool，新增 replace_text 的插入、删除、单次替换、失败异常和路径边界测试，确认 101 个测试通过。
- 2026-06-02：进入 Day 32 Tool Registry 学习，准备建立轻量工具注册、查找和调用入口。
- 2026-06-03：完成 Day 32 Tool Registry，新增 ToolResult、ToolDefinition、ToolRegistry 和默认工具集合，确认 108 个测试通过。
- 2026-06-03：进入 Day 33 Tool Trace Contract 学习，准备统一工具调用的 trace metadata 契约。
- 2026-06-03：完成 Day 33 Tool Trace Contract，统一 ToolRegistry.call 返回 metadata 顶层字段，工具特有信息进入 details；Agent 工具调用合并为 AgentAction -> ToolRegistry.call -> ToolResult -> Trace + observations，权限检查进入 ToolDefinition.permission_checker，确认 115 个测试通过。
- 2026-06-03：进入 Day 34 Git Tool 学习，准备新增只读 git status 和 git diff 工具。
- 2026-06-03：完成 Day 34 Git Tool，新增 GitTools.status/diff 并注册 git_status、git_diff，确认 119 个测试通过。
- 2026-06-03：进入 Day 35 Stage 2 Bridge Review 学习，准备复盘 Day 31-Day 34 的工具 Runtime 过渡层。
- 2026-06-03：完成 Day 35 Stage 2 Bridge Review，更新 Stage 1/Stage 2 文档边界并确认工具 Runtime 过渡完成，确认 119 个测试通过。
- 2026-06-03：进入 Day 36 Skill 数据结构学习，准备定义 Skill 的最小数据模型和 prompt 格式化能力。
- 2026-06-03：完成 Day 36 Skill 数据结构，新增 Skill 数据模型和 format_skill_for_prompt，确认 123 个测试通过。
- 2026-06-03：进入 Day 37 Skill Loader 学习，准备从项目 .minicode/skills 目录加载 SKILL.md。
- 2026-06-04：完成 Day 37 Skill Loader，新增 SKILL.md description 提取、单文件加载和项目级 discover_project_skills，确认 128 个测试通过。
- 2026-06-04：调整 Skill 主线规划，将 Day 38-Day 41 改为 Summary Injection、Skill Router、Load Skill Tool、Skill Review，避免过早进入 RAG 式粗召回/精排。
- 2026-06-04：进入 Day 38 Skill Summary Injection 学习，准备在小规模 Skill 场景下注入全部 Skill Summary。
- 2026-06-04：完成 Day 38 Skill Summary Injection，新增 Skill Summary prompt 区块格式化且不注入完整 content，确认 132 个测试通过。
- 2026-06-04：进入 Day 39 Skill Router 学习，准备封装小规模全量返回和未来可升级的路由策略入口。
- 2026-06-04：完成 Day 39 Skill Router，新增 route_skills 小规模全量返回和大规模 Router 入口，确认 140 个测试通过。
- 2026-06-04：完成 Day 40 Load Skill Tool，新增 load_project_skill 并把 load_skill 注册进默认 Tool Registry，确认 140 个测试通过。
- 2026-06-04：整理工具目录边界，新增 tools 子包；registry.py 只保留工具契约与统一调用，default.py 负责默认工具装配，file.py、shell.py、git.py、skill.py 分别承载具体工具实现。
- 2026-06-04：完成 Day 41 Skill Review，明确 Skill 不替代 Tool Registry，补充 Skill 闭环文档和 load_skill Agent 集成测试。
- 2026-06-04：重构 Memory 主线规划，将 Day 42-Day 55 升级为 Session、Working Memory、Context Compression、Episodic/Semantic/Procedural Memory、Temporal Graph 和 Hybrid Retrieval。
- 2026-06-04：进入 Day 42 Memory Architecture 学习，先确定真实记忆系统边界，再进入 Session Runtime 实现。
- 2026-06-04：修正 Skill Router 路线，移除手写关键词打分器，改为小规模全量、显式 name 命中和 LLM Router prompt/解析管线。
- 2026-06-04：补全 Skill Router 执行层，新增 LLMSkillRouter 和 route_skills_with_llm，可复用 generate(prompt) client 真实调用路由模型。
- 2026-06-04：把 Skill Router 接入 Agent/CLI，CLI agent 启动时扫描项目 Skill，并用当前 LLM client 在进入 Agent loop 前筛选 Skill Summary。
- 2026-06-04：收敛 Skill 数据契约，只保留 name、description、content、tags，避免路由系统反向绑架 Skill 输入结构。
- 2026-06-04：完成 Skill 分层路由，项目级 Skill 直接注入且同名优先，用户级/外部 Skill 必须经过显式 name 或 LLM Router 筛选，load_skill 支持项目优先和外部兜底。
- 2026-06-04：完善 Skill 二阶段路由，新增 skill_routing.py，支持任务意图识别、tags、When to use / When not to use 和 examples 派生画像，外部 Skill 通过 LLM 精排后再注入 Summary。
- 2026-06-08：完成 Day 43 Session / Thread Runtime，新增 Session 和 SessionStore，CLI agent 支持把 Run 归入指定 session，为后续 Event Log、Working Memory 和长期记忆提供会话边界。
- 2026-06-08：完成 Day 44 Event Log / Message History，新增 SessionMessage 和 SessionMessageStore，把 trace 中的用户任务、工具结果、错误和最终文本沉淀为会话级消息流。
- 2026-06-08：完成 Day 45 Working Memory，新增 WorkingMemory 和 WorkingMemoryStore，基于 SessionMessage 维护当前目标、完成项、待办、约束和最近消息。
- 2026-06-08：完成 Day 46 Context Compression / Session Summary，新增 SessionSummary、ContextCompressor 和紧凑上下文注入，较早消息压缩、最近消息保留原文，并在下一次 Agent run 前恢复会话上下文。
- 2026-06-08：重构 Memory 模块目录，Session、Message History、Working Memory、Context Summary 和 Episodic Memory 统一收进 `minicode/memory/` 包；Session Summary 升级为 LLM 优先的结构化摘要，并保留确定性兜底。
- 2026-06-08：完成 Day 47 Episodic Memory，新增 memory/episodic.py，从 trace 提炼具体经历并写入 .minicode/memory/episodes.json，为后续语义记忆、程序记忆和图谱抽取提供来源。
- 2026-06-08：完成 Day 48 Semantic Memory，新增 memory/semantic.py，从 episode 提炼稳定事实并写入 .minicode/memory/semantic.json，支持 LLM 抽取、确定性兜底、事实 upsert 和轻量搜索。
- 2026-06-08：完成 Day 49 Procedural Memory，新增 memory/procedural.py，从成功 episode 提炼可复用流程并写入 .minicode/memory/procedures.json，支持 LLM 抽取、确定性兜底、procedure upsert 和 Skill 候选转换。
- 2026-06-08：完成 Day 50 Memory Graph 数据结构，新增 memory/graph.py，把 Session、Run、Episode、Semantic Memory 和 Procedural Memory 连成可持久化来源图，并在 CLI session 模式下自动更新 .minicode/memory/graph.json。
- 2026-06-08：完成 Day 51 Entity / Relation Extraction，新增 memory/entity.py，支持 LLM 优先、Semantic 三元组兜底的实体关系抽取，并把规范实体、语义关系和来源边写入 Memory Graph。
- 2026-06-09：完成 Day 52 Temporal Facts / Conflict Resolution，新增 memory/temporal.py，为知识关系增加观测时间、有效时间、基数和状态，并在完整 Memory Graph 上解析跨 run 的替代、共存与冲突。
- 2026-06-09：完成 Day 53 Hybrid Retrieval，新增 memory/retrieval.py，组合关键词、可选 embedding 和图遍历召回长期记忆，默认过滤 superseded 事实，并在 Agent run 前把相关记忆注入 prompt。
- 2026-06-09：完成 Day 54 Memory Ranking / Injection Policy，新增 memory/ranking.py，按相关性、类型、置信度、时效性、Session 和冲突状态精排长期记忆，并用可审计字符预算控制最终 Prompt 注入。
- 2026-06-10：完成 Day 55 Memory Review，新增 memory/review.py 和 memory-review CLI，对 Session、长期记忆、Memory Graph、Temporal Facts 与 Retrieval Injection 做只读体检，输出可审计结构化报告。
- 2026-06-12：完成 Day 56 Context Layer 设计，新增 minicode/context/layers.py，把 Session Context 与 Long-term Memory 统一为可排序、可截断、可审计的上下文层，并在 CLI Agent 模式记录 context_assembly。
- 2026-06-12：完成 Day 57 Tool Result Summary，新增 context/tool_results.py，按工具类型压缩模型 observation 和原生 tool message，同时在 Trace 中保留完整输出及摘要审计字段。
- 2026-06-16：完成 Day 58 Artifact Placeholder，新增 context/artifacts.py，超大工具结果外置保存到 artifact JSON，并在 Trace 与模型 observation 中保留摘要、占位符、路径和 sha256。
- 2026-06-16：完成 Day 59 Runtime Stability，Artifact 写入改为内容 hash 幂等，新增 prompt_cache.py 生成本地 prompt cache 指纹，并在每轮模型决策前写入 Decision Freeze。
- 2026-06-16：完成 Day 60 Artifact Read Tool，新增 tools/artifact.py，把 read_artifact 注册进默认 ToolRegistry，支持按 id/path 安全读取 artifact、默认限长预览和 sha256 校验。
- 2026-06-17：补充 Memory-Skill Bridge 文档，明确经验不能直接自动沉淀为正式 Skill，需经过 Skill Candidate、来源追溯、review 状态和 promote 流程。
- 2026-06-17：实现 Skill Candidate Pipeline，新增 memory/skill_candidate.py、session run 自动生成 draft candidate、skill-candidate-review CLI、promote 写入 SKILL.md，并把 candidate 检查接入 Memory Review。
- 2026-06-17：完成 Day 61 Token Estimate，新增 context/tokens.py，为 Context Layer、CLI assembled context 和 Agent 每轮决策记录稳定的 token 成本估算。
- 2026-06-17：完成 Day 62 Auto Compaction，ContextLayerAssembler 支持 token 预算转有效字符预算，并在 ContextAssembly.compaction 中记录 keep/truncate/omit、成本和节省量。
- 2026-06-17：完成 Day 63 Context Review，新增 context/review.py 和 context-review CLI，对上下文预算、压缩审计、prompt cache、decision freeze 和 artifact 引用做只读体检。
- 2026-06-18：完成 Hook Runtime 与 Permission 解耦，新增 hooks 包和 before/after/error 工具生命周期；PermissionReviewer 通过高优先级 PermissionHook 接入 ToolRegistry，移除 ToolDefinition.permission_checker，并统一固定 CLI 与 Agent 的权限入口。
- 2026-06-18：完成 Day 64 SubAgent Tool Contract，新增 subagents 数据契约、执行接口、策略边界和 run_subagent 工具，并通过默认 Tool Registry 接入主 Agent Trace 与 Hook 生命周期。
- 2026-06-25：完成 Day 65 Reviewer SubAgent，新增只读审查 executor、结构化 finding 和按 role 分发的 SubAgent executor，为后续 Tester / Implementer SubAgent 扩展打好入口。
- 2026-06-25：完成 Day 66 Tester SubAgent，新增受控测试 executor，复用 ShellTools 在 workspace 内执行白名单 pytest 命令，并把 exit code、timeout 和输出摘要写入 SubAgentResult metadata。
- 2026-06-25：完成 Day 67 Implementer SubAgent，新增结构化文件修改 executor，支持 replace_text/write_file operations、allowed_tools 校验、changed_paths 和 diff 审计。
- 2026-06-25：完成 Day 68 Main Agent Approval，新增 SubAgentApprovalHook，在 run_subagent(role=implementer) 执行前审批 operations，避免子 Agent 内部写入绕过主 Agent 权限入口。
- 2026-06-25：完成 Day 69 Fork Mode，新增 ForkedSubAgentExecutor，在临时 workspace 副本中执行子 Agent，并把 fork 路径与隔离信息写入结果 metadata。
- 2026-06-25：完成 Day 70 Multi-Agent Review，新增 MultiAgentReviewPipeline，把 implementer、tester、reviewer 串成可审计审批报告。
- 2026-06-25：完成 Day 71 Permission Rule 分层，重构 PermissionReviewer 为 deny/allow/review 分层规则引擎，并把命中的 rule_name/layer 写入 Hook 与 SubAgent approval metadata。
- 2026-06-26：完成 Day 72 Tool Failure Handling，为 ToolRegistry 增加失败分类、可恢复标记和 retry_hint，让 unknown tool、参数错误、权限拦截、命令失败和工具异常都能进入统一 metadata 契约。
- 2026-06-27：补充完成 Day 72 Tool Self-Check，新增 ToolSelfCheckHook，在工具调用前检查参数契约、调用后检查关键 metadata，并把自检结果写入 trace details。
- 2026-06-09：升级真实模型工具调用协议，为 ToolDefinition 增加 JSON Schema，由 ToolRegistry 生成 OpenAI-compatible tools 字段，并把原生 message.tool_calls 解析成 AgentAction；旧正文 JSON action 保留为测试和兼容 fallback。
- 2026-06-09：完成 OpenAI-compatible Provider 抽象，新增 ProviderCapabilities、ModelTurn 和 ModelToolCall；TextLLM 保存标准 assistant/tool 消息，Agent 将工具结果通过 tool_call_id 回传模型，并支持 reasoning_content、strict schema 和 native tools fallback 配置。
- 2026-06-09：完成原生 tool_calls 批量执行策略，新增 AgentTurn 和 ToolDefinition.parallel_safe；连续只读工具并行执行，有副作用工具按原顺序串行执行，Trace 记录批次信息，结果按 tool_call_id 顺序回传模型。
- 2026-06-09：补充 Python 多线程与 ThreadPoolExecutor 学习笔记，梳理线程、GIL、submit、Future、result、上下文管理器及其在 MiniCode 并行工具执行中的代码映射。
