import subprocess

from minicode.tools.git import GitTools
from minicode.workspace import Workspace


def _init_repo(path) -> None:
    subprocess.run(["git", "init"], cwd=path, check=True, capture_output=True)
    subprocess.run(
        ["git", "config", "user.email", "test@example.com"],
        cwd=path,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "MiniCode Test"],
        cwd=path,
        check=True,
        capture_output=True,
    )


def test_git_tools_status_returns_short_status(tmp_path):
    _init_repo(tmp_path)
    (tmp_path / "README.md").write_text("hello\n", encoding="utf-8")
    tools = GitTools(Workspace(str(tmp_path)))

    result = tools.status()

    assert result.ok is True
    assert "?? README.md" in result.output
    assert result.metadata["exit_code"] == 0
    assert result.metadata["command"] == ["git", "status", "--short"]


def test_git_tools_diff_returns_unstaged_diff(tmp_path):
    _init_repo(tmp_path)
    file_path = tmp_path / "README.md"
    file_path.write_text("hello\n", encoding="utf-8")
    subprocess.run(["git", "add", "README.md"], cwd=tmp_path, check=True)
    subprocess.run(["git", "commit", "-m", "initial"], cwd=tmp_path, check=True)
    file_path.write_text("hello\nminicode\n", encoding="utf-8")
    tools = GitTools(Workspace(str(tmp_path)))

    result = tools.diff()

    assert result.ok is True
    assert "+minicode" in result.output
    assert result.metadata["exit_code"] == 0
    assert result.metadata["command"] == ["git", "diff"]


def test_git_tools_returns_failure_outside_git_repo(tmp_path):
    tools = GitTools(Workspace(str(tmp_path)))

    result = tools.status()

    assert result.ok is False
    assert result.output
    assert result.metadata["exit_code"] != 0
