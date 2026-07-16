from minicode.subagents.models import (
    SUBAGENT_FAILED,
    SubAgentExecutor,
    SubAgentPolicy,
    SubAgentResult,
    SubAgentTask,
)
from minicode.tools.registry import ToolDefinition, ToolResult
from typing import Callable, Optional


def create_subagent_tool(
    executor: SubAgentExecutor,
    policy: SubAgentPolicy = None,
    parent_run_id: str = "",
    parent_run_id_provider: Optional[Callable[[], str]] = None,
) -> ToolDefinition:
    """把 SubAgent executor 适配成统一 ToolDefinition。"""
    actual_policy = policy or SubAgentPolicy()
    return ToolDefinition(
        name="run_subagent",
        description=(
            "Delegate a bounded task to a controlled subagent and return its summary."
        ),
        parameters={
            "type": "object",
            "properties": {
                "role": {
                    "type": "string",
                    "enum": list(actual_policy.allowed_roles),
                    "description": "Subagent role selected for this task.",
                },
                "objective": {
                    "type": "string",
                    "description": "One concrete objective for the subagent.",
                },
                "context": {
                    "type": "string",
                    "description": "Minimal context needed to execute the objective.",
                },
                "max_steps": {
                    "type": "integer",
                    "minimum": 1,
                    "description": "Requested step limit; runtime policy may reduce it.",
                },
            },
            "required": ["role", "objective"],
            "additionalProperties": False,
        },
        # SubAgent 可能调用写工具，默认必须串行执行。
        parallel_safe=False,
        handler=lambda args: run_subagent_tool(
            executor,
            actual_policy,
            args,
            parent_run_id=(
                parent_run_id_provider()
                if parent_run_id_provider is not None
                else parent_run_id
            ),
        ),
    )


def run_subagent_tool(
    executor: SubAgentExecutor,
    policy: SubAgentPolicy,
    args: dict,
    parent_run_id: str = "",
) -> ToolResult:
    """验证边界、执行子任务，并只把摘要返回主 Agent。"""
    role = str(args.get("role") or "").strip()
    objective = str(args.get("objective") or "").strip()
    if role not in policy.allowed_roles:
        return ToolResult(
            ok=False,
            output=f"Unsupported subagent role: {role}",
            metadata={"error": "unsupported_subagent_role", "role": role},
        )
    if not objective:
        return ToolResult(
            ok=False,
            output="Subagent objective is required",
            metadata={"error": "missing_subagent_objective", "role": role},
        )

    task = SubAgentTask(
        role=role,
        objective=objective,
        context=str(args.get("context") or ""),
        # 工具和路径来自主 Agent policy，不接受模型自行传入。
        allowed_tools=policy.tools_for(role),
        allowed_paths=list(policy.allowed_paths),
        max_steps=policy.clamp_steps(args.get("max_steps")),
        parent_run_id=parent_run_id,
    )
    result = executor.execute(task)
    validation_error = validate_subagent_result(task, result)
    if validation_error:
        return ToolResult(
            ok=False,
            output=validation_error,
            metadata={
                "error": "invalid_subagent_result",
                "subagent_task": task.to_dict(),
            },
        )

    return ToolResult(
        ok=result.ok,
        # 主 Agent observation 只接收摘要；证据和 artifact 进入 metadata。
        output=result.summary,
        metadata={
            "error": "" if result.ok else "subagent_failed",
            "subagent_task": task.to_dict(),
            "subagent_result": result.to_dict(),
        },
    )


def validate_subagent_result(
    task: SubAgentTask,
    result: SubAgentResult,
) -> str:
    """验证 executor 没有返回错任务或错角色的结果。"""
    if not isinstance(result, SubAgentResult):
        return "Subagent executor must return SubAgentResult"
    if result.task_id != task.id:
        return "Subagent result task_id does not match delegated task"
    if result.role != task.role:
        return "Subagent result role does not match delegated role"
    if result.status not in {"completed", SUBAGENT_FAILED}:
        return f"Unsupported subagent result status: {result.status}"
    if not result.summary.strip():
        return "Subagent result summary is required"
    return ""
