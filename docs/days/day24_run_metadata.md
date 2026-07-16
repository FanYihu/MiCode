# Day 24：Run Metadata

## 今日目标

给每次 Run 增加关键元数据。

现在 trace 里有：

```text
run status
steps
events
```

但真实复盘时，你还会想知道：

- 这次用户 task 是什么
- 用的是哪个 provider
- 用的是哪个 model
- workspace 是哪里
- 是 CLI fixed 还是 agent 模式

Day 24 要做的是把这些信息写进 `run.metadata`。

## 为什么需要

Trace 文件保存下来后，文件名只有时间戳。

如果 run 里没有 metadata，你打开 trace 可能只能看到：

```json
"status": "completed"
```

但不知道它是在执行哪个任务。

元数据让 trace 更容易复盘和比较。

## 建议结构

```json
{
  "run": {
    "id": "...",
    "status": "completed",
    "metadata": {
      "task": "读取 README",
      "mode": "agent",
      "workspace": ".",
      "provider": "mimo",
      "model": "mimo-v2.5-pro"
    }
  }
}
```

## 修改 TraceRecorder

现在 `to_dict()` 里需要把 `run.metadata` 导出：

```python
"metadata": self.run.metadata,
```

## 修改 MicodeAgent

`MicodeAgent.run(task)` 里可以记录：

```python
run.metadata["task"] = task
run.metadata["mode"] = "agent"
```

如果能从 LLM/client 拿到 provider/model，也记录：

```python
client = getattr(self.llm, "client", None)
run.metadata["provider"] = getattr(client, "provider", "")
run.metadata["model"] = getattr(client, "model", "")
```

## 修改 CLI fixed

`run_task()` 里记录：

```python
run.metadata["task"] = task
run.metadata["mode"] = "fixed"
run.metadata["workspace"] = workspace_path
```

Agent 模式的 workspace 也可以在 `run_agent_task()` 返回后补：

```python
trace["run"]["metadata"]["workspace"] = workspace_path
```

## 你要手写的内容

修改：

```text
micode/src/micode/trace.py
micode/src/micode/agent.py
micode/src/micode/cli.py
```

修改测试：

```text
micode/tests/test_trace.py
micode/tests/test_agent_integration.py
micode/tests/test_cli.py
```

## 建议测试

```text
1. TraceRecorder.to_dict 导出 run metadata
2. MicodeAgent.run 记录 task/mode
3. 如果 TextLLM client 有 provider/model，trace 记录 provider/model
4. CLI fixed 记录 task/mode/workspace
```

## 验收标准

1. trace["run"]["metadata"] 存在。
2. fixed 和 agent 都记录 task。
3. agent 能记录 provider/model。
4. 不影响已有 step/event 输出。
5. 全量测试通过。

## 完成后运行

```bash
cd /Users/fanyihu/Desktop/技能学习/micode
PYTHONPATH=src python3 -m pytest
```

## 思考题

为什么 metadata 放在 Run 上，而不是放在某个 Step 上？

提示：task、provider、model 属于整次运行的上下文，不属于单个工具步骤。
