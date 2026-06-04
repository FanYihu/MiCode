# Day 05：File Tools

## 今日目标

实现 MiniCode 的第一组文件工具：安全读取、写入和修改预览。

Day 04 的 `Workspace` 让 Agent 能观察项目。Day 05 要让 Agent 具备最小文件操作能力，但仍然要受路径边界保护。

## 为什么重要

Coding Agent 最核心的能力不是“回答怎么改”，而是能围绕代码文件执行闭环：

```text
读取文件 -> 生成修改 -> 预览差异 -> 写入文件 -> 再运行测试
```

今天先实现文件层能力，不接模型、不做复杂 patch。

## 你要创建的文件

```text
minicode/
  src/
    minicode/
      file_tools.py
  tests/
    test_file_tools.py
```

## 建议结构

在 `file_tools.py` 中定义：

```python
class FileTools:
    ...
```

初始化时接收 `Workspace`：

```python
def __init__(self, workspace: Workspace) -> None:
    self.workspace = workspace
```

## 建议方法

### 1. 读取文件

```python
def read_file(self, path: str) -> str:
    ...
```

要求：

- 直接复用 `workspace.read_text(path)`

### 2. 写入文件

```python
def write_file(self, path: str, content: str) -> None:
    ...
```

要求：

- 使用 `workspace.resolve_path(path)` 做路径保护
- 如果父目录不存在，自动创建
- 使用 UTF-8 写入

提示：

```python
target.parent.mkdir(parents=True, exist_ok=True)
target.write_text(content, encoding="utf-8")
```

### 3. 生成修改预览

```python
def preview_write(self, path: str, new_content: str) -> str:
    ...
```

要求：

- 如果文件存在，读取旧内容
- 如果文件不存在，旧内容为空
- 返回 unified diff 字符串
- 不实际写入文件

可使用标准库：

```python
import difflib
```

提示：

```python
diff = difflib.unified_diff(
    old_content.splitlines(keepends=True),
    new_content.splitlines(keepends=True),
    fromfile=f"a/{path}",
    tofile=f"b/{path}",
)
return "".join(diff)
```

### 4. 判断文件是否存在

```python
def exists(self, path: str) -> bool:
    ...
```

要求：

- 必须先走 `workspace.resolve_path(path)`

## 测试提示

在 `test_file_tools.py` 中用 `tmp_path` 创建临时工作区。

建议测试：

- `test_read_file_uses_workspace`
- `test_write_file_creates_file`
- `test_write_file_creates_parent_dirs`
- `test_preview_write_returns_diff_without_writing`
- `test_file_tools_blocks_parent_escape`

## 验收标准

1. 能读取已有文件。
2. 能写入新文件。
3. 写入嵌套路径时能自动创建父目录。
4. `preview_write()` 能返回 diff，但不会修改文件。
5. 所有文件操作都不能越过工作区边界。
6. 所有测试通过。

## 完成后运行

```bash
cd /Users/fanyihu/Desktop/技能学习/minicode
PYTHONPATH=src python3 -m pytest
```

## 思考题

为什么要先做 `preview_write()`，而不是让 Agent 直接写文件？

提示：后续 Human-in-the-loop 会基于 diff 让用户确认高风险修改。
