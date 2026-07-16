import json

import pytest

from minicode.memory.context import (
    ContextCompressor,
    SessionSummary,
    SessionSummaryStore,
    build_session_context,
    build_summary_prompt,
    format_messages_as_summary,
    format_structured_summary,
    limit_summary_lines,
    parse_summary_response,
)
from minicode.memory.session import SessionMessage
from minicode.memory.working import WorkingMemory


def make_message(index: int, role: str = "assistant") -> SessionMessage:
    return SessionMessage(
        id=f"message-{index}",
        session_id="session-1",
        run_id=f"run-{index}",
        role=role,
        type="text",
        content=f"content {index}",
    )


def test_context_compressor_splits_history_and_recent_messages():
    messages = [make_message(index) for index in range(10)]
    compressor = ContextCompressor(recent_message_limit=3)

    history, recent = compressor.split_messages(messages)

    assert [message.id for message in history] == [f"message-{index}" for index in range(7)]
    assert [message.id for message in recent] == ["message-7", "message-8", "message-9"]


def test_context_compressor_rejects_negative_recent_limit():
    with pytest.raises(ValueError):
        ContextCompressor(recent_message_limit=-1)


def test_context_compressor_summarizes_only_uncovered_messages():
    messages = [make_message(1), make_message(2)]
    previous = SessionSummary(
        session_id="session-1",
        summary="- assistant/text: old",
        covered_message_ids=["message-1"],
        source_message_count=1,
    )
    compressor = ContextCompressor(recent_message_limit=0)

    summary = compressor.summarize("session-1", messages, previous)

    assert "old" in summary.summary
    assert "content 2" in summary.summary
    assert "content 1" not in summary.summary
    assert summary.covered_message_ids == ["message-1", "message-2"]
    assert summary.source_message_count == 2
    assert summary.structured["completed"] == ["content 2"]


def test_context_compressor_compact_keeps_recent_messages_out_of_summary():
    messages = [make_message(index) for index in range(5)]
    compressor = ContextCompressor(recent_message_limit=2)

    summary, recent = compressor.compact("session-1", messages)

    assert "content 0" in summary.summary
    assert "content 2" in summary.summary
    assert "content 3" not in summary.summary
    assert [message.content for message in recent] == ["content 3", "content 4"]


def test_build_session_context_includes_working_memory_summary_and_recent():
    memory = WorkingMemory(
        session_id="session-1",
        current_goal="继续学习记忆系统",
        completed=["完成 Session"],
        todo=["处理压缩"],
        constraints=["代码要有注释"],
    )
    summary = SessionSummary(session_id="session-1", summary="- user/task: 之前目标")
    recent = [make_message(1, role="user")]

    text = build_session_context(memory, summary, recent)

    assert "Current goal: 继续学习记忆系统" in text
    assert "Constraints:" in text
    assert "处理压缩" in text
    assert "Session summary:" in text
    assert "Recent messages:" in text


def test_format_messages_as_summary_truncates_long_content():
    message = SessionMessage(
        id="message-1",
        session_id="session-1",
        run_id="run-1",
        role="tool",
        type="tool_call",
        content="a" * 400,
    )

    summary = format_messages_as_summary([message])

    assert summary.startswith("Overview:")
    assert len(summary) < 260


def test_context_compressor_can_use_llm_structured_summarizer():
    class FakeSummarizer:
        def __init__(self):
            self.prompts = []

        def generate(self, prompt):
            self.prompts.append(prompt)
            return (
                '{"overview":"Implemented memory package.",'
                '"goals":["organize memory"],'
                '"decisions":["use structured summary"],'
                '"completed":["moved files"],'
                '"errors":[],'
                '"constraints":["no secrets"],'
                '"next_steps":["run tests"]}'
            )

    compressor = ContextCompressor(
        recent_message_limit=0,
        summarizer_client=FakeSummarizer(),
    )

    summary = compressor.summarize("session-1", [make_message(1)])

    assert summary.structured["overview"] == "Implemented memory package."
    assert summary.structured["decisions"] == ["use structured summary"]
    assert "Decisions:" in summary.summary
    assert summary.metadata["summarizer"] == "llm"


def test_parse_summary_response_rejects_invalid_json():
    assert parse_summary_response("not json") == {}


def test_build_summary_prompt_includes_messages_and_json_contract():
    prompt = build_summary_prompt([make_message(1, role="user")])

    assert "session memory summarizer" in prompt
    assert '"overview"' in prompt
    assert "content 1" in prompt


def test_format_structured_summary_renders_sections():
    text = format_structured_summary(
        {
            "overview": "Summary.",
            "goals": ["Goal"],
            "decisions": ["Decision"],
            "completed": ["Done"],
            "errors": ["Error"],
            "constraints": ["Constraint"],
            "next_steps": ["Next"],
        }
    )

    assert "Overview: Summary." in text
    assert "Goals:" in text
    assert "- Decision" in text


def test_limit_summary_lines_keeps_recent_lines_with_marker():
    summary = "\n".join(f"- item {index}" for index in range(5))

    limited = limit_summary_lines(summary, max_lines=3)

    assert limited.splitlines()[0] == "- ... 2 older summary lines omitted"
    assert "- item 4" in limited


def test_session_summary_store_save_and_load(tmp_path):
    store = SessionSummaryStore(str(tmp_path / "sessions"))
    summary = SessionSummary(
        session_id="session-1",
        summary="- user/task: hello",
        structured={"overview": "hello"},
        covered_message_ids=["message-1"],
        source_message_count=1,
    )

    store.save(summary)
    loaded = store.load("session-1")
    data = json.loads((tmp_path / "sessions" / "session-1.summary.json").read_text())

    assert loaded.summary == "- user/task: hello"
    assert loaded.structured == {"overview": "hello"}
    assert loaded.covered_message_ids == ["message-1"]
    assert data["session_id"] == "session-1"
