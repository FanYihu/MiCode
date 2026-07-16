from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Tuple

import tomli as tomllib


DEFAULT_MAX_PAYLOAD_BYTES = 4 * 1024 * 1024


@dataclass(frozen=True)
class MCPServerConfig:
    """一个 stdio MCP Server 的本地启动配置。"""

    name: str
    command: str
    args: Tuple[str, ...] = ()
    cwd: str = ""
    env: Dict[str, str] = field(default_factory=dict)
    protocol: str = "auto"
    request_timeout_seconds: float = 10.0
    startup_timeout_seconds: float = 3.0
    max_payload_bytes: int = DEFAULT_MAX_PAYLOAD_BYTES
    enabled: bool = True


def load_mcp_server_configs(path: str = "config.toml") -> Dict[str, MCPServerConfig]:
    """从现有 config.toml 的 `[mcp.servers.*]` 读取 MCP 配置。"""
    config_path = Path(path)
    if not config_path.exists():
        return {}
    with config_path.open("rb") as handle:
        data = tomllib.load(handle)
    mcp_data = data.get("mcp", {})
    if not isinstance(mcp_data, dict) or mcp_data.get("enabled", True) is False:
        return {}
    raw_servers = mcp_data.get("servers", {})
    if not isinstance(raw_servers, dict):
        raise ValueError("mcp.servers must be a table")

    servers = {}
    for name, raw in raw_servers.items():
        if not isinstance(raw, dict):
            raise ValueError(f"mcp.servers.{name} must be a table")
        enabled = bool(raw.get("enabled", True))
        if not enabled:
            continue
        command = str(raw.get("command") or "").strip()
        if not command:
            raise ValueError(f"mcp.servers.{name}.command is required")
        protocol = str(raw.get("protocol") or "auto")
        if protocol not in {"auto", "newline-json", "content-length"}:
            raise ValueError(f"unsupported MCP protocol for {name}: {protocol}")
        max_payload = int(raw.get("max_payload_bytes", DEFAULT_MAX_PAYLOAD_BYTES))
        if max_payload < 1024:
            raise ValueError(f"mcp.servers.{name}.max_payload_bytes is too small")
        args = raw.get("args", [])
        env = raw.get("env", {})
        if not isinstance(args, list) or not all(isinstance(item, str) for item in args):
            raise ValueError(f"mcp.servers.{name}.args must be an array of strings")
        if not isinstance(env, dict):
            raise ValueError(f"mcp.servers.{name}.env must be a table")
        servers[str(name)] = MCPServerConfig(
            name=str(name),
            command=command,
            args=tuple(args),
            cwd=str(raw.get("cwd") or ""),
            env={str(key): str(value) for key, value in env.items()},
            protocol=protocol,
            request_timeout_seconds=float(raw.get("request_timeout_seconds", 10.0)),
            startup_timeout_seconds=float(raw.get("startup_timeout_seconds", 3.0)),
            max_payload_bytes=max_payload,
            enabled=enabled,
        )
    return servers
