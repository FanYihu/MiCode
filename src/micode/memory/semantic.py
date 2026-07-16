import json
from dataclasses import dataclass, field
from pathlib import Path

from micode.memory.episodic import EpisodicMemory
from micode.memory.session import utc_now_iso
from micode.memory.working import truncate_memory_text


@dataclass
class SemanticMemory:
    """SemanticMemory 表示从经历中提炼出的稳定事实。"""

    id: str
    fact: str
    subject: str = ""
    predicate: str = ""
    object: str = ""
    confidence: float = 0.7
    source_episode_ids: list[str] = field(default_factory=list)
    source_run_ids: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    created_at: str = field(default_factory=utc_now_iso)
    updated_at: str = field(default_factory=utc_now_iso)
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        """转成可保存的 JSON dict。"""
        return {
            "id": self.id,
            "fact": self.fact,
            "subject": self.subject,
            "predicate": self.predicate,
            "object": self.object,
            "confidence": self.confidence,
            "source_episode_ids": self.source_episode_ids,
            "source_run_ids": self.source_run_ids,
            "tags": self.tags,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "SemanticMemory":
        """从 JSON dict 还原 SemanticMemory。"""
        return cls(
            id=str(data.get("id", "")),
            fact=str(data.get("fact", "")),
            subject=str(data.get("subject", "")),
            predicate=str(data.get("predicate", "")),
            object=str(data.get("object", "")),
            confidence=float(data.get("confidence", 0.7) or 0.7),
            source_episode_ids=_string_list(data.get("source_episode_ids", [])),
            source_run_ids=_string_list(data.get("source_run_ids", [])),
            tags=_string_list(data.get("tags", [])),
            created_at=str(data.get("created_at", "")) or utc_now_iso(),
            updated_at=str(data.get("updated_at", "")) or utc_now_iso(),
            metadata=data.get("metadata", {})
            if isinstance(data.get("metadata", {}), dict)
            else {},
        )


class SemanticMemoryStore:
    """用本地 JSON 保存 semantic memories。"""

    def __init__(self, memory_dir: str = ".micode/memory") -> None:
        self.memory_dir = Path(memory_dir)

    def load_all(self) -> list[SemanticMemory]:
        """读取全部 semantic memories；不存在时返回空列表。"""
        path = self.path()
        if not path.exists():
            return []

        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, list):
            return []
        return [
            SemanticMemory.from_dict(item)
            for item in data
            if isinstance(item, dict)
        ]

    def save_all(self, memories: list[SemanticMemory]) -> str:
        """保存完整 semantic memory 列表。"""
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

    def upsert_many(self, memories: list[SemanticMemory]) -> list[SemanticMemory]:
        """按 id 合并多条 semantic memory。"""
        existing = {memory.id: memory for memory in self.load_all()}
        for memory in memories:
            previous = existing.get(memory.id)
            if previous is not None:
                memory = merge_semantic_memory(previous, memory)
            existing[memory.id] = memory

        saved = list(existing.values())
        self.save_all(saved)
        return saved

    def search(self, query: str, limit: int = 10) -> list[SemanticMemory]:
        """轻量关键词搜索；后续 Day53 会替换成 hybrid retrieval。"""
        if limit <= 0:
            return []

        query_text = query.lower()
        matched = []
        for memory in self.load_all():
            haystack = " ".join(
                [memory.fact, memory.subject, memory.predicate, memory.object]
                + memory.tags
            ).lower()
            if query_text in haystack:
                matched.append(memory)
            if len(matched) >= limit:
                break
        return matched

    def path(self) -> Path:
        """返回 semantic memory 文件路径。"""
        return self.memory_dir / "semantic.json"


def semantic_memories_from_episode(
    episode: EpisodicMemory,
    extractor_client=None,
) -> list[SemanticMemory]:
    """从 episode 中提炼语义事实。

    优先用 LLM 抽取结构化事实；失败时回退到确定性提炼。
    """
    if extractor_client is not None:
        try:
            text = extractor_client.generate(build_semantic_extraction_prompt(episode))
            extracted = parse_semantic_extraction_response(text, episode)
            if extracted:
                return extracted
        except Exception:
            # 长期记忆提炼失败不能影响 Agent 主流程。
            pass

    return deterministic_semantic_memories_from_episode(episode)


def deterministic_semantic_memories_from_episode(
    episode: EpisodicMemory,
) -> list[SemanticMemory]:
    """不依赖模型的语义事实兜底提炼。"""
    memories = []

    if episode.task:
        memories.append(
            make_semantic_memory(
                episode,
                subject="task",
                predicate="was_requested",
                object_value=truncate_memory_text(episode.task),
                tags=["task", "episode"],
            )
        )

    if episode.outcome:
        memories.append(
            make_semantic_memory(
                episode,
                subject="task",
                predicate="had_outcome",
                object_value=truncate_memory_text(episode.outcome),
                tags=["outcome", episode.status],
            )
        )

    for tool_name in episode.tool_names:
        memories.append(
            make_semantic_memory(
                episode,
                subject="run",
                predicate="used_tool",
                object_value=tool_name,
                tags=["tool", tool_name],
            )
        )

    for evidence in episode.evidence:
        fact_text = evidence.strip()
        if not fact_text:
            continue
        memories.append(
            make_semantic_memory(
                episode,
                subject="episode",
                predicate="has_evidence",
                object_value=truncate_memory_text(fact_text),
                tags=["evidence"],
                confidence=0.6,
            )
        )

    return memories


def build_semantic_extraction_prompt(episode: EpisodicMemory) -> str:
    """构建语义事实抽取 prompt。"""
    episode_text = json.dumps(episode.to_dict(), ensure_ascii=False)
    return f"""
You are Micode's semantic memory extractor.

Extract stable, reusable facts from the episode.
Return exactly one JSON object:
{{
  "facts": [
    {{
      "subject": "entity or concept",
      "predicate": "short relation",
      "object": "fact value",
      "confidence": 0.0,
      "tags": ["short tags"]
    }}
  ]
}}

Rules:
- Extract facts useful in future tasks.
- Do not merely repeat transient tool output.
- Do not store API keys, secrets, or credentials.
- Do not invent facts.
- Use confidence between 0 and 1.
- Return an empty facts list when no stable fact exists.
- Return JSON only.

Episode:
{episode_text}
""".strip()


def parse_semantic_extraction_response(
    text: str,
    episode: EpisodicMemory,
) -> list[SemanticMemory]:
    """解析 LLM 返回的结构化事实。"""
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return []

    if not isinstance(data, dict) or not isinstance(data.get("facts"), list):
        return []

    memories = []
    for item in data["facts"]:
        if not isinstance(item, dict):
            continue
        subject = _clean_string(item.get("subject"))
        predicate = _clean_string(item.get("predicate"))
        object_value = _clean_string(item.get("object"))
        if not subject or not predicate or not object_value:
            continue

        confidence = _clean_confidence(item.get("confidence"))
        memories.append(
            make_semantic_memory(
                episode,
                subject=subject,
                predicate=predicate,
                object_value=object_value,
                tags=_string_list(item.get("tags", [])),
                confidence=confidence,
            )
        )
    return memories


def make_semantic_memory(
    episode: EpisodicMemory,
    subject: str,
    predicate: str,
    object_value: str,
    tags: list[str],
    confidence: float = 0.7,
) -> SemanticMemory:
    """创建带稳定 id 的 semantic memory。"""
    memory_id = stable_semantic_id(
        subject,
        predicate,
        object_value,
    )
    fact = f"{subject} {predicate} {object_value}"
    return SemanticMemory(
        id=memory_id,
        fact=fact,
        subject=subject,
        predicate=predicate,
        object=object_value,
        confidence=confidence,
        source_episode_ids=[episode.id],
        source_run_ids=[episode.run_id],
        tags=tags,
        created_at=episode.created_at,
        updated_at=utc_now_iso(),
        metadata={"session_id": episode.session_id},
    )


def merge_semantic_memory(
    previous: SemanticMemory,
    current: SemanticMemory,
) -> SemanticMemory:
    """合并同一事实的来源和标签。"""
    return SemanticMemory(
        id=previous.id,
        fact=current.fact or previous.fact,
        subject=current.subject or previous.subject,
        predicate=current.predicate or previous.predicate,
        object=current.object or previous.object,
        confidence=max(previous.confidence, current.confidence),
        source_episode_ids=_merge_unique(
            previous.source_episode_ids,
            current.source_episode_ids,
        ),
        source_run_ids=_merge_unique(previous.source_run_ids, current.source_run_ids),
        tags=_merge_unique(previous.tags, current.tags),
        created_at=previous.created_at,
        updated_at=utc_now_iso(),
        metadata={**previous.metadata, **current.metadata},
    )


def stable_semantic_id(
    subject: str,
    predicate: str,
    object_value: str,
) -> str:
    """生成稳定事实 id；跨 episode 的相同事实会合并来源。"""
    normalized = "|".join(
        [
            subject.strip().lower(),
            predicate.strip().lower(),
            object_value.strip().lower(),
        ]
    )
    safe = "".join(char if char.isalnum() else "-" for char in normalized)
    while "--" in safe:
        safe = safe.replace("--", "-")
    return f"semantic:{safe.strip('-')[:160]}"


def _merge_unique(first: list[str], second: list[str]) -> list[str]:
    merged = []
    for item in first + second:
        if item and item not in merged:
            merged.append(item)
    return merged


def _string_list(value) -> list[str]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, str)]


def _clean_string(value) -> str:
    return value.strip() if isinstance(value, str) else ""


def _clean_confidence(value) -> float:
    try:
        confidence = float(value)
    except (TypeError, ValueError):
        return 0.7
    return max(0.0, min(1.0, confidence))
