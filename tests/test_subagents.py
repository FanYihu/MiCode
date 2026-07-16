from minicode.agent import AgentAction, MiniCodeAgent
from minicode.models import RunStatus
from minicode.subagents import (
    ForkedSubAgentExecutor,
    ImplementerSubAgent,
    MultiAgentReviewPipeline,
    ReviewerSubAgent,
    RoleBasedSubAgentExecutor,
    SubAgentPolicy,
    SubAgentResult,
    SubAgentTask,
    TesterSubAgent,
    create_default_subagent_executor,
    create_subagent_tool,
)
from minicode.tools.file import FileTools
from minicode.tools.shell import ShellTools
from minicode.tools.default import create_default_tool_registry
from minicode.tools.registry import ToolRegistry
from minicode.workspace import Workspace


class RecordingExecutor:
    """测试 executor：记录收到的受控任务并返回成功摘要。"""

    def __init__(self):
        self.tasks = []

    def execute(self, task):
        self.tasks.append(task)
        return SubAgentResult(
            task_id=task.id,
            role=task.role,
            status="completed",
            summary="检查完成，没有发现阻塞问题。",
            evidence=["tests passed"],
        )


def test_subagent_task_and_result_are_trace_ready():
    task = SubAgentTask(
        role="reviewer",
        objective="Review the diff",
        allowed_tools=["read_file", "git_diff"],
        parent_run_id="run-1",
    )
    result = SubAgentResult(
        task_id=task.id,
        role=task.role,
        status="completed",
        summary="No findings.",
        evidence=["git diff inspected"],
    )

    assert task.to_dict()["parent_run_id"] == "run-1"
    assert result.ok is True
    assert result.to_dict()["evidence"] == ["git diff inspected"]


def test_run_subagent_tool_applies_policy_owned_boundaries():
    executor = RecordingExecutor()
    policy = SubAgentPolicy(
        allowed_tools_by_role={"reviewer": ["read_file"]},
        allowed_paths=["src"],
        max_steps=3,
    )
    registry = ToolRegistry()
    registry.register(
        create_subagent_tool(
            executor,
            policy=policy,
            parent_run_id="run-parent",
        )
    )

    result = registry.call(
        "run_subagent",
        {
            "role": "reviewer",
            "objective": "Review models.py",
            "context": "Focus on state transitions.",
            "max_steps": 99,
        },
    )

    task = executor.tasks[0]
    assert result.ok is True
    assert result.output == "检查完成，没有发现阻塞问题。"
    assert task.allowed_tools == ["read_file"]
    assert task.allowed_paths == ["src"]
    assert task.max_steps == 3
    assert task.parent_run_id == "run-parent"
    assert result.metadata["details"]["subagent_result"]["evidence"] == [
        "tests passed"
    ]


def test_run_subagent_tool_rejects_role_outside_policy():
    executor = RecordingExecutor()
    registry = ToolRegistry()
    registry.register(create_subagent_tool(executor))

    result = registry.call(
        "run_subagent",
        {"role": "admin", "objective": "Take control"},
    )

    assert result.ok is False
    assert result.metadata["error"] == "unsupported_subagent_role"
    assert executor.tasks == []


def test_run_subagent_tool_rejects_mismatched_result():
    class WrongExecutor:
        def execute(self, task):
            return SubAgentResult(
                task_id="subtask:other",
                role=task.role,
                status="completed",
                summary="Wrong task.",
            )

    registry = ToolRegistry()
    registry.register(create_subagent_tool(WrongExecutor()))

    result = registry.call(
        "run_subagent",
        {"role": "reviewer", "objective": "Review code"},
    )

    assert result.ok is False
    assert result.metadata["error"] == "invalid_subagent_result"


def test_default_registry_only_registers_subagent_when_executor_exists(tmp_path):
    workspace = Workspace(str(tmp_path))
    without_executor = create_default_tool_registry(workspace)
    executor = RecordingExecutor()
    with_executor = create_default_tool_registry(
        workspace,
        subagent_executor=executor,
    )

    assert "run_subagent" not in without_executor.list_names()
    assert "run_subagent" in with_executor.list_names()
    schema = {
        item["function"]["name"]: item["function"]["parameters"]
        for item in with_executor.openai_tools()
    }
    assert schema["run_subagent"]["required"] == ["role", "objective"]
    assert "allowed_tools" not in schema["run_subagent"]["properties"]


def test_agent_delegates_subtask_through_default_tool_registry(tmp_path):
    executor = RecordingExecutor()

    class DelegatingLLM:
        def __init__(self):
            self.calls = 0
            self.tool_definitions = []

        def set_tool_descriptions(self, descriptions):
            self.descriptions = descriptions

        def set_tool_definitions(self, definitions):
            self.tool_definitions = definitions

        def next_action(self, task, observations):
            self.calls += 1
            if self.calls == 1:
                return AgentAction(
                    tool="run_subagent",
                    args={
                        "role": "reviewer",
                        "objective": "Review the current change",
                    },
                )
            return AgentAction(
                tool="",
                args={"answer": observations[-1]},
                final=True,
            )

    llm = DelegatingLLM()
    trace = MiniCodeAgent(
        Workspace(str(tmp_path)),
        llm,
        subagent_executor=executor,
    ).run("delegate review")

    details = trace["events"][0]["metadata"]["details"]
    assert trace["run"]["status"] == RunStatus.COMPLETED.value
    assert executor.tasks[0].parent_run_id == trace["run"]["id"]
    assert details["subagent_task"]["role"] == "reviewer"
    assert details["subagent_result"]["status"] == "completed"
    assert trace["events"][-1]["content"] == "检查完成，没有发现阻塞问题。"


def test_reviewer_subagent_returns_clean_summary_for_safe_context():
    reviewer = ReviewerSubAgent()
    task = SubAgentTask(
        role="reviewer",
        objective="Review documentation-only change",
        context="Updated docs and ran pytest successfully.",
    )

    result = reviewer.execute(task)

    assert result.ok is True
    assert result.summary == "ReviewerSubAgent: no blocking findings."
    assert result.metadata["finding_count"] == 0


def test_reviewer_subagent_reports_structured_findings():
    reviewer = ReviewerSubAgent()
    task = SubAgentTask(
        role="reviewer",
        objective="实现 provider config",
        context='api_key = "sk-liveabcdef123456"\nrun_shell("rm -rf /")',
    )

    result = reviewer.execute(task)

    findings = result.metadata["findings"]
    titles = {finding["title"] for finding in findings}
    assert result.ok is True
    assert result.metadata["finding_count"] >= 2
    assert "Possible secret exposure" in titles
    assert "Destructive root removal command" in titles
    assert "Missing test evidence" in titles


def test_role_based_subagent_executor_dispatches_by_role():
    router = RoleBasedSubAgentExecutor({"reviewer": ReviewerSubAgent()})
    task = SubAgentTask(
        role="reviewer",
        objective="Review change",
        context="Tests passed.",
    )

    result = router.execute(task)

    assert result.ok is True
    assert result.role == "reviewer"


def test_role_based_subagent_executor_reports_missing_executor():
    router = RoleBasedSubAgentExecutor()
    task = SubAgentTask(role="tester", objective="Run tests")

    result = router.execute(task)

    assert result.ok is False
    assert result.summary == "No subagent executor registered for role: tester"
    assert result.metadata["error"] == "missing_subagent_executor"


def test_default_subagent_executor_without_workspace_registers_reviewer_only():
    executor = create_default_subagent_executor()
    reviewer_task = SubAgentTask(role="reviewer", objective="Review code")
    tester_task = SubAgentTask(role="tester", objective="Run tests")

    assert executor.execute(reviewer_task).ok is True
    assert executor.execute(tester_task).ok is False


def test_reviewer_subagent_runs_through_tool_registry_metadata():
    registry = ToolRegistry()
    registry.register(
        create_subagent_tool(
            RoleBasedSubAgentExecutor({"reviewer": ReviewerSubAgent()}),
            parent_run_id="run-main",
        )
    )

    result = registry.call(
        "run_subagent",
        {
            "role": "reviewer",
            "objective": "实现 risky change",
            "context": "TODO: add tests later",
        },
    )

    details = result.metadata["details"]
    findings = details["subagent_result"]["metadata"]["findings"]
    assert result.ok is True
    assert details["subagent_task"]["parent_run_id"] == "run-main"
    assert details["subagent_result"]["role"] == "reviewer"
    assert findings[0]["title"] == "TODO left in implementation"


def test_tester_subagent_runs_default_pytest_command(tmp_path):
    tests_dir = tmp_path / "tests"
    tests_dir.mkdir()
    (tests_dir / "test_sample.py").write_text(
        "def test_sample():\n    assert 1 + 1 == 2\n",
        encoding="utf-8",
    )
    tester = TesterSubAgent(ShellTools(Workspace(str(tmp_path))))
    task = SubAgentTask(role="tester", objective="Run tests")

    result = tester.execute(task)

    assert result.ok is True
    assert result.summary == "TesterSubAgent: passed command=python3 -m pytest tests -q"
    assert result.metadata["command"] == "python3 -m pytest tests -q"
    assert result.metadata["exit_code"] == 0


def test_tester_subagent_reports_failed_tests(tmp_path):
    tests_dir = tmp_path / "tests"
    tests_dir.mkdir()
    (tests_dir / "test_failure.py").write_text(
        "def test_failure():\n    assert False\n",
        encoding="utf-8",
    )
    tester = TesterSubAgent(ShellTools(Workspace(str(tmp_path))))
    task = SubAgentTask(
        role="tester",
        objective="Run targeted tests",
        context="command: python3 -m pytest tests/test_failure.py -q",
    )

    result = tester.execute(task)

    assert result.ok is False
    assert result.metadata["command"] == "python3 -m pytest tests/test_failure.py -q"
    assert result.metadata["exit_code"] == 1
    assert "TesterSubAgent: failed" in result.summary


def test_tester_subagent_blocks_non_test_shell_command(tmp_path):
    tester = TesterSubAgent(ShellTools(Workspace(str(tmp_path))))
    task = SubAgentTask(
        role="tester",
        objective="Run tests",
        context="command: rm -rf /",
    )

    result = tester.execute(task)

    assert result.ok is False
    assert result.metadata["error"] == "unsupported_test_command"
    assert result.metadata["command"] == "rm -rf /"


def test_tester_subagent_blocks_shell_chaining(tmp_path):
    tester = TesterSubAgent(ShellTools(Workspace(str(tmp_path))))
    task = SubAgentTask(
        role="tester",
        objective="Run tests",
        context="command: python3 -m pytest tests -q && rm -rf /",
    )

    result = tester.execute(task)

    assert result.ok is False
    assert result.metadata["error"] == "unsupported_test_command"


def test_default_subagent_executor_with_workspace_registers_tester(tmp_path):
    tests_dir = tmp_path / "tests"
    tests_dir.mkdir()
    (tests_dir / "test_sample.py").write_text(
        "def test_sample():\n    assert True\n",
        encoding="utf-8",
    )
    executor = create_default_subagent_executor(Workspace(str(tmp_path)))
    tester_task = SubAgentTask(role="tester", objective="Run tests")

    assert executor.execute(tester_task).ok is True


def test_tester_subagent_runs_through_tool_registry_metadata(tmp_path):
    tests_dir = tmp_path / "tests"
    tests_dir.mkdir()
    (tests_dir / "test_sample.py").write_text(
        "def test_sample():\n    assert True\n",
        encoding="utf-8",
    )
    registry = ToolRegistry()
    registry.register(
        create_subagent_tool(
            create_default_subagent_executor(Workspace(str(tmp_path))),
            parent_run_id="run-main",
        )
    )

    result = registry.call(
        "run_subagent",
        {
            "role": "tester",
            "objective": "Run tests",
            "context": "command: python3 -m pytest tests -q",
        },
    )

    details = result.metadata["details"]
    assert result.ok is True
    assert details["subagent_task"]["allowed_tools"] == [
        "list_files",
        "read_file",
        "run_shell",
    ]
    assert details["subagent_result"]["metadata"]["exit_code"] == 0


def test_implementer_subagent_replaces_text_from_context_json(tmp_path):
    file_path = tmp_path / "hello.py"
    file_path.write_text("print('old')\n", encoding="utf-8")
    implementer = ImplementerSubAgent(FileTools(Workspace(str(tmp_path))))
    task = SubAgentTask(
        role="implementer",
        objective="Update greeting",
        context='{"operations":[{"type":"replace_text","path":"hello.py","old":"old","new":"new"}]}',
        allowed_tools=["replace_text"],
    )

    result = implementer.execute(task)

    assert result.ok is True
    assert file_path.read_text(encoding="utf-8") == "print('new')\n"
    assert result.changed_paths == ["hello.py"]
    assert "-print('old')" in result.metadata["diffs"][0]
    assert "+print('new')" in result.metadata["diffs"][0]


def test_implementer_subagent_writes_file_from_context_json(tmp_path):
    implementer = ImplementerSubAgent(FileTools(Workspace(str(tmp_path))))
    task = SubAgentTask(
        role="implementer",
        objective="Create module",
        context=(
            "Apply this change:\n"
            '{"operations":[{"type":"write_file","path":"src/app.py","content":"VALUE = 1\\n"}]}'
        ),
        allowed_tools=["write_file"],
    )

    result = implementer.execute(task)

    assert result.ok is True
    assert (tmp_path / "src" / "app.py").read_text(encoding="utf-8") == "VALUE = 1\n"
    assert result.changed_paths == ["src/app.py"]
    assert "+VALUE = 1" in result.metadata["diffs"][0]


def test_implementer_subagent_rejects_tool_outside_task_policy(tmp_path):
    implementer = ImplementerSubAgent(FileTools(Workspace(str(tmp_path))))
    task = SubAgentTask(
        role="implementer",
        objective="Create module",
        context='{"operations":[{"type":"write_file","path":"app.py","content":"x = 1\\n"}]}',
        allowed_tools=["replace_text"],
    )

    result = implementer.execute(task)

    assert result.ok is False
    assert result.metadata["error"] == "operation_not_allowed"
    assert not (tmp_path / "app.py").exists()


def test_implementer_subagent_rejects_missing_operations_json(tmp_path):
    implementer = ImplementerSubAgent(FileTools(Workspace(str(tmp_path))))
    task = SubAgentTask(
        role="implementer",
        objective="Change code",
        context="please update the file somehow",
        allowed_tools=["replace_text", "write_file"],
    )

    result = implementer.execute(task)

    assert result.ok is False
    assert result.metadata["error"] == "invalid_operations"


def test_default_subagent_executor_with_workspace_registers_implementer(tmp_path):
    executor = create_default_subagent_executor(Workspace(str(tmp_path)))
    task = SubAgentTask(
        role="implementer",
        objective="Create file",
        context='{"operations":[{"type":"write_file","path":"generated.py","content":"x = 1\\n"}]}',
        allowed_tools=["write_file"],
    )

    result = executor.execute(task)

    assert result.ok is True
    assert (tmp_path / "generated.py").read_text(encoding="utf-8") == "x = 1\n"


def test_implementer_subagent_runs_through_tool_registry_metadata(tmp_path):
    registry = ToolRegistry()
    registry.register(
        create_subagent_tool(
            create_default_subagent_executor(Workspace(str(tmp_path))),
            parent_run_id="run-main",
        )
    )

    result = registry.call(
        "run_subagent",
        {
            "role": "implementer",
            "objective": "Create file",
            "context": '{"operations":[{"type":"write_file","path":"app.py","content":"x = 1\\n"}]}',
        },
    )

    details = result.metadata["details"]
    subagent_result = details["subagent_result"]
    assert result.ok is True
    assert (tmp_path / "app.py").read_text(encoding="utf-8") == "x = 1\n"
    assert details["subagent_task"]["allowed_tools"] == [
        "list_files",
        "read_file",
        "replace_text",
        "write_file",
        "run_shell",
        "git_diff",
    ]
    assert subagent_result["changed_paths"] == ["app.py"]
    assert subagent_result["metadata"]["operation_count"] == 1


def test_default_registry_approval_hook_allows_safe_implementer_write(tmp_path):
    registry = create_default_tool_registry(
        Workspace(str(tmp_path)),
        subagent_executor=create_default_subagent_executor(Workspace(str(tmp_path))),
    )

    result = registry.call(
        "run_subagent",
        {
            "role": "implementer",
            "objective": "Create module",
            "context": '{"operations":[{"type":"write_file","path":"safe.py","content":"x = 1\\n"}]}',
        },
    )

    assert result.ok is True
    assert (tmp_path / "safe.py").read_text(encoding="utf-8") == "x = 1\n"
    approval = result.metadata["details"]["subagent_approval"]
    assert approval["status"] == "approved"
    assert approval["decisions"][0]["path"] == "safe.py"


def test_default_registry_approval_hook_blocks_sensitive_implementer_write(tmp_path):
    registry = create_default_tool_registry(
        Workspace(str(tmp_path)),
        subagent_executor=create_default_subagent_executor(Workspace(str(tmp_path))),
    )

    result = registry.call(
        "run_subagent",
        {
            "role": "implementer",
            "objective": "Write env",
            "context": '{"operations":[{"type":"write_file","path":".env","content":"SECRET=1\\n"}]}',
        },
    )

    assert result.ok is False
    assert result.metadata["error"] == "subagent_write_not_approved"
    assert result.metadata["details"]["subagent_approval"]["status"] == "blocked"
    assert not (tmp_path / ".env").exists()


def test_forked_subagent_executor_keeps_original_workspace_clean(tmp_path):
    original = tmp_path / "app.py"
    original.write_text("value = 1\n", encoding="utf-8")
    forked = ForkedSubAgentExecutor(
        Workspace(str(tmp_path)),
        create_default_subagent_executor,
        keep_forks=False,
    )
    task = SubAgentTask(
        role="implementer",
        objective="Change value in fork",
        context='{"operations":[{"type":"replace_text","path":"app.py","old":"value = 1","new":"value = 2"}]}',
        allowed_tools=["replace_text", "write_file"],
    )

    result = forked.execute(task)

    assert result.ok is True
    assert original.read_text(encoding="utf-8") == "value = 1\n"
    assert result.metadata["fork_mode"]["enabled"] is True
    assert result.metadata["fork_mode"]["kept"] is False


def test_multi_agent_review_pipeline_approves_clean_change(tmp_path):
    tests_dir = tmp_path / "tests"
    tests_dir.mkdir()
    (tests_dir / "test_app.py").write_text(
        "def test_app():\n    assert True\n",
        encoding="utf-8",
    )
    pipeline = MultiAgentReviewPipeline(
        create_default_subagent_executor(Workspace(str(tmp_path)))
    )

    report = pipeline.run(
        objective="Create app module",
        operations_context='{"operations":[{"type":"write_file","path":"app.py","content":"VALUE = 1\\n"}]}',
        test_context="command: python3 -m pytest tests -q",
        review_context="Implementation includes tests and no secrets.",
    )

    assert report.approved is True
    assert report.summary == "MultiAgentReview: approved."
    assert [result.role for result in report.results] == [
        "implementer",
        "tester",
        "reviewer",
    ]
    assert report.to_dict()["approved"] is True


def test_multi_agent_review_pipeline_stops_when_tests_fail(tmp_path):
    tests_dir = tmp_path / "tests"
    tests_dir.mkdir()
    (tests_dir / "test_app.py").write_text(
        "def test_app():\n    assert False\n",
        encoding="utf-8",
    )
    pipeline = MultiAgentReviewPipeline(
        create_default_subagent_executor(Workspace(str(tmp_path)))
    )

    report = pipeline.run(
        objective="Create app module",
        operations_context='{"operations":[{"type":"write_file","path":"app.py","content":"VALUE = 1\\n"}]}',
        test_context="command: python3 -m pytest tests -q",
        review_context="Implementation includes tests.",
    )

    assert report.approved is False
    assert report.summary == "MultiAgentReview: tests failed."
    assert [result.role for result in report.results] == ["implementer", "tester"]
