from dataclasses import dataclass

from minicode.tools.registry import ToolResult


DEFAULT_TOOL_RESULT_BUDGET = 1200


@dataclass
class ToolResultSummary:
    """ToolResultSummary 是提供给模型的紧凑工具结果。"""

    content: str
    original_chars: int
    used_chars: int
    truncated: bool
    strategy: str

    def to_metadata(self) -> dict:
        """转成 trace metadata，便于复盘模型实际看到了什么。"""
        return {
            "observation_summary": self.content,
            "observation_original_chars": self.original_chars,
            "observation_used_chars": self.used_chars,
            "observation_truncated": self.truncated,
            "observation_strategy": self.strategy,
        }


def summarize_tool_result(
    tool_name: str,
    result: ToolResult,
    max_chars: int = DEFAULT_TOOL_RESULT_BUDGET,
) -> ToolResultSummary:
    """压缩提供给模型的工具输出，完整 output 仍由 Trace 保存。"""
    output = result.output if isinstance(result.output, str) else str(result.output)
    original_chars = len(output)
    if max_chars <= 0:
        return ToolResultSummary(
            content="",
            original_chars=original_chars,
            used_chars=0,
            truncated=bool(output),
            strategy="omitted",
        )
    if original_chars <= max_chars:
        return ToolResultSummary(
            content=output,
            original_chars=original_chars,
            used_chars=original_chars,
            truncated=False,
            strategy="full",
        )

    details = result.metadata.get("details", {})
    if tool_name == "list_files":
        summary = summarize_file_list(output, details, max_chars)
        strategy = "file_list"
    elif tool_name in {"run_shell", "git_diff", "git_status"}:
        # 命令输出的结尾经常包含失败原因或测试统计，因此保留首尾。
        summary = summarize_head_tail(output, max_chars, tail_ratio=0.6)
        strategy = "command_head_tail"
    elif tool_name in {"read_file", "load_skill"}:
        summary = summarize_head_tail(output, max_chars, tail_ratio=0.3)
        strategy = "document_head_tail"
    else:
        summary = summarize_head_tail(output, max_chars, tail_ratio=0.5)
        strategy = "generic_head_tail"

    return ToolResultSummary(
        content=summary,
        original_chars=original_chars,
        used_chars=len(summary),
        truncated=True,
        strategy=strategy,
    )


def summarize_file_list(output: str, details: dict, max_chars: int) -> str:
    """压缩文件列表，并在标题中保留总文件数。"""
    files = details.get("files", [])
    count = len(files) if isinstance(files, list) else len(output.splitlines())
    prefix = f"[{count} files]\n"
    body_budget = max(0, max_chars - len(prefix))
    return prefix + summarize_head_tail(output, body_budget, tail_ratio=0.35)


def summarize_head_tail(
    output: str,
    max_chars: int,
    tail_ratio: float = 0.5,
) -> str:
    """按字符预算保留输出首尾，避免只留开头而丢失最终结果。"""
    marker = "\n... [tool output truncated] ...\n"
    if len(output) <= max_chars:
        return output
    if max_chars <= len(marker) + 8:
        return output[:max_chars]

    available = max_chars - len(marker)
    tail_chars = max(1, int(available * tail_ratio))
    head_chars = available - tail_chars
    return output[:head_chars].rstrip() + marker + output[-tail_chars:].lstrip()
