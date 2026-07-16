# Day 27：Trace Detail Truncation

## 今日目标

给 trace detail view 增加内容截断。

Day 26 的详细模式会完整输出 event content：

```bash
python3 -m micode.cli trace trace.json --detail
```

这对小 trace 很方便，但真实运行时 event content 可能非常长：

- 读取了大文件
- shell 输出很多测试日志
- 模型返回了长文本

Day 27 要让 detail view 支持最大内容长度。

## 建议命令

```bash
python3 -m micode.cli trace trace.json --detail --max-content 500
```

默认可以设为：

```text
2000
```

如果用户想看完整内容，可以传：

```bash
--max-content 0
```

约定：

- `max_content > 0`：超过长度就截断
- `max_content == 0`：不截断

## 新增 helper

放在：

```text
micode/src/micode/persistence.py
```

新增：

```python
def truncate_text(text: str, max_length: int) -> str:
    ...
```

示例：

```python
truncate_text("abcdef", 3)
# "abc... [truncated]"
```

## 修改函数

把：

```python
format_trace_detail(trace)
```

改为：

```python
format_trace_detail(trace, max_content: int = 2000)
```

只截断 event content，不截断 metadata。

## 你要手写的内容

修改：

```text
micode/src/micode/persistence.py
micode/src/micode/cli.py
```

修改测试：

```text
micode/tests/test_persistence.py
micode/tests/test_cli.py
```

## 验收标准

1. detail view 默认截断过长 content。
2. `--max-content 0` 输出完整 content。
3. 摘要视图不受影响。
4. 全量测试通过。

## 思考题

为什么只截断 event content，而不截断 metadata？

提示：content 通常是大文本主体，metadata 通常是定位和调试用的结构化信息。
