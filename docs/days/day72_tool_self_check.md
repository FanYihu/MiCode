# Day 72：Tool Self-Check

## 为什么做

权限规则能回答“能不能执行”，但工具还需要回答“这次调用和返回是否符合工具契约”。

Day72 增加工具自检，让工具在执行前检查参数，在执行后检查结果 metadata。这样错误能更早暴露，Trace 也能记录工具是否返回了可审计信息。

## 做什么

新增 `ToolSelfCheckHook`：

- BEFORE 阶段检查 required 参数。
- BEFORE 阶段检查 `additionalProperties=False` 时是否传入额外参数。
- BEFORE 阶段检查 `path`、`command`、`name`、`old` 等关键文本字段是否为空。
- AFTER 阶段检查关键工具是否返回必要 metadata。

当前检查的结果 metadata：

- `read_file`：`path`
- `replace_text` / `write_file`：`path`
- `run_shell`：`command`、`exit_code`、`timed_out`
- `git_status` / `git_diff`：`command`、`exit_code`
- `load_skill`：`name`

## 怎么做

```text
ToolRegistry.call(...)
  -> BEFORE_TOOL_CALL
  -> PermissionHook
  -> ToolSelfCheckHook
  -> SubAgentApprovalHook
  -> tool.handler(...)
  -> AFTER_TOOL_CALL
  -> ToolSelfCheckHook
  -> ToolResult.metadata.details
```

执行前自检失败会阻断工具：

```text
ToolResult(ok=False, error="tool_self_check_failed")
```

执行后自检不会改工具成败，只把审计结果写入：

```text
metadata.details.tool_self_check_result
```

## 做了什么

- 新增 `hooks/tool_self_check.py`。
- 默认 Hook Manager 注册 before/after 自检。
- `hooks/__init__.py` 暴露 `ToolSelfCheckHook`。
- 补充缺必填参数、额外参数、缺结果 metadata 的测试。
- 更新旧的 ToolRegistry 测试以检查自检 metadata。

## 学习重点

权限和自检不是一回事：

```text
PermissionHook：这个动作是否允许？
ToolSelfCheckHook：这个调用是否符合工具契约？结果是否可审计？
```

后续安全章节会继续基于 Hook 生命周期扩展防御能力。
