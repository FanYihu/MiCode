import subprocess

from minicode.tool_registry import ToolResult
from minicode.workspace import Workspace


class GitTools:
    """只读 Git 工具，负责查看工作区状态和 diff。"""

    def __init__(self, workspace: Workspace) -> None:
        self.workspace = workspace

    def status(self) -> ToolResult:
        """返回 git status --short 的输出。"""
        return self._run_git(["status", "--short"])

    def diff(self) -> ToolResult:
        """返回 git diff 的输出。"""
        return self._run_git(["diff"])

    def _run_git(self, args: list[str]) -> ToolResult:
        """执行固定 git 子命令；失败也转成 ToolResult。"""
        command = ["git"] + args
        try:
            completed = subprocess.run(
                command,
                cwd=self.workspace.root,
                text=True,
                capture_output=True,
                timeout=10,
            )
        except FileNotFoundError:
            return ToolResult(
                ok=False,
                output="git is not installed",
                metadata={"command": command, "error": "git_not_found"},
            )
        except subprocess.TimeoutExpired:
            return ToolResult(
                ok=False,
                output="git command timed out",
                metadata={"command": command, "error": "git_timeout"},
            )

        output = completed.stdout if completed.returncode == 0 else completed.stderr
        return ToolResult(
            ok=completed.returncode == 0,
            output=output,
            metadata={
                "command": command,
                "exit_code": completed.returncode,
                "stderr": completed.stderr,
            },
        )
