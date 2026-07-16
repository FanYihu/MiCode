# Day 79：MCP Config

## 配置契约

```toml
[mcp]
enabled = true

[mcp.servers.example]
command = "python3"
args = ["server.py"]
protocol = "newline-json" # auto/newline-json/content-length
request_timeout_seconds = 10
startup_timeout_seconds = 3
max_payload_bytes = 4194304
```

配置由 `load_mcp_server_configs()` 解析为 `MCPServerConfig`。Server 使用参数数组和
`shell=False` 启动；禁止把通用 Shell 当 server 命令；`cwd` 必须留在 Workspace
内部；环境变量只传给子进程，不写入 Trace。
