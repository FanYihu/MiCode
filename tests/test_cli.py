from pathlib import Path

from minicode.agent import AgentAction
from minicode.cli import maybe_save_trace, run_agent_task, run_task
from minicode.models import RunStatus, StepType


def test_cli_list_files(tmp_path):
    (tmp_path / "README.md").write_text("hello", encoding="utf-8")

    trace = run_task("list files", str(tmp_path))

    assert trace["run"]["status"] == RunStatus.COMPLETED.value
    assert trace["steps"][0]["type"] == StepType.TOOL.value
    assert trace["steps"][0]["metadata"]["tool"] == "list_files"
    assert "README.md" in trace["events"][0]["content"]


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
