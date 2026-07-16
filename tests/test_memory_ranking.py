from datetime import datetime, timezone

from micode.memory.ranking import MemoryRankingPolicy
from micode.memory.retrieval import MemoryRetrievalResult


def make_result(
    memory_id: str,
    memory_type: str = "semantic",
    score: float = 0.7,
    confidence: float = 0.7,
    updated_at: str = "2026-06-01T00:00:00+00:00",
    session_id: str = "",
    status: str = "active",
    content: str = "Micode uses pytest",
) -> MemoryRetrievalResult:
    return MemoryRetrievalResult(
        id=memory_id,
        type=memory_type,
        content=content,
        score=score,
        keyword_score=score,
        status=status,
        metadata={
            "confidence": confidence,
            "updated_at": updated_at,
            "session_id": session_id,
        },
    )


def test_ranking_prefers_confident_recent_same_session_memory():
    policy = MemoryRankingPolicy()
    old = make_result(
        "semantic:old",
        confidence=0.5,
        updated_at="2025-01-01T00:00:00+00:00",
        session_id="other-session",
    )
    current = make_result(
        "semantic:current",
        confidence=0.95,
        updated_at="2026-06-09T00:00:00+00:00",
        session_id="session-1",
    )

    ranked = policy.rank(
        [old, current],
        current_session_id="session-1",
        now=datetime(2026, 6, 9, tzinfo=timezone.utc),
    )

    assert [result.id for result in ranked] == [
        "semantic:current",
        "semantic:old",
    ]
    assert ranked[0].ranking_details["confidence"] == 0.95
    assert ranked[0].ranking_details["session"] == 1.0
    assert ranked[0].ranking_details["recency"] == 1.0


def test_ranking_keeps_conflicting_memory_but_applies_penalty():
    policy = MemoryRankingPolicy()
    active = make_result("semantic:active")
    conflicting = make_result("semantic:conflict", status="conflicting")

    ranked = policy.rank(
        [conflicting, active],
        now=datetime(2026, 6, 9, tzinfo=timezone.utc),
    )

    assert ranked[0].id == "semantic:active"
    assert ranked[1].id == "semantic:conflict"
    assert ranked[1].ranking_details["status_multiplier"] == 0.75


def test_ranking_uses_type_value_when_other_signals_are_equal():
    policy = MemoryRankingPolicy()
    episode = make_result("episode:1", memory_type="episode")
    semantic = make_result("semantic:1", memory_type="semantic")

    ranked = policy.rank(
        [episode, semantic],
        now=datetime(2026, 6, 9, tzinfo=timezone.utc),
    )

    assert ranked[0].id == "semantic:1"


def test_injection_respects_budget_item_and_type_limits():
    policy = MemoryRankingPolicy()
    ranked = policy.rank(
        [
            make_result(
                f"semantic:{index}",
                content=f"fact {index} " + "x" * 120,
                score=0.9 - index * 0.01,
            )
            for index in range(6)
        ],
        now=datetime(2026, 6, 9, tzinfo=timezone.utc),
    )

    injection = policy.prepare_injection(
        ranked,
        budget_chars=240,
        item_limit=4,
        per_type_limit=2,
    )

    assert len(injection.context) <= 240
    assert len(injection.selected) <= 2
    assert injection.omitted_ids
    assert injection.used_chars == len(injection.context)


def test_injection_marks_conflicting_fact_in_prompt():
    policy = MemoryRankingPolicy()
    ranked = policy.rank(
        [
            make_result(
                "edge:conflict",
                memory_type="graph_fact",
                status="conflicting",
            )
        ],
        now=datetime(2026, 6, 9, tzinfo=timezone.utc),
    )

    injection = policy.prepare_injection(ranked, budget_chars=300)

    assert "status=conflicting" in injection.context


def test_zero_budget_omits_all_memories():
    result = make_result("semantic:1")

    injection = MemoryRankingPolicy().prepare_injection(
        [result],
        budget_chars=0,
    )

    assert injection.context == ""
    assert injection.selected == []
    assert injection.omitted_ids == ["semantic:1"]
