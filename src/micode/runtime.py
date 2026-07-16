from __future__ import annotations

import queue
import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Iterator, Optional


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class TurnPhase(str, Enum):
    """Runtime 对外公开的执行阶段。"""

    START = "start"
    EXPLORE = "explore"
    ACT = "act"
    VERIFY = "verify"
    WAITING = "waiting"
    FINISH = "finish"


class StopReason(str, Enum):
    """一次运行停止的明确原因，避免调用方猜测 RunStatus。"""

    COMPLETED = "completed"
    HUMAN_REVIEW = "human_review"
    MAX_STEPS = "max_steps"
    MODEL_ERROR = "model_error"
    TOOL_ERROR = "tool_error"
    EVIDENCE_REQUIRED = "evidence_required"
    CANCELLED = "cancelled"
    INTERNAL_ERROR = "internal_error"


@dataclass(frozen=True)
class RuntimeProfile:
    """控制 Agent Loop 深度和验证门禁的运行画像。"""

    name: str = "single"
    max_turns: int = 9
    max_model_retries: int = 1
    require_tool_evidence: bool = False
    verify_before_finish: bool = False
    widening_after_turn: int = 4

    def __post_init__(self) -> None:
        if self.max_turns < 1:
            raise ValueError("max_turns must be positive")
        if self.max_model_retries < 0:
            raise ValueError("max_model_retries cannot be negative")
        if self.widening_after_turn < 1:
            raise ValueError("widening_after_turn must be positive")

    @classmethod
    def single_deep(cls) -> "RuntimeProfile":
        """需要更深探索与证据校验时使用的显式画像。"""
        return cls(
            name="single-deep",
            max_turns=16,
            max_model_retries=2,
            require_tool_evidence=True,
            verify_before_finish=True,
            widening_after_turn=6,
        )


@dataclass(frozen=True)
class RuntimeEvent:
    """TUI、headless 和持久化层共同消费的流式事件。"""

    type: str
    phase: TurnPhase
    run_id: str = ""
    turn_index: int = 0
    content: str = ""
    metadata: dict = field(default_factory=dict)
    created_at: str = field(default_factory=_utc_now_iso)
    id: str = field(default_factory=lambda: str(uuid.uuid4()))

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "type": self.type,
            "phase": self.phase.value,
            "run_id": self.run_id,
            "turn_index": self.turn_index,
            "content": self.content,
            "metadata": self.metadata,
            "created_at": self.created_at,
        }


class AgentRuntime:
    """在线程中运行同步 Agent，并实时转发结构化 RuntimeEvent。"""

    def __init__(self, agent: Any, profile: Optional[RuntimeProfile] = None) -> None:
        self.agent = agent
        self.profile = profile or RuntimeProfile()

    def stream(self, task: str) -> Iterator[RuntimeEvent]:
        """流式执行任务；最后一个事件始终是 runtime_result。"""
        events: "queue.Queue[object]" = queue.Queue()
        sentinel = object()

        def emit(event: RuntimeEvent) -> None:
            events.put(event)

        def worker() -> None:
            try:
                trace = self.agent.run(
                    task,
                    runtime_profile=self.profile,
                    event_sink=emit,
                )
                events.put(
                    RuntimeEvent(
                        type="runtime_result",
                        phase=TurnPhase.FINISH,
                        run_id=str(trace.get("run", {}).get("id", "")),
                        metadata={"trace": trace},
                    )
                )
            except Exception as error:  # Runtime 边界必须把后台异常带回消费者。
                events.put(
                    RuntimeEvent(
                        type="runtime_error",
                        phase=TurnPhase.FINISH,
                        content=str(error),
                        metadata={"stop_reason": StopReason.INTERNAL_ERROR.value},
                    )
                )
            finally:
                events.put(sentinel)

        thread = threading.Thread(target=worker, name="micode-runtime", daemon=True)
        thread.start()
        while True:
            item = events.get()
            if item is sentinel:
                break
            yield item  # type: ignore[misc]
        thread.join()

    def run(self, task: str) -> dict:
        """消费流并返回最终 Trace，适合非流式调用方。"""
        trace = None
        for event in self.stream(task):
            if event.type == "runtime_result":
                trace = event.metadata["trace"]
            elif event.type == "runtime_error":
                raise RuntimeError(event.content)
        if trace is None:
            raise RuntimeError("runtime ended without a result")
        return trace
