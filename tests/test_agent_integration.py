from minicode.agent import AgentAction, InvalidActionText, LLMError, MiniCodeAgent
from minicode.models import EventType, RunStatus, StepType
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
