# MiniCode 架构说明

MiniCode 第一阶段主要完成了一个最小 Coding Agent 骨架。

核心是三个 Runtime 数据结构：`Run`、`Step`、`Event`。它们分别表示一次任务、任务中的一个步骤、步骤中产生的可观察事件。`TraceRecorder` 负责把这些对象组织成完整执行轨迹，方便调试、测试和后续展示。

## 模块职责

- `models.py`：定义 `Run`、`Step`、`Event`、状态枚举和 Run 状态机。
- `trace.py`：记录 Agent 执行过程，把 Step 和 Event 导出为 trace dict。
- `workspace.py`：管理工作区上下文，提供文件列表、文本读取、关键词搜索和路径边界保护。
- `file_tools.py`：提供文件读取、写入、存在判断和 diff 预览。
- `shell_tools.py`：在工作区内执行 shell 命令，返回结构化命令结果。
- `permissions.py`：判断文件写入和命令执行是允许、需要人工审核，还是直接拒绝。
- `cli.py`：命令行入口，把用户任务转换成一次 Runtime 执行。
- `agent.py`：Agent 主循环，根据 action 调用工具、记录观察，并在 final action 时结束任务。

## 执行流程

第一阶段有两条主要执行链路。

CLI 固定任务流程：

```text
用户命令
  -> cli.run_task()
  -> 创建 Run / TraceRecorder / Workspace
  -> 执行 list files 或 run tests
  -> 记录 Step 和 Event
  -> Run completed 或 failed
  -> 输出 trace JSON
```

Agent Loop 流程：

```text
用户任务
  -> MiniCodeAgent.run()
  -> LLM/MockLLM 产生 AgentAction
  -> 根据 action.tool 调用 Workspace / FileTools / ShellTools
  -> 工具结果写入 observations
  -> 工具调用写入 Trace
  -> final action 结束任务
```

## Trace 结构

Trace 是 MiniCode 的可观测性基础，主要包含三部分：

```text
trace
  run: 任务 id、状态、创建时间、更新时间
  steps: 每一步的 id、run_id、类型、状态、metadata
  events: 每个事件的 id、run_id、step_id、类型、内容、metadata
```

`steps` 和 `events` 分开存放，通过 `step_id` 关联。这样后续无论是写入数据库、展示前端页面，还是做测试评估，都比较清晰。

## 后续扩展点

1. 接入真实 LLM：优先替换 `MockLLM.next_action()`，让模型生成 `AgentAction`。
2. 增加 Skills：把常见开发任务封装成可复用能力，例如读项目结构、修测试、生成文档。
3. 接入 MCP：把外部工具按标准协议暴露给 Agent。
4. 增加 Hooks：在工具调用前后插入日志、权限审核、格式化、测试等流程。
5. 持久化 Trace：把 Run、Step、Event 保存到数据库，支持恢复、查询和复盘。
6. 更强权限系统：对删除、安装依赖、网络访问、批量修改等操作进行人工确认。

