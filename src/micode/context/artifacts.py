import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

from micode.memory.session import utc_now_iso
from micode.tools.registry import ToolResult


DEFAULT_ARTIFACT_THRESHOLD = 8000


@dataclass
class ArtifactRef:
    """ArtifactRef 描述一个被外置保存的大结果。"""

    id: str
    kind: str
    path: str
    size_chars: int
    sha256: str

    @property
    def placeholder(self) -> str:
        """返回可放进 prompt 或 trace 的短占位符。"""
        return (
            f"[artifact id={self.id} kind={self.kind} "
            f"size_chars={self.size_chars} path={self.path}]"
        )

    def to_metadata(self) -> dict:
        """转成 trace metadata。"""
        return {
            "artifact_id": self.id,
            "artifact_kind": self.kind,
            "artifact_path": self.path,
            "artifact_size_chars": self.size_chars,
            "artifact_sha256": self.sha256,
            "artifact_placeholder": self.placeholder,
        }


class ArtifactStore:
    """把超大运行产物保存到本地 artifact 目录。"""

    def __init__(self, artifact_dir: str = ".micode/artifacts") -> None:
        self.artifact_dir = Path(artifact_dir)

    def save_tool_result(
        self,
        tool_name: str,
        result: ToolResult,
        metadata: dict = None,
    ) -> ArtifactRef:
        """保存完整工具结果，并返回可追踪引用。"""
        content = result.output if isinstance(result.output, str) else str(result.output)
        digest = hashlib.sha256(content.encode("utf-8")).hexdigest()
        artifact_id = f"artifact:tool-result:{digest[:24]}"
        target_dir = self.artifact_dir / "tool-results"
        target_dir.mkdir(parents=True, exist_ok=True)
        path = target_dir / f"{safe_artifact_filename(artifact_id)}.json"
        if path.exists():
            return ArtifactRef(
                id=artifact_id,
                kind="tool_result",
                path=str(path),
                size_chars=len(content),
                sha256=digest,
            )

        payload = {
            "id": artifact_id,
            "kind": "tool_result",
            "tool": tool_name,
            "content": content,
            "size_chars": len(content),
            "sha256": digest,
            "created_at": utc_now_iso(),
            "metadata": metadata or {},
        }
        path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return ArtifactRef(
            id=artifact_id,
            kind="tool_result",
            path=str(path),
            size_chars=len(content),
            sha256=digest,
        )


def maybe_store_tool_result_artifact(
    store: ArtifactStore,
    tool_name: str,
    result: ToolResult,
    threshold_chars: int = DEFAULT_ARTIFACT_THRESHOLD,
    metadata: dict = None,
) -> ArtifactRef:
    """超过阈值才外置工具结果；未超过时返回 None。"""
    content = result.output if isinstance(result.output, str) else str(result.output)
    if threshold_chars <= 0 or len(content) <= threshold_chars:
        return None
    return store.save_tool_result(tool_name, result, metadata=metadata)


def safe_artifact_filename(artifact_id: str) -> str:
    """把 artifact id 转成文件系统友好的名称。"""
    return "".join(char if char.isalnum() else "-" for char in artifact_id).strip("-")
