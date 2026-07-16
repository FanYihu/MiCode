from dataclasses import dataclass, field
from typing import Protocol
import uuid


SUBAGENT_COMPLETED = "completed"
SUBAGENT_FAILED = "failed"


@dataclass
class SubAgentTask:
    """主 Agent 交给 SubAgent 的受控任务契约。"""

    role: str
    objective: str
    context: str = ""
    allowed_tools: list[str] = field(default_factory=list)
    allowed_paths: list[str] = field(default_factory=list)
    max_steps: int = 4
    parent_run_id: str = ""
    metadata: dict = field(default_factory=dict)
    id: str = field(default_factory=lambda: f"subtask:{uuid.uuid4()}")

    def to_dict(self) -> dict:
        """转成 ToolResult 和 Trace 可复用的结构。"""
        return {
            "id": self.id,
            "role": self.role,
            "objective": self.objective,
            "context": self.context,
            "allowed_tools": list(self.allowed_tools),
            "allowed_paths": list(self.allowed_paths),
            "max_steps": self.max_steps,
            "parent_run_id": self.parent_run_id,
            "metadata": self.metadata,
        }


@dataclass
class SubAgentResult:
    """SubAgent 返回给主 Agent 的最小结果契约。"""

    task_id: str
    role: str
    status: str
    summary: str
    evidence: list[str] = field(default_factory=list)
    artifacts: list[dict] = field(default_factory=list)
    changed_paths: list[str] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        """只有 completed 状态才表示子任务成功。"""
        return self.status == SUBAGENT_COMPLETED

    def to_dict(self) -> dict:
        """转成统一 Tool metadata。"""
        return {
            "task_id": self.task_id,
            "role": self.role,
            "status": self.status,
            "summary": self.summary,
            "evidence": list(self.evidence),
            "artifacts": list(self.artifacts),
            "changed_paths": list(self.changed_paths),
            "metadata": self.metadata,
        }


class SubAgentExecutor(Protocol):
    """具体 SubAgent runtime 必须实现的执行接口。"""

    def execute(self, task: SubAgentTask) -> SubAgentResult:
        """执行受控子任务，并返回结构化结果。"""
        ...


@dataclass
class SubAgentPolicy:
    """由主 Agent 配置的 SubAgent 边界，模型不能自行扩大权限。"""

    allowed_roles: tuple[str, ...] = ("reviewer", "tester", "implementer")
    allowed_tools_by_role: dict[str, list[str]] = field(
        default_factory=lambda: {
            "reviewer": ["list_files", "read_file", "git_diff"],
            "tester": ["list_files", "read_file", "run_shell"],
            "implementer": [
                "list_files",
                "read_file",
                "replace_text",
                "write_file",
                "run_shell",
                "git_diff",
            ],
        }
    )
    allowed_paths: list[str] = field(default_factory=lambda: ["."])
    default_max_steps: int = 4
    max_steps: int = 8

    def tools_for(self, role: str) -> list[str]:
        """返回该角色由主 Agent 固定授予的工具白名单。"""
        return list(self.allowed_tools_by_role.get(role, []))

    def clamp_steps(self, requested_steps) -> int:
        """把模型请求的步数限制在策略上限内。"""
        try:
            steps = int(requested_steps)
        except (TypeError, ValueError):
            steps = self.default_max_steps
        if steps <= 0:
            steps = self.default_max_steps
        return min(steps, max(1, self.max_steps))
