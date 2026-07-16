from typing import Callable, Optional

from micode.checkpoints import CheckpointStore
from micode.hooks import HookManager, create_default_hook_manager
from micode.human_review import HumanReviewStore
from micode.security import SecurityState, TrustLevel
from micode.mcp.config import MCPServerConfig
from micode.mcp.integration import MCPManager, create_mcp_tool_bundle
from micode.tools.file import FileTools
from micode.tools.git import GitTools
from micode.skills import Skill
from micode.subagents import SubAgentExecutor, SubAgentPolicy, create_subagent_tool
from micode.tools.artifact import create_read_artifact_tool
from micode.tools.shell import ShellTools, run_shell_tool
from micode.tools.skill import load_skill_tool
from micode.tools.registry import (
    ToolCapabilities,
    ToolDefinition,
    ToolRegistry,
    ToolResult,
)
from micode.workspace import Workspace


def create_default_tool_registry(
    workspace: Workspace,
    external_skills: Optional[list[Skill]] = None,
    artifact_dir: str = ".micode/artifacts",
    hook_manager: Optional[HookManager] = None,
    subagent_executor: Optional[SubAgentExecutor] = None,
    subagent_policy: Optional[SubAgentPolicy] = None,
    subagent_parent_run_id_provider: Optional[Callable[[], str]] = None,
    human_review_store: Optional[HumanReviewStore] = None,
    security_state: Optional[SecurityState] = None,
    mcp_server_configs: Optional[dict[str, MCPServerConfig]] = None,
    mcp_manager: Optional[MCPManager] = None,
) -> ToolRegistry:
    """基于当前 Workspace 装配默认工具集合。"""
    file_tools = FileTools(workspace)
    git_tools = GitTools(workspace)
    shell_tools = ShellTools(workspace)
    review_store = human_review_store or HumanReviewStore(
        str(workspace.resolve_path(".micode/human-reviews"))
    )
    registry = ToolRegistry(
        hook_manager=create_default_hook_manager(
            manager=hook_manager,
            human_review_store=review_store,
            security_state=security_state,
        ),
        checkpoint_store=CheckpointStore(workspace),
    )

    registry.register(
        ToolDefinition(
            name="list_files",
            description="List files in the current workspace.",
            parallel_safe=True,
            capabilities=ToolCapabilities(read_only=True),
            output_trust=TrustLevel.LOCAL.value,
            source="workspace:file-tree",
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
            parallel_safe=True,
            capabilities=ToolCapabilities(read_only=True),
            output_trust=TrustLevel.LOCAL.value,
            source="workspace:file",
            parameters=_object_schema(
                {"path": {"type": "string", "description": "Workspace-relative file path."}},
                required=["path"],
            ),
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
            capabilities=ToolCapabilities(
                writes_workspace=True,
                reversible=True,
            ),
            output_trust=TrustLevel.LOCAL.value,
            source="workspace:diff",
            parameters=_object_schema(
                {
                    "path": {"type": "string"},
                    "old": {"type": "string"},
                    "new": {"type": "string"},
                },
                required=["path", "old", "new"],
            ),
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
            capabilities=ToolCapabilities(
                runs_commands=True,
                writes_workspace=True,
                external_io=True,
            ),
            output_trust=TrustLevel.UNTRUSTED.value,
            source="subprocess:shell",
            parameters=_object_schema(
                {"command": {"type": "string", "description": "Shell command to run."}},
                required=["command"],
            ),
            handler=lambda args: run_shell_tool(shell_tools, args),
        )
    )
    registry.register(
        ToolDefinition(
            name="git_status",
            description="Show git status --short for the current workspace.",
            parallel_safe=True,
            capabilities=ToolCapabilities(read_only=True),
            output_trust=TrustLevel.LOCAL.value,
            source="subprocess:git",
            handler=lambda args: git_tools.status(),
        )
    )
    registry.register(
        ToolDefinition(
            name="write_file",
            description="Write content to a file in the workspace.",
            capabilities=ToolCapabilities(
                writes_workspace=True,
                reversible=True,
            ),
            parameters=_object_schema(
                {
                    "path": {"type": "string"},
                    "content": {"type": "string"},
                },
                required=["path", "content"],
            ),
            handler=lambda args: write_file_tool(file_tools, args),
        )
    )
    registry.register(
        ToolDefinition(
            name="git_diff",
            description="Show git diff for the current workspace.",
            parallel_safe=True,
            capabilities=ToolCapabilities(read_only=True),
            output_trust=TrustLevel.LOCAL.value,
            source="subprocess:git",
            handler=lambda args: git_tools.diff(),
        )
    )
    registry.register(
        ToolDefinition(
            name="load_skill",
            description="Load the full content of a Skill by name.",
            parallel_safe=True,
            capabilities=ToolCapabilities(read_only=True),
            source="skill-store",
            parameters=_object_schema(
                {"name": {"type": "string", "description": "Skill name."}},
                required=["name"],
            ),
            handler=lambda args: load_skill_tool(workspace, args, external_skills or []),
        )
    )
    registry.register(create_read_artifact_tool(artifact_dir))
    if subagent_executor is not None:
        registry.register(
            create_subagent_tool(
                subagent_executor,
                policy=subagent_policy,
                parent_run_id_provider=subagent_parent_run_id_provider,
            )
        )

    if mcp_server_configs:
        bundle = create_mcp_tool_bundle(
            mcp_server_configs,
            str(workspace.root),
            manager=mcp_manager,
        )
        for tool in bundle.tools:
            registry.register(tool)
        registry.mcp_manager = bundle.manager
        registry.register_disposer(bundle.manager.close)

    return registry


def _object_schema(properties: dict, required: Optional[list[str]] = None) -> dict:
    """构建严格 object schema，避免每个工具重复写公共字段。"""
    return {
        "type": "object",
        "properties": properties,
        "required": required or [],
        "additionalProperties": False,
    }


def write_file_tool(file_tools: FileTools, args: dict) -> ToolResult:
    """执行文件写入并适配成统一 ToolResult。"""
    file_tools.write_file(args["path"], args["content"])
    return ToolResult(
        ok=True,
        output=f"Wrote {args['path']}",
        metadata={"path": args["path"]},
    )
