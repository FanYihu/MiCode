# Day 78：MCP Concept Review

MCP 在 Micode 中不是第二套工具系统。它只负责把远端 server 的 JSON-RPC 能力
转换成 `ToolDefinition`：

```text
config.toml
  -> StdioMCPClient initialize/discovery
  -> mcp__<server>__<tool>
  -> ToolRegistry.call()
  -> Hook + Permission + ToolResult
  -> Trace + untrusted observation
```

Resources 和 Prompts 通过 `list_mcp_resources`、`read_mcp_resource`、
`list_mcp_prompts`、`get_mcp_prompt` 四个标准工具提供，不与动态 tool 名混合。

Micode 不自动读取参考项目的 `.mcp.json`，只读取用户当前 `config.toml` 中显式启用
的 `[mcp.servers.*]`，避免项目检出后自动执行第三方进程。
