# Stage 1：最小 Coding Agent Runtime

## 阶段边界

Stage 1 的目标是把 Micode 从零搭成一个可测试、可复盘、可接真实模型的最小 coding-agent runtime。

这一阶段关注“基础闭环”：

```text
用户任务 -> Run -> Step/Event -> 工具调用 -> Trace -> CLI 输出/保存
```

Stage 1 不追求复杂 Skill、Memory、MCP、多 Agent 或上下文压缩；这些放到 Stage 2。

## 架构骨架

Micode 的基础 Runtime 由三个核心对象组成：

- `Run`：一次完整任务，负责状态流转。
- `Step`：任务中的一个动作，例如模型决策、工具调用、最终回答。
- `Event`：动作产生的可观察记录，例如文本、工具结果、错误。

`TraceRecorder` 负责把 Run、Step、Event 组织成可序列化 trace。这个 trace 是后续调试、测试、复盘、记忆沉淀和报告导出的基础。

## 主要模块

- `models.py`：定义 Runtime 数据模型、状态枚举和 Run 状态机。
- `trace.py`：记录 Step/Event，并导出 trace dict。
- `workspace.py`：管理工作区路径边界，支持文件列表、读取和搜索。
- `permissions.py`：对文件写入和 shell 命令做 allow/review/deny 审核。
- `agent.py`：AgentAction、action parser、prompt builder、LLM adapter 和 MicodeAgent loop。
- `cli.py`：命令行入口，支持固定任务、agent 模式和 trace 管理。
- `persistence.py`：trace 保存、加载、查看、过滤、清理和 Markdown 导出。
- `tools/registry.py`：统一工具注册、调用、权限检查和工具 trace metadata 契约。
- `tools/default.py`：装配默认工具集合。
- `tools/file.py`：提供文件读取、写入、存在判断、diff 预览和基础结构化编辑。
- `tools/git.py`：提供只读 Git 状态和 diff 观察能力。
- `tools/shell.py`：在工作区执行命令，捕获 stdout、stderr、exit code 和超时。
- `tools/skill.py`：把项目 Skill 加载能力适配成可注册工具。

## 已完成能力

### Runtime 与 Trace

- Run 状态机，限制非法状态流转。
- Step/Event 记录和导出。
- trace JSON 保存和读取。
- trace 摘要、详细视图、内容截断。
- trace 列表、清理、metadata 筛选。
- Markdown 复盘报告和 `.md` 文件导出。

### Workspace 与工具

- 工作区路径保护。
- 文件列表、读取、写入、存在判断。
- diff 预览。
- shell 命令执行、输出捕获、超时记录。
- 结构化文本替换，默认只替换第一处匹配并返回 diff。
- Tool Registry 统一注册 `list_files`、`read_file`、`replace_text`、`run_shell`、`git_status`、`git_diff`。
- 工具调用 metadata 顶层字段统一，工具特有信息进入 `details`。
- 工具权限检查已从 ToolDefinition 解耦，由 `PermissionHook` 订阅 `before_tool_call` 生命周期。
- 只读 Git 状态和 diff 观察能力。

### Agent Loop

- `AgentAction` 定义模型下一步动作。
- action 校验和 JSON parser。
- prompt builder。
- `MockLLM` 用于稳定测试。
- `TextLLM` 接入通用文本 client。
- OpenAI-compatible client，通过 `config.toml` 配置 provider、model、base_url 和明文 `api_key`。
- Agent 通过 `ToolRegistry.call(...)` 调用工具，不再为每个具体工具写硬编码分支。
- Agent 支持 Registry 中注册的工具，以及 `final`。
- 模型调用、解析、校验失败会写入 trace，并标记 Run failed。

### CLI

- `fixed`：运行固定任务，如 `list files` 和 `run tests`。
- `agent`：通过 `config.toml` 启动真实模型驱动的 Agent。
- `trace`：查看保存的 trace 摘要。
- `trace --detail`：查看详细 trace。
- `trace --detail --max-content N`：控制详细视图内容长度。
- `trace --markdown`：输出 Markdown 复盘报告。
- `trace --markdown --output report.md`：导出 Markdown 文件。
- `traces`：列出 trace。
- `traces --mode/--provider/--model/--task-contains`：筛选 trace。
- `cleanup-traces`：清理旧 trace。

## Stage 1 复盘

Stage 1 最重要的收获是理解了 coding agent 的 Harness Engineering：

- Agent 不是一次性生成答案，而是观察、决定动作、执行工具、记录结果，再继续下一步。
- Trace 是可观测性的核心，没有 trace 就无法复盘 Agent 为什么失败或为什么成功。
- 工具能力必须受工作区和权限系统约束，不能让模型直接无限制操作本机。

## Stage 1 遗留问题

- Agent 工具分发已进入 Tool Registry，但还没有更丰富的工具 schema 和参数验证。
- 文件编辑已有精确文本替换，还没有 patch、多文件编辑和人工确认闭环。
- trace metadata 已有工具契约，但还没有更完整的审计、统计和安全分析。
- Git 已有只读 status/diff，还没有 commit、branch、log 和变更复盘工具。
- 没有 Skill、Memory、Context 压缩、SubAgent、MCP。
- 权限系统已接入工具生命周期，但仍缺少工具自检、prompt injection 防御和人工确认闭环。

这些遗留问题就是 Stage 2 的入口。
