# 补充章节：Hook Runtime 与 Permission 集成

## 为什么做

原来的权限检查保存在 `ToolDefinition.permission_checker` 中，工具定义同时承担工具能力和权限策略，后续增加审计、参数改写、SubAgent 边界或 MCP 权限时会继续膨胀。

Hook Runtime 把横切逻辑放进统一生命周期，Tool 只描述参数和执行逻辑，Permission 作为 `before_tool_call` Hook 独立运行。

## 做什么

- 建立同步 Hook 注册和派发系统。
- 支持 `before_tool_call`、`after_tool_call`、`tool_error`。
- before Hook 支持参数改写和阻断。
- Hook 支持优先级、注销、统计和执行 metadata。
- before Hook 异常时 fail-closed，避免权限 Hook 失效后继续执行工具。
- PermissionHook 审核 `run_shell`、`write_file` 和 `replace_text`。
- 删除 `ToolDefinition.permission_checker`。

## 怎么做

```text
AgentAction
  -> ToolRegistry.call(tool, args)
  -> HookManager.emit(before_tool_call)
       -> PermissionHook
       -> 其他参数改写/审计 Hook
  -> blocked ? ToolResult(error) : ToolDefinition.handler(args)
  -> success: HookManager.emit(after_tool_call)
  -> exception: HookManager.emit(tool_error)
  -> 统一 ToolResult metadata
  -> Trace + observations
```

默认优先级：

```text
PermissionHook(priority=1000)
  -> 其他 before Hook
  -> Tool handler
```

危险调用被 PermissionHook 阻断后，低优先级 Hook 和 Tool handler 都不会继续运行。

## 参考项目学到了什么

参考项目用事件枚举、HookContext、注册管理器和注销函数表达生命周期扩展点。

当前 MiniCode 沿用这个思想，但按自己的同步 Tool Registry 做了收敛：

- 当前只实现工具生命周期，不提前加入 Agent/Session 全部事件。
- Hook 可以返回结构化 `continue` / `block`，而不只是执行旁路回调。
- `before_tool_call` Hook 异常默认阻断，满足权限 fail-closed。
- Hook 执行记录进入 `ToolResult.metadata.details.hooks`，继续复用现有 Trace 契约。

## 做了什么

- 新增 `minicode/hooks/` 包。
- 新增 Hook 事件、上下文、结果、注册、优先级、注销和统计。
- `ToolRegistry.call()` 接入 before/after/error 生命周期。
- PermissionReviewer 通过 PermissionHook 接入默认 Registry。
- shell/file 工具不再直接依赖权限模块。
- 固定 CLI 与 Agent 都通过 Tool Registry 使用权限 Hook。
- 增加 Hook 生命周期、fail-closed、权限阻断和文件写入测试。

## 验收标准

- ToolDefinition 不包含权限字段。
- 危险 shell 命令仍会被阻断。
- `.env` 等敏感文件写入会被阻断。
- 普通文件写入正常执行。
- 自定义 HookManager 不会绕过或重复注册 PermissionHook。
- Hook 参数改写、after、error、注销和统计均有测试。
