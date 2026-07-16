from micode.hooks.models import HookContext, HookResult
from micode.human_review import HumanReviewError, HumanReviewStore
from micode.permissions import (
    PermissionDecision,
    PermissionResult,
    PermissionReviewer,
)
from micode.security import SecurityState


class PermissionHook:
    """把 PermissionReviewer 适配到 before_tool_call 生命周期。"""

    def __init__(
        self,
        reviewer: PermissionReviewer = None,
        review_store: HumanReviewStore = None,
        security_state: SecurityState = None,
    ) -> None:
        self.reviewer = reviewer or PermissionReviewer()
        self.review_store = review_store or HumanReviewStore()
        self.security_state = security_state or SecurityState()

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
        elif getattr(context.tool, "capabilities", None) is not None and (
            context.tool.capabilities.requires_review
        ):
            review = PermissionResult(
                decision=PermissionDecision.REVIEW,
                reason="工具能力声明要求人工审核",
                review_message=f"是否允许调用工具：{context.tool_name}",
                rule_name="tool_requires_review",
                layer="review",
            )
            blocked_output = "需要人工审核，工具调用已暂停"
        else:
            review = None
            blocked_output = "需要人工审核，工具调用已暂停"

        capabilities = getattr(context.tool, "capabilities", None)
        contaminated_review = self.security_state.requires_review(
            bool(capabilities and capabilities.has_side_effects)
        )
        if review is None and not contaminated_review:
            return None
        if review is None:
            review = PermissionResult(
                decision=PermissionDecision.REVIEW,
                reason="不可信上下文污染后，副作用工具必须升级人工审核",
                review_message=f"污染上下文后是否允许调用：{context.tool_name}",
                rule_name="contaminated_context_write_review",
                layer="review",
            )

        # deny 是不可绕过边界，即使调用方带有历史批准也必须拒绝。
        if review.decision == PermissionDecision.DENY:
            return HookResult.block(
                blocked_output,
                metadata={
                    "decision": review.decision.value,
                    "permission_reason": review.reason,
                    "review_message": review.review_message,
                    "permission_rule": review.rule_name,
                    "permission_layer": review.layer,
                    "error": review.reason,
                },
            )

        review_id = str(context.metadata.get("review_id") or "")
        if review_id:
            try:
                request = self.review_store.authorize(
                    review_id,
                    context.tool_name,
                    context.args,
                )
            except HumanReviewError as error:
                return HookResult.block(
                    "人工审核无效，无法恢复工具调用",
                    metadata={
                        "decision": "deny",
                        "error": "human_review_invalid",
                        "failure_class": "human_review_invalid",
                        "recoverable": False,
                        "review_id": review_id,
                        "review_error": str(error),
                    },
                )
            return HookResult.continue_with(
                metadata={
                    "decision": "allow",
                    "permission_reason": "人工审核已批准并消费",
                    "permission_rule": "human_review_approved",
                    "permission_layer": "human",
                    "human_review": request.to_dict(),
                }
            )

        if review.decision == PermissionDecision.ALLOW and not contaminated_review:
            return HookResult.continue_with(
                metadata={
                    "decision": review.decision.value,
                    "permission_reason": review.reason,
                    "review_message": review.review_message,
                    "permission_rule": review.rule_name,
                    "permission_layer": review.layer,
                }
            )

        reason = (
            "不可信上下文污染后，副作用工具必须升级人工审核"
            if contaminated_review
            else review.reason
        )
        request = self.review_store.create(
            context.tool_name,
            context.args,
            reason=reason,
            run_id=str(context.metadata.get("run_id") or ""),
            session_id=str(context.metadata.get("session_id") or ""),
        )

        metadata = {
            "decision": PermissionDecision.REVIEW.value,
            "permission_reason": reason,
            "review_message": review.review_message,
            "permission_rule": (
                "contaminated_context_write_review"
                if contaminated_review
                else review.rule_name
            ),
            "permission_layer": review.layer,
            "error": "human_review_required",
            "failure_class": "human_review_required",
            "recoverable": True,
            "retry_hint": "Approve the review request, then resume it by review_id.",
            "review_id": request.id,
            "human_review": request.to_dict(),
            "pause_required": True,
        }
        return HookResult.block(
            blocked_output,
            metadata=metadata,
        )
