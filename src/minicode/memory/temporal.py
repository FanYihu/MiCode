from datetime import datetime

from minicode.memory.session import utc_now_iso


ACTIVE = "active"
SUPERSEDED = "superseded"
CONFLICTING = "conflicting"


def resolve_temporal_conflicts(graph) -> dict:
    """解析图中的单值时序事实冲突，并返回本次图的状态统计。

    多值关系可以同时成立；单值关系按 observed_at、confidence 选出当前事实。
    如果时间和置信度都相同，则保留冲突，等待后续证据或人工 review。
    """
    groups = {}
    for edge in graph.edges:
        if not is_temporal_fact_edge(edge):
            continue
        if edge.properties.get("cardinality", "multi") != "single":
            edge.properties.setdefault("fact_status", ACTIVE)
            continue
        key = (edge.source_id, edge.relation)
        groups.setdefault(key, []).append(edge)

    for edges in groups.values():
        resolve_fact_group(edges)

    return temporal_status_counts(graph)


def resolve_fact_group(edges: list) -> None:
    """处理同一 subject + predicate 下的候选事实。"""
    if not edges:
        return

    ranked = sorted(edges, key=fact_rank, reverse=True)
    winner = ranked[0]
    tied = [
        edge
        for edge in ranked
        if fact_rank(edge) == fact_rank(winner)
        and edge.target_id != winner.target_id
    ]

    if tied:
        conflicting_ids = [winner.id] + [edge.id for edge in tied]
        for edge in ranked:
            if edge.id in conflicting_ids:
                edge.properties["fact_status"] = CONFLICTING
                edge.properties["conflicts_with"] = [
                    edge_id for edge_id in conflicting_ids if edge_id != edge.id
                ]
                edge.properties.pop("superseded_by", None)
                edge.properties.pop("valid_to", None)
            else:
                mark_superseded(edge, winner)
        return

    winner.properties["fact_status"] = ACTIVE
    winner.properties.pop("conflicts_with", None)
    winner.properties.pop("superseded_by", None)
    winner.properties.pop("valid_to", None)
    for edge in ranked[1:]:
        mark_superseded(edge, winner)


def mark_superseded(edge, winner) -> None:
    """把旧事实标为失效，同时保留它和替代事实的关系。"""
    edge.properties["fact_status"] = SUPERSEDED
    edge.properties["superseded_by"] = winner.id
    edge.properties["valid_to"] = (
        winner.properties.get("valid_from")
        or winner.properties.get("observed_at")
        or utc_now_iso()
    )
    edge.properties.pop("conflicts_with", None)


def is_temporal_fact_edge(edge) -> bool:
    """判断一条边是否是需要进行时序管理的知识事实。"""
    return bool(edge.properties.get("temporal_fact"))


def fact_rank(edge) -> tuple:
    """按观测时间和置信度为事实排序。"""
    observed_at = (
        edge.properties.get("observed_at")
        or edge.properties.get("valid_from")
        or edge.created_at
    )
    confidence = edge.properties.get("confidence", 0.0)
    try:
        confidence_value = float(confidence)
    except (TypeError, ValueError):
        confidence_value = 0.0
    return (timestamp_value(str(observed_at)), confidence_value)


def timestamp_value(value: str) -> float:
    """把 ISO 时间转成可比较值；非法时间按最早处理。"""
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp()
    except (TypeError, ValueError):
        return 0.0


def temporal_status_counts(graph) -> dict:
    """统计图中时序事实的状态。"""
    counts = {ACTIVE: 0, SUPERSEDED: 0, CONFLICTING: 0}
    for edge in graph.edges:
        if not is_temporal_fact_edge(edge):
            continue
        status = edge.properties.get("fact_status", ACTIVE)
        if status in counts:
            counts[status] += 1
    return counts
