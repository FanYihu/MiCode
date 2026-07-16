from minicode.memory.entity import (
    build_entity_relation_extraction_prompt,
    deterministic_entity_relation_extraction,
    extract_entities_and_relations,
    make_knowledge_entity,
    normalize_predicate,
    infer_relation_cardinality,
    parse_entity_relation_response,
    stable_entity_id,
)
from minicode.memory.episodic import EpisodicMemory
from minicode.memory.semantic import SemanticMemory


def make_episode() -> EpisodicMemory:
    return EpisodicMemory(
        id="episode:run-1",
        session_id="session-1",
        run_id="run-1",
        task="用 pytest 测试 MiniCode CLI",
        outcome="测试通过",
        status="completed",
    )


def make_semantic_memory() -> SemanticMemory:
    return SemanticMemory(
        id="semantic:minicode-uses-pytest",
        fact="MiniCode uses pytest",
        subject="MiniCode",
        predicate="uses",
        object="pytest",
        confidence=0.9,
        source_episode_ids=["episode:run-1"],
        source_run_ids=["run-1"],
        tags=["test"],
    )


class FakeEntityClient:
    def __init__(self, text: str) -> None:
        self.text = text
        self.prompts = []

    def generate(self, prompt: str) -> str:
        self.prompts.append(prompt)
        return self.text


def test_deterministic_entity_relation_extraction_uses_semantic_triples():
    episode = make_episode()
    semantic = make_semantic_memory()

    extraction = deterministic_entity_relation_extraction(episode, [semantic])

    entity_ids = [entity.id for entity in extraction.entities]
    relation = extraction.relations[0]
    assert "entity:minicode" in entity_ids
    assert "entity:pytest" in entity_ids
    assert relation.source_entity_id == "entity:minicode"
    assert relation.target_entity_id == "entity:pytest"
    assert relation.predicate == "uses"
    assert relation.source_memory_ids == [semantic.id]


def test_parse_entity_relation_response_canonicalizes_names_and_aliases():
    episode = make_episode()
    semantic = make_semantic_memory()
    text = """
{
  "entities": [
    {"name": "MiniCode", "type": "project", "aliases": ["minicode"]},
    {"name": "pytest", "type": "library", "aliases": []}
  ],
  "relations": [
    {
      "source": "minicode",
      "predicate": "uses",
      "target": "pytest",
      "confidence": 0.95,
      "source_memory_ids": ["semantic:minicode-uses-pytest"]
    }
  ]
}
"""

    extraction = parse_entity_relation_response(text, episode, [semantic])

    assert len(extraction.entities) == 2
    assert extraction.entities[0].type == "project"
    assert extraction.relations[0].confidence == 0.95
    assert extraction.relations[0].source_episode_ids == [episode.id]


def test_extract_entities_and_relations_uses_llm_then_fallback():
    episode = make_episode()
    semantic = make_semantic_memory()
    client = FakeEntityClient(
        '{"entities":[{"name":"MiniCode","type":"project"},'
        '{"name":"pytest","type":"library"}],'
        '"relations":[{"source":"MiniCode","predicate":"uses",'
        '"target":"pytest","confidence":0.9,'
        '"source_memory_ids":["semantic:minicode-uses-pytest"]}]}'
    )

    extraction = extract_entities_and_relations(episode, [semantic], client)

    assert extraction.entities[0].name == "MiniCode"
    assert extraction.relations[0].predicate == "uses"
    assert "knowledge graph entity" in client.prompts[0]


def test_extract_entities_and_relations_falls_back_on_bad_json():
    episode = make_episode()
    semantic = make_semantic_memory()
    client = FakeEntityClient("bad json")

    extraction = extract_entities_and_relations(episode, [semantic], client)

    assert extraction.relations[0].predicate == "uses"


def test_entity_prompt_includes_episode_and_semantic_memory():
    prompt = build_entity_relation_extraction_prompt(
        make_episode(),
        [make_semantic_memory()],
    )

    assert "Return exactly one JSON object" in prompt
    assert "MiniCode uses pytest" in prompt


def test_entity_ids_and_predicates_are_stable():
    assert stable_entity_id("MiniCode") == stable_entity_id(" minicode ")
    assert normalize_predicate("Uses Tool") == "uses_tool"
    assert make_knowledge_entity("pytest", entity_type="library").type == "library"
    assert infer_relation_cardinality("uses") == "multi"
    assert infer_relation_cardinality("uses_model") == "single"


def test_deterministic_relation_contains_temporal_metadata():
    episode = make_episode()
    episode.created_at = "2026-06-08T00:00:00+00:00"
    episode.updated_at = "2026-06-08T00:00:03+00:00"
    semantic = make_semantic_memory()

    relation = deterministic_entity_relation_extraction(
        episode,
        [semantic],
    ).relations[0]

    assert relation.observed_at == semantic.updated_at
    assert relation.valid_from == semantic.created_at
    assert relation.cardinality == "multi"
