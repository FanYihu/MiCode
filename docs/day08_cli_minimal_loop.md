# Day 08：CLI 最小闭环

## 今日目标

实现一个最小 CLI，让 MiniCode 可以从命令行接收任务，并完成一次可观察的运行。

前面七章已经分别完成：

- `Run / Step / Event`
- Run 状态机
- `TraceRecorder`
- `Workspace`
- `FileTools`
- `ShellTools`
- `PermissionReviewer`

Day 08 要把它们串起来：

```text
命令行输入任务 -> 创建 Run -> 开始运行 -> 记录 Step/Event -> 输出 trace -> 完成 Run
```

## 为什么重要

到现在为止，我们有很多模块，但还没有一个“入口”。

CLI 的意义是让 MiniCode 开始像一个真实工具：

```bash
python3 -m minicode.cli "列出当前项目文件"
```

第一版 CLI 不接大模型，不自动改代码，只做固定动作，把运行链路打通。

## 你要创建的文件

```text
minicode/
  src/
    minicode/
      cli.py
  tests/
    test_cli.py
```

## 建议 CLI 行为

命令格式：

```bash
PYTHONPATH=src python3 -m minicode.cli "list files" --workspace .
```

最小支持两个任务：

- `list files`：列出工作区文件
- `run tests`：执行 `python3 -m pytest`

其他任务先返回“不支持的任务”。

## 建议结构

### 1. 纯函数入口

先写一个方便测试的函数：

```python
def run_task(task: str, workspace_path: str) -> dict:
    ...
```

### 2. CLI main

再写命令行入口：

```python
def main() -> None:
    ...
```

用标准库：

```python
import argparse
import json
```

## 验收标准

1. `run_task("list files", path)` 返回包含 run、steps、events 的 trace。
2. `list files` 能把工作区文件写入 event。
3. 不支持的任务不会崩溃，会返回文本事件。
4. `run tests` 能执行 pytest 并记录 exit_code。
5. `python3 -m minicode.cli "list files" --workspace .` 能打印 JSON。
6. 所有测试通过。
