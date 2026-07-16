import pytest

from micode.workspace import Workspace


def test_list_files_returns_relative_paths(tmp_path):
    (tmp_path / "README.md").write_text("hello", encoding="utf-8")
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "main.py").write_text("print('hi')", encoding="utf-8")
    (tmp_path / ".git").mkdir()
    (tmp_path / ".git" / "config").write_text("ignored", encoding="utf-8")

    workspace = Workspace(str(tmp_path))

    assert workspace.list_files() == ["README.md", "src/main.py"]


def test_read_text_reads_file_content(tmp_path):
    (tmp_path / "hello.txt").write_text("hello micode", encoding="utf-8")
    workspace = Workspace(str(tmp_path))

    assert workspace.read_text("hello.txt") == "hello micode"


def test_search_text_returns_matches(tmp_path):
    (tmp_path / "a.txt").write_text("hello\nmicode\n", encoding="utf-8")
    (tmp_path / "b.txt").write_text("mini agent\nother\n", encoding="utf-8")
    workspace = Workspace(str(tmp_path))

    matches = workspace.search_text("mi")

    assert matches == [
        {"path": "a.txt", "line": 2, "text": "micode"},
        {"path": "b.txt", "line": 1, "text": "mini agent"},
    ]


def test_resolve_path_blocks_parent_escape(tmp_path):
    outside = tmp_path.parent / "outside.txt"
    outside.write_text("secret", encoding="utf-8")
    workspace = Workspace(str(tmp_path))

    with pytest.raises(ValueError):
        workspace.read_text("../outside.txt")
