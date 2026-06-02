from dataclasses import dataclass
from enum import Enum


class PermissionDecision(Enum):
    ALLOW = "allow"
    REVIEW = "review"
    DENY = "deny"


@dataclass
class PermissionResult:
    decision: PermissionDecision
    reason: str
    review_message: str = ""


class PermissionReviewer:
    """根据简单规则判断文件写入和 shell 命令是否允许执行。"""

    def review_file_write(self, path: str) -> PermissionResult:
        lower_path = path.lower()

        if lower_path.endswith((".env", ".pem", ".key")):
            return PermissionResult(
                PermissionDecision.DENY,
                "拒绝写入敏感文件",
            )

        if lower_path.endswith((".txt", ".md", ".py", ".ipynb", ".json", ".csv")):
            return PermissionResult(PermissionDecision.ALLOW, "允许写入普通文本文件")

        return PermissionResult(
            PermissionDecision.REVIEW,
            "需要人工确认文件写入",
            review_message=f"是否允许写入文件：{path}",
        )

    def review_shell_command(self, command: str) -> PermissionResult:
        normalized = command.strip().lower()
        dangerous_keywords = ["rm -rf", "sudo", "mkfs", "shutdown", "reboot"]

        if any(keyword in normalized for keyword in dangerous_keywords):
            return PermissionResult(
                PermissionDecision.DENY,
                "拒绝执行危险命令",
            )

        allowed_prefixes = (
            "python",
            "python3",
            "pytest",
            "ls",
            "pwd",
            "cat",
            "echo",
        )
        if normalized.startswith(allowed_prefixes):
            return PermissionResult(PermissionDecision.ALLOW, "允许执行低风险命令")

        return PermissionResult(
            PermissionDecision.REVIEW,
            "需要人工确认命令执行",
            review_message=f"是否允许执行命令：{command}",
        )
