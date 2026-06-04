# Day 23：Trace Cleanup

## 今日目标

清理旧的 trace 文件。

前面已经完成：

```text
save_trace()      保存 trace
load_trace()      读取 trace
summarize_trace() 查看摘要
list_traces()     列出最近 trace
```

Day 23 要补一个维护能力：

```text
cleanup_traces()
```

避免 `.minicode/traces` 目录越来越大。

## 为什么需要

真实模型调试时，trace 会很多。

如果每次运行都 `--save-trace`，目录会快速堆满：

```text
.minicode/traces/
  2026-06-02T12-00-00Z.json
  2026-06-02T12-01-00Z.json
  ...
```

保留最近 N 个，删除更旧的，是一个简单有效的策略。

## 新增函数

放在：

```text
minicode/src/minicode/persistence.py
```

新增：

```python
def cleanup_traces(trace_dir: str = ".minicode/traces", keep: int = 20) -> list[str]:
    ...
```

行为：

- 如果目录不存在，返回空列表。
- 按修改时间倒序排列。
- 保留最新的 `keep` 个。
- 删除其余 `.json` 文件。
- 返回被删除的文件路径列表。

## 建议实现

```python
def cleanup_traces(trace_dir: str = ".minicode/traces", keep: int = 20) -> list[str]:
    paths = list_traces(trace_dir=trace_dir, limit=10_000)
    deleted = []

    for path in paths[keep:]:
        Path(path).unlink()
        deleted.append(path)

    return deleted
```

## 接入 CLI

新增子命令：

```bash
python3 -m minicode.cli cleanup-traces --trace-dir .minicode/traces --keep 20
```

输出：

```text
Deleted 3 trace files.
```

如果没有删除：

```text
No trace files deleted.
```

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

## 建议测试

```text
1. cleanup_traces 在目录不存在时返回 []
2. cleanup_traces 保留最新 N 个
3. cleanup_traces 返回被删除路径
4. CLI cleanup-traces 输出删除数量
```

## 验收标准

1. 能按 keep 数量清理旧 trace。
2. 不删除非 JSON 文件。
3. CLI 支持 cleanup-traces。
4. 全量测试通过。

## 完成后运行

```bash
cd /Users/fanyihu/Desktop/技能学习/minicode
PYTHONPATH=src python3 -m pytest
```

## 思考题

为什么 cleanup 函数应该返回“删除了哪些文件”，而不是只返回数量？

提示：路径列表既能用于 CLI 统计，也能用于测试和审计。
