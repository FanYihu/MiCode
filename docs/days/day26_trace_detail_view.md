# Day 26：Trace Detail View

## 今日目标

给 trace viewer 增加详细查看模式。

现在 `trace` 子命令输出的是摘要：

```text
Run: completed
Steps: 2
Events: 2

1. tool list_files
2. final
```

Day 26 要新增：

```bash
python3 -m minicode.cli trace path/to/trace.json --detail
```

详细模式可以展示：

- run metadata
- 每个 step 的 metadata
- 每个 event 的 type/content/metadata

## 为什么需要

摘要适合快速扫一眼。

但真实模型调试时，你经常需要看：

- prompt 之后模型返回了什么
- tool event 的 metadata 是什么
- shell 命令 exit_code 是多少
- 哪个 event 写了错误

详细模式就是为了不打开 JSON，也能在终端看关键细节。

## 建议新增函数

放在：

```text
minicode/src/minicode/persistence.py
```

新增：

```python
def format_trace_detail(trace: dict) -> str:
    ...
```

保留：

```python
summarize_trace(trace)
```

摘要和详细分开，避免一个函数越来越复杂。

## CLI 变化

```bash
python3 -m minicode.cli trace trace.json
python3 -m minicode.cli trace trace.json --detail
```

`--detail` 为 False 时继续摘要。

`--detail` 为 True 时输出详细内容。

## 你要手写的内容

修改：

```text
minicode/src/minicode/persistence.py
minicode/src/minicode/cli.py
```

修改测试：

```text
minicode/tests/test_persistence.py
minicode/tests/test_cli.py
```

## 验收标准

1. `trace` 子命令默认仍然输出摘要。
2. `trace --detail` 输出 metadata 和 event 细节。
3. 全量测试通过。

## 思考题

为什么 detail view 应该是格式化已有 trace，而不是重新运行 agent？

提示：查看 trace 是复盘历史事实，重新运行会产生新的模型输出和工具结果。
