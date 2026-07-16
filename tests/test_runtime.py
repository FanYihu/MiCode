import time

from micode.agent import AgentAction, MicodeAgent
from micode.models import RunStatus
from micode.runtime import AgentRuntime, RuntimeProfile, StopReason, TurnPhase
from micode.tools.registry import ToolDefinition, ToolRegistry, ToolResult
from micode.workspace import Workspace


class SequenceLLM:
    def __init__(self, actions):
        self.actions = list(actions)

    def next_action(self, task, observations):
        return self.actions.pop(0)


def test_runtime_streams_events_before_result(tmp_path):
    registry = ToolRegistry()

    def slow_tool(args):
        time.sleep(0.02)
        return ToolResult(ok=True, output="evidence")

    registry.register(
        ToolDefinition(
            name="slow",
            description="Return delayed evidence for streaming tests.",
            handler=slow_tool,
        )
    )
    agent = MicodeAgent(
        Workspace(str(tmp_path)),
        SequenceLLM(
            [
                AgentAction(tool="slow", args={}),
                AgentAction(tool="", args={"answer": "done"}, final=True),
            ]
        ),
        tool_registry=registry,
    )

    events = list(AgentRuntime(agent).stream("test streaming"))

    assert [event.type for event in events] == [
        "run_started",
        "model_started",
        "tool_batch_started",
        "tool_batch_completed",
        "model_started",
        "run_stopped",
        "runtime_result",
    ]
    assert events[2].phase == TurnPhase.ACT
    assert events[-1].metadata["trace"]["run"]["status"] == "completed"


def test_runtime_profile_enforces_evidence_gate(tmp_path):
    agent = MicodeAgent(
        Workspace(str(tmp_path)),
        SequenceLLM([AgentAction(tool="", args={"answer": "guess"}, final=True)]),
    )
    profile = RuntimeProfile(require_tool_evidence=True)

    trace = AgentRuntime(agent, profile).run("answer with evidence")

    assert trace["run"]["status"] == RunStatus.FAILED.value
    assert trace["run"]["metadata"]["stop_reason"] == StopReason.EVIDENCE_REQUIRED.value


def test_runtime_retries_transient_model_protocol_error(tmp_path):
    class RetryLLM:
        def __init__(self):
            self.calls = 0

        def next_action(self, task, observations):
            self.calls += 1
            if self.calls == 1:
                from micode.agent import InvalidActionText

                raise InvalidActionText("temporary malformed response")
            return AgentAction(tool="", args={"answer": "recovered"}, final=True)

    llm = RetryLLM()
    agent = MicodeAgent(Workspace(str(tmp_path)), llm)

    trace = AgentRuntime(agent, RuntimeProfile(max_model_retries=1)).run("retry")

    assert trace["run"]["status"] == RunStatus.COMPLETED.value
    assert llm.calls == 2
