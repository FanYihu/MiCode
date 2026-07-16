from dataclasses import dataclass, field

from micode.subagents.models import (
    SUBAGENT_COMPLETED,
    SUBAGENT_FAILED,
    SubAgentExecutor,
    SubAgentPolicy,
    SubAgentResult,
    SubAgentTask,
)


@dataclass
class MultiAgentReviewReport:
    """一次 implementer/tester/reviewer 协作的聚合报告。"""

    approved: bool
    summary: str
    results: list[SubAgentResult] = field(default_factory=list)

    def to_dict(self) -> dict:
        """转成可写入 Trace 或文档的普通字典。"""
        return {
            "approved": self.approved,
            "summary": self.summary,
            "results": [result.to_dict() for result in self.results],
        }


@dataclass
class MultiAgentReviewPipeline:
    """主 Agent 使用的多 SubAgent 协作编排器。

    Pipeline 自己不绕过 SubAgent 契约；每一步仍然构造 SubAgentTask，并交给
    同一个 SubAgentExecutor 执行，方便复用 RoleBased/Forked executor。
    """

    executor: SubAgentExecutor
    policy: SubAgentPolicy = field(default_factory=SubAgentPolicy)

    def run(
        self,
        objective: str,
        operations_context: str,
        test_context: str = "",
        review_context: str = "",
        parent_run_id: str = "",
    ) -> MultiAgentReviewReport:
        """按 implementer -> tester -> reviewer 顺序执行完整审查。"""
        results: list[SubAgentResult] = []

        implementer_result = self._run_task(
            role="implementer",
            objective=objective,
            context=operations_context,
            parent_run_id=parent_run_id,
        )
        results.append(implementer_result)
        if not implementer_result.ok:
            return self._report(False, "MultiAgentReview: implementer failed.", results)

        tester_result = self._run_task(
            role="tester",
            objective=f"Test implementation for: {objective}",
            context=test_context,
            parent_run_id=parent_run_id,
        )
        results.append(tester_result)
        if not tester_result.ok:
            return self._report(False, "MultiAgentReview: tests failed.", results)

        reviewer_result = self._run_task(
            role="reviewer",
            objective=f"Review implementation for: {objective}",
            context=self._build_review_context(
                review_context,
                implementer_result,
                tester_result,
            ),
            parent_run_id=parent_run_id,
        )
        results.append(reviewer_result)
        approved = reviewer_result.ok and not _reviewer_has_high_findings(reviewer_result)
        summary = (
            "MultiAgentReview: approved."
            if approved
            else "MultiAgentReview: reviewer found blocking issues."
        )
        return self._report(approved, summary, results)

    def _run_task(
        self,
        role: str,
        objective: str,
        context: str,
        parent_run_id: str,
    ) -> SubAgentResult:
        """创建带 policy 边界的 SubAgentTask 并执行。"""
        task = SubAgentTask(
            role=role,
            objective=objective,
            context=context,
            allowed_tools=self.policy.tools_for(role),
            allowed_paths=list(self.policy.allowed_paths),
            max_steps=self.policy.default_max_steps,
            parent_run_id=parent_run_id,
        )
        return self.executor.execute(task)

    def _build_review_context(
        self,
        review_context: str,
        implementer_result: SubAgentResult,
        tester_result: SubAgentResult,
    ) -> str:
        """把实现和测试结果压成 reviewer 可读上下文。"""
        return "\n".join(
            [
                review_context,
                f"Implementer summary: {implementer_result.summary}",
                f"Changed paths: {implementer_result.changed_paths}",
                f"Tester summary: {tester_result.summary}",
                "Tester evidence:",
                "\n".join(tester_result.evidence),
            ]
        ).strip()

    def _report(
        self,
        approved: bool,
        summary: str,
        results: list[SubAgentResult],
    ) -> MultiAgentReviewReport:
        """构造聚合报告。"""
        return MultiAgentReviewReport(
            approved=approved,
            summary=summary,
            results=results,
        )


def _reviewer_has_high_findings(result: SubAgentResult) -> bool:
    """从 Reviewer metadata 判断是否存在高严重度问题。"""
    findings = result.metadata.get("findings", [])
    if not isinstance(findings, list):
        return False
    return any(
        isinstance(finding, dict) and finding.get("severity") == "high"
        for finding in findings
    )
