# Day 73：Untrusted Content 与 Provenance

## 本章目标

让每个工具结果都能回答四个问题：内容从哪里来、可信级别是什么、字节是否被
修改、是否存在 Prompt Injection 风险。

## 已完成实现

- `ToolResult` 保留 `ok`、`output`、`metadata`，新增 `trust_level`、`source`、
  `content_sha256` 和 `injection_risk`。
- `ToolDefinition` 新增 `ToolCapabilities`、`output_trust` 和 `source`。
- `ToolRegistry.call()` 在统一入口计算 SHA-256，并把 provenance 写入 Trace metadata。
- 可信级别分为 `trusted`、`local`、`untrusted`；文件内容属于 local，Shell/MCP
  属于 untrusted，Runtime 固定文本属于 trusted。
- Agent 给 local/untrusted observation 加显式数据边界，完整原文仍由 Trace 保存。

## 关键流转

```text
ToolDefinition provenance
  -> Tool handler returns ToolResult
  -> annotate_tool_result()
  -> SecurityBoundaryHook
  -> normalized metadata
  -> Trace + bounded model observation
```

测试见 `tests/test_security.py` 和 `tests/test_tool_registry.py`。
