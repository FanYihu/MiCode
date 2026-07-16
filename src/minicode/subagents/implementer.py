from dataclasses import dataclass
import json

from minicode.subagents.models import (
    SUBAGENT_COMPLETED,
    SUBAGENT_FAILED,
    SubAgentResult,
    SubAgentTask,
)
from minicode.tools.file import FileTools


@dataclass
class ImplementerOperation:
    """Implementer 可执行的一条结构化文件操作。"""

    type: str
    path: str
    old: str = ""
    new: str = ""
    content: str = ""

    def to_dict(self) -> dict:
        """转成 trace metadata 使用的普通字典。"""
        return {
            "type": self.type,
            "path": self.path,
            "old": self.old,
            "new": self.new,
            "content": self.content,
        }


@dataclass
class ImplementerSubAgent:
    """受控实现 SubAgent。

    Day67 不让 Implementer 自己推理改法，而是执行主 Agent 给出的结构化
    operations。这样它可以真实写文件，又能保持可审计和可测试。
    """

    file_tools: FileTools

    def execute(self, task: SubAgentTask) -> SubAgentResult:
        """解析、校验并执行文件修改操作。"""
        operations, error = self._load_operations(task)
        if error:
            return self._failed(task, error, metadata={"error": "invalid_operations"})

        validation_error = self._validate_operations(task, operations)
        if validation_error:
            return self._failed(
                task,
                validation_error,
                metadata={
                    "error": "operation_not_allowed",
                    "operations": [operation.to_dict() for operation in operations],
                },
            )

        changed_paths: list[str] = []
        diffs: list[str] = []
        try:
            for operation in operations:
                diff = self._apply_operation(operation)
                diffs.append(diff)
                if operation.path not in changed_paths:
                    changed_paths.append(operation.path)
        except Exception as error:
            return self._failed(
                task,
                f"ImplementerSubAgent: {type(error).__name__}: {error}",
                metadata={
                    "error": type(error).__name__,
                    "changed_paths": changed_paths,
                    "diffs": diffs,
                },
                changed_paths=changed_paths,
            )

        summary = (
            "ImplementerSubAgent: applied "
            f"{len(operations)} operation(s) to {len(changed_paths)} file(s)."
        )
        return SubAgentResult(
            task_id=task.id,
            role=task.role,
            status=SUBAGENT_COMPLETED,
            summary=summary,
            evidence=[_trim_diff(diff) for diff in diffs if diff],
            changed_paths=changed_paths,
            metadata={
                "operation_count": len(operations),
                "operations": [operation.to_dict() for operation in operations],
                "diffs": [_trim_diff(diff) for diff in diffs],
            },
        )

    def _load_operations(
        self,
        task: SubAgentTask,
    ) -> tuple[list[ImplementerOperation], str]:
        """从 task metadata 或 context JSON 中读取 operations。"""
        raw_operations = task.metadata.get("operations")
        if raw_operations is None:
            payload, error = _extract_json_object(task.context)
            if error:
                return [], error
            raw_operations = payload.get("operations")

        if not isinstance(raw_operations, list) or not raw_operations:
            return [], "ImplementerSubAgent requires a non-empty operations list"

        operations = []
        for raw in raw_operations:
            if not isinstance(raw, dict):
                return [], "Each implementer operation must be an object"
            operations.append(
                ImplementerOperation(
                    type=str(raw.get("type") or raw.get("tool") or "").strip(),
                    path=str(raw.get("path") or "").strip(),
                    old=str(raw.get("old") or ""),
                    new=str(raw.get("new") or ""),
                    content=str(raw.get("content") or ""),
                )
            )
        return operations, ""

    def _validate_operations(
        self,
        task: SubAgentTask,
        operations: list[ImplementerOperation],
    ) -> str:
        """校验操作类型、必填字段和 policy 授权工具。"""
        allowed_tools = set(task.allowed_tools)
        for operation in operations:
            if not operation.path:
                return "Implementer operation path is required"
            if operation.type == "replace_text":
                if "replace_text" not in allowed_tools:
                    return "replace_text is not allowed for this subagent task"
                if operation.old == "":
                    return "replace_text operation requires non-empty old text"
                continue
            if operation.type == "write_file":
                if "write_file" not in allowed_tools:
                    return "write_file is not allowed for this subagent task"
                continue
            return f"Unsupported implementer operation type: {operation.type}"
        return ""

    def _apply_operation(self, operation: ImplementerOperation) -> str:
        """执行单个文件操作，并返回 diff。"""
        if operation.type == "replace_text":
            return self.file_tools.replace_text(
                operation.path,
                operation.old,
                operation.new,
            )

        diff = self.file_tools.preview_write(operation.path, operation.content)
        self.file_tools.write_file(operation.path, operation.content)
        return diff

    def _failed(
        self,
        task: SubAgentTask,
        summary: str,
        metadata: dict,
        changed_paths: list[str] = None,
    ) -> SubAgentResult:
        """统一构造失败结果，方便 ToolResult 和 Trace 消费。"""
        return SubAgentResult(
            task_id=task.id,
            role=task.role,
            status=SUBAGENT_FAILED,
            summary=summary,
            changed_paths=changed_paths or [],
            metadata=metadata,
        )


def _extract_json_object(text: str) -> tuple[dict, str]:
    """从 context 中提取 JSON object，允许前后带说明文字。"""
    stripped = (text or "").strip()
    if not stripped:
        return {}, "ImplementerSubAgent context must contain operations JSON"

    decoder = json.JSONDecoder()
    for index, char in enumerate(stripped):
        if char != "{":
            continue
        try:
            payload, _ = decoder.raw_decode(stripped[index:])
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            return payload, ""
    return {}, "ImplementerSubAgent context must contain a JSON object"


def _trim_diff(diff: str, max_chars: int = 1200) -> str:
    """限制 diff 证据长度，避免 SubAgentResult metadata 过大。"""
    if len(diff) <= max_chars:
        return diff
    return f"{diff[:max_chars]}... [truncated]"
