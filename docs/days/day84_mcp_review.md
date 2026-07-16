# Day 84：MCP Review

## 可用入口

```bash
micode mcp-inspect --config config.toml --workspace .
```

检查结果包含 serverInfo、tools、resources、prompts 和 discovery error。Registry
实现 disposer/context-manager，关闭时会终止全部 MCP 子进程并唤醒 pending request。

## 失败场景

- 初始化失败与协议不匹配。
- request timeout。
- Server 在 pending request 中退出。
- 响应超过 payload 限制。
- cwd 越过 Workspace。
- 写型工具未审批。
- 进程退出后的下一次调用重连。

对应测试位于 `tests/test_mcp.py`。
