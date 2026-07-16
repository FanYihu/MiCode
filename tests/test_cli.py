import json
from pathlib import Path

from minicode.agent import AgentAction
from minicode.cli import (
    maybe_save_trace,
    run_context_review,
    run_memory_review,
    run_agent_task,
    run_skill_candidate_review,
    run_task,
    run_trace_cleanup,
    run_trace_list,
    run_trace_viewer,
)
from minicode.models import RunStatus, StepType


def test_cli_list_files(tmp_path):
    (tmp_path / "README.md").write_text("hello", encoding="utf-8")

    trace = run_task("list files", str(tmp_path))

    assert trace["run"]["status"] == RunStatus.COMPLETED.value
    assert trace["steps"][0]["type"] == StepType.TOOL.value
    assert trace["steps"][0]["metadata"]["tool"] == "list_files"
    assert "README.md" in trace["events"][0]["content"]
    assert trace["run"]["metadata"]["task"] == "list files"
    assert trace["run"]["metadata"]["mode"] == "fixed"
    assert trace["run"]["metadata"]["workspace"] == str(tmp_path)


def test_cli_unsupported_task_completes_with_message(tmp_path):
    trace = run_task("unknown task", str(tmp_path))

    assert trace["run"]["status"] == RunStatus.COMPLETED.value
    assert trace["steps"][0]["type"] == StepType.FINAL.value
    assert "不支持的任务" in trace["events"][0]["content"]


def test_cli_run_tests_records_shell_result(tmp_path):
    (tmp_path / "test_sample.py").write_text(
        "def test_sample():\n    assert True\n",
        encoding="utf-8",
    )

    trace = run_task("run tests", str(tmp_path))

    assert trace["run"]["status"] == RunStatus.COMPLETED.value
    assert trace["steps"][0]["metadata"]["tool"] == "shell"
    assert trace["events"][0]["metadata"]["exit_code"] == 0


def test_maybe_save_trace_adds_saved_trace_path(tmp_path):
    trace = {"run": {"status": "completed"}, "steps": [], "events": []}

    result = maybe_save_trace(trace, True, str(tmp_path / "traces"))

    assert "saved_trace_path" in result
    assert Path(result["saved_trace_path"]).exists()


def test_maybe_save_trace_keeps_trace_when_disabled(tmp_path):
    trace = {"run": {"status": "completed"}, "steps": [], "events": []}

    result = maybe_save_trace(trace, False, str(tmp_path / "traces"))

    assert "saved_trace_path" not in result
    assert not (tmp_path / "traces").exists()


def test_run_agent_task_uses_configured_llm(monkeypatch, tmp_path):
    class SequenceLLM:
        def __init__(self):
            self.actions = [
                AgentAction(tool="list_files", args={}),
                AgentAction(tool="", args={"answer": "完成"}, final=True),
            ]
            self.index = 0

        def next_action(self, task, observations):
            action = self.actions[self.index]
            self.index += 1
            return action

    monkeypatch.setattr("minicode.cli.create_llm_from_config", lambda path: SequenceLLM())
    monkeypatch.setattr("minicode.cli.discover_user_skills", lambda: [])
    (tmp_path / "README.md").write_text("hello", encoding="utf-8")

    trace = run_agent_task("列出文件", str(tmp_path), "config.toml")

    assert trace["run"]["status"] == RunStatus.COMPLETED.value
    assert trace["steps"][0]["metadata"]["tool"] == "list_files"
    assert trace["events"][-1]["content"] == "完成"
    assert trace["run"]["metadata"]["task"] == "列出文件"
    assert trace["run"]["metadata"]["mode"] == "agent"
    assert trace["run"]["metadata"]["workspace"] == str(tmp_path)
    assert trace["run"]["metadata"]["config"] == "config.toml"


def test_run_agent_task_discovers_project_skills_without_routing(monkeypatch, tmp_path):
    class RouterAndAgentClient:
        def __init__(self):
            self.calls = 0

        def generate(self, prompt):
            self.calls += 1
            if "Skill Router" in prompt:
                return '{"skills":["python-test"]}'
            assert "python-test" in prompt
            assert "Use pytest." not in prompt
            return '{"tool":"","args":{"answer":"完成"},"final":true}'

    class TextLikeLLM:
        def __init__(self):
            from minicode.agent import DEFAULT_TOOL_DESCRIPTIONS

            self.client = RouterAndAgentClient()
            self.tool_descriptions = DEFAULT_TOOL_DESCRIPTIONS
            self.skill_summaries = ""

        def set_tool_descriptions(self, tool_descriptions):
            self.tool_descriptions = tool_descriptions

        def set_skill_summaries(self, skill_summaries):
            self.skill_summaries = skill_summaries

        def next_action(self, task, observations):
            from minicode.agent import build_action_prompt, parse_action

            prompt = build_action_prompt(
                task,
                observations,
                self.tool_descriptions,
                self.skill_summaries,
            )
            return parse_action(self.client.generate(prompt))

    llm = TextLikeLLM()
    monkeypatch.setattr("minicode.cli.create_llm_from_config", lambda path: llm)
    monkeypatch.setattr("minicode.cli.discover_user_skills", lambda: [])
    for index in range(21):
        skill_dir = tmp_path / ".minicode" / "skills" / f"skill-{index}"
        skill_dir.mkdir(parents=True)
        (skill_dir / "SKILL.md").write_text(
            "# General\n\nGeneral helper.",
            encoding="utf-8",
        )
    selected_dir = tmp_path / ".minicode" / "skills" / "python-test"
    selected_dir.mkdir(parents=True)
    (selected_dir / "SKILL.md").write_text(
        "# Python Test\n\nRun Python tests safely.\n\nUse pytest.",
        encoding="utf-8",
    )

    trace = run_agent_task("run tests", str(tmp_path), "config.toml")

    assert trace["run"]["status"] == RunStatus.COMPLETED.value
    assert trace["run"]["metadata"]["skills"][0] == "python-test"
    assert "skill-0" in trace["run"]["metadata"]["skills"]
    assert trace["events"][-1]["content"] == "完成"
    assert llm.client.calls == 1


def test_run_agent_task_routes_user_skills_with_llm(monkeypatch, tmp_path):
    class RouterAndAgentClient:
        def __init__(self):
            self.calls = 0

        def generate(self, prompt):
            self.calls += 1
            if "task intent extractor" in prompt:
                return (
                    '{"goal":"run tests","task_type":"testing",'
                    '"keywords":["pytest"],"tags":["test"]}'
                )
            if "Skill Router" in prompt:
                assert "user-test" in prompt
                return '{"skills":["user-test"]}'
            assert "user-test" in prompt
            return '{"tool":"","args":{"answer":"完成"},"final":true}'

    class TextLikeLLM:
        def __init__(self):
            from minicode.agent import DEFAULT_TOOL_DESCRIPTIONS

            self.client = RouterAndAgentClient()
            self.tool_descriptions = DEFAULT_TOOL_DESCRIPTIONS
            self.skill_summaries = ""

        def set_tool_descriptions(self, tool_descriptions):
            self.tool_descriptions = tool_descriptions

        def set_skill_summaries(self, skill_summaries):
            self.skill_summaries = skill_summaries

        def next_action(self, task, observations):
            from minicode.agent import build_action_prompt, parse_action

            prompt = build_action_prompt(
                task,
                observations,
                self.tool_descriptions,
                self.skill_summaries,
            )
            return parse_action(self.client.generate(prompt))

    from minicode.skills import Skill

    llm = TextLikeLLM()
    monkeypatch.setattr("minicode.cli.create_llm_from_config", lambda path: llm)
    monkeypatch.setattr(
        "minicode.cli.discover_user_skills",
        lambda: [Skill(name="user-test", description="User test flow.", content="")],
    )

    trace = run_agent_task("run tests", str(tmp_path), "config.toml")

    assert trace["run"]["status"] == RunStatus.COMPLETED.value
    assert trace["run"]["metadata"]["skills"] == ["user-test"]
    assert llm.client.calls == 3


def test_run_agent_task_records_run_in_session(monkeypatch, tmp_path):
    class Client:
        provider = "mimo"
        model = "mimo-v2.5-pro"

        def generate(self, prompt):
            return '{"tool":"","args":{"answer":"完成"},"final":true}'

    class TextLikeLLM:
        def __init__(self):
            from minicode.agent import TextLLM

            self.inner = TextLLM(Client())
            self.client = self.inner.client

        def set_tool_descriptions(self, tool_descriptions):
            self.inner.set_tool_descriptions(tool_descriptions)

        def set_skill_summaries(self, skill_summaries):
            self.inner.set_skill_summaries(skill_summaries)

        def next_action(self, task, observations):
            return self.inner.next_action(task, observations)

    session_dir = tmp_path / "sessions"
    memory_dir = tmp_path / "memory"
    monkeypatch.setattr("minicode.cli.create_llm_from_config", lambda path: TextLikeLLM())
    monkeypatch.setattr("minicode.cli.discover_user_skills", lambda: [])

    trace = run_agent_task(
        "继续学习",
        str(tmp_path),
        "config.toml",
        session_id="session-1",
        session_dir=str(session_dir),
        session_title="MiniCode 学习",
        memory_dir=str(memory_dir),
        skill_candidate_dir=str(tmp_path / "skill-candidates"),
    )

    session_path = session_dir / "session-1.json"
    messages_path = session_dir / "session-1.messages.json"
    working_memory_path = session_dir / "session-1.working_memory.json"
    summary_path = session_dir / "session-1.summary.json"
    episodic_memory_path = memory_dir / "episodes.json"
    semantic_memory_path = memory_dir / "semantic.json"
    procedural_memory_path = memory_dir / "procedures.json"
    memory_graph_path = memory_dir / "graph.json"
    skill_candidate_dir = tmp_path / "skill-candidates"
    session = json.loads(session_path.read_text(encoding="utf-8"))
    messages = json.loads(messages_path.read_text(encoding="utf-8"))
    working_memory = json.loads(working_memory_path.read_text(encoding="utf-8"))
    episodes = json.loads(episodic_memory_path.read_text(encoding="utf-8"))
    semantic_memories = json.loads(semantic_memory_path.read_text(encoding="utf-8"))
    procedural_memories = json.loads(procedural_memory_path.read_text(encoding="utf-8"))
    memory_graph = json.loads(memory_graph_path.read_text(encoding="utf-8"))
    skill_candidate_path = next(skill_candidate_dir.glob("*.json"))
    skill_candidate = json.loads(skill_candidate_path.read_text(encoding="utf-8"))

    assert trace["run"]["metadata"]["session_id"] == "session-1"
    assert trace["run"]["metadata"]["session_path"] == str(session_path)
    assert trace["run"]["metadata"]["session_messages_path"] == str(messages_path)
    assert trace["run"]["metadata"]["working_memory_path"] == str(working_memory_path)
    assert trace["run"]["metadata"]["session_summary_path"] == str(summary_path)
    assert trace["run"]["metadata"]["episodic_memory_path"] == str(
        episodic_memory_path
    )
    assert trace["run"]["metadata"]["episodic_memory_id"] == (
        f"episode:{trace['run']['id']}"
    )
    assert trace["run"]["metadata"]["semantic_memory_path"] == str(
        semantic_memory_path
    )
    assert trace["run"]["metadata"]["semantic_memory_ids"]
    assert trace["run"]["metadata"]["procedural_memory_path"] == str(
        procedural_memory_path
    )
    assert trace["run"]["metadata"]["procedural_memory_ids"]
    assert trace["run"]["metadata"]["skill_candidate_ids"]
    assert trace["run"]["metadata"]["skill_candidate_dir"] == str(skill_candidate_dir)
    assert trace["run"]["metadata"]["knowledge_entity_ids"]
    assert trace["run"]["metadata"]["knowledge_relation_count"] > 0
    assert trace["run"]["metadata"]["temporal_fact_status"]["active"] > 0
    assert trace["run"]["metadata"]["memory_graph_path"] == str(memory_graph_path)
    assert trace["run"]["metadata"]["memory_graph_node_ids"]
    assert trace["run"]["metadata"]["memory_graph_edge_ids"]
    assert trace["run"]["metadata"]["memory_graph_size"]["nodes"] == len(
        memory_graph["nodes"]
    )
    assert any(
        node["id"] == f"episode:{trace['run']['id']}"
        for node in memory_graph["nodes"]
    )
    assert any(node["type"] == "entity" for node in memory_graph["nodes"])
    assert "Session Context:" in trace["run"]["metadata"]["compressed_context"]
    assert session["title"] == "MiniCode 学习"
    assert session["run_ids"] == [trace["run"]["id"]]
    assert [message["role"] for message in messages] == ["user", "assistant"]
    assert [message["content"] for message in messages] == ["继续学习", "完成"]
    assert working_memory["current_goal"] == "继续学习"
    assert working_memory["completed"] == ["完成"]
    assert summary_path.exists()
    assert episodes[0]["task"] == "继续学习"
    assert episodes[0]["outcome"] == "完成"
    assert episodes[0]["session_id"] == "session-1"
    assert any(memory["predicate"] == "was_requested" for memory in semantic_memories)
    assert any(memory["predicate"] == "had_outcome" for memory in semantic_memories)
    assert procedural_memories[0]["steps"]
    assert procedural_memories[0]["source_episode_ids"] == [
        f"episode:{trace['run']['id']}"
    ]
    assert skill_candidate["status"] == "draft"
    assert skill_candidate["source_procedure_ids"] == [
        procedural_memories[0]["id"]
    ]


def test_run_skill_candidate_review_generates_and_promotes(tmp_path):
    from minicode.memory.procedural import ProceduralMemory, ProceduralMemoryStore

    memory_dir = tmp_path / "memory"
    candidate_dir = tmp_path / "skill-candidates"
    skills_root = tmp_path / "skills"
    procedure = ProceduralMemory(
        id="procedure:update-cli",
        name="update-cli",
        description="Update CLI safely.",
        steps=["Read CLI.", "Patch parser.", "Run tests."],
        tags=["cli"],
        source_episode_ids=["episode:run-1"],
        source_run_ids=["run-1"],
    )
    ProceduralMemoryStore(str(memory_dir)).upsert_many([procedure])

    generated = run_skill_candidate_review(
        action="generate",
        candidate_dir=str(candidate_dir),
        memory_dir=str(memory_dir),
    )
    candidate_id = generated["candidates"][0]["id"]
    approved = run_skill_candidate_review(
        action="approve",
        candidate_dir=str(candidate_dir),
        candidate_id=candidate_id,
        note="stable flow",
    )
    promoted = run_skill_candidate_review(
        action="promote",
        candidate_dir=str(candidate_dir),
        skills_root=str(skills_root),
        candidate_id=candidate_id,
    )

    assert generated["generated_count"] == 1
    assert approved["candidate"]["status"] == "approved"
    assert promoted["candidate"]["status"] == "promoted"
    assert (skills_root / "update-cli" / "SKILL.md").exists()


def test_run_agent_task_injects_existing_session_context(monkeypatch, tmp_path):
    from minicode.memory.context import SessionSummary, SessionSummaryStore
    from minicode.memory.session import SessionMessage, SessionMessageStore, SessionStore
    from minicode.memory.working import WorkingMemory, WorkingMemoryStore

    class ContextCapturingLLM:
        def __init__(self):
            self.session_context = ""

        def set_tool_descriptions(self, tool_descriptions):
            pass

        def set_session_context(self, session_context):
            self.session_context = session_context

        def next_action(self, task, observations):
            return AgentAction(
                tool="",
                args={"answer": self.session_context},
                final=True,
            )

    session_dir = tmp_path / "sessions"
    memory_dir = tmp_path / "memory"
    SessionStore(str(session_dir)).create(
        title="Memory",
        session_id="session-1",
    )
    SessionMessageStore(str(session_dir)).append_messages(
        "session-1",
        [
            SessionMessage(
                id="old-message",
                session_id="session-1",
                run_id="old-run",
                role="user",
                type="task",
                content="之前在实现 Session",
            )
        ],
    )
    WorkingMemoryStore(str(session_dir)).save(
        WorkingMemory(
            session_id="session-1",
            current_goal="继续记忆系统",
            constraints=["代码要有注释"],
        )
    )
    SessionSummaryStore(str(session_dir)).save(
        SessionSummary(
            session_id="session-1",
            summary="- assistant/text: 已完成 Session",
        )
    )
    llm = ContextCapturingLLM()
    monkeypatch.setattr("minicode.cli.create_llm_from_config", lambda path: llm)
    monkeypatch.setattr("minicode.cli.discover_user_skills", lambda: [])

    trace = run_agent_task(
        "继续学习",
        str(tmp_path),
        "config.toml",
        session_id="session-1",
        session_dir=str(session_dir),
        memory_dir=str(memory_dir),
    )

    final = trace["events"][-1]["content"]
    assert "Current goal: 继续记忆系统" in final
    assert "代码要有注释" in final
    assert "已完成 Session" in final
    assert "之前在实现 Session" in final
    assert trace["run"]["metadata"]["context_assembly"]["layers"][0]["name"] == "session"


def test_run_agent_task_injects_retrieved_long_term_memory(monkeypatch, tmp_path):
    from minicode.memory.semantic import SemanticMemory, SemanticMemoryStore

    class ContextCapturingLLM:
        def __init__(self):
            self.session_context = ""

        def set_tool_descriptions(self, tool_descriptions):
            pass

        def set_session_context(self, session_context):
            self.session_context = session_context

        def next_action(self, task, observations):
            return AgentAction(
                tool="",
                args={"answer": self.session_context},
                final=True,
            )

    memory_dir = tmp_path / "memory"
    SemanticMemoryStore(str(memory_dir)).upsert_many(
        [
            SemanticMemory(
                id="semantic:minicode-uses-pytest",
                fact="MiniCode uses pytest",
                subject="MiniCode",
                predicate="uses",
                object="pytest",
                tags=["test"],
            )
        ]
    )
    llm = ContextCapturingLLM()
    monkeypatch.setattr("minicode.cli.create_llm_from_config", lambda path: llm)
    monkeypatch.setattr("minicode.cli.discover_user_skills", lambda: [])

    trace = run_agent_task(
        "如何使用 pytest",
        str(tmp_path),
        "config.toml",
        memory_dir=str(memory_dir),
    )

    final = trace["events"][-1]["content"]
    assert "Relevant Long-Term Memory:" in final
    assert "MiniCode uses pytest" in final
    assert trace["run"]["metadata"]["retrieved_memory_ids"] == [
        "semantic:minicode-uses-pytest"
    ]
    assert trace["run"]["metadata"]["retrieved_memories"][0]["ranking_score"] > 0
    assert trace["run"]["metadata"]["memory_injection"]["selected_count"] == 1
    assert trace["run"]["metadata"]["memory_injection"]["used_chars"] <= 1800
    assert trace["run"]["metadata"]["context_assembly"]["used_chars"] <= 4000
    assert any(
        layer["name"] == "long_term_memory"
        and layer["included"] is True
        for layer in trace["run"]["metadata"]["context_assembly"]["layers"]
    )


def test_run_agent_task_respects_memory_injection_budget(monkeypatch, tmp_path):
    from minicode.memory.semantic import SemanticMemory, SemanticMemoryStore

    class ContextCapturingLLM:
        def __init__(self):
            self.session_context = ""

        def set_tool_descriptions(self, tool_descriptions):
            pass

        def set_session_context(self, session_context):
            self.session_context = session_context

        def next_action(self, task, observations):
            return AgentAction(
                tool="",
                args={"answer": self.session_context},
                final=True,
            )

    memory_dir = tmp_path / "memory"
    SemanticMemoryStore(str(memory_dir)).upsert_many(
        [
            SemanticMemory(
                id=f"semantic:pytest-{index}",
                fact=f"pytest fact {index} " + "x" * 200,
                subject="pytest",
                predicate="has_fact",
                object=str(index),
                tags=["pytest"],
            )
            for index in range(5)
        ]
    )
    llm = ContextCapturingLLM()
    monkeypatch.setattr("minicode.cli.create_llm_from_config", lambda path: llm)
    monkeypatch.setattr("minicode.cli.discover_user_skills", lambda: [])

    trace = run_agent_task(
        "pytest",
        str(tmp_path),
        "config.toml",
        memory_dir=str(memory_dir),
        memory_budget_chars=180,
    )

    injection = trace["run"]["metadata"]["memory_injection"]
    assert injection["used_chars"] <= 180
    assert injection["selected_count"] < injection["candidate_count"]
    assert injection["omitted_ids"]


def test_run_agent_task_passes_artifact_options_to_agent(monkeypatch, tmp_path):
    class LLM:
        def __init__(self):
            self.calls = 0

        def set_tool_descriptions(self, tool_descriptions):
            pass

        def set_tool_definitions(self, tool_definitions):
            pass

        def next_action(self, task, observations):
            self.calls += 1
            if self.calls == 1:
                return AgentAction(tool="read_file", args={"path": "large.txt"})
            return AgentAction(tool="", args={"answer": observations[-1]}, final=True)

    (tmp_path / "large.txt").write_text("z" * 300, encoding="utf-8")
    monkeypatch.setattr("minicode.cli.create_llm_from_config", lambda path: LLM())
    monkeypatch.setattr("minicode.cli.discover_user_skills", lambda: [])

    trace = run_agent_task(
        "large",
        str(tmp_path),
        "config.toml",
        artifact_dir=str(tmp_path / "my-artifacts"),
        artifact_threshold_chars=100,
        tool_result_budget_chars=80,
    )

    artifact = trace["events"][0]["metadata"]["artifact"]
    assert artifact["artifact_path"].startswith(str(tmp_path / "my-artifacts"))
    assert artifact["artifact_placeholder"] in trace["events"][-1]["content"]


def test_run_agent_task_records_prompt_cache_and_decision_freeze(monkeypatch, tmp_path):
    class LLM:
        def __init__(self):
            self.session_context = ""

        def set_tool_descriptions(self, tool_descriptions):
            pass

        def set_tool_definitions(self, tool_definitions):
            pass

        def set_session_context(self, session_context):
            self.session_context = session_context

        def next_action(self, task, observations):
            return AgentAction(tool="", args={"answer": "完成"}, final=True)

    monkeypatch.setattr("minicode.cli.create_llm_from_config", lambda path: LLM())
    monkeypatch.setattr("minicode.cli.discover_user_skills", lambda: [])

    trace = run_agent_task(
        "cache freeze",
        str(tmp_path),
        "config.toml",
        prompt_cache_dir=str(tmp_path / "prompt-cache"),
    )

    prompt_cache = trace["run"]["metadata"]["prompt_cache"]
    freeze = trace["run"]["metadata"]["decision_freezes"][0]
    assert prompt_cache["prompt_cache_key"].startswith("prompt-cache:")
    assert prompt_cache["prompt_cache_path"].startswith(str(tmp_path / "prompt-cache"))
    assert freeze["prompt_cache_key"] == prompt_cache["prompt_cache_key"]


def test_run_agent_task_respects_context_layer_budget(monkeypatch, tmp_path):
    from minicode.memory.context import SessionSummary, SessionSummaryStore
    from minicode.memory.session import SessionMessage, SessionMessageStore, SessionStore
    from minicode.memory.working import WorkingMemory, WorkingMemoryStore

    class ContextCapturingLLM:
        def __init__(self):
            self.session_context = ""

        def set_tool_descriptions(self, tool_descriptions):
            pass

        def set_session_context(self, session_context):
            self.session_context = session_context

        def next_action(self, task, observations):
            return AgentAction(
                tool="",
                args={"answer": self.session_context},
                final=True,
            )

    session_dir = tmp_path / "sessions"
    memory_dir = tmp_path / "memory"
    SessionStore(str(session_dir)).create(title="Memory", session_id="session-1")
    SessionMessageStore(str(session_dir)).append_messages(
        "session-1",
        [
            SessionMessage(
                id=f"message-{index}",
                session_id="session-1",
                run_id=f"run-{index}",
                role="user",
                type="task",
                content="长会话内容 " + "x" * 160,
            )
            for index in range(5)
        ],
    )
    WorkingMemoryStore(str(session_dir)).save(
        WorkingMemory(
            session_id="session-1",
            current_goal="长上下文测试 " + "y" * 180,
        )
    )
    SessionSummaryStore(str(session_dir)).save(
        SessionSummary(
            session_id="session-1",
            summary="摘要 " + "z" * 300,
        )
    )
    llm = ContextCapturingLLM()
    monkeypatch.setattr("minicode.cli.create_llm_from_config", lambda path: llm)
    monkeypatch.setattr("minicode.cli.discover_user_skills", lambda: [])

    trace = run_agent_task(
        "继续学习",
        str(tmp_path),
        "config.toml",
        session_id="session-1",
        session_dir=str(session_dir),
        memory_dir=str(memory_dir),
        context_budget_chars=220,
        memory_budget_chars=80,
    )

    assembly = trace["run"]["metadata"]["context_assembly"]
    token_estimate = trace["run"]["metadata"]["context_token_estimate"]
    assert assembly["used_chars"] <= 220
    assert assembly["estimated_tokens"] > 0
    assert token_estimate["estimated_tokens"] > 0
    assert any(
        part["name"] == "assembled_context"
        for part in token_estimate["parts"]
    )
    assert len(trace["events"][-1]["content"]) <= 220
    assert any(layer["truncated"] is True for layer in assembly["layers"])


def test_run_agent_task_records_auto_compaction_metadata(monkeypatch, tmp_path):
    from minicode.memory.context import SessionSummary, SessionSummaryStore
    from minicode.memory.session import SessionStore

    class ContextCapturingLLM:
        def __init__(self):
            self.session_context = ""

        def set_tool_descriptions(self, tool_descriptions):
            pass

        def set_session_context(self, session_context):
            self.session_context = session_context

        def next_action(self, task, observations):
            return AgentAction(
                tool="",
                args={"answer": self.session_context},
                final=True,
            )

    session_dir = tmp_path / "sessions"
    memory_dir = tmp_path / "memory"
    SessionStore(str(session_dir)).create(title="Compact", session_id="session-1")
    SessionSummaryStore(str(session_dir)).save(
        SessionSummary(
            session_id="session-1",
            summary="摘要 " + "x" * 400,
        )
    )
    monkeypatch.setattr(
        "minicode.cli.create_llm_from_config",
        lambda path: ContextCapturingLLM(),
    )
    monkeypatch.setattr("minicode.cli.discover_user_skills", lambda: [])

    trace = run_agent_task(
        "继续学习",
        str(tmp_path),
        "config.toml",
        session_id="session-1",
        session_dir=str(session_dir),
        memory_dir=str(memory_dir),
        context_budget_chars=300,
        context_budget_tokens=30,
    )

    compaction = trace["run"]["metadata"]["context_assembly"]["compaction"]

    assert compaction["compacted"] is True
    assert compaction["effective_budget_chars"] == 120
    assert compaction["saved_chars"] > 0


def test_run_trace_viewer_returns_summary(tmp_path):
    trace_path = tmp_path / "trace.json"
    trace_path.write_text(
        '{"run":{"status":"completed"},"steps":[],"events":[]}',
        encoding="utf-8",
    )

    summary = run_trace_viewer(str(trace_path))

    assert "Run: completed" in summary
    assert "Steps: 0" in summary


def test_run_context_review_reports_missing_context_metadata(tmp_path):
    trace_path = tmp_path / "trace.json"
    trace_path.write_text(
        json.dumps({"run": {"metadata": {}}, "steps": [], "events": []}),
        encoding="utf-8",
    )

    report = run_context_review(str(trace_path))

    assert report["ok"] is True
    codes = [issue["code"] for issue in report["issues"]]
    assert "missing_context_assembly" in codes
    assert "missing_prompt_cache" in codes


def test_run_trace_viewer_returns_detail_when_requested(tmp_path):
    trace_path = tmp_path / "trace.json"
    trace_path.write_text(
        '{"run":{"id":"run-1","status":"completed","metadata":{"task":"读取 README"}},"steps":[],"events":[]}',
        encoding="utf-8",
    )

    detail = run_trace_viewer(str(trace_path), detail=True)

    assert "Run" in detail
    assert "run-1" in detail
    assert '"task": "读取 README"' in detail


def test_run_trace_viewer_detail_respects_max_content(tmp_path):
    trace_path = tmp_path / "trace.json"
    trace = {
        "run": {"id": "run-1", "status": "completed", "metadata": {}},
        "steps": [],
        "events": [
            {
                "type": "text",
                "step_id": "step-1",
                "content": "abcdef",
                "metadata": {},
            }
        ],
    }
    trace_path.write_text(json.dumps(trace), encoding="utf-8")

    detail = run_trace_viewer(str(trace_path), detail=True, max_content=3)

    assert "content: abc... [truncated]" in detail


def test_run_trace_viewer_detail_can_disable_content_truncation(tmp_path):
    trace_path = tmp_path / "trace.json"
    trace = {
        "run": {"id": "run-1", "status": "completed", "metadata": {}},
        "steps": [],
        "events": [
            {
                "type": "text",
                "step_id": "step-1",
                "content": "abcdef",
                "metadata": {},
            }
        ],
    }
    trace_path.write_text(json.dumps(trace), encoding="utf-8")

    detail = run_trace_viewer(str(trace_path), detail=True, max_content=0)

    assert "content: abcdef" in detail
    assert "[truncated]" not in detail


def test_run_trace_viewer_returns_markdown_when_requested(tmp_path):
    trace_path = tmp_path / "trace.json"
    trace = {
        "run": {
            "status": "completed",
            "metadata": {"task": "读取 README", "mode": "agent"},
        },
        "steps": [{"type": "final", "metadata": {}}],
        "events": [{"type": "text", "content": "完成"}],
    }
    trace_path.write_text(json.dumps(trace), encoding="utf-8")

    report = run_trace_viewer(str(trace_path), markdown=True)

    assert report.startswith("# MiniCode Trace Report")
    assert "- task: 读取 README" in report
    assert "1. final" in report
    assert "完成" in report


def test_run_trace_viewer_saves_markdown_when_output_is_provided(tmp_path):
    trace_path = tmp_path / "trace.json"
    output_path = tmp_path / "reports" / "trace.md"
    trace = {
        "run": {
            "status": "completed",
            "metadata": {"task": "读取 README", "mode": "agent"},
        },
        "steps": [{"type": "final", "metadata": {}}],
        "events": [{"type": "text", "content": "完成"}],
    }
    trace_path.write_text(json.dumps(trace), encoding="utf-8")

    output = run_trace_viewer(str(trace_path), markdown=True, output=str(output_path))

    assert output == f"Markdown report saved to {output_path}"
    assert output_path.exists()
    assert "# MiniCode Trace Report" in output_path.read_text(encoding="utf-8")


def test_run_trace_viewer_markdown_takes_priority_over_detail(tmp_path):
    trace_path = tmp_path / "trace.json"
    trace = {
        "run": {"id": "run-1", "status": "completed", "metadata": {}},
        "steps": [],
        "events": [],
    }
    trace_path.write_text(json.dumps(trace), encoding="utf-8")

    report = run_trace_viewer(str(trace_path), detail=True, markdown=True)

    assert report.startswith("# MiniCode Trace Report")
    assert "id: run-1" not in report


def test_run_trace_list_returns_numbered_paths(tmp_path):
    trace_dir = tmp_path / "traces"
    trace_dir.mkdir()
    trace_path = trace_dir / "trace.json"
    trace_path.write_text('{"run":{"metadata":{}}}', encoding="utf-8")

    output = run_trace_list(str(trace_dir), limit=10)

    assert output == f"1. {trace_path}"


def test_run_trace_list_returns_message_when_empty(tmp_path):
    output = run_trace_list(str(tmp_path / "missing"), limit=10)

    assert output == "No traces found."


def test_run_trace_list_filters_by_metadata(tmp_path):
    trace_dir = tmp_path / "traces"
    trace_dir.mkdir()
    agent_trace = trace_dir / "agent.json"
    fixed_trace = trace_dir / "fixed.json"
    agent_trace.write_text(
        '{"run":{"metadata":{"mode":"agent","provider":"mimo","model":"mimo-v2.5-pro","task":"读取 README"}}}',
        encoding="utf-8",
    )
    fixed_trace.write_text(
        '{"run":{"metadata":{"mode":"fixed","task":"list files"}}}',
        encoding="utf-8",
    )

    output = run_trace_list(
        str(trace_dir),
        limit=10,
        mode="agent",
        provider="mimo",
        model="mimo-v2.5-pro",
        task_contains="README",
    )

    assert str(agent_trace) in output
    assert str(fixed_trace) not in output


def test_run_trace_cleanup_returns_deleted_count(tmp_path):
    trace_dir = tmp_path / "traces"
    trace_dir.mkdir()
    old_trace = trace_dir / "old.json"
    new_trace = trace_dir / "new.json"
    old_trace.write_text("{}", encoding="utf-8")
    new_trace.write_text("{}", encoding="utf-8")

    import os
    os.utime(old_trace, (1000, 1000))
    os.utime(new_trace, (2000, 2000))

    output = run_trace_cleanup(str(trace_dir), keep=1)

    assert output == "Deleted 1 trace files."
    assert not old_trace.exists()
    assert new_trace.exists()


def test_run_trace_cleanup_returns_empty_message(tmp_path):
    output = run_trace_cleanup(str(tmp_path / "missing"), keep=20)

    assert output == "No trace files deleted."


def test_run_memory_review_returns_empty_report_for_empty_dirs(tmp_path):
    report = run_memory_review(
        session_dir=str(tmp_path / "sessions"),
        memory_dir=str(tmp_path / "memory"),
        skill_candidate_dir=str(tmp_path / "skill-candidates"),
    )

    assert report["ok"] is True
    assert report["summary"]["sessions"] == 0
    assert report["summary"]["episodes"] == 0
    assert report["issues"] == []
