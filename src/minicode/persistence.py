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
