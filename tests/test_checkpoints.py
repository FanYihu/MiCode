import pytest

from micode.checkpoints import CheckpointStore, MISSING_HASH
from micode.tools.default import create_default_tool_registry
from micode.workspace import Workspace


def test_checkpoint_rewinds_existing_file(tmp_path):
    path = tmp_path / "note.txt"
    path.write_text("before", encoding="utf-8")
    store = CheckpointStore(Workspace(str(tmp_path)))
    checkpoint = store.create(["note.txt"], reason="test")
    path.write_text("after", encoding="utf-8")
    store.finalize(checkpoint.id)

    preview = store.preview_rewind(checkpoint.id)
    store.rewind(checkpoint.id)

    assert preview["can_rewind"] is True
    assert path.read_text(encoding="utf-8") == "before"


def test_checkpoint_rewind_detects_later_user_change(tmp_path):
    path = tmp_path / "note.txt"
    path.write_text("before", encoding="utf-8")
    store = CheckpointStore(Workspace(str(tmp_path)))
    checkpoint = store.create(["note.txt"], reason="test")
    path.write_text("tool change", encoding="utf-8")
    store.finalize(checkpoint.id)
    path.write_text("user change", encoding="utf-8")

    preview = store.preview_rewind(checkpoint.id)

    assert preview["can_rewind"] is False
    with pytest.raises(RuntimeError):
        store.rewind(checkpoint.id)
    assert path.read_text(encoding="utf-8") == "user change"


def test_registry_checkpoints_write_file_and_new_file_can_be_removed(tmp_path):
    workspace = Workspace(str(tmp_path))
    registry = create_default_tool_registry(workspace)

    result = registry.call("write_file", {"path": "new.txt", "content": "new"})
    checkpoint = result.metadata["details"]["checkpoint"]

    assert result.ok is True
    assert checkpoint["entries"][0]["before_sha256"] == MISSING_HASH
    store = registry.checkpoint_store
    assert store.preview_rewind(checkpoint["id"])["can_rewind"] is True
    store.rewind(checkpoint["id"])
    assert not (tmp_path / "new.txt").exists()


def test_shell_write_is_explicitly_not_reversible(tmp_path):
    registry = create_default_tool_registry(Workspace(str(tmp_path)))

    result = registry.call("run_shell", {"command": "printf hello"})

    assert result.metadata["details"]["reversible"] is False
