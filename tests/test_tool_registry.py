import pytest
import subprocess

from minicode.tool_registry import (
    DuplicateToolName,
    ToolDefinition,
    ToolRegistry,
    ToolResult,
    create_default_tool_registry,
)
from minicode.workspace import Workspace


def test_tool_registry_registers_and_finds_tool():
    registry = ToolRegistry()
    tool = ToolDefinition(
        name="echo",
        description="Return the input text.",
        handler=lambda args: ToolResult(ok=True, output=args["text"]),
    )

    registry.register(tool)

    assert registry.get("echo") is tool
    assert registry.list_names() == ["echo"]
    assert registry.describe_tools() == ["- echo: Return the input text."]


def test_tool_registry_calls_registered_tool():
    registry = ToolRegistry()
    registry.register(
        ToolDefinition(
            name="echo",
            description="Return the input text.",
            handler=lambda args: ToolResult(
                ok=True,
                output=args["text"],
                metadata={"source": "test"},
            ),
        )
    )

    result = registry.call("echo", {"text": "hello"})

    assert result.ok is True
    assert result.output == "hello"
    assert result.metadata["tool"] == "echo"
    assert result.metadata["args"] == {"text": "hello"}
    assert result.metadata["ok"] is True
    assert result.metadata["result_summary"] == "hello"
    assert result.metadata["error"] == ""
    assert result.metadata["details"] == {"source": "test"}


def test_tool_registry_returns_error_for_unknown_tool():
    registry = ToolRegistry()

    result = registry.call("missing", {})

    assert result.ok is False
    assert result.output == "Unknown tool: missing"
    assert result.metadata["tool"] == "missing"
    assert result.metadata["args"] == {}
    assert result.metadata["ok"] is False
    assert result.metadata["result_summary"] == "Unknown tool: missing"
    assert result.metadata["error"] == "unknown_tool"
    assert result.metadata["details"] == {}


def test_tool_registry_rejects_duplicate_tool_names():
    registry = ToolRegistry()
    tool = ToolDefinition(
        name="echo",
        description="Return the input text.",
        handler=lambda args: ToolResult(ok=True, output=args["text"]),
    )
    registry.register(tool)

    with pytest.raises(DuplicateToolName):
        registry.register(tool)


def test_default_tool_registry_lists_and_reads_workspace_files(tmp_path):
    (tmp_path / "README.md").write_text("hello", encoding="utf-8")
    registry = create_default_tool_registry(Workspace(str(tmp_path)))

    list_result = registry.call("list_files", {})
    read_result = registry.call("read_file", {"path": "README.md"})

    assert list_result.ok is True
    assert list_result.output == "README.md"
    assert read_result.ok is True
    assert read_result.output == "hello"
    assert read_result.metadata["tool"] == "read_file"
    assert read_result.metadata["args"] == {"path": "README.md"}
    assert read_result.metadata["ok"] is True
    assert read_result.metadata["result_summary"] == "hello"
    assert read_result.metadata["error"] == ""
    assert read_result.metadata["details"] == {"path": "README.md"}


def test_default_tool_registry_replaces_text_and_returns_diff(tmp_path):
    file_path = tmp_path / "README.md"
    file_path.write_text("old\n", encoding="utf-8")
    registry = create_default_tool_registry(Workspace(str(tmp_path)))

    result = registry.call(
        "replace_text",
        {"path": "README.md", "old": "old", "new": "new"},
    )

    assert result.ok is True
    assert "+new" in result.output
    assert file_path.read_text(encoding="utf-8") == "new\n"


def test_default_tool_registry_runs_shell_command(tmp_path):
    registry = create_default_tool_registry(Workspace(str(tmp_path)))

    result = registry.call("run_shell", {"command": "echo hello"})

    assert result.ok is True
    assert result.output == "hello\n"
    assert result.metadata["tool"] == "run_shell"
    assert result.metadata["args"] == {"command": "echo hello"}
    assert result.metadata["ok"] is True
    assert result.metadata["result_summary"] == "hello\n"
    assert result.metadata["error"] == ""
    assert result.metadata["details"]["command"] == "echo hello"
    assert result.metadata["details"]["exit_code"] == 0
    assert result.metadata["details"]["timed_out"] is False


def test_default_tool_registry_registers_git_tools(tmp_path):
    subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True)
    (tmp_path / "README.md").write_text("hello\n", encoding="utf-8")
    registry = create_default_tool_registry(Workspace(str(tmp_path)))

    status = registry.call("git_status", {})
    diff = registry.call("git_diff", {})

    assert "git_status" in registry.list_names()
    assert "git_diff" in registry.list_names()
    assert status.ok is True
    assert "?? README.md" in status.output
    assert status.metadata["tool"] == "git_status"
    assert status.metadata["args"] == {}
    assert status.metadata["ok"] is True
    assert status.metadata["error"] == ""
    assert status.metadata["details"]["command"] == ["git", "status", "--short"]
    assert status.metadata["details"]["exit_code"] == 0
    assert diff.ok is True
    assert diff.metadata["tool"] == "git_diff"
    assert diff.metadata["details"]["command"] == ["git", "diff"]


def test_default_tool_registry_loads_project_skill(tmp_path):
    skill_dir = tmp_path / ".minicode" / "skills" / "python-test"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(
        "# Python Test\n\nRun Python tests safely.\n\nUse pytest.",
        encoding="utf-8",
    )
    registry = create_default_tool_registry(Workspace(str(tmp_path)))

    result = registry.call("load_skill", {"name": "python-test"})

    assert result.ok is True
    assert "load_skill" in registry.list_names()
    assert "SKILL: python-test" in result.output
    assert "DESCRIPTION: Run Python tests safely." in result.output
    assert "Use pytest." in result.output
    assert result.metadata["tool"] == "load_skill"
    assert result.metadata["args"] == {"name": "python-test"}
    assert result.metadata["ok"] is True
    assert result.metadata["error"] == ""
    assert result.metadata["details"]["name"] == "python-test"


def test_default_tool_registry_returns_error_for_unknown_skill(tmp_path):
    registry = create_default_tool_registry(Workspace(str(tmp_path)))

    result = registry.call("load_skill", {"name": "missing"})

    assert result.ok is False
    assert result.output == "Unknown skill: missing"
    assert result.metadata["tool"] == "load_skill"
    assert result.metadata["error"] == "unknown_skill"
    assert result.metadata["details"]["name"] == "missing"


def test_default_tool_registry_denies_dangerous_shell_command(tmp_path):
    registry = create_default_tool_registry(Workspace(str(tmp_path)))

    result = registry.call("run_shell", {"command": "rm -rf /"})

    assert result.ok is False
    assert result.output == "权限不足，无法运行命令"
    assert result.metadata["tool"] == "run_shell"
    assert result.metadata["args"] == {"command": "rm -rf /"}
    assert result.metadata["ok"] is False
    assert result.metadata["error"]
    assert result.metadata["details"]["decision"]
    assert "review_message" in result.metadata["details"]


def test_tool_registry_summarizes_long_output_in_metadata():
    registry = ToolRegistry()
    long_output = "x" * 250
    registry.register(
        ToolDefinition(
            name="long_output",
            description="Return long output.",
            handler=lambda args: ToolResult(ok=True, output=long_output),
        )
    )

    result = registry.call("long_output", {})

    assert result.output == long_output
    assert len(result.metadata["result_summary"]) < len(long_output)
    assert result.metadata["result_summary"].endswith("... [truncated]")


def test_tool_registry_uses_output_as_error_when_failed_tool_has_no_error_metadata():
    registry = ToolRegistry()
    registry.register(
        ToolDefinition(
            name="fail",
            description="Return failed result.",
            handler=lambda args: ToolResult(ok=False, output="failed"),
        )
    )

    result = registry.call("fail", {})

    assert result.ok is False
    assert result.metadata["error"] == "failed"
