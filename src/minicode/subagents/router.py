from dataclasses import dataclass, field

from minicode.subagents.models import (
    SUBAGENT_FAILED,
    SubAgentExecutor,
    SubAgentResult,
    SubAgentTask,
)
from minicode.workspace import Workspace


@dataclass
class RoleBasedSubAgentExecutor:
    """按 role 把任务分发给对应 SubAgent executor。"""

    executors: dict[str, SubAgentExecutor] = field(default_factory=dict)

    def register(self, role: str, executor: SubAgentExecutor) -> None:
        """注册一个角色 executor；同角色后注册会覆盖旧实现。"""
        self.executors[role] = executor

    def execute(self, task: SubAgentTask) -> SubAgentResult:
        """执行对应角色；没有 executor 时返回失败结果，交给主 Agent 决策。"""
        executor = self.executors.get(task.role)
        if executor is None:
            return SubAgentResult(
                task_id=task.id,
                role=task.role,
                status=SUBAGENT_FAILED,
                summary=f"No subagent executor registered for role: {task.role}",
                metadata={"error": "missing_subagent_executor"},
            )
        return executor.execute(task)


def create_default_subagent_executor(
    workspace: Workspace = None,
) -> RoleBasedSubAgentExecutor:
    """创建当前 MiniCode 默认 SubAgent 组合。

    没有 workspace 时只能提供只读 reviewer；传入 workspace 后，
    tester 可以复用 ShellTools 在工作区内运行受控测试命令。
    """
    from minicode.subagents.reviewer import ReviewerSubAgent
    from minicode.subagents.implementer import ImplementerSubAgent
    from minicode.subagents.tester import TesterSubAgent
    from minicode.tools.file import FileTools
    from minicode.tools.shell import ShellTools

    executors: dict[str, SubAgentExecutor] = {"reviewer": ReviewerSubAgent()}
    if workspace is not None:
        executors["tester"] = TesterSubAgent(ShellTools(workspace))
        executors["implementer"] = ImplementerSubAgent(FileTools(workspace))
    return RoleBasedSubAgentExecutor(executors)
