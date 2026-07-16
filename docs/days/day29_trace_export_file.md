# Day 29：Trace Export File

## 今日目标

把 Markdown trace 报告保存成 `.md` 文件。

Day 28 已经能在终端输出 Markdown：

```bash
python3 -m micode.cli trace trace.json --markdown
```

Day 29 要进一步支持导出文件，方便直接放进学习笔记目录。

## 为什么做

终端输出适合快速查看，但复盘时更需要一个稳定文件：

- 可以长期保存
- 可以提交到笔记目录
- 可以继续手写补充心得

## 建议命令

```bash
python3 -m micode.cli trace trace.json --markdown --output notes/trace-report.md
```

## 建议函数

放在：

```text
micode/src/micode/persistence.py
```

新增：

```python
def write_text_report(content: str, output_path: str) -> str:
    ...
```

这个函数只负责：

1. 创建父目录。
2. 用 UTF-8 写入文本。
3. 返回写入路径。

## 要修改的文件

```text
micode/src/micode/persistence.py
micode/src/micode/cli.py
micode/tests/test_persistence.py
micode/tests/test_cli.py
```

## 验收标准

1. `--markdown --output xxx.md` 能生成 Markdown 文件。
2. CLI 输出保存路径，方便用户知道文件在哪里。
3. 不传 `--output` 时，`--markdown` 仍然输出到终端。
4. 全量测试通过。

## 做了什么

- 新增 `write_text_report(content, output_path)`，统一负责创建目录和写入 UTF-8 文本。
- `trace --markdown --output xxx.md` 可以把 Markdown trace 报告保存到文件。
- 不传 `--output` 时，`trace --markdown` 仍然直接输出报告内容。
- 补充 persistence 和 CLI 测试，覆盖文件导出和终端输出两种路径。

## 思考题

为什么导出文件逻辑不直接写在 CLI 里？

提示：CLI 负责解析参数和展示结果，文件写入属于 persistence 层职责。
