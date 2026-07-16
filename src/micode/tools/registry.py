from dataclasses import asdict, dataclass, field
from typing import Callable, Optional

from micode.hooks.manager import HookManager
from micode.hooks.models import HookContext, HookEvent
from micode.human_review import HumanReviewError
from micode.security import TrustLevel, annotate_tool_result


RESULT_SUMMARY_LIMIT = 200


class DuplicateToolName(ValueError):
    """注册表中已经存在同名工具。"""


@dataclass
class ToolResult:
    """工具调用的统一返回值，后续 trace 和 Agent 都可以复用。"""

    ok: bool
    output: str
    metadata: dict = field(default_factory=dict)
    trust_level: str = ""
    source: str = ""
    content_sha256: str = ""
    injection_risk: dict = field(default_factory=dict)


@dataclass(frozen=True)
class ToolCapabilities:
    """工具的统一能力声明，供并行、权限、审核和 UI 共同消费。"""

    read_only: bool = False
    writes_workspace: bool = False
    runs_commands: bool = False
    external_io: bool = False
    requires_review: bool = False
    reversible: bool = False

    @property
    def has_side_effects(self) -> bool:
        return bool(
            self.writes_workspace
            or self.runs_commands
            or self.requires_review
            or (self.external_io and not self.read_only)
        )

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class ToolDefinition:
    """一个可注册工具的最小定义。"""

    name: str
    description: str
    handler: Callable[[dict], ToolResult]
    # OpenAI-compatible function tool 使用的 JSON Schema。
    parameters: dict = field(
        default_factory=lambda: {
            "type": "object",
            "properties": {},
            "additionalProperties": False,
        }
    )
    # 只有无副作用、彼此独立的工具才能进入并行执行组。
    parallel_safe: bool = False
    capabilities: ToolCapabilities = field(default_factory=ToolCapabilities)
    output_trust: str = TrustLevel.TRUSTED.value
    source: str = "runtime"


@dataclass
class ToolFailure:
    """工具失败的标准分类，帮助 Agent 判断能否恢复。"""

    failure_class: str
    recoverable: bool
    retry_hint: str


class ToolRegistry:
    """轻量工具注册表，负责工具注册、查找和统一调用。"""

    def __init__(self, hook_manager: Optional[HookManager] = None) -> None:
        self._tools: dict[str, ToolDefinition] = {}
        self.hook_manager = hook_manager or HookManager()
        self._disposers = []
        self._closed = False

    def register(self, tool: ToolDefinition) -> None:
        """注册工具；同名工具不允许覆盖，避免隐藏错误。"""
        if tool.name in self._tools:
            raise DuplicateToolName(f"tool already registered: {tool.name}")

        self._tools[tool.name] = tool

    def get(self, name: str) -> ToolDefinition:
        """按名称获取工具；未知工具抛出 KeyError，适合测试和内部使用。"""
        return self._tools[name]

    def list_names(self) -> list[str]:
        """返回当前已注册工具名，保持注册顺序便于调试。"""
        return list(self._tools.keys())

    def describe_tools(self) -> list[str]:
        """生成 prompt 可用的工具说明行。"""
        return [
            f"- {tool.name}: {tool.description}"
            for tool in self._tools.values()
        ]

    def openai_tools(self) -> list[dict]:
        """生成 OpenAI-compatible Chat Completions 的 tools 字段。"""
        return [
            {
                "type": "function",
                "function": {
                    "name": tool.name,
                    "description": tool.description,
                    "parameters": tool.parameters,
                },
            }
            for tool in self._tools.values()
        ]

    def capability_inventory(self) -> list[dict]:
        """返回 UI、readiness 和权限审核可复用的能力清单。"""
        return [
            {
                "name": tool.name,
                "parallel_safe": tool.parallel_safe,
                "capabilities": tool.capabilities.to_dict(),
                "output_trust": tool.output_trust,
                "source": tool.source,
            }
            for tool in self._tools.values()
        ]

    def is_parallel_safe(self, name: str) -> bool:
        """返回工具是否允许和同批其他只读工具并行执行。"""
        tool = self._tools.get(name)
        return bool(tool and tool.parallel_safe)

    def call(
        self,
        name: str,
        args: dict,
        *,
        review_id: str = "",
        run_id: str = "",
        session_id: str = "",
    ) -> ToolResult:
        """调用工具；未知工具用失败结果表达，方便 Agent 后续记录进 trace。"""
        tool = self._tools.get(name)
        if tool is None:
            return _normalize_result(
                name,
                args,
                ToolResult(
                    ok=False,
                    output=f"Unknown tool: {name}",
                    metadata={
                        "error": "unknown_tool",
                        "available_tools": self.list_names(),
                    },
                    trust_level=TrustLevel.TRUSTED.value,
                    source="registry",
                ),
            )

        before = self.hook_manager.emit(
            HookContext(
                event=HookEvent.BEFORE_TOOL_CALL,
                tool_name=name,
                args=dict(args),
                tool=tool,
                metadata={
                    "review_id": review_id,
                    "run_id": run_id,
                    "session_id": session_id,
                },
            )
        )
        actual_args = before.context.args
        if before.blocked:
            return _normalize_result(
                name,
                actual_args,
                ToolResult(
                    ok=False,
                    output=before.output or "Tool call blocked by hook",
                    metadata={
                        **before.metadata,
                        "hooks": before.executions,
                    },
                ),
                tool,
            )

        try:
            result = tool.handler(actual_args)
            if not isinstance(result, ToolResult):
                raise TypeError("tool handler must return ToolResult")
        except Exception as error:
            error_dispatch = self.hook_manager.emit(
                HookContext(
                    event=HookEvent.TOOL_ERROR,
                    tool_name=name,
                    args=actual_args,
                    tool=tool,
                    error=error,
                )
            )
            # 工具层异常转成 ToolResult，避免单个工具把 Agent loop 打崩。
            output = f"{type(error).__name__}: {error}"
            failure = _classify_exception(error)
            return _normalize_result(
                name,
                actual_args,
                ToolResult(
                    ok=False,
                    output=output,
                    metadata={
                        "error": type(error).__name__,
                        "exception_type": type(error).__name__,
                        "failure_class": failure.failure_class,
                        "recoverable": failure.recoverable,
                        "retry_hint": failure.retry_hint,
                        **before.metadata,
                        **error_dispatch.metadata,
                        "hooks": before.executions + error_dispatch.executions,
                    },
                ),
                tool,
            )

        annotate_tool_result(
            result,
            default_trust_level=tool.output_trust,
            default_source=tool.source,
        )

        after = self.hook_manager.emit(
            HookContext(
                event=HookEvent.AFTER_TOOL_CALL,
                tool_name=name,
                args=actual_args,
                tool=tool,
                result=result,
            )
        )
        hook_executions = before.executions + after.executions
        result.metadata = {
            **before.metadata,
            **result.metadata,
            **after.metadata,
        }
        if hook_executions:
            result.metadata["hooks"] = hook_executions
        return _normalize_result(name, actual_args, result, tool)

    def resume(self, review_id: str) -> ToolResult:
        """在人工批准后恢复原工具调用，批准只能消费一次。"""
        store = getattr(self.hook_manager, "human_review_store", None)
        if store is None:
            return ToolResult(
                ok=False,
                output="Human review store is not configured",
                metadata={"error": "human_review_not_configured"},
            )
        try:
            request = store.get(review_id)
        except HumanReviewError as error:
            return ToolResult(
                ok=False,
                output=str(error),
                metadata={"error": "human_review_invalid"},
            )
        return self.call(
            request.tool_name,
            request.args,
            review_id=review_id,
            run_id=request.run_id,
            session_id=request.session_id,
        )

    def register_disposer(self, disposer: Callable[[], None]) -> None:
        """登记外部进程、线程池或后台任务的关闭函数。"""
        if self._closed:
            disposer()
            return
        self._disposers.append(disposer)

    def close(self) -> None:
        """按注册逆序可靠关闭资源；重复调用不会再次执行。"""
        if self._closed:
            return
        self._closed = True
        errors = []
        for disposer in reversed(self._disposers):
            try:
                disposer()
            except Exception as error:  # pragma: no cover - 防御性关闭路径
                errors.append(f"{type(error).__name__}: {error}")
        self._disposers = []
        if errors:
            raise RuntimeError("tool registry close failed: " + "; ".join(errors))

    def __enter__(self) -> "ToolRegistry":
        return self

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        self.close()


def _normalize_result(
    name: str,
    args: dict,
    result: ToolResult,
    tool: Optional[ToolDefinition] = None,
) -> ToolResult:
    """给 ToolResult 补齐统一 metadata 契约。"""
    annotate_tool_result(
        result,
        default_trust_level=(tool.output_trust if tool else TrustLevel.TRUSTED.value),
        default_source=(tool.source if tool else "runtime"),
    )
    result.metadata = _build_tool_metadata(
        tool_name=name,
        args=args,
        ok=result.ok,
        output=result.output,
        metadata=result.metadata,
        trust_level=result.trust_level,
        source=result.source,
        content_sha256=result.content_sha256,
        injection_risk=result.injection_risk,
        capabilities=(tool.capabilities.to_dict() if tool else ToolCapabilities().to_dict()),
    )
    return result


def _build_tool_metadata(
    tool_name: str,
    args: dict,
    ok: bool,
    output: str,
    metadata: dict,
    trust_level: str,
    source: str,
    content_sha256: str,
    injection_risk: dict,
    capabilities: dict,
) -> dict:
    """生成统一工具 trace metadata；工具特有信息统一收进 details。"""
    error = "" if ok else str(metadata.get("error") or output)
    enriched_metadata = dict(metadata)
    if not ok:
        failure = _classify_failure(error, output, enriched_metadata)
        enriched_metadata.setdefault("failure_class", failure.failure_class)
        enriched_metadata.setdefault("recoverable", failure.recoverable)
        enriched_metadata.setdefault("retry_hint", failure.retry_hint)

    details = {
        key: value
        for key, value in enriched_metadata.items()
        if key != "error"
    }
    normalized = {
        "tool": tool_name,
        "args": dict(args),
        "ok": ok,
        "result_summary": _summarize_tool_output(output),
        "error": error,
        "trust_level": trust_level,
        "source": source,
        "content_sha256": content_sha256,
        "injection_risk": dict(injection_risk),
        "capabilities": dict(capabilities),
        "details": details,
    }
    return normalized


def _classify_failure(error: str, output: str, metadata: dict) -> ToolFailure:
    """把失败统一分类，避免 Agent 只能读自然语言报错。"""
    if metadata.get("failure_class"):
        return ToolFailure(
            failure_class=str(metadata["failure_class"]),
            recoverable=bool(metadata.get("recoverable", True)),
            retry_hint=str(metadata.get("retry_hint", "")),
        )

    if error == "unknown_tool":
        return ToolFailure(
            "unknown_tool",
            True,
            "Choose one of the available tools from details.available_tools.",
        )
    if error == "human_review_required":
        return ToolFailure(
            "human_review_required",
            True,
            "Approve the review request, then resume it by review_id.",
        )
    if error in {"permission_denied", "subagent_write_not_approved"}:
        return ToolFailure(
            "permission_denied",
            False,
            "Do not retry the same call; choose a safer operation or ask for approval.",
        )
    if metadata.get("decision") in {"deny", "review"}:
        return ToolFailure(
            "permission_denied",
            False,
            "Do not retry the same call; choose a safer operation or ask for approval.",
        )
    if error in {"hook_execution_failed", "subagent_operations_not_reviewable"}:
        return ToolFailure(
            "policy_check_failed",
            True,
            "Fix the tool arguments so the policy hook can review the request.",
        )
    if "timed_out" in metadata and metadata.get("timed_out"):
        return ToolFailure(
            "timeout",
            True,
            "Retry with a narrower command or inspect partial output first.",
        )
    if "exit_code" in metadata and metadata.get("exit_code") not in (0, None):
        return ToolFailure(
            "command_failed",
            True,
            "Read stdout/stderr and fix the underlying command or code before retrying.",
        )
    if error:
        return ToolFailure(
            "tool_error",
            True,
            "Read the error and adjust arguments before retrying.",
        )
    return ToolFailure(
        "failed_result",
        True,
        "Inspect result details and retry only after changing the request.",
    )


def _classify_exception(error: Exception) -> ToolFailure:
    """根据 Python 异常类型给工具异常一个可恢复提示。"""
    exception_name = type(error).__name__
    if exception_name == "MCPTimeoutError":
        return ToolFailure(
            "mcp_timeout",
            True,
            "Retry a read-only call or inspect MCP server health before retrying a write.",
        )
    if exception_name == "MCPProcessExited":
        return ToolFailure(
            "mcp_process_exited",
            True,
            "The client will reconnect on the next call; retry only if the call is idempotent.",
        )
    if exception_name == "MCPPayloadTooLarge":
        return ToolFailure(
            "mcp_payload_too_large",
            False,
            "Reduce the response at the MCP server or raise the audited payload limit.",
        )
    if exception_name in {"MCPProtocolError", "MCPError"}:
        return ToolFailure(
            "mcp_protocol_error",
            True,
            "Inspect MCP configuration and server stderr before retrying.",
        )
    if isinstance(error, KeyError):
        return ToolFailure(
            "invalid_args",
            True,
            "Provide the missing required argument named in the error.",
        )
    if isinstance(error, FileNotFoundError):
        return ToolFailure(
            "file_not_found",
            True,
            "List or read files first, then retry with an existing path.",
        )
    if isinstance(error, PermissionError):
        return ToolFailure(
            "permission_denied",
            False,
            "Do not retry the same path or command without changing permissions.",
        )
    if isinstance(error, ValueError):
        return ToolFailure(
            "invalid_args",
            True,
            "Fix the invalid argument mentioned in the error message.",
        )
    return ToolFailure(
        "tool_exception",
        True,
        "Inspect the exception message and retry with corrected arguments.",
    )


def _summarize_tool_output(output: str) -> str:
    """给 metadata 使用的短摘要；完整输出继续放在 ToolResult.output。"""
    if len(output) <= RESULT_SUMMARY_LIMIT:
        return output

    return f"{output[:RESULT_SUMMARY_LIMIT]}... [truncated]"
