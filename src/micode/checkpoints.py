from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from micode.workspace import Workspace


MISSING_HASH = "missing"


def _sha256(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class CheckpointEntry:
    path: str
    before_sha256: str
    after_sha256: str = ""

    def to_dict(self) -> dict:
        return {
            "path": self.path,
            "before_sha256": self.before_sha256,
            "after_sha256": self.after_sha256,
        }


@dataclass
class Checkpoint:
    id: str
    created_at: str
    reason: str
    run_id: str = ""
    tool_name: str = ""
    entries: list[CheckpointEntry] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "created_at": self.created_at,
            "reason": self.reason,
            "run_id": self.run_id,
            "tool_name": self.tool_name,
            "entries": [entry.to_dict() for entry in self.entries],
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Checkpoint":
        return cls(
            id=str(data["id"]),
            created_at=str(data["created_at"]),
            reason=str(data.get("reason", "")),
            run_id=str(data.get("run_id", "")),
            tool_name=str(data.get("tool_name", "")),
            entries=[CheckpointEntry(**entry) for entry in data.get("entries", [])],
        )


class CheckpointStore:
    """用内容寻址 blob 保存写入前状态，并提供冲突安全回退。"""

    def __init__(self, workspace: Workspace, root: str = ".micode/checkpoints") -> None:
        self.workspace = workspace
        self.root = workspace.resolve_path(root)
        self.blob_dir = self.root / "blobs"
        self.manifest_dir = self.root / "manifests"

    def create(
        self,
        paths: list[str],
        *,
        reason: str,
        run_id: str = "",
        tool_name: str = "",
    ) -> Checkpoint:
        """在写操作前保存指定路径；相同内容只保存一个 blob。"""
        checkpoint = Checkpoint(
            id=str(uuid.uuid4()),
            created_at=_utc_now_iso(),
            reason=reason,
            run_id=run_id,
            tool_name=tool_name,
        )
        for path in sorted(set(paths)):
            target = self.workspace.resolve_path(path)
            before_hash = self._capture(target)
            checkpoint.entries.append(CheckpointEntry(path=path, before_sha256=before_hash))
        self._save(checkpoint)
        return checkpoint

    def finalize(self, checkpoint_id: str) -> Checkpoint:
        """写操作结束后记录 after hash，作为 rewind 冲突判断基线。"""
        checkpoint = self.load(checkpoint_id)
        for entry in checkpoint.entries:
            entry.after_sha256 = self._current_hash(
                self.workspace.resolve_path(entry.path)
            )
        self._save(checkpoint)
        return checkpoint

    def preview_rewind(self, checkpoint_id: str) -> dict:
        checkpoint = self.load(checkpoint_id)
        changes = []
        conflicts = []
        for entry in checkpoint.entries:
            current_hash = self._current_hash(self.workspace.resolve_path(entry.path))
            item = {
                "path": entry.path,
                "current_sha256": current_hash,
                "restore_sha256": entry.before_sha256,
                "expected_sha256": entry.after_sha256,
            }
            # 未 finalize 的 checkpoint 不具备可靠的冲突基线。
            if not entry.after_sha256 or current_hash != entry.after_sha256:
                conflicts.append(item)
            elif current_hash != entry.before_sha256:
                changes.append(item)
        return {
            "checkpoint_id": checkpoint_id,
            "can_rewind": not conflicts,
            "changes": changes,
            "conflicts": conflicts,
        }

    def rewind(self, checkpoint_id: str) -> dict:
        """仅在 preview 无冲突时恢复，整个检查通过后才开始写文件。"""
        preview = self.preview_rewind(checkpoint_id)
        if not preview["can_rewind"]:
            raise RuntimeError("checkpoint rewind conflicts with current workspace")
        checkpoint = self.load(checkpoint_id)
        for entry in checkpoint.entries:
            target = self.workspace.resolve_path(entry.path)
            if entry.before_sha256 == MISSING_HASH:
                if target.exists():
                    target.unlink()
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes((self.blob_dir / entry.before_sha256).read_bytes())
        return preview

    def load(self, checkpoint_id: str) -> Checkpoint:
        path = self.manifest_dir / f"{checkpoint_id}.json"
        return Checkpoint.from_dict(json.loads(path.read_text(encoding="utf-8")))

    def _capture(self, path: Path) -> str:
        if not path.exists():
            return MISSING_HASH
        content = path.read_bytes()
        content_hash = _sha256(content)
        self.blob_dir.mkdir(parents=True, exist_ok=True)
        blob = self.blob_dir / content_hash
        if not blob.exists():
            blob.write_bytes(content)
        return content_hash

    @staticmethod
    def _current_hash(path: Path) -> str:
        if not path.exists():
            return MISSING_HASH
        return _sha256(path.read_bytes())

    def _save(self, checkpoint: Checkpoint) -> None:
        self.manifest_dir.mkdir(parents=True, exist_ok=True)
        path = self.manifest_dir / f"{checkpoint.id}.json"
        temporary = path.with_suffix(".json.tmp")
        temporary.write_text(
            json.dumps(checkpoint.to_dict(), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        temporary.replace(path)
