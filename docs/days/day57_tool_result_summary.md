# Day 57：Tool Result Summary

## 为什么做

`read_file`、`run_shell` 和 `git_diff` 可能返回几千字符。如果完整结果反复进入模型请求，会挤掉任务目标；但完整输出也不能丢，因为 Trace 需要支持审计。

## 做什么

新增 `context/tool_results.py`：

- `ToolResultSummary` 记录模型实际看到的结果。
- `summarize_tool_result(...)` 按工具类型选择摘要策略。
- Trace 保存完整输出。
- Agent observation 和原生 tool message 使用摘要。
- Trace metadata 记录原始长度、摘要长度、策略和截断状态。

## 怎么做

```text
ToolRegistry.call(...)
  -> ToolResult.output 完整结果
  -> summarize_tool_result(...)
      -> observation summary
      -> native tool message summary
  -> Trace Event.content 完整结果
  -> Trace metadata 摘要审计信息
```

摘要策略：

- `run_shell`、`git_diff`、`git_status`：保留首尾，并给结尾更多预算。
- `read_file`、`load_skill`：保留正文开头和少量结尾。
- `list_files`：保留文件总数和列表首尾。
- 其他工具：使用通用首尾摘要。

截断标记：

```text
... [tool output truncated] ...
```

## CLI

默认每条工具 observation 最多 `1200` 字符：

```bash
micode agent "运行测试" --tool-result-budget-chars 1200
```

Trace metadata 新增：

- `observation_summary`
- `observation_original_chars`
- `observation_used_chars`
- `observation_truncated`
- `observation_strategy`

## 关键边界

- 本章只压缩模型上下文，不修改工具执行结果。
- Trace Event.content 继续保存完整输出。
- 原生 tool call 和旧 observations 使用同一摘要。
- Day58 会把超大完整结果外置成 Artifact。
- 当前使用字符预算，Day60 再统一为 Token Estimate。

## 参考项目学到了什么

参考项目区分工具原始结果与上下文表示。Micode 先实现确定性摘要，使结果既可审计，又不会无边界占用 Prompt。

## 验收标准

- 短结果保持原文。
- 长结果保留首尾并带截断标记。
- 命令结果保留结尾测试统计或错误。
- list_files 摘要保留总文件数。
- Agent observation 和原生 tool message 使用摘要。
- Trace 保存完整输出及摘要审计字段。

## 做了什么

新增 `context/tool_results.py`，实现按工具类型压缩结果。

Agent 将摘要传给下一轮模型，同时继续把完整结果写入 Trace，并支持通过 CLI 调整单条工具结果预算。
