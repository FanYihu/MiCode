import json

import pytest

from micode.memory.session import (
    Session,
    SessionMessage,
    SessionMessageStore,
    SessionStore,
    messages_from_trace,
    role_for_event_type,
)
from micode.memory.context import SessionSummary, SessionSummaryStore
from micode.memory.working import WorkingMemoryStore


def test_session_has_default_identity_and_metadata():
    session = Session(title="学习 CLI")

    assert session.id
    assert session.title == "学习 CLI"
    assert session.created_at
    assert session.updated_at
    assert session.run_ids == []
    assert session.metadata == {}


def test_session_add_run_updates_run_ids_once():
    session = Session()

    session.add_run("run-1")
    first_updated_at = session.updated_at
    session.add_run("run-1")

    assert session.run_ids == ["run-1"]
    assert session.updated_at >= first_updated_at


def test_session_add_run_rejects_empty_run_id():
    session = Session()

    with pytest.raises(ValueError):
        session.add_run("")


def test_session_round_trip_dict_preserves_fields():
    session = Session(
        id="session-1",
        title="Micode 学习",
        run_ids=["run-1"],
        metadata={"workspace": "."},
    )

    loaded = Session.from_dict(session.to_dict())

    assert loaded.id == "session-1"
    assert loaded.title == "Micode 学习"
    assert loaded.run_ids == ["run-1"]
    assert loaded.metadata == {"workspace": "."}


def test_session_store_create_save_and_load(tmp_path):
    store = SessionStore(str(tmp_path / "sessions"))

    session = store.create(
        title="学习记忆系统",
        metadata={"workspace": "project"},
        session_id="session-1",
    )
    loaded = store.load("session-1")

    assert session.id == "session-1"
    assert loaded.title == "学习记忆系统"
    assert loaded.metadata == {"workspace": "project"}
    assert (tmp_path / "sessions" / "session-1.json").exists()


def test_session_store_get_or_create_loads_existing_session(tmp_path):
    store = SessionStore(str(tmp_path / "sessions"))
    store.create(title="first", session_id="session-1")

    session = store.get_or_create("session-1", title="second")

    assert session.title == "first"


def test_session_store_add_run_persists_update(tmp_path):
    store = SessionStore(str(tmp_path / "sessions"))
    store.create(session_id="session-1")

    session = store.add_run("session-1", "run-1")
    loaded = store.load("session-1")

    assert session.run_ids == ["run-1"]
    assert loaded.run_ids == ["run-1"]


def test_session_store_list_sessions_returns_recent_first(tmp_path):
    store = SessionStore(str(tmp_path / "sessions"))
    old_session = store.create(title="old", session_id="old")
    new_session = store.create(title="new", session_id="new")

    sessions = store.list_sessions(limit=2)

    assert [session.id for session in sessions] == [new_session.id, old_session.id]


def test_session_file_is_plain_json(tmp_path):
    store = SessionStore(str(tmp_path / "sessions"))
    store.create(title="可读 JSON", session_id="session-1")

    data = json.loads((tmp_path / "sessions" / "session-1.json").read_text())

    assert data["id"] == "session-1"
    assert data["title"] == "可读 JSON"


def test_messages_from_trace_includes_user_task_and_events():
    trace = {
        "run": {
            "id": "run-1",
            "created_at": "2026-06-08T00:00:00+00:00",
            "metadata": {"task": "继续学习"},
        },
        "events": [
            {
                "id": "event-1",
                "step_id": "step-1",
                "type": "tool_call",
                "created_at": "2026-06-08T00:00:01+00:00",
                "content": "README.md",
                "metadata": {"tool": "list_files"},
            },
            {
                "id": "event-2",
                "step_id": "step-2",
                "type": "text",
                "created_at": "2026-06-08T00:00:02+00:00",
                "content": "完成",
                "metadata": {},
            },
        ],
    }

    messages = messages_from_trace("session-1", trace)

    assert [message.role for message in messages] == ["user", "tool", "assistant"]
    assert [message.content for message in messages] == ["继续学习", "README.md", "完成"]
    assert messages[0].id == "run-1:user"
    assert messages[1].metadata["event_metadata"] == {"tool": "list_files"}


def test_role_for_event_type_maps_trace_events_to_message_roles():
    assert role_for_event_type("tool_call") == "tool"
    assert role_for_event_type("error") == "error"
    assert role_for_event_type("state") == "system"
    assert role_for_event_type("text") == "assistant"


def test_session_message_store_append_messages_persists_and_deduplicates(tmp_path):
    store = SessionMessageStore(str(tmp_path / "sessions"))
    message = SessionMessage(
        id="message-1",
        session_id="session-1",
        run_id="run-1",
        role="assistant",
        content="完成",
    )

    store.append_messages("session-1", [message])
    store.append_messages("session-1", [message])
    loaded = store.load_messages("session-1")

    assert [item.id for item in loaded] == ["message-1"]
    assert loaded[0].content == "完成"
    assert (tmp_path / "sessions" / "session-1.messages.json").exists()


def test_session_store_list_sessions_ignores_message_files(tmp_path):
    session_store = SessionStore(str(tmp_path / "sessions"))
    message_store = SessionMessageStore(str(tmp_path / "sessions"))
    summary_store = SessionSummaryStore(str(tmp_path / "sessions"))
    working_memory_store = WorkingMemoryStore(str(tmp_path / "sessions"))
    session_store.create(title="session", session_id="session-1")
    message_store.append_messages(
        "session-1",
        [
            SessionMessage(
                id="message-1",
                session_id="session-1",
                run_id="run-1",
                content="完成",
            )
        ],
    )
    working_memory = working_memory_store.load("session-1")
    working_memory_store.save(working_memory)
    summary_store.save(SessionSummary(session_id="session-1", summary="done"))

    sessions = session_store.list_sessions(limit=10)

    assert [session.id for session in sessions] == ["session-1"]
