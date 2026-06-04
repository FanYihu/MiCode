import pytest

from minicode.agent import InvalidActionText, TextLLM


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
