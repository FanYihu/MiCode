from micode.memory.graph import MemoryGraph, MemoryGraphStore, make_edge
from micode.memory.temporal import (
    ACTIVE,
    CONFLICTING,
    SUPERSEDED,
    resolve_temporal_conflicts,
    temporal_status_counts,
)


def temporal_edge(
    target_id: str,
    observed_at: str,
    confidence: float = 0.9,
    cardinality: str = "single",
):
    return make_edge(
        "entity:micode",
        target_id,
        "uses_model",
        properties={
            "temporal_fact": True,
            "fact_status": ACTIVE,
            "observed_at": observed_at,
            "valid_from": observed_at,
            "cardinality": cardinality,
            "confidence": confidence,
        },
    )


def test_newer_single_value_fact_supersedes_old_fact():
    old = temporal_edge("entity:model-a", "2026-06-01T00:00:00+00:00")
    new = temporal_edge("entity:model-b", "2026-06-09T00:00:00+00:00")
    graph = MemoryGraph(edges=[old, new])

    counts = resolve_temporal_conflicts(graph)

    assert old.properties["fact_status"] == SUPERSEDED
    assert old.properties["superseded_by"] == new.id
    assert old.properties["valid_to"] == "2026-06-09T00:00:00+00:00"
    assert new.properties["fact_status"] == ACTIVE
    assert counts == {ACTIVE: 1, SUPERSEDED: 1, CONFLICTING: 0}


def test_multi_value_facts_remain_active():
    first = temporal_edge(
        "entity:pytest",
        "2026-06-01T00:00:00+00:00",
        cardinality="multi",
    )
    first.relation = "uses"
    second = temporal_edge(
        "entity:ruff",
        "2026-06-09T00:00:00+00:00",
        cardinality="multi",
    )
    second.relation = "uses"
    graph = MemoryGraph(edges=[first, second])

    resolve_temporal_conflicts(graph)

    assert first.properties["fact_status"] == ACTIVE
    assert second.properties["fact_status"] == ACTIVE


def test_equal_rank_single_value_facts_are_marked_conflicting():
    first = temporal_edge("entity:model-a", "2026-06-09T00:00:00+00:00")
    second = temporal_edge("entity:model-b", "2026-06-09T00:00:00+00:00")
    graph = MemoryGraph(edges=[first, second])

    resolve_temporal_conflicts(graph)

    assert first.properties["fact_status"] == CONFLICTING
    assert second.properties["fact_status"] == CONFLICTING
    assert first.properties["conflicts_with"] == [second.id]
    assert second.properties["conflicts_with"] == [first.id]


def test_higher_confidence_breaks_same_time_tie():
    weaker = temporal_edge(
        "entity:model-a",
        "2026-06-09T00:00:00+00:00",
        confidence=0.6,
    )
    stronger = temporal_edge(
        "entity:model-b",
        "2026-06-09T00:00:00+00:00",
        confidence=0.95,
    )
    graph = MemoryGraph(edges=[weaker, stronger])

    resolve_temporal_conflicts(graph)

    assert weaker.properties["fact_status"] == SUPERSEDED
    assert stronger.properties["fact_status"] == ACTIVE


def test_graph_store_resolves_conflicts_across_separate_runs(tmp_path):
    store = MemoryGraphStore(str(tmp_path / "memory"))
    old = temporal_edge("entity:model-a", "2026-06-01T00:00:00+00:00")
    new = temporal_edge("entity:model-b", "2026-06-09T00:00:00+00:00")

    store.upsert_graph(MemoryGraph(edges=[old]))
    saved = store.upsert_graph(MemoryGraph(edges=[new]))

    statuses = {edge.target_id: edge.properties["fact_status"] for edge in saved.edges}
    assert statuses == {
        "entity:model-a": SUPERSEDED,
        "entity:model-b": ACTIVE,
    }
    assert temporal_status_counts(saved)[SUPERSEDED] == 1
