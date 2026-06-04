# Stage 2：从基础 Runtime 到可扩展 Coding Agent

## 阶段边界

Stage 2 承接 Stage 1 已经完成的最小 runtime，不推倒重来。

Stage 2 的目标是把 MiniCode 从“能跑通 agent loop”升级为“可扩展、可复盘、可受控的 coding-agent runtime”。

这一阶段从当前 Day 31 继续：

1. Day 31-Day 35：平滑过渡，把现有能力整理成可扩展工具 runtime。
2. Day 36-Day 69：围绕 Skill、Memory、Context、多 Agent、安全审查五条技术主线推进。
3. Day 70-Day 76：在工具、权限和上下文稳定后接入 MCP。

## 当前工具 Runtime 边界

Day 31-Day 34 已经完成基础过渡层：

- `MiniCodeAgent` 不再按工具名写硬编码分支，而是统一走 `ToolRegistry.call(...)`。
- 新增工具只需要注册 `ToolDefinition`，并提供 `handler`。
- 工具权限检查通过 `ToolDefinition.permission_checker` 进入工具生命周期。
- `ToolResult` 是 Agent、Trace 和 observations 之间的统一结果对象。
- 工具 trace metadata 顶层字段统一为 `tool`、`args`、`ok`、`result_summary`、`error`、`details`。
- 默认工具集合包含 `list_files`、`read_file`、`replace_text`、`run_shell`、`git_status`、`git_diff`。

这意味着后续 Skill、Memory、Context、SubAgent 和 MCP 都应该复用 Tool Registry，而不是重新发明一套工具分发。

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
| `file_tools.py` | `minicode/tools/edit_file.py`、`modify_file.py`、`patch_file.py` | 结构化编辑、patch、安全修改 |
| `shell_tools.py` | `minicode/tools/run_command.py`、`test_runner.py` | 命令执行、测试运行、输出摘要 |
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
```

### Skill 能力体系

目标：

- 把原子 Tool、高层 Skill、Skill 目录分层组织。
- 根据 Skill 数量分级选择路由策略：小规模全量摘要注入，中规模使用 LLM Router 筛选候选，大规模再启用 Embedding Index。
- 小规模阶段直接注入全部 Skill Summary，避免过早进入 RAG 式粗召回和精排。
- 中规模以后通过 Skill Router 选择候选 Summary，并按需调用 `load_skill` 加载完整 Skill。
- Skill 只负责能力组织和 prompt 注入，不替代 Tool Registry。

参考：

```text
minicode/skills.py
minicode/tools/load_skill.py
```

### 自进化记忆沉淀

目标：

- 从 trace 中提炼程序性经验、情景记忆和用户画像。
- 建立“执行-反思-提炼-分类存储-索引更新-按需复用”闭环。

参考：

```text
minicode/memory.py
minicode/memory_pipeline.py
minicode/memory_injector.py
minicode/agent_reflection.py
```

### 分层上下文压缩

目标：

- 将大工具结果外置化。
- 用摘要预览、artifact 占位、按需检索治理长上下文。
- 提升长会话稳定性，降低 Token 成本。

参考：

```text
minicode/context_manager.py
minicode/context_compactor.py
minicode/layered_context.py
minicode/tooling.py
```

### 中心化多 Agent 协作

目标：

- 主 Agent 统一规划、审批和质量控制。
- 子 Agent 作为受控 Tool Call 执行，不移交控制权。
- 通过路径边界、权限约束和最小结果传递保证安全。

参考：

```text
minicode/agent_router.py
minicode/task_object.py
minicode/task_tracker.py
minicode/pipeline_engine.py
```

### 权限与安全审查

目标：

- 扩展现有 `PermissionDecision.ALLOW / REVIEW / DENY`。
- 构建规则过滤、工具自检、prompt injection 防御、人工确认和 trace 审计链路。

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

- `roadmap.md`：Day 31-Day 76 章节路线。
- `rules.md`：后续每章必须遵守的开发规则。
