import json
from dataclasses import dataclass, field
from pathlib import Path

from micode.memory.entity import EntityRelationExtraction, KnowledgeEntity
from micode.memory.episodic import EpisodicMemory
from micode.memory.procedural import ProceduralMemory
from micode.memory.semantic import SemanticMemory
from micode.memory.session import utc_now_iso


@dataclass
class MemoryNode:
    """MemoryNode 是图里的点，用来表示 session、run、episode、fact 或 procedure。"""

    id: str
    type: str
    label: str
    created_at: str = field(default_factory=utc_now_iso)
    updated_at: str = field(default_factory=utc_now_iso)
    properties: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        """转成可保存的 JSON dict。"""
        return {
            "id": self.id,
            "type": self.type,
            "label": self.label,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "properties": self.properties,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "MemoryNode":
        """从 JSON dict 还原 MemoryNode。"""
        return cls(
            id=str(data.get("id", "")),
            type=str(data.get("type", "")),
            label=str(data.get("label", "")),
            created_at=str(data.get("created_at", "")) or utc_now_iso(),
            updated_at=str(data.get("updated_at", "")) or utc_now_iso(),
            properties=data.get("properties", {})
            if isinstance(data.get("properties", {}), dict)
            else {},
        )


@dataclass
class MemoryEdge:
    """MemoryEdge 是图里的边，用来表达两个记忆节点之间的关系。"""

    id: str
    source_id: str
    target_id: str
    relation: str
    created_at: str = field(default_factory=utc_now_iso)
    updated_at: str = field(default_factory=utc_now_iso)
    properties: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        """转成可保存的 JSON dict。"""
        return {
            "id": self.id,
            "source_id": self.source_id,
            "target_id": self.target_id,
            "relation": self.relation,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "properties": self.properties,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "MemoryEdge":
        """从 JSON dict 还原 MemoryEdge。"""
        return cls(
            id=str(data.get("id", "")),
            source_id=str(data.get("source_id", "")),
            target_id=str(data.get("target_id", "")),
            relation=str(data.get("relation", "")),
            created_at=str(data.get("created_at", "")) or utc_now_iso(),
            updated_at=str(data.get("updated_at", "")) or utc_now_iso(),
            properties=data.get("properties", {})
            if isinstance(data.get("properties", {}), dict)
            else {},
        )


@dataclass
class MemoryGraph:
    """MemoryGraph 是长期记忆的关系索引，不复制完整记忆正文。"""

    nodes: list[MemoryNode] = field(default_factory=list)
    edges: list[MemoryEdge] = field(default_factory=list)

    def add_node(self, node: MemoryNode) -> None:
        """按 id upsert 节点；旧 properties 会和新 properties 合并。"""
        for index, existing in enumerate(self.nodes):
            if existing.id == node.id:
                self.nodes[index] = merge_node(existing, node)
                return
        self.nodes.append(node)

    def add_edge(self, edge: MemoryEdge) -> None:
        """按 id upsert 边，避免同一关系重复写入。"""
        for index, existing in enumerate(self.edges):
            if existing.id == edge.id:
                self.edges[index] = merge_edge(existing, edge)
                return
        self.edges.append(edge)

    def neighbors(self, node_id: str, relation: str = "") -> list[MemoryNode]:
        """查找从 node_id 出发的邻居节点；Day53 会基于它做 graph traversal。"""
        target_ids = [
            edge.target_id
            for edge in self.edges
            if edge.source_id == node_id and (not relation or edge.relation == relation)
        ]
        return [node for node in self.nodes if node.id in target_ids]

    def to_dict(self) -> dict:
        """转成可保存的 JSON dict。"""
        return {
            "nodes": [node.to_dict() for node in self.nodes],
            "edges": [edge.to_dict() for edge in self.edges],
        }

    @classmethod
    def from_dict(cls, data: dict) -> "MemoryGraph":
        """从 JSON dict 还原 MemoryGraph。"""
        if not isinstance(data, dict):
            return cls()
        return cls(
            nodes=[
                MemoryNode.from_dict(item)
                for item in data.get("nodes", [])
                if isinstance(item, dict)
            ],
            edges=[
                MemoryEdge.from_dict(item)
                for item in data.get("edges", [])
                if isinstance(item, dict)
            ],
        )


class MemoryGraphStore:
    """用本地 JSON 保存 memory graph。"""

    def __init__(self, memory_dir: str = ".micode/memory") -> None:
        self.memory_dir = Path(memory_dir)

    def load(self) -> MemoryGraph:
        """读取 memory graph；不存在时返回空图。"""
        path = self.path()
        if not path.exists():
            return MemoryGraph()

        data = json.loads(path.read_text(encoding="utf-8"))
        return MemoryGraph.from_dict(data)

    def save(self, graph: MemoryGraph) -> str:
        """保存完整 graph。"""
        self.memory_dir.mkdir(parents=True, exist_ok=True)
        path = self.path()
        path.write_text(
            json.dumps(graph.to_dict(), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return str(path)

    def upsert_graph(self, graph: MemoryGraph) -> MemoryGraph:
        """把一段新图合并进持久化图。"""
        current = self.load()
        for node in graph.nodes:
            current.add_node(node)
        for edge in graph.edges:
            current.add_edge(edge)
        # 在完整图上统一解析事实状态，避免每次 run 只看局部图而漏掉旧事实。
        from micode.memory.temporal import resolve_temporal_conflicts

        resolve_temporal_conflicts(current)
        self.save(current)
        return current

    def path(self) -> Path:
        """返回 memory graph 文件路径。"""
        return self.memory_dir / "graph.json"


def build_memory_graph(
    session_id: str,
    episode: EpisodicMemory,
    semantic_memories: list[SemanticMemory],
    procedural_memories: list[ProceduralMemory],
    entity_relations: EntityRelationExtraction = None,
) -> MemoryGraph:
    """从一次 run 产生的长期记忆构建局部图。

    当前只建立确定来源关系；Day51/Day52 会继续补实体、关系、时间和冲突处理。
    """
    graph = MemoryGraph()
    session_node_id = f"session:{session_id}"
    run_node_id = f"run:{episode.run_id}"

    graph.add_node(
        MemoryNode(
            id=session_node_id,
            type="session",
            label=session_id,
            properties={"session_id": session_id},
        )
    )
    graph.add_node(
        MemoryNode(
            id=run_node_id,
            type="run",
            label=episode.run_id,
            created_at=episode.created_at,
            updated_at=episode.updated_at,
            properties={"run_id": episode.run_id, "status": episode.status},
        )
    )
    graph.add_node(memory_node_from_episode(episode))
    graph.add_edge(make_edge(episode.id, session_node_id, "belongs_to_session"))
    graph.add_edge(make_edge(episode.id, run_node_id, "records_run"))

    for semantic_memory in semantic_memories:
        graph.add_node(memory_node_from_semantic(semantic_memory))
        graph.add_edge(make_edge(semantic_memory.id, episode.id, "derived_from_episode"))
        for run_id in semantic_memory.source_run_ids:
            graph.add_edge(make_edge(semantic_memory.id, f"run:{run_id}", "derived_from_run"))

    for procedural_memory in procedural_memories:
        graph.add_node(memory_node_from_procedure(procedural_memory))
        graph.add_edge(make_edge(procedural_memory.id, episode.id, "derived_from_episode"))
        graph.add_edge(make_edge(procedural_memory.id, "skill_candidate", "can_become"))
        for run_id in procedural_memory.source_run_ids:
            graph.add_edge(make_edge(procedural_memory.id, f"run:{run_id}", "derived_from_run"))

    if procedural_memories:
        graph.add_node(
            MemoryNode(
                id="skill_candidate",
                type="concept",
                label="Skill Candidate",
                properties={"description": "Reviewed procedures can become project skills."},
            )
        )

    if entity_relations is not None:
        add_entity_relation_graph(graph, entity_relations)

    return graph


def add_entity_relation_graph(
    graph: MemoryGraph,
    extraction: EntityRelationExtraction,
) -> None:
    """把实体关系抽取结果加入 Memory Graph。"""
    for entity in extraction.entities:
        graph.add_node(memory_node_from_entity(entity))

    for relation in extraction.relations:
        graph.add_edge(
            make_edge(
                relation.source_entity_id,
                relation.target_entity_id,
                relation.predicate,
                properties={
                    "confidence": relation.confidence,
                    "temporal_fact": True,
                    "fact_status": "active",
                    "observed_at": relation.observed_at,
                    "valid_from": relation.valid_from or relation.observed_at,
                    "valid_to": relation.valid_to,
                    "cardinality": relation.cardinality,
                    "source_memory_ids": relation.source_memory_ids,
                    "source_episode_ids": relation.source_episode_ids,
                    **relation.properties,
                },
            )
        )
        for memory_id in relation.source_memory_ids:
            graph.add_edge(
                make_edge(
                    relation.source_entity_id,
                    memory_id,
                    "supported_by_memory",
                )
            )
            graph.add_edge(
                make_edge(
                    relation.target_entity_id,
                    memory_id,
                    "supported_by_memory",
                )
            )


def memory_node_from_episode(episode: EpisodicMemory) -> MemoryNode:
    """把 Episode 转成图节点，只放摘要级 properties。"""
    return MemoryNode(
        id=episode.id,
        type="episode",
        label=episode.task or episode.id,
        created_at=episode.created_at,
        updated_at=episode.updated_at,
        properties={
            "session_id": episode.session_id,
            "run_id": episode.run_id,
            "status": episode.status,
            "task": episode.task,
            "outcome": episode.outcome,
            "tool_names": episode.tool_names,
        },
    )


def memory_node_from_semantic(memory: SemanticMemory) -> MemoryNode:
    """把 SemanticMemory 转成事实节点。"""
    return MemoryNode(
        id=memory.id,
        type="semantic",
        label=memory.fact,
        created_at=memory.created_at,
        updated_at=memory.updated_at,
        properties={
            "subject": memory.subject,
            "predicate": memory.predicate,
            "object": memory.object,
            "confidence": memory.confidence,
            "tags": memory.tags,
        },
    )


def memory_node_from_procedure(memory: ProceduralMemory) -> MemoryNode:
    """把 ProceduralMemory 转成流程节点。"""
    return MemoryNode(
        id=memory.id,
        type="procedure",
        label=memory.name,
        created_at=memory.created_at,
        updated_at=memory.updated_at,
        properties={
            "description": memory.description,
            "steps": memory.steps,
            "when_to_use": memory.when_to_use,
            "when_not_to_use": memory.when_not_to_use,
            "tags": memory.tags,
        },
    )


def memory_node_from_entity(entity: KnowledgeEntity) -> MemoryNode:
    """把规范实体转成图节点。"""
    return MemoryNode(
        id=entity.id,
        type="entity",
        label=entity.name,
        properties={
            "entity_type": entity.type,
            "aliases": entity.aliases,
            "source_memory_ids": entity.source_memory_ids,
            **entity.properties,
        },
    )


def make_edge(source_id: str, target_id: str, relation: str, properties: dict = None) -> MemoryEdge:
    """创建稳定边 id；同一 source/relation/target 会自然去重。"""
    edge_id = stable_edge_id(source_id, target_id, relation)
    return MemoryEdge(
        id=edge_id,
        source_id=source_id,
        target_id=target_id,
        relation=relation,
        properties=properties or {},
    )


def stable_edge_id(source_id: str, target_id: str, relation: str) -> str:
    """生成稳定边 id。"""
    raw = f"{source_id}|{relation}|{target_id}".lower()
    safe = "".join(char if char.isalnum() else "-" for char in raw)
    while "--" in safe:
        safe = safe.replace("--", "-")
    return f"edge:{safe.strip('-')[:220]}"


def merge_node(previous: MemoryNode, current: MemoryNode) -> MemoryNode:
    """合并节点，保留最早 created_at，刷新 updated_at 和 properties。"""
    return MemoryNode(
        id=previous.id,
        type=current.type or previous.type,
        label=current.label or previous.label,
        created_at=previous.created_at,
        updated_at=utc_now_iso(),
        properties=merge_graph_properties(
            previous.properties,
            current.properties,
        ),
    )


def merge_edge(previous: MemoryEdge, current: MemoryEdge) -> MemoryEdge:
    """合并边，保留最早 created_at，刷新 updated_at 和 properties。"""
    return MemoryEdge(
        id=previous.id,
        source_id=current.source_id or previous.source_id,
        target_id=current.target_id or previous.target_id,
        relation=current.relation or previous.relation,
        created_at=previous.created_at,
        updated_at=utc_now_iso(),
        properties=merge_graph_properties(
            previous.properties,
            current.properties,
        ),
    )


def merge_graph_properties(previous: dict, current: dict) -> dict:
    """合并图属性；来源、标签和别名列表需要保留历史值。"""
    merged = {**previous, **current}
    list_keys = {
        "source_memory_ids",
        "source_episode_ids",
        "aliases",
        "tags",
    }
    for key in list_keys:
        old_items = previous.get(key, [])
        new_items = current.get(key, [])
        if isinstance(old_items, list) and isinstance(new_items, list):
            merged[key] = merge_unique_strings(old_items, new_items)
    return merged


def merge_unique_strings(first: list, second: list) -> list:
    merged = []
    for item in first + second:
        if isinstance(item, str) and item and item not in merged:
            merged.append(item)
    return merged
