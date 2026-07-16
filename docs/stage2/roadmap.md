# Stage 2 Roadmap

## 平滑过渡

### Day 31：Structured File Edit Tool

承接现有 `tools/file.py`，补结构化编辑能力。

- 按旧文本替换新文本。
- 默认只替换第一个匹配项。
- 返回 diff。
- 沿用 Workspace 路径保护。

### Day 32：Tool Registry

承接现有 Agent 工具分发逻辑。

- 参考 `tooling.py`。
- 建立轻量工具注册表。
- 把 `list_files`、`read_file`、`run_shell` 注册为工具。
- 为 Skill、MCP、SubAgent 提供统一入口。

### Day 33：Tool Trace Contract

承接现有 trace 系统。

- 统一工具 metadata：`tool`、`args`、`ok`、`result_summary`、`error`、`details`。
- 工具特有字段统一放入 `details`，不摊平到顶层。
- 后续所有工具复用这个契约。

### Day 34：Git Tool

承接 shell 工具，但独立出只读 git 工具。

- 支持 `git status`。
- 支持 `git diff`。
- 先不做 commit。

### Day 35：Stage 2 Bridge Review

复盘 Day 31-Day 34。

- 更新 Stage 1/Stage 2 边界文档。
- 确认当前项目已经从基础 agent loop 过渡到可扩展工具 runtime。

## Skill 能力体系

- Day 36：Skill 数据结构。
- Day 37：Skill Loader。
- Day 38：Skill Summary Injection。
- Day 39：Skill Router。
- Day 40：Load Skill Tool。
- Day 41：Skill Review。

## 自进化记忆沉淀

- Day 42：Memory Architecture。
- Day 43：Session / Thread Runtime。
- Day 44：Event Log / Message History。
- Day 45：Working Memory。
- Day 46：Context Compression / Session Summary。
- Day 47：Episodic Memory。
- Day 48：Semantic Memory。
- Day 49：Procedural Memory，与 Skill 打通。
- Day 50：Memory Graph 数据结构。
- Day 51：Entity / Relation Extraction。
- Day 52：Temporal Facts / Conflict Resolution。
- Day 53：Hybrid Retrieval，keyword + vector-ready + graph traversal。
- Day 54：Memory Ranking / Injection Policy。
- Day 55：Memory Review。
- Memory-Skill Bridge 补充章节：Skill Candidate Pipeline，从 Procedural Memory 生成候选 Skill，经 Review 后再提升为正式 Skill。

## 分层上下文压缩

- Day 56：Context Layer 设计。
- Day 57：Tool Result Summary。
- Day 58：Artifact Placeholder。
- Day 59：Runtime Stability：幂等写入、Prompt Cache、Decision Freeze。
- Day 60：Artifact Read Tool。
- Day 61：Token Estimate。
- Day 62：Auto Compaction。
- Day 63：Context Review。

## 中心化多 Agent 协作

- 补充章节：Hook Runtime 与 Permission 集成，为 SubAgent、Security 和 MCP 提供统一生命周期扩展点。

- Day 64：SubAgent Tool Contract。
- Day 65：Reviewer SubAgent。
- Day 66：Tester SubAgent。
- Day 67：Implementer SubAgent。
- Day 68：Main Agent Approval。
- Day 69：Fork Mode。
- Day 70：Multi-Agent Review。

## 权限与安全审查

- Day 71：Permission Rule 分层。
- Day 72：Tool Self-Check。
- Day 73：Untrusted Content 标记。
- Day 74：Prompt Injection 防御。
- Day 75：Human Review Flow。
- Day 76：Security Trace Audit。
- Day 77：Security Review。

## MCP Track

- Day 78：MCP Concept Review。
- Day 79：MCP Config。
- Day 80：Mock MCP Server。
- Day 81：MCP Tool Discovery。
- Day 82：MCP Tool Call。
- Day 83：MCP Permission。
- Day 84：MCP Review。
