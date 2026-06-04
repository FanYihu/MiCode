# Day 07：Permission / Human Review

## 今日目标

实现最小版权限审核，让 MiniCode 在高风险操作前能判断是否需要人工确认。

前面已经有：

- `FileTools`：可以写文件
- `ShellTools`：可以执行命令

这两类能力都很强，也都可能危险。Day 07 要加一层权限判断：

```text
操作请求 -> 风险判断 -> 允许执行 / 等待人工确认 / 直接拒绝
```

## 为什么重要

Coding Agent 不应该无条件执行所有操作，例如：

- 删除文件
- 覆盖重要配置
- 执行 `rm -rf`
- 执行安装、网络、系统级命令
- 修改工作区外路径

Human-in-the-loop 的核心不是“问用户一句话”，而是 Runtime 能明确知道：

- 哪些操作安全
- 哪些操作需要确认
- 哪些操作必须拒绝

## 你要创建的文件

```text
minicode/
  src/
    minicode/
      permissions.py
  tests/
    test_permissions.py
```

## 建议结构

定义权限决策枚举：

```python
from enum import Enum


class PermissionDecision(str, Enum):
    ALLOW = "allow"
    REVIEW = "review"
    DENY = "deny"
```

定义审核结果：

```python
from dataclasses import dataclass
from typing import Optional


@dataclass
class PermissionResult:
    decision: PermissionDecision
    reason: str
    review_message: Optional[str] = None
```

定义审核器：

```python
class PermissionReviewer:
    ...
```

## 建议方法

### 1. 文件写入审核

```python
def review_file_write(self, path: str) -> PermissionResult:
    ...
```

建议规则：

- 普通 `.py`、`.md`、`.txt` 文件：`ALLOW`
- `.env`、`secrets`、`credentials` 相关文件：`REVIEW`
- 路径包含 `..`：`DENY`

### 2. 命令审核

```python
def review_shell_command(self, command: str) -> PermissionResult:
    ...
```

建议规则：

- `pytest`、`python3 -m pytest`、`ls`、`pwd`、`echo`：`ALLOW`
- `pip install`、`curl`、`npm install`：`REVIEW`
- `rm -rf`、`sudo`、`chmod -R`：`DENY`

先用简单字符串判断即可，不需要做复杂 shell parser。

## 测试提示

建议测试：

- `test_safe_file_write_allowed`
- `test_secret_file_write_requires_review`
- `test_parent_escape_file_write_denied`
- `test_safe_shell_command_allowed`
- `test_install_command_requires_review`
- `test_dangerous_shell_command_denied`

## 验收标准

1. 安全文件写入返回 `ALLOW`。
2. 敏感文件写入返回 `REVIEW`。
3. 越界路径返回 `DENY`。
4. 安全命令返回 `ALLOW`。
5. 安装或网络命令返回 `REVIEW`。
6. 明显危险命令返回 `DENY`。
7. 每个结果都包含清晰的 `reason`。

## 完成后运行

```bash
cd /Users/fanyihu/Desktop/技能学习/minicode
PYTHONPATH=src python3 -m pytest
```

## 思考题

为什么权限审核器只返回决策，不直接执行或阻止工具？

提示：Runtime 需要根据决策创建 Step/Event，必要时进入 `waiting_human`，所以“判断”和“执行”最好分开。
