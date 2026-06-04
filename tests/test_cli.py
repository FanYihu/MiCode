import json
from pathlib import Path

from minicode.agent import AgentAction
from minicode.cli import (
    maybe_save_trace,
    run_agent_task,
    run_task,
    run_trace_cleanup,
    run_trace_list,
    run_trace_viewer,
)
from minicode.models import RunStatus, StepType


def test_cli_list_files(tmp_path):
    (tmp_path / "README.md").write_text("hello", encoding="utf-8")

    trace = run_task("list files", str(tmp_path))

    assert trace["run"]["status"] == RunStatus.COMPLETED.value
    assert trace["steps"][0]["type"] == StepType.TOOL.value
    assert trace["steps"][0]["metadata"]["tool"] == "list_files"
    assert "README.md" in trace["events"][0]["content"]
    assert trace["run"]["metadata"]["task"] == "list files"
    assert trace["run"]["metadata"]["mode"] == "fixed"
    assert trace["run"]["metadata"]["workspace"] == str(tmp_path)


def test_cli_unsupported_task_completes_with_message(tmp_path):
    trace = run_task("unknown task", str(tmp_path))

    assert trace["run"]["status"] == RunStatus.COMPLETED.value
    assert trace["steps"][0]["type"] == StepType.FINAL.value
    assert "不支持的任务" in trace["events"][0]["content"]


def test_cli_run_tests_records_shell_result(tmp_path):
    (tmp_path / "test_sample.py").write_text(
        "def test_sample():\n    assert True\n",
        encoding="utf-8",
    )

    trace = run_task("run tests", str(tmp_path))

    assert trace["run"]["status"] == RunStatus.COMPLETED.value
    assert trace["steps"][0]["metadata"]["tool"] == "shell"
    assert trace["events"][0]["metadata"]["exit_code"] == 0


def test_maybe_save_trace_adds_saved_trace_path(tmp_path):
    trace = {"run": {"status": "completed"}, "steps": [], "events": []}

    result = maybe_save_trace(trace, True, str(tmp_path / "traces"))

    assert "saved_trace_path" in result
    assert Path(result["saved_trace_path"]).exists()


def test_maybe_save_trace_keeps_trace_when_disabled(tmp_path):
    trace = {"run": {"status": "completed"}, "steps": [], "events": []}

    result = maybe_save_trace(trace, False, str(tmp_path / "traces"))

    assert "saved_trace_path" not in result
    assert not (tmp_path / "traces").exists()


def test_run_agent_task_uses_configured_llm(monkeypatch, tmp_path):
    class SequenceLLM:
        def __init__(self):
            self.actions = [
                AgentAction(tool="list_files", args={}),
                AgentAction(tool="", args={"answer": "完成"}, final=True),
            ]
            self.index = 0

        def next_action(self, task, observations):
            action = self.actions[self.index]
            self.index += 1
            return action

    monkeypatch.setattr("minicode.cli.create_llm_from_config", lambda path: SequenceLLM())
    (tmp_path / "README.md").write_text("hello", encoding="utf-8")

    trace = run_agent_task("列出文件", str(tmp_path), "config.toml")

    assert trace["run"]["status"] == RunStatus.COMPLETED.value
    assert trace["steps"][0]["metadata"]["tool"] == "list_files"
    assert trace["events"][-1]["content"] == "完成"
    assert trace["run"]["metadata"]["task"] == "列出文件"
    assert trace["run"]["metadata"]["mode"] == "agent"
    assert trace["run"]["metadata"]["workspace"] == str(tmp_path)
    assert trace["run"]["metadata"]["config"] == "config.toml"


def test_run_trace_viewer_returns_summary(tmp_path):
    trace_path = tmp_path / "trace.json"
    trace_path.write_text(
        '{"run":{"status":"completed"},"steps":[],"events":[]}',
        encoding="utf-8",
    )

    summary = run_trace_viewer(str(trace_path))

    assert "Run: completed" in summary
    assert "Steps: 0" in summary


def test_run_trace_viewer_returns_detail_when_requested(tmp_path):
    trace_path = tmp_path / "trace.json"
    trace_path.write_text(
        '{"run":{"id":"run-1","status":"completed","metadata":{"task":"读取 README"}},"steps":[],"events":[]}',
        encoding="utf-8",
    )

    detail = run_trace_viewer(str(trace_path), detail=True)

    assert "Run" in detail
    assert "run-1" in detail
    assert '"task": "读取 README"' in detail


def test_run_trace_viewer_detail_respects_max_content(tmp_path):
    trace_path = tmp_path / "trace.json"
    trace = {
        "run": {"id": "run-1", "status": "completed", "metadata": {}},
        "steps": [],
        "events": [
            {
                "type": "text",
                "step_id": "step-1",
                "content": "abcdef",
                "metadata": {},
            }
        ],
    }
    trace_path.write_text(json.dumps(trace), encoding="utf-8")

    detail = run_trace_viewer(str(trace_path), detail=True, max_content=3)

    assert "content: abc... [truncated]" in detail


def test_run_trace_viewer_detail_can_disable_content_truncation(tmp_path):
    trace_path = tmp_path / "trace.json"
    trace = {
        "run": {"id": "run-1", "status": "completed", "metadata": {}},
        "steps": [],
        "events": [
            {
                "type": "text",
                "step_id": "step-1",
                "content": "abcdef",
                "metadata": {},
            }
        ],
    }
    trace_path.write_text(json.dumps(trace), encoding="utf-8")

    detail = run_trace_viewer(str(trace_path), detail=True, max_content=0)

    assert "content: abcdef" in detail
    assert "[truncated]" not in detail


def test_run_trace_viewer_returns_markdown_when_requested(tmp_path):
    trace_path = tmp_path / "trace.json"
    trace = {
        "run": {
            "status": "completed",
            "metadata": {"task": "读取 README", "mode": "agent"},
        },
        "steps": [{"type": "final", "metadata": {}}],
        "events": [{"type": "text", "content": "完成"}],
    }
    trace_path.write_text(json.dumps(trace), encoding="utf-8")

    report = run_trace_viewer(str(trace_path), markdown=True)

    assert report.startswith("# MiniCode Trace Report")
    assert "- task: 读取 README" in report
    assert "1. final" in report
    assert "完成" in report


def test_run_trace_viewer_saves_markdown_when_output_is_provided(tmp_path):
    trace_path = tmp_path / "trace.json"
    output_path = tmp_path / "reports" / "trace.md"
    trace = {
        "run": {
            "status": "completed",
            "metadata": {"task": "读取 README", "mode": "agent"},
        },
        "steps": [{"type": "final", "metadata": {}}],
        "events": [{"type": "text", "content": "完成"}],
    }
    trace_path.write_text(json.dumps(trace), encoding="utf-8")

    output = run_trace_viewer(str(trace_path), markdown=True, output=str(output_path))

    assert output == f"Markdown report saved to {output_path}"
    assert output_path.exists()
    assert "# MiniCode Trace Report" in output_path.read_text(encoding="utf-8")


def test_run_trace_viewer_markdown_takes_priority_over_detail(tmp_path):
    trace_path = tmp_path / "trace.json"
    trace = {
        "run": {"id": "run-1", "status": "completed", "metadata": {}},
        "steps": [],
        "events": [],
    }
    trace_path.write_text(json.dumps(trace), encoding="utf-8")

    report = run_trace_viewer(str(trace_path), detail=True, markdown=True)

    assert report.startswith("# MiniCode Trace Report")
    assert "id: run-1" not in report


def test_run_trace_list_returns_numbered_paths(tmp_path):
    trace_dir = tmp_path / "traces"
    trace_dir.mkdir()
    trace_path = trace_dir / "trace.json"
    trace_path.write_text('{"run":{"metadata":{}}}', encoding="utf-8")

    output = run_trace_list(str(trace_dir), limit=10)

    assert output == f"1. {trace_path}"


def test_run_trace_list_returns_message_when_empty(tmp_path):
    output = run_trace_list(str(tmp_path / "missing"), limit=10)

    assert output == "No traces found."


def test_run_trace_list_filters_by_metadata(tmp_path):
    trace_dir = tmp_path / "traces"
    trace_dir.mkdir()
    agent_trace = trace_dir / "agent.json"
    fixed_trace = trace_dir / "fixed.json"
    agent_trace.write_text(
        '{"run":{"metadata":{"mode":"agent","provider":"mimo","model":"mimo-v2.5-pro","task":"读取 README"}}}',
        encoding="utf-8",
    )
    fixed_trace.write_text(
        '{"run":{"metadata":{"mode":"fixed","task":"list files"}}}',
        encoding="utf-8",
    )

    output = run_trace_list(
        str(trace_dir),
        limit=10,
        mode="agent",
        provider="mimo",
        model="mimo-v2.5-pro",
        task_contains="README",
    )

    assert str(agent_trace) in output
    assert str(fixed_trace) not in output


def test_run_trace_cleanup_returns_deleted_count(tmp_path):
    trace_dir = tmp_path / "traces"
    trace_dir.mkdir()
    old_trace = trace_dir / "old.json"
    new_trace = trace_dir / "new.json"
    old_trace.write_text("{}", encoding="utf-8")
    new_trace.write_text("{}", encoding="utf-8")

    import os
    os.utime(old_trace, (1000, 1000))
    os.utime(new_trace, (2000, 2000))

    output = run_trace_cleanup(str(trace_dir), keep=1)

    assert output == "Deleted 1 trace files."
    assert not old_trace.exists()
    assert new_trace.exists()


def test_run_trace_cleanup_returns_empty_message(tmp_path):
    output = run_trace_cleanup(str(tmp_path / "missing"), keep=20)

    assert output == "No trace files deleted."
