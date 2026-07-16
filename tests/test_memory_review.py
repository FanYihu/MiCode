import json

from minicode.cli import run_memory_review
from minicode.memory.context import SessionSummary, SessionSummaryStore
from minicode.memory.episodic import EpisodicMemory, EpisodicMemoryStore
from minicode.memory.graph import MemoryGraph, MemoryGraphStore, MemoryNode, make_edge
from minicode.memory.procedural import ProceduralMemory, ProceduralMemoryStore
from minicode.memory.review import review_memory_system
from minicode.memory.semantic import SemanticMemory, SemanticMemoryStore
from minicode.memory.session import SessionMessage, SessionMessageStore, SessionStore
from minicode.memory.skill_candidate import (
    APPROVED,
    PROMOTED,
    SkillCandidateStore,
    skill_candidate_from_procedure,
)
from minicode.memory.working import WorkingMemory, WorkingMemoryStore


def seed_healthy_memory(session_dir, memory_dir) -> None:
    session_store = SessionStore(str(session_dir))
    session = session_store.create(
        title="MiniCode 学习",
        session_id="session-1",
    )
    session.add_run("run-1")
    session_store.save(session)
    SessionMessageStore(str(session_dir)).append_messages(
        "session-1",
        [
            SessionMessage(
                id="message-1",
                session_id="session-1",
                run_id="run-1",
                role="user",
                type="task",
                content="使用 pytest 测试 CLI",
            )
        ],
    )
    WorkingMemoryStore(str(session_dir)).save(
        WorkingMemory(session_id="session-1", current_goal="使用 pytest 测试 CLI")
    )
    SessionSummaryStore(str(session_dir)).save(
        SessionSummary(session_id="session-1", summary="已完成 session 记忆闭环。")
    )

    episode = EpisodicMemory(
        id="episode:run-1",
        session_id="session-1",
        run_id="run-1",
        task="使用 pytest 测试 CLI",
        outcome="测试通过",
        status="completed",
        tool_names=["run_shell"],
    )
    semantic = SemanticMemory(
        id="semantic:minicode-uses-pytest",
        fact="MiniCode uses pytest",
        subject="MiniCode",
        predicate="uses",
        object="pytest",
        confidence=0.9,
        source_episode_ids=[episode.id],
        tags=["test"],
    )
    procedure = ProceduralMemory(
        id="procedure:test-cli",
        name="test-cli",
        description="Test CLI with pytest.",
        steps=["Run pytest."],
        source_episode_ids=[episode.id],
        tags=["test"],
    )
    EpisodicMemoryStore(str(memory_dir)).upsert(episode)
    SemanticMemoryStore(str(memory_dir)).upsert_many([semantic])
    ProceduralMemoryStore(str(memory_dir)).upsert_many([procedure])
    candidate = skill_candidate_from_procedure(procedure)
    candidate.status = APPROVED
    candidate.review_notes = ["Reusable pytest CLI flow."]
    SkillCandidateStore(str(memory_dir.parent / "skill-candidates")).upsert_many(
        [candidate]
    )

    graph = MemoryGraph(
        nodes=[
            MemoryNode(id="session:session-1", type="session", label="session-1"),
            MemoryNode(id="run:run-1", type="run", label="run-1"),
            MemoryNode(id=episode.id, type="episode", label=episode.task),
            MemoryNode(id=semantic.id, type="semantic", label=semantic.fact),
            MemoryNode(id=procedure.id, type="procedure", label=procedure.name),
            MemoryNode(id="entity:minicode", type="entity", label="MiniCode"),
            MemoryNode(id="entity:pytest", type="entity", label="pytest"),
        ],
        edges=[
            make_edge(episode.id, "session:session-1", "belongs_to_session"),
            make_edge(episode.id, "run:run-1", "records_run"),
            make_edge(semantic.id, episode.id, "derived_from_episode"),
            make_edge(procedure.id, episode.id, "derived_from_episode"),
            make_edge(
                "entity:minicode",
                "entity:pytest",
                "uses",
                properties={
                    "temporal_fact": True,
                    "fact_status": "active",
                    "cardinality": "multi",
                    "source_memory_ids": [semantic.id],
                    "source_episode_ids": [episode.id],
                },
            ),
            make_edge("entity:minicode", semantic.id, "supported_by_memory"),
            make_edge("entity:pytest", semantic.id, "supported_by_memory"),
        ],
    )
    MemoryGraphStore(str(memory_dir)).save(graph)


def test_review_memory_system_reports_healthy_pipeline(tmp_path):
    session_dir = tmp_path / "sessions"
    memory_dir = tmp_path / "memory"
    seed_healthy_memory(session_dir, memory_dir)

    report = review_memory_system(
        str(session_dir),
        str(memory_dir),
        skill_candidate_dir=str(tmp_path / "skill-candidates"),
        sample_query="pytest",
        memory_budget_chars=600,
    )

    data = report.to_dict()
    assert data["ok"] is True
    assert data["summary"]["sessions"] == 1
    assert data["summary"]["session_messages"] == 1
    assert data["summary"]["working_memories"] == 1
    assert data["summary"]["session_summaries"] == 1
    assert data["summary"]["episodes"] == 1
    assert data["summary"]["semantic_memories"] == 1
    assert data["summary"]["procedural_memories"] == 1
    assert data["summary"]["skill_candidates"] == 1
    assert data["summary"]["temporal_facts"]["active"] == 1
    assert data["retrieval_preview"]["candidate_count"] > 0
    assert data["retrieval_preview"]["selected_ids"]
    assert data["issues"] == []


def test_review_memory_system_detects_broken_skill_candidate(tmp_path):
    candidate_dir = tmp_path / "skill-candidates"
    candidate = skill_candidate_from_procedure(
        ProceduralMemory(
            id="procedure:missing",
            name="missing-procedure",
            description="Broken candidate.",
            steps=["Do something."],
            source_episode_ids=["episode:missing"],
            source_run_ids=["run-missing"],
        )
    )
    candidate.status = "mystery"
    SkillCandidateStore(str(candidate_dir)).upsert_many([candidate])

    report = review_memory_system(
        memory_dir=str(tmp_path / "memory"),
        skill_candidate_dir=str(candidate_dir),
    )
    codes = [issue.code for issue in report.issues]

    assert report.ok is False
    assert "skill_candidate_invalid_status" in codes
    assert "skill_candidate_missing_source_procedure" in codes
    assert "skill_candidate_missing_source_episode" in codes


def test_review_memory_system_detects_promoted_candidate_without_skill(tmp_path):
    memory_dir = tmp_path / "memory"
    candidate_dir = tmp_path / "skill-candidates"
    episode = EpisodicMemory(
        id="episode:run-1",
        session_id="session-1",
        run_id="run-1",
        task="test",
        outcome="done",
        status="completed",
    )
    procedure = ProceduralMemory(
        id="procedure:test",
        name="test-skill",
        description="Test skill.",
        steps=["Run test."],
        source_episode_ids=[episode.id],
        source_run_ids=["run-1"],
    )
    EpisodicMemoryStore(str(memory_dir)).upsert(episode)
    ProceduralMemoryStore(str(memory_dir)).upsert_many([procedure])
    candidate = skill_candidate_from_procedure(procedure)
    candidate.status = PROMOTED
    SkillCandidateStore(str(candidate_dir)).upsert_many([candidate])

    report = review_memory_system(
        memory_dir=str(memory_dir),
        skill_candidate_dir=str(candidate_dir),
        skills_root=str(tmp_path / "skills"),
    )

    assert any(
        issue.code == "promoted_skill_candidate_missing_skill"
        for issue in report.issues
    )


def test_review_memory_system_detects_broken_sources_and_graph_edges(tmp_path):
    memory_dir = tmp_path / "memory"
    SemanticMemoryStore(str(memory_dir)).upsert_many(
        [
            SemanticMemory(
                id="semantic:broken",
                fact="Broken fact",
                subject="project",
                predicate="uses",
                object="missing",
                source_episode_ids=["episode:missing"],
            )
        ]
    )
    graph = MemoryGraph(
        nodes=[MemoryNode(id="entity:project", type="entity", label="project")],
        edges=[
            make_edge(
                "entity:project",
                "entity:missing",
                "uses",
                properties={
                    "temporal_fact": True,
                    "fact_status": "mystery",
                },
            )
        ],
    )
    MemoryGraphStore(str(memory_dir)).save(graph)

    report = review_memory_system(memory_dir=str(memory_dir))
    codes = [issue.code for issue in report.issues]

    assert report.ok is False
    assert "semantic_missing_source_episode" in codes
    assert "graph_edge_missing_target" in codes
    assert "invalid_temporal_fact_status" in codes
    assert report.summary["issues"]["errors"] == 3


def test_review_memory_system_warns_when_sample_query_retrieves_nothing(tmp_path):
    memory_dir = tmp_path / "memory"
    EpisodicMemoryStore(str(memory_dir)).upsert(
        EpisodicMemory(
            id="episode:run-1",
            session_id="session-1",
            run_id="run-1",
            task="unrelated task",
            outcome="done",
            status="completed",
        )
    )

    report = review_memory_system(
        memory_dir=str(memory_dir),
        sample_query="pytest",
    )

    assert report.ok is True
    assert any(issue.code == "retrieval_returned_empty" for issue in report.issues)


def test_run_memory_review_returns_json_ready_dict(tmp_path):
    session_dir = tmp_path / "sessions"
    memory_dir = tmp_path / "memory"
    seed_healthy_memory(session_dir, memory_dir)

    report = run_memory_review(
        session_dir=str(session_dir),
        memory_dir=str(memory_dir),
        sample_query="pytest",
    )

    assert report["ok"] is True
    assert report["retrieval_preview"]["sample_query"] == "pytest"
    json.dumps(report, ensure_ascii=False)
