import argparse
import json
from pathlib import Path

from minicode.agent import MiniCodeAgent, create_llm_from_config
from minicode.context.layers import ContextLayer, ContextLayerAssembler
from minicode.context.prompt_cache import PromptCacheStore
from minicode.context.review import review_context_trace_file
from minicode.context.tokens import estimate_text_parts
from minicode.memory.context import (
    ContextCompressor,
    SessionSummaryStore,
    build_session_context,
)
from minicode.memory.entity import extract_entities_and_relations
from minicode.models import EventType, Run, StepType
from minicode.memory.episodic import EpisodicMemoryStore, episodic_memory_from_trace
from minicode.memory.graph import MemoryGraphStore, build_memory_graph
from minicode.memory.procedural import (
    ProceduralMemoryStore,
    procedural_memories_from_episode,
)
from minicode.memory.ranking import MemoryRankingPolicy
from minicode.memory.retrieval import HybridMemoryRetriever
from minicode.memory.review import review_memory_system
from minicode.memory.semantic import (
    SemanticMemoryStore,
    semantic_memories_from_episode,
)
from minicode.memory.skill_candidate import (
    SkillCandidateStore,
    approve_skill_candidate,
    promote_skill_candidate,
    reject_skill_candidate,
    skill_candidates_from_procedures,
)
from minicode.memory.temporal import temporal_status_counts
from minicode.persistence import (
    cleanup_traces,
    filter_traces,
    format_trace_detail,
    format_trace_markdown,
    load_trace,
    list_traces,
    save_trace,
    summarize_trace,
    write_text_report,
)
from minicode.memory.session import SessionMessageStore, SessionStore, messages_from_trace
from minicode.skills import LLMSkillRouter, discover_project_skills, discover_user_skills
from minicode.subagents import create_default_subagent_executor
from minicode.tools.default import create_default_tool_registry
from minicode.trace import TraceRecorder
from minicode.memory.working import WorkingMemoryStore
from minicode.workspace import Workspace


def run_task(task: str, workspace_path: str) -> dict:
    """执行一个固定 CLI 任务，并返回可序列化的 trace。"""
    run = Run()
    run.metadata["task"] = task
    run.metadata["mode"] = "fixed"
    run.metadata["workspace"] = workspace_path
    trace = TraceRecorder(run)
    workspace = Workspace(workspace_path)

    run.start()

    if task == "list files":
        step = trace.add_step(StepType.TOOL, metadata={"tool": "list_files"})
        files = workspace.list_files()
        trace.add_event(
            step,
            EventType.TOOL_CALL,
            content="\n".join(files),
            metadata={"files": files},
        )
        run.complete()

    elif task == "run tests":
        command = "python3 -m pytest"
        step = trace.add_step(
            StepType.TOOL,
            metadata={"tool": "shell", "command": command},
        )

        # 固定 CLI 任务也复用 Tool Registry，因此权限只由 PermissionHook 处理。
        result = create_default_tool_registry(workspace).call(
            "run_shell",
            {"command": command},
        )
        details = result.metadata.get("details", {})
        trace.add_event(
            step,
            EventType.TOOL_CALL if result.ok else EventType.ERROR,
            content=result.output,
            metadata={
                **details,
                "tool": result.metadata.get("tool", "run_shell"),
                "ok": result.ok,
                "error": result.metadata.get("error", ""),
            },
        )

        if result.ok:
            run.complete()
        else:
            run.fail()

    else:
        step = trace.add_step(StepType.FINAL)
        trace.add_event(
            step,
            EventType.TEXT,
            content=f"不支持的任务：{task}",
        )
        run.complete()

    return trace.to_dict()

def run_agent_task(
    task: str,
    workspace_path: str,
    config_path: str,
    session_id: str = "",
    session_dir: str = ".minicode/sessions",
    session_title: str = "",
    memory_dir: str = ".minicode/memory",
    memory_budget_chars: int = 1800,
    context_budget_chars: int = 4000,
    context_budget_tokens: int = 0,
    tool_result_budget_chars: int = 1200,
    artifact_dir: str = ".minicode/artifacts",
    artifact_threshold_chars: int = 8000,
    prompt_cache_dir: str = ".minicode/prompt-cache",
    skill_candidate_dir: str = ".minicode/skill-candidates",
) -> dict:
    """用 config.toml 创建 LLM，并运行 Agent Loop。"""
    workspace = Workspace(workspace_path)
    skill_candidate_dir = resolve_cli_skill_candidate_dir(
        memory_dir,
        skill_candidate_dir,
    )
    llm = create_llm_from_config(config_path)
    llm_client = getattr(llm, "client", None)
    session_context = ""
    retrieval_candidates = HybridMemoryRetriever(
        memory_dir=memory_dir,
        embedding_client=llm_client
        if llm_client is not None and hasattr(llm_client, "embed")
        else None,
    ).retrieve(task, limit=24)
    ranking_policy = MemoryRankingPolicy()
    ranked_memories = ranking_policy.rank(
        retrieval_candidates,
        current_session_id=session_id,
    )
    memory_injection = ranking_policy.prepare_injection(
        ranked_memories,
        budget_chars=memory_budget_chars,
    )
    retrieved_memory_context = memory_injection.context
    if session_id:
        message_store = SessionMessageStore(session_dir)
        working_memory_store = WorkingMemoryStore(session_dir)
        summary_store = SessionSummaryStore(session_dir)
        compressor = ContextCompressor(summarizer_client=llm_client)
        messages = message_store.load_messages(session_id)
        summary, recent_messages = compressor.compact(
            session_id,
            messages,
            summary_store.load(session_id),
        )
        session_context = build_session_context(
            working_memory_store.load(session_id),
            summary,
            recent_messages,
        )
    context_assembly = ContextLayerAssembler(
        budget_chars=context_budget_chars,
        budget_tokens=context_budget_tokens,
    ).assemble(
        [
            ContextLayer(
                name="session",
                content=session_context,
                priority=100,
                budget_chars=max(0, context_budget_chars - memory_budget_chars),
                metadata={"source": "session_memory"},
            ),
            ContextLayer(
                name="long_term_memory",
                content=retrieved_memory_context,
                priority=80,
                budget_chars=memory_budget_chars,
                metadata={"source": "hybrid_memory_retrieval"},
            ),
        ]
    )
    session_context = context_assembly.context
    context_token_estimate = estimate_text_parts(
        {
            "task": task,
            "assembled_context": session_context,
            "retrieved_memory_context": retrieved_memory_context,
        }
    )
    prompt_cache_entry = PromptCacheStore(prompt_cache_dir).put(
        session_context,
        metadata={
            "task": task,
            "session_id": session_id,
            "context_assembly": context_assembly.to_dict(),
            "context_token_estimate": context_token_estimate,
        },
    )

    project_skills = discover_project_skills(workspace)
    user_skills = discover_user_skills()
    skill_router = (
        LLMSkillRouter(llm_client)
        if llm_client is not None and hasattr(llm_client, "generate")
        else None
    )
    agent = MiniCodeAgent(
        workspace,
        llm,
        skills=user_skills,
        project_skills=project_skills,
        skill_router=skill_router,
        session_id=session_id,
        tool_result_budget_chars=tool_result_budget_chars,
        artifact_dir=artifact_dir,
        artifact_threshold_chars=artifact_threshold_chars,
        prompt_cache_key=prompt_cache_entry.key,
        subagent_executor=create_default_subagent_executor(workspace),
    )
    if session_context and hasattr(llm, "set_session_context"):
        llm.set_session_context(session_context)

    trace = agent.run(task)
    trace["run"]["metadata"]["context_assembly"] = context_assembly.to_dict()
    trace["run"]["metadata"]["context_token_estimate"] = context_token_estimate
    trace["run"]["metadata"]["prompt_cache"] = prompt_cache_entry.to_metadata()
    trace["run"]["metadata"]["retrieved_memory_ids"] = [
        result.id for result in memory_injection.selected
    ]
    trace["run"]["metadata"]["retrieved_memories"] = [
        {
            "id": result.id,
            "type": result.type,
            "score": result.score,
            "keyword_score": result.keyword_score,
            "vector_score": result.vector_score,
            "graph_score": result.graph_score,
            "ranking_score": result.ranking_score,
            "ranking_details": result.ranking_details,
            "status": result.status,
        }
        for result in ranked_memories
    ]
    trace["run"]["metadata"]["memory_injection"] = {
        "candidate_count": len(retrieval_candidates),
        "selected_count": len(memory_injection.selected),
        "selected_ids": [
            result.id for result in memory_injection.selected
        ],
        "omitted_ids": memory_injection.omitted_ids,
        "used_chars": memory_injection.used_chars,
        "budget_chars": memory_injection.budget_chars,
    }
    if session_id:
        # CLI 负责 Session 持久化；Agent 只在 run metadata 中记录归属关系。
        store = SessionStore(session_dir)
        session = store.get_or_create(
            session_id,
            title=session_title or task,
            metadata={"workspace": workspace_path},
        )
        session.add_run(trace["run"]["id"])
        store.save(session)
        message_store = SessionMessageStore(session_dir)
        new_messages = messages_from_trace(session.id, trace)
        all_messages = message_store.append_messages(session.id, new_messages)
        working_memory_store = WorkingMemoryStore(session_dir)
        working_memory = working_memory_store.update_from_messages(
            session.id,
            new_messages,
        )
        summary_store = SessionSummaryStore(session_dir)
        compressor = ContextCompressor(summarizer_client=llm_client)
        summary, recent_messages = compressor.compact(
            session.id,
            all_messages,
            summary_store.load(session.id),
        )
        summary_store.save(summary)
        compressed_context = build_session_context(
            working_memory,
            summary,
            recent_messages,
        )
        trace["run"]["metadata"]["session_id"] = session.id
        trace["run"]["metadata"]["session_path"] = str(store.path_for(session.id))
        trace["run"]["metadata"]["session_messages_path"] = str(
            message_store.path_for(session.id)
        )
        trace["run"]["metadata"]["working_memory_path"] = str(
            working_memory_store.path_for(session.id)
        )
        trace["run"]["metadata"]["session_summary_path"] = str(
            summary_store.path_for(session.id)
        )
        if compressed_context:
            trace["run"]["metadata"]["compressed_context"] = compressed_context
        episodic_memory = episodic_memory_from_trace(session.id, trace)
        episodic_store = EpisodicMemoryStore(memory_dir)
        episodic_store.upsert(episodic_memory)
        trace["run"]["metadata"]["episodic_memory_id"] = episodic_memory.id
        trace["run"]["metadata"]["episodic_memory_path"] = str(episodic_store.path())
        semantic_memories = semantic_memories_from_episode(
            episodic_memory,
            extractor_client=llm_client,
        )
        semantic_store = SemanticMemoryStore(memory_dir)
        semantic_store.upsert_many(semantic_memories)
        trace["run"]["metadata"]["semantic_memory_ids"] = [
            memory.id for memory in semantic_memories
        ]
        trace["run"]["metadata"]["semantic_memory_path"] = str(
            semantic_store.path()
        )
        procedural_memories = procedural_memories_from_episode(
            episodic_memory,
            extractor_client=llm_client,
        )
        procedural_store = ProceduralMemoryStore(memory_dir)
        procedural_store.upsert_many(procedural_memories)
        skill_candidates = skill_candidates_from_procedures(procedural_memories)
        skill_candidate_store = SkillCandidateStore(skill_candidate_dir)
        saved_skill_candidates = skill_candidate_store.upsert_many(skill_candidates)
        trace["run"]["metadata"]["procedural_memory_ids"] = [
            memory.id for memory in procedural_memories
        ]
        trace["run"]["metadata"]["procedural_memory_path"] = str(
            procedural_store.path()
        )
        trace["run"]["metadata"]["skill_candidate_ids"] = [
            candidate.id for candidate in saved_skill_candidates
        ]
        trace["run"]["metadata"]["skill_candidate_dir"] = skill_candidate_dir
        entity_relations = extract_entities_and_relations(
            episodic_memory,
            semantic_memories,
            extractor_client=llm_client,
        )
        trace["run"]["metadata"]["knowledge_entity_ids"] = [
            entity.id for entity in entity_relations.entities
        ]
        trace["run"]["metadata"]["knowledge_relation_count"] = len(
            entity_relations.relations
        )
        # Memory Graph 只保存记忆之间的关系索引，原始内容仍由各 memory store 管理。
        memory_graph = build_memory_graph(
            session.id,
            episodic_memory,
            semantic_memories,
            procedural_memories,
            entity_relations=entity_relations,
        )
        graph_store = MemoryGraphStore(memory_dir)
        saved_graph = graph_store.upsert_graph(memory_graph)
        trace["run"]["metadata"]["memory_graph_path"] = str(graph_store.path())
        trace["run"]["metadata"]["memory_graph_node_ids"] = [
            node.id for node in memory_graph.nodes
        ]
        trace["run"]["metadata"]["memory_graph_edge_ids"] = [
            edge.id for edge in memory_graph.edges
        ]
        trace["run"]["metadata"]["memory_graph_size"] = {
            "nodes": len(saved_graph.nodes),
            "edges": len(saved_graph.edges),
        }
        trace["run"]["metadata"]["temporal_fact_status"] = temporal_status_counts(
            saved_graph
        )
    # workspace/config 是 CLI 入口补充的运行上下文，不让 Agent 直接关心命令行参数。
    trace["run"]["metadata"]["workspace"] = workspace_path
    trace["run"]["metadata"]["config"] = config_path
    return trace


def maybe_save_trace(trace: dict, should_save: bool, output_dir: str) -> dict:
    """按 CLI 参数决定是否保存 trace，并把保存路径放进输出。"""
    if should_save:
        trace["saved_trace_path"] = save_trace(trace, output_dir=output_dir)
    return trace


def run_trace_viewer(
    trace_path: str,
    detail: bool = False,
    max_content: int = 2000,
    markdown: bool = False,
    output: str = "",
) -> str:
    """读取已保存 trace，并按参数返回摘要或详细视图。"""
    trace = load_trace(trace_path)
    if markdown:
        report = format_trace_markdown(trace)
        if output:
            # CLI 只返回用户需要看的保存结果，具体写文件动作交给 persistence 层。
            saved_path = write_text_report(report, output)
            return f"Markdown report saved to {saved_path}"
        return report
    if detail:
        return format_trace_detail(trace, max_content=max_content)
    return summarize_trace(trace)


def run_trace_list(
    trace_dir: str,
    limit: int,
    mode: str = "",
    provider: str = "",
    model: str = "",
    task_contains: str = "",
) -> str:
    """列出最近 trace 文件；CLI 层负责把路径列表格式化成文本。"""
    # 先多取一些候选，再过滤并截断，避免过滤前 limit 过小漏掉匹配项。
    candidates = list_traces(trace_dir=trace_dir, limit=10_000)
    paths = filter_traces(
        candidates,
        mode=mode,
        provider=provider,
        model=model,
        task_contains=task_contains,
    )[:limit]
    if not paths:
        return "No traces found."

    return "\n".join(f"{index}. {path}" for index, path in enumerate(paths, start=1))


def run_trace_cleanup(trace_dir: str, keep: int) -> str:
    """清理旧 trace；CLI 只展示结果，不隐藏底层删除策略。"""
    deleted = cleanup_traces(trace_dir=trace_dir, keep=keep)
    if not deleted:
        return "No trace files deleted."

    return f"Deleted {len(deleted)} trace files."


def run_memory_review(
    session_dir: str = ".minicode/sessions",
    memory_dir: str = ".minicode/memory",
    skill_candidate_dir: str = ".minicode/skill-candidates",
    sample_query: str = "",
    memory_budget_chars: int = 1800,
) -> dict:
    """执行记忆系统 review，并返回结构化报告。"""
    return review_memory_system(
        session_dir=session_dir,
        memory_dir=memory_dir,
        skill_candidate_dir=skill_candidate_dir,
        sample_query=sample_query,
        memory_budget_chars=memory_budget_chars,
    ).to_dict()


def run_context_review(trace_path: str) -> dict:
    """对一条已保存 trace 执行上下文审计。"""
    return review_context_trace_file(trace_path).to_dict()


def run_skill_candidate_review(
    action: str = "list",
    candidate_dir: str = ".minicode/skill-candidates",
    memory_dir: str = ".minicode/memory",
    skills_root: str = ".minicode/skills",
    candidate_id: str = "",
    note: str = "",
    force: bool = False,
) -> dict:
    """管理 Skill Candidate：生成、查看、审批、拒绝和提升。"""
    candidate_dir = resolve_cli_skill_candidate_dir(memory_dir, candidate_dir)
    store = SkillCandidateStore(candidate_dir)

    if action == "generate":
        procedures = ProceduralMemoryStore(memory_dir).load_all()
        candidates = skill_candidates_from_procedures(procedures)
        saved = store.upsert_many(candidates)
        return {
            "action": action,
            "candidate_dir": candidate_dir,
            "generated_count": len(candidates),
            "candidates": [candidate.to_dict() for candidate in saved],
        }

    if action == "list":
        candidates = store.load_all()
        return {
            "action": action,
            "candidate_dir": candidate_dir,
            "candidates": [candidate.to_dict() for candidate in candidates],
        }

    if not candidate_id:
        raise ValueError("candidate_id is required for this action")

    if action == "approve":
        candidate = approve_skill_candidate(store, candidate_id, note=note)
        return {"action": action, "candidate": candidate.to_dict()}
    if action == "reject":
        candidate = reject_skill_candidate(store, candidate_id, note=note)
        return {"action": action, "candidate": candidate.to_dict()}
    if action == "promote":
        result = promote_skill_candidate(
            store,
            candidate_id,
            skills_root=skills_root,
            note=note,
            force=force,
        )
        return {"action": action, **result}

    raise ValueError(f"unknown skill candidate action: {action}")


def resolve_cli_skill_candidate_dir(memory_dir: str, candidate_dir: str) -> str:
    """CLI 传入自定义 memory_dir 时，默认候选目录跟随到同级。"""
    if (
        candidate_dir == ".minicode/skill-candidates"
        and memory_dir != ".minicode/memory"
    ):
        return str(Path(memory_dir).parent / "skill-candidates")
    return candidate_dir

def main() -> None:
    """解析命令行参数，并根据模式输出 JSON trace 或摘要文本。"""
    parser = argparse.ArgumentParser(description="MiniCode CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    fixed_parser = subparsers.add_parser("fixed")
    fixed_parser.add_argument("task")
    fixed_parser.add_argument("--workspace", default=".")
    fixed_parser.add_argument("--save-trace", action="store_true")
    fixed_parser.add_argument("--trace-dir", default=".minicode/traces")

    agent_parser = subparsers.add_parser("agent")
    agent_parser.add_argument("task")
    agent_parser.add_argument("--workspace", default=".")
    agent_parser.add_argument("--config", default="config.toml")
    agent_parser.add_argument("--save-trace", action="store_true")
    agent_parser.add_argument("--trace-dir", default=".minicode/traces")
    agent_parser.add_argument("--session-id", default="")
    agent_parser.add_argument("--session-dir", default=".minicode/sessions")
    agent_parser.add_argument("--session-title", default="")
    agent_parser.add_argument("--memory-dir", default=".minicode/memory")
    agent_parser.add_argument("--memory-budget-chars", type=int, default=1800)
    agent_parser.add_argument("--context-budget-chars", type=int, default=4000)
    agent_parser.add_argument("--context-budget-tokens", type=int, default=0)
    agent_parser.add_argument("--tool-result-budget-chars", type=int, default=1200)
    agent_parser.add_argument("--artifact-dir", default=".minicode/artifacts")
    agent_parser.add_argument("--artifact-threshold-chars", type=int, default=8000)
    agent_parser.add_argument("--prompt-cache-dir", default=".minicode/prompt-cache")
    agent_parser.add_argument(
        "--skill-candidate-dir",
        default=".minicode/skill-candidates",
    )

    trace_parser = subparsers.add_parser("trace")
    trace_parser.add_argument("path")
    trace_parser.add_argument("--detail", action="store_true")
    trace_parser.add_argument("--max-content", type=int, default=2000)
    trace_parser.add_argument("--markdown", action="store_true")
    trace_parser.add_argument("--output", default="")

    traces_parser = subparsers.add_parser("traces")
    traces_parser.add_argument("--trace-dir", default=".minicode/traces")
    traces_parser.add_argument("--limit", type=int, default=10)
    traces_parser.add_argument("--mode", default="")
    traces_parser.add_argument("--provider", default="")
    traces_parser.add_argument("--model", default="")
    traces_parser.add_argument("--task-contains", default="")

    cleanup_parser = subparsers.add_parser("cleanup-traces")
    cleanup_parser.add_argument("--trace-dir", default=".minicode/traces")
    cleanup_parser.add_argument("--keep", type=int, default=20)

    memory_review_parser = subparsers.add_parser("memory-review")
    memory_review_parser.add_argument("--session-dir", default=".minicode/sessions")
    memory_review_parser.add_argument("--memory-dir", default=".minicode/memory")
    memory_review_parser.add_argument(
        "--skill-candidate-dir",
        default=".minicode/skill-candidates",
    )
    memory_review_parser.add_argument("--sample-query", default="")
    memory_review_parser.add_argument("--memory-budget-chars", type=int, default=1800)

    context_review_parser = subparsers.add_parser("context-review")
    context_review_parser.add_argument("path")

    skill_candidate_parser = subparsers.add_parser("skill-candidate-review")
    skill_candidate_parser.add_argument(
        "action",
        choices=["generate", "list", "approve", "reject", "promote"],
    )
    skill_candidate_parser.add_argument("--candidate-dir", default=".minicode/skill-candidates")
    skill_candidate_parser.add_argument("--memory-dir", default=".minicode/memory")
    skill_candidate_parser.add_argument("--skills-root", default=".minicode/skills")
    skill_candidate_parser.add_argument("--candidate-id", default="")
    skill_candidate_parser.add_argument("--note", default="")
    skill_candidate_parser.add_argument("--force", action="store_true")

    args = parser.parse_args()

    if args.command == "fixed":
        trace = run_task(args.task, args.workspace)
        trace = maybe_save_trace(trace, args.save_trace, args.trace_dir)
        print(json.dumps(trace, ensure_ascii=False, indent=2))
    elif args.command == "agent":
        trace = run_agent_task(
            args.task,
            args.workspace,
            args.config,
            session_id=args.session_id,
            session_dir=args.session_dir,
            session_title=args.session_title,
            memory_dir=args.memory_dir,
            memory_budget_chars=args.memory_budget_chars,
            context_budget_chars=args.context_budget_chars,
            context_budget_tokens=args.context_budget_tokens,
            tool_result_budget_chars=args.tool_result_budget_chars,
            artifact_dir=args.artifact_dir,
            artifact_threshold_chars=args.artifact_threshold_chars,
            prompt_cache_dir=args.prompt_cache_dir,
            skill_candidate_dir=args.skill_candidate_dir,
        )
        trace = maybe_save_trace(trace, args.save_trace, args.trace_dir)
        print(json.dumps(trace, ensure_ascii=False, indent=2))
    elif args.command == "trace":
        print(
            run_trace_viewer(
                args.path,
                detail=args.detail,
                max_content=args.max_content,
                markdown=args.markdown,
                output=args.output,
            )
        )
    elif args.command == "traces":
        print(
            run_trace_list(
                args.trace_dir,
                args.limit,
                mode=args.mode,
                provider=args.provider,
                model=args.model,
                task_contains=args.task_contains,
            )
        )
    elif args.command == "cleanup-traces":
        print(run_trace_cleanup(args.trace_dir, args.keep))
    elif args.command == "memory-review":
        report = run_memory_review(
            session_dir=args.session_dir,
            memory_dir=args.memory_dir,
            skill_candidate_dir=args.skill_candidate_dir,
            sample_query=args.sample_query,
            memory_budget_chars=args.memory_budget_chars,
        )
        print(json.dumps(report, ensure_ascii=False, indent=2))
    elif args.command == "context-review":
        report = run_context_review(args.path)
        print(json.dumps(report, ensure_ascii=False, indent=2))
    elif args.command == "skill-candidate-review":
        report = run_skill_candidate_review(
            action=args.action,
            candidate_dir=args.candidate_dir,
            memory_dir=args.memory_dir,
            skills_root=args.skills_root,
            candidate_id=args.candidate_id,
            note=args.note,
            force=args.force,
        )
        print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
