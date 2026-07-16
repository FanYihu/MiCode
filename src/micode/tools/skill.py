from typing import Optional

from micode.skills import Skill, format_skill_for_prompt, load_project_skill
from micode.tools.registry import ToolResult
from micode.workspace import Workspace


def load_skill_tool(
    workspace: Workspace,
    args: dict,
    external_skills: Optional[list[Skill]] = None,
) -> ToolResult:
    """按名称加载完整 Skill 内容；项目级优先，其次外部层。"""
    name = args["name"]
    skill = load_project_skill(workspace, name)
    if skill is None:
        skill = _find_external_skill(name, external_skills or [])
    if skill is None:
        return ToolResult(
            ok=False,
            output=f"Unknown skill: {name}",
            metadata={"error": "unknown_skill", "name": name},
        )

    output = "\n".join(
        [
            f"SKILL: {skill.name}",
            f"DESCRIPTION: {skill.description}",
            "",
            "CONTENT:",
            format_skill_for_prompt(skill),
        ]
    )
    return ToolResult(
        ok=True,
        output=output,
        metadata={"name": skill.name},
    )


def _find_external_skill(name: str, external_skills: list[Skill]) -> Optional[Skill]:
    """从外部 Skill 列表按名称查找；项目级查找由调用方先完成。"""
    for skill in external_skills:
        if skill.name == name:
            return skill
    return None
