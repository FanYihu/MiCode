import sys
from types import SimpleNamespace

from micode.agent import (
    LLMConfig,
    LLMError,
    OpenAICompatibleTextClient,
    ProviderCapabilities,
    TextLLM,
    create_llm_from_config,
    load_llm_config,
)


def test_load_llm_config(tmp_path):
    config_path = tmp_path / "config.toml"
    config_path.write_text(
        """
[llm]
provider = "mimo"
model = "mimo-v2.5-pro"
base_url = "https://api.xiaomimimo.com/v1"
api_key = "test-key"
""",
        encoding="utf-8",
    )

    config = load_llm_config(str(config_path))

    assert config == LLMConfig(
        provider="mimo",
        model="mimo-v2.5-pro",
        base_url="https://api.xiaomimimo.com/v1",
        api_key="test-key",
    )


def test_load_llm_config_reads_provider_capabilities(tmp_path):
    config_path = tmp_path / "config.toml"
    config_path.write_text(
        """
[llm]
provider = "mimo"
model = "mimo-v2.5-pro"
base_url = "https://api.xiaomimimo.com/v1"
api_key = "test-key"

[llm.capabilities]
native_tools = true
parallel_tool_calls = false
reasoning_content = true
strict_tool_schema = false
""",
        encoding="utf-8",
    )

    config = load_llm_config(str(config_path))

    assert config.capabilities == ProviderCapabilities(
        native_tools=True,
        parallel_tool_calls=False,
        reasoning_content=True,
        strict_tool_schema=False,
    )


def test_create_llm_from_config_does_not_call_real_client(monkeypatch, tmp_path):
    config_path = tmp_path / "config.toml"
    config_path.write_text(
        """
[llm]
provider = "test"
model = "test-model"
base_url = "https://example.com/v1"
api_key = "test-key"
""",
        encoding="utf-8",
    )

    class DummyClient:
        def __init__(self, config):
            self.config = config

    monkeypatch.setattr("micode.agent.OpenAICompatibleTextClient", DummyClient)

    llm = create_llm_from_config(str(config_path))

    assert isinstance(llm, TextLLM)
    assert isinstance(llm.client, DummyClient)
    assert llm.client.config.model == "test-model"


def test_openai_compatible_client_reads_api_key_from_config(monkeypatch):
    captured = {}

    class DummyOpenAI:
        def __init__(self, api_key, base_url):
            captured["api_key"] = api_key
            captured["base_url"] = base_url
            self.chat = SimpleNamespace(completions=SimpleNamespace(create=lambda **kwargs: None))

    monkeypatch.setitem(sys.modules, "openai", SimpleNamespace(OpenAI=DummyOpenAI))
    client = OpenAICompatibleTextClient(
        LLMConfig(
            provider="mimo",
            model="mimo-v2.5-pro",
            base_url="https://api.xiaomimimo.com/v1",
            api_key="secret-from-config",
        )
    )

    assert client.api_key == "secret-from-config"
    assert captured["api_key"] == "secret-from-config"
    assert captured["base_url"] == "https://api.xiaomimimo.com/v1"


def test_openai_compatible_client_rejects_empty_api_key(monkeypatch):
    monkeypatch.setitem(sys.modules, "openai", SimpleNamespace(OpenAI=object))

    try:
        OpenAICompatibleTextClient(
            LLMConfig(
                provider="mimo",
                model="mimo-v2.5-pro",
                base_url="https://api.xiaomimimo.com/v1",
                api_key="",
            )
        )
    except LLMError as error:
        assert "missing api key" in str(error)
    else:
        raise AssertionError("expected LLMError")


def test_openai_compatible_client_wraps_request_error(monkeypatch):
    class BrokenCompletions:
        def create(self, **kwargs):
            raise RuntimeError("provider unavailable")

    class DummyOpenAI:
        def __init__(self, api_key, base_url):
            self.chat = SimpleNamespace(completions=BrokenCompletions())

    monkeypatch.setitem(sys.modules, "openai", SimpleNamespace(OpenAI=DummyOpenAI))
    client = OpenAICompatibleTextClient(
        LLMConfig(
            provider="mimo",
            model="mimo-v2.5-pro",
            base_url="https://api.xiaomimimo.com/v1",
            api_key="test-key",
        )
    )

    try:
        client.generate("hello")
    except LLMError as error:
        assert "llm request failed" in str(error)
        assert "provider unavailable" in str(error)
    else:
        raise AssertionError("expected LLMError")


def test_openai_compatible_client_parses_native_tool_call(monkeypatch):
    captured = {}
    message = SimpleNamespace(
        content=None,
        tool_calls=[
            SimpleNamespace(
                id="call-123",
                function=SimpleNamespace(
                    name="read_file",
                    arguments='{"path":"README.md"}',
                ),
            )
        ],
    )

    class DummyCompletions:
        def create(self, **kwargs):
            captured.update(kwargs)
            return SimpleNamespace(
                choices=[SimpleNamespace(message=message)]
            )

    class DummyOpenAI:
        def __init__(self, api_key, base_url):
            self.chat = SimpleNamespace(completions=DummyCompletions())

    monkeypatch.setitem(sys.modules, "openai", SimpleNamespace(OpenAI=DummyOpenAI))
    client = OpenAICompatibleTextClient(
        LLMConfig(
            provider="mimo",
            model="mimo-v2.5-pro",
            base_url="https://api.xiaomimimo.com/v1",
            api_key="test-key",
        )
    )
    tools = [
        {
            "type": "function",
            "function": {
                "name": "read_file",
                "description": "Read a file.",
                "parameters": {"type": "object", "properties": {}},
            },
        }
    ]

    action = client.generate_action("read it", tools)

    assert action.tool == "read_file"
    assert action.args == {"path": "README.md"}
    assert action.tool_call_id == "call-123"
    assert captured["tools"] == tools
    assert captured["tool_choice"] == "auto"


def test_openai_complete_returns_normalized_turn_and_assistant_message(monkeypatch):
    message = SimpleNamespace(
        content=None,
        reasoning_content="need inspect file",
        tool_calls=[
            SimpleNamespace(
                id="call-123",
                function=SimpleNamespace(
                    name="read_file",
                    arguments='{"path":"README.md"}',
                ),
            )
        ],
    )

    class DummyOpenAI:
        def __init__(self, api_key, base_url):
            self.chat = SimpleNamespace(
                completions=SimpleNamespace(
                    create=lambda **kwargs: SimpleNamespace(
                        choices=[
                            SimpleNamespace(
                                message=message,
                                finish_reason="tool_calls",
                            )
                        ]
                    )
                )
            )

    monkeypatch.setitem(sys.modules, "openai", SimpleNamespace(OpenAI=DummyOpenAI))
    client = OpenAICompatibleTextClient(
        LLMConfig(
            provider="mimo",
            model="mimo-v2.5-pro",
            base_url="https://api.xiaomimimo.com/v1",
            api_key="test-key",
            capabilities=ProviderCapabilities(reasoning_content=True),
        )
    )

    turn = client.complete(
        [{"role": "user", "content": "read it"}],
        [],
    )

    assert turn.tool_calls[0].name == "read_file"
    assert turn.finish_reason == "tool_calls"
    assert turn.assistant_message["role"] == "assistant"
    assert turn.assistant_message["tool_calls"][0]["id"] == "call-123"
    assert turn.assistant_message["reasoning_content"] == "need inspect file"


def test_openai_client_adds_strict_only_when_capability_enabled(monkeypatch):
    captured = {}
    message = SimpleNamespace(content="done", tool_calls=[])

    class DummyCompletions:
        def create(self, **kwargs):
            captured.update(kwargs)
            return SimpleNamespace(
                choices=[
                    SimpleNamespace(message=message, finish_reason="stop")
                ]
            )

    class DummyOpenAI:
        def __init__(self, api_key, base_url):
            self.chat = SimpleNamespace(completions=DummyCompletions())

    monkeypatch.setitem(sys.modules, "openai", SimpleNamespace(OpenAI=DummyOpenAI))
    client = OpenAICompatibleTextClient(
        LLMConfig(
            provider="test",
            model="test-model",
            base_url="https://example.com/v1",
            api_key="test-key",
            capabilities=ProviderCapabilities(strict_tool_schema=True),
        )
    )
    tools = [
        {
            "type": "function",
            "function": {
                "name": "list_files",
                "description": "List files.",
                "parameters": {"type": "object", "properties": {}},
            },
        }
    ]

    client.complete([{"role": "user", "content": "list"}], tools)

    assert captured["tools"][0]["function"]["strict"] is True


def test_openai_client_requests_parallel_tool_calls_when_enabled(monkeypatch):
    captured = {}
    message = SimpleNamespace(content="done", tool_calls=[])

    class DummyCompletions:
        def create(self, **kwargs):
            captured.update(kwargs)
            return SimpleNamespace(
                choices=[
                    SimpleNamespace(message=message, finish_reason="stop")
                ]
            )

    class DummyOpenAI:
        def __init__(self, api_key, base_url):
            self.chat = SimpleNamespace(completions=DummyCompletions())

    monkeypatch.setitem(sys.modules, "openai", SimpleNamespace(OpenAI=DummyOpenAI))
    client = OpenAICompatibleTextClient(
        LLMConfig(
            provider="test",
            model="test-model",
            base_url="https://example.com/v1",
            api_key="test-key",
            capabilities=ProviderCapabilities(parallel_tool_calls=True),
        )
    )

    client.complete(
        [{"role": "user", "content": "inspect"}],
        [
            {
                "type": "function",
                "function": {
                    "name": "list_files",
                    "description": "List files.",
                    "parameters": {"type": "object", "properties": {}},
                },
            }
        ],
    )

    assert captured["parallel_tool_calls"] is True


def test_openai_compatible_client_uses_content_as_final_answer(monkeypatch):
    message = SimpleNamespace(content="任务完成", tool_calls=[])

    class DummyOpenAI:
        def __init__(self, api_key, base_url):
            self.chat = SimpleNamespace(
                completions=SimpleNamespace(
                    create=lambda **kwargs: SimpleNamespace(
                        choices=[SimpleNamespace(message=message)]
                    )
                )
            )

    monkeypatch.setitem(sys.modules, "openai", SimpleNamespace(OpenAI=DummyOpenAI))
    client = OpenAICompatibleTextClient(
        LLMConfig(
            provider="mimo",
            model="mimo-v2.5-pro",
            base_url="https://api.xiaomimimo.com/v1",
            api_key="test-key",
        )
    )

    action = client.generate_action("finish", [])

    assert action.final is True
    assert action.args == {"answer": "任务完成"}


def test_openai_compatible_client_rejects_multiple_tool_calls(monkeypatch):
    calls = [
        SimpleNamespace(
            id="call-1",
            function=SimpleNamespace(name="list_files", arguments="{}"),
        ),
        SimpleNamespace(
            id="call-2",
            function=SimpleNamespace(name="git_status", arguments="{}"),
        ),
    ]
    message = SimpleNamespace(content=None, tool_calls=calls)

    class DummyOpenAI:
        def __init__(self, api_key, base_url):
            self.chat = SimpleNamespace(
                completions=SimpleNamespace(
                    create=lambda **kwargs: SimpleNamespace(
                        choices=[SimpleNamespace(message=message)]
                    )
                )
            )

    monkeypatch.setitem(sys.modules, "openai", SimpleNamespace(OpenAI=DummyOpenAI))
    client = OpenAICompatibleTextClient(
        LLMConfig(
            provider="mimo",
            model="mimo-v2.5-pro",
            base_url="https://api.xiaomimimo.com/v1",
            api_key="test-key",
        )
    )

    try:
        client.generate_action("inspect", [])
    except Exception as error:
        assert "multiple native tool calls" in str(error)
    else:
        raise AssertionError("expected multiple tool call error")
