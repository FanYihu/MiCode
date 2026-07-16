import json

from minicode.cli import run_context_review
from minicode.context.artifacts import ArtifactStore
from minicode.context.prompt_cache import PromptCacheStore
from minicode.context.review import review_context_trace
from minicode.tools.registry import ToolResult


def make_context_trace(tmp_path) -> dict:
    prompt_cache = PromptCacheStore(str(tmp_path / "prompt-cache")).put(
        "session context",
        metadata={"source": "test"},
    )
    artifact = ArtifactStore(str(tmp_path / "artifacts")).save_tool_result(
        "read_file",
        ToolResult(ok=True, output="large artifact content"),
    )
    return {
        "run": {
            "id": "run-1",
            "metadata": {
                "mode": "agent",
                "context_assembly": {
                    "budget_chars": 200,
                    "used_chars": 15,
                    "estimated_tokens": 4,
                    "compaction": {
                        "enabled": True,
                        "compacted": False,
                        "strategy": "priority_layer_budget",
                        "chars_per_token": 4,
                        "budget_chars": 200,
                        "effective_budget_chars": 200,
                        "budget_tokens": 0,
                        "raw_chars": 15,
                        "raw_tokens": 4,
                        "used_chars": 15,
                        "used_tokens": 4,
                        "saved_chars": 0,
                        "saved_tokens": 0,
                        "actions": [
                            {
                                "layer": "session",
                                "action": "keep",
                                "reason": "within_budget",
                                "original_chars": 15,
                                "used_chars": 15,
                                "original_tokens": 4,
                                "used_tokens": 4,
                            }
                        ],
                    },
                    "layers": [
                        {
                            "name": "session",
                            "included": True,
                            "truncated": False,
                            "original_chars": 15,
                            "used_chars": 15,
                            "original_tokens": 4,
                            "used_tokens": 4,
                            "priority": 100,
                            "omitted_reason": "",
                            "metadata": {},
                        }
                    ],
                },
                "context_token_estimate": {
                    "strategy": "chars_per_token",
                    "chars_per_token": 4,
                    "total_chars": 15,
                    "estimated_tokens": 4,
                    "parts": [
                        {
                            "name": "assembled_context",
                            "chars": 15,
                            "estimated_tokens": 4,
                            "strategy": "chars_per_token",
                            "chars_per_token": 4,
                        }
                    ],
                },
                "prompt_cache": prompt_cache.to_metadata(),
                "decision_freezes": [
                    {
                        "turn_index": 1,
                        "prompt_cache_key": prompt_cache.key,
                        "task_hash": "task",
                        "observations_hash": "obs",
                        "session_context_hash": "ctx",
                    }
                ],
            },
        },
        "steps": [],
        "events": [
            {
                "content": f"summary\n\n{artifact.placeholder}",
                "metadata": {"artifact": artifact.to_metadata()},
            }
        ],
    }


def test_review_context_trace_reports_healthy_context(tmp_path):
    report = review_context_trace(make_context_trace(tmp_path))
    data = report.to_dict()

    assert data["ok"] is True
    assert data["summary"]["has_context_assembly"] is True
    assert data["summary"]["has_prompt_cache"] is True
    assert data["summary"]["artifact_references"] == 1
    assert data["issues"] == []


def test_review_context_trace_detects_context_budget_overrun(tmp_path):
    trace = make_context_trace(tmp_path)
    trace["run"]["metadata"]["context_assembly"]["used_chars"] = 300

    report = review_context_trace(trace)

    assert report.ok is False
    assert any(issue.code == "context_budget_exceeded" for issue in report.issues)


def test_review_context_trace_detects_prompt_cache_hash_mismatch(tmp_path):
    trace = make_context_trace(tmp_path)
    prompt_cache = trace["run"]["metadata"]["prompt_cache"]
    path = prompt_cache["prompt_cache_path"]
    payload = json.loads(open(path, encoding="utf-8").read())
    payload["content"] = "tampered"
    open(path, "w", encoding="utf-8").write(json.dumps(payload))

    report = review_context_trace(trace)

    assert report.ok is False
    assert any(issue.code == "prompt_cache_hash_mismatch" for issue in report.issues)


def test_review_context_trace_detects_decision_freeze_mismatch(tmp_path):
    trace = make_context_trace(tmp_path)
    trace["run"]["metadata"]["decision_freezes"][0][
        "prompt_cache_key"
    ] = "prompt-cache:other"

    report = review_context_trace(trace)

    assert report.ok is False
    assert any(
        issue.code == "decision_freeze_prompt_cache_mismatch"
        for issue in report.issues
    )


def test_review_context_trace_detects_artifact_hash_mismatch(tmp_path):
    trace = make_context_trace(tmp_path)
    artifact = trace["events"][0]["metadata"]["artifact"]
    path = artifact["artifact_path"]
    payload = json.loads(open(path, encoding="utf-8").read())
    payload["content"] = "tampered"
    open(path, "w", encoding="utf-8").write(json.dumps(payload))

    report = review_context_trace(trace)

    assert report.ok is False
    assert any(issue.code == "artifact_hash_mismatch" for issue in report.issues)


def test_run_context_review_loads_trace_file(tmp_path):
    trace = make_context_trace(tmp_path)
    trace_path = tmp_path / "trace.json"
    trace_path.write_text(json.dumps(trace, ensure_ascii=False), encoding="utf-8")

    report = run_context_review(str(trace_path))

    assert report["ok"] is True
    assert report["summary"]["artifact_references"] == 1
