import json

from minicode.hooks.models import HookContext, HookResult
from minicode.permissions import PermissionDecision, PermissionReviewer


class SubAgentApprovalHook:
    """主 Agent 对 SubAgent 写入任务的审批 Hook。

    PermissionHook 只能看到普通 write_file/replace_text 工具；Implementer
    SubAgent 的写入发生在 run_subagent 内部，所以这里在执行前单独审查
    role=implementer 的 operations。
    """

    def __init__(self, reviewer: PermissionReviewer = None) -> None:
        self.reviewer = reviewer or PermissionReviewer()

    def __call__(self, context: HookContext) -> HookResult:
        """只审批 run_subagent 的 implementer 写入任务。"""
        if context.tool_name != "run_subagent":
            return None

        role = str(context.args.get("role") or "").strip()
        if role != "implementer":
            return HookResult.continue_with(
                metadata={
                    "subagent_approval": {
                        "required": False,
                        "role": role,
                        "status": "not_required",
                    }
                }
            )

        operations, error = _load_operations_from_args(context.args)
        if error:
            return HookResult.block(
                "无法审批子 Agent 写入：缺少可审计 operations",
                metadata={
                    "error": "subagent_operations_not_reviewable",
                    "subagent_approval": {
                        "required": True,
                        "role": role,
                        "status": "blocked",
                        "reason": error,
                    },
                },
            )

        approval = self._review_operations(operations)
        if approval["status"] != "approved":
            return HookResult.block(
                "子 Agent 写入未获批准",
                metadata={
                    "error": "subagent_write_not_approved",
                    "subagent_approval": approval,
                },
            )

        return HookResult.continue_with(
            metadata={"subagent_approval": approval}
        )

    def _review_operations(self, operations: list[dict]) -> dict:
        """逐个路径复用 PermissionReviewer，并聚合成审批记录。"""
        decisions = []
        blocked = False
        for operation in operations:
            path = str(operation.get("path") or "")
            review = self.reviewer.review_file_write(path)
            decision = {
                "operation": str(operation.get("type") or operation.get("tool") or ""),
                "path": path,
                "decision": review.decision.value,
                "reason": review.reason,
                "review_message": review.review_message,
                "rule": review.rule_name,
                "layer": review.layer,
            }
            decisions.append(decision)
            if review.decision != PermissionDecision.ALLOW:
                blocked = True

        return {
            "required": True,
            "role": "implementer",
            "status": "blocked" if blocked else "approved",
            "decisions": decisions,
        }


def _load_operations_from_args(args: dict) -> tuple[list[dict], str]:
    """从 run_subagent args 中读取 operations。"""
    metadata = args.get("metadata")
    if isinstance(metadata, dict) and isinstance(metadata.get("operations"), list):
        return metadata["operations"], ""

    payload, error = _extract_json_object(str(args.get("context") or ""))
    if error:
        return [], error
    operations = payload.get("operations")
    if not isinstance(operations, list) or not operations:
        return [], "operations must be a non-empty list"
    if not all(isinstance(operation, dict) for operation in operations):
        return [], "each operation must be an object"
    return operations, ""


def _extract_json_object(text: str) -> tuple[dict, str]:
    """从文本中提取第一个 JSON object。"""
    stripped = text.strip()
    if not stripped:
        return {}, "context is empty"

    decoder = json.JSONDecoder()
    for index, char in enumerate(stripped):
        if char != "{":
            continue
        try:
            payload, _ = decoder.raw_decode(stripped[index:])
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            return payload, ""
    return {}, "context must contain a JSON object"
