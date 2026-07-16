from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import List


@dataclass(frozen=True)
class SecurityFinding:
    """Security Trace Audit 的单条可定位发现。"""

    severity: str
    code: str
    message: str
    event_id: str = ""
    tool: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


def review_security_trace(trace: dict) -> dict:
    """审计工具 provenance、注入风险和污染后的副作用调用。"""
    findings: List[SecurityFinding] = []
    trust_counts = {"trusted": 0, "local": 0, "untrusted": 0, "missing": 0}
    risk_counts = {"none": 0, "low": 0, "medium": 0, "high": 0}
    contaminated = False
    reviewed_writes = 0

    for event in trace.get("events", []):
        metadata = event.get("metadata", {})
        tool = str(metadata.get("tool") or "")
        if not tool:
            continue
        event_id = str(event.get("id") or "")
        trust_level = str(metadata.get("trust_level") or "missing")
        if trust_level not in trust_counts:
            trust_level = "missing"
        trust_counts[trust_level] += 1

        content_hash = str(metadata.get("content_sha256") or "")
        if trust_level == "missing" or len(content_hash) != 64:
            findings.append(
                SecurityFinding(
                    severity="high",
                    code="missing_tool_provenance",
                    message="工具事件缺少可信级别或 SHA-256 provenance。",
                    event_id=event_id,
                    tool=tool,
                )
            )

        risk = metadata.get("injection_risk", {})
        risk_level = str(risk.get("level") or "none")
        if risk_level not in risk_counts:
            risk_level = "none"
        risk_counts[risk_level] += 1
        if trust_level != "trusted" and risk_level in {"medium", "high"}:
            contaminated = True
            findings.append(
                SecurityFinding(
                    severity="medium" if risk_level == "medium" else "high",
                    code="prompt_injection_risk",
                    message=(
                        "不可信工具输出命中 Prompt Injection 规则："
                        + ", ".join(risk.get("matched_rules", []))
                    ),
                    event_id=event_id,
                    tool=tool,
                )
            )

        capabilities = metadata.get("capabilities", {})
        has_side_effects = bool(
            capabilities.get("writes_workspace")
            or capabilities.get("runs_commands")
            or capabilities.get("requires_review")
            or (
                capabilities.get("external_io")
                and not capabilities.get("read_only")
            )
        )
        if not contaminated or not has_side_effects:
            continue

        details = metadata.get("details", {})
        error = str(metadata.get("error") or "")
        review = details.get("human_review", {})
        if error == "human_review_required":
            continue
        if review.get("status") == "consumed":
            reviewed_writes += 1
            continue
        if metadata.get("ok"):
            findings.append(
                SecurityFinding(
                    severity="critical",
                    code="unreviewed_write_after_contamination",
                    message="受污染上下文之后执行了未经过人工审核的副作用工具。",
                    event_id=event_id,
                    tool=tool,
                )
            )

    severity_counts = {
        severity: sum(item.severity == severity for item in findings)
        for severity in ("critical", "high", "medium", "low")
    }
    if severity_counts["critical"]:
        status = "fail"
    elif severity_counts["high"] or severity_counts["medium"]:
        status = "warn"
    else:
        status = "pass"
    return {
        "status": status,
        "run_id": trace.get("run", {}).get("id", ""),
        "run_status": trace.get("run", {}).get("status", ""),
        "trust_counts": trust_counts,
        "injection_risk_counts": risk_counts,
        "contaminated": contaminated,
        "reviewed_writes": reviewed_writes,
        "severity_counts": severity_counts,
        "findings": [item.to_dict() for item in findings],
    }


def review_security_trace_file(path: str) -> dict:
    """读取持久化 Trace 并执行安全审计。"""
    trace = json.loads(Path(path).read_text(encoding="utf-8"))
    return review_security_trace(trace)
