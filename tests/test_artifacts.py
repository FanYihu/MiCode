import json

from micode.context.artifacts import (
    ArtifactStore,
    maybe_store_tool_result_artifact,
    safe_artifact_filename,
)
from micode.tools.artifact import read_artifact_tool
from micode.tools.default import create_default_tool_registry
from micode.tools.registry import ToolResult
from micode.workspace import Workspace


def test_artifact_store_saves_tool_result_payload(tmp_path):
    store = ArtifactStore(str(tmp_path / "artifacts"))
    result = ToolResult(ok=True, output="large output")

    artifact = store.save_tool_result(
        "read_file",
        result,
        metadata={"path": "README.md"},
    )
    data = json.loads(open(artifact.path, encoding="utf-8").read())

    assert artifact.id.startswith("artifact:tool-result:")
    assert artifact.kind == "tool_result"
    assert artifact.size_chars == len("large output")
    assert data["content"] == "large output"
    assert data["metadata"]["path"] == "README.md"
    assert "path=" in artifact.placeholder


def test_maybe_store_tool_result_artifact_respects_threshold(tmp_path):
    store = ArtifactStore(str(tmp_path / "artifacts"))
    small = ToolResult(ok=True, output="small")
    large = ToolResult(ok=True, output="x" * 20)

    assert maybe_store_tool_result_artifact(store, "echo", small, 10) is None
    artifact = maybe_store_tool_result_artifact(store, "echo", large, 10)

    assert artifact is not None
    assert open(artifact.path, encoding="utf-8").read()


def test_artifact_store_writes_same_content_idempotently(tmp_path):
    store = ArtifactStore(str(tmp_path / "artifacts"))
    result = ToolResult(ok=True, output="same large output")

    first = store.save_tool_result("read_file", result, metadata={"call": "one"})
    second = store.save_tool_result("read_file", result, metadata={"call": "two"})
    payload = json.loads(open(first.path, encoding="utf-8").read())

    assert first.id == second.id
    assert first.path == second.path
    assert first.sha256 == second.sha256
    assert payload["metadata"] == {"call": "one"}


def test_safe_artifact_filename_removes_separators():
    assert safe_artifact_filename("artifact:tool-result:abc") == (
        "artifact-tool-result-abc"
    )


def test_read_artifact_tool_reads_by_id_with_preview(tmp_path):
    store = ArtifactStore(str(tmp_path / "artifacts"))
    artifact = store.save_tool_result(
        "run_shell",
        ToolResult(ok=True, output="HEAD\n" + "x" * 80 + "\nTAIL"),
    )

    result = read_artifact_tool(
        str(tmp_path / "artifacts"),
        {"id": artifact.id, "max_chars": 70},
    )

    assert result.ok is True
    assert "HEAD" in result.output
    assert "TAIL" in result.output
    assert result.metadata["artifact_id"] == artifact.id
    assert result.metadata["read_truncated"] is True


def test_read_artifact_tool_reads_by_path(tmp_path):
    store = ArtifactStore(str(tmp_path / "artifacts"))
    artifact = store.save_tool_result(
        "read_file",
        ToolResult(ok=True, output="完整内容"),
    )

    result = read_artifact_tool(
        str(tmp_path / "artifacts"),
        {"path": artifact.path, "max_chars": 0},
    )

    assert result.ok is True
    assert result.output == "完整内容"
    assert result.metadata["read_truncated"] is False


def test_read_artifact_tool_rejects_path_outside_artifact_root(tmp_path):
    outside = tmp_path / "outside.json"
    outside.write_text("{}", encoding="utf-8")

    result = read_artifact_tool(
        str(tmp_path / "artifacts"),
        {"path": str(outside)},
    )

    assert result.ok is False
    assert result.metadata["error"] == "artifact_path_outside_root"


def test_read_artifact_tool_detects_hash_mismatch(tmp_path):
    store = ArtifactStore(str(tmp_path / "artifacts"))
    artifact = store.save_tool_result(
        "read_file",
        ToolResult(ok=True, output="original"),
    )
    payload = json.loads(open(artifact.path, encoding="utf-8").read())
    payload["content"] = "tampered"
    open(artifact.path, "w", encoding="utf-8").write(
        json.dumps(payload, ensure_ascii=False)
    )

    result = read_artifact_tool(
        str(tmp_path / "artifacts"),
        {"id": artifact.id},
    )

    assert result.ok is False
    assert result.metadata["error"] == "artifact_hash_mismatch"


def test_default_tool_registry_registers_read_artifact(tmp_path):
    store = ArtifactStore(str(tmp_path / "artifacts"))
    artifact = store.save_tool_result(
        "read_file",
        ToolResult(ok=True, output="artifact body"),
    )
    registry = create_default_tool_registry(
        Workspace(str(tmp_path)),
        artifact_dir=str(tmp_path / "artifacts"),
    )

    result = registry.call("read_artifact", {"id": artifact.id})

    assert "read_artifact" in registry.list_names()
    assert result.ok is True
    assert result.output == "artifact body"
    assert result.metadata["details"]["artifact_id"] == artifact.id
