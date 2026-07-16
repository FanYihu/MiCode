from minicode.skills import (
    Skill,
    LLMSkillRouter,
    build_skill_rerank_prompt,
    build_skill_router_prompt,
    build_skill_routing_profile,
    discover_skills_in_directory,
    discover_project_skills,
    discover_user_skills,
    extract_markdown_section_items,
    extract_skill_description,
    find_explicit_skills,
    format_skill_summaries_for_prompt,
    format_skill_summary,
    format_skill_for_prompt,
    load_skill_examples,
    load_project_skill,
    load_skill_from_file,
    merge_project_and_external_skills,
    parse_skill_router_response,
    parse_task_intent_response,
    recall_skill_candidates,
    route_external_skills,
    route_skills,
    route_skills_with_llm,
    select_skills_by_name,
)
from minicode.workspace import Workspace


class FakeRouterClient:
    """测试专用 Router client，记录 prompt 并返回固定 JSON。"""

    def __init__(self, text: str):
        self.text = text
        self.prompts = []

    def generate(self, prompt: str) -> str:
        self.prompts.append(prompt)
        return self.text


def test_skill_can_be_created_with_core_fields():
    skill = Skill(
        name="python-test",
        description="Run Python tests safely.",
        content="Use pytest and inspect failures.",
        tags=["python", "test"],
    )

    assert skill.name == "python-test"
    assert skill.description == "Run Python tests safely."
    assert skill.content == "Use pytest and inspect failures."
    assert skill.tags == ["python", "test"]


def test_skill_default_lists_are_not_shared():
    first = Skill(name="first", description="First skill.", content="A")
    second = Skill(name="second", description="Second skill.", content="B")

    first.tags.append("python")

    assert second.tags == []


def test_format_skill_for_prompt_includes_metadata_and_content():
    skill = Skill(
        name="python-test",
        description="Run Python tests safely.",
        content="1. Run pytest.\n2. Read failures.",
        tags=["python", "test"],
    )

    prompt_text = format_skill_for_prompt(skill)

    assert "Skill: python-test" in prompt_text
    assert "Description: Run Python tests safely." in prompt_text
    assert "Tags: python, test" in prompt_text
    assert "1. Run pytest." in prompt_text


def test_format_skill_for_prompt_omits_empty_optional_lists():
    skill = Skill(name="small", description="Small skill.", content="Do one thing.")

    prompt_text = format_skill_for_prompt(skill)

    assert "Skill: small" in prompt_text
    assert "Tags:" not in prompt_text
    assert "Tools:" not in prompt_text


def test_format_skill_summary_includes_description_and_tags():
    skill = Skill(
        name="python-test",
        description="Run Python tests safely.",
        content="Full instructions should not appear here.",
        tags=["python", "test"],
    )

    summary = format_skill_summary(skill)

    assert summary == (
        "- python-test: Run Python tests safely. "
        "[tags: python, test]"
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
            tags=["pytest"],
        ),
    ]

    text = format_skill_summaries_for_prompt(skills)

    assert text.startswith("Available Skills:")
    assert "- docs-review: Review documentation changes." in text
    assert "- python-test: Run Python tests safely. [tags: pytest]" in text
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


def test_skill_routing_profile_reads_boundaries_and_examples(tmp_path):
    skill_dir = tmp_path / "python-test"
    examples_dir = skill_dir / "examples"
    examples_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(
        "# Python Test\n\n"
        "Run Python tests safely.\n\n"
        "## When to use\n\n"
        "- The task asks to run pytest.\n"
        "- The user needs test failure analysis.\n\n"
        "## When not to use\n\n"
        "- The task only edits documentation.\n",
        encoding="utf-8",
    )
    (examples_dir / "basic.md").write_text(
        "# Example\n\nRun `pytest` and summarize failures.",
        encoding="utf-8",
    )

    skill = load_skill_from_file(str(skill_dir / "SKILL.md"))
    profile = build_skill_routing_profile(skill)

    assert profile.name == "python-test"
    assert profile.when_to_use == [
        "The task asks to run pytest.",
        "The user needs test failure analysis.",
    ]
    assert profile.when_not_to_use == ["The task only edits documentation."]
    assert profile.examples == ["# Example Run `pytest` and summarize failures."]


def test_extract_markdown_section_items_returns_empty_for_missing_section():
    markdown = "# Skill\n\nDo work.\n\n## Steps\n\n- One"

    assert extract_markdown_section_items(markdown, "when to use") == []


def test_load_skill_examples_returns_empty_without_source_directory():
    skill = Skill(name="manual", description="Manual skill.", content="")

    assert load_skill_examples(skill) == []


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


def test_discover_user_skills_can_use_custom_root(tmp_path):
    skill_dir = tmp_path / "skills" / "global-test"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(
        "# Global Test\n\nRun tests across projects.",
        encoding="utf-8",
    )

    skills = discover_user_skills(str(tmp_path / "skills"))

    assert [skill.name for skill in skills] == ["global-test"]


def test_discover_skills_in_directory_returns_empty_for_missing_root(tmp_path):
    assert discover_skills_in_directory(tmp_path / "missing") == []


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
        Skill(name="two", description="Second.", content="", tags=["pytest"]),
    ]

    assert route_skills("please run pytest", skills, limit=1) == [skills[0]]


def test_route_skills_returns_empty_for_large_skill_set_without_router():
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

    assert selected == []


def test_route_skills_prefers_explicit_skill_name_when_limit_is_small():
    skills = [
        Skill(name="docs-review", description="Review docs.", content=""),
        Skill(name="python-test", description="Run Python tests.", content=""),
    ]

    selected = route_skills("use python-test", skills, limit=1)

    assert selected == [skills[1]]


def test_find_explicit_skills_uses_name_only():
    skills = [
        Skill(name="docs-review", description="Review docs.", content=""),
        Skill(name="python-test", description="Run tests.", content="", tags=["pytest"]),
    ]

    assert find_explicit_skills("use docs-review", skills) == [skills[0]]
    assert find_explicit_skills("please run pytest", skills) == []


def test_build_skill_router_prompt_uses_summaries_not_full_content():
    skill = Skill(
        name="python-test",
        description="Run Python tests safely.",
        content="Full instructions should stay out of router prompt.",
        tags=["pytest"],
    )

    prompt = build_skill_router_prompt("run tests", [skill], limit=3)

    assert "Skill Router" in prompt
    assert "at most 3 skills" in prompt
    assert "- python-test: Run Python tests safely. [tags: pytest]" in prompt
    assert "Full instructions" not in prompt


def test_parse_skill_router_response_extracts_names():
    names = parse_skill_router_response('{"skills":["python-test","docs-review"]}')

    assert names == ["python-test", "docs-review"]


def test_parse_skill_router_response_ignores_non_list_skills():
    assert parse_skill_router_response('{"skills":"python-test"}') == []


def test_parse_task_intent_response_extracts_structured_intent():
    intent = parse_task_intent_response(
        (
            '{"goal":"run tests","task_type":"testing",'
            '"keywords":["pytest"],"tags":["python","test"]}'
        ),
        fallback_task="fallback",
    )

    assert intent.goal == "run tests"
    assert intent.task_type == "testing"
    assert intent.keywords == ["pytest"]
    assert intent.tags == ["python", "test"]


def test_recall_skill_candidates_keeps_candidates_without_hand_scoring():
    skills = [
        Skill(name=f"skill-{index}", description="General helper.", content="")
        for index in range(3)
    ]

    assert recall_skill_candidates("anything", skills, limit=2) == skills[:2]


def test_build_skill_rerank_prompt_includes_intent_boundaries_and_examples():
    skill = Skill(
        name="python-test",
        description="Run Python tests safely.",
        content=(
            "## When to use\n\n- Test tasks.\n\n"
            "## When not to use\n\n- Docs only."
        ),
        tags=["pytest"],
    )
    profile = build_skill_routing_profile(skill)
    intent = parse_task_intent_response(
        '{"goal":"run tests","task_type":"testing","keywords":["pytest"],"tags":["test"]}',
        fallback_task="run tests",
    )

    prompt = build_skill_rerank_prompt("run tests", intent, [profile], limit=1)

    assert "Task intent:" in prompt
    assert "python-test" in prompt
    assert "Tags: pytest" in prompt
    assert "When to use:" in prompt
    assert "When not to use:" in prompt


def test_select_skills_by_name_keeps_router_order_and_ignores_unknowns():
    skills = [
        Skill(name="docs-review", description="Review docs.", content=""),
        Skill(name="python-test", description="Run tests.", content=""),
    ]

    selected = select_skills_by_name(
        ["missing", "python-test", "docs-review", "python-test"],
        skills,
        limit=2,
    )

    assert selected == [skills[1], skills[0]]


def test_llm_skill_router_calls_client_and_selects_skills():
    skills = [
        Skill(name="docs-review", description="Review docs.", content="docs"),
        Skill(name="python-test", description="Run tests.", content="tests"),
    ]
    client = FakeRouterClient('{"skills":["python-test"]}')
    router = LLMSkillRouter(client)

    selected = router.route("run tests", skills, limit=1)

    assert selected == [skills[1]]
    assert len(client.prompts) == 2
    assert "run tests" in client.prompts[0]
    assert "task intent extractor" in client.prompts[0]
    assert "Candidate skill profiles" in client.prompts[1]
    assert "python-test" in client.prompts[1]


def test_route_skills_with_llm_uses_deterministic_route_first():
    skills = [
        Skill(name="docs-review", description="Review docs.", content="docs"),
        Skill(name="python-test", description="Run tests.", content="tests"),
    ]
    client = FakeRouterClient('{"skills":["python-test"]}')
    router = LLMSkillRouter(client)

    selected = route_skills_with_llm("use docs-review", skills, router, limit=1)

    assert selected == [skills[0]]
    assert client.prompts == []


def test_route_skills_with_llm_calls_router_for_large_skill_set():
    skills = [
        Skill(name=f"skill-{index}", description="General helper.", content="")
        for index in range(21)
    ]
    selected_skill = Skill(name="python-test", description="Run tests.", content="")
    skills.append(selected_skill)
    router = LLMSkillRouter(FakeRouterClient('{"skills":["python-test"]}'))

    selected = route_skills_with_llm("run tests", skills, router, limit=2)

    assert selected == [selected_skill]


def test_route_external_skills_calls_router_even_for_small_skill_set():
    skills = [Skill(name="python-test", description="Run tests.", content="")]
    client = FakeRouterClient('{"skills":["python-test"]}')
    router = LLMSkillRouter(client)

    selected = route_external_skills("run tests", skills, router, limit=1)

    assert selected == skills
    assert len(client.prompts) == 2


def test_route_external_skills_without_router_only_allows_explicit_name():
    skills = [Skill(name="python-test", description="Run tests.", content="")]

    assert route_external_skills("run tests", skills, None) == []
    assert route_external_skills("use python-test", skills, None) == skills


def test_merge_project_and_external_skills_keeps_project_priority():
    project = [Skill(name="python-test", description="Project test.", content="project")]
    external = [
        Skill(name="python-test", description="User test.", content="user"),
        Skill(name="docs-review", description="Review docs.", content="docs"),
    ]

    merged = merge_project_and_external_skills(project, external)

    assert merged == [project[0], external[1]]


def test_route_skills_returns_empty_for_non_positive_limit():
    skills = [Skill(name="python-test", description="Run tests.", content="")]

    assert route_skills("python", skills, limit=0) == []
