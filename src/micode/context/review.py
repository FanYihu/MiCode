import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path

from micode.persistence import load_trace


@dataclass
class ContextReviewIssue:
    """ContextReviewIssue 描述上下文审计发现的问题。"""

    severity: str
    code: str
    message: str
    subject_id: str = ""
    details: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        """转成 CLI 友好的 JSON dict。"""
        return {
            "severity": self.severity,
            "code": self.code,
            "message": self.message,
            "subject_id": self.subject_id,
            "details": self.details,
        }


@dataclass
class ContextReviewReport:
    """ContextReviewReport 汇总一次 trace 的上下文健康状态。"""

    summary: dict = field(default_factory=dict)
    issues: list[ContextReviewIssue] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        """没有 error 级问题时认为 review 通过。"""
        return not any(issue.severity == "error" for issue in self.issues)

    def to_dict(self) -> dict:
        """转成可保存或 CLI 输出的 JSON dict。"""
        return {
            "ok": self.ok,
            "summary": self.summary,
            "issues": [issue.to_dict() for issue in self.issues],
        }


def review_context_trace_file(trace_path: str) -> ContextReviewReport:
    """读取 trace 文件并执行 Context Review。"""
    return review_context_trace(load_trace(trace_path))


def review_context_trace(trace: dict) -> ContextReviewReport:
    """检查一条 trace 的上下文压缩、缓存和 artifact 引用是否自洽。"""
    run = trace.get("run", {})
    metadata = run.get("metadata", {})
    events = trace.get("events", [])
    issues = []

    assembly = metadata.get("context_assembly", {})
    issues.extend(review_context_assembly(assembly))
    issues.extend(review_context_token_estimate(metadata.get("context_token_estimate")))
    issues.extend(review_prompt_cache(metadata.get("prompt_cache", {})))
    issues.extend(review_decision_freezes(metadata))
    issues.extend(review_artifact_references(events))

    summary = {
        "run_id": run.get("id", ""),
        "mode": metadata.get("mode", run.get("mode", "")),
        "has_context_assembly": bool(assembly),
        "has_context_token_estimate": bool(metadata.get("context_token_estimate")),
        "has_prompt_cache": bool(metadata.get("prompt_cache")),
        "decision_freezes": len(metadata.get("decision_freezes", [])),
        "artifact_references": count_artifact_references(events),
        "issues": {
            "errors": sum(1 for issue in issues if issue.severity == "error"),
            "warnings": sum(1 for issue in issues if issue.severity == "warning"),
        },
    }
    if assembly:
        summary["context_used_chars"] = assembly.get("used_chars", 0)
        summary["context_estimated_tokens"] = assembly.get("estimated_tokens", 0)
        summary["context_compacted"] = assembly.get("compaction", {}).get(
            "compacted",
            False,
        )

    return ContextReviewReport(summary=summary, issues=issues)


def review_context_assembly(assembly: dict) -> list[ContextReviewIssue]:
    """检查 ContextAssembly metadata 是否完整且未超预算。"""
    if not assembly:
        return [
            ContextReviewIssue(
                severity="warning",
                code="missing_context_assembly",
                message="Trace has no context_assembly metadata.",
            )
        ]

    issues = []
    budget_chars = int(assembly.get("budget_chars") or 0)
    used_chars = int(assembly.get("used_chars") or 0)
    if budget_chars > 0 and used_chars > budget_chars:
        issues.append(
            ContextReviewIssue(
                severity="error",
                code="context_budget_exceeded",
                message="Assembled context exceeds its character budget.",
                details={"budget_chars": budget_chars, "used_chars": used_chars},
            )
        )

    layers = assembly.get("layers", [])
    if not isinstance(layers, list):
        issues.append(
            ContextReviewIssue(
                severity="error",
                code="invalid_context_layers",
                message="context_assembly.layers must be a list.",
            )
        )
        layers = []

    if "estimated_tokens" not in assembly:
        issues.append(
            ContextReviewIssue(
                severity="warning",
                code="missing_context_estimated_tokens",
                message="Context assembly has no estimated token count.",
            )
        )

    compaction = assembly.get("compaction", {})
    if not compaction:
        issues.append(
            ContextReviewIssue(
                severity="warning",
                code="missing_compaction_metadata",
                message="Context assembly has no auto compaction metadata.",
            )
        )
        return issues

    effective_budget = int(compaction.get("effective_budget_chars") or 0)
    compaction_used = int(compaction.get("used_chars") or 0)
    if effective_budget > 0 and compaction_used > effective_budget:
        issues.append(
            ContextReviewIssue(
                severity="error",
                code="compaction_budget_exceeded",
                message="Compacted context exceeds effective budget.",
                details={
                    "effective_budget_chars": effective_budget,
                    "used_chars": compaction_used,
                },
            )
        )

    action_names = {
        action.get("layer")
        for action in compaction.get("actions", [])
        if isinstance(action, dict)
    }
    missing_actions = [
        layer.get("name")
        for layer in layers
        if layer.get("name") not in action_names
    ]
    if missing_actions:
        issues.append(
            ContextReviewIssue(
                severity="warning",
                code="compaction_missing_layer_actions",
                message="Some context layers have no compaction action record.",
                details={"layers": missing_actions},
            )
        )

    compacted = bool(compaction.get("compacted"))
    has_truncated_or_omitted = any(
        layer.get("truncated")
        or (
            not layer.get("included", False)
            and layer.get("omitted_reason") not in {"", "empty"}
        )
        for layer in layers
    )
    if has_truncated_or_omitted and not compacted:
        issues.append(
            ContextReviewIssue(
                severity="warning",
                code="compaction_flag_mismatch",
                message="Layers were truncated or omitted but compaction flag is false.",
            )
        )

    return issues


def review_context_token_estimate(estimate: dict) -> list[ContextReviewIssue]:
    """检查 CLI assembled context 的 token estimate 是否存在关键部分。"""
    if not estimate:
        return [
            ContextReviewIssue(
                severity="warning",
                code="missing_context_token_estimate",
                message="Trace has no context_token_estimate metadata.",
            )
        ]
    parts = estimate.get("parts", [])
    part_names = {
        part.get("name")
        for part in parts
        if isinstance(part, dict)
    }
    if "assembled_context" not in part_names:
        return [
            ContextReviewIssue(
                severity="warning",
                code="missing_assembled_context_token_estimate",
                message="context_token_estimate has no assembled_context part.",
            )
        ]
    return []


def review_prompt_cache(prompt_cache: dict) -> list[ContextReviewIssue]:
    """检查 prompt cache metadata 指向的文件是否存在且 hash 自洽。"""
    if not prompt_cache:
        return [
            ContextReviewIssue(
                severity="warning",
                code="missing_prompt_cache",
                message="Trace has no prompt_cache metadata.",
            )
        ]
    path = Path(prompt_cache.get("prompt_cache_path", ""))
    if not path.exists():
        return [
            ContextReviewIssue(
                severity="warning",
                code="prompt_cache_file_missing",
                message="Prompt cache file does not exist.",
                subject_id=str(path),
            )
        ]

    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        return [
            ContextReviewIssue(
                severity="error",
                code="invalid_prompt_cache_json",
                message="Prompt cache file is not valid JSON.",
                subject_id=str(path),
                details={"error": str(error)},
            )
        ]

    content = payload.get("content", "")
    digest = hashlib.sha256(str(content).encode("utf-8")).hexdigest()
    expected = prompt_cache.get("prompt_cache_sha256") or payload.get("sha256")
    if expected and expected != digest:
        return [
            ContextReviewIssue(
                severity="error",
                code="prompt_cache_hash_mismatch",
                message="Prompt cache content hash does not match metadata.",
                subject_id=str(path),
                details={"expected_sha256": expected, "actual_sha256": digest},
            )
        ]
    return []


def review_decision_freezes(metadata: dict) -> list[ContextReviewIssue]:
    """检查 Decision Freeze 是否和 Prompt Cache 关联一致。"""
    freezes = metadata.get("decision_freezes", [])
    if not freezes:
        return [
            ContextReviewIssue(
                severity="warning",
                code="missing_decision_freezes",
                message="Trace has no decision freeze records.",
            )
        ]

    issues = []
    prompt_cache_key = metadata.get("prompt_cache", {}).get("prompt_cache_key", "")
    for freeze in freezes:
        freeze_key = freeze.get("prompt_cache_key", "")
        if prompt_cache_key and freeze_key != prompt_cache_key:
            issues.append(
                ContextReviewIssue(
                    severity="error",
                    code="decision_freeze_prompt_cache_mismatch",
                    message="Decision freeze prompt_cache_key does not match run prompt cache.",
                    subject_id=str(freeze.get("turn_index", "")),
                    details={
                        "prompt_cache_key": prompt_cache_key,
                        "freeze_prompt_cache_key": freeze_key,
                    },
                )
            )
    return issues


def review_artifact_references(events: list[dict]) -> list[ContextReviewIssue]:
    """检查 Trace event 中的 artifact 引用是否仍可读取和校验。"""
    issues = []
    for event in events:
        artifact = event.get("metadata", {}).get("artifact", {})
        if not artifact:
            continue
        artifact_path = Path(artifact.get("artifact_path", ""))
        artifact_id = artifact.get("artifact_id", "")
        if not artifact_path.exists():
            issues.append(
                ContextReviewIssue(
                    severity="error",
                    code="artifact_file_missing",
                    message="Artifact file referenced by trace does not exist.",
                    subject_id=artifact_id,
                    details={"artifact_path": str(artifact_path)},
                )
            )
            continue

        try:
            payload = json.loads(artifact_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as error:
            issues.append(
                ContextReviewIssue(
                    severity="error",
                    code="invalid_artifact_json",
                    message="Artifact file is not valid JSON.",
                    subject_id=artifact_id,
                    details={"error": str(error)},
                )
            )
            continue

        content = payload.get("content", "")
        digest = hashlib.sha256(str(content).encode("utf-8")).hexdigest()
        expected = artifact.get("artifact_sha256") or payload.get("sha256")
        if expected and expected != digest:
            issues.append(
                ContextReviewIssue(
                    severity="error",
                    code="artifact_hash_mismatch",
                    message="Artifact content hash does not match trace metadata.",
                    subject_id=artifact_id,
                    details={"expected_sha256": expected, "actual_sha256": digest},
                )
            )

        placeholder = artifact.get("artifact_placeholder", "")
        if placeholder and placeholder not in event.get("content", ""):
            issues.append(
                ContextReviewIssue(
                    severity="warning",
                    code="artifact_placeholder_missing_from_event",
                    message="Artifact metadata has a placeholder but event content does not include it.",
                    subject_id=artifact_id,
                )
            )
    return issues


def count_artifact_references(events: list[dict]) -> int:
    """统计 trace event 中非空 artifact metadata 的数量。"""
    return sum(
        1
        for event in events
        if event.get("metadata", {}).get("artifact")
    )
