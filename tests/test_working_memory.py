import json

from minicode.memory.session import SessionMessage
from minicode.memory.working import (
    WorkingMemory,
    WorkingMemoryStore,
    truncate_memory_text,
)


def test_working_memory_apply_messages_updates_current_goal_and_completed():
    memory = WorkingMemory(session_id="session-1")
    messages = [
        SessionMessage(
            id="message-1",
            session_id="session-1",
            run_id="run-1",
            role="user",
            type="task",
            content="继续实现 Working Memory",
        ),
        SessionMessage(
            id="message-2",
            session_id="session-1",
            run_id="run-1",
            role="assistant",
            type="text",
            content="Working Memory 已完成",
        ),
    ]

    memory.apply_messages(messages)

    assert memory.current_goal == "继续实现 Working Memory"
    assert memory.completed == ["Working Memory 已完成"]
    assert [item["role"] for item in memory.recent_messages] == ["user", "assistant"]


def test_working_memory_apply_error_adds_todo():
    memory = WorkingMemory(session_id="session-1")

    memory.apply_messages(
        [
            SessionMessage(
                id="message-1",
                session_id="session-1",
                run_id="run-1",
                role="error",
                type="error",
                content="pytest failed",
            )
        ]
    )

    assert memory.todo == ["处理错误：pytest failed"]


def test_working_memory_supports_explicit_state_updates():
    memory = WorkingMemory(session_id="session-1")

    memory.set_goal("完善记忆系统")
    memory.add_todo("实现 Working Memory")
    memory.add_constraint("代码要有注释")
    memory.complete_item("实现 Working Memory")

    assert memory.current_goal == "完善记忆系统"
    assert memory.todo == []
    assert memory.completed == ["实现 Working Memory"]
    assert memory.constraints == ["代码要有注释"]


def test_working_memory_round_trip_dict():
    memory = WorkingMemory(
        session_id="session-1",
        current_goal="学习记忆系统",
        completed=["SessionStore"],
        todo=["Working Memory"],
        constraints=["代码要有注释"],
        recent_messages=[{"role": "user", "content": "继续"}],
        metadata={"source": "test"},
    )

    loaded = WorkingMemory.from_dict(memory.to_dict())

    assert loaded.session_id == "session-1"
    assert loaded.current_goal == "学习记忆系统"
    assert loaded.completed == ["SessionStore"]
    assert loaded.todo == ["Working Memory"]
    assert loaded.constraints == ["代码要有注释"]
    assert loaded.recent_messages == [{"role": "user", "content": "继续"}]
    assert loaded.metadata == {"source": "test"}


def test_working_memory_store_update_from_messages_persists(tmp_path):
    store = WorkingMemoryStore(str(tmp_path / "sessions"))
    messages = [
        SessionMessage(
            id="message-1",
            session_id="session-1",
            run_id="run-1",
            role="user",
            type="task",
            content="继续学习",
        )
    ]

    memory = store.update_from_messages("session-1", messages)
    loaded = store.load("session-1")
    data = json.loads(
        (tmp_path / "sessions" / "session-1.working_memory.json").read_text()
    )

    assert memory.current_goal == "继续学习"
    assert loaded.current_goal == "继续学习"
    assert data["session_id"] == "session-1"


def test_truncate_memory_text_shortens_long_content():
    assert truncate_memory_text("abcdef", max_length=4) == "a..."
