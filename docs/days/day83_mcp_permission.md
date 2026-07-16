# Day 83：MCP Permission

MCP 权限复用 ToolRegistry 的 `ToolCapabilities` 和 `PermissionHook`：

- readOnlyHint 工具按外部只读工具执行。
- 未声明只读的 MCP tool 强制创建 Human Review。
- 批准记录绑定 server tool 的本地名称和完整参数哈希，只能消费一次。
- 所有 MCP 输出无条件标为 `untrusted`，并执行 Prompt Injection 扫描。
- 子进程始终 `shell=False`，cwd 不得离开 Workspace。
- 单请求和响应都受 `max_payload_bytes` 限制。

这样 MCP 不会绕过现有 Permission、Hook、Trace 或 contaminated-context 规则。
