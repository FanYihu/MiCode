from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from micode.workspace import Workspace


SMALL_SKILL_COUNT = 20
_SKILL_DIRECTORIES: dict[int, Path] = {}


@dataclass
class Skill:
    """Skill 描述一个可注入给模型的高层操作能力。"""

    name: str
    description: str
    content: str
    tags: list[str] = field(default_factory=list)


def format_skill_for_prompt(skill: Skill) -> str:
    """把 Skill 格式化为适合 prompt 注入的紧凑文本。"""
    lines = [
        f"Skill: {skill.name}",
        f"Description: {skill.description}",
    ]

    if skill.tags:
        lines.append(f"Tags: {', '.join(skill.tags)}")

    lines.extend(["", skill.content])
    return "\n".join(lines)


def format_skill_summary(skill: Skill) -> str:
    """格式化 Skill 摘要，不包含完整 content。"""
    suffixes = []
    if skill.tags:
        suffixes.append(f"tags: {', '.join(skill.tags)}")

    suffix = f" [{' | '.join(suffixes)}]" if suffixes else ""
    return f"- {skill.name}: {skill.description}{suffix}"


def format_skill_summaries_for_prompt(skills: list[Skill]) -> str:
    """把多个 Skill Summary 拼成 prompt 区块；空列表返回空字符串。"""
    if not skills:
        return ""

    lines = ["Available Skills:"]
    lines.extend(format_skill_summary(skill) for skill in skills)
    return "\n".join(lines)


def extract_skill_description(markdown: str) -> str:
    """从 Markdown 中提取第一段非标题正文作为 Skill 描述。"""
    normalized = markdown.replace("\r\n", "\n")
    paragraphs = [block.strip() for block in normalized.split("\n\n") if block.strip()]

    for block in paragraphs:
        if block.startswith("#"):
            continue
        for line in block.splitlines():
            text = line.strip()
            if text and not text.startswith("#"):
                return text.replace("`", "")

    return "No description provided."


def load_skill_from_file(path: str) -> Skill:
    """从单个 SKILL.md 文件加载 Skill，名称默认取父目录名。"""
    skill_path = Path(path)
    content = skill_path.read_text(encoding="utf-8")
    skill = Skill(
        name=skill_path.parent.name,
        description=extract_skill_description(content),
        content=content,
    )
    # Skill 本体只保留四个字段；source directory 作为 loader 的内部索引供路由层读取 examples。
    _SKILL_DIRECTORIES[id(skill)] = skill_path.parent
    return skill


def get_skill_directory(skill: Skill) -> Optional[Path]:
    """返回 Skill 来源目录；手动构造的 Skill 没有来源目录。"""
    return _SKILL_DIRECTORIES.get(id(skill))


def discover_project_skills(workspace: Workspace) -> list[Skill]:
    """扫描项目级 .micode/skills/*/SKILL.md。"""
    skills_root = workspace.resolve_path(".micode/skills")
    return discover_skills_in_directory(skills_root)


def discover_user_skills(skills_root: Optional[str] = None) -> list[Skill]:
    """扫描用户级 Skill；默认读取 ~/.micode/skills。"""
    root = Path(skills_root) if skills_root else Path.home() / ".micode" / "skills"
    return discover_skills_in_directory(root)


def discover_skills_in_directory(skills_root: Path) -> list[Skill]:
    """扫描任意 Skill 根目录下的 */SKILL.md。"""
    if not skills_root.exists():
        return []

    skills = []
    for skill_file in sorted(skills_root.glob("*/SKILL.md")):
        skills.append(load_skill_from_file(str(skill_file)))

    return skills


def load_project_skill(workspace: Workspace, name: str) -> Optional[Skill]:
    """按名称加载项目级 Skill；找不到时返回 None。"""
    normalized_name = name.strip()
    if not normalized_name:
        return None

    skill_path = workspace.resolve_path(
        f".micode/skills/{normalized_name}/SKILL.md"
    )
    if not skill_path.exists():
        return None

    return load_skill_from_file(str(skill_path))


def route_skills(task: str, skills: list[Skill], limit: int = SMALL_SKILL_COUNT) -> list[Skill]:
    """按约定策略选择 Skill：显式点名优先，小规模全量返回。"""
    if limit <= 0 or not skills:
        return []

    explicit_skills = find_explicit_skills(task, skills)
    if explicit_skills:
        return explicit_skills[:limit]

    if len(skills) <= SMALL_SKILL_COUNT:
        return skills[:limit]

    # 中/大规模场景不在这里手写打分器；交给 LLM Router 或后续 Embedding/Graph Router。
    return []


def route_external_skills(
    task: str,
    skills: list[Skill],
    router,
    limit: int = SMALL_SKILL_COUNT,
) -> list[Skill]:
    """兼容入口；实际实现放在 skill_routing，避免 skills.py 变成大杂烩。"""
    from micode.skill_routing import route_external_skills as _route_external_skills

    return _route_external_skills(task, skills, router, limit)


def merge_project_and_external_skills(
    project_skills: list[Skill],
    external_skills: list[Skill],
) -> list[Skill]:
    """合并 Skill，项目级同名优先，外部同名 Skill 被忽略。"""
    project_names = {skill.name for skill in project_skills}
    merged = list(project_skills)
    for skill in external_skills:
        if skill.name in project_names:
            continue
        merged.append(skill)
    return merged


def find_explicit_skills(task: str, skills: list[Skill]) -> list[Skill]:
    """只处理用户明确点名 Skill name 的情况，不做相关性猜测。"""
    task_text = task.lower()
    matched = []
    for skill in skills:
        normalized_name = skill.name.lower()
        if normalized_name and normalized_name in task_text:
            matched.append(skill)
    return matched


def select_skills_by_name(
    names: list[str],
    skills: list[Skill],
    limit: int = SMALL_SKILL_COUNT,
) -> list[Skill]:
    """按 LLM Router 返回的名称选择 Skill，忽略未知名称并保持模型给出的顺序。"""
    if limit <= 0:
        return []

    skill_by_name = {skill.name: skill for skill in skills}
    selected = []
    seen = set()
    for name in names:
        if name in seen:
            continue
        skill = skill_by_name.get(name)
        if skill is None:
            continue
        selected.append(skill)
        seen.add(name)
        if len(selected) >= limit:
            break
    return selected


from micode.skill_routing import (  # noqa: E402
    LLMSkillRouter,
    TaskIntent,
    SkillRoutingProfile,
    TwoStageSkillRouter,
    build_skill_rerank_prompt,
    build_skill_router_prompt,
    build_task_intent_prompt,
    build_skill_routing_profile,
    extract_markdown_section_items,
    load_skill_examples,
    parse_skill_router_response,
    parse_task_intent_response,
    recall_skill_candidates,
    route_skills_with_llm,
)
