import json

from minicode.memory.episodic import (
    EpisodicMemory,
    EpisodicMemoryStore,
    episodic_memory_from_trace,
    extract_evidence,
    extract_outcome,
    extract_tool_names,
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
            {"type": "tool", "metadata": {"tool": "replace_text"}},
            {"type": "tool", "metadata": {"tool": "run_shell"}},
            {"type": "final", "metadata": {}},
        ],
        "events": [
            {
                "id": "event-1",
                "type": "tool_call",
                "content": "read cli.py",
            },
            {
                "id": "event-2",
                "type": "tool_call",
                "content": "replace_text succeeded",
            },
            {
                "id": "event-3",
                "type": "tool_call",
                "content": "196 passed",
            },
            {
                "id": "event-4",
                "type": "text",
                "content": "完成，已增加 --session-id，并确认测试通过",
            },
        ],
    }


def test_episodic_memory_from_trace_extracts_run_experience():
    memory = episodic_memory_from_trace("session-1", make_trace())

    assert memory.id == "episode:run-1"
    assert memory.session_id == "session-1"
    assert memory.run_id == "run-1"
    assert memory.task == "给 cli.py 增加 --session-id 并运行测试"
    assert memory.outcome == "完成，已增加 --session-id，并确认测试通过"
    assert memory.status == "completed"
    assert memory.tool_names == ["read_file", "replace_text", "run_shell"]
    assert memory.source_event_ids == ["event-1", "event-2", "event-3", "event-4"]
    assert memory.metadata["provider"] == "mimo"


def test_extract_outcome_prefers_final_text_then_error():
    assert extract_outcome(make_trace()["events"]) == "完成，已增加 --session-id，并确认测试通过"
    assert extract_outcome([{"type": "error", "content": "pytest failed"}]) == "pytest failed"
    assert extract_outcome([{"type": "tool_call", "content": "tool output"}]) == "tool output"


def test_extract_tool_names_deduplicates_tools():
    trace = {
        "steps": [
            {"metadata": {"tool": "read_file"}},
            {"metadata": {"tool": "read_file"}},
            {"metadata": {"tool": "run_shell"}},
        ]
    }

    assert extract_tool_names(trace) == ["read_file", "run_shell"]


def test_extract_evidence_keeps_key_event_content():
    evidence = extract_evidence(make_trace()["events"])

    assert evidence[0] == "tool_call: read cli.py"
    assert evidence[-1] == "text: 完成，已增加 --session-id，并确认测试通过"


def test_episodic_memory_round_trip_dict():
    memory = EpisodicMemory(
        id="episode:run-1",
        session_id="session-1",
        run_id="run-1",
        task="学习",
        outcome="完成",
        status="completed",
        tool_names=["read_file"],
        evidence=["text: 完成"],
        source_event_ids=["event-1"],
        metadata={"workspace": "."},
    )

    loaded = EpisodicMemory.from_dict(memory.to_dict())

    assert loaded.id == "episode:run-1"
    assert loaded.tool_names == ["read_file"]
    assert loaded.evidence == ["text: 完成"]
    assert loaded.metadata == {"workspace": "."}


def test_episodic_memory_store_upserts_by_id(tmp_path):
    store = EpisodicMemoryStore(str(tmp_path / "memory"))
    first = episodic_memory_from_trace("session-1", make_trace())
    second = EpisodicMemory(
        id=first.id,
        session_id="session-1",
        run_id="run-1",
        task="updated",
        outcome="updated",
        status="completed",
    )

    store.upsert(first)
    store.upsert(second)
    memories = store.load_all()
    data = json.loads((tmp_path / "memory" / "episodes.json").read_text())

    assert len(memories) == 1
    assert memories[0].task == "updated"
    assert data[0]["id"] == "episode:run-1"


def test_episodic_memory_store_finds_by_session(tmp_path):
    store = EpisodicMemoryStore(str(tmp_path / "memory"))
    store.upsert(episodic_memory_from_trace("session-1", make_trace()))

    assert len(store.find_by_session("session-1")) == 1
    assert store.find_by_session("missing") == []
