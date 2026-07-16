from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional


class HookEvent(str, Enum):
    """MiniCode 当前支持的工具生命周期事件。"""

    BEFORE_TOOL_CALL = "before_tool_call"
    AFTER_TOOL_CALL = "after_tool_call"
    TOOL_ERROR = "tool_error"


class HookAction(str, Enum):
    """Hook 对当前生命周期的控制动作。"""

    CONTINUE = "continue"
    BLOCK = "block"


@dataclass
class HookContext:
    """HookContext 是 Hook 与 Tool Registry 之间的稳定数据契约。"""

    event: HookEvent
    tool_name: str
    args: dict
    tool: Any = None
    result: Any = None
    error: Optional[Exception] = None
    metadata: dict = field(default_factory=dict)


@dataclass
class HookResult:
    """HookResult 可放行、改写参数或阻断本次工具调用。"""

    action: HookAction = HookAction.CONTINUE
    args: Optional[dict] = None
    output: str = ""
    metadata: dict = field(default_factory=dict)

    @classmethod
    def continue_with(
        cls,
        args: Optional[dict] = None,
        metadata: Optional[dict] = None,
    ) -> "HookResult":
        """继续工具生命周期，并可选择替换参数。"""
        return cls(
            action=HookAction.CONTINUE,
            args=args,
            metadata=metadata or {},
        )

    @classmethod
    def block(
        cls,
        output: str,
        metadata: Optional[dict] = None,
    ) -> "HookResult":
        """阻断工具调用，并返回可写入 ToolResult 的信息。"""
        return cls(
            action=HookAction.BLOCK,
            output=output,
            metadata=metadata or {},
        )


@dataclass
class HookDispatchResult:
    """一次 Hook 事件派发后的聚合结果。"""

    context: HookContext
    blocked: bool = False
    output: str = ""
    metadata: dict = field(default_factory=dict)
    executions: list[dict] = field(default_factory=list)

