from dataclasses import dataclass
import re

from micode.subagents.models import (
    SUBAGENT_COMPLETED,
    SUBAGENT_FAILED,
    SubAgentResult,
    SubAgentTask,
)
from micode.tools.shell import ShellTools


DEFAULT_TEST_COMMAND = "python3 -m pytest tests -q"


@dataclass
class TesterSubAgent:
    """受控测试 SubAgent。

    Tester 只负责运行测试类命令并摘要结果；命令仍在 Workspace 内执行，
    且必须通过测试命令白名单，避免把 tester 变成任意 shell 通道。
    """

    shell_tools: ShellTools
    default_command: str = DEFAULT_TEST_COMMAND
    timeout: int = 30
    __test__ = False

    def execute(self, task: SubAgentTask) -> SubAgentResult:
        """选择测试命令、执行并返回结构化测试结果。"""
        command = self._select_command(task)
        if not self._is_allowed_test_command(command):
            return SubAgentResult(
                task_id=task.id,
                role=task.role,
                status=SUBAGENT_FAILED,
                summary=f"TesterSubAgent: blocked unsupported test command: {command}",
                metadata={
                    "error": "unsupported_test_command",
                    "command": command,
                },
            )

        result = self.shell_tools.run(command, timeout=self.timeout)
        output = _trim_output(result.stdout or result.stderr)
        passed = result.exit_code == 0 and not result.timed_out
        status = SUBAGENT_COMPLETED if passed else SUBAGENT_FAILED
        summary = self._build_summary(command, result.exit_code, result.timed_out, output)

        return SubAgentResult(
            task_id=task.id,
            role=task.role,
            status=status,
            summary=summary,
            evidence=[output] if output else [],
            metadata={
                "command": command,
                "exit_code": result.exit_code,
                "timed_out": result.timed_out,
                "stdout": _trim_output(result.stdout),
                "stderr": _trim_output(result.stderr),
            },
        )

    def _select_command(self, task: SubAgentTask) -> str:
        """从任务上下文提取测试命令；没有明确命令时使用默认 pytest。"""
        explicit = str(task.metadata.get("command") or "").strip()
        if explicit:
            return explicit

        text = "\n".join([task.objective, task.context])
        for line in text.splitlines():
            match = re.match(r"\s*(test command|command|测试命令)\s*[:：]\s*(.+)\s*$", line, re.I)
            if match:
                return match.group(2).strip()
        return self.default_command

    def _is_allowed_test_command(self, command: str) -> bool:
        """只允许测试命令，并拒绝 shell 拼接、重定向和命令替换。"""
        stripped = command.strip()
        if not stripped:
            return False
        blocked_tokens = [";", "&&", "||", "|", ">", "<", "`", "$("]
        if any(token in stripped for token in blocked_tokens):
            return False

        allowed_prefixes = (
            "pytest",
            "python -m pytest",
            "python3 -m pytest",
        )
        return stripped == "pytest" or stripped.startswith(allowed_prefixes)

    def _build_summary(
        self,
        command: str,
        exit_code: int,
        timed_out: bool,
        output: str,
    ) -> str:
        """生成主 Agent observation 使用的测试摘要。"""
        if timed_out:
            return f"TesterSubAgent: timed out command={command}"
        if exit_code == 0:
            return f"TesterSubAgent: passed command={command}"
        if output:
            return (
                f"TesterSubAgent: failed command={command}, "
                f"exit_code={exit_code}. {output}"
            )
        return f"TesterSubAgent: failed command={command}, exit_code={exit_code}"


def _trim_output(text: str, max_chars: int = 1200) -> str:
    """限制测试输出长度，完整 trace 可以后续交给 artifact 处理。"""
    stripped = (text or "").strip()
    if len(stripped) <= max_chars:
        return stripped
    return f"{stripped[:max_chars]}... [truncated]"
