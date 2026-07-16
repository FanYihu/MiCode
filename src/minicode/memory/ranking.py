from dataclasses import dataclass, field, replace
from datetime import datetime, timezone

from minicode.memory.retrieval import MemoryRetrievalResult
from minicode.memory.temporal import ACTIVE, CONFLICTING
from minicode.memory.working import truncate_memory_text


DEFAULT_MEMORY_BUDGET = 1800
DEFAULT_MEMORY_ITEM_LIMIT = 8


@dataclass
class MemoryInjection:
    """MemoryInjection 表示经过排序和预算裁剪后真正进入 prompt 的记忆。"""

    context: str = ""
    selected: list[MemoryRetrievalResult] = field(default_factory=list)
    omitted_ids: list[str] = field(default_factory=list)
    used_chars: int = 0
    budget_chars: int = DEFAULT_MEMORY_BUDGET


class MemoryRankingPolicy:
    """对混合召回结果做业务排序，并控制长期记忆注入预算。"""

    def __init__(
        self,
        retrieval_weight: float = 0.55,
        type_weight: float = 0.15,
        confidence_weight: float = 0.15,
        recency_weight: float = 0.10,
        session_weight: float = 0.05,
        conflict_multiplier: float = 0.75,
    ) -> None:
        self.retrieval_weight = retrieval_weight
        self.type_weight = type_weight
        self.confidence_weight = confidence_weight
        self.recency_weight = recency_weight
        self.session_weight = session_weight
        self.conflict_multiplier = conflict_multiplier

    def rank(
        self,
        results: list[MemoryRetrievalResult],
        current_session_id: str = "",
        now: datetime = None,
    ) -> list[MemoryRetrievalResult]:
        """根据相关性、类型、置信度、时效和 Session 归属进行精排。"""
        reference_time = now or datetime.now(timezone.utc)
        ranked = []
        for result in results:
            type_score = memory_type_score(result.type)
            confidence_score = memory_confidence(result)
            recency_score = memory_recency(result, reference_time)
            session_score = memory_session_score(result, current_session_id)
            score = (
                result.score * self.retrieval_weight
                + type_score * self.type_weight
                + confidence_score * self.confidence_weight
                + recency_score * self.recency_weight
                + session_score * self.session_weight
            )
            if result.status == CONFLICTING:
                score *= self.conflict_multiplier

            ranked.append(
                replace(
                    result,
                    ranking_score=round(score, 6),
                    ranking_details={
                        "retrieval": round(result.score, 6),
                        "type": round(type_score, 6),
                        "confidence": round(confidence_score, 6),
                        "recency": round(recency_score, 6),
                        "session": round(session_score, 6),
                        "status_multiplier": (
                            self.conflict_multiplier
                            if result.status == CONFLICTING
                            else 1.0
                        ),
                    },
                )
            )

        ranked.sort(
            key=lambda result: (
                result.ranking_score,
                result.score,
                result.keyword_score,
            ),
            reverse=True,
        )
        return ranked

    def prepare_injection(
        self,
        ranked_results: list[MemoryRetrievalResult],
        budget_chars: int = DEFAULT_MEMORY_BUDGET,
        item_limit: int = DEFAULT_MEMORY_ITEM_LIMIT,
        per_type_limit: int = 3,
    ) -> MemoryInjection:
        """按字符预算、数量和类型多样性选择最终注入项。"""
        if budget_chars <= 0 or item_limit <= 0 or not ranked_results:
            return MemoryInjection(
                omitted_ids=[result.id for result in ranked_results],
                budget_chars=max(0, budget_chars),
            )

        header = "Relevant Long-Term Memory:"
        lines = [header]
        selected = []
        omitted_ids = []
        type_counts = {}

        for result in ranked_results:
            if len(selected) >= item_limit:
                omitted_ids.append(result.id)
                continue
            if type_counts.get(result.type, 0) >= per_type_limit:
                omitted_ids.append(result.id)
                continue

            remaining = budget_chars - len("\n".join(lines)) - 1
            prefix = format_memory_prefix(result)
            if remaining <= len(prefix) + 24:
                omitted_ids.append(result.id)
                continue

            content_limit = min(320, remaining - len(prefix))
            line = prefix + truncate_memory_text(
                result.content,
                max_length=content_limit,
            )
            candidate_text = "\n".join(lines + [line])
            if len(candidate_text) > budget_chars:
                omitted_ids.append(result.id)
                continue

            lines.append(line)
            selected.append(result)
            type_counts[result.type] = type_counts.get(result.type, 0) + 1

        selected_ids = {result.id for result in selected}
        omitted_ids.extend(
            result.id
            for result in ranked_results
            if result.id not in selected_ids and result.id not in omitted_ids
        )
        context = "\n".join(lines) if selected else ""
        return MemoryInjection(
            context=context,
            selected=selected,
            omitted_ids=omitted_ids,
            used_chars=len(context),
            budget_chars=budget_chars,
        )


def memory_type_score(memory_type: str) -> float:
    """不同记忆类型的默认复用价值。"""
    return {
        "semantic": 1.0,
        "procedure": 0.95,
        "graph_fact": 0.9,
        "episode": 0.75,
    }.get(memory_type, 0.6)


def memory_confidence(result: MemoryRetrievalResult) -> float:
    """读取并限制来源置信度；没有显式置信度时使用中性值。"""
    value = result.metadata.get("confidence", 0.7)
    try:
        confidence = float(value)
    except (TypeError, ValueError):
        confidence = 0.7
    return max(0.0, min(1.0, confidence))


def memory_recency(
    result: MemoryRetrievalResult,
    now: datetime,
) -> float:
    """按更新时间做平滑衰减；30 天约为 0.5，越旧越低但不会直接归零。"""
    timestamp = (
        result.metadata.get("updated_at")
        or result.metadata.get("observed_at")
        or result.metadata.get("created_at")
    )
    parsed = parse_datetime(timestamp)
    if parsed is None:
        return 0.5
    age_seconds = max(0.0, (normalize_datetime(now) - parsed).total_seconds())
    age_days = age_seconds / 86400
    return 1.0 / (1.0 + age_days / 30.0)


def memory_session_score(
    result: MemoryRetrievalResult,
    current_session_id: str,
) -> float:
    """同 Session 的 Episode 优先，但跨 Session 记忆仍然可以参与。"""
    if not current_session_id:
        return 0.0
    return (
        1.0
        if result.metadata.get("session_id") == current_session_id
        else 0.0
    )


def format_memory_prefix(result: MemoryRetrievalResult) -> str:
    """生成带类型和冲突警告的注入前缀。"""
    status = f" status={result.status}" if result.status != ACTIVE else ""
    return f"- [{result.type}{status}] "


def parse_datetime(value) -> datetime:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        return normalize_datetime(
            datetime.fromisoformat(value.replace("Z", "+00:00"))
        )
    except ValueError:
        return None


def normalize_datetime(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)
