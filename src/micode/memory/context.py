import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from micode.memory.session import SessionMessage, utc_now_iso
from micode.memory.working import WorkingMemory, truncate_memory_text


DEFAULT_RECENT_MESSAGE_LIMIT = 8
SUMMARY_ITEM_LIMIT = 30


@dataclass
class SessionSummary:
    """SessionSummary 保存被压缩过的较早会话内容。"""

    session_id: str
    summary: str = ""
    structured: dict = field(default_factory=dict)
    covered_message_ids: list[str] = field(default_factory=list)
    source_message_count: int = 0
    updated_at: str = field(default_factory=utc_now_iso)
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        """转成可保存的 JSON dict。"""
        return {
            "session_id": self.session_id,
            "summary": self.summary,
            "structured": self.structured,
            "covered_message_ids": self.covered_message_ids,
            "source_message_count": self.source_message_count,
            "updated_at": self.updated_at,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "SessionSummary":
        """从 JSON dict 还原 SessionSummary。"""
        return cls(
            session_id=str(data.get("session_id", "")),
            summary=str(data.get("summary", "")),
            structured=data.get("structured", {})
            if isinstance(data.get("structured", {}), dict)
            else {},
            covered_message_ids=_string_list(data.get("covered_message_ids", [])),
            source_message_count=int(data.get("source_message_count", 0) or 0),
            updated_at=str(data.get("updated_at", "")) or utc_now_iso(),
            metadata=data.get("metadata", {})
            if isinstance(data.get("metadata", {}), dict)
            else {},
        )


class SessionSummaryStore:
    """用本地 JSON 保存 Session Summary。"""

    def __init__(self, session_dir: str = ".micode/sessions") -> None:
        self.session_dir = Path(session_dir)

    def load(self, session_id: str) -> SessionSummary:
        """读取 Session Summary；不存在时返回空摘要。"""
        path = self.path_for(session_id)
        if not path.exists():
            return SessionSummary(session_id=session_id)

        data = json.loads(path.read_text(encoding="utf-8"))
        return SessionSummary.from_dict(data)

    def save(self, summary: SessionSummary) -> str:
        """保存 Session Summary，并返回文件路径。"""
        self.session_dir.mkdir(parents=True, exist_ok=True)
        path = self.path_for(summary.session_id)
        path.write_text(
            json.dumps(summary.to_dict(), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return str(path)

    def path_for(self, session_id: str) -> Path:
        """根据 session_id 计算 summary 文件路径。"""
        normalized_session_id = session_id.strip()
        if not normalized_session_id:
            raise ValueError("session_id is required")
        return self.session_dir / f"{normalized_session_id}.summary.json"


class ContextCompressor:
    """把较早 SessionMessage 压缩成 SessionSummary，并保留最近消息。"""

    def __init__(
        self,
        recent_message_limit: int = DEFAULT_RECENT_MESSAGE_LIMIT,
        summarizer_client=None,
    ) -> None:
        if recent_message_limit < 0:
            raise ValueError("recent_message_limit must be non-negative")
        self.recent_message_limit = recent_message_limit
        # summarizer_client 只需要 generate(prompt)，可复用 OpenAI-compatible client。
        self.summarizer_client = summarizer_client

    def split_messages(
        self,
        messages: list[SessionMessage],
    ) -> tuple[list[SessionMessage], list[SessionMessage]]:
        """把消息拆成待压缩的历史消息和仍保留原文的最近消息。"""
        if self.recent_message_limit == 0:
            return list(messages), []
        if len(messages) <= self.recent_message_limit:
            return [], list(messages)
        return messages[:-self.recent_message_limit], messages[-self.recent_message_limit:]

    def summarize(
        self,
        session_id: str,
        messages: list[SessionMessage],
        previous_summary: Optional[SessionSummary] = None,
    ) -> SessionSummary:
        """压缩消息为摘要；已覆盖过的消息不会重复写入。"""
        previous = previous_summary or SessionSummary(session_id=session_id)
        covered = set(previous.covered_message_ids)
        new_messages = [message for message in messages if message.id not in covered]
        if not new_messages:
            return previous

        new_structured = summarize_messages_structured(
            new_messages,
            self.summarizer_client,
        )
        previous_structured = previous.structured
        if not previous_structured and previous.summary:
            # 兼容旧版只有 summary 文本的存量文件。
            previous_structured = {
                **empty_structured_summary(),
                "overview": previous.summary,
            }
        structured = merge_structured_summaries(previous_structured, new_structured)
        summary_text = format_structured_summary(structured)

        covered_message_ids = previous.covered_message_ids + [
            message.id for message in new_messages
        ]

        return SessionSummary(
            session_id=session_id,
            summary=limit_summary_lines(summary_text),
            structured=structured,
            covered_message_ids=covered_message_ids,
            source_message_count=len(covered_message_ids),
            updated_at=utc_now_iso(),
            metadata={
                "recent_message_limit": self.recent_message_limit,
                "summarizer": "llm" if self.summarizer_client else "deterministic",
            },
        )

    def compact(
        self,
        session_id: str,
        messages: list[SessionMessage],
        previous_summary: Optional[SessionSummary] = None,
    ) -> tuple[SessionSummary, list[SessionMessage]]:
        """返回最新 summary 和最近消息。"""
        history, recent = self.split_messages(messages)
        summary = self.summarize(session_id, history, previous_summary)
        return summary, recent


def build_session_context(
    working_memory: WorkingMemory,
    summary: SessionSummary,
    recent_messages: list[SessionMessage],
) -> str:
    """构建适合注入 prompt 的紧凑 session context 文本。"""
    lines = ["Session Context:"]

    if working_memory.current_goal:
        lines.append(f"Current goal: {working_memory.current_goal}")
    if working_memory.constraints:
        lines.append("Constraints:")
        lines.extend(f"- {item}" for item in working_memory.constraints)
    if working_memory.todo:
        lines.append("Todo:")
        lines.extend(f"- {item}" for item in working_memory.todo)
    if working_memory.completed:
        lines.append("Completed:")
        lines.extend(f"- {item}" for item in working_memory.completed[-5:])
    if summary.summary:
        lines.append("Session summary:")
        lines.append(summary.summary)
    if recent_messages:
        lines.append("Recent messages:")
        for message in recent_messages:
            lines.append(
                f"- {message.role}/{message.type}: "
                f"{truncate_memory_text(message.content, max_length=240)}"
            )

    if len(lines) == 1:
        return ""
    return "\n".join(lines)


def format_messages_as_summary(messages: list[SessionMessage]) -> str:
    """把消息压缩成结构化摘要文本。"""
    return format_structured_summary(summarize_messages_structured(messages))


def summarize_messages_structured(
    messages: list[SessionMessage],
    summarizer_client=None,
) -> dict:
    """生成结构化摘要；优先 LLM，失败时使用确定性兜底。"""
    if summarizer_client is not None and messages:
        prompt = build_summary_prompt(messages)
        try:
            text = summarizer_client.generate(prompt)
            structured = parse_summary_response(text)
            if structured:
                return structured
        except Exception:
            # 摘要不能影响主流程；模型摘要失败时回退到可测试的确定性摘要。
            pass
    return deterministic_structured_summary(messages)


def build_summary_prompt(messages: list[SessionMessage]) -> str:
    """构建 LLM summarizer prompt，要求返回结构化 JSON。"""
    message_lines = []
    for message in messages:
        content = truncate_memory_text(message.content, max_length=700)
        message_lines.append(
            f"- id={message.id} role={message.role} type={message.type} "
            f"content={json.dumps(content, ensure_ascii=False)}"
        )

    return f"""
You are Micode's session memory summarizer.

Summarize the older session messages into one JSON object.
Return exactly this shape:
{{
  "overview": "short paragraph",
  "goals": ["active or historical goals"],
  "decisions": ["important decisions"],
  "completed": ["completed work"],
  "errors": ["errors or blockers"],
  "constraints": ["user constraints or project rules"],
  "next_steps": ["useful next steps"]
}}

Rules:
- Keep each item concise.
- Do not include raw API keys or secrets.
- Do not invent facts not supported by the messages.
- Return JSON only.

Messages:
{chr(10).join(message_lines)}
""".strip()


def parse_summary_response(text: str) -> dict:
    """解析 LLM summarizer JSON。"""
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return {}
    if not isinstance(data, dict):
        return {}
    return normalize_structured_summary(data)


def deterministic_structured_summary(messages: list[SessionMessage]) -> dict:
    """无 LLM 时的结构化兜底摘要。"""
    structured = empty_structured_summary()
    for message in messages:
        content = truncate_memory_text(message.content, max_length=140)
        if not content:
            continue
        if message.role == "user":
            structured["goals"].append(content)
        elif message.role == "assistant":
            structured["completed"].append(content)
        elif message.role == "error":
            structured["errors"].append(content)
        elif message.role == "tool":
            structured["decisions"].append(f"Tool {message.type}: {content}")
        else:
            structured["overview"] = append_sentence(structured["overview"], content)

    if not structured["overview"] and messages:
        structured["overview"] = "Older session messages were summarized structurally."
    return normalize_structured_summary(structured)


def merge_structured_summaries(previous: dict, new: dict) -> dict:
    """合并旧结构化摘要和新摘要，按字段去重。"""
    merged = empty_structured_summary()
    previous = normalize_structured_summary(previous)
    new = normalize_structured_summary(new)
    merged["overview"] = "\n".join(
        item for item in [previous.get("overview", ""), new.get("overview", "")] if item
    )
    for key in ["goals", "decisions", "completed", "errors", "constraints", "next_steps"]:
        merged[key] = unique_strings(previous.get(key, []) + new.get(key, []))
    return merged


def format_structured_summary(structured: dict) -> str:
    """把结构化摘要格式化成 prompt 友好的文本。"""
    structured = normalize_structured_summary(structured)
    lines = []
    if structured["overview"]:
        lines.append(f"Overview: {structured['overview']}")
    labels = [
        ("goals", "Goals"),
        ("decisions", "Decisions"),
        ("completed", "Completed"),
        ("errors", "Errors"),
        ("constraints", "Constraints"),
        ("next_steps", "Next steps"),
    ]
    for key, label in labels:
        items = structured[key]
        if not items:
            continue
        lines.append(f"{label}:")
        lines.extend(f"- {item}" for item in items[-8:])
    return "\n".join(lines)


def normalize_structured_summary(data: dict) -> dict:
    """规范化结构化摘要字段。"""
    normalized = empty_structured_summary()
    normalized["overview"] = str(data.get("overview", "")).strip()
    for key in ["goals", "decisions", "completed", "errors", "constraints", "next_steps"]:
        normalized[key] = unique_strings(_string_list(data.get(key, [])))
    return normalized


def empty_structured_summary() -> dict:
    return {
        "overview": "",
        "goals": [],
        "decisions": [],
        "completed": [],
        "errors": [],
        "constraints": [],
        "next_steps": [],
    }


def unique_strings(items: list[str]) -> list[str]:
    """保持顺序去重。"""
    seen = set()
    result = []
    for item in items:
        normalized = item.strip()
        if not normalized or normalized in seen:
            continue
        result.append(normalized)
        seen.add(normalized)
    return result


def append_sentence(text: str, sentence: str) -> str:
    if not text:
        return sentence
    return f"{text}\n{sentence}"


def limit_summary_lines(summary: str, max_lines: int = SUMMARY_ITEM_LIMIT) -> str:
    """限制摘要行数，避免 summary 自己无限增长。"""
    lines = [line for line in summary.splitlines() if line.strip()]
    if len(lines) <= max_lines:
        return "\n".join(lines)
    omitted = len(lines) - max_lines
    kept = lines[-max_lines:]
    return "\n".join([f"- ... {omitted} older summary lines omitted"] + kept)


def _string_list(value) -> list[str]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, str)]
