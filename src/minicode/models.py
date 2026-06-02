from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime, timezone
import uuid


class RunStatus(str, Enum):
    """Run 的状态枚举"""
    CREATED = "created"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class StepType(str, Enum):
    """Step 的类型枚举"""
    MODEL = "model"
    TOOL = "tool"
    HUMAN = "human"
    FINAL = "final"


class EventType(str, Enum):
    """Event 的类型枚举"""
    TEXT = "text"
    STATE = "state"
    TOOL_CALL = "tool_call"
    ERROR = "error"


class InvalidRunStatusTransition(Exception):
    """Run 状态流转非法时抛出的异常"""


@dataclass
class Run:
    """
    Run: 代表一次完整的用户任务执行过程。
    它是顶层容器，包含多个 Step。
    """
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    status: RunStatus = field(default=RunStatus.CREATED)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    # 可以预留一些元数据字段，比如 user_id, input_prompt 等，但今日目标只需基础字段
    metadata: dict = field(default_factory=dict)

    def start(self) -> None:
        if self.status != RunStatus.CREATED:
            raise InvalidRunStatusTransition("状态流转非法")

        now = datetime.now(timezone.utc)
        self.status = RunStatus.RUNNING
        self.started_at = now
        self.updated_at = now

    def complete(self) -> None:
        if self.status != RunStatus.RUNNING:
            raise InvalidRunStatusTransition("状态流转非法")

        now = datetime.now(timezone.utc)
        self.status = RunStatus.COMPLETED
        self.completed_at = now
        self.updated_at = now

    def fail(self) -> None:
        if self.status != RunStatus.RUNNING:
            raise InvalidRunStatusTransition("状态流转非法")

        now = datetime.now(timezone.utc)
        self.status = RunStatus.FAILED
        self.completed_at = now
        self.updated_at = now

    def cancel(self) -> None:
        if self.status not in (RunStatus.RUNNING, RunStatus.CREATED):
            raise InvalidRunStatusTransition("状态流转非法")

        now = datetime.now(timezone.utc)
        self.status = RunStatus.CANCELLED
        self.completed_at = now
        self.updated_at = now


@dataclass
class Step:
    """
    Step: 代表 Run 执行过程中的一个具体步骤（如调用模型、调用工具、人工干预）。
    它归属于某个 Run，并包含多个 Event。
    """
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    run_id: str = ""  # 关联的 Run ID
    type: StepType = field(default=StepType.MODEL)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    # 可以预留状态或结果字段
    status: str = field(default="pending")  # 例如 pending, success, error
    metadata: dict = field(default_factory=dict)


@dataclass
class Event:
    """
    Event: 代表 Step 中产生的可观察事件（如模型输出的文本、工具调用的参数、错误信息）。
    它归属于某个 Step 和 Run。
    """
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    run_id: str = ""  # 关联的 Run ID
    step_id: str = ""  # 关联的 Step ID
    type: EventType = field(default=EventType.TEXT)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    content: str = ""  # 事件的具体内容
    metadata: dict = field(default_factory=dict)
