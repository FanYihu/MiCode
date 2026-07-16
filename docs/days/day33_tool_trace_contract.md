# Day 33：Tool Trace Contract

## 今日目标

统一工具调用写入 trace 的 metadata 格式。

Day 32 已经有了轻量 `ToolRegistry`，但工具结果现在只是 `ok/output/metadata`。Day 33 要先定义一个稳定的 trace 契约，让后续 Agent、Skill、MCP、SubAgent 调工具时都能记录一致的信息。

## 为什么做

Trace 是 Micode 的可观测性核心。

如果每个工具随意写 metadata，后面会很难做：

- 工具调用审计
- 失败统计
- 权限分析
- memory 提炼
- context 压缩

所以需要先统一工具层 metadata 的基本字段。

## 承接已有能力

本章承接：

- Day 32 的 `ToolResult` 和 `ToolRegistry`。
- 现有 `TraceRecorder` 的 step/event 结构。
- 现有 CLI 和 Agent 里已经使用的 tool metadata。

## 参考项目学到了什么

参考：

```text
references/MiniCode-Python/minicode/tooling.py
references/MiniCode-Python/minicode/decision_audit.py
references/MiniCode-Python/minicode/agent_metrics.py
```

参考项目的重点不是只看工具输出，而是把工具调用变成可审计事件：

- 工具名要稳定。
- 输入参数要可追踪。
- 成功失败要明确。
- 大输出要能摘要。
- 错误要变成结构化信息。

本章只做最小契约，不做复杂指标系统。

## 建议字段

工具 trace metadata 先统一成：

```python
{
    "tool": "read_file",
    "args": {"path": "README.md"},
    "ok": True,
    "result_summary": "hello...",
    "error": "",
}
```

Shell 工具可以额外保留：

```python
{
    "details": {
        "exit_code": 0,
        "timed_out": False,
    }
}
```

## 要修改的文件

```text
micode/src/micode/tool_registry.py
micode/tests/test_tool_registry.py
docs/SDD.md
```

这一章同步改 `agent.py`，把旧的硬编码工具分发合并到 Tool Registry。

## 验收标准

1. `ToolRegistry.call` 返回的 metadata 至少包含 `tool`、`args`、`ok`、`result_summary`、`error`。
2. 未知工具也符合同一 metadata 契约。
3. 默认工具集合不在 metadata 顶层摊平工具特有字段；工具细节统一放进 `details`。
4. result summary 不输出无限长内容。
5. 工具权限检查统一进入工具生命周期；当前实现已升级为 `PermissionHook -> before_tool_call`，Agent 不为具体工具写权限分支。
6. 全量测试通过。

## 做了什么

- 新增统一工具 metadata 构造逻辑。
- `ToolRegistry.call` 会给所有工具结果补齐 `tool`、`args`、`ok`、`result_summary`、`error`。
- 未知工具也返回相同 metadata 契约。
- 默认工具的扩展字段统一放进 `details`，例如 `path`、`command`、`exit_code`、`timed_out`。
- `result_summary` 对长输出做截断，完整内容仍保留在 `ToolResult.output`。
- `MicodeAgent` 改为走 `AgentAction -> ToolRegistry.call(...) -> ToolResult -> Trace + observations`。
- 权限最初在 ToolDefinition 注册层完成，现已解耦为高优先级 PermissionHook，并复用同一 ToolResult metadata 契约。
- `TextLLM` 的 prompt 工具说明改为由 Registry 注入，新增工具注册后可以进入模型提示。
- 补充测试覆盖成功工具、失败工具、未知工具、默认工具、长输出摘要和 Agent 自定义工具调用。

## 思考题

为什么 `result_summary` 不直接等于完整 `output`？

提示：完整输出可能很长，trace metadata 应该适合筛选和复盘，完整内容可以放在 event content 里。
