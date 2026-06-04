# Stage 2 Roadmap

## 平滑过渡

### Day 31：Structured File Edit Tool

承接现有 `file_tools.py`，补结构化编辑能力。

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

- Day 42：Memory 数据结构。
- Day 43：Trace Reflection。
- Day 44：Memory Store。
- Day 45：Memory Index。
- Day 46：Memory Recall。
- Day 47：Memory Prompt Injection。
- Day 48：Memory Review。

## 分层上下文压缩

- Day 49：Context Layer 设计。
- Day 50：Tool Result Summary。
- Day 51：Artifact Placeholder。
- Day 52：Artifact Read Tool。
- Day 53：Token Estimate。
- Day 54：Auto Compaction。
- Day 55：Context Review。

## 中心化多 Agent 协作

- Day 56：SubAgent Tool Contract。
- Day 57：Reviewer SubAgent。
- Day 58：Tester SubAgent。
- Day 59：Implementer SubAgent。
- Day 60：Main Agent Approval。
- Day 61：Fork Mode。
- Day 62：Multi-Agent Review。

## 权限与安全审查

- Day 63：Permission Rule 分层。
- Day 64：Tool Self-Check。
- Day 65：Untrusted Content 标记。
- Day 66：Prompt Injection 防御。
- Day 67：Human Review Flow。
- Day 68：Security Trace Audit。
- Day 69：Security Review。

## MCP Track

- Day 70：MCP Concept Review。
- Day 71：MCP Config。
- Day 72：Mock MCP Server。
- Day 73：MCP Tool Discovery。
- Day 74：MCP Tool Call。
- Day 75：MCP Permission。
- Day 76：MCP Review。
