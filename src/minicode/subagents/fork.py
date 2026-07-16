from dataclasses import dataclass, field
import shutil
import tempfile
from pathlib import Path
from typing import Callable

from minicode.subagents.models import (
    SUBAGENT_FAILED,
    SubAgentExecutor,
    SubAgentResult,
    SubAgentTask,
)
from minicode.workspace import Workspace


DEFAULT_FORK_IGNORE_DIRS = {
    ".git",
    ".minicode",
    ".pytest_cache",
    "__pycache__",
}


@dataclass
class ForkedSubAgentExecutor:
    """在临时 workspace fork 中执行 SubAgent。

    Fork Mode 让 implementer/tester 可以在隔离副本里试错；默认不会把文件
    写回原工作区，主 Agent 后续可以根据 result metadata 决定是否采纳。
    """

    workspace: Workspace
    executor_factory: Callable[[Workspace], SubAgentExecutor]
    keep_forks: bool = True
    ignore_dirs: set[str] = field(default_factory=lambda: set(DEFAULT_FORK_IGNORE_DIRS))

    def execute(self, task: SubAgentTask) -> SubAgentResult:
        """复制 workspace，使用 fork 内 executor 执行任务。"""
        fork_root = Path(tempfile.mkdtemp(prefix="minicode-subagent-fork-"))
        try:
            _copy_workspace(self.workspace.root, fork_root, self.ignore_dirs)
            fork_executor = self.executor_factory(Workspace(str(fork_root)))
            result = fork_executor.execute(task)
            if not isinstance(result, SubAgentResult):
                return SubAgentResult(
                    task_id=task.id,
                    role=task.role,
                    status=SUBAGENT_FAILED,
                    summary="Forked executor must return SubAgentResult",
                    metadata={"error": "invalid_forked_result"},
                )

            result.metadata = {
                **result.metadata,
                "fork_mode": {
                    "enabled": True,
                    "workspace_root": str(self.workspace.root),
                    "fork_root": str(fork_root),
                    "kept": self.keep_forks,
                },
            }
            return result
        finally:
            if not self.keep_forks:
                shutil.rmtree(fork_root, ignore_errors=True)


def _copy_workspace(source: Path, target: Path, ignore_dirs: set[str]) -> None:
    """复制 workspace 内容，跳过运行产物和 git 元数据。"""
    for item in source.iterdir():
        if item.name in ignore_dirs:
            continue
        destination = target / item.name
        if item.is_dir():
            shutil.copytree(
                item,
                destination,
                ignore=shutil.ignore_patterns(*ignore_dirs),
            )
        else:
            shutil.copy2(item, destination)
