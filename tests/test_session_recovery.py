from micode.cli import run_checkpoint_command, run_session_command
from micode.memory.context import SessionSummary, SessionSummaryStore
from micode.memory.session import SessionMessage, SessionMessageStore, SessionStore
from micode.tools.default import create_default_tool_registry
from micode.workspace import Workspace


def test_session_inspect_replay_and_summary(tmp_path):
    session_dir = str(tmp_path / "sessions")
    SessionStore(session_dir).create(title="recover", session_id="session-1")
    SessionMessageStore(session_dir).append_messages(
        "session-1",
        [
            SessionMessage(
                id="message-1",
                session_id="session-1",
                role="user",
                content="continue",
            )
        ],
    )
    SessionSummaryStore(session_dir).save(
        SessionSummary(session_id="session-1", summary="work in progress")
    )

    inspected = run_session_command("inspect", "session-1", session_dir)
    replayed = run_session_command("replay", "session-1", session_dir)
    summarized = run_session_command("summary", "session-1", session_dir)

    assert inspected["message_count"] == 1
    assert inspected["resumable"] is True
    assert replayed["messages"][0]["content"] == "continue"
    assert summarized["summary"]["summary"] == "work in progress"


def test_checkpoint_cli_preview_and_rewind(tmp_path):
    registry = create_default_tool_registry(Workspace(str(tmp_path)))
    result = registry.call("write_file", {"path": "generated.txt", "content": "x"})
    checkpoint_id = result.metadata["details"]["checkpoint"]["id"]

    preview = run_checkpoint_command("preview", checkpoint_id, str(tmp_path))
    run_checkpoint_command("rewind", checkpoint_id, str(tmp_path))

    assert preview["can_rewind"] is True
    assert not (tmp_path / "generated.txt").exists()
