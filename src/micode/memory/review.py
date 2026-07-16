from dataclasses import dataclass, field
from pathlib import Path

from micode.memory.context import SessionSummaryStore
from micode.memory.episodic import EpisodicMemoryStore
from micode.memory.graph import MemoryGraph, MemoryGraphStore
from micode.memory.procedural import ProceduralMemoryStore
from micode.memory.ranking import MemoryRankingPolicy
from micode.memory.retrieval import HybridMemoryRetriever
from micode.memory.semantic import SemanticMemoryStore
from micode.memory.session import SessionMessageStore, SessionStore
from micode.memory.skill_candidate import (
    PROMOTED,
    SkillCandidateStore,
    VALID_SKILL_CANDIDATE_STATUSES,
)
from micode.memory.temporal import (
    ACTIVE,
    CONFLICTING,
    SUPERSEDED,
    temporal_status_counts,
)
from micode.memory.working import WorkingMemoryStore


@dataclass
class MemoryReviewIssue:
    """MemoryReviewIssue 描述一次记忆系统体检发现的问题。"""

    severity: str
    code: str
    message: str
    subject_id: str = ""
    details: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        """转成可保存或 CLI 输出的 JSON dict。"""
        return {
            "severity": self.severity,
            "code": self.code,
            "message": self.message,
            "subject_id": self.subject_id,
            "details": self.details,
        }


@dataclass
class MemoryReviewReport:
    """MemoryReviewReport 汇总记忆系统的完整性和检索可用性。"""

    summary: dict = field(default_factory=dict)
    issues: list[MemoryReviewIssue] = field(default_factory=list)
    retrieval_preview: dict = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        """没有 error 级问题时认为 review 通过。"""
        return not any(issue.severity == "error" for issue in self.issues)

    def to_dict(self) -> dict:
        """转成 CLI 友好的 JSON dict。"""
        return {
            "ok": self.ok,
            "summary": self.summary,
            "issues": [issue.to_dict() for issue in self.issues],
            "retrieval_preview": self.retrieval_preview,
        }


def review_memory_system(
    session_dir: str = ".micode/sessions",
    memory_dir: str = ".micode/memory",
    skill_candidate_dir: str = ".micode/skill-candidates",
    skills_root: str = ".micode/skills",
    sample_query: str = "",
    memory_budget_chars: int = 1800,
) -> MemoryReviewReport:
    """执行一次记忆系统 review。

    Review 只读取现有文件，不修改 memory；它检查引用完整性，并可选跑一遍检索注入。
    """
    skill_candidate_dir = resolve_skill_candidate_dir(memory_dir, skill_candidate_dir)
    sessions = SessionStore(session_dir).list_sessions(limit=10_000)
    episodes = EpisodicMemoryStore(memory_dir).load_all()
    semantics = SemanticMemoryStore(memory_dir).load_all()
    procedures = ProceduralMemoryStore(memory_dir).load_all()
    skill_candidates = SkillCandidateStore(skill_candidate_dir).load_all()
    graph = MemoryGraphStore(memory_dir).load()

    session_ids = {session.id for session in sessions}
    episode_ids = {episode.id for episode in episodes}
    semantic_ids = {memory.id for memory in semantics}
    procedure_ids = {memory.id for memory in procedures}
    run_ids = {episode.run_id for episode in episodes if episode.run_id}
    graph_node_ids = {node.id for node in graph.nodes}
    graph_edge_ids = {edge.id for edge in graph.edges}

    issues = []
    issues.extend(review_sessions(session_dir, sessions, episode_ids))
    issues.extend(review_episodes(episodes, session_ids, graph_node_ids))
    issues.extend(review_semantic_memories(semantics, episode_ids, graph_node_ids))
    issues.extend(review_procedural_memories(procedures, episode_ids, graph_node_ids))
    issues.extend(
        review_skill_candidates(
            skill_candidates,
            procedure_ids=procedure_ids,
            episode_ids=episode_ids,
            run_ids=run_ids,
            skills_root=skills_root,
        )
    )
    issues.extend(
        review_graph(
            graph,
            episode_ids=episode_ids,
            semantic_ids=semantic_ids,
            procedure_ids=procedure_ids,
        )
    )

    retrieval_preview = {}
    if sample_query:
        retrieval_preview = run_retrieval_preview(
            sample_query,
            memory_dir,
            memory_budget_chars,
        )
        if retrieval_preview.get("candidate_count", 0) == 0 and (
            episodes or semantics or procedures or graph.nodes
        ):
            issues.append(
                MemoryReviewIssue(
                    severity="warning",
                    code="retrieval_returned_empty",
                    message="Sample query did not retrieve any long-term memory.",
                    details={"sample_query": sample_query},
                )
            )

    summary = {
        "sessions": len(sessions),
        "session_messages": count_session_messages(session_dir, sessions),
        "working_memories": count_existing_session_files(
            session_dir,
            sessions,
            suffix=".working_memory.json",
        ),
        "session_summaries": count_existing_session_files(
            session_dir,
            sessions,
            suffix=".summary.json",
        ),
        "episodes": len(episodes),
        "semantic_memories": len(semantics),
        "procedural_memories": len(procedures),
        "skill_candidates": len(skill_candidates),
        "graph_nodes": len(graph_node_ids),
        "graph_edges": len(graph_edge_ids),
        "temporal_facts": temporal_status_counts(graph),
        "issues": {
            "errors": sum(1 for issue in issues if issue.severity == "error"),
            "warnings": sum(1 for issue in issues if issue.severity == "warning"),
        },
    }

    return MemoryReviewReport(
        summary=summary,
        issues=issues,
        retrieval_preview=retrieval_preview,
    )


def resolve_skill_candidate_dir(memory_dir: str, skill_candidate_dir: str) -> str:
    """memory_dir 被重定向时，默认 candidate 目录跟着放到同级。"""
    if (
        skill_candidate_dir == ".micode/skill-candidates"
        and memory_dir != ".micode/memory"
    ):
        return str(Path(memory_dir).parent / "skill-candidates")
    return skill_candidate_dir


def review_sessions(
    session_dir: str,
    sessions: list,
    episode_ids: set,
) -> list[MemoryReviewIssue]:
    """检查 Session 相关文件和 run -> episode 链路。"""
    issues = []
    message_store = SessionMessageStore(session_dir)
    working_store = WorkingMemoryStore(session_dir)
    summary_store = SessionSummaryStore(session_dir)

    for session in sessions:
        if not message_store.path_for(session.id).exists():
            issues.append(
                MemoryReviewIssue(
                    severity="warning",
                    code="missing_session_messages",
                    message="Session has no message history file.",
                    subject_id=session.id,
                )
            )
        if not working_store.path_for(session.id).exists():
            issues.append(
                MemoryReviewIssue(
                    severity="warning",
                    code="missing_working_memory",
                    message="Session has no working memory file.",
                    subject_id=session.id,
                )
            )
        if not summary_store.path_for(session.id).exists():
            issues.append(
                MemoryReviewIssue(
                    severity="warning",
                    code="missing_session_summary",
                    message="Session has no compressed summary file.",
                    subject_id=session.id,
                )
            )
        for run_id in session.run_ids:
            episode_id = f"episode:{run_id}"
            if episode_id not in episode_ids:
                issues.append(
                    MemoryReviewIssue(
                        severity="warning",
                        code="missing_episode_for_run",
                        message="Session run has no episodic memory.",
                        subject_id=run_id,
                        details={"expected_episode_id": episode_id},
                    )
                )
    return issues


def review_episodes(
    episodes: list,
    session_ids: set,
    graph_node_ids: set,
) -> list[MemoryReviewIssue]:
    """检查 Episode 是否能回到 Session 和 Graph。"""
    issues = []
    for episode in episodes:
        if episode.session_id and session_ids and episode.session_id not in session_ids:
            issues.append(
                MemoryReviewIssue(
                    severity="warning",
                    code="episode_missing_session",
                    message="Episode references a session that was not found.",
                    subject_id=episode.id,
                    details={"session_id": episode.session_id},
                )
            )
        if graph_node_ids and episode.id not in graph_node_ids:
            issues.append(
                MemoryReviewIssue(
                    severity="warning",
                    code="episode_missing_graph_node",
                    message="Episode is not represented as a graph node.",
                    subject_id=episode.id,
                )
            )
    return issues


def review_semantic_memories(
    memories: list,
    episode_ids: set,
    graph_node_ids: set,
) -> list[MemoryReviewIssue]:
    """检查 Semantic Memory 的来源和图节点。"""
    issues = []
    for memory in memories:
        missing_sources = [
            episode_id
            for episode_id in memory.source_episode_ids
            if episode_id not in episode_ids
        ]
        if missing_sources:
            issues.append(
                MemoryReviewIssue(
                    severity="error",
                    code="semantic_missing_source_episode",
                    message="Semantic memory references missing source episodes.",
                    subject_id=memory.id,
                    details={"missing_episode_ids": missing_sources},
                )
            )
        if graph_node_ids and memory.id not in graph_node_ids:
            issues.append(
                MemoryReviewIssue(
                    severity="warning",
                    code="semantic_missing_graph_node",
                    message="Semantic memory is not represented as a graph node.",
                    subject_id=memory.id,
                )
            )
    return issues


def review_procedural_memories(
    memories: list,
    episode_ids: set,
    graph_node_ids: set,
) -> list[MemoryReviewIssue]:
    """检查 Procedural Memory 的来源和图节点。"""
    issues = []
    for memory in memories:
        missing_sources = [
            episode_id
            for episode_id in memory.source_episode_ids
            if episode_id not in episode_ids
        ]
        if missing_sources:
            issues.append(
                MemoryReviewIssue(
                    severity="error",
                    code="procedure_missing_source_episode",
                    message="Procedural memory references missing source episodes.",
                    subject_id=memory.id,
                    details={"missing_episode_ids": missing_sources},
                )
            )
        if graph_node_ids and memory.id not in graph_node_ids:
            issues.append(
                MemoryReviewIssue(
                    severity="warning",
                    code="procedure_missing_graph_node",
                    message="Procedural memory is not represented as a graph node.",
                    subject_id=memory.id,
                )
            )
    return issues


def review_skill_candidates(
    candidates: list,
    procedure_ids: set,
    episode_ids: set,
    run_ids: set,
    skills_root: str = ".micode/skills",
) -> list[MemoryReviewIssue]:
    """检查 Skill Candidate 的来源、状态和 promoted 结果。"""
    issues = []
    root = Path(skills_root)
    for candidate in candidates:
        if candidate.status not in VALID_SKILL_CANDIDATE_STATUSES:
            issues.append(
                MemoryReviewIssue(
                    severity="error",
                    code="skill_candidate_invalid_status",
                    message="Skill candidate has an invalid status.",
                    subject_id=candidate.id,
                    details={"status": candidate.status},
                )
            )

        missing_procedures = [
            procedure_id
            for procedure_id in candidate.source_procedure_ids
            if procedure_id not in procedure_ids
        ]
        if missing_procedures:
            issues.append(
                MemoryReviewIssue(
                    severity="error",
                    code="skill_candidate_missing_source_procedure",
                    message="Skill candidate references missing source procedures.",
                    subject_id=candidate.id,
                    details={"missing_procedure_ids": missing_procedures},
                )
            )

        missing_episodes = [
            episode_id
            for episode_id in candidate.source_episode_ids
            if episode_id not in episode_ids
        ]
        if missing_episodes:
            issues.append(
                MemoryReviewIssue(
                    severity="error",
                    code="skill_candidate_missing_source_episode",
                    message="Skill candidate references missing source episodes.",
                    subject_id=candidate.id,
                    details={"missing_episode_ids": missing_episodes},
                )
            )

        missing_runs = [
            run_id
            for run_id in candidate.source_run_ids
            if run_ids and run_id not in run_ids
        ]
        if missing_runs:
            issues.append(
                MemoryReviewIssue(
                    severity="warning",
                    code="skill_candidate_missing_source_run",
                    message="Skill candidate references source runs not found in episodes.",
                    subject_id=candidate.id,
                    details={"missing_run_ids": missing_runs},
                )
            )

        if candidate.status == PROMOTED:
            skill_path = root / candidate.name / "SKILL.md"
            if not skill_path.exists():
                issues.append(
                    MemoryReviewIssue(
                        severity="error",
                        code="promoted_skill_candidate_missing_skill",
                        message="Promoted skill candidate has no matching SKILL.md.",
                        subject_id=candidate.id,
                        details={"expected_path": str(skill_path)},
                    )
                )

        if candidate.status != PROMOTED and not candidate.review_notes:
            issues.append(
                MemoryReviewIssue(
                    severity="warning",
                    code="skill_candidate_missing_review_notes",
                    message="Skill candidate has not been reviewed yet.",
                    subject_id=candidate.id,
                )
            )

    return issues


def review_graph(
    graph: MemoryGraph,
    episode_ids: set,
    semantic_ids: set,
    procedure_ids: set,
) -> list[MemoryReviewIssue]:
    """检查 Graph 引用、时序状态和 memory 覆盖。"""
    issues = []
    node_ids = {node.id for node in graph.nodes}
    for edge in graph.edges:
        if edge.source_id not in node_ids:
            issues.append(
                MemoryReviewIssue(
                    severity="error",
                    code="graph_edge_missing_source",
                    message="Graph edge source node is missing.",
                    subject_id=edge.id,
                    details={"source_id": edge.source_id},
                )
            )
        if edge.target_id not in node_ids:
            issues.append(
                MemoryReviewIssue(
                    severity="error",
                    code="graph_edge_missing_target",
                    message="Graph edge target node is missing.",
                    subject_id=edge.id,
                    details={"target_id": edge.target_id},
                )
            )
        issues.extend(review_temporal_edge(edge))

    node_ids = {node.id for node in graph.nodes}
    for memory_id in episode_ids | semantic_ids | procedure_ids:
        if graph.nodes and memory_id not in node_ids:
            issues.append(
                MemoryReviewIssue(
                    severity="warning",
                    code="memory_not_indexed_in_graph",
                    message="Memory exists on disk but is not indexed in graph.",
                    subject_id=memory_id,
                )
            )
    return issues


def review_temporal_edge(edge) -> list[MemoryReviewIssue]:
    """检查时序事实边的状态字段是否完整。"""
    if not edge.properties.get("temporal_fact"):
        return []

    issues = []
    status = edge.properties.get("fact_status", ACTIVE)
    if status not in {ACTIVE, SUPERSEDED, CONFLICTING}:
        issues.append(
            MemoryReviewIssue(
                severity="error",
                code="invalid_temporal_fact_status",
                message="Temporal fact has an invalid status.",
                subject_id=edge.id,
                details={"fact_status": status},
            )
        )
    if status == SUPERSEDED and not edge.properties.get("superseded_by"):
        issues.append(
            MemoryReviewIssue(
                severity="warning",
                code="superseded_fact_missing_replacement",
                message="Superseded fact does not record superseded_by.",
                subject_id=edge.id,
            )
        )
    if status == CONFLICTING and not edge.properties.get("conflicts_with"):
        issues.append(
            MemoryReviewIssue(
                severity="warning",
                code="conflicting_fact_missing_peer",
                message="Conflicting fact does not record conflicts_with.",
                subject_id=edge.id,
            )
        )
    return issues


def run_retrieval_preview(
    sample_query: str,
    memory_dir: str,
    memory_budget_chars: int,
) -> dict:
    """用 sample query 干跑召回、精排和注入预算。"""
    candidates = HybridMemoryRetriever(memory_dir=memory_dir).retrieve(
        sample_query,
        limit=24,
    )
    ranked = MemoryRankingPolicy().rank(candidates)
    injection = MemoryRankingPolicy().prepare_injection(
        ranked,
        budget_chars=memory_budget_chars,
    )
    return {
        "sample_query": sample_query,
        "candidate_count": len(candidates),
        "selected_count": len(injection.selected),
        "selected_ids": [result.id for result in injection.selected],
        "omitted_ids": injection.omitted_ids,
        "used_chars": injection.used_chars,
        "budget_chars": injection.budget_chars,
        "top_results": [
            {
                "id": result.id,
                "type": result.type,
                "score": result.score,
                "ranking_score": result.ranking_score,
                "status": result.status,
            }
            for result in ranked[:5]
        ],
    }


def count_session_messages(session_dir: str, sessions: list) -> int:
    """统计所有 Session 消息数量。"""
    store = SessionMessageStore(session_dir)
    total = 0
    for session in sessions:
        total += len(store.load_messages(session.id))
    return total


def count_existing_session_files(
    session_dir: str,
    sessions: list,
    suffix: str,
) -> int:
    """统计指定 session 派生文件数量。"""
    root = Path(session_dir)
    return sum(
        1
        for session in sessions
        if (root / f"{session.id}{suffix}").exists()
    )
