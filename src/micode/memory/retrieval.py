import math
import re
from dataclasses import dataclass, field

from micode.memory.episodic import EpisodicMemoryStore
from micode.memory.graph import MemoryGraph, MemoryGraphStore
from micode.memory.procedural import ProceduralMemoryStore
from micode.memory.semantic import SemanticMemoryStore
from micode.memory.temporal import ACTIVE, CONFLICTING, SUPERSEDED
from micode.memory.working import truncate_memory_text


@dataclass
class MemoryDocument:
    """MemoryDocument 是各类长期记忆进入检索器后的统一表示。"""

    id: str
    type: str
    content: str
    graph_node_ids: list[str] = field(default_factory=list)
    source_ids: list[str] = field(default_factory=list)
    status: str = ACTIVE
    metadata: dict = field(default_factory=dict)


@dataclass
class MemoryRetrievalResult:
    """MemoryRetrievalResult 保存总分和各召回通道的可解释分数。"""

    id: str
    type: str
    content: str
    score: float
    keyword_score: float = 0.0
    vector_score: float = 0.0
    graph_score: float = 0.0
    ranking_score: float = 0.0
    status: str = ACTIVE
    source_ids: list[str] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)
    ranking_details: dict = field(default_factory=dict)


class HybridMemoryRetriever:
    """组合关键词、可选向量和图遍历的长期记忆召回器。"""

    def __init__(
        self,
        memory_dir: str = ".micode/memory",
        embedding_client=None,
        keyword_weight: float = 0.5,
        vector_weight: float = 0.35,
        graph_weight: float = 0.15,
    ) -> None:
        self.memory_dir = memory_dir
        self.embedding_client = embedding_client
        self.keyword_weight = keyword_weight
        self.vector_weight = vector_weight
        self.graph_weight = graph_weight

    def retrieve(
        self,
        query: str,
        limit: int = 8,
        include_conflicting: bool = True,
        include_superseded: bool = False,
    ) -> list[MemoryRetrievalResult]:
        """召回与任务相关的长期记忆。"""
        if limit <= 0 or not query.strip():
            return []

        graph = MemoryGraphStore(self.memory_dir).load()
        documents = build_memory_documents(graph, self.memory_dir)
        documents = [
            document
            for document in documents
            if is_status_allowed(
                document.status,
                include_conflicting=include_conflicting,
                include_superseded=include_superseded,
            )
        ]
        if not documents:
            return []

        keyword_scores = {
            document.id: keyword_similarity(query, document.content)
            for document in documents
        }
        vector_scores = vector_similarities(
            query,
            documents,
            self.embedding_client,
        )
        seed_ids = select_seed_document_ids(
            documents,
            keyword_scores,
            vector_scores,
        )
        graph_scores = graph_expansion_scores(graph, documents, seed_ids)

        results = []
        for document in documents:
            keyword_score = keyword_scores.get(document.id, 0.0)
            vector_score = vector_scores.get(document.id, 0.0)
            graph_score = graph_scores.get(document.id, 0.0)
            score = (
                keyword_score * self.keyword_weight
                + vector_score * self.vector_weight
                + graph_score * self.graph_weight
            )
            if score <= 0:
                continue
            results.append(
                MemoryRetrievalResult(
                    id=document.id,
                    type=document.type,
                    content=document.content,
                    score=round(score, 6),
                    keyword_score=round(keyword_score, 6),
                    vector_score=round(vector_score, 6),
                    graph_score=round(graph_score, 6),
                    status=document.status,
                    source_ids=document.source_ids,
                    metadata=document.metadata,
                )
            )

        results.sort(
            key=lambda result: (
                result.score,
                result.keyword_score,
                result.vector_score,
            ),
            reverse=True,
        )
        return results[:limit]


def build_memory_documents(
    graph: MemoryGraph,
    memory_dir: str,
) -> list[MemoryDocument]:
    """把四类长期记忆和图事实转成统一检索文档。"""
    documents = []
    temporal_status = temporal_status_by_memory_id(graph)

    for memory in EpisodicMemoryStore(memory_dir).load_all():
        documents.append(
            MemoryDocument(
                id=memory.id,
                type="episode",
                content=" ".join(
                    [memory.task, memory.outcome]
                    + memory.tool_names
                    + memory.evidence
                ).strip(),
                graph_node_ids=[memory.id],
                source_ids=memory.source_event_ids,
                metadata={
                    "session_id": memory.session_id,
                    "run_id": memory.run_id,
                    "created_at": memory.created_at,
                    "updated_at": memory.updated_at,
                },
            )
        )

    for memory in SemanticMemoryStore(memory_dir).load_all():
        status = temporal_status.get(memory.id, ACTIVE)
        documents.append(
            MemoryDocument(
                id=memory.id,
                type="semantic",
                content=" ".join(
                    [
                        memory.fact,
                        memory.subject,
                        memory.predicate,
                        memory.object,
                    ]
                    + memory.tags
                ).strip(),
                graph_node_ids=[memory.id],
                source_ids=memory.source_episode_ids,
                status=status,
                metadata={
                    "confidence": memory.confidence,
                    "session_id": memory.metadata.get("session_id", ""),
                    "created_at": memory.created_at,
                    "updated_at": memory.updated_at,
                },
            )
        )

    for memory in ProceduralMemoryStore(memory_dir).load_all():
        documents.append(
            MemoryDocument(
                id=memory.id,
                type="procedure",
                content=" ".join(
                    [memory.name, memory.description]
                    + memory.steps
                    + memory.when_to_use
                    + memory.tags
                ).strip(),
                graph_node_ids=[memory.id],
                source_ids=memory.source_episode_ids,
                metadata={
                    "session_id": memory.metadata.get("session_id", ""),
                    "created_at": memory.created_at,
                    "updated_at": memory.updated_at,
                    "confidence": memory.metadata.get("confidence", 0.8),
                },
            )
        )

    node_by_id = {node.id: node for node in graph.nodes}
    for edge in graph.edges:
        if not edge.properties.get("temporal_fact"):
            continue
        source = node_by_id.get(edge.source_id)
        target = node_by_id.get(edge.target_id)
        source_label = source.label if source is not None else edge.source_id
        target_label = target.label if target is not None else edge.target_id
        documents.append(
            MemoryDocument(
                id=edge.id,
                type="graph_fact",
                content=f"{source_label} {edge.relation} {target_label}",
                graph_node_ids=[edge.source_id, edge.target_id],
                source_ids=list(edge.properties.get("source_memory_ids", [])),
                status=str(edge.properties.get("fact_status", ACTIVE)),
                metadata={
                    "relation": edge.relation,
                    "confidence": edge.properties.get("confidence", 0.0),
                    "observed_at": edge.properties.get("observed_at", ""),
                    "created_at": edge.created_at,
                    "updated_at": edge.updated_at,
                },
            )
        )

    return deduplicate_documents(documents)


def temporal_status_by_memory_id(graph: MemoryGraph) -> dict:
    """根据图事实来源，计算 semantic memory 当前的时序状态。"""
    statuses = {}
    priority = {ACTIVE: 3, CONFLICTING: 2, SUPERSEDED: 1}
    for edge in graph.edges:
        if not edge.properties.get("temporal_fact"):
            continue
        status = str(edge.properties.get("fact_status", ACTIVE))
        for memory_id in edge.properties.get("source_memory_ids", []):
            previous = statuses.get(memory_id)
            if previous is None or priority.get(status, 0) > priority.get(previous, 0):
                statuses[memory_id] = status
    return statuses


def keyword_similarity(query: str, content: str) -> float:
    """计算轻量关键词相似度，支持英文 token 和连续中文片段。"""
    query_tokens = tokenize(query)
    content_tokens = tokenize(content)
    if not query_tokens or not content_tokens:
        return 0.0

    overlap = query_tokens.intersection(content_tokens)
    coverage = len(overlap) / len(query_tokens)
    exact_bonus = 0.25 if query.strip().lower() in content.lower() else 0.0
    return min(1.0, coverage + exact_bonus)


def tokenize(text: str) -> set[str]:
    """提取英文数字 token，并给中文连续文本增加二元片段。"""
    normalized = text.lower()
    tokens = set(re.findall(r"[a-z0-9_./-]+", normalized))
    for block in re.findall(r"[\u4e00-\u9fff]+", normalized):
        tokens.add(block)
        if len(block) > 1:
            tokens.update(block[index : index + 2] for index in range(len(block) - 1))
    return {token for token in tokens if token}


def vector_similarities(
    query: str,
    documents: list[MemoryDocument],
    embedding_client=None,
) -> dict:
    """使用可选 embed(texts) 接口计算向量相似度。"""
    if embedding_client is None or not hasattr(embedding_client, "embed"):
        return {}

    texts = [query] + [document.content for document in documents]
    try:
        vectors = embedding_client.embed(texts)
    except Exception:
        return {}
    if not isinstance(vectors, list) or len(vectors) != len(texts):
        return {}

    query_vector = vectors[0]
    scores = {}
    for document, vector in zip(documents, vectors[1:]):
        scores[document.id] = max(0.0, cosine_similarity(query_vector, vector))
    return scores


def cosine_similarity(first, second) -> float:
    """计算两个数值向量的余弦相似度。"""
    if not isinstance(first, list) or not isinstance(second, list):
        return 0.0
    if not first or len(first) != len(second):
        return 0.0
    try:
        dot = sum(float(left) * float(right) for left, right in zip(first, second))
        first_norm = math.sqrt(sum(float(value) ** 2 for value in first))
        second_norm = math.sqrt(sum(float(value) ** 2 for value in second))
    except (TypeError, ValueError):
        return 0.0
    if first_norm == 0 or second_norm == 0:
        return 0.0
    return dot / (first_norm * second_norm)


def select_seed_document_ids(
    documents: list[MemoryDocument],
    keyword_scores: dict,
    vector_scores: dict,
    limit: int = 5,
) -> list[str]:
    """选出图遍历起点，避免无关节点扩散。"""
    ranked = sorted(
        documents,
        key=lambda document: max(
            keyword_scores.get(document.id, 0.0),
            vector_scores.get(document.id, 0.0),
        ),
        reverse=True,
    )
    return [
        document.id
        for document in ranked[:limit]
        if max(
            keyword_scores.get(document.id, 0.0),
            vector_scores.get(document.id, 0.0),
        )
        > 0
    ]


def graph_expansion_scores(
    graph: MemoryGraph,
    documents: list[MemoryDocument],
    seed_ids: list[str],
) -> dict:
    """从命中文档对应图节点做一跳双向扩展。"""
    document_by_id = {document.id: document for document in documents}
    seed_node_ids = set()
    for seed_id in seed_ids:
        document = document_by_id.get(seed_id)
        if document is not None:
            seed_node_ids.update(document.graph_node_ids)

    neighboring_node_ids = set(seed_node_ids)
    for edge in graph.edges:
        if edge.source_id in seed_node_ids:
            neighboring_node_ids.add(edge.target_id)
        if edge.target_id in seed_node_ids:
            neighboring_node_ids.add(edge.source_id)

    scores = {}
    for document in documents:
        matched_nodes = neighboring_node_ids.intersection(document.graph_node_ids)
        if not matched_nodes:
            continue
        scores[document.id] = (
            1.0 if set(document.graph_node_ids).intersection(seed_node_ids) else 0.5
        )
    return scores


def format_retrieved_memories(
    results: list[MemoryRetrievalResult],
    max_content: int = 260,
) -> str:
    """把召回结果格式化为可注入 Agent prompt 的紧凑文本。"""
    if not results:
        return ""

    lines = ["Relevant Long-Term Memory:"]
    for result in results:
        status = f" status={result.status}" if result.status != ACTIVE else ""
        lines.append(
            f"- [{result.type}{status}] "
            f"{truncate_memory_text(result.content, max_length=max_content)}"
        )
    return "\n".join(lines)


def is_status_allowed(
    status: str,
    include_conflicting: bool,
    include_superseded: bool,
) -> bool:
    if status == SUPERSEDED:
        return include_superseded
    if status == CONFLICTING:
        return include_conflicting
    return True


def deduplicate_documents(documents: list[MemoryDocument]) -> list[MemoryDocument]:
    """按 id 去重，优先保留后构建的图事实状态。"""
    by_id = {}
    for document in documents:
        by_id[document.id] = document
    return list(by_id.values())
