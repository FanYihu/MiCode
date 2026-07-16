from __future__ import annotations

import json
import os
import threading
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
from typing import List, Optional


PENDING = "pending"
APPROVED = "approved"
REJECTED = "rejected"
CANCELLED = "cancelled"
CONSUMED = "consumed"


class HumanReviewError(RuntimeError):
    """人工审核请求不存在、状态不符或参数不匹配。"""


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _args_hash(tool_name: str, args: dict) -> str:
    payload = json.dumps(
        {"tool": tool_name, "args": args},
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return sha256(payload.encode("utf-8")).hexdigest()


@dataclass
class HumanReviewRequest:
    """一次可持久化、可恢复且只能消费一次的人工审核。"""

    id: str
    tool_name: str
    args: dict
    args_sha256: str
    reason: str
    status: str = PENDING
    created_at: str = field(default_factory=_utc_now)
    updated_at: str = field(default_factory=_utc_now)
    run_id: str = ""
    session_id: str = ""
    note: str = ""

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "HumanReviewRequest":
        return cls(**data)


class HumanReviewStore:
    """用独立 JSON 文件保存审核状态，便于 CLI 跨进程恢复。"""

    def __init__(self, review_dir: str = ".micode/human-reviews") -> None:
        self.review_dir = Path(review_dir)
        self._lock = threading.RLock()

    def create(
        self,
        tool_name: str,
        args: dict,
        reason: str,
        run_id: str = "",
        session_id: str = "",
    ) -> HumanReviewRequest:
        request = HumanReviewRequest(
            id=f"review-{uuid.uuid4().hex}",
            tool_name=tool_name,
            args=dict(args),
            args_sha256=_args_hash(tool_name, args),
            reason=reason,
            run_id=run_id,
            session_id=session_id,
        )
        with self._lock:
            self._save(request)
        return request

    def get(self, review_id: str) -> HumanReviewRequest:
        path = self._path_for(review_id)
        if not path.exists():
            raise HumanReviewError(f"human review not found: {review_id}")
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            raise HumanReviewError(f"invalid human review file: {review_id}") from error
        return HumanReviewRequest.from_dict(data)

    def list(self, status: str = "") -> List[HumanReviewRequest]:
        if not self.review_dir.exists():
            return []
        requests = []
        for path in sorted(self.review_dir.glob("review-*.json")):
            request = self.get(path.stem)
            if not status or request.status == status:
                requests.append(request)
        return requests

    def decide(self, review_id: str, status: str, note: str = "") -> HumanReviewRequest:
        if status not in {APPROVED, REJECTED, CANCELLED}:
            raise HumanReviewError(f"unsupported human review decision: {status}")
        with self._lock:
            request = self.get(review_id)
            if request.status != PENDING:
                raise HumanReviewError(
                    f"human review {review_id} is already {request.status}"
                )
            request.status = status
            request.note = note
            request.updated_at = _utc_now()
            self._save(request)
            return request

    def authorize(self, review_id: str, tool_name: str, args: dict) -> HumanReviewRequest:
        """校验批准与原调用完全一致，并原子标记为 consumed。"""
        with self._lock:
            request = self.get(review_id)
            if request.status != APPROVED:
                raise HumanReviewError(
                    f"human review {review_id} is {request.status}, not approved"
                )
            actual_hash = _args_hash(tool_name, args)
            if request.tool_name != tool_name or request.args_sha256 != actual_hash:
                raise HumanReviewError("human review does not match tool call")
            request.status = CONSUMED
            request.updated_at = _utc_now()
            self._save(request)
            return request

    def _path_for(self, review_id: str) -> Path:
        if not review_id.startswith("review-") or not review_id[7:].isalnum():
            raise HumanReviewError("invalid human review id")
        return self.review_dir / f"{review_id}.json"

    def _save(self, request: HumanReviewRequest) -> None:
        self.review_dir.mkdir(parents=True, exist_ok=True)
        path = self._path_for(request.id)
        temporary = path.with_suffix(f".tmp-{uuid.uuid4().hex}")
        temporary.write_text(
            json.dumps(request.to_dict(), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        os.replace(str(temporary), str(path))
