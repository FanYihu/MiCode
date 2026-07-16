# Day 06：Shell Tools

## 今日目标

实现 Micode 的命令执行工具 `ShellTools`，让 Agent 能在工作区内运行命令并拿到结构化结果。

前面我们已经有：

- `Workspace`：看文件、搜文件、限制路径
- `FileTools`：读写文件、预览修改

今天加上执行能力：

```text
运行命令 -> 捕获 stdout/stderr -> 记录 exit_code -> 处理 timeout
```

## 为什么重要

Coding Agent 修改代码后，必须能验证结果：

- 运行测试
- 执行 lint
- 查看脚本输出
- 读取失败错误

但 Shell 是高风险能力，所以第一版要非常克制：只在工作区根目录运行，并设置超时。

## 你要创建的文件

```text
micode/
  src/
    micode/
      shell_tools.py
  tests/
    test_shell_tools.py
```

## 建议结构

在 `shell_tools.py` 中定义一个结果模型：

```python
from dataclasses import dataclass


@dataclass
class CommandResult:
    command: str
    exit_code: int
    stdout: str
    stderr: str
    timed_out: bool = False
```

再定义：

```python
class ShellTools:
    ...
```

初始化时接收 `Workspace`：

```python
def __init__(self, workspace: Workspace) -> None:
    self.workspace = workspace
```

## 建议方法

### 1. 执行命令

```python
def run(self, command: str, timeout: float = 10.0) -> CommandResult:
    ...
```

要求：

- 使用 `subprocess.run`
- `cwd` 固定为 `self.workspace.root`
- 捕获 stdout 和 stderr
- 文本模式运行
- 设置 timeout
- 返回 `CommandResult`

提示：

```python
completed = subprocess.run(
    command,
    cwd=self.workspace.root,
    shell=True,
    capture_output=True,
    text=True,
    timeout=timeout,
)
```

### 2. 处理超时

如果 `subprocess.TimeoutExpired`，返回：

```python
CommandResult(
    command=command,
    exit_code=-1,
    stdout=exc.stdout or "",
    stderr=exc.stderr or "命令执行超时",
    timed_out=True,
)
```

注意：Python 有时会把超时输出保存成 bytes，如果遇到 bytes，要 decode。

## 测试提示

在 `test_shell_tools.py` 中用 `tmp_path` 创建临时工作区。

建议测试：

- `test_run_success_command`
- `test_run_failure_command`
- `test_run_uses_workspace_as_cwd`
- `test_run_timeout`

示例：

```python
def test_run_success_command(tmp_path):
    shell = ShellTools(Workspace(str(tmp_path)))

    result = shell.run("echo hello")

    assert result.exit_code == 0
    assert "hello" in result.stdout
    assert result.timed_out is False
```

## 验收标准

1. 成功命令返回 `exit_code == 0`。
2. 失败命令返回非 0 exit code，并捕获 stderr。
3. 命令运行目录固定在 workspace root。
4. 超时命令不会卡住测试，返回 `timed_out=True`。
5. 所有测试通过。

## 安全提醒

这一章先不做危险命令拦截，Day 07 会专门处理 Permission / Human Review。

但你现在就要记住：

```text
ShellTools 是 Micode 里风险最高的工具之一。
```

后续所有删除、移动、安装依赖、网络访问等操作，都应该进入权限审核。

## 完成后运行

```bash
cd /Users/fanyihu/Desktop/技能学习/micode
PYTHONPATH=src python3 -m pytest
```

## 思考题

为什么 `ShellTools.run()` 要返回结构化 `CommandResult`，而不是直接返回 stdout 字符串？

提示：Agent 需要同时理解成功/失败、标准输出、错误输出和是否超时。
