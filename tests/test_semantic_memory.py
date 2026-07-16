import json

from micode.memory.episodic import episodic_memory_from_trace
from micode.memory.semantic import (
    SemanticMemory,
    SemanticMemoryStore,
    build_semantic_extraction_prompt,
    deterministic_semantic_memories_from_episode,
    merge_semantic_memory,
    parse_semantic_extraction_response,
    semantic_memories_from_episode,
    stable_semantic_id,
)


def make_trace() -> dict:
    return {
        "run": {
            "id": "run-1",
            "status": "completed",
            "created_at": "2026-06-08T00:00:00+00:00",
            "updated_at": "2026-06-08T00:00:03+00:00",
            "metadata": {
                "task": "给 cli.py 增加 --session-id 并运行测试",
                "provider": "mimo",
                "model": "mimo-v2.5-pro",
                "workspace": "project",
            },
        },
        "steps": [
            {"type": "tool", "metadata": {"tool": "read_file"}},
            {"type": "tool", "metadata": {"tool": "run_shell"}},
        ],
        "events": [
            {"id": "event-1", "type": "tool_call", "content": "read cli.py"},
            {"id": "event-2", "type": "tool_call", "content": "196 passed"},
            {
                "id": "event-3",
                "type": "text",
                "content": "完成，已增加 --session-id，并确认测试通过",
            },
        ],
    }


class FakeSemanticClient:
    def __init__(self, text: str) -> None:
        self.text = text
        self.prompts = []

    def generate(self, prompt: str) -> str:
        self.prompts.append(prompt)
        return self.text


def test_deterministic_semantic_memories_from_episode_extracts_facts():
    episode = episodic_memory_from_trace("session-1", make_trace())

    memories = deterministic_semantic_memories_from_episode(episode)

    facts = [memory.fact for memory in memories]
    assert "task was_requested 给 cli.py 增加 --session-id 并运行测试" in facts
    assert "task had_outcome 完成，已增加 --session-id，并确认测试通过" in facts
    assert "run used_tool read_file" in facts
    assert "run used_tool run_shell" in facts


def test_semantic_memories_from_episode_uses_llm_extractor_when_available():
    episode = episodic_memory_from_trace("session-1", make_trace())
    client = FakeSemanticClient(
        '{"facts":[{"subject":"project","predicate":"uses_test_runner",'
        '"object":"pytest","confidence":0.9,"tags":["python","test"]}]}'
    )

    memories = semantic_memories_from_episode(episode, extractor_client=client)

    assert len(memories) == 1
    assert memories[0].fact == "project uses_test_runner pytest"
    assert memories[0].confidence == 0.9
    assert memories[0].tags == ["python", "test"]
    assert "semantic memory extractor" in client.prompts[0]


def test_semantic_memories_from_episode_falls_back_when_llm_returns_bad_json():
    episode = episodic_memory_from_trace("session-1", make_trace())
    client = FakeSemanticClient("not json")

    memories = semantic_memories_from_episode(episode, extractor_client=client)

    assert len(memories) > 1
    assert any(memory.predicate == "was_requested" for memory in memories)


def test_parse_semantic_extraction_response_ignores_invalid_facts():
    episode = episodic_memory_from_trace("session-1", make_trace())
    memories = parse_semantic_extraction_response(
        '{"facts":[{"subject":"project","predicate":"","object":"pytest"}]}',
        episode,
    )

    assert memories == []


def test_build_semantic_extraction_prompt_includes_episode_payload():
    episode = episodic_memory_from_trace("session-1", make_trace())

    prompt = build_semantic_extraction_prompt(episode)

    assert "Return exactly one JSON object" in prompt
    assert "给 cli.py 增加 --session-id" in prompt


def test_stable_semantic_id_merges_same_fact_across_episodes():
    first = stable_semantic_id("project", "uses_test_runner", "pytest")
    second = stable_semantic_id("project", "uses_test_runner", "pytest")

    assert first == second


def test_merge_semantic_memory_combines_sources_and_tags():
    previous = SemanticMemory(
        id="semantic:project-uses-pytest",
        fact="project uses pytest",
        subject="project",
        predicate="uses",
        object="pytest",
        source_episode_ids=["episode:1"],
        source_run_ids=["run-1"],
        tags=["test"],
        confidence=0.6,
    )
    current = SemanticMemory(
        id="semantic:project-uses-pytest",
        fact="project uses pytest",
        subject="project",
        predicate="uses",
        object="pytest",
        source_episode_ids=["episode:2"],
        source_run_ids=["run-2"],
        tags=["python"],
        confidence=0.9,
    )

    merged = merge_semantic_memory(previous, current)

    assert merged.source_episode_ids == ["episode:1", "episode:2"]
    assert merged.source_run_ids == ["run-1", "run-2"]
    assert merged.tags == ["test", "python"]
    assert merged.confidence == 0.9


def test_semantic_memory_store_upserts_and_searches(tmp_path):
    store = SemanticMemoryStore(str(tmp_path / "memory"))
    memory = SemanticMemory(
        id="semantic:project-uses-pytest",
        fact="project uses pytest",
        subject="project",
        predicate="uses",
        object="pytest",
        tags=["test"],
    )

    store.upsert_many([memory])
    loaded = store.load_all()
    data = json.loads((tmp_path / "memory" / "semantic.json").read_text())

    assert loaded[0].fact == "project uses pytest"
    assert data[0]["id"] == "semantic:project-uses-pytest"
    assert store.search("pytest") == loaded
    assert store.search("missing") == []
