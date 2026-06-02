import sys
from types import SimpleNamespace

from minicode.agent import (
    LLMConfig,
    LLMError,
    OpenAICompatibleTextClient,
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

    monkeypatch.setattr("minicode.agent.OpenAICompatibleTextClient", DummyClient)

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
