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
- Day 42：Memory 数据结构
- Day 43：Trace Reflection
- Day 44：Memory Store
- Day 45：Memory Index
- Day 46：Memory Recall
- Day 47：Memory Prompt Injection
- Day 48：Memory Review
- Day 49：Context Layer 设计
- Day 50：Tool Result Summary
- Day 51：Artifact Placeholder
- Day 52：Artifact Read Tool
- Day 53：Token Estimate
- Day 54：Auto Compaction
- Day 55：Context Review
- Day 56：SubAgent Tool Contract
- Day 57：Reviewer SubAgent
- Day 58：Tester SubAgent
- Day 59：Implementer SubAgent
- Day 60：Main Agent Approval
- Day 61：Fork Mode
- Day 62：Multi-Agent Review
- Day 63：Permission Rule 分层
- Day 64：Tool Self-Check
- Day 65：Untrusted Content 标记
- Day 66：Prompt Injection 防御
- Day 67：Human Review Flow
- Day 68：Security Trace Audit
- Day 69：Security Review
- Day 70：MCP Concept Review
- Day 71：MCP Config
- Day 72：Mock MCP Server
- Day 73：MCP Tool Discovery
- Day 74：MCP Tool Call
- Day 75：MCP Permission
- Day 76：MCP Review

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
- 2026-06-04：完成 Day 39 Skill Router，新增 route_skills 小规模全量返回和大规模关键词兜底选择，确认 140 个测试通过。
- 2026-06-04：完成 Day 40 Load Skill Tool，新增 load_project_skill 并把 load_skill 注册进默认 Tool Registry，确认 140 个测试通过。
- 2026-06-04：进入 Day 41 Skill Review 学习，准备复盘 Skill 主线和 Tool Registry 合流边界。
