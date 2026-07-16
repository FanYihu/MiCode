from hashlib import sha256

from micode.state_migration import migrate_state


def test_migrate_state_copies_and_verifies_files(tmp_path):
    source = tmp_path / ".minicode"
    target = tmp_path / ".micode"
    session = source / "sessions" / "session-1.json"
    memory = source / "memory" / "episodes.json"
    session.parent.mkdir(parents=True)
    memory.parent.mkdir(parents=True)
    session.write_text('{"id":"session-1"}', encoding="utf-8")
    memory.write_text("[]", encoding="utf-8")

    report = migrate_state(str(source), str(target))

    assert report["ok"] is True
    assert report["copied"] == 2
    assert report["conflicts"] == 0
    assert (target / "sessions" / "session-1.json").read_bytes() == session.read_bytes()
    assert report["files"][0]["sha256"]


def test_migrate_state_is_idempotent(tmp_path):
    source = tmp_path / ".minicode"
    target = tmp_path / ".micode"
    source.mkdir()
    (source / "state.json").write_text("{}", encoding="utf-8")

    first = migrate_state(str(source), str(target))
    second = migrate_state(str(source), str(target))

    assert first["copied"] == 1
    assert second["copied"] == 0
    assert second["unchanged"] == 1
    assert second["ok"] is True


def test_migrate_state_preserves_conflicting_target(tmp_path):
    source = tmp_path / ".minicode"
    target = tmp_path / ".micode"
    source.mkdir()
    target.mkdir()
    (source / "state.json").write_text("old", encoding="utf-8")
    (target / "state.json").write_text("new", encoding="utf-8")

    report = migrate_state(str(source), str(target))

    assert report["ok"] is False
    assert report["conflicts"] == 1
    assert (target / "state.json").read_text(encoding="utf-8") == "new"
    assert report["files"][0]["sha256"] == sha256(b"old").hexdigest()


def test_migrate_state_missing_source_is_a_safe_noop(tmp_path):
    report = migrate_state(
        str(tmp_path / ".minicode"),
        str(tmp_path / ".micode"),
    )

    assert report["ok"] is True
    assert report["source_exists"] is False
    assert report["files"] == []
