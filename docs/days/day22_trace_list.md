# Day 22：Trace List

## 今日目标

让 CLI 能列出最近保存的 trace 文件。

Day 20 已经能保存：

```bash
python3 -m minicode.cli agent "读取 README" --save-trace
```

Day 21 已经能查看：

```bash
python3 -m minicode.cli trace .minicode/traces/xxx.json
```

但真实使用时，你不一定记得文件名。

Day 22 要新增：

```bash
python3 -m minicode.cli traces
```

输出最近保存的 trace 文件列表。

## 为什么需要

Trace 文件按时间戳命名，适合机器保存，但人不容易记。

`traces` 子命令可以帮你快速找到最近一次运行：

```text
1. .minicode/traces/2026-06-02T12-30-00Z.json
2. .minicode/traces/2026-06-02T12-20-00Z.json
```

之后再用：

```bash
python3 -m minicode.cli trace path/to/file.json
```

## 新增函数

建议放在：

```text
minicode/src/minicode/persistence.py
```

新增：

```python
def list_traces(trace_dir: str = ".minicode/traces", limit: int = 10) -> list[str]:
    ...
```

行为：

- 如果目录不存在，返回空列表。
- 只列 `.json` 文件。
- 按修改时间倒序排列。
- 最多返回 `limit` 个。

## 建议实现

```python
def list_traces(trace_dir: str = ".minicode/traces", limit: int = 10) -> list[str]:
    directory = Path(trace_dir)
    if not directory.exists():
        return []

    paths = sorted(
        directory.glob("*.json"),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    return [str(path) for path in paths[:limit]]
```

## 接入 CLI

新增子命令：

```bash
python3 -m minicode.cli traces --trace-dir .minicode/traces --limit 10
```

输出：

```text
1. .minicode/traces/a.json
2. .minicode/traces/b.json
```

如果没有 trace：

```text
No traces found.
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
1. list_traces 在目录不存在时返回 []
2. list_traces 只返回 json 文件
3. list_traces 按最近修改时间排序
4. CLI traces 子命令能格式化输出列表
```

## 验收标准

1. 能列出最近 trace 文件。
2. 支持 limit。
3. 没有 trace 时输出友好提示。
4. 不影响 trace 查看和保存。
5. 全量测试通过。

## 完成后运行

```bash
cd /Users/fanyihu/Desktop/技能学习/minicode
PYTHONPATH=src python3 -m pytest
```

## 思考题

为什么 `list_traces()` 应该返回路径列表，而不是直接 print？

提示：底层函数返回数据，CLI 决定怎么展示；这样测试和复用更简单。
