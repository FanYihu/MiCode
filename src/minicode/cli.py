import argparse
import json

from minicode.agent import MiniCodeAgent, create_llm_from_config
from minicode.models import EventType, Run, StepType
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
from minicode.permissions import PermissionDecision, PermissionReviewer
from minicode.shell_tools import ShellTools
from minicode.trace import TraceRecorder
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
    """用 config.toml 创建 LLM，并运行 Agent Loop。"""
    workspace = Workspace(workspace_path)
    llm = create_llm_from_config(config_path)
    agent = MiniCodeAgent(workspace, llm)
    trace = agent.run(task)
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

    args = parser.parse_args()

    if args.command == "fixed":
        trace = run_task(args.task, args.workspace)
        trace = maybe_save_trace(trace, args.save_trace, args.trace_dir)
        print(json.dumps(trace, ensure_ascii=False, indent=2))
    elif args.command == "agent":
        trace = run_agent_task(args.task, args.workspace, args.config)
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


if __name__ == "__main__":
    main()
