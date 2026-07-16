# Day 81：MCP Tool Discovery

`MCPManager` 为每个 server 维护一个惰性 `StdioMCPClient`。第一次 discovery 会：

1. 启动进程并发送 `initialize`。
2. 发送 `notifications/initialized`。
3. 分页调用 `tools/list`。
4. 把 inputSchema 原样映射到 OpenAI-compatible Tool Schema。
5. 将名称规范为 `mcp__<server>__<tool>`。

`annotations.readOnlyHint=true` 的工具可以并行；其他工具声明
`requires_review=true`。单个 server 发现失败会进入 `discovery_errors`，不会伪装成
空成功结果。
