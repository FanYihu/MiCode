import json
from datetime import datetime, timezone
from pathlib import Path


def save_trace(trace: dict, output_dir: str = ".micode/traces") -> str:
    """把 trace 保存为 JSON 文件，并返回保存路径。"""
    directory = Path(output_dir)
    directory.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%SZ")
    path = directory / f"{timestamp}.json"

    path.write_text(
        json.dumps(trace, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return str(path)


def load_trace(path: str) -> dict:
    """从 JSON 文件读取一次已保存的 trace。"""
    return json.loads(Path(path).read_text(encoding="utf-8"))


def summarize_trace(trace: dict) -> str:
    """把 trace 压缩成适合终端阅读的复盘摘要。"""
    run = trace.get("run", {})
    steps = trace.get("steps", [])
    events = trace.get("events", [])

    lines = [
        f"Run: {run.get('status', 'unknown')}",
        f"Steps: {len(steps)}",
        f"Events: {len(events)}",
        "",
    ]

    # Step 摘要只保留类型和关键工具名，避免把完整 metadata 淹没在终端里。
    for index, step in enumerate(steps, start=1):
        step_type = step.get("type", "unknown")
        tool = step.get("metadata", {}).get("tool")
        suffix = f" {tool}" if tool else ""
        lines.append(f"{index}. {step_type}{suffix}")

    error_events = [event for event in events if event.get("type") == "error"]
    if error_events:
        lines.extend(["", "Errors:"])
        for event in error_events:
            lines.append(f"- {event.get('content', '')}")

    final_events = [
        event
        for event in events
        if event.get("type") == "text" and event.get("content")
    ]
    if final_events:
        lines.extend(["", f"Final: {final_events[-1]['content']}"])

    return "\n".join(lines)


def truncate_text(text: str, max_length: int) -> str:
    """按最大长度截断长文本；max_length 为 0 时表示完整保留。"""
    if max_length < 0:
        raise ValueError("max_length must be non-negative")
    if max_length == 0 or len(text) <= max_length:
        return text

    return f"{text[:max_length]}... [truncated]"


def format_trace_detail(trace: dict, max_content: int = 2000) -> str:
    """格式化完整 trace 细节，给 CLI detail view 使用。"""
    run = trace.get("run", {})
    steps = trace.get("steps", [])
    events = trace.get("events", [])

    lines = [
        "Run",
        f"- id: {run.get('id', '')}",
        f"- status: {run.get('status', 'unknown')}",
        f"- metadata: {json.dumps(run.get('metadata', {}), ensure_ascii=False)}",
        "",
        "Steps",
    ]

    # 详细视图保留每个 step 的 metadata，便于定位具体工具或模型阶段。
    for index, step in enumerate(steps, start=1):
        lines.extend(
            [
                f"{index}. {step.get('type', 'unknown')}",
                f"   id: {step.get('id', '')}",
                f"   status: {step.get('status', '')}",
                f"   metadata: {json.dumps(step.get('metadata', {}), ensure_ascii=False)}",
            ]
        )

    lines.extend(["", "Events"])

    # Event content 往往是文件内容、命令输出或模型文本，详细视图默认截断防止刷屏。
    for index, event in enumerate(events, start=1):
        content = truncate_text(str(event.get("content", "")), max_content)
        lines.extend(
            [
                f"{index}. {event.get('type', 'unknown')}",
                f"   step_id: {event.get('step_id', '')}",
                f"   content: {content}",
                f"   metadata: {json.dumps(event.get('metadata', {}), ensure_ascii=False)}",
            ]
        )

    return "\n".join(lines)


def format_trace_markdown(trace: dict) -> str:
    """把 trace 格式化成适合贴进学习笔记的 Markdown 复盘报告。"""
    run = trace.get("run", {})
    metadata = run.get("metadata", {})
    steps = trace.get("steps", [])
    events = trace.get("events", [])

    lines = [
        "# Micode Trace Report",
        "",
        "## Run",
        "",
        f"- status: {run.get('status', 'unknown')}",
    ]

    # Run metadata 是复盘的上下文核心：任务、模式、模型信息都优先展示。
    for key in ["task", "mode", "workspace", "provider", "model"]:
        value = metadata.get(key)
        if value:
            lines.append(f"- {key}: {value}")

    lines.extend(["", "## Steps", ""])

    if steps:
        for index, step in enumerate(steps, start=1):
            step_type = step.get("type", "unknown")
            tool = step.get("metadata", {}).get("tool")
            suffix = f" {tool}" if tool else ""
            lines.append(f"{index}. {step_type}{suffix}")
    else:
        lines.append("No steps.")

    error_events = [event for event in events if event.get("type") == "error"]
    final_events = [
        event
        for event in events
        if event.get("type") == "text" and event.get("content")
    ]

    if error_events:
        lines.extend(["", "## Errors", ""])
        for event in error_events:
            lines.append(f"- {event.get('content', '')}")

    if final_events:
        # Markdown report 面向复盘，只展示最终文本，不展开所有中间 content。
        lines.extend(["", "## Final", "", str(final_events[-1].get("content", ""))])

    return "\n".join(lines)


def write_text_report(content: str, output_path: str) -> str:
    """把文本报告写入指定路径，并返回最终文件路径。"""
    path = Path(output_path)
    # 导出报告时允许用户传 notes/report.md 这类还不存在的目录。
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return str(path)


def list_traces(trace_dir: str = ".micode/traces", limit: int = 10) -> list[str]:
    """按修改时间倒序列出最近保存的 trace JSON 文件。"""
    directory = Path(trace_dir)
    if not directory.exists():
        return []

    # 只返回 JSON trace 文件；排序放在数据层，展示格式留给 CLI。
    paths = sorted(
        directory.glob("*.json"),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    return [str(path) for path in paths[:limit]]


def cleanup_traces(trace_dir: str = ".micode/traces", keep: int = 20) -> list[str]:
    """删除旧 trace，只保留最近 keep 个 JSON 文件，并返回被删除路径。"""
    if keep < 0:
        raise ValueError("keep must be non-negative")

    # 复用 list_traces 的排序规则，保证“最新文件”定义在整个模块里一致。
    paths = list_traces(trace_dir=trace_dir, limit=10_000)
    deleted = []

    for path in paths[keep:]:
        Path(path).unlink()
        deleted.append(path)

    return deleted


def filter_traces(
    trace_paths: list[str],
    mode: str = "",
    provider: str = "",
    model: str = "",
    task_contains: str = "",
) -> list[str]:
    """按 run metadata 筛选 trace 路径，保留传入路径的原始顺序。"""
    matched = []

    for path in trace_paths:
        trace = load_trace(path)
        metadata = trace.get("run", {}).get("metadata", {})

        # 空过滤条件表示“不限制该字段”，多个条件同时满足才算匹配。
        if mode and metadata.get("mode") != mode:
            continue
        if provider and metadata.get("provider") != provider:
            continue
        if model and metadata.get("model") != model:
            continue
        if task_contains and task_contains not in metadata.get("task", ""):
            continue

        matched.append(path)

    return matched
