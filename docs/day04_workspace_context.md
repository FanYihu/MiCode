# Day 04：Workspace Context

## 今日目标

实现一个最小版 `Workspace`，让 MiniCode 能读取本地代码工程的上下文。

前面三章做的是 Runtime 内核：

- `Run`：任务
- 状态机：保护任务生命周期
- `TraceRecorder`：记录执行过程

今天开始进入 Coding Agent 的工具能力。第一步不是修改文件，而是先学会观察工作区。

## 为什么重要

Coding Agent 在动手前必须先观察：

- 当前项目有哪些文件？
- 目标文件内容是什么？
- 某个关键词出现在哪些位置？
- 读取路径是否越过了工作区边界？

没有 Workspace Context，Agent 就只能盲写代码。

## 你要创建的文件

```text
minicode/
  src/
    minicode/
      workspace.py
  tests/
    test_workspace.py
```

## 建议你手写的结构

在 `workspace.py` 中定义：

```python
from pathlib import Path


class Workspace:
    ...
```

初始化时接收一个根目录：

```python
def __init__(self, root: str) -> None:
    ...
```

建议保存为：

```python
self.root = Path(root).resolve()
```

## 建议方法

### 1. 路径解析与保护

```python
def resolve_path(self, path: str) -> Path:
    ...
```

要求：

- 把相对路径解析到 `self.root` 下
- 禁止访问工作区外的路径
- 如果越界，抛出 `ValueError`

提示：

```python
target = (self.root / path).resolve()
if self.root not in target.parents and target != self.root:
    raise ValueError("路径越过工作区边界")
```

### 2. 读取文本文件

```python
def read_text(self, path: str) -> str:
    ...
```

要求：

- 使用 `resolve_path()` 获取安全路径
- 用 UTF-8 读取文本

### 3. 列出文件

```python
def list_files(self) -> list[str]:
    ...
```

要求：

- 返回工作区下所有文件的相对路径
- 忽略 `.git`、`.pytest_cache`、`__pycache__`
- 结果排序，方便测试

### 4. 搜索文本

```python
def search_text(self, keyword: str) -> list[dict]:
    ...
```

要求返回类似：

```python
[
    {
        "path": "README.md",
        "line": 3,
        "text": "hello minicode",
    }
]
```

先做最小实现：

- 遍历 `list_files()`
- 逐行读取文本
- 命中关键词就记录路径、行号、行内容
- 遇到无法按文本读取的文件，可以跳过

## 测试提示

在 `test_workspace.py` 中用 pytest 的 `tmp_path` 创建临时工作区。

建议测试：

- `test_list_files_returns_relative_paths`
- `test_read_text_reads_file_content`
- `test_search_text_returns_matches`
- `test_resolve_path_blocks_parent_escape`

`tmp_path` 示例：

```python
def test_read_text_reads_file_content(tmp_path):
    file_path = tmp_path / "hello.txt"
    file_path.write_text("hello", encoding="utf-8")

    workspace = Workspace(str(tmp_path))

    assert workspace.read_text("hello.txt") == "hello"
```

## 验收标准

1. 能列出工作区内文件。
2. 能读取工作区内文本文件。
3. 能搜索关键词并返回路径、行号和文本。
4. 不能通过 `../` 读取工作区外文件。
5. 所有测试通过。

## 完成后运行

```bash
cd /Users/fanyihu/Desktop/技能学习/minicode
PYTHONPATH=src python3 -m pytest
```

## 思考题

为什么 `resolve_path()` 必须先做边界保护？

提示：以后 File Tools 会修改文件。如果路径不受控，Agent 可能改到工作区外的真实文件。
