import json
from dataclasses import dataclass, field
from pathlib import Path

from micode.memory.session import utc_now_iso
from micode.memory.working import truncate_memory_text


MAX_EVIDENCE_ITEMS = 8


@dataclass
class EpisodicMemory:
    """EpisodicMemory 表示一次具体经历，通常对应一次 Run。"""

    id: str
    session_id: str
    run_id: str
    task: str
    outcome: str
    status: str
    tool_names: list[str] = field(default_factory=list)
    evidence: list[str] = field(default_factory=list)
    source_event_ids: list[str] = field(default_factory=list)
    created_at: str = field(default_factory=utc_now_iso)
    updated_at: str = field(default_factory=utc_now_iso)
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        """转成可保存的 JSON dict。"""
        return {
            "id": self.id,
            "session_id": self.session_id,
            "run_id": self.run_id,
            "task": self.task,
            "outcome": self.outcome,
            "status": self.status,
            "tool_names": self.tool_names,
            "evidence": self.evidence,
            "source_event_ids": self.source_event_ids,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "EpisodicMemory":
        """从 JSON dict 还原 EpisodicMemory。"""
        return cls(
            id=str(data.get("id", "")),
            session_id=str(data.get("session_id", "")),
            run_id=str(data.get("run_id", "")),
            task=str(data.get("task", "")),
            outcome=str(data.get("outcome", "")),
            status=str(data.get("status", "")),
            tool_names=_string_list(data.get("tool_names", [])),
            evidence=_string_list(data.get("evidence", [])),
            source_event_ids=_string_list(data.get("source_event_ids", [])),
            created_at=str(data.get("created_at", "")) or utc_now_iso(),
            updated_at=str(data.get("updated_at", "")) or utc_now_iso(),
            metadata=data.get("metadata", {})
            if isinstance(data.get("metadata", {}), dict)
            else {},
        )


class EpisodicMemoryStore:
    """用本地 JSON 保存跨 Session 的 episodic memories。"""

    def __init__(self, memory_dir: str = ".micode/memory") -> None:
        self.memory_dir = Path(memory_dir)

    def load_all(self) -> list[EpisodicMemory]:
        """读取所有 episodic memories；不存在时返回空列表。"""
        path = self.path()
        if not path.exists():
            return []

        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, list):
            return []
        return [
            EpisodicMemory.from_dict(item)
            for item in data
            if isinstance(item, dict)
        ]

    def save_all(self, memories: list[EpisodicMemory]) -> str:
        """保存完整 episodic memory 列表。"""
        self.memory_dir.mkdir(parents=True, exist_ok=True)
        path = self.path()
        path.write_text(
            json.dumps(
                [memory.to_dict() for memory in memories],
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        return str(path)

    def upsert(self, memory: EpisodicMemory) -> list[EpisodicMemory]:
        """按 id 新增或替换 episode，返回保存后的完整列表。"""
        memories = self.load_all()
        replaced = False
        updated = []

        for existing in memories:
            if existing.id == memory.id:
                updated.append(memory)
                replaced = True
            else:
                updated.append(existing)

        if not replaced:
            updated.append(memory)

        self.save_all(updated)
        return updated

    def find_by_session(self, session_id: str) -> list[EpisodicMemory]:
        """按 session_id 查询 episode。"""
        return [
            memory
            for memory in self.load_all()
            if memory.session_id == session_id
        ]

    def path(self) -> Path:
        """返回 episodic memory 文件路径。"""
        return self.memory_dir / "episodes.json"


def episodic_memory_from_trace(session_id: str, trace: dict) -> EpisodicMemory:
    """从一次 trace 提炼 episodic memory。

    Episode 是长期记忆候选，只保留任务、结果、工具和关键证据，不复制完整 trace。
    """
    run = trace.get("run", {})
    metadata = run.get("metadata", {})
    run_id = str(run.get("id", ""))
    status = str(run.get("status", "unknown"))
    task = str(metadata.get("task", ""))
    events = trace.get("events", [])

    return EpisodicMemory(
        id=f"episode:{run_id}",
        session_id=session_id,
        run_id=run_id,
        task=task,
        outcome=extract_outcome(events),
        status=status,
        tool_names=extract_tool_names(trace),
        evidence=extract_evidence(events),
        source_event_ids=[
            str(event.get("id", ""))
            for event in events
            if isinstance(event, dict) and event.get("id")
        ],
        created_at=str(run.get("created_at", "")) or utc_now_iso(),
        updated_at=str(run.get("updated_at", "")) or utc_now_iso(),
        metadata={
            "provider": metadata.get("provider", ""),
            "model": metadata.get("model", ""),
            "workspace": metadata.get("workspace", ""),
        },
    )


def extract_outcome(events: list[dict]) -> str:
    """提取一次经历的结果：优先 final text，其次最近 error，再其次最近事件内容。"""
    text_events = [
        event
        for event in events
        if isinstance(event, dict)
        and event.get("type") == "text"
        and event.get("content")
    ]
    if text_events:
        return truncate_memory_text(str(text_events[-1].get("content", "")))

    error_events = [
        event
        for event in events
        if isinstance(event, dict)
        and event.get("type") == "error"
        and event.get("content")
    ]
    if error_events:
        return truncate_memory_text(str(error_events[-1].get("content", "")))

    for event in reversed(events):
        if isinstance(event, dict) and event.get("content"):
            return truncate_memory_text(str(event.get("content", "")))

    return ""


def extract_tool_names(trace: dict) -> list[str]:
    """从 steps metadata 中提取本次经历用过的工具名。"""
    tool_names = []
    for step in trace.get("steps", []):
        if not isinstance(step, dict):
            continue
        tool = step.get("metadata", {}).get("tool")
        if isinstance(tool, str) and tool and tool not in tool_names:
            tool_names.append(tool)
    return tool_names


def extract_evidence(events: list[dict]) -> list[str]:
    """提取关键证据，保留短内容，避免复制完整工具输出。"""
    evidence = []
    for event in events:
        if not isinstance(event, dict):
            continue
        content = str(event.get("content", "")).strip()
        if not content:
            continue

        event_type = str(event.get("type", ""))
        if event_type not in {"tool_call", "error", "text"}:
            continue

        evidence.append(f"{event_type}: {truncate_memory_text(content, max_length=220)}")
        if len(evidence) >= MAX_EVIDENCE_ITEMS:
            break
    return evidence


def _string_list(value) -> list[str]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, str)]
