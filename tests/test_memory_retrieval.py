from micode.memory.episodic import EpisodicMemory, EpisodicMemoryStore
from micode.memory.graph import MemoryGraph, MemoryGraphStore, MemoryNode, make_edge
from micode.memory.procedural import ProceduralMemory, ProceduralMemoryStore
from micode.memory.retrieval import (
    HybridMemoryRetriever,
    cosine_similarity,
    format_retrieved_memories,
    keyword_similarity,
)
from micode.memory.semantic import SemanticMemory, SemanticMemoryStore


def seed_memory(memory_dir) -> None:
    EpisodicMemoryStore(str(memory_dir)).upsert(
        EpisodicMemory(
            id="episode:run-1",
            session_id="session-1",
            run_id="run-1",
            task="给 CLI 增加 session 参数",
            outcome="验证通过",
            status="completed",
            tool_names=["read_file", "run_shell"],
        )
    )
    SemanticMemoryStore(str(memory_dir)).upsert_many(
        [
            SemanticMemory(
                id="semantic:micode-uses-pytest",
                fact="Micode uses pytest",
                subject="Micode",
                predicate="uses",
                object="pytest",
                confidence=0.9,
                source_episode_ids=["episode:run-1"],
                tags=["test"],
            ),
            SemanticMemory(
                id="semantic:micode-uses-old-model",
                fact="Micode uses_model old-model",
                subject="Micode",
                predicate="uses_model",
                object="old-model",
                source_episode_ids=["episode:run-0"],
            ),
        ]
    )
    ProceduralMemoryStore(str(memory_dir)).upsert_many(
        [
            ProceduralMemory(
                id="procedure:update-cli",
                name="update-cli",
                description="Update CLI behavior and run tests.",
                steps=["Read CLI code.", "Patch arguments.", "Run pytest."],
                tags=["cli", "test"],
                source_episode_ids=["episode:run-1"],
            )
        ]
    )
    graph = MemoryGraph(
        nodes=[
            MemoryNode(id="entity:micode", type="entity", label="Micode"),
            MemoryNode(id="entity:pytest", type="entity", label="pytest"),
            MemoryNode(id="entity:old-model", type="entity", label="old-model"),
            MemoryNode(
                id="semantic:micode-uses-pytest",
                type="semantic",
                label="Micode uses pytest",
            ),
        ],
        edges=[
            make_edge(
                "entity:micode",
                "entity:pytest",
                "uses",
                properties={
                    "temporal_fact": True,
                    "fact_status": "active",
                    "cardinality": "multi",
                    "source_memory_ids": ["semantic:micode-uses-pytest"],
                },
            ),
            make_edge(
                "entity:micode",
                "entity:old-model",
                "uses_model",
                properties={
                    "temporal_fact": True,
                    "fact_status": "superseded",
                    "cardinality": "single",
                    "source_memory_ids": ["semantic:micode-uses-old-model"],
                },
            ),
            make_edge(
                "semantic:micode-uses-pytest",
                "episode:run-1",
                "derived_from_episode",
            ),
        ],
    )
    MemoryGraphStore(str(memory_dir)).save(graph)


class FakeEmbeddingClient:
    def embed(self, texts):
        vectors = []
        for text in texts:
            normalized = text.lower()
            vectors.append(
                [
                    1.0 if "pytest" in normalized or "测试" in normalized else 0.0,
                    1.0 if "cli" in normalized else 0.0,
                ]
            )
        return vectors


def test_hybrid_retrieval_combines_keyword_vector_and_graph(tmp_path):
    memory_dir = tmp_path / "memory"
    seed_memory(memory_dir)
    retriever = HybridMemoryRetriever(
        str(memory_dir),
        embedding_client=FakeEmbeddingClient(),
    )

    results = retriever.retrieve("如何测试 CLI", limit=6)

    result_by_id = {result.id: result for result in results}
    assert "procedure:update-cli" in result_by_id
    assert "semantic:micode-uses-pytest" in result_by_id
    assert result_by_id["procedure:update-cli"].keyword_score > 0
    assert result_by_id["procedure:update-cli"].vector_score > 0
    assert result_by_id["semantic:micode-uses-pytest"].graph_score > 0


def test_retrieval_excludes_superseded_facts_by_default(tmp_path):
    memory_dir = tmp_path / "memory"
    seed_memory(memory_dir)
    retriever = HybridMemoryRetriever(str(memory_dir))

    default_results = retriever.retrieve("old-model", limit=10)
    history_results = retriever.retrieve(
        "old-model",
        limit=10,
        include_superseded=True,
    )

    assert all("old-model" not in result.content for result in default_results)
    assert any(result.status == "superseded" for result in history_results)


def test_retrieval_works_without_embedding_client(tmp_path):
    memory_dir = tmp_path / "memory"
    seed_memory(memory_dir)

    results = HybridMemoryRetriever(str(memory_dir)).retrieve("pytest")

    assert results
    assert results[0].keyword_score > 0
    assert results[0].vector_score == 0


def test_graph_traversal_recalls_neighbor_without_keyword_match(tmp_path):
    memory_dir = tmp_path / "memory"
    seed_memory(memory_dir)

    results = HybridMemoryRetriever(str(memory_dir)).retrieve("pytest", limit=10)
    episode = next(result for result in results if result.id == "episode:run-1")

    assert episode.keyword_score == 0
    assert episode.vector_score == 0
    assert episode.graph_score > 0


def test_similarity_helpers_handle_valid_and_invalid_inputs():
    assert keyword_similarity("pytest", "Micode uses pytest") > 0
    assert keyword_similarity("missing", "Micode uses pytest") == 0
    assert cosine_similarity([1.0, 0.0], [1.0, 0.0]) == 1.0
    assert cosine_similarity([1.0], [1.0, 0.0]) == 0.0


def test_format_retrieved_memories_marks_conflicts():
    from micode.memory.retrieval import MemoryRetrievalResult

    text = format_retrieved_memories(
        [
            MemoryRetrievalResult(
                id="edge:1",
                type="graph_fact",
                content="Micode uses_model model-a",
                score=0.8,
                status="conflicting",
            )
        ]
    )

    assert "Relevant Long-Term Memory:" in text
    assert "status=conflicting" in text
