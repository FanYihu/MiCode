from dataclasses import dataclass, field
import re

from micode.subagents.models import (
    SUBAGENT_COMPLETED,
    SubAgentResult,
    SubAgentTask,
)


@dataclass
class ReviewerFinding:
    """Reviewer 发现的一个具体问题。"""

    severity: str
    title: str
    detail: str
    evidence: str = ""

    def to_dict(self) -> dict:
        """转成可写入 SubAgentResult metadata 的普通字典。"""
        return {
            "severity": self.severity,
            "title": self.title,
            "detail": self.detail,
            "evidence": self.evidence,
        }


@dataclass
class ReviewerSubAgent:
    """只读代码审查 SubAgent。

    Day65 先实现确定性 reviewer：它不修改文件，也不直接调用外部模型；
    只根据主 Agent 传入的 objective/context 找出高风险信号。
    """

    secret_patterns: list[re.Pattern] = field(default_factory=list)

    def __post_init__(self) -> None:
        """延迟初始化正则，避免 dataclass 默认值共享复杂对象。"""
        if self.secret_patterns:
            return
        self.secret_patterns = [
            re.compile(r"sk-[A-Za-z0-9_\-]{12,}"),
            re.compile(
                r"(?i)(api[_-]?key|secret|password|token)\s*[:=]\s*['\"][^'\"]{6,}['\"]"
            ),
        ]

    def execute(self, task: SubAgentTask) -> SubAgentResult:
        """执行审查任务，并返回主 Agent 可验收的结构化结果。"""
        findings = self.review(task)
        if findings:
            summary = self._summarize_findings(findings)
        else:
            summary = "ReviewerSubAgent: no blocking findings."

        return SubAgentResult(
            task_id=task.id,
            role=task.role,
            status=SUBAGENT_COMPLETED,
            summary=summary,
            evidence=[finding.evidence for finding in findings if finding.evidence],
            metadata={
                "finding_count": len(findings),
                "findings": [finding.to_dict() for finding in findings],
            },
        )

    def review(self, task: SubAgentTask) -> list[ReviewerFinding]:
        """把 objective 和 context 当作审查输入，生成 findings。"""
        text = "\n".join([task.objective, task.context])
        findings: list[ReviewerFinding] = []
        findings.extend(self._find_secret_risks(text))
        findings.extend(self._find_dangerous_commands(text))
        findings.extend(self._find_placeholder_code(text))
        findings.extend(self._find_missing_tests(task))
        return findings

    def _find_secret_risks(self, text: str) -> list[ReviewerFinding]:
        """检查是否把密钥、token 等敏感内容塞进了上下文。"""
        findings = []
        for pattern in self.secret_patterns:
            match = pattern.search(text)
            if match:
                findings.append(
                    ReviewerFinding(
                        severity="high",
                        title="Possible secret exposure",
                        detail=(
                            "Context appears to contain an API key, token, "
                            "password, or secret-like value."
                        ),
                        evidence=_line_excerpt(text, match.start()),
                    )
                )
                break
        return findings

    def _find_dangerous_commands(self, text: str) -> list[ReviewerFinding]:
        """检查明显危险的 shell/git 操作。"""
        checks = [
            ("rm -rf /", "Destructive root removal command"),
            ("git reset --hard", "Destructive git reset"),
            ("git clean -fd", "Destructive git clean"),
            ("chmod -R 777", "Over-broad permission change"),
        ]
        findings = []
        lowered = text.lower()
        for needle, title in checks:
            index = lowered.find(needle)
            if index >= 0:
                findings.append(
                    ReviewerFinding(
                        severity="high",
                        title=title,
                        detail=f"Reviewer found risky command pattern: {needle}",
                        evidence=_line_excerpt(text, index),
                    )
                )
        return findings

    def _find_placeholder_code(self, text: str) -> list[ReviewerFinding]:
        """检查容易被误提交的占位实现。"""
        checks = [
            ("TODO", "TODO left in implementation"),
            ("FIXME", "FIXME left in implementation"),
            ("NotImplementedError", "Unimplemented code path"),
        ]
        findings = []
        for needle, title in checks:
            index = text.find(needle)
            if index >= 0:
                findings.append(
                    ReviewerFinding(
                        severity="medium",
                        title=title,
                        detail=(
                            "Reviewer found a placeholder marker that may need "
                            "resolution before considering the task complete."
                        ),
                        evidence=_line_excerpt(text, index),
                    )
                )
        return findings

    def _find_missing_tests(self, task: SubAgentTask) -> list[ReviewerFinding]:
        """粗略提醒：实现类任务如果没有测试信号，需要主 Agent 继续验证。"""
        text = "\n".join([task.objective, task.context]).lower()
        implementation_words = ("implement", "add", "新增", "实现", "修改", "change")
        test_words = ("test", "pytest", "unittest", "测试", "断言")
        if any(word in text for word in implementation_words) and not any(
            word in text for word in test_words
        ):
            return [
                ReviewerFinding(
                    severity="medium",
                    title="Missing test evidence",
                    detail=(
                        "Task looks like an implementation change, but the "
                        "review context does not mention tests or verification."
                    ),
                    evidence=task.objective,
                )
            ]
        return []

    def _summarize_findings(self, findings: list[ReviewerFinding]) -> str:
        """生成给主 Agent observation 使用的短摘要。"""
        high_count = sum(1 for finding in findings if finding.severity == "high")
        medium_count = sum(1 for finding in findings if finding.severity == "medium")
        titles = "; ".join(finding.title for finding in findings[:3])
        return (
            "ReviewerSubAgent: "
            f"{len(findings)} finding(s), high={high_count}, medium={medium_count}. "
            f"{titles}"
        )


def _line_excerpt(text: str, index: int) -> str:
    """根据字符位置返回所在行，避免把整段上下文塞进 evidence。"""
    start = text.rfind("\n", 0, index) + 1
    end = text.find("\n", index)
    if end == -1:
        end = len(text)
    return text[start:end].strip()
