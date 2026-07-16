import threading
import time
import json

from minicode.agent import (
    AgentAction,
    AgentTurn,
    InvalidActionText,
    LLMError,
    MiniCodeAgent,
)
from minicode.context.artifacts import ArtifactStore
from minicode.models import EventType, RunStatus, StepType
from minicode.skills import LLMSkillRouter, Skill
from minicode.tools.registry import ToolDefinition, ToolRegistry, ToolResult
from minicode.workspace import Workspace


class SequenceLLM:
    """测试专用 LLM：按顺序返回预设 action。"""

    def __init__(self, actions):
        self.actions = actions
        self.index = 0

    def next_action(self, task, observations):
        action = self.actions[self.index]
        self.index += 1
        return action


class RepeatingLLM:
    """测试专用 LLM：一直返回同一个 action，用来验证最大步数保护。"""

    def __init__(self, action):
        self.action = action

    def next_action(self, task, observations):
        return self.action


class ErrorLLM:
    """测试专用 LLM：模拟模型层异常。"""

    def __init__(self, error):
        self.error = error

    def next_action(self, task, observations):
        raise self.error


class PromptCapturingLLM:
    """测试专用 LLM：记录 Agent 设置的 Skill Summary。"""

    def __init__(self):
        self.skill_summaries = ""

    def set_skill_summaries(self, skill_summaries):
        self.skill_summaries = skill_summaries

    def next_action(self, task, observations):
        return AgentAction(tool="", args={"answer": self.skill_summaries}, final=True)


class RouterClient:
    """测试专用 Skill Router client。"""

    def generate(self, prompt):
        return '{"skills":["python-test"]}'


class SkillObservationLLM:
    """测试专用 LLM：先加载 Skill，再确认完整内容进入 observations。"""

    def __init__(self):
        self.calls = 0

    def next_action(self, task, observations):
        self.calls += 1
        if self.calls == 1:
            return AgentAction(
                tool="load_skill",
                args={"name": "python-test"},
            )

        if "Use pytest." in observations[-1]:
            return AgentAction(
                tool="",
                args={"answer": "Skill 内容已加载"},
                final=True,
            )

        return AgentAction(tool="", args={"answer": "缺少 Skill 内容"}, final=True)


def test_agent_reads_file_then_finishes(tmp_path):
    (tmp_path / "README.md").write_text("hello minicode", encoding="utf-8")
    agent = MiniCodeAgent(
        Workspace(str(tmp_path)),
        SequenceLLM(
            [
                AgentAction(tool="read_file", args={"path": "README.md"}),
                AgentAction(tool="", args={"answer": "读取完成"}, final=True),
            ]
        ),
    )

    trace = agent.run("read README")

    assert trace["run"]["status"] == RunStatus.COMPLETED.value
    assert [step["type"] for step in trace["steps"]] == [
        StepType.TOOL.value,
        StepType.FINAL.value,
    ]
    assert "hello minicode" in trace["events"][0]["content"]
    assert trace["events"][-1]["content"] == "读取完成"
    assert trace["run"]["metadata"]["task"] == "read README"
    assert trace["run"]["metadata"]["mode"] == "agent"


def test_agent_records_provider_and_model_metadata(tmp_path):
    class Client:
        provider = "mimo"
        model = "mimo-v2.5-pro"

    class LLM:
        def __init__(self):
            self.client = Client()
            self.actions = [AgentAction(tool="", args={"answer": "完成"}, final=True)]

        def next_action(self, task, observations):
            return self.actions.pop(0)

    agent = MiniCodeAgent(Workspace(str(tmp_path)), LLM())

    trace = agent.run("metadata test")

    assert trace["run"]["metadata"]["provider"] == "mimo"
    assert trace["run"]["metadata"]["model"] == "mimo-v2.5-pro"


def test_agent_denies_dangerous_shell_command(tmp_path):
    agent = MiniCodeAgent(
        Workspace(str(tmp_path)),
        SequenceLLM(
            [
                AgentAction(tool="run_shell", args={"command": "rm -rf /"}),
            ]
        ),
    )

    trace = agent.run("dangerous command")

    assert trace["run"]["status"] == RunStatus.FAILED.value
    assert trace["steps"][0]["metadata"]["tool"] == "run_shell"
    assert "权限不足" in trace["events"][-1]["content"]
    assert trace["events"][-1]["type"] == EventType.ERROR.value
    assert trace["events"][-1]["metadata"]["tool"] == "run_shell"
    assert trace["events"][-1]["metadata"]["args"] == {"command": "rm -rf /"}
    assert trace["events"][-1]["metadata"]["ok"] is False
    assert trace["events"][-1]["metadata"]["error"]
    assert trace["events"][-1]["metadata"]["details"]["decision"]
    assert "review_message" in trace["events"][-1]["metadata"]["details"]


def test_agent_routes_tool_actions_through_tool_registry(tmp_path):
    registry = ToolRegistry()
    registry.register(
        ToolDefinition(
            name="echo",
            description="Echo text for agent observation.",
            handler=lambda args: ToolResult(
                ok=True,
                output=f"echo: {args['text']}",
                metadata={"custom": "yes"},
            ),
        )
    )
    agent = MiniCodeAgent(
        Workspace(str(tmp_path)),
        SequenceLLM(
            [
                AgentAction(tool="echo", args={"text": "hello"}),
                AgentAction(tool="", args={"answer": "完成"}, final=True),
            ]
        ),
        tool_registry=registry,
    )

    trace = agent.run("echo test")

    assert trace["run"]["status"] == RunStatus.COMPLETED.value
    assert trace["events"][0]["type"] == EventType.TOOL_CALL.value
    assert trace["events"][0]["content"] == "echo: hello"
    assert trace["events"][0]["metadata"]["tool"] == "echo"
    assert trace["events"][0]["metadata"]["args"] == {"text": "hello"}
    assert trace["events"][0]["metadata"]["details"]["custom"] == "yes"


def test_agent_summarizes_observation_but_keeps_full_trace_output(tmp_path):
    full_output = "START\n" + "x" * 500 + "\nEND RESULT"
    registry = ToolRegistry()
    registry.register(
        ToolDefinition(
            name="large_output",
            description="Return a large result.",
            handler=lambda args: ToolResult(ok=True, output=full_output),
        )
    )

    class ObservationLLM:
        def __init__(self):
            self.calls = 0
            self.observation = ""

        def next_action(self, task, observations):
            self.calls += 1
            if self.calls == 1:
                return AgentAction(tool="large_output", args={})
            self.observation = observations[-1]
            return AgentAction(tool="", args={"answer": "完成"}, final=True)

    llm = ObservationLLM()
    trace = MiniCodeAgent(
        Workspace(str(tmp_path)),
        llm,
        tool_registry=registry,
        tool_result_budget_chars=100,
    ).run("large output")

    assert trace["events"][0]["content"] == full_output
    assert len(llm.observation) <= 100
    assert "START" in llm.observation
    assert "END RESULT" in llm.observation
    assert trace["events"][0]["metadata"]["observation_truncated"] is True
    assert trace["events"][0]["metadata"]["observation_used_chars"] <= 100


def test_agent_returns_summary_to_native_tool_protocol(tmp_path):
    full_output = "HEADER\n" + "x" * 400 + "\nFINAL"
    registry = ToolRegistry()
    registry.register(
        ToolDefinition(
            name="large_output",
            description="Return a large result.",
            handler=lambda args: ToolResult(ok=True, output=full_output),
        )
    )

    class NativeLLM:
        def __init__(self):
            self.calls = 0
            self.recorded = []

        def next_action(self, task, observations):
            self.calls += 1
            if self.calls == 1:
                return AgentAction(
                    tool="large_output",
                    args={},
                    tool_call_id="call-large",
                )
            return AgentAction(tool="", args={"answer": "完成"}, final=True)

        def record_tool_result(self, action, output):
            self.recorded.append((action.tool_call_id, output))

    llm = NativeLLM()
    trace = MiniCodeAgent(
        Workspace(str(tmp_path)),
        llm,
        tool_registry=registry,
        tool_result_budget_chars=90,
    ).run("large native result")

    assert trace["events"][0]["content"] == full_output
    assert llm.recorded[0][0] == "call-large"
    assert len(llm.recorded[0][1]) <= 90
    assert "FINAL" in llm.recorded[0][1]


def test_agent_externalizes_large_tool_result_as_artifact(tmp_path):
    full_output = "HEAD\n" + "x" * 500 + "\nTAIL"
    registry = ToolRegistry()
    registry.register(
        ToolDefinition(
            name="large_output",
            description="Return a large result.",
            handler=lambda args: ToolResult(ok=True, output=full_output),
        )
    )

    class ObservationLLM:
        def __init__(self):
            self.calls = 0
            self.observation = ""

        def next_action(self, task, observations):
            self.calls += 1
            if self.calls == 1:
                return AgentAction(tool="large_output", args={})
            self.observation = observations[-1]
            return AgentAction(tool="", args={"answer": "完成"}, final=True)

    artifact_dir = tmp_path / "artifacts"
    llm = ObservationLLM()
    trace = MiniCodeAgent(
        Workspace(str(tmp_path)),
        llm,
        tool_registry=registry,
        tool_result_budget_chars=80,
        artifact_dir=str(artifact_dir),
        artifact_threshold_chars=100,
    ).run("large artifact")

    event = trace["events"][0]
    artifact = event["metadata"]["artifact"]
    payload = json.loads(open(artifact["artifact_path"], encoding="utf-8").read())

    assert event["content"] != full_output
    assert artifact["artifact_id"].startswith("artifact:tool-result:")
    assert artifact["artifact_placeholder"] in event["content"]
    assert artifact["artifact_placeholder"] in llm.observation
    assert payload["content"] == full_output


def test_agent_records_decision_freeze_for_each_model_turn(tmp_path):
    registry = ToolRegistry()
    registry.register(
        ToolDefinition(
            name="echo",
            description="Echo text.",
            handler=lambda args: ToolResult(ok=True, output="hello"),
        )
    )
    agent = MiniCodeAgent(
        Workspace(str(tmp_path)),
        SequenceLLM(
            [
                AgentAction(tool="echo", args={}),
                AgentAction(tool="", args={"answer": "完成"}, final=True),
            ]
        ),
        tool_registry=registry,
        prompt_cache_key="prompt-cache:test",
    )

    trace = agent.run("freeze")
    freezes = trace["run"]["metadata"]["decision_freezes"]
    token_estimates = trace["run"]["metadata"]["token_estimates"]

    assert len(freezes) == 2
    assert len(token_estimates) == 2
    assert freezes[0]["turn_index"] == 1
    assert freezes[1]["turn_index"] == 2
    assert token_estimates[0]["turn_index"] == 1
    assert token_estimates[1]["turn_index"] == 2
    assert token_estimates[1]["estimated_tokens"] > token_estimates[0]["estimated_tokens"]
    assert freezes[0]["prompt_cache_key"] == "prompt-cache:test"
    assert freezes[0]["observations_hash"] != freezes[1]["observations_hash"]


def test_agent_returns_artifact_placeholder_to_native_tool_protocol(tmp_path):
    full_output = "HEAD\n" + "y" * 400 + "\nTAIL"
    registry = ToolRegistry()
    registry.register(
        ToolDefinition(
            name="large_output",
            description="Return a large result.",
            handler=lambda args: ToolResult(ok=True, output=full_output),
        )
    )

    class NativeLLM:
        def __init__(self):
            self.calls = 0
            self.recorded = []

        def next_action(self, task, observations):
            self.calls += 1
            if self.calls == 1:
                return AgentAction(
                    tool="large_output",
                    args={},
                    tool_call_id="call-large",
                )
            return AgentAction(tool="", args={"answer": "完成"}, final=True)

        def record_tool_result(self, action, output):
            self.recorded.append(output)

    llm = NativeLLM()
    trace = MiniCodeAgent(
        Workspace(str(tmp_path)),
        llm,
        tool_registry=registry,
        tool_result_budget_chars=80,
        artifact_dir=str(tmp_path / "artifacts"),
        artifact_threshold_chars=100,
    ).run("large native artifact")

    placeholder = trace["events"][0]["metadata"]["artifact"]["artifact_placeholder"]
    assert placeholder in llm.recorded[0]


def test_default_agent_can_read_saved_artifact(tmp_path):
    artifact_dir = tmp_path / "artifacts"
    artifact = ArtifactStore(str(artifact_dir)).save_tool_result(
        "read_file",
        ToolResult(ok=True, output="artifact content for later turn"),
    )

    class ReadArtifactLLM:
        def __init__(self):
            self.calls = 0
            self.observation = ""

        def set_tool_descriptions(self, tool_descriptions):
            self.tool_descriptions = tool_descriptions

        def set_tool_definitions(self, tool_definitions):
            self.tool_definitions = tool_definitions

        def next_action(self, task, observations):
            self.calls += 1
            if self.calls == 1:
                return AgentAction(
                    tool="read_artifact",
                    args={"id": artifact.id, "max_chars": 0},
                )
            self.observation = observations[-1]
            return AgentAction(tool="", args={"answer": "完成"}, final=True)

    llm = ReadArtifactLLM()
    trace = MiniCodeAgent(
        Workspace(str(tmp_path)),
        llm,
        artifact_dir=str(artifact_dir),
    ).run("read previous artifact")

    assert trace["run"]["status"] == RunStatus.COMPLETED.value
    assert "read_artifact" in "\n".join(llm.tool_descriptions)
    assert "artifact content for later turn" in llm.observation


def test_agent_injects_native_tool_definitions_and_records_call_id(tmp_path):
    class NativeLLM:
        def __init__(self):
            self.tool_definitions = []
            self.calls = 0

        def set_tool_definitions(self, definitions):
            self.tool_definitions = definitions

        def next_action(self, task, observations):
            self.calls += 1
            if self.calls == 1:
                return AgentAction(
                    tool="list_files",
                    args={},
                    tool_call_id="call-list",
                )
            return AgentAction(
                tool="",
                args={"answer": "完成"},
                final=True,
            )

    llm = NativeLLM()
    agent = MiniCodeAgent(Workspace(str(tmp_path)), llm)

    trace = agent.run("列出文件")

    names = [
        item["function"]["name"]
        for item in llm.tool_definitions
    ]
    assert "list_files" in names
    assert trace["steps"][0]["metadata"]["tool_call_id"] == "call-list"


def test_agent_returns_tool_result_to_native_llm_protocol(tmp_path):
    class NativeLLM:
        def __init__(self):
            self.calls = 0
            self.recorded = []

        def next_action(self, task, observations):
            self.calls += 1
            if self.calls == 1:
                return AgentAction(
                    tool="list_files",
                    args={},
                    tool_call_id="call-list",
                )
            return AgentAction(
                tool="",
                args={"answer": "完成"},
                final=True,
            )

        def record_tool_result(self, action, output):
            self.recorded.append((action.tool_call_id, action.tool, output))

    llm = NativeLLM()
    agent = MiniCodeAgent(Workspace(str(tmp_path)), llm)

    trace = agent.run("列出文件")

    assert trace["run"]["status"] == RunStatus.COMPLETED.value
    assert llm.recorded == [("call-list", "list_files", "")]


def test_agent_executes_parallel_safe_batch_concurrently(tmp_path):
    active = 0
    max_active = 0
    lock = threading.Lock()

    def read_handler(args):
        nonlocal active, max_active
        with lock:
            active += 1
            max_active = max(max_active, active)
        time.sleep(0.05)
        with lock:
            active -= 1
        return ToolResult(ok=True, output=args["name"])

    registry = ToolRegistry()
    for name in ["read_a", "read_b"]:
        registry.register(
            ToolDefinition(
                name=name,
                description="Read test data.",
                parallel_safe=True,
                handler=read_handler,
            )
        )

    class BatchLLM:
        def __init__(self):
            self.calls = 0
            self.recorded = []

        def next_turn(self, task, observations):
            self.calls += 1
            if self.calls == 1:
                return AgentTurn(
                    actions=[
                        AgentAction(
                            tool="read_a",
                            args={"name": "a"},
                            tool_call_id="call-a",
                        ),
                        AgentAction(
                            tool="read_b",
                            args={"name": "b"},
                            tool_call_id="call-b",
                        ),
                    ]
                )
            return AgentTurn(final_answer="完成")

        def record_tool_results(self, results):
            self.recorded.extend(results)

    llm = BatchLLM()
    agent = MiniCodeAgent(
        Workspace(str(tmp_path)),
        llm,
        tool_registry=registry,
    )

    trace = agent.run("parallel reads")

    assert trace["run"]["status"] == RunStatus.COMPLETED.value
    assert max_active == 2
    assert [step["metadata"]["execution_mode"] for step in trace["steps"][:2]] == [
        "parallel",
        "parallel",
    ]
    assert [step["metadata"]["batch_index"] for step in trace["steps"][:2]] == [0, 1]
    assert [action.tool_call_id for action, _ in llm.recorded] == [
        "call-a",
        "call-b",
    ]


def test_agent_keeps_mutating_tools_sequential_in_mixed_batch(tmp_path):
    timeline = []
    lock = threading.Lock()

    def handler(name, delay=0.02):
        def run(args):
            with lock:
                timeline.append(f"{name}:start")
            time.sleep(delay)
            with lock:
                timeline.append(f"{name}:end")
            return ToolResult(ok=True, output=name)

        return run

    registry = ToolRegistry()
    registry.register(
        ToolDefinition(
            name="read_a",
            description="Read A.",
            parallel_safe=True,
            handler=handler("read_a"),
        )
    )
    registry.register(
        ToolDefinition(
            name="read_b",
            description="Read B.",
            parallel_safe=True,
            handler=handler("read_b"),
        )
    )
    registry.register(
        ToolDefinition(
            name="write",
            description="Write data.",
            parallel_safe=False,
            handler=handler("write"),
        )
    )
    registry.register(
        ToolDefinition(
            name="read_c",
            description="Read C.",
            parallel_safe=True,
            handler=handler("read_c"),
        )
    )

    class BatchLLM:
        def __init__(self):
            self.calls = 0

        def next_turn(self, task, observations):
            self.calls += 1
            if self.calls > 1:
                return AgentTurn(final_answer="完成")
            return AgentTurn(
                actions=[
                    AgentAction(tool="read_a", args={}),
                    AgentAction(tool="read_b", args={}),
                    AgentAction(tool="write", args={}),
                    AgentAction(tool="read_c", args={}),
                ]
            )

    trace = MiniCodeAgent(
        Workspace(str(tmp_path)),
        BatchLLM(),
        tool_registry=registry,
    ).run("mixed batch")

    modes = [step["metadata"]["execution_mode"] for step in trace["steps"][:4]]
    assert modes == ["parallel", "parallel", "sequential", "sequential"]
    assert timeline.index("write:start") > timeline.index("read_a:end")
    assert timeline.index("write:start") > timeline.index("read_b:end")
    assert timeline.index("read_c:start") > timeline.index("write:end")


def test_agent_stops_remaining_sequential_tools_after_failure(tmp_path):
    executed = []
    registry = ToolRegistry()
    registry.register(
        ToolDefinition(
            name="write_fail",
            description="Fail a write.",
            handler=lambda args: (
                executed.append("write_fail")
                or ToolResult(ok=False, output="failed")
            ),
        )
    )
    registry.register(
        ToolDefinition(
            name="write_after",
            description="Should not run.",
            handler=lambda args: (
                executed.append("write_after")
                or ToolResult(ok=True, output="unexpected")
            ),
        )
    )

    class BatchLLM:
        def next_turn(self, task, observations):
            return AgentTurn(
                actions=[
                    AgentAction(tool="write_fail", args={}),
                    AgentAction(tool="write_after", args={}),
                ]
            )

    trace = MiniCodeAgent(
        Workspace(str(tmp_path)),
        BatchLLM(),
        tool_registry=registry,
    ).run("stop on write failure")

    assert trace["run"]["status"] == RunStatus.FAILED.value
    assert executed == ["write_fail"]
    assert len(trace["steps"]) == 1


def test_agent_loads_skill_content_through_tool_registry(tmp_path):
    skill_dir = tmp_path / ".minicode" / "skills" / "python-test"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(
        "# Python Test\n\nRun Python tests safely.\n\nUse pytest.",
        encoding="utf-8",
    )
    agent = MiniCodeAgent(Workspace(str(tmp_path)), SkillObservationLLM())

    trace = agent.run("run python tests")

    assert trace["run"]["status"] == RunStatus.COMPLETED.value
    assert trace["steps"][0]["type"] == StepType.TOOL.value
    assert trace["events"][0]["metadata"]["tool"] == "load_skill"
    assert "Use pytest." in trace["events"][0]["content"]
    assert trace["events"][-1]["content"] == "Skill 内容已加载"


def test_agent_selects_skills_with_llm_router_before_loop(tmp_path):
    skills = [
        Skill(name=f"skill-{index}", description="General helper.", content="")
        for index in range(21)
    ]
    skills.append(
        Skill(
            name="python-test",
            description="Run Python tests safely.",
            content="Use pytest.",
        )
    )
    llm = PromptCapturingLLM()
    agent = MiniCodeAgent(
        Workspace(str(tmp_path)),
        llm,
        skills=skills,
        skill_router=LLMSkillRouter(RouterClient()),
    )

    trace = agent.run("run tests")

    assert trace["run"]["metadata"]["skills"] == ["python-test"]
    assert "python-test" in trace["events"][-1]["content"]
    assert "Use pytest." not in trace["events"][-1]["content"]


def test_agent_always_includes_project_skills_without_router(tmp_path):
    project_skill = Skill(
        name="project-test",
        description="Project-specific test flow.",
        content="Project content.",
    )
    external_skill = Skill(
        name="user-test",
        description="User-level test flow.",
        content="User content.",
    )
    llm = PromptCapturingLLM()
    agent = MiniCodeAgent(
        Workspace(str(tmp_path)),
        llm,
        skills=[external_skill],
        project_skills=[project_skill],
    )

    trace = agent.run("run tests")

    assert trace["run"]["metadata"]["skills"] == ["project-test"]
    assert "project-test" in trace["events"][-1]["content"]
    assert "user-test" not in trace["events"][-1]["content"]


def test_agent_records_unknown_registry_tool_as_tool_error(tmp_path):
    agent = MiniCodeAgent(
        Workspace(str(tmp_path)),
        SequenceLLM([AgentAction(tool="missing", args={})]),
    )

    trace = agent.run("missing tool")

    assert trace["run"]["status"] == RunStatus.FAILED.value
    assert trace["events"][0]["type"] == EventType.ERROR.value
    assert trace["events"][0]["metadata"]["tool"] == "missing"
    assert trace["events"][0]["metadata"]["error"] == "unknown_tool"


def test_agent_fails_when_max_steps_exceeded(tmp_path):
    agent = MiniCodeAgent(
        Workspace(str(tmp_path)),
        RepeatingLLM(AgentAction(tool="list_files", args={})),
    )

    trace = agent.run("never finish")

    assert trace["run"]["status"] == RunStatus.FAILED.value
    assert trace["events"][-1]["content"] == "超过最大步骤数"


def test_agent_records_invalid_action_text_as_model_error(tmp_path):
    agent = MiniCodeAgent(
        Workspace(str(tmp_path)),
        ErrorLLM(InvalidActionText("action text must be valid json")),
    )

    trace = agent.run("bad model output")

    assert trace["run"]["status"] == RunStatus.FAILED.value
    assert trace["steps"][0]["type"] == StepType.MODEL.value
    assert trace["events"][0]["type"] == EventType.ERROR.value
    assert "valid json" in trace["events"][0]["content"]


def test_agent_records_llm_error_as_model_error(tmp_path):
    agent = MiniCodeAgent(
        Workspace(str(tmp_path)),
        ErrorLLM(LLMError("llm request failed")),
    )

    trace = agent.run("model request")

    assert trace["run"]["status"] == RunStatus.FAILED.value
    assert trace["steps"][0]["type"] == StepType.MODEL.value
    assert trace["events"][0]["type"] == EventType.ERROR.value
    assert "llm request failed" in trace["events"][0]["content"]
