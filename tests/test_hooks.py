from micode.hooks import HookContext, HookEvent, HookManager, HookResult
from micode.tools.default import create_default_tool_registry
from micode.tools.registry import ToolDefinition, ToolRegistry, ToolResult
from micode.workspace import Workspace


def test_before_hooks_run_by_priority_and_can_rewrite_args():
    manager = HookManager()
    order = []

    def low_priority(context):
        order.append("low")
        return HookResult.continue_with(
            args={"text": context.args["text"] + "!"}
        )

    def high_priority(context):
        order.append("high")
        return HookResult.continue_with(
            args={"text": context.args["text"].upper()}
        )

    manager.register(HookEvent.BEFORE_TOOL_CALL, low_priority, priority=10)
    manager.register(HookEvent.BEFORE_TOOL_CALL, high_priority, priority=100)
    registry = ToolRegistry(manager)
    registry.register(
        ToolDefinition(
            name="echo",
            description="Echo text.",
            handler=lambda args: ToolResult(ok=True, output=args["text"]),
        )
    )

    result = registry.call("echo", {"text": "hello"})

    assert order == ["high", "low"]
    assert result.output == "HELLO!"
    assert result.metadata["args"] == {"text": "HELLO!"}
    assert [item["hook"] for item in result.metadata["details"]["hooks"]] == [
        "high_priority",
        "low_priority",
    ]


def test_before_hook_can_block_tool_execution():
    manager = HookManager()
    executed = []
    manager.register(
        HookEvent.BEFORE_TOOL_CALL,
        lambda context: HookResult.block(
            "blocked",
            metadata={"error": "blocked_by_test", "policy": "test"},
        ),
        name="blocker",
    )
    registry = ToolRegistry(manager)
    registry.register(
        ToolDefinition(
            name="write",
            description="Write data.",
            handler=lambda args: (
                executed.append(True)
                or ToolResult(ok=True, output="written")
            ),
        )
    )

    result = registry.call("write", {})

    assert executed == []
    assert result.ok is False
    assert result.output == "blocked"
    assert result.metadata["error"] == "blocked_by_test"
    assert result.metadata["details"]["policy"] == "test"


def test_after_hook_can_add_result_metadata():
    manager = HookManager()

    def after(context):
        assert context.result.output == "done"
        return HookResult.continue_with(metadata={"audited": True})

    manager.register(HookEvent.AFTER_TOOL_CALL, after, name="audit")
    registry = ToolRegistry(manager)
    registry.register(
        ToolDefinition(
            name="work",
            description="Do work.",
            handler=lambda args: ToolResult(ok=True, output="done"),
        )
    )

    result = registry.call("work", {})

    assert result.ok is True
    assert result.metadata["details"]["audited"] is True
    assert result.metadata["details"]["hooks"][0]["event"] == "after_tool_call"


def test_tool_error_hook_receives_handler_exception():
    manager = HookManager()
    errors = []

    def on_error(context):
        errors.append(str(context.error))
        return HookResult.continue_with(metadata={"error_hook_seen": True})

    manager.register(HookEvent.TOOL_ERROR, on_error)
    registry = ToolRegistry(manager)
    registry.register(
        ToolDefinition(
            name="explode",
            description="Raise an error.",
            handler=lambda args: (_ for _ in ()).throw(ValueError("boom")),
        )
    )

    result = registry.call("explode", {})

    assert result.ok is False
    assert errors == ["boom"]
    assert result.metadata["error"] == "ValueError"
    assert result.metadata["details"]["error_hook_seen"] is True


def test_before_hook_exception_fails_closed():
    manager = HookManager()

    def broken_hook(context):
        raise RuntimeError("hook broke")

    manager.register(HookEvent.BEFORE_TOOL_CALL, broken_hook, name="broken")
    registry = ToolRegistry(manager)
    registry.register(
        ToolDefinition(
            name="dangerous",
            description="Must not execute.",
            handler=lambda args: ToolResult(ok=True, output="executed"),
        )
    )

    result = registry.call("dangerous", {})

    assert result.ok is False
    assert result.output == "Hook execution failed: broken"
    assert result.metadata["error"] == "hook_execution_failed"
    assert result.metadata["details"]["hook_errors"][0]["hook"] == "broken"


def test_hook_registration_can_be_unregistered():
    manager = HookManager()
    calls = []
    unregister = manager.register(
        HookEvent.BEFORE_TOOL_CALL,
        lambda context: calls.append(context.tool_name),
    )
    unregister()

    manager.emit(
        HookContext(
            event=HookEvent.BEFORE_TOOL_CALL,
            tool_name="echo",
            args={},
        )
    )

    assert calls == []
    assert manager.stats()["registered"] == 0


def test_default_permission_hook_denies_sensitive_file_write(tmp_path):
    registry = create_default_tool_registry(Workspace(str(tmp_path)))

    result = registry.call(
        "write_file",
        {"path": ".env", "content": "SECRET=value"},
    )

    assert result.ok is False
    assert result.output == "权限不足，无法写入文件"
    assert result.metadata["details"]["decision"] == "deny"
    assert result.metadata["details"]["hooks"][0]["hook"] == "permission"
    assert not (tmp_path / ".env").exists()


def test_default_permission_hook_allows_normal_file_write(tmp_path):
    registry = create_default_tool_registry(Workspace(str(tmp_path)))

    result = registry.call(
        "write_file",
        {"path": "README.md", "content": "hello"},
    )

    assert result.ok is True
    assert result.output == "Wrote README.md"
    assert result.metadata["details"]["decision"] == "allow"
    assert result.metadata["details"]["hooks"][0]["hook"] == "permission"
    assert result.metadata["details"]["tool_self_check"]["status"] == "passed"
    assert result.metadata["details"]["tool_self_check_result"]["status"] == "passed"
    assert (tmp_path / "README.md").read_text(encoding="utf-8") == "hello"


def test_custom_default_hook_manager_does_not_bypass_permission(tmp_path):
    manager = HookManager()
    observed = []
    manager.register(
        HookEvent.BEFORE_TOOL_CALL,
        lambda context: observed.append(context.tool_name),
        name="observer",
        priority=0,
    )
    registry = create_default_tool_registry(
        Workspace(str(tmp_path)),
        hook_manager=manager,
    )

    result = registry.call("run_shell", {"command": "rm -rf /"})

    assert result.ok is False
    # PermissionHook 优先阻断，低优先级 Hook 不再获得危险调用。
    assert observed == []
    assert result.metadata["details"]["hooks"][0]["hook"] == "permission"


def test_default_hook_manager_does_not_register_permission_twice(tmp_path):
    manager = HookManager()
    create_default_tool_registry(Workspace(str(tmp_path)), hook_manager=manager)
    create_default_tool_registry(Workspace(str(tmp_path)), hook_manager=manager)

    # 默认 Hook 包含 permission、subagent_approval、before/after 自检和安全边界。
    assert manager.stats()["registered"] == 5


def test_named_hook_cannot_impersonate_permission_hook(tmp_path):
    manager = HookManager()
    manager.register(
        HookEvent.BEFORE_TOOL_CALL,
        lambda context: None,
        name="permission",
    )
    registry = create_default_tool_registry(
        Workspace(str(tmp_path)),
        hook_manager=manager,
    )

    result = registry.call("run_shell", {"command": "rm -rf /"})

    assert result.ok is False
    assert manager.stats()["registered"] == 6
    assert result.metadata["details"]["hooks"][0]["hook"] == "permission"


def test_tool_self_check_blocks_missing_required_argument(tmp_path):
    registry = create_default_tool_registry(Workspace(str(tmp_path)))

    result = registry.call("read_file", {})

    assert result.ok is False
    assert result.metadata["error"] == "tool_self_check_failed"
    self_check = result.metadata["details"]["tool_self_check"]
    assert self_check["phase"] == "before"
    assert self_check["status"] == "failed"
    assert self_check["issues"] == ["missing required argument: path"]
    assert not result.metadata["details"].get("tool_self_check_result")


def test_tool_self_check_blocks_unexpected_argument(tmp_path):
    (tmp_path / "README.md").write_text("hello", encoding="utf-8")
    registry = create_default_tool_registry(Workspace(str(tmp_path)))

    result = registry.call("read_file", {"path": "README.md", "mode": "raw"})

    assert result.ok is False
    assert result.metadata["error"] == "tool_self_check_failed"
    assert "unexpected argument: mode" in result.metadata["details"]["tool_self_check"]["issues"]


def test_tool_self_check_records_missing_result_metadata():
    manager = HookManager()
    from micode.hooks.tool_self_check import ToolSelfCheckHook

    self_check = ToolSelfCheckHook()
    manager.register(HookEvent.BEFORE_TOOL_CALL, self_check, name="tool_self_check")
    manager.register(HookEvent.AFTER_TOOL_CALL, self_check, name="tool_self_check")
    registry = ToolRegistry(manager)
    registry.register(
        ToolDefinition(
            name="run_shell",
            description="Fake shell without metadata.",
            parameters={
                "type": "object",
                "properties": {"command": {"type": "string"}},
                "required": ["command"],
                "additionalProperties": False,
            },
            handler=lambda args: ToolResult(ok=True, output="ok"),
        )
    )

    result = registry.call("run_shell", {"command": "echo ok"})

    self_check_result = result.metadata["details"]["tool_self_check_result"]
    assert result.ok is True
    assert self_check_result["status"] == "failed"
    assert self_check_result["missing_metadata"] == [
        "command",
        "exit_code",
        "timed_out",
    ]
