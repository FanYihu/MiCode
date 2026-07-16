import json

from micode.memory.procedural import ProceduralMemory
from micode.memory.skill_candidate import (
    APPROVED,
    DRAFT,
    PROMOTED,
    REJECTED,
    SkillCandidateStore,
    approve_skill_candidate,
    promote_skill_candidate,
    reject_skill_candidate,
    skill_candidate_from_procedure,
    skill_candidates_from_procedures,
    stable_skill_candidate_id,
)


def make_procedure() -> ProceduralMemory:
    return ProceduralMemory(
        id="procedure:update-cli-and-test",
        name="update-cli-and-test",
        description="Update CLI and run tests.",
        steps=["Read cli.py.", "Patch args.", "Run pytest."],
        when_to_use=["CLI behavior changes"],
        when_not_to_use=["No CLI work"],
        tags=["cli", "test"],
        source_episode_ids=["episode:run-1"],
        source_run_ids=["run-1"],
    )


def test_skill_candidate_from_procedure_keeps_sources_and_stays_draft():
    candidate = skill_candidate_from_procedure(make_procedure())

    assert candidate.id == "skill-candidate:update-cli-and-test"
    assert candidate.status == DRAFT
    assert candidate.source_procedure_ids == ["procedure:update-cli-and-test"]
    assert candidate.source_episode_ids == ["episode:run-1"]
    assert candidate.source_run_ids == ["run-1"]
    assert "## Steps" in candidate.content
    assert "1. Read cli.py." in candidate.content


def test_skill_candidate_store_upserts_without_overwriting_review_state(tmp_path):
    store = SkillCandidateStore(str(tmp_path / "candidates"))
    first = skill_candidate_from_procedure(make_procedure())
    store.upsert_many([first])
    approved = approve_skill_candidate(store, first.id, note="stable enough")

    second = skill_candidate_from_procedure(
        ProceduralMemory(
            id="procedure:update-cli-and-test",
            name="update-cli-and-test",
            description="Update CLI and run tests.",
            steps=["Run targeted tests."],
            tags=["pytest"],
            source_episode_ids=["episode:run-2"],
            source_run_ids=["run-2"],
        )
    )
    store.upsert_many([second])
    loaded = store.get(first.id)

    assert approved.status == APPROVED
    assert loaded.status == APPROVED
    assert loaded.review_notes == ["stable enough"]
    assert loaded.source_episode_ids == ["episode:run-1", "episode:run-2"]
    assert loaded.tags == ["cli", "test", "pytest"]


def test_approve_reject_and_promote_skill_candidate(tmp_path):
    store = SkillCandidateStore(str(tmp_path / "candidates"))
    candidate = skill_candidate_from_procedure(make_procedure())
    store.upsert_many([candidate])

    rejected = reject_skill_candidate(store, candidate.id, note="too specific")
    assert rejected.status == REJECTED

    approved = approve_skill_candidate(store, candidate.id, note="make it reusable")
    result = promote_skill_candidate(
        store,
        approved.id,
        skills_root=str(tmp_path / "skills"),
    )
    promoted = store.get(candidate.id)
    skill_path = tmp_path / "skills" / candidate.name / "SKILL.md"

    assert promoted.status == PROMOTED
    assert skill_path.read_text(encoding="utf-8") == candidate.content
    assert result["skill_path"] == str(skill_path)


def test_promote_requires_approval_by_default(tmp_path):
    store = SkillCandidateStore(str(tmp_path / "candidates"))
    candidate = skill_candidate_from_procedure(make_procedure())
    store.upsert_many([candidate])

    try:
        promote_skill_candidate(store, candidate.id, skills_root=str(tmp_path / "skills"))
    except ValueError as error:
        assert "approved" in str(error)
    else:
        raise AssertionError("promotion should require approval")


def test_skill_candidates_from_procedures_and_stable_id(tmp_path):
    candidates = skill_candidates_from_procedures([make_procedure()])
    store = SkillCandidateStore(str(tmp_path / "candidates"))
    store.upsert_many(candidates)
    data = json.loads(store.path_for(candidates[0].id).read_text(encoding="utf-8"))

    assert stable_skill_candidate_id("Update CLI + Test!") == (
        "skill-candidate:update-cli-test"
    )
    assert data["id"] == candidates[0].id
