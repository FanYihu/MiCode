from micode.tools.shell import ShellTools
from micode.workspace import Workspace


def test_run_success_command(tmp_path):
    result = ShellTools(Workspace(str(tmp_path))).run("echo hello")

    assert result.exit_code == 0
    assert result.stdout.strip() == "hello"
    assert result.timed_out is False


def test_run_failure_command(tmp_path):
    result = ShellTools(Workspace(str(tmp_path))).run("python3 -c 'import sys; sys.exit(3)'")

    assert result.exit_code == 3
    assert result.timed_out is False


def test_run_uses_workspace_cwd(tmp_path):
    (tmp_path / "hello.txt").write_text("hello", encoding="utf-8")

    result = ShellTools(Workspace(str(tmp_path))).run("cat hello.txt")

    assert result.stdout == "hello"


def test_run_timeout(tmp_path):
    result = ShellTools(Workspace(str(tmp_path))).run(
        "python3 -c 'import time; time.sleep(1)'",
        timeout=0.1,
    )

    assert result.exit_code == -1
    assert result.timed_out is True
