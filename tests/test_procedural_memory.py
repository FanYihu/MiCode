import json

from minicode.memory.episodic import EpisodicMemory, episodic_memory_from_trace
from minicode.memory.procedural import (
    ProceduralMemory,
    ProceduralMemoryStore,
    deterministic_procedural_memories_from_episode,
    is_successful_episode,
    merge_procedural_memory,
    parse_procedural_extraction_response,
    procedural_memories_from_episode,
    procedural_memory_to_skill,
    slugify_procedure_name,
    stable_procedural_id,
)


def make_trace(status: str = "completed") -> dict:
    return {
        "run": {
            "id": "run-1",
            "status": status,
            "created_at": "2026-06-08T00:00:00+00:00",
            "updated_at": "2026-06-08T00:00:03+00:00",
            "metadata": {
                "task": "给 CLI 增加 session 参数并运行测试",
                "workspace": "project",
            },
        },
        "steps": [
            {"type": "tool", "metadata": {"tool": "read_file"}},
            {"type": "tool", "metadata": {"tool": "replace_text"}},
            {"type": "tool", "metadata": {"tool": "run_shell"}},
        ],
        "events": [
            {"id": "event-1", "type": "tool_call", "content": "read cli.py"},
            {"id": "event-2", "type": "tool_call", "content": "replace succeeded"},
            {"id": "event-3", "type": "text", "content": "完成并测试通过"},
        ],
    }


class FakeProcedureClient:
    def __init__(self, text: str) -> None:
        self.text = text
        self.prompts = []

    def generate(self, prompt: str) -> str:
        self.prompts.append(prompt)
        return self.text


def test_deterministic_procedural_memories_from_successful_episode():
    episode = episodic_memory_from_trace("session-1", make_trace())

    memories = deterministic_procedural_memories_from_episode(episode)

    assert len(memories) == 1
    assert memories[0].description == "给 CLI 增加 session 参数并运行测试"
    assert "Use read_file when needed." in memories[0].steps
    assert "replace_text" in memories[0].tags
    assert memories[0].source_episode_ids == [episode.id]


def test_procedural_memories_from_episode_uses_llm_extractor_when_available():
    episode = episodic_memory_from_trace("session-1", make_trace())
    client = FakeProcedureClient(
        '{"procedures":[{"name":"update-cli-and-test",'
        '"description":"Update CLI behavior and verify it.",'
        '"steps":["Read the CLI code.","Patch the argument handling.","Run tests."],'
        '"when_to_use":["CLI behavior changes"],'
        '"when_not_to_use":["No CLI changes"],'
        '"tags":["cli","test"]}]}'
    )

    memories = procedural_memories_from_episode(episode, extractor_client=client)

    assert len(memories) == 1
    assert memories[0].name == "update-cli-and-test"
    assert memories[0].steps == [
        "Read the CLI code.",
        "Patch the argument handling.",
        "Run tests.",
    ]
    assert "procedural memory extractor" in client.prompts[0]


def test_procedural_memories_from_episode_falls_back_when_llm_returns_bad_json():
    episode = episodic_memory_from_trace("session-1", make_trace())
    client = FakeProcedureClient("bad json")

    memories = procedural_memories_from_episode(episode, extractor_client=client)

    assert len(memories) == 1
    assert memories[0].steps


def test_failed_episode_does_not_create_procedural_memory():
    episode = episodic_memory_from_trace("session-1", make_trace(status="failed"))

    assert not is_successful_episode(episode)
    assert procedural_memories_from_episode(episode) == []


def test_parse_procedural_extraction_response_ignores_incomplete_items():
    episode = episodic_memory_from_trace("session-1", make_trace())

    memories = parse_procedural_extraction_response(
        '{"procedures":[{"name":"missing-steps","description":"No steps"}]}',
        episode,
    )

    assert memories == []


def test_procedural_memory_to_skill_keeps_skill_four_field_contract():
    memory = ProceduralMemory(
        id="procedure:update-cli-and-test",
        name="update-cli-and-test",
        description="Update CLI and run tests.",
        steps=["Read code.", "Patch code.", "Run tests."],
        when_to_use=["CLI behavior changes"],
        when_not_to_use=["No CLI work"],
        tags=["cli", "test"],
    )

    skill = procedural_memory_to_skill(memory)

    assert skill.name == "update-cli-and-test"
    assert skill.description == "Update CLI and run tests."
    assert skill.tags == ["cli", "test"]
    assert "## When to use" in skill.content
    assert "1. Read code." in skill.content


def test_merge_procedural_memory_combines_sources_steps_and_tags():
    previous = ProceduralMemory(
        id="procedure:update-cli",
        name="update-cli",
        description="Update CLI.",
        steps=["Read code."],
        tags=["cli"],
        source_episode_ids=["episode:1"],
        source_run_ids=["run-1"],
    )
    current = ProceduralMemory(
        id="procedure:update-cli",
        name="update-cli",
        description="Update CLI.",
        steps=["Run tests."],
        tags=["test"],
        source_episode_ids=["episode:2"],
        source_run_ids=["run-2"],
    )

    merged = merge_procedural_memory(previous, current)

    assert merged.steps == ["Read code.", "Run tests."]
    assert merged.tags == ["cli", "test"]
    assert merged.source_episode_ids == ["episode:1", "episode:2"]


def test_procedural_memory_store_upserts_and_searches(tmp_path):
    store = ProceduralMemoryStore(str(tmp_path / "memory"))
    memory = ProceduralMemory(
        id="procedure:update-cli",
        name="update-cli",
        description="Update CLI.",
        steps=["Run tests."],
        tags=["cli"],
    )

    store.upsert_many([memory])
    loaded = store.load_all()
    data = json.loads((tmp_path / "memory" / "procedures.json").read_text())

    assert loaded[0].name == "update-cli"
    assert data[0]["id"] == "procedure:update-cli"
    assert store.search("cli") == loaded
    assert store.search("missing") == []


def test_procedure_ids_are_stable():
    assert slugify_procedure_name("Update CLI + Test!") == "update-cli-test"
    assert stable_procedural_id("Update CLI") == "procedure:update-cli"
