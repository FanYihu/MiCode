from minicode.context.tool_results import (
    summarize_head_tail,
    summarize_tool_result,
)
from minicode.tools.registry import ToolResult


def make_result(output: str, details: dict = None) -> ToolResult:
    return ToolResult(
        ok=True,
        output=output,
        metadata={"details": details or {}},
    )


def test_short_tool_result_is_kept_in_full():
    summary = summarize_tool_result(
        "read_file",
        make_result("hello"),
        max_chars=20,
    )

    assert summary.content == "hello"
    assert summary.truncated is False
    assert summary.strategy == "full"


def test_command_summary_preserves_head_and_tail():
    output = "COMMAND START\n" + "x" * 300 + "\n5 failed, 20 passed"

    summary = summarize_tool_result(
        "run_shell",
        make_result(output),
        max_chars=120,
    )

    assert len(summary.content) <= 120
    assert "COMMAND START" in summary.content
    assert "5 failed, 20 passed" in summary.content
    assert summary.truncated is True
    assert summary.strategy == "command_head_tail"


def test_file_list_summary_includes_total_count():
    files = [f"file-{index}.py" for index in range(100)]

    summary = summarize_tool_result(
        "list_files",
        make_result("\n".join(files), {"files": files}),
        max_chars=140,
    )

    assert summary.content.startswith("[100 files]")
    assert len(summary.content) <= 140
    assert summary.strategy == "file_list"


def test_zero_budget_omits_observation_but_records_original_size():
    summary = summarize_tool_result(
        "read_file",
        make_result("long output"),
        max_chars=0,
    )

    assert summary.content == ""
    assert summary.original_chars == len("long output")
    assert summary.truncated is True
    assert summary.strategy == "omitted"


def test_head_tail_handles_tiny_budget():
    summary = summarize_head_tail("abcdefghijklmnopqrstuvwxyz", max_chars=5)

    assert summary == "abcde"
