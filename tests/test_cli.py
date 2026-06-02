from minicode.cli import run_task
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
