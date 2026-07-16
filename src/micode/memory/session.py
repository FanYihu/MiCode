import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional


def utc_now_iso() -> str:
    """生成统一的 UTC 时间字符串，避免各模块自己拼时间格式。"""
    return datetime.now(timezone.utc).isoformat()


@dataclass
class Session:
    """Session 表示一次连续对话容器，可以包含多次 Run。"""

    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    title: str = ""
    created_at: str = field(default_factory=utc_now_iso)
    updated_at: str = field(default_factory=utc_now_iso)
    run_ids: list[str] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)

    def add_run(self, run_id: str) -> None:
        """把一次 Run 归入当前会话；重复 run_id 不重复追加。"""
        normalized_run_id = run_id.strip()
        if not normalized_run_id:
            raise ValueError("run_id is required")

        if normalized_run_id not in self.run_ids:
            self.run_ids.append(normalized_run_id)
        self.updated_at = utc_now_iso()

    def to_dict(self) -> dict:
        """转成可保存的 JSON dict。"""
        return {
            "id": self.id,
            "title": self.title,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "run_ids": self.run_ids,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Session":
        """从 JSON dict 还原 Session，缺字段时给出保守默认值。"""
        return cls(
            id=str(data.get("id", "")) or str(uuid.uuid4()),
            title=str(data.get("title", "")),
            created_at=str(data.get("created_at", "")) or utc_now_iso(),
            updated_at=str(data.get("updated_at", "")) or utc_now_iso(),
            run_ids=[
                run_id
                for run_id in data.get("run_ids", [])
                if isinstance(run_id, str) and run_id
            ],
            metadata=data.get("metadata", {})
            if isinstance(data.get("metadata", {}), dict)
            else {},
        )


class SessionStore:
    """用本地 JSON 文件保存 Session；后续可替换成 SQLite 或图数据库。"""

    def __init__(self, session_dir: str = ".micode/sessions") -> None:
        self.session_dir = Path(session_dir)

    def create(
        self,
        title: str = "",
        metadata: Optional[dict] = None,
        session_id: str = "",
    ) -> Session:
        """创建并保存新 Session；测试或 CLI 可传固定 session_id。"""
        session = Session(
            id=session_id or str(uuid.uuid4()),
            title=title,
            metadata=metadata or {},
        )
        self.save(session)
        return session

    def save(self, session: Session) -> str:
        """保存 Session，并返回 JSON 文件路径。"""
        self.session_dir.mkdir(parents=True, exist_ok=True)
        path = self.path_for(session.id)
        path.write_text(
            json.dumps(session.to_dict(), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return str(path)

    def load(self, session_id: str) -> Session:
        """按 id 读取 Session；不存在时抛 FileNotFoundError。"""
        path = self.path_for(session_id)
        return Session.from_dict(json.loads(path.read_text(encoding="utf-8")))

    def get_or_create(
        self,
        session_id: str,
        title: str = "",
        metadata: Optional[dict] = None,
    ) -> Session:
        """读取已有 Session；如果不存在则用指定 id 创建。"""
        path = self.path_for(session_id)
        if path.exists():
            return self.load(session_id)
        return self.create(title=title, metadata=metadata, session_id=session_id)

    def add_run(self, session_id: str, run_id: str) -> Session:
        """把 run_id 追加到 Session 并保存，返回更新后的 Session。"""
        session = self.load(session_id)
        session.add_run(run_id)
        self.save(session)
        return session

    def list_sessions(self, limit: int = 20) -> list[Session]:
        """按修改时间倒序列出最近 Session。"""
        if limit <= 0 or not self.session_dir.exists():
            return []

        paths = sorted(
            (
                path
                for path in self.session_dir.glob("*.json")
                if not path.name.endswith(".messages.json")
                and not path.name.endswith(".working_memory.json")
                and not path.name.endswith(".summary.json")
            ),
            key=lambda path: path.stat().st_mtime,
            reverse=True,
        )
        return [self.load(path.stem) for path in paths[:limit]]

    def path_for(self, session_id: str) -> Path:
        """根据 session_id 计算保存路径。"""
        normalized_session_id = session_id.strip()
        if not normalized_session_id:
            raise ValueError("session_id is required")
        return self.session_dir / f"{normalized_session_id}.json"


@dataclass
class SessionMessage:
    """SessionMessage 是会话级消息流的最小事件单元。"""

    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    session_id: str = ""
    run_id: str = ""
    role: str = "system"
    type: str = "text"
    content: str = ""
    created_at: str = field(default_factory=utc_now_iso)
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        """转成可保存的 JSON dict。"""
        return {
            "id": self.id,
            "session_id": self.session_id,
            "run_id": self.run_id,
            "role": self.role,
            "type": self.type,
            "content": self.content,
            "created_at": self.created_at,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "SessionMessage":
        """从 JSON dict 还原消息；缺字段时使用保守默认值。"""
        return cls(
            id=str(data.get("id", "")) or str(uuid.uuid4()),
            session_id=str(data.get("session_id", "")),
            run_id=str(data.get("run_id", "")),
            role=str(data.get("role", "system")),
            type=str(data.get("type", "text")),
            content=str(data.get("content", "")),
            created_at=str(data.get("created_at", "")) or utc_now_iso(),
            metadata=data.get("metadata", {})
            if isinstance(data.get("metadata", {}), dict)
            else {},
        )


class SessionMessageStore:
    """保存 Session 级消息流，为后续 Working Memory 和压缩层提供输入。"""

    def __init__(self, session_dir: str = ".micode/sessions") -> None:
        self.session_dir = Path(session_dir)

    def append_messages(
        self,
        session_id: str,
        messages: list[SessionMessage],
    ) -> list[SessionMessage]:
        """追加消息并去重保存，返回完整消息列表。"""
        existing = self.load_messages(session_id)
        existing_ids = {message.id for message in existing}
        merged = list(existing)

        for message in messages:
            if message.id in existing_ids:
                continue
            merged.append(message)
            existing_ids.add(message.id)

        self.save_messages(session_id, merged)
        return merged

    def append_trace(self, session_id: str, trace: dict) -> list[SessionMessage]:
        """把一次 trace 的关键事件追加成会话级消息。"""
        messages = messages_from_trace(session_id, trace)
        return self.append_messages(session_id, messages)

    def save_messages(
        self,
        session_id: str,
        messages: list[SessionMessage],
    ) -> str:
        """保存消息列表，并返回消息文件路径。"""
        self.session_dir.mkdir(parents=True, exist_ok=True)
        path = self.path_for(session_id)
        path.write_text(
            json.dumps(
                [message.to_dict() for message in messages],
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        return str(path)

    def load_messages(self, session_id: str) -> list[SessionMessage]:
        """读取指定 Session 的消息列表；不存在时返回空列表。"""
        path = self.path_for(session_id)
        if not path.exists():
            return []

        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, list):
            return []
        return [
            SessionMessage.from_dict(item)
            for item in data
            if isinstance(item, dict)
        ]

    def path_for(self, session_id: str) -> Path:
        """根据 session_id 计算消息文件路径。"""
        normalized_session_id = session_id.strip()
        if not normalized_session_id:
            raise ValueError("session_id is required")
        return self.session_dir / f"{normalized_session_id}.messages.json"


def messages_from_trace(session_id: str, trace: dict) -> list[SessionMessage]:
    """从 trace 中提取会话级消息。

    Trace 仍然保存完整执行细节；这里仅提取适合会话回放和后续记忆压缩的消息流。
    """
    run = trace.get("run", {})
    run_id = str(run.get("id", ""))
    metadata = run.get("metadata", {})
    messages = []

    task = metadata.get("task")
    if task:
        messages.append(
            SessionMessage(
                id=f"{run_id}:user",
                session_id=session_id,
                run_id=run_id,
                role="user",
                type="task",
                content=str(task),
                created_at=str(run.get("created_at", "")) or utc_now_iso(),
                metadata={"source": "run.metadata.task"},
            )
        )

    for event in trace.get("events", []):
        content = str(event.get("content", ""))
        if not content:
            continue

        event_type = str(event.get("type", "text"))
        messages.append(
            SessionMessage(
                id=str(event.get("id", "")) or str(uuid.uuid4()),
                session_id=session_id,
                run_id=run_id,
                role=role_for_event_type(event_type),
                type=event_type,
                content=content,
                created_at=str(event.get("created_at", "")) or utc_now_iso(),
                metadata={
                    "source": "trace.event",
                    "step_id": event.get("step_id", ""),
                    "event_metadata": event.get("metadata", {}),
                },
            )
        )

    return messages


def role_for_event_type(event_type: str) -> str:
    """把 trace event type 映射成会话消息角色。"""
    if event_type == "tool_call":
        return "tool"
    if event_type == "error":
        return "error"
    if event_type == "state":
        return "system"
    return "assistant"
