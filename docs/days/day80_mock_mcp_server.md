# Day 80：Mock MCP Server

`tests/fixtures/mock_mcp_server.py` 是独立 stdio 进程，不在测试进程内伪造 client。

它支持：

- newline-json 与 Content-Length framing。
- initialize、tools/list、tools/call。
- resources/list、resources/read。
- prompts/list、prompts/get。
- hang、process exit、oversized payload 和 injection 输出模式。

因此测试覆盖真实进程管道、线程、超时和关闭行为，而不只是函数 mock。
