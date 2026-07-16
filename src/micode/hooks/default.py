from micode.hooks.manager import HookManager
from micode.hooks.models import HookEvent
from micode.hooks.permission import PermissionHook
from micode.hooks.security import SecurityBoundaryHook
from micode.hooks.subagent_approval import SubAgentApprovalHook
from micode.hooks.tool_self_check import ToolSelfCheckHook
from micode.permissions import PermissionReviewer
from micode.human_review import HumanReviewStore
from micode.security import SecurityState


def create_default_hook_manager(
    permission_reviewer: PermissionReviewer = None,
    manager: HookManager = None,
    human_review_store: HumanReviewStore = None,
    security_state: SecurityState = None,
) -> HookManager:
    """装配默认 Hook；权限 Hook 优先运行，避免副作用提前发生。"""
    manager = manager or HookManager()
    actual_review_store = (
        human_review_store
        or manager.human_review_store
        or HumanReviewStore()
    )
    actual_security_state = (
        security_state
        or manager.security_state
        or SecurityState()
    )
    manager.human_review_store = actual_review_store
    manager.security_state = actual_security_state
    if not manager.has_handler_type(HookEvent.BEFORE_TOOL_CALL, PermissionHook):
        manager.register(
            HookEvent.BEFORE_TOOL_CALL,
            PermissionHook(
                permission_reviewer,
                review_store=actual_review_store,
                security_state=actual_security_state,
            ),
            name="permission",
            priority=1000,
        )
    if not manager.has_handler_type(HookEvent.BEFORE_TOOL_CALL, SubAgentApprovalHook):
        manager.register(
            HookEvent.BEFORE_TOOL_CALL,
            SubAgentApprovalHook(permission_reviewer),
            name="subagent_approval",
            priority=900,
        )
    if not manager.has_handler_type(HookEvent.BEFORE_TOOL_CALL, ToolSelfCheckHook):
        self_check = ToolSelfCheckHook()
        manager.register(
            HookEvent.BEFORE_TOOL_CALL,
            self_check,
            name="tool_self_check",
            priority=950,
        )
        manager.register(
            HookEvent.AFTER_TOOL_CALL,
            self_check,
            name="tool_self_check",
            priority=950,
        )
    if not manager.has_handler_type(HookEvent.AFTER_TOOL_CALL, SecurityBoundaryHook):
        manager.register(
            HookEvent.AFTER_TOOL_CALL,
            SecurityBoundaryHook(actual_security_state),
            name="security_boundary",
            priority=1000,
        )
    return manager
