import argparse
import json

from minicode.agent import MiniCodeAgent, create_llm_from_config
from minicode.models import EventType, Run, StepType
from minicode.persistence import save_trace
from minicode.permissions import PermissionDecision, PermissionReviewer
from minicode.shell_tools import ShellTools
from minicode.trace import TraceRecorder
from minicode.workspace import Workspace


def run_task(task: str, workspace_path: str) -> dict:
    """执行一个固定 CLI 任务，并返回可序列化的 trace。"""
    run = Run()
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

        review = PermissionReviewer().review_shell_command(command)
        if review.decision != PermissionDecision.ALLOW:
            trace.add_event(
                step,
                EventType.ERROR,
                content=review.reason,
                metadata={
                    "decision": review.decision.value,
                    "review_message": review.review_message,
                },
            )
            run.fail()
        else:
            result = ShellTools(workspace).run(command)
            trace.add_event(
                step,
                EventType.TOOL_CALL,
                content=result.stdout or result.stderr,
                metadata={
                    "exit_code": result.exit_code,
                    "stdout": result.stdout,
                    "stderr": result.stderr,
                    "timed_out": result.timed_out,
                },
            )

            if result.exit_code == 0:
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

def run_agent_task(task: str, workspace_path: str, config_path: str) -> dict:
    workspace = Workspace(workspace_path)
    llm = create_llm_from_config(config_path)
    agent = MiniCodeAgent(workspace, llm)
    return agent.run(task)


def maybe_save_trace(trace: dict, should_save: bool, output_dir: str) -> dict:
    """按 CLI 参数决定是否保存 trace，并把保存路径放进输出。"""
    if should_save:
        trace["saved_trace_path"] = save_trace(trace, output_dir=output_dir)
    return trace

def main() -> None:
    """解析命令行参数并把 trace JSON 打印到 stdout。"""
    parser = argparse.ArgumentParser(description="MiniCode CLI")
    subparsers = parser.add_subparsers(dest="mode", required=True)

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

    args = parser.parse_args()

    if args.mode == "fixed":
     trace = run_task(args.task, args.workspace)
    elif args.mode == "agent":
     trace = run_agent_task(args.task, args.workspace, args.config)
    trace = maybe_save_trace(trace, args.save_trace, args.trace_dir)
    print(json.dumps(trace, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
