# Day 60：Artifact Read Tool

## 为什么做

Day58 把超大工具结果外置成 artifact，Day59 保证 artifact 写入幂等、可追踪。

但只有占位符还不够：后续模型如果需要完整内容，必须能通过工具按需读回，而不是把所有大结果重新塞进 prompt。

## 做什么

新增 `read_artifact` 工具：

- 支持按 `id` 读取，例如 `artifact:tool-result:...`。
- 支持按 placeholder 里的 `path` 读取。
- 默认只返回首尾预览，避免重新撑爆上下文。
- 校验读取路径必须在 artifact 目录内。
- 校验内容 hash，防止 artifact 文件被改坏后继续被信任。

## 怎么做

核心流转：

```text
AgentAction(read_artifact)
  -> ToolRegistry.call("read_artifact", args)
  -> tools/artifact.py
  -> 解析 id/path
  -> 限制在 artifact_dir 内
  -> 读取 JSON payload
  -> 校验 content sha256
  -> 返回 ToolResult(output=预览或全文, metadata=artifact 信息)
  -> Agent 写入 Trace + observations
```

`read_artifact` 被注册进默认 `ToolRegistry`，所以正常 CLI / Agent 入口都可以直接使用。

## 做了什么

- 新增 `minicode/tools/artifact.py`，实现 `read_artifact`。
- 默认工具集合注册 `read_artifact`。
- `MiniCodeAgent` 创建默认工具集合时传入当前 `artifact_dir`。
- 增加 artifact 读取、边界保护、hash mismatch、默认 Agent 调用读取的测试。

## 学习重点

Artifact 不是“省略内容”，而是“把内容移到可追踪、可校验、可按需读取的外部存储”。

这章完成后，长上下文链路变成：

```text
大工具结果
  -> Artifact Placeholder
  -> Trace 记录 id/path/sha256
  -> 后续需要时 read_artifact 按需读回
```
