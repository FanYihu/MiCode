import threading
import time
from dataclasses import dataclass
from typing import Callable

from minicode.hooks.models import (
    HookAction,
    HookContext,
    HookDispatchResult,
    HookEvent,
    HookResult,
)


HookHandler = Callable[[HookContext], HookResult]


@dataclass
class HookRegistration:
    """保存一个 Hook 的注册信息和轻量运行统计。"""

    event: HookEvent
    handler: HookHandler
    name: str
    priority: int = 0
    enabled: bool = True
    call_count: int = 0
    total_duration_ms: float = 0.0


class HookManager:
    """同步 Hook 管理器，服务于当前同步 Tool Registry。"""

    def __init__(self) -> None:
        self._hooks = {event: [] for event in HookEvent}
        self._lock = threading.RLock()

    def register(
        self,
        event: HookEvent,
        handler: HookHandler,
        name: str = "",
        priority: int = 0,
    ) -> Callable[[], None]:
        """注册 Hook，并返回可调用的注销函数。"""
        registration = HookRegistration(
            event=event,
            handler=handler,
            name=name or getattr(handler, "__name__", handler.__class__.__name__),
            priority=priority,
        )
        with self._lock:
            self._hooks[event].append(registration)
            self._hooks[event].sort(key=lambda item: item.priority, reverse=True)

        def unregister() -> None:
            with self._lock:
                if registration in self._hooks[event]:
                    self._hooks[event].remove(registration)

        return unregister

    def emit(self, context: HookContext) -> HookDispatchResult:
        """按优先级同步触发 Hook；调用前 Hook 异常默认阻断工具。"""
        with self._lock:
            registrations = list(self._hooks[context.event])

        dispatch = HookDispatchResult(context=context)
        for registration in registrations:
            if not registration.enabled:
                continue
            started = time.perf_counter()
            try:
                result = registration.handler(context)
                if result is None:
                    continue
                if result.args is not None:
                    context.args = dict(result.args)
                dispatch.metadata.update(result.metadata)
                execution = {
                    "event": context.event.value,
                    "hook": registration.name,
                    "action": result.action.value,
                    "ok": True,
                }
                dispatch.executions.append(execution)
                if result.action == HookAction.BLOCK:
                    dispatch.blocked = True
                    dispatch.output = result.output
                    break
            except Exception as error:
                execution = {
                    "event": context.event.value,
                    "hook": registration.name,
                    "action": "error",
                    "ok": False,
                    "error": f"{type(error).__name__}: {error}",
                }
                dispatch.executions.append(execution)
                dispatch.metadata.setdefault("hook_errors", []).append(execution)
                # 调用前 Hook 可能承担权限职责，因此异常时必须 fail closed。
                if context.event == HookEvent.BEFORE_TOOL_CALL:
                    dispatch.blocked = True
                    dispatch.output = f"Hook execution failed: {registration.name}"
                    dispatch.metadata["error"] = "hook_execution_failed"
                    break
            finally:
                duration_ms = (time.perf_counter() - started) * 1000
                with self._lock:
                    registration.call_count += 1
                    registration.total_duration_ms += duration_ms

        return dispatch

    def stats(self) -> dict:
        """返回 Hook 注册和调用统计，便于后续 review。"""
        with self._lock:
            registrations = [
                registration
                for hooks in self._hooks.values()
                for registration in hooks
            ]
        return {
            "registered": len(registrations),
            "enabled": sum(1 for item in registrations if item.enabled),
            "calls": sum(item.call_count for item in registrations),
            "duration_ms": round(
                sum(item.total_duration_ms for item in registrations),
                3,
            ),
        }

    def has_hook(self, event: HookEvent, name: str) -> bool:
        """检查指定事件是否已有同名 Hook。"""
        with self._lock:
            return any(
                registration.name == name
                for registration in self._hooks[event]
            )

    def has_handler_type(self, event: HookEvent, handler_type: type) -> bool:
        """按处理器类型检查 Hook，避免仅凭名称判断安全组件。"""
        with self._lock:
            return any(
                isinstance(registration.handler, handler_type)
                for registration in self._hooks[event]
            )
