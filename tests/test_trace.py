from minicode.models import EventType, Run, StepType
from minicode.trace import TraceRecorder


def test_trace_recorder_starts_empty():
    run = Run()
    recorder = TraceRecorder(run)

    assert recorder.run == run
    assert recorder.steps == []
    assert recorder.events == []


def test_add_step_belongs_to_run():
    run = Run()
    recorder = TraceRecorder(run)

    step = recorder.add_step(StepType.TOOL)

    assert step.run_id == run.id
    assert step.type == StepType.TOOL
    assert recorder.steps == [step]


def test_add_event_belongs_to_step():
    run = Run()
    recorder = TraceRecorder(run)
    step = recorder.add_step(StepType.MODEL)

    event = recorder.add_event(step, EventType.TEXT, content="hello")

    assert event.run_id == run.id
    assert event.step_id == step.id
    assert event.type == EventType.TEXT
    assert event.content == "hello"
    assert recorder.events == [event]


def test_trace_to_dict_contains_run_steps_events():
    run = Run()
    recorder = TraceRecorder(run)
    step = recorder.add_step(StepType.TOOL, metadata={"name": "read_file"})
    recorder.add_event(step, EventType.TOOL_CALL, content="read README")

    trace = recorder.to_dict()

    assert trace["run"]["id"] == run.id
    assert trace["run"]["status"] == run.status.value
    assert trace["steps"][0]["id"] == step.id
    assert trace["steps"][0]["metadata"] == {"name": "read_file"}
    assert trace["events"][0]["step_id"] == step.id
    assert trace["events"][0]["content"] == "read README"
