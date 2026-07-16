from __future__ import annotations

import json
import os
import queue
import shutil
import subprocess
import threading
from pathlib import Path
from typing import Any, Dict, List, Optional

from micode.mcp.config import MCPServerConfig


class MCPError(RuntimeError):
    """MCP 客户端基础异常。"""


class MCPTimeoutError(MCPError):
    """MCP 请求在配置时间内没有返回。"""


class MCPProcessExited(MCPError):
    """MCP Server 在请求期间退出。"""


class MCPPayloadTooLarge(MCPError):
    """MCP 请求或响应超过 payload 上限。"""


class MCPProtocolError(MCPError):
    """MCP Server 返回无效 JSON-RPC 消息。"""


class StdioMCPClient:
    """带超时、重连和 payload 边界的同步 stdio JSON-RPC 客户端。"""

    def __init__(self, config: MCPServerConfig, workspace_root: str) -> None:
        self.config = config
        self.workspace_root = Path(workspace_root).resolve()
        self.process: Optional[subprocess.Popen] = None
        self.protocol = ""
        self.server_capabilities: Dict[str, Any] = {}
        self.server_info: Dict[str, Any] = {}
        self.stderr_lines: List[str] = []
        self._next_id = 1
        self._pending: Dict[int, queue.Queue] = {}
        self._pending_lock = threading.RLock()
        self._write_lock = threading.RLock()
        self._start_lock = threading.RLock()
        self._reader_thread: Optional[threading.Thread] = None
        self._stderr_thread: Optional[threading.Thread] = None
        self._started = False
        self._closing = False
        self._tools_cache = None
        self._resources_cache = None
        self._prompts_cache = None

    @property
    def is_started(self) -> bool:
        return bool(self._started and self._is_alive())

    @property
    def pending_count(self) -> int:
        with self._pending_lock:
            return len(self._pending)

    def start(self) -> None:
        """惰性启动并完成 initialize；已启动时是幂等操作。"""
        with self._start_lock:
            if self.is_started:
                return
            self.close()
            last_error = None
            candidates = (
                [self.config.protocol]
                if self.config.protocol != "auto"
                else ["newline-json", "content-length"]
            )
            for protocol in candidates:
                try:
                    self._spawn(protocol)
                    initialized = self._request_without_start(
                        "initialize",
                        {
                            "protocolVersion": "2024-11-05",
                            "capabilities": {},
                            "clientInfo": {"name": "micode", "version": "0.1.0"},
                        },
                        timeout_seconds=self.config.startup_timeout_seconds,
                    )
                    if not isinstance(initialized, dict):
                        raise MCPProtocolError("initialize result must be an object")
                    self.server_capabilities = dict(initialized.get("capabilities", {}))
                    self.server_info = dict(initialized.get("serverInfo", {}))
                    self.notify("notifications/initialized", {})
                    self._started = True
                    return
                except Exception as error:
                    last_error = error
                    self.close()
            raise MCPError(
                f'MCP server "{self.config.name}" failed to initialize: {last_error}'
            )

    def request(
        self,
        method: str,
        params: Optional[dict] = None,
        timeout_seconds: Optional[float] = None,
    ) -> Any:
        self._ensure_started()
        return self._request_without_start(method, params or {}, timeout_seconds)

    def notify(self, method: str, params: Optional[dict] = None) -> None:
        message = {"jsonrpc": "2.0", "method": method, "params": params or {}}
        self._write_message(message)

    def list_tools(self, refresh: bool = False) -> List[dict]:
        if self._tools_cache is None or refresh:
            self._tools_cache = self._list_paginated("tools/list", "tools")
        return list(self._tools_cache)

    def list_resources(self, refresh: bool = False) -> List[dict]:
        if self._resources_cache is None or refresh:
            self._resources_cache = self._list_paginated("resources/list", "resources")
        return list(self._resources_cache)

    def list_prompts(self, refresh: bool = False) -> List[dict]:
        if self._prompts_cache is None or refresh:
            self._prompts_cache = self._list_paginated("prompts/list", "prompts")
        return list(self._prompts_cache)

    def call_tool(self, name: str, arguments: dict) -> Any:
        return self.request("tools/call", {"name": name, "arguments": arguments})

    def read_resource(self, uri: str) -> Any:
        return self.request("resources/read", {"uri": uri})

    def get_prompt(self, name: str, arguments: Optional[dict] = None) -> Any:
        return self.request(
            "prompts/get",
            {"name": name, "arguments": arguments or {}},
        )

    def close(self) -> None:
        """终止子进程并让所有 pending request 立即失败。"""
        process = self.process
        self._closing = True
        self._started = False
        if process is not None and process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=1.0)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=1.0)
        self._fail_pending(MCPProcessExited("MCP client closed"))
        current = threading.current_thread()
        for thread in (self._reader_thread, self._stderr_thread):
            if thread is not None and thread is not current and thread.is_alive():
                thread.join(timeout=0.5)
        self.process = None
        self._reader_thread = None
        self._stderr_thread = None
        self._closing = False

    def _ensure_started(self) -> None:
        if self._started and not self._is_alive():
            self.close()
        if not self._started:
            self.start()

    def _spawn(self, protocol: str) -> None:
        command = self._resolve_command(self.config.command)
        cwd = self._resolve_cwd(self.config.cwd)
        env = os.environ.copy()
        env.update(self.config.env)
        self.protocol = protocol
        self._closing = False
        self._tools_cache = None
        self._resources_cache = None
        self._prompts_cache = None
        try:
            self.process = subprocess.Popen(
                [command, *self.config.args],
                cwd=str(cwd),
                env=env,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                bufsize=0,
            )
        except OSError as error:
            raise MCPError(f"failed to start MCP command: {error}") from error
        self.stderr_lines = []
        self._reader_thread = threading.Thread(
            target=self._reader_loop,
            args=(self.process,),
            name=f"micode-mcp-{self.config.name}-stdout",
            daemon=True,
        )
        self._stderr_thread = threading.Thread(
            target=self._stderr_loop,
            args=(self.process,),
            name=f"micode-mcp-{self.config.name}-stderr",
            daemon=True,
        )
        self._reader_thread.start()
        self._stderr_thread.start()

    def _request_without_start(
        self,
        method: str,
        params: dict,
        timeout_seconds: Optional[float],
    ) -> Any:
        timeout = (
            self.config.request_timeout_seconds
            if timeout_seconds is None
            else float(timeout_seconds)
        )
        with self._pending_lock:
            request_id = self._next_id
            self._next_id += 1
            response_queue = queue.Queue(maxsize=1)
            self._pending[request_id] = response_queue
        try:
            self._write_message(
                {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "method": method,
                    "params": params,
                }
            )
            try:
                response = response_queue.get(timeout=timeout)
            except queue.Empty as error:
                raise MCPTimeoutError(
                    f'MCP request timed out: server={self.config.name} method={method}'
                ) from error
            if isinstance(response, Exception):
                raise response
            if not isinstance(response, dict):
                raise MCPProtocolError("JSON-RPC response must be an object")
            if "error" in response:
                raise MCPError(f"MCP JSON-RPC error: {response['error']}")
            if "result" not in response:
                raise MCPProtocolError("JSON-RPC response has no result")
            return response["result"]
        finally:
            with self._pending_lock:
                self._pending.pop(request_id, None)

    def _write_message(self, message: dict) -> None:
        process = self.process
        if process is None or process.stdin is None or process.poll() is not None:
            raise MCPProcessExited(
                f'MCP process exited: server={self.config.name}'
            )
        body = json.dumps(
            message,
            ensure_ascii=False,
            separators=(",", ":"),
        ).encode("utf-8")
        if len(body) > self.config.max_payload_bytes:
            raise MCPPayloadTooLarge(
                f"MCP request payload exceeds {self.config.max_payload_bytes} bytes"
            )
        if self.protocol == "content-length":
            payload = f"Content-Length: {len(body)}\r\n\r\n".encode("ascii") + body
        else:
            payload = body + b"\n"
        with self._write_lock:
            try:
                process.stdin.write(payload)
                process.stdin.flush()
            except (BrokenPipeError, OSError) as error:
                raise MCPProcessExited(
                    f'MCP process exited while writing: server={self.config.name}'
                ) from error

    def _reader_loop(self, process: subprocess.Popen) -> None:
        try:
            while process.poll() is None:
                message = self._read_message(process)
                if message is None:
                    break
                response_id = message.get("id") if isinstance(message, dict) else None
                if response_id is None:
                    continue
                with self._pending_lock:
                    response_queue = self._pending.get(response_id)
                if response_queue is not None:
                    response_queue.put(message)
        except Exception as error:
            self._fail_pending(error if isinstance(error, MCPError) else MCPProtocolError(str(error)))
        finally:
            if not self._closing:
                self._started = False
                code = process.poll()
                self._fail_pending(
                    MCPProcessExited(
                        f'MCP process exited: server={self.config.name} code={code}'
                    )
                )

    def _read_message(self, process: subprocess.Popen) -> Optional[dict]:
        if process.stdout is None:
            raise MCPProcessExited("MCP stdout is unavailable")
        if self.protocol == "content-length":
            body = self._read_content_length_body(process.stdout)
        else:
            body = process.stdout.readline(self.config.max_payload_bytes + 1)
            if not body:
                return None
            if len(body) > self.config.max_payload_bytes:
                raise MCPPayloadTooLarge(
                    f"MCP response payload exceeds {self.config.max_payload_bytes} bytes"
                )
        try:
            message = json.loads(body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise MCPProtocolError(f"invalid MCP JSON response: {error}") from error
        if not isinstance(message, dict) or message.get("jsonrpc") != "2.0":
            raise MCPProtocolError("invalid JSON-RPC envelope")
        return message

    def _read_content_length_body(self, stream) -> bytes:
        headers = {}
        header_bytes = 0
        while True:
            line = stream.readline(8193)
            if not line:
                raise MCPProcessExited("MCP process exited while reading headers")
            header_bytes += len(line)
            if header_bytes > 8192:
                raise MCPProtocolError("MCP headers exceed 8192 bytes")
            if line in {b"\r\n", b"\n"}:
                break
            try:
                key, value = line.decode("ascii").split(":", 1)
            except (UnicodeDecodeError, ValueError) as error:
                raise MCPProtocolError("invalid MCP content-length header") from error
            headers[key.strip().lower()] = value.strip()
        try:
            content_length = int(headers["content-length"])
        except (KeyError, ValueError) as error:
            raise MCPProtocolError("missing MCP Content-Length header") from error
        if content_length > self.config.max_payload_bytes:
            raise MCPPayloadTooLarge(
                f"MCP response payload exceeds {self.config.max_payload_bytes} bytes"
            )
        body = stream.read(content_length)
        if len(body) != content_length:
            raise MCPProcessExited("MCP process exited during response body")
        return body

    def _stderr_loop(self, process: subprocess.Popen) -> None:
        if process.stderr is None:
            return
        for raw_line in iter(process.stderr.readline, b""):
            line = raw_line.decode("utf-8", errors="replace").strip()
            if line:
                self.stderr_lines.append(line)
                self.stderr_lines = self.stderr_lines[-20:]

    def _list_paginated(self, method: str, key: str) -> List[dict]:
        items = []
        cursor = ""
        for _ in range(100):
            params = {"cursor": cursor} if cursor else {}
            result = self.request(method, params)
            if not isinstance(result, dict) or not isinstance(result.get(key, []), list):
                raise MCPProtocolError(f"{method} returned invalid {key}")
            items.extend(item for item in result.get(key, []) if isinstance(item, dict))
            cursor = str(result.get("nextCursor") or "")
            if not cursor:
                return items
        raise MCPProtocolError(f"{method} exceeded pagination limit")

    def _resolve_command(self, command: str) -> str:
        dangerous = {"sh", "bash", "zsh", "fish", "cmd", "cmd.exe", "powershell", "pwsh"}
        if Path(command).name.lower() in dangerous:
            raise MCPError("MCP server command cannot be a general-purpose shell")
        if Path(command).is_absolute():
            if not Path(command).is_file():
                raise MCPError(f"MCP command does not exist: {command}")
            return command
        resolved = shutil.which(command)
        if not resolved:
            raise MCPError(f"MCP command not found: {command}")
        return resolved

    def _resolve_cwd(self, configured: str) -> Path:
        candidate = (
            (self.workspace_root / configured).resolve()
            if configured
            else self.workspace_root
        )
        try:
            candidate.relative_to(self.workspace_root)
        except ValueError as error:
            raise MCPError("MCP cwd must stay inside the workspace") from error
        if not candidate.is_dir():
            raise MCPError(f"MCP cwd does not exist: {candidate}")
        return candidate

    def _is_alive(self) -> bool:
        return self.process is not None and self.process.poll() is None

    def _fail_pending(self, error: Exception) -> None:
        with self._pending_lock:
            queues = list(self._pending.values())
        for response_queue in queues:
            try:
                response_queue.put_nowait(error)
            except queue.Full:
                continue
