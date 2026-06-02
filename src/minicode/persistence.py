import json
from datetime import datetime, timezone
from pathlib import Path


def save_trace(trace: dict, output_dir: str = ".minicode/traces") -> str:
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


def list_traces(trace_dir: str = ".minicode/traces", limit: int = 10) -> list[str]:
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


def cleanup_traces(trace_dir: str = ".minicode/traces", keep: int = 20) -> list[str]:
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
