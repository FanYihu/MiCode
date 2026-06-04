from dataclasses import dataclass, field
from typing import Callable, Optional

from minicode.file_tools import FileTools
from minicode.permissions import PermissionDecision, PermissionReviewer
from minicode.skills import format_skill_for_prompt, load_project_skill
from minicode.shell_tools import ShellTools
from minicode.workspace import Workspace


RESULT_SUMMARY_LIMIT = 200


class DuplicateToolName(ValueError):
    """注册表中已经存在同名工具。"""


@dataclass
class ToolResult:
    """工具调用的统一返回值，后续 trace 和 Agent 都可以复用。"""

    ok: bool
    output: str
    metadata: dict = field(default_factory=dict)


@dataclass
class ToolDefinition:
    """一个可注册工具的最小定义。"""

    name: str
    description: str
    handler: Callable[[dict], ToolResult]
    permission_checker: Optional[Callable[[dict], Optional[ToolResult]]] = None


class ToolRegistry:
    """轻量工具注册表，负责工具注册、查找和统一调用。"""

    def __init__(self) -> None:
        self._tools: dict[str, ToolDefinition] = {}

    def register(self, tool: ToolDefinition) -> None:
        """注册工具；同名工具不允许覆盖，避免隐藏错误。"""
        if tool.name in self._tools:
            raise DuplicateToolName(f"tool already registered: {tool.name}")

        self._tools[tool.name] = tool

    def get(self, name: str) -> ToolDefinition:
        """按名称获取工具；未知工具抛出 KeyError，适合测试和内部使用。"""
        return self._tools[name]

    def list_names(self) -> list[str]:
        """返回当前已注册工具名，保持注册顺序便于调试。"""
        return list(self._tools.keys())

    def describe_tools(self) -> list[str]:
        """生成 prompt 可用的工具说明行。"""
        return [
            f"- {tool.name}: {tool.description}"
            for tool in self._tools.values()
        ]

    def call(self, name: str, args: dict) -> ToolResult:
        """调用工具；未知工具用失败结果表达，方便 Agent 后续记录进 trace。"""
        tool = self._tools.get(name)
        if tool is None:
            return ToolResult(
                ok=False,
                output=f"Unknown tool: {name}",
                metadata=_build_tool_metadata(
                    tool_name=name,
                    args=args,
                    ok=False,
                    output=f"Unknown tool: {name}",
                    metadata={"error": "unknown_tool"},
                ),
            )

        try:
            if tool.permission_checker is not None:
                permission_result = tool.permission_checker(args)
                if permission_result is not None:
                    permission_result.metadata = _build_tool_metadata(
                        tool_name=name,
                        args=args,
                        ok=permission_result.ok,
                        output=permission_result.output,
                        metadata=permission_result.metadata,
                    )
                    return permission_result

            result = tool.handler(args)
        except Exception as error:
            # 工具层异常转成 ToolResult，避免单个工具把 Agent loop 打崩。
            output = f"{type(error).__name__}: {error}"
            return ToolResult(
                ok=False,
                output=output,
                metadata=_build_tool_metadata(
                    tool_name=name,
                    args=args,
                    ok=False,
                    output=output,
                    metadata={"error": type(error).__name__},
                ),
            )

        result.metadata = _build_tool_metadata(
            tool_name=name,
            args=args,
            ok=result.ok,
            output=result.output,
            metadata=result.metadata,
        )
        return result


def create_default_tool_registry(workspace: Workspace) -> ToolRegistry:
    """基于当前 Workspace 创建默认工具集合。"""
    from minicode.git_tools import GitTools

    file_tools = FileTools(workspace)
    git_tools = GitTools(workspace)
    shell_tools = ShellTools(workspace)
    reviewer = PermissionReviewer()
    registry = ToolRegistry()

    registry.register(
        ToolDefinition(
            name="list_files",
            description="List files in the current workspace.",
            handler=lambda args: ToolResult(
                ok=True,
                output="\n".join(workspace.list_files()),
                metadata={"files": workspace.list_files()},
            ),
        )
    )
    registry.register(
        ToolDefinition(
            name="read_file",
            description="Read a UTF-8 text file from the workspace.",
            handler=lambda args: ToolResult(
                ok=True,
                output=file_tools.read_file(args["path"]),
                metadata={"path": args["path"]},
            ),
        )
    )
    registry.register(
        ToolDefinition(
            name="replace_text",
            description="Replace the first exact text match in a workspace file.",
            handler=lambda args: ToolResult(
                ok=True,
                output=file_tools.replace_text(args["path"], args["old"], args["new"]),
                metadata={"path": args["path"]},
            ),
        )
    )
    registry.register(
        ToolDefinition(
            name="run_shell",
            description="Run a shell command inside the workspace.",
            handler=lambda args: _run_shell_tool(shell_tools, args),
            permission_checker=lambda args: _check_shell_permission(reviewer, args),
        )
    )
    registry.register(
        ToolDefinition(
            name="git_status",
            description="Show git status --short for the current workspace.",
            handler=lambda args: git_tools.status(),
        )
    )
    registry.register(
        ToolDefinition(
            name="git_diff",
            description="Show git diff for the current workspace.",
            handler=lambda args: git_tools.diff(),
        )
    )
    registry.register(
        ToolDefinition(
            name="load_skill",
            description="Load the full content of a project Skill by name.",
            handler=lambda args: _load_skill_tool(workspace, args),
        )
    )

    return registry


def _check_shell_permission(
    reviewer: PermissionReviewer,
    args: dict,
) -> Optional[ToolResult]:
    """在 shell 工具执行前做权限审核；允许时返回 None。"""
    review = reviewer.review_shell_command(args["command"])
    if review.decision == PermissionDecision.ALLOW:
        return None

    return ToolResult(
        ok=False,
        output="权限不足，无法运行命令",
        metadata={
            "decision": review.decision.value,
            "review_message": review.review_message,
            "error": review.reason,
        },
    )


def _run_shell_tool(shell_tools: ShellTools, args: dict) -> ToolResult:
    """把 ShellResult 适配为 ToolResult，先保持输出和 metadata 简单稳定。"""
    result = shell_tools.run(args["command"])
    return ToolResult(
        ok=result.exit_code == 0 and not result.timed_out,
        output=result.stdout or result.stderr,
        metadata={
            "command": args["command"],
            "exit_code": result.exit_code,
            "timed_out": result.timed_out,
        },
    )


def _load_skill_tool(workspace: Workspace, args: dict) -> ToolResult:
    """按名称加载完整 Skill 内容，供 Agent 按需放入 observations。"""
    name = args["name"]
    skill = load_project_skill(workspace, name)
    if skill is None:
        return ToolResult(
            ok=False,
            output=f"Unknown skill: {name}",
            metadata={"error": "unknown_skill", "name": name},
        )

    output = "\n".join(
        [
            f"SKILL: {skill.name}",
            f"DESCRIPTION: {skill.description}",
            "",
            "CONTENT:",
            format_skill_for_prompt(skill),
        ]
    )
    return ToolResult(
        ok=True,
        output=output,
        metadata={"name": skill.name},
    )


def _build_tool_metadata(
    tool_name: str,
    args: dict,
    ok: bool,
    output: str,
    metadata: dict,
) -> dict:
    """生成统一工具 trace metadata；工具特有信息统一收进 details。"""
    error = "" if ok else str(metadata.get("error") or output)
    details = {
        key: value
        for key, value in metadata.items()
        if key != "error"
    }
    normalized = {
        "tool": tool_name,
        "args": dict(args),
        "ok": ok,
        "result_summary": _summarize_tool_output(output),
        "error": error,
        "details": details,
    }
    return normalized


def _summarize_tool_output(output: str) -> str:
    """给 metadata 使用的短摘要；完整输出继续放在 ToolResult.output。"""
    if len(output) <= RESULT_SUMMARY_LIMIT:
        return output

    return f"{output[:RESULT_SUMMARY_LIMIT]}... [truncated]"
