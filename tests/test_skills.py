from minicode.skills import (
    Skill,
    discover_project_skills,
    extract_skill_description,
    format_skill_summaries_for_prompt,
    format_skill_summary,
    format_skill_for_prompt,
    load_project_skill,
    load_skill_from_file,
    route_skills,
)
from minicode.workspace import Workspace


def test_skill_can_be_created_with_core_fields():
    skill = Skill(
        name="python-test",
        description="Run Python tests safely.",
        content="Use pytest and inspect failures.",
        tags=["python", "test"],
        tools=["run_shell", "read_file"],
    )

    assert skill.name == "python-test"
    assert skill.description == "Run Python tests safely."
    assert skill.content == "Use pytest and inspect failures."
    assert skill.tags == ["python", "test"]
    assert skill.tools == ["run_shell", "read_file"]


def test_skill_default_lists_are_not_shared():
    first = Skill(name="first", description="First skill.", content="A")
    second = Skill(name="second", description="Second skill.", content="B")

    first.tags.append("python")
    first.tools.append("read_file")

    assert second.tags == []
    assert second.tools == []


def test_format_skill_for_prompt_includes_metadata_and_content():
    skill = Skill(
        name="python-test",
        description="Run Python tests safely.",
        content="1. Run pytest.\n2. Read failures.",
        tags=["python", "test"],
        tools=["run_shell", "read_file"],
    )

    prompt_text = format_skill_for_prompt(skill)

    assert "Skill: python-test" in prompt_text
    assert "Description: Run Python tests safely." in prompt_text
    assert "Tags: python, test" in prompt_text
    assert "Tools: run_shell, read_file" in prompt_text
    assert "1. Run pytest." in prompt_text


def test_format_skill_for_prompt_omits_empty_optional_lists():
    skill = Skill(name="small", description="Small skill.", content="Do one thing.")

    prompt_text = format_skill_for_prompt(skill)

    assert "Skill: small" in prompt_text
    assert "Tags:" not in prompt_text
    assert "Tools:" not in prompt_text


def test_format_skill_summary_includes_description_tags_and_tools():
    skill = Skill(
        name="python-test",
        description="Run Python tests safely.",
        content="Full instructions should not appear here.",
        tags=["python", "test"],
        tools=["run_shell", "read_file"],
    )

    summary = format_skill_summary(skill)

    assert summary == (
        "- python-test: Run Python tests safely. "
        "[tags: python, test | tools: run_shell, read_file]"
    )
    assert "Full instructions" not in summary


def test_format_skill_summary_omits_empty_optional_lists():
    skill = Skill(
        name="docs-review",
        description="Review documentation changes.",
        content="Full docs review flow.",
    )

    assert format_skill_summary(skill) == "- docs-review: Review documentation changes."


def test_format_skill_summaries_for_prompt_formats_multiple_skills():
    skills = [
        Skill(
            name="docs-review",
            description="Review documentation changes.",
            content="Do a full docs review.",
        ),
        Skill(
            name="python-test",
            description="Run Python tests safely.",
            content="Run pytest.",
            tools=["run_shell"],
        ),
    ]

    text = format_skill_summaries_for_prompt(skills)

    assert text.startswith("Available Skills:")
    assert "- docs-review: Review documentation changes." in text
    assert "- python-test: Run Python tests safely. [tools: run_shell]" in text
    assert "Do a full docs review." not in text
    assert "Run pytest." not in text


def test_format_skill_summaries_for_prompt_returns_empty_string_for_no_skills():
    assert format_skill_summaries_for_prompt([]) == ""


def test_extract_skill_description_uses_first_non_heading_paragraph():
    markdown = "# Python Test\n\nRun Python tests safely.\n\n## Steps\n\nUse pytest."

    assert extract_skill_description(markdown) == "Run Python tests safely."


def test_extract_skill_description_returns_fallback_when_missing_body():
    assert extract_skill_description("# Only Title") == "No description provided."


def test_load_skill_from_file_uses_parent_directory_as_name(tmp_path):
    skill_dir = tmp_path / "python-test"
    skill_dir.mkdir()
    skill_path = skill_dir / "SKILL.md"
    skill_path.write_text(
        "# Python Test\n\nRun Python tests safely.\n\nUse pytest.",
        encoding="utf-8",
    )

    skill = load_skill_from_file(str(skill_path))

    assert skill.name == "python-test"
    assert skill.description == "Run Python tests safely."
    assert "Use pytest." in skill.content


def test_discover_project_skills_loads_skill_files(tmp_path):
    skills_root = tmp_path / ".minicode" / "skills"
    (skills_root / "python-test").mkdir(parents=True)
    (skills_root / "python-test" / "SKILL.md").write_text(
        "# Python Test\n\nRun Python tests safely.",
        encoding="utf-8",
    )
    (skills_root / "docs-review").mkdir(parents=True)
    (skills_root / "docs-review" / "SKILL.md").write_text(
        "# Docs Review\n\nReview docs changes.",
        encoding="utf-8",
    )

    skills = discover_project_skills(Workspace(str(tmp_path)))

    assert [skill.name for skill in skills] == ["docs-review", "python-test"]
    assert [skill.description for skill in skills] == [
        "Review docs changes.",
        "Run Python tests safely.",
    ]


def test_discover_project_skills_returns_empty_for_missing_dir(tmp_path):
    assert discover_project_skills(Workspace(str(tmp_path))) == []


def test_load_project_skill_returns_skill_by_name(tmp_path):
    skill_dir = tmp_path / ".minicode" / "skills" / "python-test"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(
        "# Python Test\n\nRun Python tests safely.",
        encoding="utf-8",
    )

    skill = load_project_skill(Workspace(str(tmp_path)), "python-test")

    assert skill is not None
    assert skill.name == "python-test"
    assert skill.description == "Run Python tests safely."


def test_load_project_skill_returns_none_for_unknown_skill(tmp_path):
    assert load_project_skill(Workspace(str(tmp_path)), "missing") is None


def test_route_skills_returns_all_for_small_skill_set():
    skills = [
        Skill(name="docs-review", description="Review docs.", content="docs"),
        Skill(name="python-test", description="Run tests.", content="tests"),
    ]

    assert route_skills("unrelated task", skills) == skills


def test_route_skills_respects_limit_for_small_skill_set():
    skills = [
        Skill(name="one", description="First.", content=""),
        Skill(name="two", description="Second.", content=""),
    ]

    assert route_skills("anything", skills, limit=1) == [skills[0]]


def test_route_skills_uses_keywords_for_large_skill_set():
    skills = [
        Skill(name=f"skill-{index}", description="General helper.", content="")
        for index in range(21)
    ]
    python_skill = Skill(
        name="python-test",
        description="Run Python tests safely.",
        content="",
        tags=["pytest"],
    )
    docs_skill = Skill(
        name="docs-review",
        description="Review documentation changes.",
        content="",
        tags=["docs"],
    )
    skills.extend([python_skill, docs_skill])

    selected = route_skills("please run pytest for python", skills, limit=2)

    assert selected == [python_skill]


def test_route_skills_returns_empty_for_non_positive_limit():
    skills = [Skill(name="python-test", description="Run tests.", content="")]

    assert route_skills("python", skills, limit=0) == []
