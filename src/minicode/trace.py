from typing import Optional

from .models import Event, EventType, Run, Step, StepType


class TraceRecorder:
    """
    TraceRecorder: 用于记录一次用户任务执行过程。
    """

    def __init__(self, run: Run) -> None:
        self.run = run
        self.steps = []
        self.events = []

    def add_step(self, step_type: StepType, metadata: Optional[dict] = None) -> Step:
        step = Step(
            run_id=self.run.id,
            type=step_type,
            metadata=metadata or {},
        )
        self.steps.append(step)
        return step
    
    def add_event(
       self,
       step: Step,
       event_type: EventType,
       content: str = "",
       metadata: Optional[dict] = None,
       ) -> Event:
        event = Event(
            run_id=self.run.id,
            step_id=step.id,
            type=event_type,
            content=content,
            metadata=metadata or {},
        )
        self.events.append(event)
        return event
    
    def to_dict(self) -> dict:
        return {
            "run": {
                "id": self.run.id,
                "status": self.run.status.value,
                "created_at": self.run.created_at.isoformat(),
                "updated_at": self.run.updated_at.isoformat(),
            },
            "steps": [
                {
                    "id": step.id,
                    "run_id": step.run_id,
                    "type": step.type.value,
                    "created_at": step.created_at.isoformat(),
                    "status": getattr(step, "status", "pending"),
                    "metadata": step.metadata,
                }
                for step in self.steps
            ],
            "events": [
                {
                    "id": event.id,
                    "run_id": event.run_id,
                    "step_id": event.step_id,
                    "type": event.type.value,
                    "created_at": event.created_at.isoformat(),
                    "content": event.content,
                    "metadata": event.metadata,
                }
                for event in self.events
            ],
        }
