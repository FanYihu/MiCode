from minicode.file_tools import FileTools
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


def test_exists_returns_file_existence(tmp_path):
    (tmp_path / "README.md").write_text("hello", encoding="utf-8")
    tools = FileTools(Workspace(str(tmp_path)))

    assert tools.exists("README.md") is True
    assert tools.exists("missing.md") is False
