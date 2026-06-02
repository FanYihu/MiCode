import json
from pathlib import Path

import pytest

from minicode.persistence import (
    cleanup_traces,
    load_trace,
    list_traces,
    save_trace,
    summarize_trace,
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
