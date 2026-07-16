import json
from dataclasses import dataclass, field
from pathlib import Path

from minicode.memory.episodic import EpisodicMemory
from minicode.memory.session import utc_now_iso
from minicode.memory.working import truncate_memory_text
from minicode.skills import Skill


@dataclass
class ProceduralMemory:
    """ProceduralMemory 表示可复用的做事流程。"""

    id: str
    name: str
    description: str
    steps: list[str] = field(default_factory=list)
    when_to_use: list[str] = field(default_factory=list)
    when_not_to_use: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    source_episode_ids: list[str] = field(default_factory=list)
    source_run_ids: list[str] = field(default_factory=list)
    created_at: str = field(default_factory=utc_now_iso)
    updated_at: str = field(default_factory=utc_now_iso)
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        """转成可保存的 JSON dict。"""
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "steps": self.steps,
            "when_to_use": self.when_to_use,
            "when_not_to_use": self.when_not_to_use,
            "tags": self.tags,
            "source_episode_ids": self.source_episode_ids,
            "source_run_ids": self.source_run_ids,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "ProceduralMemory":
        """从 JSON dict 还原 ProceduralMemory。"""
        return cls(
            id=str(data.get("id", "")),
            name=str(data.get("name", "")),
            description=str(data.get("description", "")),
            steps=_string_list(data.get("steps", [])),
            when_to_use=_string_list(data.get("when_to_use", [])),
            when_not_to_use=_string_list(data.get("when_not_to_use", [])),
            tags=_string_list(data.get("tags", [])),
            source_episode_ids=_string_list(data.get("source_episode_ids", [])),
            source_run_ids=_string_list(data.get("source_run_ids", [])),
            created_at=str(data.get("created_at", "")) or utc_now_iso(),
            updated_at=str(data.get("updated_at", "")) or utc_now_iso(),
            metadata=data.get("metadata", {})
            if isinstance(data.get("metadata", {}), dict)
            else {},
        )


class ProceduralMemoryStore:
    """用本地 JSON 保存 procedural memories。"""

    def __init__(self, memory_dir: str = ".minicode/memory") -> None:
        self.memory_dir = Path(memory_dir)

    def load_all(self) -> list[ProceduralMemory]:
        """读取全部 procedural memories；不存在时返回空列表。"""
        path = self.path()
        if not path.exists():
            return []

        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, list):
            return []
        return [
            ProceduralMemory.from_dict(item)
            for item in data
            if isinstance(item, dict)
        ]

    def save_all(self, memories: list[ProceduralMemory]) -> str:
        """保存完整 procedural memory 列表。"""
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

    def upsert_many(self, memories: list[ProceduralMemory]) -> list[ProceduralMemory]:
        """按 id 合并多条 procedure。"""
        existing = {memory.id: memory for memory in self.load_all()}
        for memory in memories:
            previous = existing.get(memory.id)
            if previous is not None:
                memory = merge_procedural_memory(previous, memory)
            existing[memory.id] = memory

        saved = list(existing.values())
        self.save_all(saved)
        return saved

    def search(self, query: str, limit: int = 10) -> list[ProceduralMemory]:
        """轻量关键词搜索；后续可接入 hybrid retrieval。"""
        if limit <= 0:
            return []

        query_text = query.lower()
        matched = []
        for memory in self.load_all():
            haystack = " ".join(
                [memory.name, memory.description]
                + memory.tags
                + memory.steps
                + memory.when_to_use
            ).lower()
            if query_text in haystack:
                matched.append(memory)
            if len(matched) >= limit:
                break
        return matched

    def path(self) -> Path:
        """返回 procedural memory 文件路径。"""
        return self.memory_dir / "procedures.json"


def procedural_memories_from_episode(
    episode: EpisodicMemory,
    extractor_client=None,
) -> list[ProceduralMemory]:
    """从成功 episode 中提炼 procedural memories。"""
    if not is_successful_episode(episode):
        return []

    if extractor_client is not None:
        try:
            text = extractor_client.generate(build_procedural_extraction_prompt(episode))
            extracted = parse_procedural_extraction_response(text, episode)
            if extracted:
                return extracted
        except Exception:
            # 程序记忆提炼失败不能影响 Agent 主流程。
            pass

    return deterministic_procedural_memories_from_episode(episode)


def deterministic_procedural_memories_from_episode(
    episode: EpisodicMemory,
) -> list[ProceduralMemory]:
    """不依赖模型的流程记忆兜底提炼。"""
    if not is_successful_episode(episode):
        return []

    steps = []
    if episode.task:
        steps.append(f"Clarify the task: {truncate_memory_text(episode.task, 160)}")
    for tool_name in episode.tool_names:
        steps.append(f"Use {tool_name} when needed.")
    if episode.outcome:
        steps.append(f"Verify the outcome: {truncate_memory_text(episode.outcome, 160)}")

    name = slugify_procedure_name(episode.task or "procedure")
    return [
        ProceduralMemory(
            id=stable_procedural_id(name),
            name=name,
            description=truncate_memory_text(
                episode.task or episode.outcome or "Reusable procedure",
                240,
            ),
            steps=steps,
            when_to_use=[episode.task] if episode.task else [],
            when_not_to_use=["When the task is unrelated to this workflow."],
            tags=["procedure"] + episode.tool_names,
            source_episode_ids=[episode.id],
            source_run_ids=[episode.run_id],
            created_at=episode.created_at,
            updated_at=utc_now_iso(),
            metadata={"session_id": episode.session_id},
        )
    ]


def build_procedural_extraction_prompt(episode: EpisodicMemory) -> str:
    """构建 procedure 抽取 prompt。"""
    episode_text = json.dumps(episode.to_dict(), ensure_ascii=False)
    return f"""
You are MiniCode's procedural memory extractor.

Extract reusable procedures from this successful episode.
Return exactly one JSON object:
{{
  "procedures": [
    {{
      "name": "short-kebab-case-name",
      "description": "what this procedure helps with",
      "steps": ["ordered reusable steps"],
      "when_to_use": ["applicable situations"],
      "when_not_to_use": ["non-applicable situations"],
      "tags": ["short tags"]
    }}
  ]
}}

Rules:
- Extract only reusable workflows, not one-off facts.
- Do not include API keys, secrets, or credentials.
- Keep steps actionable and concise.
- Return an empty procedures list if there is no reusable workflow.
- Return JSON only.

Episode:
{episode_text}
""".strip()


def parse_procedural_extraction_response(
    text: str,
    episode: EpisodicMemory,
) -> list[ProceduralMemory]:
    """解析 LLM 返回的 procedure JSON。"""
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return []

    if not isinstance(data, dict) or not isinstance(data.get("procedures"), list):
        return []

    memories = []
    for item in data["procedures"]:
        if not isinstance(item, dict):
            continue
        name = slugify_procedure_name(str(item.get("name", "")))
        description = str(item.get("description", "")).strip()
        steps = _string_list(item.get("steps", []))
        if not name or not description or not steps:
            continue

        memories.append(
            ProceduralMemory(
                id=stable_procedural_id(name),
                name=name,
                description=description,
                steps=steps,
                when_to_use=_string_list(item.get("when_to_use", [])),
                when_not_to_use=_string_list(item.get("when_not_to_use", [])),
                tags=_string_list(item.get("tags", [])),
                source_episode_ids=[episode.id],
                source_run_ids=[episode.run_id],
                created_at=episode.created_at,
                updated_at=utc_now_iso(),
                metadata={"session_id": episode.session_id},
            )
        )
    return memories


def procedural_memory_to_skill(memory: ProceduralMemory) -> Skill:
    """把 Procedure 转成 Skill 候选；Skill 本体仍只保留四字段。"""
    lines = [
        f"# {memory.name}",
        "",
        memory.description,
    ]
    if memory.when_to_use:
        lines.extend(["", "## When to use"])
        lines.extend(f"- {item}" for item in memory.when_to_use)
    if memory.when_not_to_use:
        lines.extend(["", "## When not to use"])
        lines.extend(f"- {item}" for item in memory.when_not_to_use)
    if memory.steps:
        lines.extend(["", "## Steps"])
        lines.extend(f"{index}. {step}" for index, step in enumerate(memory.steps, start=1))

    return Skill(
        name=memory.name,
        description=memory.description,
        content="\n".join(lines),
        tags=list(memory.tags),
    )


def merge_procedural_memory(
    previous: ProceduralMemory,
    current: ProceduralMemory,
) -> ProceduralMemory:
    """合并同名流程的来源、步骤和标签。"""
    return ProceduralMemory(
        id=previous.id,
        name=current.name or previous.name,
        description=current.description or previous.description,
        steps=_merge_unique(previous.steps, current.steps),
        when_to_use=_merge_unique(previous.when_to_use, current.when_to_use),
        when_not_to_use=_merge_unique(
            previous.when_not_to_use,
            current.when_not_to_use,
        ),
        tags=_merge_unique(previous.tags, current.tags),
        source_episode_ids=_merge_unique(
            previous.source_episode_ids,
            current.source_episode_ids,
        ),
        source_run_ids=_merge_unique(previous.source_run_ids, current.source_run_ids),
        created_at=previous.created_at,
        updated_at=utc_now_iso(),
        metadata={**previous.metadata, **current.metadata},
    )


def is_successful_episode(episode: EpisodicMemory) -> bool:
    """只有成功经历才适合提炼成做法。"""
    return episode.status == "completed" and bool(episode.outcome)


def stable_procedural_id(name: str) -> str:
    """按流程名称生成稳定 id。"""
    return f"procedure:{slugify_procedure_name(name)}"


def slugify_procedure_name(text: str) -> str:
    """把任意名称压成简单 kebab-case。"""
    normalized = text.strip().lower()
    chars = []
    for char in normalized:
        if char.isalnum():
            chars.append(char)
        else:
            chars.append("-")
    slug = "".join(chars)
    while "--" in slug:
        slug = slug.replace("--", "-")
    return slug.strip("-")[:80] or "procedure"


def _merge_unique(first: list[str], second: list[str]) -> list[str]:
    merged = []
    for item in first + second:
        if item and item not in merged:
            merged.append(item)
    return merged


def _string_list(value) -> list[str]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, str) and item.strip()]
