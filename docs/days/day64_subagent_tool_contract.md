# Day 64：SubAgent Tool Contract

## 为什么做

多 Agent 不能从“再启动一个 Agent”开始，否则控制权、权限、上下文和 Trace 很快就会分裂。

MiniCode 先把 SubAgent 定义成主 Agent 可以调用的受控 Tool：主 Agent 负责授权和验收，SubAgent 只执行一个有边界的子任务。

## 做什么

新增 SubAgent 基础契约：

- `SubAgentTask`：角色、目标、最小上下文、工具白名单、路径范围、步数上限和主 Run 引用。
- `SubAgentResult`：状态、摘要、证据、artifact、修改路径和 metadata。
- `SubAgentExecutor`：具体 SubAgent runtime 必须实现的执行接口。
- `SubAgentPolicy`：由主 Agent 配置角色、工具、路径和步数边界。
- `run_subagent`：把 executor 接进 Tool Registry 的统一工具。

## 怎么做

完整流转：

```text
Main Agent
  -> AgentAction(tool="run_subagent")
  -> ToolRegistry.call(...)
  -> BEFORE_TOOL_CALL Hooks
  -> SubAgentPolicy 校验角色、限制工具/路径/步数
  -> SubAgentExecutor.execute(SubAgentTask)
  -> SubAgentResult 契约校验
  -> ToolResult(summary + structured metadata)
  -> AFTER_TOOL_CALL Hooks
  -> Main Trace + observations
  -> Main Agent 决定下一步
```

关键控制规则：

- 模型不能通过参数传入 `allowed_tools` 或 `allowed_paths`。
- `max_steps` 可以请求，但不能超过 policy 上限。
- SubAgent 结果必须匹配原 task id 和 role。
- 主 Agent observation 只接收摘要；证据、artifact 和修改路径进入 metadata。
- SubAgent 工具默认串行，因为后续 Implementer 可能产生写操作。
- 未提供 executor 时，不注册 `run_subagent`，避免暴露不能执行的假工具。

## 做了什么

- 新增 `minicode/subagents/models.py`。
- 新增 `minicode/subagents/tool.py`。
- 默认 Tool Registry 支持可选注册 `run_subagent`。
- `MiniCodeAgent` 支持注入 SubAgent executor 和 policy。
- 子任务自动记录当前主 Run id。
- 增加契约、限权、错误结果、可选注册和完整 Agent 调用测试。

## 学习重点

SubAgent 不是新的控制中心，而是一个受控执行单元。

```text
主 Agent：规划、授权、验收、继续决策
SubAgent：在限定工具、路径和步数内执行一个目标
Tool Registry + Hooks：统一权限、调用和审计
```
