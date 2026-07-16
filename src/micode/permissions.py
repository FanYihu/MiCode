from dataclasses import dataclass
from enum import Enum
from typing import Optional


class PermissionDecision(Enum):
    ALLOW = "allow"
    REVIEW = "review"
    DENY = "deny"


@dataclass
class PermissionResult:
    decision: PermissionDecision
    reason: str
    review_message: str = ""
    rule_name: str = ""
    layer: str = ""


@dataclass
class PermissionRule:
    """一条权限规则，只处理自己关心的请求类型和目标。"""

    name: str
    layer: str
    kinds: tuple[str, ...]
    decision: PermissionDecision
    reason: str
    suffixes: tuple[str, ...] = ()
    prefixes: tuple[str, ...] = ()
    contains: tuple[str, ...] = ()
    review_template: str = ""

    def evaluate(self, kind: str, target: str) -> Optional[PermissionResult]:
        """匹配则返回 PermissionResult，不匹配返回 None。"""
        if kind not in self.kinds:
            return None

        normalized = target.strip().lower()
        matched = False
        if self.suffixes and normalized.endswith(self.suffixes):
            matched = True
        if self.prefixes and normalized.startswith(self.prefixes):
            matched = True
        if self.contains and any(item in normalized for item in self.contains):
            matched = True
        if not (self.suffixes or self.prefixes or self.contains):
            matched = True
        if not matched:
            return None

        return PermissionResult(
            decision=self.decision,
            reason=self.reason,
            review_message=(
                self.review_template.format(target=target)
                if self.review_template
                else ""
            ),
            rule_name=self.name,
            layer=self.layer,
        )


class PermissionReviewer:
    """按 deny / allow / review 分层规则判断工具权限。"""

    layer_order = ("deny", "allow", "review")

    def __init__(self, rules: Optional[list[PermissionRule]] = None) -> None:
        self.rules = list(rules) if rules is not None else default_permission_rules()

    def review_file_write(self, path: str) -> PermissionResult:
        """审查文件写入请求。"""
        return self._review("file_write", path)

    def review_shell_command(self, command: str) -> PermissionResult:
        """审查 shell 命令执行请求。"""
        return self._review("shell_command", command)

    def _review(self, kind: str, target: str) -> PermissionResult:
        """按层执行规则；deny 层永远先于 allow 层。"""
        for layer in self.layer_order:
            for rule in self.rules:
                if rule.layer != layer:
                    continue
                result = rule.evaluate(kind, target)
                if result is not None:
                    return result

        return PermissionResult(
            PermissionDecision.REVIEW,
            "没有匹配到明确权限规则",
            review_message=f"是否允许执行：{target}",
            rule_name="fallback_review",
            layer="review",
        )


def default_permission_rules() -> list[PermissionRule]:
    """Micode 默认权限规则集合。"""
    return [
        PermissionRule(
            name="deny_sensitive_file_write",
            layer="deny",
            kinds=("file_write",),
            decision=PermissionDecision.DENY,
            reason="拒绝写入敏感文件",
            suffixes=(".env", ".pem", ".key"),
        ),
        PermissionRule(
            name="deny_dangerous_shell_command",
            layer="deny",
            kinds=("shell_command",),
            decision=PermissionDecision.DENY,
            reason="拒绝执行危险命令",
            contains=("rm -rf", "sudo", "mkfs", "shutdown", "reboot"),
        ),
        PermissionRule(
            name="allow_common_text_file_write",
            layer="allow",
            kinds=("file_write",),
            decision=PermissionDecision.ALLOW,
            reason="允许写入普通文本文件",
            suffixes=(".txt", ".md", ".py", ".ipynb", ".json", ".csv"),
        ),
        PermissionRule(
            name="allow_low_risk_shell_command",
            layer="allow",
            kinds=("shell_command",),
            decision=PermissionDecision.ALLOW,
            reason="允许执行低风险命令",
            prefixes=("python", "python3", "pytest", "ls", "pwd", "cat", "echo"),
        ),
        PermissionRule(
            name="review_unknown_file_write",
            layer="review",
            kinds=("file_write",),
            decision=PermissionDecision.REVIEW,
            reason="需要人工确认文件写入",
            review_template="是否允许写入文件：{target}",
        ),
        PermissionRule(
            name="review_unknown_shell_command",
            layer="review",
            kinds=("shell_command",),
            decision=PermissionDecision.REVIEW,
            reason="需要人工确认命令执行",
            review_template="是否允许执行命令：{target}",
        )
    ]
