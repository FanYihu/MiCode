# Day 82：MCP Tool Call

## 调用链

```text
AgentAction
  -> ToolRegistry.call(mcp__server__tool)
  -> before hooks
  -> StdioMCPClient tools/call
  -> JSON-RPC response
  -> ToolResult(untrusted, source=mcp:...)
  -> after hooks
  -> Trace + observation boundary
```

Reader thread按 request id 分发响应。pending request 在成功、超时、进程退出和协议
错误时都会删除。Server 退出后，下一次调用会重新 initialize；不会自动重放刚刚
失败的写请求，以免重复副作用。
