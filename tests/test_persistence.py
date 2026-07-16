import json
from pathlib import Path

import pytest

from micode.persistence import (
    cleanup_traces,
    filter_traces,
    format_trace_detail,
    format_trace_markdown,
    load_trace,
    list_traces,
    save_trace,
    summarize_trace,
    truncate_text,
    write_text_report,
)


def test_save_trace_creates_json_file(tmp_path):
    trace = {"run": {"status": "completed"}, "steps": [], "events": []}

    path = save_trace(trace, output_dir=str(tmp_path / "traces"))

    saved_path = Path(path)
    assert saved_path.exists()
    assert saved_path.parent == tmp_path / "traces"
    assert json.loads(saved_path.read_text(encoding="utf-8")) == trace


def test_load_trace_reads_saved_json(tmp_path):
    trace = {"run": {"status": "completed"}, "steps": [], "events": []}
    path = save_trace(trace, output_dir=str(tmp_path / "traces"))

    assert load_trace(path) == trace


def test_summarize_trace_includes_status_steps_and_final_answer():
    trace = {
        "run": {"status": "completed"},
        "steps": [
            {"type": "tool", "metadata": {"tool": "list_files"}},
            {"type": "final", "metadata": {}},
        ],
        "events": [
            {"type": "text", "content": "README.md"},
            {"type": "text", "content": "完成"},
        ],
    }

    summary = summarize_trace(trace)

    assert "Run: completed" in summary
    assert "Steps: 2" in summary
    assert "1. tool list_files" in summary
    assert "2. final" in summary
    assert "Final: 完成" in summary


def test_summarize_trace_includes_errors():
    trace = {
        "run": {"status": "failed"},
        "steps": [{"type": "model", "metadata": {}}],
        "events": [{"type": "error", "content": "action text must be valid json"}],
    }

    summary = summarize_trace(trace)

    assert "Run: failed" in summary
    assert "Errors:" in summary
    assert "action text must be valid json" in summary


def test_format_trace_detail_includes_metadata_and_event_details():
    trace = {
        "run": {
            "id": "run-1",
            "status": "completed",
            "metadata": {"task": "读取 README", "provider": "mimo"},
        },
        "steps": [
            {
                "id": "step-1",
                "type": "tool",
                "status": "pending",
                "metadata": {"tool": "read_file"},
            }
        ],
        "events": [
            {
                "step_id": "step-1",
                "type": "text",
                "content": "hello",
                "metadata": {"path": "README.md"},
            }
        ],
    }

    detail = format_trace_detail(trace)

    assert "Run" in detail
    assert "run-1" in detail
    assert '"task": "读取 README"' in detail
    assert "Steps" in detail
    assert '"tool": "read_file"' in detail
    assert "Events" in detail
    assert "content: hello" in detail
    assert '"path": "README.md"' in detail


def test_truncate_text_keeps_short_text():
    assert truncate_text("hello", max_length=10) == "hello"


def test_truncate_text_truncates_long_text_with_marker():
    assert truncate_text("abcdef", max_length=3) == "abc... [truncated]"


def test_truncate_text_allows_full_output_with_zero_limit():
    assert truncate_text("abcdef", max_length=0) == "abcdef"


def test_truncate_text_rejects_negative_limit():
    with pytest.raises(ValueError):
        truncate_text("abcdef", max_length=-1)


def test_format_trace_detail_truncates_event_content_but_keeps_metadata():
    trace = {
        "run": {"id": "run-1", "status": "completed", "metadata": {}},
        "steps": [],
        "events": [
            {
                "step_id": "step-1",
                "type": "tool_call",
                "content": "abcdef",
                "metadata": {"full_path": "README-with-long-metadata-name.md"},
            }
        ],
    }

    detail = format_trace_detail(trace, max_content=3)

    assert "content: abc... [truncated]" in detail
    assert "README-with-long-metadata-name.md" in detail


def test_format_trace_detail_can_show_full_event_content():
    trace = {
        "run": {"id": "run-1", "status": "completed", "metadata": {}},
        "steps": [],
        "events": [
            {
                "step_id": "step-1",
                "type": "text",
                "content": "abcdef",
                "metadata": {},
            }
        ],
    }

    detail = format_trace_detail(trace, max_content=0)

    assert "content: abcdef" in detail
    assert "[truncated]" not in detail


def test_format_trace_markdown_includes_run_steps_and_final():
    trace = {
        "run": {
            "status": "completed",
            "metadata": {
                "task": "读取 README",
                "mode": "agent",
                "provider": "mimo",
                "model": "mimo-v2.5-pro",
            },
        },
        "steps": [
            {"type": "tool", "metadata": {"tool": "read_file"}},
            {"type": "final", "metadata": {}},
        ],
        "events": [
            {"type": "tool_call", "content": "README content"},
            {"type": "text", "content": "完成"},
        ],
    }

    report = format_trace_markdown(trace)

    assert "# Micode Trace Report" in report
    assert "- status: completed" in report
    assert "- task: 读取 README" in report
    assert "- provider: mimo" in report
    assert "1. tool read_file" in report
    assert "2. final" in report
    assert "## Final" in report
    assert "完成" in report


def test_format_trace_markdown_includes_errors_and_empty_steps():
    trace = {
        "run": {"status": "failed", "metadata": {"task": "运行测试"}},
        "steps": [],
        "events": [{"type": "error", "content": "pytest failed"}],
    }

    report = format_trace_markdown(trace)

    assert "- status: failed" in report
    assert "No steps." in report
    assert "## Errors" in report
    assert "- pytest failed" in report


def test_write_text_report_creates_parent_directory_and_file(tmp_path):
    output_path = tmp_path / "notes" / "trace-report.md"

    saved_path = write_text_report("# Report\n\n完成", str(output_path))

    assert saved_path == str(output_path)
    assert output_path.read_text(encoding="utf-8") == "# Report\n\n完成"


def test_list_traces_returns_empty_for_missing_dir(tmp_path):
    assert list_traces(str(tmp_path / "missing")) == []


def test_list_traces_returns_only_json_files_by_recent_order(tmp_path):
    trace_dir = tmp_path / "traces"
    trace_dir.mkdir()
    old_trace = trace_dir / "old.json"
    new_trace = trace_dir / "new.json"
    ignored_file = trace_dir / "notes.txt"

    old_trace.write_text("{}", encoding="utf-8")
    new_trace.write_text("{}", encoding="utf-8")
    ignored_file.write_text("not a trace", encoding="utf-8")

    old_time = 1000
    new_time = 2000
    old_trace.touch()
    new_trace.touch()
    ignored_file.touch()
    import os
    os.utime(old_trace, (old_time, old_time))
    os.utime(new_trace, (new_time, new_time))

    assert list_traces(str(trace_dir)) == [str(new_trace), str(old_trace)]


def test_list_traces_respects_limit(tmp_path):
    trace_dir = tmp_path / "traces"
    trace_dir.mkdir()
    first = trace_dir / "first.json"
    second = trace_dir / "second.json"
    first.write_text("{}", encoding="utf-8")
    second.write_text("{}", encoding="utf-8")

    assert len(list_traces(str(trace_dir), limit=1)) == 1


def test_cleanup_traces_returns_empty_for_missing_dir(tmp_path):
    assert cleanup_traces(str(tmp_path / "missing"), keep=2) == []


def test_cleanup_traces_keeps_recent_json_and_deletes_old(tmp_path):
    trace_dir = tmp_path / "traces"
    trace_dir.mkdir()
    old_trace = trace_dir / "old.json"
    middle_trace = trace_dir / "middle.json"
    new_trace = trace_dir / "new.json"
    notes = trace_dir / "notes.txt"

    for path in [old_trace, middle_trace, new_trace]:
        path.write_text("{}", encoding="utf-8")
    notes.write_text("keep me", encoding="utf-8")

    import os
    os.utime(old_trace, (1000, 1000))
    os.utime(middle_trace, (2000, 2000))
    os.utime(new_trace, (3000, 3000))

    deleted = cleanup_traces(str(trace_dir), keep=2)

    assert deleted == [str(old_trace)]
    assert not old_trace.exists()
    assert middle_trace.exists()
    assert new_trace.exists()
    assert notes.exists()


def test_cleanup_traces_can_delete_all_json_files(tmp_path):
    trace_dir = tmp_path / "traces"
    trace_dir.mkdir()
    trace = trace_dir / "trace.json"
    trace.write_text("{}", encoding="utf-8")

    deleted = cleanup_traces(str(trace_dir), keep=0)

    assert deleted == [str(trace)]
    assert not trace.exists()


def test_cleanup_traces_rejects_negative_keep(tmp_path):
    with pytest.raises(ValueError):
        cleanup_traces(str(tmp_path), keep=-1)


def _write_trace(path, metadata):
    path.write_text(
        json.dumps({"run": {"metadata": metadata}, "steps": [], "events": []}),
        encoding="utf-8",
    )


def test_filter_traces_by_mode_provider_model_and_task(tmp_path):
    agent_trace = tmp_path / "agent.json"
    fixed_trace = tmp_path / "fixed.json"
    _write_trace(
        agent_trace,
        {
            "mode": "agent",
            "provider": "mimo",
            "model": "mimo-v2.5-pro",
            "task": "读取 README",
        },
    )
    _write_trace(
        fixed_trace,
        {
            "mode": "fixed",
            "provider": "",
            "model": "",
            "task": "list files",
        },
    )

    result = filter_traces(
        [str(agent_trace), str(fixed_trace)],
        mode="agent",
        provider="mimo",
        model="mimo-v2.5-pro",
        task_contains="README",
    )

    assert result == [str(agent_trace)]


def test_filter_traces_preserves_order_and_allows_empty_filters(tmp_path):
    first = tmp_path / "first.json"
    second = tmp_path / "second.json"
    _write_trace(first, {"mode": "agent", "task": "first"})
    _write_trace(second, {"mode": "agent", "task": "second"})

    result = filter_traces([str(first), str(second)])

    assert result == [str(first), str(second)]


def test_filter_traces_returns_empty_when_no_match(tmp_path):
    trace = tmp_path / "trace.json"
    _write_trace(trace, {"mode": "fixed", "task": "list files"})

    assert filter_traces([str(trace)], mode="agent") == []
