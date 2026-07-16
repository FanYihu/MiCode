# Day 32：Tool Registry

## 今日目标

建立一个轻量工具注册表，把现有工具调用从硬编码分发，逐步过渡到可扩展 runtime。

Day 31 已经补了结构化文件编辑工具。Day 32 不急着改 Agent 行为，而是先把“工具是什么、怎么查找、怎么调用、调用失败怎么表示”定义清楚。

## 为什么做

现在 Agent 里对工具的处理还是 `if action.tool == ...` 这种分支。

这种写法适合最小闭环，但后面接 Skill、MCP、SubAgent 时会很难扩展。Tool Registry 要成为后续能力的统一入口。

## 承接已有能力

本章承接：

- `Workspace` 的路径边界。
- `FileTools` 的 `read_file`、`replace_text`。
- `ShellTools` 的 `run`。
- 后续会再接入 `TraceRecorder` 的 metadata 契约。

## 参考项目学到了什么

参考：

```text
references/MiniCode-Python/minicode/tooling.py
```

参考项目里每个工具都有：

- 名字和描述。
- 输入校验函数。
- 执行函数。
- 统一结果对象。
- 注册表查找和执行入口。

本章只做最小版本：先实现注册、查找、调用和未知工具错误。

## 建议接口

新增文件：

```text
micode/src/micode/tool_registry.py
```

建议结构：

```python
@dataclass
class ToolResult:
    ok: bool
    output: str
    metadata: dict

@dataclass
class ToolDefinition:
    name: str
    description: str
    handler: Callable[[dict], ToolResult]

class ToolRegistry:
    def register(self, tool: ToolDefinition) -> None:
        ...

    def get(self, name: str) -> ToolDefinition:
        ...

    def call(self, name: str, args: dict) -> ToolResult:
        ...
```

## 要修改的文件

```text
micode/src/micode/tool_registry.py
micode/tests/test_tool_registry.py
docs/SDD.md
```

这一章先不改 `agent.py`，避免同时改工具契约和 Agent loop。

## 验收标准

1. 可以注册工具。
2. 可以按名称查找工具。
3. 可以通过 registry 调用工具。
4. 未知工具返回清晰错误。
5. 重复注册同名工具时抛出明确异常。
6. 全量测试通过。

## 做了什么

- 新增 `tool_registry.py`，定义 `ToolResult`、`ToolDefinition` 和 `ToolRegistry`。
- 支持工具注册、按名称查找、按名称调用和工具名列表。
- 未知工具返回 `ok=False` 的 `ToolResult`，方便后续 Agent 写入 trace。
- 重复注册同名工具时抛出 `DuplicateToolName`。
- 新增 `create_default_tool_registry(workspace)`，先注册 `list_files`、`read_file`、`replace_text` 和 `run_shell`。
- 补充 `test_tool_registry.py`，覆盖注册、查找、调用、未知工具、重复注册和默认工具集合。

## 思考题

为什么 Day 32 先不直接把 Agent 全部改成 Tool Registry？

提示：先稳定工具抽象，再改调用方，风险更小，也更容易测试。
