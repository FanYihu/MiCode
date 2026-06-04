# Day 34：Git Tool

## 今日目标

新增一个只读 Git 工具，让 MiniCode 能看见当前仓库状态和 diff。

Day 33 已经统一了工具结果 metadata。Day 34 要把 git 能力作为一个普通工具接入，为后续 Agent 复盘“我改了什么”打基础。

## 为什么做

Coding agent 修改代码后，必须能回答两个问题：

- 当前工作区有哪些变化？
- 具体 diff 是什么？

如果没有 Git Tool，Agent 只能依赖文件读写结果，无法稳定复盘项目级变化。

## 承接已有能力

本章承接：

- Day 32 的 `ToolRegistry`。
- Day 33 的工具 metadata 契约。
- 现有 `Workspace` 路径边界。

## 参考项目学到了什么

参考：

```text
references/MiniCode-Python/minicode/tools/git.py
```

参考项目的 git 工具支持 status、diff、log、commit、review 等动作。

本章只吸收只读能力：

- `git status --short`
- `git diff`

先不做 `commit`，避免在工具层引入写仓库历史的能力。

## 建议接口

新增文件：

```text
minicode/src/minicode/git_tools.py
```

建议结构：

```python
class GitTools:
    def status(self) -> ToolResult:
        ...

    def diff(self) -> ToolResult:
        ...
```

也可以先返回普通字符串，但推荐直接复用 `ToolResult`。

## 要修改的文件

```text
minicode/src/minicode/git_tools.py
minicode/src/minicode/tool_registry.py
minicode/tests/test_git_tools.py
minicode/tests/test_tool_registry.py
docs/SDD.md
```

## 验收标准

1. `GitTools.status()` 返回 `git status --short` 的结果。
2. `GitTools.diff()` 返回 `git diff` 的结果。
3. 命令失败时返回 `ok=False`，不抛出未处理异常。
4. 默认 Tool Registry 注册 `git_status` 和 `git_diff`。
5. Git 工具 metadata 符合 Day 33 契约：顶层字段统一，Git 细节放进 `details`。
6. 全量测试通过。

## 做了什么

- 新增 `git_tools.py`，实现只读 `GitTools.status()` 和 `GitTools.diff()`。
- 使用固定参数列表执行 `git status --short` 和 `git diff`，不走 shell 字符串。
- Git 命令失败时返回 `ToolResult(ok=False, ...)`，不向上抛未处理异常。
- 默认 Tool Registry 注册 `git_status` 和 `git_diff`。
- Git 命令细节如 `command`、`exit_code`、`stderr` 统一进入 metadata 的 `details`。
- 补充 Git 工具测试和 Registry 注册测试。

## 思考题

为什么 Day 34 只做只读 Git Tool，不做 commit？

提示：查看状态和 diff 是观察能力，commit 是改变仓库历史，应该等权限和人工确认链路更稳定后再做。
