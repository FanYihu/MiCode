from minicode.hooks.manager import HookManager
from minicode.hooks.models import HookEvent
from minicode.hooks.permission import PermissionHook
from minicode.hooks.subagent_approval import SubAgentApprovalHook
from minicode.hooks.tool_self_check import ToolSelfCheckHook
from minicode.permissions import PermissionReviewer


def create_default_hook_manager(
    permission_reviewer: PermissionReviewer = None,
    manager: HookManager = None,
) -> HookManager:
    """装配默认 Hook；权限 Hook 优先运行，避免副作用提前发生。"""
    manager = manager or HookManager()
    if not manager.has_handler_type(HookEvent.BEFORE_TOOL_CALL, PermissionHook):
        manager.register(
            HookEvent.BEFORE_TOOL_CALL,
            PermissionHook(permission_reviewer),
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
    return manager
