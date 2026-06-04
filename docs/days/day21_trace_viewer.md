# Day 21：Trace Viewer

## 今日目标

从已保存的 trace JSON 里生成一份简洁复盘摘要。

Day 20 已经能保存 trace：

```text
.minicode/traces/2026-06-02T12-30-00Z.json
```

Day 21 要做的是：

```text
trace JSON 文件 -> 可读摘要
```

这样你不用每次都手动翻 JSON。

## 为什么需要 Trace Viewer

真实模型调试时，trace 可能很长。

你最想快速知道的是：

- Run 最终状态是什么
- 一共有多少 step/event
- 每一步是什么类型
- 哪一步出错了
- final answer 是什么

Trace Viewer 不改变 Agent 行为，只负责读 trace 和总结 trace。

## 新增函数

建议继续放在：

```text
minicode/src/minicode/persistence.py
```

新增：

```python
def load_trace(path: str) -> dict:
    ...

def summarize_trace(trace: dict) -> str:
    ...
```

## load_trace

负责读取 JSON：

```python
def load_trace(path: str) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))
```

## summarize_trace

第一版可以输出纯文本：

```text
Run: completed
Steps: 2
Events: 2

1. tool list_files
2. final

Final: 完成
```

如果有错误：

```text
Run: failed
Steps: 1
Events: 1

1. model

Errors:
- action text must be valid json
```

## 接入 CLI

新增一个子命令：

```bash
python3 -m minicode.cli trace path/to/trace.json
```

输出摘要文本，而不是 JSON。

示例：

```bash
python3 -m minicode.cli trace .minicode/traces/2026-06-02T12-30-00Z.json
```

## 你要手写的内容

修改：

```text
minicode/src/minicode/persistence.py
minicode/src/minicode/cli.py
```

新增或修改测试：

```text
minicode/tests/test_persistence.py
minicode/tests/test_cli.py
```

## 建议测试

```text
1. load_trace 能读取保存过的 trace
2. summarize_trace 能显示 run status
3. summarize_trace 能显示 final answer
4. summarize_trace 能显示 error event
5. CLI trace 子命令能调用 summarize_trace
```

## 验收标准

1. 能从 JSON 文件加载 trace。
2. 能生成可读摘要。
3. CLI 支持 `trace` 子命令。
4. 不影响 fixed/agent 原有输出。
5. 全量测试通过。

## 完成后运行

```bash
cd /Users/fanyihu/Desktop/技能学习/minicode
PYTHONPATH=src python3 -m pytest
```

## 思考题

为什么 Trace Viewer 不应该调用模型？

提示：它是复盘工具，只读已经发生的事实，不负责生成新 action。
