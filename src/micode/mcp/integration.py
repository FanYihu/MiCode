from __future__ import annotations

import json
import re
import threading
from dataclasses import dataclass
from typing import Dict, List, Optional

from micode.mcp.client import MCPError, StdioMCPClient
from micode.mcp.config import MCPServerConfig
from micode.security import TrustLevel
from micode.tools.registry import (
    ToolCapabilities,
    ToolDefinition,
    ToolResult,
)


def _safe_name(value: str) -> str:
    normalized = re.sub(r"[^A-Za-z0-9_-]+", "_", value).strip("_")
    return normalized or "unnamed"


def _object_schema(value) -> dict:
    if isinstance(value, dict) and value.get("type") == "object":
        return value
    return {
        "type": "object",
        "properties": {},
        "additionalProperties": True,
    }


def _render_content_block(block) -> str:
    if isinstance(block, dict) and block.get("type") == "text":
        return str(block.get("text") or "")
    return json.dumps(block, ensure_ascii=False, indent=2)


def _render_tool_result(payload) -> ToolResult:
    if not isinstance(payload, dict):
        return ToolResult(ok=True, output=json.dumps(payload, ensure_ascii=False, indent=2))
    parts = []
    content = payload.get("content")
    if isinstance(content, list):
        parts.extend(_render_content_block(block) for block in content)
    if "structuredContent" in payload:
        parts.append(
            "STRUCTURED_CONTENT:\n"
            + json.dumps(payload["structuredContent"], ensure_ascii=False, indent=2)
        )
    if not parts:
        parts.append(json.dumps(payload, ensure_ascii=False, indent=2))
    return ToolResult(ok=not bool(payload.get("isError")), output="\n\n".join(parts))


def _render_resource_result(payload) -> ToolResult:
    if not isinstance(payload, dict):
        return ToolResult(ok=False, output="Invalid MCP resource response")
    rendered = []
    for item in payload.get("contents", []):
        if not isinstance(item, dict):
            continue
        header = f"URI: {item.get('uri', '')}"
        if item.get("mimeType"):
            header += f"\nMIME: {item['mimeType']}"
        if isinstance(item.get("text"), str):
            body = item["text"]
        elif isinstance(item.get("blob"), str):
            body = "BLOB:\n" + item["blob"]
        else:
            body = json.dumps(item, ensure_ascii=False, indent=2)
        rendered.append(f"{header}\n\n{body}")
    return ToolResult(ok=True, output="\n\n".join(rendered) or "No resource contents returned.")


def _render_prompt_result(payload) -> ToolResult:
    if not isinstance(payload, dict):
        return ToolResult(ok=False, output="Invalid MCP prompt response")
    parts = []
    if payload.get("description"):
        parts.append(f"DESCRIPTION: {payload['description']}")
    for message in payload.get("messages", []):
        if not isinstance(message, dict):
            continue
        content = message.get("content")
        if isinstance(content, list):
            rendered = "\n".join(_render_content_block(item) for item in content)
        elif isinstance(content, dict):
            rendered = _render_content_block(content)
        else:
            rendered = str(content or "")
        parts.append(f"[{message.get('role', 'unknown')}]\n{rendered}")
    return ToolResult(ok=True, output="\n\n".join(parts))


class MCPManager:
    """持有多个 MCP 客户端，统一发现、检查和关闭生命周期。"""

    def __init__(self, configs: Dict[str, MCPServerConfig], workspace_root: str) -> None:
        self.configs = dict(configs)
        self.workspace_root = workspace_root
        self.clients: Dict[str, StdioMCPClient] = {}
        self.discovery_errors: Dict[str, str] = {}
        self._lock = threading.RLock()
        self._closed = False

    def get_client(self, server_name: str) -> StdioMCPClient:
        with self._lock:
            if self._closed:
                raise MCPError("MCP manager is closed")
            if server_name not in self.configs:
                raise MCPError(f"unknown MCP server: {server_name}")
            if server_name not in self.clients:
                self.clients[server_name] = StdioMCPClient(
                    self.configs[server_name],
                    self.workspace_root,
                )
            return self.clients[server_name]

    def close(self) -> None:
        with self._lock:
            if self._closed:
                return
            self._closed = True
            clients = list(self.clients.values())
        for client in reversed(clients):
            client.close()

    def inspect(self) -> dict:
        servers = []
        for server_name in self.configs:
            client = self.get_client(server_name)
            record = {"name": server_name, "ok": True}
            try:
                discovered_tools = client.list_tools()
                record.update(
                    {
                        "server_info": client.server_info,
                        "tools": discovered_tools,
                        "resources": client.list_resources(),
                        "prompts": client.list_prompts(),
                    }
                )
            except Exception as error:
                record.update({"ok": False, "error": f"{type(error).__name__}: {error}"})
            servers.append(record)
        return {
            "servers": servers,
            "discovery_errors": dict(self.discovery_errors),
        }


@dataclass
class MCPToolBundle:
    tools: List[ToolDefinition]
    manager: MCPManager


def create_mcp_tool_bundle(
    configs: Dict[str, MCPServerConfig],
    workspace_root: str,
    manager: Optional[MCPManager] = None,
) -> MCPToolBundle:
    """发现远端 Tool，并连同标准 Resource/Prompt 工具适配到 Registry。"""
    actual_manager = manager or MCPManager(configs, workspace_root)
    tools: List[ToolDefinition] = []
    for server_name in configs:
        client = actual_manager.get_client(server_name)
        try:
            remote_tools = client.list_tools()
        except Exception as error:
            actual_manager.discovery_errors[server_name] = f"{type(error).__name__}: {error}"
            continue
        for remote in remote_tools:
            remote_name = str(remote.get("name") or "")
            if not remote_name:
                continue
            annotations = remote.get("annotations", {})
            read_only = bool(
                isinstance(annotations, dict)
                and annotations.get("readOnlyHint", False)
            )
            local_name = f"mcp__{_safe_name(server_name)}__{_safe_name(remote_name)}"
            tools.append(
                ToolDefinition(
                    name=local_name,
                    description=(
                        f"MCP {server_name}/{remote_name}: "
                        + str(remote.get("description") or "Remote MCP tool.")
                    ),
                    parameters=_object_schema(remote.get("inputSchema")),
                    parallel_safe=read_only,
                    capabilities=ToolCapabilities(
                        read_only=read_only,
                        external_io=True,
                        requires_review=not read_only,
                    ),
                    output_trust=TrustLevel.UNTRUSTED.value,
                    source=f"mcp:{server_name}:tool:{remote_name}",
                    handler=_mcp_tool_handler(
                        actual_manager,
                        server_name,
                        remote_name,
                    ),
                )
            )

    if configs:
        tools.extend(_standard_mcp_tools(actual_manager))
    return MCPToolBundle(tools=tools, manager=actual_manager)


def _mcp_tool_handler(manager: MCPManager, server_name: str, remote_name: str):
    def handler(args: dict) -> ToolResult:
        payload = manager.get_client(server_name).call_tool(remote_name, args)
        result = _render_tool_result(payload)
        result.source = f"mcp:{server_name}:tool:{remote_name}"
        result.trust_level = TrustLevel.UNTRUSTED.value
        result.metadata.update(
            {
                "mcp_server": server_name,
                "mcp_tool": remote_name,
                "mcp_method": "tools/call",
            }
        )
        return result

    return handler


def _standard_mcp_tools(manager: MCPManager) -> List[ToolDefinition]:
    common = ToolCapabilities(read_only=True, external_io=True)
    return [
        ToolDefinition(
            name="list_mcp_resources",
            description="List resources exposed by configured MCP servers.",
            parameters=_server_schema(),
            parallel_safe=True,
            capabilities=common,
            output_trust=TrustLevel.UNTRUSTED.value,
            source="mcp:resources",
            handler=lambda args: _list_resources(manager, args),
        ),
        ToolDefinition(
            name="read_mcp_resource",
            description="Read one MCP resource by server and URI.",
            parameters={
                "type": "object",
                "properties": {
                    "server": {"type": "string"},
                    "uri": {"type": "string"},
                },
                "required": ["server", "uri"],
                "additionalProperties": False,
            },
            parallel_safe=True,
            capabilities=common,
            output_trust=TrustLevel.UNTRUSTED.value,
            source="mcp:resource",
            handler=lambda args: _read_resource(manager, args),
        ),
        ToolDefinition(
            name="list_mcp_prompts",
            description="List prompts exposed by configured MCP servers.",
            parameters=_server_schema(),
            parallel_safe=True,
            capabilities=common,
            output_trust=TrustLevel.UNTRUSTED.value,
            source="mcp:prompts",
            handler=lambda args: _list_prompts(manager, args),
        ),
        ToolDefinition(
            name="get_mcp_prompt",
            description="Render one MCP prompt by server and name.",
            parameters={
                "type": "object",
                "properties": {
                    "server": {"type": "string"},
                    "name": {"type": "string"},
                    "arguments": {"type": "object"},
                },
                "required": ["server", "name"],
                "additionalProperties": False,
            },
            parallel_safe=True,
            capabilities=common,
            output_trust=TrustLevel.UNTRUSTED.value,
            source="mcp:prompt",
            handler=lambda args: _get_prompt(manager, args),
        ),
    ]


def _server_schema() -> dict:
    return {
        "type": "object",
        "properties": {"server": {"type": "string"}},
        "required": [],
        "additionalProperties": False,
    }


def _selected_servers(manager: MCPManager, args: dict) -> List[str]:
    requested = str(args.get("server") or "")
    if requested:
        if requested not in manager.configs:
            raise MCPError(f"unknown MCP server: {requested}")
        return [requested]
    return list(manager.configs)


def _list_resources(manager: MCPManager, args: dict) -> ToolResult:
    records = []
    for server in _selected_servers(manager, args):
        for resource in manager.get_client(server).list_resources():
            records.append({"server": server, **resource})
    return ToolResult(
        ok=True,
        output=json.dumps(records, ensure_ascii=False, indent=2),
        metadata={"mcp_method": "resources/list", "resource_count": len(records)},
        trust_level=TrustLevel.UNTRUSTED.value,
        source="mcp:resources",
    )


def _read_resource(manager: MCPManager, args: dict) -> ToolResult:
    server = str(args["server"])
    result = _render_resource_result(
        manager.get_client(server).read_resource(str(args["uri"]))
    )
    result.trust_level = TrustLevel.UNTRUSTED.value
    result.source = f"mcp:{server}:resource:{args['uri']}"
    result.metadata.update({"mcp_server": server, "mcp_method": "resources/read"})
    return result


def _list_prompts(manager: MCPManager, args: dict) -> ToolResult:
    records = []
    for server in _selected_servers(manager, args):
        for prompt in manager.get_client(server).list_prompts():
            records.append({"server": server, **prompt})
    return ToolResult(
        ok=True,
        output=json.dumps(records, ensure_ascii=False, indent=2),
        metadata={"mcp_method": "prompts/list", "prompt_count": len(records)},
        trust_level=TrustLevel.UNTRUSTED.value,
        source="mcp:prompts",
    )


def _get_prompt(manager: MCPManager, args: dict) -> ToolResult:
    server = str(args["server"])
    result = _render_prompt_result(
        manager.get_client(server).get_prompt(
            str(args["name"]),
            args.get("arguments", {}),
        )
    )
    result.trust_level = TrustLevel.UNTRUSTED.value
    result.source = f"mcp:{server}:prompt:{args['name']}"
    result.metadata.update({"mcp_server": server, "mcp_method": "prompts/get"})
    return result
