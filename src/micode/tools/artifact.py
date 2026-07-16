import hashlib
import json
from pathlib import Path
from typing import Optional

from micode.context.artifacts import safe_artifact_filename
from micode.context.tool_results import summarize_head_tail
from micode.security import TrustLevel
from micode.tools.registry import ToolCapabilities, ToolDefinition, ToolResult


DEFAULT_ARTIFACT_READ_CHARS = 4000


def create_read_artifact_tool(artifact_dir: str) -> ToolDefinition:
    """创建 artifact 读取工具，并把目录边界固定在当前运行配置里。"""
    return ToolDefinition(
        name="read_artifact",
        description="Read a saved artifact by id or path with workspace-safe bounds.",
        parallel_safe=True,
        capabilities=ToolCapabilities(read_only=True),
        output_trust=TrustLevel.LOCAL.value,
        source="artifact-store",
        parameters={
            "type": "object",
            "properties": {
                "id": {
                    "type": "string",
                    "description": "Artifact id, such as artifact:tool-result:xxxx.",
                },
                "path": {
                    "type": "string",
                    "description": "Artifact JSON path from a previous placeholder.",
                },
                "max_chars": {
                    "type": "integer",
                    "description": (
                        "Maximum content chars to return. Use 0 or negative for full content."
                    ),
                },
            },
            "required": [],
            "additionalProperties": False,
        },
        handler=lambda args: read_artifact_tool(artifact_dir, args),
    )


def read_artifact_tool(artifact_dir: str, args: dict) -> ToolResult:
    """按 artifact id 或 path 读取已保存内容，默认返回限长预览。"""
    artifact_id = str(args.get("id") or "").strip()
    artifact_path = str(args.get("path") or "").strip()
    max_chars = _coerce_max_chars(args.get("max_chars"))

    if not artifact_id and not artifact_path:
        return ToolResult(
            ok=False,
            output="read_artifact requires either id or path",
            metadata={"error": "missing_artifact_reference"},
        )

    artifact_root = Path(artifact_dir).resolve()
    path = _resolve_artifact_path(
        artifact_root=artifact_root,
        artifact_id=artifact_id,
        artifact_path=artifact_path,
    )
    if path is None:
        return ToolResult(
            ok=False,
            output="artifact path is outside artifact directory",
            metadata={"error": "artifact_path_outside_root"},
        )

    if not path.exists():
        return ToolResult(
            ok=False,
            output=f"artifact not found: {path}",
            metadata={"error": "artifact_not_found", "artifact_path": str(path)},
        )

    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        return ToolResult(
            ok=False,
            output=f"artifact json is invalid: {error}",
            metadata={"error": "invalid_artifact_json", "artifact_path": str(path)},
        )

    content = payload.get("content", "")
    if not isinstance(content, str):
        return ToolResult(
            ok=False,
            output="artifact content must be a string",
            metadata={"error": "invalid_artifact_content", "artifact_path": str(path)},
        )

    digest = hashlib.sha256(content.encode("utf-8")).hexdigest()
    expected_digest = payload.get("sha256", "")
    if expected_digest and digest != expected_digest:
        return ToolResult(
            ok=False,
            output="artifact content hash does not match payload sha256",
            metadata={
                "error": "artifact_hash_mismatch",
                "artifact_path": str(path),
                "artifact_id": payload.get("id", artifact_id),
                "expected_sha256": expected_digest,
                "actual_sha256": digest,
            },
        )

    output = _preview_content(content, max_chars)
    return ToolResult(
        ok=True,
        output=output,
        metadata={
            "artifact_id": payload.get("id", artifact_id),
            "artifact_kind": payload.get("kind", ""),
            "artifact_path": str(path),
            "artifact_tool": payload.get("tool", ""),
            "artifact_size_chars": len(content),
            "artifact_sha256": digest,
            "read_max_chars": max_chars,
            "read_truncated": max_chars > 0 and len(content) > max_chars,
        },
    )


def _resolve_artifact_path(
    artifact_root: Path,
    artifact_id: str,
    artifact_path: str,
) -> Optional[Path]:
    """把 id/path 解析成 artifact_root 内部的真实路径。"""
    if artifact_id:
        filename = f"{safe_artifact_filename(artifact_id)}.json"
        candidate = artifact_root / "tool-results" / filename
    else:
        candidate = Path(artifact_path)
        if not candidate.is_absolute():
            candidate = Path.cwd() / candidate

    resolved = candidate.resolve()
    try:
        resolved.relative_to(artifact_root)
    except ValueError:
        return None
    return resolved


def _coerce_max_chars(value) -> int:
    """把模型传来的 max_chars 容错转成整数。"""
    if value is None:
        return DEFAULT_ARTIFACT_READ_CHARS
    try:
        return int(value)
    except (TypeError, ValueError):
        return DEFAULT_ARTIFACT_READ_CHARS


def _preview_content(content: str, max_chars: int) -> str:
    """默认按首尾预览读取 artifact，避免重新撑爆上下文。"""
    if max_chars <= 0 or len(content) <= max_chars:
        return content
    return summarize_head_tail(content, max_chars, tail_ratio=0.5)
