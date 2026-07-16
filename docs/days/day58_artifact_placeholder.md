# Day 58：Artifact Placeholder

## 为什么做

Day57 已经把工具结果压成 observation 摘要，但完整结果仍可能很大。

如果几万字符的 `git diff`、测试日志或文件内容继续直接写进 Trace，Trace 文件会越来越重，后续上下文治理也难以按需读取。

Day58 的目标是把超大完整结果外置保存，Prompt 和 Trace 中只保留摘要与 artifact 引用。

## 做什么

新增 `context/artifacts.py`：

- `ArtifactStore`：保存大结果。
- `ArtifactRef`：描述 artifact id、路径、大小和 hash。
- `maybe_store_tool_result_artifact(...)`：超过阈值才外置。

Agent 工具执行后：

- 小结果：Trace content 仍写完整输出。
- 大结果：完整输出写入 artifact JSON。
- Trace content 写摘要和 placeholder。
- observation / 原生 tool message 写摘要和 placeholder。
- Trace metadata 写 artifact id、path、size、sha256。

## 怎么做

流程：

```text
ToolResult.output
  -> summarize_tool_result(...)
  -> if too large:
       ArtifactStore.save_tool_result(...)
       Trace content = summary + artifact placeholder
       Model observation = summary + artifact placeholder
     else:
       Trace content = full output
       Model observation = summary/full output
```

Artifact 文件格式：

```json
{
  "id": "artifact:tool-result:...",
  "kind": "tool_result",
  "tool": "read_file",
  "content": "完整工具输出",
  "size_chars": 12000,
  "sha256": "...",
  "created_at": "...",
  "metadata": {
    "tool_call_id": "..."
  }
}
```

Prompt 占位符：

```text
[artifact id=artifact:tool-result:... kind=tool_result size_chars=12000 path=.micode/artifacts/tool-results/...json]
```

## CLI

新增参数：

```bash
micode agent "读取大文件" \
  --artifact-dir .micode/artifacts \
  --artifact-threshold-chars 8000
```

默认阈值：

```text
8000 chars
```

## 关键边界

- Artifact 只保存超大完整结果，小结果不额外落盘。
- Artifact Placeholder 不负责读取内容，Day59 会实现 Artifact Read Tool。
- Trace 不再强行内嵌超大完整结果，而是保留摘要、占位符和可验证 hash。
- 摘要策略仍由 Day57 的 Tool Result Summary 提供。
- Artifact 文件目前是本地 JSON，后续可以替换为对象存储或 SQLite。

## 参考项目学到了什么

参考项目会把大上下文拆成可引用的外部资源，而不是无条件塞回模型。Micode 这一章先实现本地 artifact placeholder，让大结果可追踪、可验证、可按需读取。

## 验收标准

- 超过阈值的工具结果会写入 artifact 文件。
- artifact 文件保存完整内容、大小和 sha256。
- Trace content 不再包含超大完整输出。
- Trace metadata 包含 artifact 引用。
- observation 和原生 tool message 都包含 artifact placeholder。
- CLI 可以指定 artifact 目录和阈值。

## 做了什么

新增 `context/artifacts.py`，实现工具结果 artifact 外置存储。

Agent 在工具输出超过阈值时保存 artifact，并把摘要和 placeholder 传给模型与 Trace，为 Day59 的 Artifact Read Tool 打基础。
