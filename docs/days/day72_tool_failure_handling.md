# Day 72：Tool Failure Handling

## 为什么做

工具调用失败不能只返回一段自然语言错误。

Agent 需要知道失败属于哪一类、能不能恢复、下一轮应该怎么修正，否则很容易重复调用同一个错误工具，或者把权限拦截当成普通失败绕过去。

## 做什么

在 `ToolRegistry` 中增加统一失败分类：

- `failure_class`：失败类别。
- `recoverable`：是否建议模型修正后重试。
- `retry_hint`：下一轮可执行的修正提示。

当前覆盖：

- `unknown_tool`
- `invalid_args`
- `file_not_found`
- `permission_denied`
- `policy_check_failed`
- `timeout`
- `command_failed`
- `tool_exception`
- `failed_result`

## 怎么做

```text
ToolRegistry.call(...)
  -> unknown tool / hook blocked / handler exception / ok=False result
  -> _classify_failure(...)
  -> ToolResult.metadata.details
  -> Trace + observation
```

异常类工具失败会走 `_classify_exception()`，例如缺少参数导致 `KeyError` 会被归类成 `invalid_args`。

命令类失败会根据 `exit_code` / `timed_out` 归类成 `command_failed` 或 `timeout`。

权限类失败会根据 Hook metadata 中的 `decision=deny/review` 归类成 `permission_denied`。

## 做了什么

- 新增 `ToolFailure`。
- `ToolRegistry` 对失败结果统一补充 `failure_class`、`recoverable`、`retry_hint`。
- unknown tool 结果附带 `available_tools`。
- handler 异常结果附带 `exception_type`。
- 补充 unknown tool、缺参数异常、普通 failed result、shell exit code 失败和权限拦截测试。

## 学习重点

好的 Agent Runtime 不追求工具永远不失败，而是让失败可处理：

```text
可分类
可追踪
可恢复
不可恢复时安全停止
```
