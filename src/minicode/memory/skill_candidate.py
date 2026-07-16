import json
from dataclasses import dataclass, field
from pathlib import Path

from minicode.memory.procedural import ProceduralMemory, slugify_procedure_name
from minicode.memory.session import utc_now_iso
from minicode.skills import Skill


DRAFT = "draft"
APPROVED = "approved"
REJECTED = "rejected"
PROMOTED = "promoted"
VALID_SKILL_CANDIDATE_STATUSES = {DRAFT, APPROVED, REJECTED, PROMOTED}


@dataclass
class SkillCandidate:
    """SkillCandidate 是经验到正式 Skill 之间的缓冲层。"""

    id: str
    name: str
    description: str
    content: str
    tags: list[str] = field(default_factory=list)
    status: str = DRAFT
    confidence: float = 0.5
    source_procedure_ids: list[str] = field(default_factory=list)
    source_episode_ids: list[str] = field(default_factory=list)
    source_run_ids: list[str] = field(default_factory=list)
    review_notes: list[str] = field(default_factory=list)
    created_at: str = field(default_factory=utc_now_iso)
    updated_at: str = field(default_factory=utc_now_iso)

    def to_dict(self) -> dict:
        """转成可落盘的 JSON dict。"""
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "content": self.content,
            "tags": self.tags,
            "status": self.status,
            "confidence": self.confidence,
            "source_procedure_ids": self.source_procedure_ids,
            "source_episode_ids": self.source_episode_ids,
            "source_run_ids": self.source_run_ids,
            "review_notes": self.review_notes,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "SkillCandidate":
        """从 JSON dict 还原 SkillCandidate。"""
        return cls(
            id=str(data.get("id", "")),
            name=str(data.get("name", "")),
            description=str(data.get("description", "")),
            content=str(data.get("content", "")),
            tags=_string_list(data.get("tags", [])),
            status=str(data.get("status", DRAFT)) or DRAFT,
            confidence=float(data.get("confidence", 0.5) or 0.5),
            source_procedure_ids=_string_list(data.get("source_procedure_ids", [])),
            source_episode_ids=_string_list(data.get("source_episode_ids", [])),
            source_run_ids=_string_list(data.get("source_run_ids", [])),
            review_notes=_string_list(data.get("review_notes", [])),
            created_at=str(data.get("created_at", "")) or utc_now_iso(),
            updated_at=str(data.get("updated_at", "")) or utc_now_iso(),
        )

    def to_skill(self) -> Skill:
        """提升前的纯转换；是否允许提升由 promote 流程判断。"""
        return Skill(
            name=self.name,
            description=self.description,
            content=self.content,
            tags=list(self.tags),
        )


class SkillCandidateStore:
    """用一个目录保存多个 SkillCandidate JSON 文件。"""

    def __init__(self, candidate_dir: str = ".minicode/skill-candidates") -> None:
        self.candidate_dir = Path(candidate_dir)

    def load_all(self) -> list[SkillCandidate]:
        """读取全部候选；目录不存在时返回空列表。"""
        if not self.candidate_dir.exists():
            return []

        candidates = []
        for path in sorted(self.candidate_dir.glob("*.json")):
            data = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                candidates.append(SkillCandidate.from_dict(data))
        return candidates

    def get(self, candidate_id: str) -> SkillCandidate:
        """按 id 读取候选；不存在时抛出 KeyError。"""
        path = self.path_for(candidate_id)
        if not path.exists():
            raise KeyError(f"unknown skill candidate: {candidate_id}")
        return SkillCandidate.from_dict(json.loads(path.read_text(encoding="utf-8")))

    def save(self, candidate: SkillCandidate) -> str:
        """保存单个候选。"""
        self.candidate_dir.mkdir(parents=True, exist_ok=True)
        path = self.path_for(candidate.id)
        path.write_text(
            json.dumps(candidate.to_dict(), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return str(path)

    def upsert_many(self, candidates: list[SkillCandidate]) -> list[SkillCandidate]:
        """合并保存候选；已 review 的候选不会被 draft 覆盖状态。"""
        existing = {candidate.id: candidate for candidate in self.load_all()}
        for candidate in candidates:
            previous = existing.get(candidate.id)
            if previous is not None:
                candidate = merge_skill_candidate(previous, candidate)
            existing[candidate.id] = candidate

        saved = list(existing.values())
        for candidate in saved:
            self.save(candidate)
        return saved

    def path_for(self, candidate_id: str) -> Path:
        """返回候选文件路径。"""
        return self.candidate_dir / f"{safe_candidate_filename(candidate_id)}.json"


def skill_candidate_from_procedure(memory: ProceduralMemory) -> SkillCandidate:
    """把 Procedure 转成 draft SkillCandidate。"""
    content = build_candidate_content(memory)
    return SkillCandidate(
        id=stable_skill_candidate_id(memory.name),
        name=memory.name,
        description=memory.description,
        content=content,
        tags=list(memory.tags),
        status=DRAFT,
        confidence=0.6,
        source_procedure_ids=[memory.id],
        source_episode_ids=list(memory.source_episode_ids),
        source_run_ids=list(memory.source_run_ids),
        review_notes=[],
        created_at=memory.created_at,
        updated_at=utc_now_iso(),
    )


def skill_candidates_from_procedures(
    memories: list[ProceduralMemory],
) -> list[SkillCandidate]:
    """批量从 Procedure 生成候选。"""
    return [skill_candidate_from_procedure(memory) for memory in memories]


def approve_skill_candidate(
    store: SkillCandidateStore,
    candidate_id: str,
    note: str = "",
) -> SkillCandidate:
    """把候选标记为 approved。"""
    return update_skill_candidate_status(store, candidate_id, APPROVED, note)


def reject_skill_candidate(
    store: SkillCandidateStore,
    candidate_id: str,
    note: str = "",
) -> SkillCandidate:
    """把候选标记为 rejected。"""
    return update_skill_candidate_status(store, candidate_id, REJECTED, note)


def promote_skill_candidate(
    store: SkillCandidateStore,
    candidate_id: str,
    skills_root: str = ".minicode/skills",
    note: str = "",
    force: bool = False,
) -> dict:
    """把 approved candidate 写成正式 SKILL.md，并标记为 promoted。"""
    candidate = store.get(candidate_id)
    if candidate.status != APPROVED and not force:
        raise ValueError("skill candidate must be approved before promotion")

    skill_dir = Path(skills_root) / candidate.name
    skill_path = skill_dir / "SKILL.md"
    skill_dir.mkdir(parents=True, exist_ok=True)
    if skill_path.exists():
        existing = skill_path.read_text(encoding="utf-8")
        if existing != candidate.content and not force:
            raise FileExistsError(f"skill already exists: {skill_path}")

    skill_path.write_text(candidate.content, encoding="utf-8")
    promoted = update_skill_candidate_status(
        store,
        candidate_id,
        PROMOTED,
        note or f"Promoted to {skill_path}",
    )
    return {
        "candidate": promoted.to_dict(),
        "skill_path": str(skill_path),
    }


def update_skill_candidate_status(
    store: SkillCandidateStore,
    candidate_id: str,
    status: str,
    note: str = "",
) -> SkillCandidate:
    """更新候选状态，并追加 review note。"""
    if status not in VALID_SKILL_CANDIDATE_STATUSES:
        raise ValueError(f"invalid skill candidate status: {status}")

    candidate = store.get(candidate_id)
    candidate.status = status
    candidate.updated_at = utc_now_iso()
    if note:
        candidate.review_notes.append(note)
    store.save(candidate)
    return candidate


def merge_skill_candidate(
    previous: SkillCandidate,
    current: SkillCandidate,
) -> SkillCandidate:
    """合并同一个候选的来源；保留已有 review 状态和 notes。"""
    return SkillCandidate(
        id=previous.id,
        name=current.name or previous.name,
        description=current.description or previous.description,
        content=current.content or previous.content,
        tags=_merge_unique(previous.tags, current.tags),
        status=previous.status if previous.status != DRAFT else current.status,
        confidence=max(previous.confidence, current.confidence),
        source_procedure_ids=_merge_unique(
            previous.source_procedure_ids,
            current.source_procedure_ids,
        ),
        source_episode_ids=_merge_unique(
            previous.source_episode_ids,
            current.source_episode_ids,
        ),
        source_run_ids=_merge_unique(previous.source_run_ids, current.source_run_ids),
        review_notes=_merge_unique(previous.review_notes, current.review_notes),
        created_at=previous.created_at,
        updated_at=utc_now_iso(),
    )


def build_candidate_content(memory: ProceduralMemory) -> str:
    """把 Procedure 写成正式 SKILL.md 可用的 Markdown 草稿。"""
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
        lines.extend(
            f"{index}. {step}"
            for index, step in enumerate(memory.steps, start=1)
        )
    return "\n".join(lines)


def stable_skill_candidate_id(name: str) -> str:
    """按候选名称生成稳定 id。"""
    return f"skill-candidate:{slugify_procedure_name(name)}"


def safe_candidate_filename(candidate_id: str) -> str:
    """把 candidate id 转成文件名。"""
    return "".join(char if char.isalnum() else "-" for char in candidate_id).strip("-")


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
