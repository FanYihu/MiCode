from micode.hooks.models import HookContext, HookEvent, HookResult
from micode.security import SecurityState


class SecurityBoundaryHook:
    """在工具返回后更新当前运行的不可信上下文状态。"""

    def __init__(self, state: SecurityState) -> None:
        self.state = state

    def __call__(self, context: HookContext) -> HookResult:
        if context.event != HookEvent.AFTER_TOOL_CALL or context.result is None:
            return None
        self.state.observe(context.tool_name, context.result)
        return HookResult.continue_with(
            metadata={"security_state": self.state.snapshot()}
        )
