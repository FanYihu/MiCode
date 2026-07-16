import json
from dataclasses import dataclass, field

from minicode.memory.episodic import EpisodicMemory
from minicode.memory.semantic import SemanticMemory


@dataclass
class KnowledgeEntity:
    """KnowledgeEntity 表示知识图谱中的规范实体。"""

    id: str
    name: str
    type: str = "concept"
    aliases: list[str] = field(default_factory=list)
    source_memory_ids: list[str] = field(default_factory=list)
    properties: dict = field(default_factory=dict)


@dataclass
class KnowledgeRelation:
    """KnowledgeRelation 表示两个实体之间、带来源的语义关系。"""

    source_entity_id: str
    target_entity_id: str
    predicate: str
    confidence: float = 0.7
    observed_at: str = ""
    valid_from: str = ""
    valid_to: str = ""
    cardinality: str = "multi"
    source_memory_ids: list[str] = field(default_factory=list)
    source_episode_ids: list[str] = field(default_factory=list)
    properties: dict = field(default_factory=dict)


@dataclass
class EntityRelationExtraction:
    """一次实体关系抽取结果。"""

    entities: list[KnowledgeEntity] = field(default_factory=list)
    relations: list[KnowledgeRelation] = field(default_factory=list)


def extract_entities_and_relations(
    episode: EpisodicMemory,
    semantic_memories: list[SemanticMemory],
    extractor_client=None,
) -> EntityRelationExtraction:
    """从 episode 和 semantic memories 中抽取实体关系。

    优先使用 LLM 做实体规范化和关系提炼；失败时把已有语义三元组直接转成图。
    """
    if extractor_client is not None:
        try:
            text = extractor_client.generate(
                build_entity_relation_extraction_prompt(
                    episode,
                    semantic_memories,
                )
            )
            extracted = parse_entity_relation_response(
                text,
                episode,
                semantic_memories,
            )
            if extracted.entities and extracted.relations:
                return extracted
        except Exception:
            # 图谱增强失败不能阻断 Agent 和基础记忆持久化。
            pass

    return deterministic_entity_relation_extraction(
        episode,
        semantic_memories,
    )


def deterministic_entity_relation_extraction(
    episode: EpisodicMemory,
    semantic_memories: list[SemanticMemory],
) -> EntityRelationExtraction:
    """把 SemanticMemory 已有的 subject-predicate-object 三元组转成实体关系。"""
    extraction = EntityRelationExtraction()

    for memory in semantic_memories:
        subject = memory.subject.strip()
        predicate = normalize_predicate(memory.predicate)
        object_value = memory.object.strip()
        if not subject or not predicate or not object_value:
            continue

        source = make_knowledge_entity(
            subject,
            source_memory_ids=[memory.id],
        )
        target = make_knowledge_entity(
            object_value,
            source_memory_ids=[memory.id],
        )
        upsert_entity(extraction.entities, source)
        upsert_entity(extraction.entities, target)
        upsert_relation(
            extraction.relations,
            KnowledgeRelation(
                source_entity_id=source.id,
                target_entity_id=target.id,
                predicate=predicate,
                confidence=memory.confidence,
                observed_at=memory.updated_at or episode.updated_at,
                valid_from=memory.created_at or episode.created_at,
                cardinality=infer_relation_cardinality(predicate),
                source_memory_ids=[memory.id],
                source_episode_ids=memory.source_episode_ids or [episode.id],
            ),
        )

    return extraction


def build_entity_relation_extraction_prompt(
    episode: EpisodicMemory,
    semantic_memories: list[SemanticMemory],
) -> str:
    """构建实体和关系抽取 prompt。"""
    payload = {
        "episode": episode.to_dict(),
        "semantic_facts": [memory.to_dict() for memory in semantic_memories],
    }
    return f"""
You are MiniCode's knowledge graph entity and relation extractor.

Extract canonical entities and stable relations useful for future coding tasks.
Return exactly one JSON object:
{{
  "entities": [
    {{
      "name": "canonical entity name",
      "type": "project|file|tool|library|model|provider|language|concept|person",
      "aliases": ["optional aliases"],
      "properties": {{}}
    }}
  ],
  "relations": [
    {{
      "source": "canonical source entity name",
      "predicate": "short_snake_case_relation",
      "target": "canonical target entity name",
      "confidence": 0.0,
      "valid_from": "optional ISO-8601 effective time",
      "cardinality": "single|multi",
      "source_memory_ids": ["semantic memory ids"]
    }}
  ]
}}

Rules:
- Prefer concrete reusable entities such as projects, files, tools, libraries and models.
- Canonicalize aliases to one entity name.
- Exclude API keys, credentials, secrets and transient raw output.
- Relations must reference names present in entities.
- Use single cardinality only when one source should have one current target for that predicate.
- Use multi cardinality when several targets may be true at the same time.
- Use confidence between 0 and 1.
- Do not invent information.
- Return JSON only.

Memory payload:
{json.dumps(payload, ensure_ascii=False)}
""".strip()


def parse_entity_relation_response(
    text: str,
    episode: EpisodicMemory,
    semantic_memories: list[SemanticMemory],
) -> EntityRelationExtraction:
    """解析 LLM 返回的实体关系 JSON。"""
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return EntityRelationExtraction()

    if not isinstance(data, dict):
        return EntityRelationExtraction()

    entity_items = data.get("entities", [])
    relation_items = data.get("relations", [])
    if not isinstance(entity_items, list) or not isinstance(relation_items, list):
        return EntityRelationExtraction()

    extraction = EntityRelationExtraction()
    entity_by_name = {}
    valid_memory_ids = {memory.id for memory in semantic_memories}

    for item in entity_items:
        if not isinstance(item, dict):
            continue
        name = clean_string(item.get("name"))
        if not name:
            continue
        entity = make_knowledge_entity(
            name,
            entity_type=clean_string(item.get("type")) or "concept",
            aliases=string_list(item.get("aliases", [])),
            properties=item.get("properties", {})
            if isinstance(item.get("properties", {}), dict)
            else {},
        )
        upsert_entity(extraction.entities, entity)
        entity_by_name[normalize_name(name)] = entity
        for alias in entity.aliases:
            entity_by_name[normalize_name(alias)] = entity

    for item in relation_items:
        if not isinstance(item, dict):
            continue
        source = entity_by_name.get(normalize_name(clean_string(item.get("source"))))
        target = entity_by_name.get(normalize_name(clean_string(item.get("target"))))
        predicate = normalize_predicate(clean_string(item.get("predicate")))
        if source is None or target is None or not predicate:
            continue

        source_memory_ids = [
            memory_id
            for memory_id in string_list(item.get("source_memory_ids", []))
            if memory_id in valid_memory_ids
        ]
        relation = KnowledgeRelation(
            source_entity_id=source.id,
            target_entity_id=target.id,
            predicate=predicate,
            confidence=clean_confidence(item.get("confidence")),
            observed_at=episode.updated_at or episode.created_at,
            valid_from=clean_string(item.get("valid_from"))
            or episode.updated_at
            or episode.created_at,
            cardinality=clean_cardinality(
                item.get("cardinality"),
                predicate,
            ),
            source_memory_ids=source_memory_ids,
            source_episode_ids=[episode.id],
        )
        upsert_relation(extraction.relations, relation)

        # 关系来源也写回实体，方便从实体追溯支撑它的 semantic memory。
        source.source_memory_ids = merge_unique(
            source.source_memory_ids,
            source_memory_ids,
        )
        target.source_memory_ids = merge_unique(
            target.source_memory_ids,
            source_memory_ids,
        )

    return extraction


def make_knowledge_entity(
    name: str,
    entity_type: str = "concept",
    aliases: list[str] = None,
    source_memory_ids: list[str] = None,
    properties: dict = None,
) -> KnowledgeEntity:
    """创建带稳定 id 的知识实体。"""
    canonical_name = name.strip()
    return KnowledgeEntity(
        id=stable_entity_id(canonical_name),
        name=canonical_name,
        type=normalize_entity_type(entity_type),
        aliases=aliases or [],
        source_memory_ids=source_memory_ids or [],
        properties=properties or {},
    )


def stable_entity_id(name: str) -> str:
    """按规范名称生成稳定实体 id，使跨 episode 的同名实体可以合并。"""
    normalized = normalize_name(name)
    safe = "".join(char if char.isalnum() else "-" for char in normalized)
    while "--" in safe:
        safe = safe.replace("--", "-")
    return f"entity:{safe.strip('-')[:160] or 'unknown'}"


def normalize_name(value: str) -> str:
    """规范化实体名称，供 id 和别名匹配使用。"""
    return " ".join(value.strip().lower().split())


def normalize_predicate(value: str) -> str:
    """把关系名称规范成 snake_case。"""
    normalized = value.strip().lower()
    chars = [char if char.isalnum() else "_" for char in normalized]
    result = "".join(chars)
    while "__" in result:
        result = result.replace("__", "_")
    return result.strip("_")[:80]


def normalize_entity_type(value: str) -> str:
    """限制实体类型，未知类型统一归为 concept。"""
    allowed = {
        "project",
        "file",
        "tool",
        "library",
        "model",
        "provider",
        "language",
        "concept",
        "person",
    }
    normalized = value.strip().lower()
    return normalized if normalized in allowed else "concept"


def upsert_entity(
    entities: list[KnowledgeEntity],
    current: KnowledgeEntity,
) -> None:
    """按稳定 id 合并实体来源、别名和属性。"""
    for index, previous in enumerate(entities):
        if previous.id != current.id:
            continue
        entities[index] = KnowledgeEntity(
            id=previous.id,
            name=current.name or previous.name,
            type=current.type
            if current.type != "concept"
            else previous.type,
            aliases=merge_unique(previous.aliases, current.aliases),
            source_memory_ids=merge_unique(
                previous.source_memory_ids,
                current.source_memory_ids,
            ),
            properties={**previous.properties, **current.properties},
        )
        return
    entities.append(current)


def upsert_relation(
    relations: list[KnowledgeRelation],
    current: KnowledgeRelation,
) -> None:
    """按 source-predicate-target 合并关系来源。"""
    for index, previous in enumerate(relations):
        if relation_key(previous) != relation_key(current):
            continue
        relations[index] = KnowledgeRelation(
            source_entity_id=previous.source_entity_id,
            target_entity_id=previous.target_entity_id,
            predicate=previous.predicate,
            confidence=max(previous.confidence, current.confidence),
            observed_at=current.observed_at or previous.observed_at,
            valid_from=current.valid_from or previous.valid_from,
            valid_to=current.valid_to or previous.valid_to,
            cardinality=current.cardinality or previous.cardinality,
            source_memory_ids=merge_unique(
                previous.source_memory_ids,
                current.source_memory_ids,
            ),
            source_episode_ids=merge_unique(
                previous.source_episode_ids,
                current.source_episode_ids,
            ),
            properties={**previous.properties, **current.properties},
        )
        return
    relations.append(current)


def relation_key(relation: KnowledgeRelation) -> tuple:
    return (
        relation.source_entity_id,
        relation.predicate,
        relation.target_entity_id,
    )


def infer_relation_cardinality(predicate: str) -> str:
    """推断关系是否单值；普通 uses/contains 等关系默认允许多个目标。"""
    normalized = normalize_predicate(predicate)
    single_predicates = {
        "status",
        "has_status",
        "version",
        "has_version",
        "uses_model",
        "uses_provider",
        "configured_model",
        "configured_provider",
        "preferred_model",
        "preferred_provider",
    }
    return "single" if normalized in single_predicates else "multi"


def merge_unique(first: list[str], second: list[str]) -> list[str]:
    merged = []
    for item in first + second:
        if item and item not in merged:
            merged.append(item)
    return merged


def string_list(value) -> list[str]:
    if not isinstance(value, list):
        return []
    return [item.strip() for item in value if isinstance(item, str) and item.strip()]


def clean_string(value) -> str:
    return value.strip() if isinstance(value, str) else ""


def clean_confidence(value) -> float:
    try:
        confidence = float(value)
    except (TypeError, ValueError):
        return 0.7
    return max(0.0, min(1.0, confidence))


def clean_cardinality(value, predicate: str) -> str:
    """清洗 LLM 返回的 cardinality，非法值使用确定性推断。"""
    if isinstance(value, str) and value.strip().lower() in {"single", "multi"}:
        return value.strip().lower()
    return infer_relation_cardinality(predicate)
