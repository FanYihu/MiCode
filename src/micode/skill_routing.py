import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from micode.skills import (
    SMALL_SKILL_COUNT,
    Skill,
    find_explicit_skills,
    format_skill_summaries_for_prompt,
    get_skill_directory,
    select_skills_by_name,
)


LARGE_SKILL_COUNT = 120
MAX_EXAMPLE_CHARS = 1200


@dataclass
class TaskIntent:
    """任务意图是路由阶段的中间结果，不写回 Skill 本体。"""

    goal: str
    task_type: str = ""
    keywords: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)


@dataclass
class SkillRoutingProfile:
    """Skill 路由画像由 Skill 内容和 examples 派生，不污染 Skill 数据结构。"""

    name: str
    description: str
    tags: list[str] = field(default_factory=list)
    when_to_use: list[str] = field(default_factory=list)
    when_not_to_use: list[str] = field(default_factory=list)
    examples: list[str] = field(default_factory=list)


def build_task_intent_prompt(task: str) -> str:
    """构建任务意图识别 prompt，让 LLM 返回可解析的 JSON。"""
    return f"""
You are Micode's task intent extractor.

Read the user task and return exactly one JSON object:
{{
  "goal": "short natural language goal",
  "task_type": "one short type such as code_refactor, testing, docs, debug, shell, git, unknown",
  "keywords": ["important domain words"],
  "tags": ["broad routing tags"]
}}

Rules:
- Do not explain.
- Use an empty list when unsure.
- Keep values short.

Task:
{task}
""".strip()


def parse_task_intent_response(text: str, fallback_task: str = "") -> TaskIntent:
    """解析任务意图 JSON；模型输出坏掉时回退到原始任务文本。"""
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return TaskIntent(goal=fallback_task)

    if not isinstance(data, dict):
        return TaskIntent(goal=fallback_task)

    return TaskIntent(
        goal=_clean_string(data.get("goal")) or fallback_task,
        task_type=_clean_string(data.get("task_type")),
        keywords=_clean_string_list(data.get("keywords")),
        tags=_clean_string_list(data.get("tags")),
    )


def build_skill_routing_profile(skill: Skill) -> SkillRoutingProfile:
    """从 Skill 四字段、Markdown 边界段落和 examples 目录生成路由画像。"""
    return SkillRoutingProfile(
        name=skill.name,
        description=skill.description,
        tags=list(skill.tags),
        when_to_use=extract_markdown_section_items(skill.content, "when to use"),
        when_not_to_use=extract_markdown_section_items(skill.content, "when not to use"),
        examples=load_skill_examples(skill),
    )


def build_skill_rerank_prompt(
    task: str,
    intent: TaskIntent,
    profiles: list[SkillRoutingProfile],
    limit: int = SMALL_SKILL_COUNT,
) -> str:
    """构建精排 prompt，让 LLM 基于画像选择最终 Skill。"""
    profile_text = "\n\n".join(format_skill_profile_for_prompt(profile) for profile in profiles)
    return f"""
You are Micode's Skill Router.

Choose at most {limit} skills for the task.
Use only skill names from the candidate profiles.
Return exactly one JSON object with this shape:
{{"skills":["skill-name"]}}
Return an empty list if no skill is useful.
Do not explain.

Task:
{task}

Task intent:
{json.dumps(_task_intent_to_dict(intent), ensure_ascii=False)}

Candidate skill profiles:
{profile_text or "No candidate skills."}
""".strip()


def parse_skill_router_response(text: str) -> list[str]:
    """解析 Router 返回的 JSON，提取 Skill 名称列表。"""
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return []

    if not isinstance(data, dict):
        return []

    names = data.get("skills", [])
    if not isinstance(names, list):
        return []
    return [name for name in names if isinstance(name, str)]


class TwoStageSkillRouter:
    """二阶段 Skill Router：先识别任务意图，再基于路由画像精排候选。"""

    def __init__(self, client) -> None:
        # client 只需要提供 generate(prompt)，因此可以复用 OpenAI-compatible client。
        self.client = client

    def route(
        self,
        task: str,
        skills: list[Skill],
        limit: int = SMALL_SKILL_COUNT,
    ) -> list[Skill]:
        """路由入口：显式 name 优先，其余交给 LLM 意图识别和精排。"""
        if limit <= 0 or not skills:
            return []

        explicit_skills = find_explicit_skills(task, skills)
        if explicit_skills:
            return explicit_skills[:limit]

        candidates = recall_skill_candidates(task, skills)
        if not candidates:
            return []

        intent_text = self.client.generate(build_task_intent_prompt(task))
        intent = parse_task_intent_response(intent_text, fallback_task=task)
        profiles = [build_skill_routing_profile(skill) for skill in candidates]
        rerank_text = self.client.generate(
            build_skill_rerank_prompt(task, intent, profiles, limit)
        )
        names = parse_skill_router_response(rerank_text)
        return select_skills_by_name(names, candidates, limit)


class LLMSkillRouter(TwoStageSkillRouter):
    """兼容旧名称；当前实现已经升级为二阶段 Router。"""


def route_external_skills(
    task: str,
    skills: list[Skill],
    router: Optional[TwoStageSkillRouter],
    limit: int = SMALL_SKILL_COUNT,
) -> list[Skill]:
    """路由非项目级 Skill；外部 Skill 必须显式点名或经过 Router。"""
    if limit <= 0 or not skills:
        return []

    explicit_skills = find_explicit_skills(task, skills)
    if explicit_skills:
        return explicit_skills[:limit]

    if router is None:
        return []

    return router.route(task, skills, limit)


def route_skills_with_llm(
    task: str,
    skills: list[Skill],
    router: TwoStageSkillRouter,
    limit: int = SMALL_SKILL_COUNT,
) -> list[Skill]:
    """兼容旧入口：先走基础策略，必要时交给二阶段 Router。"""
    from micode.skills import route_skills

    selected = route_skills(task, skills, limit)
    if selected:
        return selected
    return router.route(task, skills, limit)


def build_skill_router_prompt(
    task: str,
    skills: list[Skill],
    limit: int = SMALL_SKILL_COUNT,
) -> str:
    """保留旧 prompt 构造入口，用于文档和兼容测试。"""
    summaries = format_skill_summaries_for_prompt(skills) or "No skills available."
    return f"""
You are Micode's Skill Router.

Select at most {limit} skills for the task.
Use only the skill names listed below.
Return exactly one JSON object with this shape:
{{"skills":["skill-name"]}}
Return an empty list if no skill is useful.
Do not explain.

Task:
{task}

Available skill summaries:
{summaries}
""".strip()


def recall_skill_candidates(
    task: str,
    skills: list[Skill],
    limit: int = LARGE_SKILL_COUNT,
) -> list[Skill]:
    """第一阶段召回。

    当前没有接 embedding/index，因此 <=120 个外部 Skill 直接作为候选交给 LLM 精排。
    超过 120 个时先保守截断，后续 Day 可以替换成向量召回或图召回。
    """
    if limit <= 0:
        return []

    explicit_skills = find_explicit_skills(task, skills)
    if explicit_skills:
        return explicit_skills[:limit]

    return skills[:limit]


def format_skill_profile_for_prompt(profile: SkillRoutingProfile) -> str:
    """把路由画像格式化成紧凑 prompt 文本。"""
    lines = [
        f"Skill: {profile.name}",
        f"Description: {profile.description}",
    ]
    if profile.tags:
        lines.append(f"Tags: {', '.join(profile.tags)}")
    if profile.when_to_use:
        lines.append("When to use:")
        lines.extend(f"- {item}" for item in profile.when_to_use)
    if profile.when_not_to_use:
        lines.append("When not to use:")
        lines.extend(f"- {item}" for item in profile.when_not_to_use)
    if profile.examples:
        lines.append("Examples:")
        lines.extend(f"- {example}" for example in profile.examples)
    return "\n".join(lines)


def extract_markdown_section_items(markdown: str, heading: str) -> list[str]:
    """提取指定 Markdown 标题下的要点；支持中英文冒号和列表/普通段落。"""
    section = _extract_markdown_section(markdown, heading)
    if not section:
        return []

    items = []
    for raw_line in section.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        line = re.sub(r"^[-*]\s+", "", line)
        line = re.sub(r"^\d+[.)]\s+", "", line)
        line = line.strip()
        if line:
            items.append(line)
    return items


def load_skill_examples(skill: Skill) -> list[str]:
    """读取 skill/examples 下的示例摘要；没有 examples 时返回空列表。"""
    skill_dir = get_skill_directory(skill)
    if skill_dir is None:
        return []

    examples_dir = skill_dir / "examples"
    if not examples_dir.exists() or not examples_dir.is_dir():
        return []

    examples = []
    for path in sorted(examples_dir.iterdir()):
        if not path.is_file() or path.name.startswith("."):
            continue
        text = path.read_text(encoding="utf-8").strip()
        if not text:
            continue
        examples.append(_compact_text(text, MAX_EXAMPLE_CHARS))
    return examples


def _extract_markdown_section(markdown: str, heading: str) -> str:
    normalized = markdown.replace("\r\n", "\n")
    heading_pattern = re.compile(r"^(#{1,6})\s+(.+?)\s*$", re.IGNORECASE)
    target = _normalize_heading(heading)
    lines = normalized.splitlines()
    start_index = None
    start_level = 0

    for index, line in enumerate(lines):
        match = heading_pattern.match(line)
        if not match:
            continue
        level = len(match.group(1))
        title = _normalize_heading(match.group(2))
        if title == target:
            start_index = index + 1
            start_level = level
            break

    if start_index is None:
        return ""

    end_index = len(lines)
    for index in range(start_index, len(lines)):
        match = heading_pattern.match(lines[index])
        if match and len(match.group(1)) <= start_level:
            end_index = index
            break

    return "\n".join(lines[start_index:end_index]).strip()


def _normalize_heading(text: str) -> str:
    text = text.strip().lower()
    text = text.replace("：", ":")
    text = text.rstrip(":")
    return re.sub(r"\s+", " ", text)


def _clean_string(value) -> str:
    return value.strip() if isinstance(value, str) else ""


def _clean_string_list(value) -> list[str]:
    if not isinstance(value, list):
        return []
    return [item.strip() for item in value if isinstance(item, str) and item.strip()]


def _compact_text(text: str, max_chars: int) -> str:
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) <= max_chars:
        return text
    return text[: max_chars - 3].rstrip() + "..."


def _task_intent_to_dict(intent: TaskIntent) -> dict:
    return {
        "goal": intent.goal,
        "task_type": intent.task_type,
        "keywords": intent.keywords,
        "tags": intent.tags,
    }
