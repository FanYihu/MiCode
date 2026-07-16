import json
from dataclasses import dataclass, field
from pathlib import Path

from minicode.memory.session import SessionMessage, utc_now_iso


MAX_RECENT_MESSAGES = 12
MAX_ITEMS = 20


@dataclass
class WorkingMemory:
    """WorkingMemory 描述当前 Session 的短期工作状态。"""

    session_id: str
    current_goal: str = ""
    completed: list[str] = field(default_factory=list)
    todo: list[str] = field(default_factory=list)
    constraints: list[str] = field(default_factory=list)
    recent_messages: list[dict] = field(default_factory=list)
    updated_at: str = field(default_factory=utc_now_iso)
    metadata: dict = field(default_factory=dict)

    def set_goal(self, goal: str) -> None:
        """设置当前目标。"""
        self.current_goal = goal.strip()
        self.updated_at = utc_now_iso()

    def add_todo(self, item: str) -> None:
        """添加待办事项。"""
        self._append_unique(self.todo, item)
        self.updated_at = utc_now_iso()

    def complete_item(self, item: str) -> None:
        """把事项标记为完成，并从 todo 中移除同名项。"""
        normalized = item.strip()
        if not normalized:
            return
        self.todo = [todo for todo in self.todo if todo != normalized]
        self._append_unique(self.completed, normalized)
        self.updated_at = utc_now_iso()

    def add_constraint(self, constraint: str) -> None:
        """记录当前会话必须遵守的约束。"""
        self._append_unique(self.constraints, constraint)
        self.updated_at = utc_now_iso()

    def to_dict(self) -> dict:
        """转成可保存的 JSON dict。"""
        return {
            "session_id": self.session_id,
            "current_goal": self.current_goal,
            "completed": self.completed,
            "todo": self.todo,
            "constraints": self.constraints,
            "recent_messages": self.recent_messages,
            "updated_at": self.updated_at,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "WorkingMemory":
        """从 JSON dict 还原 WorkingMemory。"""
        return cls(
            session_id=str(data.get("session_id", "")),
            current_goal=str(data.get("current_goal", "")),
            completed=_string_list(data.get("completed", [])),
            todo=_string_list(data.get("todo", [])),
            constraints=_string_list(data.get("constraints", [])),
            recent_messages=[
                item for item in data.get("recent_messages", []) if isinstance(item, dict)
            ],
            updated_at=str(data.get("updated_at", "")) or utc_now_iso(),
            metadata=data.get("metadata", {})
            if isinstance(data.get("metadata", {}), dict)
            else {},
        )

    def apply_messages(self, messages: list[SessionMessage]) -> None:
        """根据新消息更新当前工作状态。

        这里先用确定性规则打底；后续 Day46/Day54 可以接 LLM 压缩和 Ranking。
        """
        for message in messages:
            if message.role == "user" and message.content:
                self.set_goal(message.content)
                self._remember_recent(message)
            elif message.role == "assistant" and message.content:
                self.complete_item(message.content)
                self._remember_recent(message)
            elif message.role == "tool" and message.content:
                self._remember_recent(message)
            elif message.role == "error" and message.content:
                self.add_todo(f"处理错误：{message.content}")
                self._remember_recent(message)

        self.completed = self.completed[-MAX_ITEMS:]
        self.todo = self.todo[-MAX_ITEMS:]
        self.constraints = self.constraints[-MAX_ITEMS:]
        self.recent_messages = self.recent_messages[-MAX_RECENT_MESSAGES:]
        self.updated_at = utc_now_iso()

    def _remember_recent(self, message: SessionMessage) -> None:
        """保留最近消息的短摘要，避免 Working Memory 无限膨胀。"""
        self.recent_messages.append(
            {
                "id": message.id,
                "run_id": message.run_id,
                "role": message.role,
                "type": message.type,
                "content": truncate_memory_text(message.content),
                "created_at": message.created_at,
            }
        )

    def _append_unique(self, items: list[str], value: str) -> None:
        """追加去重列表项。"""
        normalized = value.strip()
        if normalized and normalized not in items:
            items.append(normalized)


class WorkingMemoryStore:
    """用本地 JSON 保存 Working Memory；它是 session 的短期状态文件。"""

    def __init__(self, session_dir: str = ".minicode/sessions") -> None:
        self.session_dir = Path(session_dir)

    def load(self, session_id: str) -> WorkingMemory:
        """读取 Working Memory；不存在时返回空状态。"""
        path = self.path_for(session_id)
        if not path.exists():
            return WorkingMemory(session_id=session_id)

        data = json.loads(path.read_text(encoding="utf-8"))
        return WorkingMemory.from_dict(data)

    def save(self, memory: WorkingMemory) -> str:
        """保存 Working Memory，并返回文件路径。"""
        self.session_dir.mkdir(parents=True, exist_ok=True)
        path = self.path_for(memory.session_id)
        path.write_text(
            json.dumps(memory.to_dict(), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return str(path)

    def update_from_messages(
        self,
        session_id: str,
        messages: list[SessionMessage],
    ) -> WorkingMemory:
        """读取现有 Working Memory，应用新消息后保存。"""
        memory = self.load(session_id)
        memory.apply_messages(messages)
        self.save(memory)
        return memory

    def path_for(self, session_id: str) -> Path:
        """根据 session_id 计算 Working Memory 文件路径。"""
        normalized_session_id = session_id.strip()
        if not normalized_session_id:
            raise ValueError("session_id is required")
        return self.session_dir / f"{normalized_session_id}.working_memory.json"


def truncate_memory_text(text: str, max_length: int = 300) -> str:
    """Working Memory 只保留短文本，长内容后续交给 Context Compression。"""
    if len(text) <= max_length:
        return text
    return text[: max_length - 3].rstrip() + "..."


def _string_list(value) -> list[str]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, str)]
