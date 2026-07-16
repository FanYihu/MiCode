from micode.hooks.models import HookContext, HookResult
from micode.permissions import PermissionDecision, PermissionReviewer


class PermissionHook:
    """把 PermissionReviewer 适配到 before_tool_call 生命周期。"""

    def __init__(self, reviewer: PermissionReviewer = None) -> None:
        self.reviewer = reviewer or PermissionReviewer()

    def __call__(self, context: HookContext) -> HookResult:
        """只审核有副作用且已有权限规则的工具。"""
        if context.tool_name == "run_shell":
            review = self.reviewer.review_shell_command(
                str(context.args.get("command", ""))
            )
            blocked_output = "权限不足，无法运行命令"
        elif context.tool_name in {"write_file", "replace_text"}:
            review = self.reviewer.review_file_write(
                str(context.args.get("path", ""))
            )
            blocked_output = "权限不足，无法写入文件"
        else:
            return None

        metadata = {
            "decision": review.decision.value,
            "permission_reason": review.reason,
            "review_message": review.review_message,
            "permission_rule": review.rule_name,
            "permission_layer": review.layer,
        }
        if review.decision == PermissionDecision.ALLOW:
            return HookResult.continue_with(metadata=metadata)

        return HookResult.block(
            blocked_output,
            metadata={**metadata, "error": review.reason},
        )
