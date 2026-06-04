# Day 28：Trace Markdown Report

## 今日目标

把一次 trace 转成 Markdown 报告。

前面几章我们已经能保存、查看、筛选和清理 trace。Day 28 要做的是让 trace 更适合写进学习笔记或复盘文档里。

## 为什么做

JSON 适合程序读取，但人复盘时更想看到：

- 这次任务是什么
- Run 最后成功还是失败
- 每一步用了什么工具
- 最终回答或错误是什么

Markdown 报告能直接放进笔记里，也方便以后做“运行历史复盘”。

## 建议效果

新增函数：

```python
def format_trace_markdown(trace: dict) -> str:
    ...
```

输出大概长这样：

```markdown
# MiniCode Trace Report

## Run

- status: completed
- task: 读取 README
- mode: agent

## Steps

1. tool read_file
2. final

## Final

完成
```

## 要修改的文件

```text
minicode/src/minicode/persistence.py
minicode/src/minicode/cli.py
minicode/tests/test_persistence.py
minicode/tests/test_cli.py
```

## CLI 入口

建议在现有 trace 子命令上增加：

```bash
python3 -m minicode.cli trace trace.json --markdown
```

规则：

- 默认仍然输出 summary。
- `--detail` 输出详细文本。
- `--markdown` 输出 Markdown 报告。
- 如果同时传 `--detail` 和 `--markdown`，可以让 `--markdown` 优先，保持逻辑简单。

## 验收标准

1. `format_trace_markdown` 能输出 Run、Steps、Final/Error。
2. CLI `trace --markdown` 能读取 JSON trace 并输出 Markdown。
3. 现有 summary/detail 行为不被破坏。
4. 全量测试通过。

## 思考题

Markdown 报告和 detail view 有什么区别？

提示：detail view 更偏调试，Markdown report 更偏复盘和分享。
