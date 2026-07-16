from micode.hooks.models import HookContext, HookEvent, HookResult


CRITICAL_TEXT_FIELDS = {
    "path",
    "command",
    "name",
    "old",
}

REQUIRED_RESULT_METADATA = {
    "read_file": ("path",),
    "replace_text": ("path",),
    "write_file": ("path",),
    "run_shell": ("command", "exit_code", "timed_out"),
    "git_status": ("command", "exit_code"),
    "git_diff": ("command", "exit_code"),
    "load_skill": ("name",),
}


class ToolSelfCheckHook:
    """工具自检 Hook，负责参数和结果 metadata 的轻量体检。"""

    def __call__(self, context: HookContext) -> HookResult:
        """根据生命周期分别执行调用前和调用后检查。"""
        if context.event == HookEvent.BEFORE_TOOL_CALL:
            return self._check_before_call(context)
        if context.event == HookEvent.AFTER_TOOL_CALL:
            return self._check_after_call(context)
        return None

    def _check_before_call(self, context: HookContext) -> HookResult:
        """执行前检查参数是否满足工具 schema 的最小契约。"""
        issues = []
        parameters = getattr(context.tool, "parameters", {}) or {}
        required = parameters.get("required", []) or []
        properties = parameters.get("properties", {}) or {}

        for name in required:
            if name not in context.args:
                issues.append(f"missing required argument: {name}")

        if parameters.get("additionalProperties") is False:
            for name in context.args:
                if name not in properties:
                    issues.append(f"unexpected argument: {name}")

        for name, value in context.args.items():
            if name in CRITICAL_TEXT_FIELDS and isinstance(value, str) and not value.strip():
                issues.append(f"empty critical argument: {name}")

        if issues:
            return HookResult.block(
                "工具自检失败，参数不满足工具契约",
                metadata={
                    "error": "tool_self_check_failed",
                    "tool_self_check": {
                        "phase": "before",
                        "status": "failed",
                        "issues": issues,
                    },
                },
            )

        return HookResult.continue_with(
            metadata={
                "tool_self_check": {
                    "phase": "before",
                    "status": "passed",
                    "issues": [],
                }
            }
        )

    def _check_after_call(self, context: HookContext) -> HookResult:
        """执行后检查工具是否返回了后续审计需要的 metadata。"""
        result = context.result
        metadata = getattr(result, "metadata", {}) or {}
        required = REQUIRED_RESULT_METADATA.get(context.tool_name, ())
        missing = [name for name in required if name not in metadata]
        status = "failed" if missing else "passed"

        return HookResult.continue_with(
            metadata={
                "tool_self_check_result": {
                    "phase": "after",
                    "status": status,
                    "missing_metadata": missing,
                }
            }
        )
