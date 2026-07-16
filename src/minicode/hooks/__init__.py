from minicode.hooks.default import create_default_hook_manager
from minicode.hooks.manager import HookManager, HookRegistration
from minicode.hooks.models import (
    HookAction,
    HookContext,
    HookDispatchResult,
    HookEvent,
    HookResult,
)
from minicode.hooks.permission import PermissionHook
from minicode.hooks.subagent_approval import SubAgentApprovalHook
from minicode.hooks.tool_self_check import ToolSelfCheckHook

__all__ = [
    "HookAction",
    "HookContext",
    "HookDispatchResult",
    "HookEvent",
    "HookManager",
    "HookRegistration",
    "HookResult",
    "PermissionHook",
    "SubAgentApprovalHook",
    "ToolSelfCheckHook",
    "create_default_hook_manager",
]
