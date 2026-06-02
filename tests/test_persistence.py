import json
from pathlib import Path

from minicode.persistence import save_trace


def test_save_trace_creates_json_file(tmp_path):
    trace = {"run": {"status": "completed"}, "steps": [], "events": []}

    path = save_trace(trace, output_dir=str(tmp_path / "traces"))

    saved_path = Path(path)
    assert saved_path.exists()
    assert saved_path.parent == tmp_path / "traces"
    assert json.loads(saved_path.read_text(encoding="utf-8")) == trace
