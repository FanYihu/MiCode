import sys
from pathlib import Path

import pytest

from micode.cli import run_mcp_inspect
from micode.human_review import APPROVED, HumanReviewStore
from micode.mcp.client import (
    MCPPayloadTooLarge,
    MCPProcessExited,
    MCPTimeoutError,
    StdioMCPClient,
)
from micode.mcp.config import MCPServerConfig, load_mcp_server_configs
from micode.tools.default import create_default_tool_registry
from micode.workspace import Workspace


def _server_script() -> Path:
    return Path(__file__).parent / "fixtures" / "mock_mcp_server.py"


def _config(mode="normal", **overrides) -> MCPServerConfig:
    values = {
        "name": "mock",
        "command": sys.executable,
        "args": (str(_server_script()),),
        "env": {"MOCK_MCP_MODE": mode},
        "protocol": "newline-json",
        "request_timeout_seconds": 1.0,
        "startup_timeout_seconds": 1.0,
        "max_payload_bytes": 1024 * 1024,
    }
    values.update(overrides)
    return MCPServerConfig(**values)


def test_load_mcp_server_configs_from_main_toml(tmp_path):
    path = tmp_path / "config.toml"
    path.write_text(
        """
[llm]
provider = "test"
model = "test"
base_url = "http://localhost"
api_key = "test"

[mcp.servers.mock]
command = "python3"
args = ["server.py"]
protocol = "newline-json"
request_timeout_seconds = 2

[mcp.servers.disabled]
enabled = false
command = "python3"
""".strip(),
        encoding="utf-8",
    )

    configs = load_mcp_server_configs(str(path))

    assert list(configs) == ["mock"]
    assert configs["mock"].args == ("server.py",)
    assert configs["mock"].request_timeout_seconds == 2.0


def test_registry_discovers_and_calls_mcp_tools(tmp_path):
    review_store = HumanReviewStore(str(tmp_path / "reviews"))
    registry = create_default_tool_registry(
        Workspace(str(tmp_path)),
        mcp_server_configs={"mock": _config()},
        human_review_store=review_store,
    )

    assert "mcp__mock__echo" in registry.list_names()
    assert "read_mcp_resource" in registry.list_names()
    result = registry.call("mcp__mock__echo", {"text": "hi"})

    assert result.ok is True
    assert result.output == "echo:hi"
    assert result.trust_level == "untrusted"
    assert result.source == "mcp:mock:tool:echo"
    assert result.metadata["details"]["mcp_method"] == "tools/call"

    blocked = registry.call("mcp__mock__mutate", {"value": "x"})
    assert blocked.ok is False
    assert blocked.metadata["error"] == "human_review_required"
    review_id = blocked.metadata["details"]["review_id"]
    review_store.decide(review_id, APPROVED)
    resumed = registry.resume(review_id)
    assert resumed.ok is True
    assert resumed.output == "mutated:x"
    registry.close()


def test_mcp_resource_prompt_and_lifecycle(tmp_path):
    registry = create_default_tool_registry(
        Workspace(str(tmp_path)),
        mcp_server_configs={"mock": _config()},
    )
    manager = registry.mcp_manager
    client = manager.get_client("mock")

    resources = registry.call("list_mcp_resources", {"server": "mock"})
    resource = registry.call(
        "read_mcp_resource",
        {"server": "mock", "uri": "mock://hello"},
    )
    prompts = registry.call("list_mcp_prompts", {"server": "mock"})
    prompt = registry.call(
        "get_mcp_prompt",
        {"server": "mock", "name": "hello", "arguments": {"name": "cc"}},
    )

    assert "mock://hello" in resources.output
    assert "hello resource" in resource.output
    assert "Greeting prompt" in prompts.output
    assert "hello cc" in prompt.output
    process = client.process
    assert process is not None and process.poll() is None
    registry.close()
    assert process.poll() is not None
    registry.close()


def test_mcp_supports_content_length_framing(tmp_path):
    client = StdioMCPClient(_config(protocol="content-length"), str(tmp_path))

    result = client.call_tool("echo", {"text": "framed"})

    assert result["content"][0]["text"] == "echo:framed"
    client.close()


def test_mcp_request_timeout_cleans_pending(tmp_path):
    client = StdioMCPClient(
        _config(mode="hang_on_call", request_timeout_seconds=0.1),
        str(tmp_path),
    )
    client.start()

    with pytest.raises(MCPTimeoutError):
        client.call_tool("echo", {"text": "hi"})

    assert client.pending_count == 0
    client.close()


def test_mcp_process_exit_cleans_pending(tmp_path):
    client = StdioMCPClient(_config(mode="exit_on_call"), str(tmp_path))
    client.start()

    with pytest.raises(MCPProcessExited):
        client.call_tool("echo", {"text": "hi"})

    assert client.pending_count == 0
    client.close()


def test_mcp_reconnects_after_process_was_killed(tmp_path):
    client = StdioMCPClient(_config(), str(tmp_path))
    client.start()
    first_process = client.process
    assert first_process is not None
    first_process.kill()
    first_process.wait(timeout=2)

    result = client.call_tool("echo", {"text": "again"})

    assert result["content"][0]["text"] == "echo:again"
    assert client.process is not None
    assert client.process.pid != first_process.pid
    client.close()


def test_mcp_rejects_oversized_response(tmp_path):
    client = StdioMCPClient(
        _config(mode="oversized", max_payload_bytes=1024),
        str(tmp_path),
    )
    client.start()

    with pytest.raises(MCPPayloadTooLarge):
        client.call_tool("echo", {"text": "hi"})

    assert client.pending_count == 0
    client.close()


def test_mcp_cwd_cannot_escape_workspace(tmp_path):
    client = StdioMCPClient(_config(cwd=".."), str(tmp_path))

    with pytest.raises(Exception, match="cwd must stay inside"):
        client.start()


def test_mcp_inspect_cli_service_reports_discovery(tmp_path):
    config_path = tmp_path / "config.toml"
    config_path.write_text(
        "\n".join(
            [
                "[mcp.servers.mock]",
                f'command = "{sys.executable}"',
                f'args = ["{_server_script()}"]',
                'protocol = "newline-json"',
            ]
        ),
        encoding="utf-8",
    )

    report = run_mcp_inspect(str(config_path), str(tmp_path))

    assert report["servers"][0]["ok"] is True
    assert report["servers"][0]["server_info"]["name"] == "micode-mock-mcp"
    assert {tool["name"] for tool in report["servers"][0]["tools"]} == {
        "echo",
        "mutate",
    }
