import pytest

from micode.agent import AgentAction, InvalidActionText, TextLLM


class FakeTextClient:
    def __init__(self, responses):
        self.responses = responses
        self.prompts = []
        self.index = 0

    def generate(self, prompt):
        self.prompts.append(prompt)
        response = self.responses[self.index]
        self.index += 1
        return response


def test_text_llm_parses_client_response():
    client = FakeTextClient(['{"tool":"list_files","args":{},"final":false}'])
    llm = TextLLM(client)

    action = llm.next_action("列出文件", [])

    assert action.tool == "list_files"
    assert "列出文件" in client.prompts[0]


def test_text_llm_includes_observations_in_prompt():
    client = FakeTextClient(['{"tool":"","args":{"answer":"完成"},"final":true}'])
    llm = TextLLM(client)

    llm.next_action("总结", ["README 内容"])

    assert "README 内容" in client.prompts[0]


def test_text_llm_uses_injected_tool_descriptions():
    client = FakeTextClient(['{"tool":"echo","args":{"text":"hi"},"final":false}'])
    llm = TextLLM(client)

    llm.set_tool_descriptions(["- echo: echo text, args={\"text\": \"...\"}"])
    llm.next_action("回显", [])

    assert "echo: echo text" in client.prompts[0]
    assert "list_files" not in client.prompts[0]


def test_text_llm_raises_for_invalid_json():
    client = FakeTextClient(["not json"])
    llm = TextLLM(client)

    with pytest.raises(InvalidActionText):
        llm.next_action("坏输出", [])


def test_text_llm_prefers_native_generate_action():
    class NativeClient:
        def __init__(self):
            self.calls = []

        def generate_action(self, prompt, tools):
            self.calls.append((prompt, tools))
            return AgentAction(
                tool="read_file",
                args={"path": "README.md"},
                tool_call_id="call-1",
            )

    client = NativeClient()
    llm = TextLLM(client)
    llm.set_tool_definitions([{"type": "function", "function": {"name": "read_file"}}])

    action = llm.next_action("读取文件", [])

    assert action.tool == "read_file"
    assert action.tool_call_id == "call-1"
    assert client.calls[0][1][0]["function"]["name"] == "read_file"
    assert "Use the provided function tools" in client.calls[0][0]
    assert "Return exactly one JSON object" not in client.calls[0][0]


def test_text_llm_keeps_native_assistant_and_tool_messages():
    from micode.agent import ModelToolCall, ModelTurn

    class CompleteClient:
        def __init__(self):
            self.requests = []
            self.turns = [
                ModelTurn(
                    tool_calls=[
                        ModelToolCall(
                            id="call-1",
                            name="read_file",
                            arguments={"path": "README.md"},
                            raw_arguments='{"path":"README.md"}',
                        )
                    ],
                    assistant_message={
                        "role": "assistant",
                        "content": None,
                        "tool_calls": [
                            {
                                "id": "call-1",
                                "type": "function",
                                "function": {
                                    "name": "read_file",
                                    "arguments": '{"path":"README.md"}',
                                },
                            }
                        ],
                    },
                ),
                ModelTurn(
                    text="完成",
                    assistant_message={
                        "role": "assistant",
                        "content": "完成",
                    },
                ),
            ]

        def complete(self, messages, tools):
            self.requests.append([dict(message) for message in messages])
            return self.turns.pop(0)

    client = CompleteClient()
    llm = TextLLM(client)

    action = llm.next_action("读取 README", [])
    llm.record_tool_result(action, "hello")
    final = llm.next_action("读取 README", ["hello"])

    second_messages = client.requests[1]
    assert second_messages[1]["role"] == "assistant"
    assert second_messages[1]["tool_calls"][0]["id"] == "call-1"
    assert second_messages[2] == {
        "role": "tool",
        "tool_call_id": "call-1",
        "name": "read_file",
        "content": "hello",
    }
    assert final.final is True
    assert final.args["answer"] == "完成"


def test_text_llm_falls_back_when_native_tools_are_disabled():
    from micode.agent import ProviderCapabilities

    class CompatibleClient:
        capabilities = ProviderCapabilities(native_tools=False)

        def complete(self, messages, tools):
            raise AssertionError("complete should not be used")

        def generate(self, prompt):
            return '{"tool":"list_files","args":{},"final":false}'

    llm = TextLLM(CompatibleClient())

    action = llm.next_action("列出文件", [])

    assert action.tool == "list_files"


def test_text_llm_next_turn_returns_multiple_native_tool_calls():
    from micode.agent import ModelToolCall, ModelTurn

    class CompleteClient:
        def complete(self, messages, tools):
            return ModelTurn(
                tool_calls=[
                    ModelToolCall(
                        id="call-1",
                        name="read_file",
                        arguments={"path": "README.md"},
                    ),
                    ModelToolCall(
                        id="call-2",
                        name="git_status",
                        arguments={},
                    ),
                ],
                assistant_message={
                    "role": "assistant",
                    "content": None,
                    "tool_calls": [],
                },
            )

    turn = TextLLM(CompleteClient()).next_turn("检查项目", [])

    assert [action.tool for action in turn.actions] == [
        "read_file",
        "git_status",
    ]
    assert [action.tool_call_id for action in turn.actions] == [
        "call-1",
        "call-2",
    ]
