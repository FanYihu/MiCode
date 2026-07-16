import json

from minicode.memory.episodic import EpisodicMemory
from minicode.memory.graph import (
    MemoryEdge,
    MemoryGraph,
    MemoryGraphStore,
    MemoryNode,
    build_memory_graph,
    make_edge,
    stable_edge_id,
)
from minicode.memory.entity import (
    EntityRelationExtraction,
    KnowledgeEntity,
    KnowledgeRelation,
)
from minicode.memory.procedural import ProceduralMemory
from minicode.memory.semantic import SemanticMemory


def make_episode() -> EpisodicMemory:
    return EpisodicMemory(
        id="episode:run-1",
        session_id="session-1",
        run_id="run-1",
        task="给 CLI 增加 session 参数",
        outcome="完成并测试通过",
        status="completed",
        tool_names=["read_file", "replace_text", "run_shell"],
        created_at="2026-06-08T00:00:00+00:00",
        updated_at="2026-06-08T00:00:03+00:00",
    )


def test_memory_node_and_edge_round_trip():
    node = MemoryNode(
        id="semantic:project-uses-pytest",
        type="semantic",
        label="project uses pytest",
        properties={"confidence": 0.9},
    )
    edge = make_edge(node.id, "episode:run-1", "derived_from_episode")

    loaded_node = MemoryNode.from_dict(node.to_dict())
    loaded_edge = MemoryEdge.from_dict(edge.to_dict())

    assert loaded_node.id == node.id
    assert loaded_node.properties == {"confidence": 0.9}
    assert loaded_edge.source_id == node.id
    assert loaded_edge.relation == "derived_from_episode"


def test_build_memory_graph_links_all_memory_layers():
    episode = make_episode()
    semantic = SemanticMemory(
        id="semantic:project-uses-pytest",
        fact="project uses pytest",
        subject="project",
        predicate="uses",
        object="pytest",
        source_episode_ids=[episode.id],
        source_run_ids=[episode.run_id],
    )
    procedure = ProceduralMemory(
        id="procedure:update-cli",
        name="update-cli",
        description="Update CLI and test it.",
        steps=["Read code.", "Patch code.", "Run tests."],
        source_episode_ids=[episode.id],
        source_run_ids=[episode.run_id],
    )

    graph = build_memory_graph("session-1", episode, [semantic], [procedure])

    node_types = {node.id: node.type for node in graph.nodes}
    relations = {
        (edge.source_id, edge.relation, edge.target_id)
        for edge in graph.edges
    }
    assert node_types["session:session-1"] == "session"
    assert node_types["run:run-1"] == "run"
    assert node_types[episode.id] == "episode"
    assert node_types[semantic.id] == "semantic"
    assert node_types[procedure.id] == "procedure"
    assert node_types["skill_candidate"] == "concept"
    assert (episode.id, "belongs_to_session", "session:session-1") in relations
    assert (episode.id, "records_run", "run:run-1") in relations
    assert (semantic.id, "derived_from_episode", episode.id) in relations
    assert (procedure.id, "can_become", "skill_candidate") in relations


def test_build_memory_graph_adds_entity_relation_subgraph():
    episode = make_episode()
    semantic = SemanticMemory(
        id="semantic:minicode-uses-pytest",
        fact="MiniCode uses pytest",
        subject="MiniCode",
        predicate="uses",
        object="pytest",
        source_episode_ids=[episode.id],
        source_run_ids=[episode.run_id],
    )
    extraction = EntityRelationExtraction(
        entities=[
            KnowledgeEntity(
                id="entity:minicode",
                name="MiniCode",
                type="project",
                source_memory_ids=[semantic.id],
            ),
            KnowledgeEntity(
                id="entity:pytest",
                name="pytest",
                type="library",
                source_memory_ids=[semantic.id],
            ),
        ],
        relations=[
            KnowledgeRelation(
                source_entity_id="entity:minicode",
                target_entity_id="entity:pytest",
                predicate="uses",
                confidence=0.9,
                source_memory_ids=[semantic.id],
                source_episode_ids=[episode.id],
            )
        ],
    )

    graph = build_memory_graph(
        "session-1",
        episode,
        [semantic],
        [],
        entity_relations=extraction,
    )

    node_types = {node.id: node.type for node in graph.nodes}
    relations = {
        (edge.source_id, edge.relation, edge.target_id)
        for edge in graph.edges
    }
    entity_edge = next(
        edge
        for edge in graph.edges
        if edge.source_id == "entity:minicode" and edge.relation == "uses"
    )
    assert node_types["entity:minicode"] == "entity"
    assert node_types["entity:pytest"] == "entity"
    assert ("entity:minicode", "uses", "entity:pytest") in relations
    assert (
        "entity:minicode",
        "supported_by_memory",
        "semantic:minicode-uses-pytest",
    ) in relations
    assert entity_edge.properties["confidence"] == 0.9
    assert entity_edge.properties["temporal_fact"] is True
    assert entity_edge.properties["fact_status"] == "active"


def test_memory_graph_upserts_nodes_edges_and_finds_neighbors():
    graph = MemoryGraph()
    graph.add_node(MemoryNode(id="episode:1", type="episode", label="first"))
    graph.add_node(
        MemoryNode(
            id="episode:1",
            type="episode",
            label="updated",
            properties={"status": "completed"},
        )
    )
    graph.add_node(MemoryNode(id="session:1", type="session", label="session"))
    edge = make_edge("episode:1", "session:1", "belongs_to_session")
    graph.add_edge(edge)
    graph.add_edge(edge)

    assert len(graph.nodes) == 2
    assert len(graph.edges) == 1
    assert graph.nodes[0].label == "updated"
    assert graph.neighbors("episode:1", "belongs_to_session")[0].id == "session:1"


def test_memory_graph_store_merges_local_graphs(tmp_path):
    store = MemoryGraphStore(str(tmp_path / "memory"))
    first = MemoryGraph(
        nodes=[MemoryNode(id="session:1", type="session", label="one")]
    )
    second = MemoryGraph(
        nodes=[MemoryNode(id="session:2", type="session", label="two")]
    )

    store.upsert_graph(first)
    saved = store.upsert_graph(second)
    loaded = store.load()
    data = json.loads((tmp_path / "memory" / "graph.json").read_text())

    assert [node.id for node in saved.nodes] == ["session:1", "session:2"]
    assert [node.id for node in loaded.nodes] == ["session:1", "session:2"]
    assert len(data["nodes"]) == 2


def test_graph_merge_preserves_all_relation_sources():
    graph = MemoryGraph()
    first = make_edge(
        "entity:minicode",
        "entity:pytest",
        "uses",
        properties={
            "source_episode_ids": ["episode:1"],
            "source_memory_ids": ["semantic:1"],
        },
    )
    second = make_edge(
        "entity:minicode",
        "entity:pytest",
        "uses",
        properties={
            "source_episode_ids": ["episode:2"],
            "source_memory_ids": ["semantic:2"],
        },
    )

    graph.add_edge(first)
    graph.add_edge(second)

    assert graph.edges[0].properties["source_episode_ids"] == [
        "episode:1",
        "episode:2",
    ]
    assert graph.edges[0].properties["source_memory_ids"] == [
        "semantic:1",
        "semantic:2",
    ]


def test_stable_edge_id_is_deterministic():
    first = stable_edge_id("semantic:1", "episode:1", "derived_from_episode")
    second = stable_edge_id("semantic:1", "episode:1", "derived_from_episode")

    assert first == second
