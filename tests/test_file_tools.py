import pytest

from minicode.tools.file import EmptySearchText, FileTools, SearchTextNotFound
from minicode.workspace import Workspace


def test_read_file_reads_workspace_file(tmp_path):
    (tmp_path / "README.md").write_text("hello", encoding="utf-8")
    tools = FileTools(Workspace(str(tmp_path)))

    assert tools.read_file("README.md") == "hello"


def test_write_file_creates_parent_dirs(tmp_path):
    tools = FileTools(Workspace(str(tmp_path)))

    tools.write_file("src/main.py", "print('hi')\n")

    assert (tmp_path / "src" / "main.py").read_text(encoding="utf-8") == "print('hi')\n"


def test_preview_write_returns_diff(tmp_path):
    (tmp_path / "README.md").write_text("old\n", encoding="utf-8")
    tools = FileTools(Workspace(str(tmp_path)))

    diff = tools.preview_write("README.md", "new\n")

    assert "--- a/README.md" in diff
    assert "+++ b/README.md" in diff
    assert "-old" in diff
    assert "+new" in diff


def test_replace_text_replaces_first_match_and_returns_diff(tmp_path):
    file_path = tmp_path / "README.md"
    file_path.write_text("old\nold\n", encoding="utf-8")
    tools = FileTools(Workspace(str(tmp_path)))

    diff = tools.replace_text("README.md", "old", "new")

    assert file_path.read_text(encoding="utf-8") == "new\nold\n"
    assert "--- a/README.md" in diff
    assert "+++ b/README.md" in diff
    assert "-old" in diff
    assert "+new" in diff


def test_replace_text_can_insert_text_around_existing_marker(tmp_path):
    file_path = tmp_path / "README.md"
    file_path.write_text("start\nend\n", encoding="utf-8")
    tools = FileTools(Workspace(str(tmp_path)))

    diff = tools.replace_text("README.md", "end\n", "middle\nend\n")

    assert file_path.read_text(encoding="utf-8") == "start\nmiddle\nend\n"
    assert "+middle" in diff


def test_replace_text_can_delete_text_with_empty_replacement(tmp_path):
    file_path = tmp_path / "README.md"
    file_path.write_text("start\nremove me\nend\n", encoding="utf-8")
    tools = FileTools(Workspace(str(tmp_path)))

    diff = tools.replace_text("README.md", "remove me\n", "")

    assert file_path.read_text(encoding="utf-8") == "start\nend\n"
    assert "-remove me" in diff


def test_replace_text_rejects_empty_search_text(tmp_path):
    (tmp_path / "README.md").write_text("hello\n", encoding="utf-8")
    tools = FileTools(Workspace(str(tmp_path)))

    with pytest.raises(EmptySearchText):
        tools.replace_text("README.md", "", "new")


def test_replace_text_rejects_missing_search_text(tmp_path):
    (tmp_path / "README.md").write_text("hello\n", encoding="utf-8")
    tools = FileTools(Workspace(str(tmp_path)))

    with pytest.raises(SearchTextNotFound):
        tools.replace_text("README.md", "missing", "new")


def test_replace_text_keeps_workspace_path_boundary(tmp_path):
    outside = tmp_path.parent / "outside.txt"
    outside.write_text("secret\n", encoding="utf-8")
    tools = FileTools(Workspace(str(tmp_path)))

    with pytest.raises(ValueError):
        tools.replace_text("../outside.txt", "secret", "changed")

    assert outside.read_text(encoding="utf-8") == "secret\n"


def test_exists_returns_file_existence(tmp_path):
    (tmp_path / "README.md").write_text("hello", encoding="utf-8")
    tools = FileTools(Workspace(str(tmp_path)))

    assert tools.exists("README.md") is True
    assert tools.exists("missing.md") is False
