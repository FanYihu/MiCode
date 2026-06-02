import subprocess
from dataclasses import dataclass

from minicode.workspace import Workspace


@dataclass
class CommandResult:
    command: str
    exit_code: int
    stdout: str
    stderr: str
    timed_out: bool = False


class ShellTools:
    """在工作区目录内执行 shell 命令并捕获结果。"""

    def __init__(self, workspace: Workspace) -> None:
        self.workspace = workspace

    def run(self, command: str, timeout: int = 10) -> CommandResult:
        try:
            completed = subprocess.run(
                command,
                cwd=self.workspace.root,
                shell=True,
                text=True,
                capture_output=True,
                timeout=timeout,
            )
        except subprocess.TimeoutExpired as error:
            return CommandResult(
                command=command,
                exit_code=-1,
                stdout=error.stdout or "",
                stderr=error.stderr or "命令执行超时",
                timed_out=True,
            )

        return CommandResult(
            command=command,
            exit_code=completed.returncode,
            stdout=completed.stdout,
            stderr=completed.stderr,
            timed_out=False,
        )
