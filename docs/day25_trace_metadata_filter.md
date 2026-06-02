# Day 25：Trace Metadata Filter

## 今日目标

按 metadata 筛选 trace。

Day 24 已经把这些信息写进 trace：

```json
{
  "task": "读取 README",
  "mode": "agent",
  "workspace": ".",
  "provider": "mimo",
  "model": "mimo-v2.5-pro"
}
```

Day 25 要让 `traces` 子命令支持按这些字段过滤。

## 为什么需要

当 trace 文件变多以后，你可能想快速找到：

- 最近的 agent 模式运行
- 某个 provider 的运行
- 某个 model 的运行
- 某个 task 关键词相关的运行

这比手动打开 JSON 更有效。

## 建议新增函数

放在：

```text
minicode/src/minicode/persistence.py
```

新增：

```python
def filter_traces(
    trace_paths: list[str],
    mode: str = "",
    provider: str = "",
    model: str = "",
    task_contains: str = "",
) -> list[str]:
    ...
```

行为：

- 读取每个 trace
- 查看 `trace["run"]["metadata"]`
- 匹配指定条件
- 返回符合条件的路径

## CLI 示例

```bash
python3 -m minicode.cli traces --mode agent
python3 -m minicode.cli traces --provider mimo
python3 -m minicode.cli traces --model mimo-v2.5-pro
python3 -m minicode.cli traces --task-contains README
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

## 验收标准

1. `traces` 子命令支持 metadata 过滤。
2. 多个过滤条件可以一起使用。
3. 无匹配时输出 `No traces found.`
4. 全量测试通过。

## 思考题

为什么过滤逻辑应该放在 persistence 层，而不是写死在 CLI 里？

提示：CLI 负责展示，persistence 负责读取和筛选 trace 数据。
