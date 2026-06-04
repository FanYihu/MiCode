from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from minicode.workspace import Workspace


SMALL_SKILL_COUNT = 20


@dataclass
class Skill:
    """Skill 描述一个可注入给模型的高层操作能力。"""

    name: str
    description: str
    content: str
    tags: list[str] = field(default_factory=list)
    tools: list[str] = field(default_factory=list)


def format_skill_for_prompt(skill: Skill) -> str:
    """把 Skill 格式化为适合 prompt 注入的紧凑文本。"""
    lines = [
        f"Skill: {skill.name}",
        f"Description: {skill.description}",
    ]

    if skill.tags:
        lines.append(f"Tags: {', '.join(skill.tags)}")
    if skill.tools:
        lines.append(f"Tools: {', '.join(skill.tools)}")

    lines.extend(["", skill.content])
    return "\n".join(lines)


def format_skill_summary(skill: Skill) -> str:
    """格式化 Skill 摘要，不包含完整 content。"""
    suffixes = []
    if skill.tags:
        suffixes.append(f"tags: {', '.join(skill.tags)}")
    if skill.tools:
        suffixes.append(f"tools: {', '.join(skill.tools)}")

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
    return Skill(
        name=skill_path.parent.name,
        description=extract_skill_description(content),
        content=content,
    )


def discover_project_skills(workspace: Workspace) -> list[Skill]:
    """扫描项目级 .minicode/skills/*/SKILL.md。"""
    skills_root = workspace.resolve_path(".minicode/skills")
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
        f".minicode/skills/{normalized_name}/SKILL.md"
    )
    if not skill_path.exists():
        return None

    return load_skill_from_file(str(skill_path))


def route_skills(task: str, skills: list[Skill], limit: int = SMALL_SKILL_COUNT) -> list[Skill]:
    """选择要注入 Summary 的 Skill；小规模时直接返回全部。"""
    if limit <= 0 or not skills:
        return []

    if len(skills) <= SMALL_SKILL_COUNT:
        return skills[:limit]

    scored = []
    tokens = _tokenize(task)
    task_text = task.lower()
    for index, skill in enumerate(skills):
        score = _score_skill(skill, tokens, task_text)
        if score > 0:
            scored.append((score, -index, skill))

    scored.sort(reverse=True)
    return [skill for _, _, skill in scored[:limit]]


def _score_skill(skill: Skill, tokens: set[str], task_text: str) -> int:
    """用关键词做大规模场景的兜底排序，后续可替换成 LLM Router。"""
    score = 0
    name = skill.name.lower()
    description = skill.description.lower()

    if name and name in task_text:
        score += 5

    for token in tokens:
        if token in name:
            score += 3
        if token in description:
            score += 2
        for tag in skill.tags:
            if token in tag.lower():
                score += 2

    return score


def _tokenize(text: str) -> set[str]:
    """按简单字符规则切分任务文本，避免引入复杂检索依赖。"""
    normalized = []
    for char in text.lower():
        normalized.append(char if char.isalnum() or char in {"-", "_"} else " ")
    return {part for part in "".join(normalized).split() if part}
