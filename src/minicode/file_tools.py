import difflib

from minicode.workspace import Workspace


class FileTools:
    """基于 Workspace 的安全文件读写工具。"""

    def __init__(self, workspace: Workspace) -> None:
        self.workspace = workspace

    def read_file(self, path: str) -> str:
        return self.workspace.read_text(path)

    def write_file(self, path: str, content: str) -> None:
        target = self.workspace.resolve_path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")

    def preview_write(self, path: str, new_content: str) -> str:
        old_content = self.read_file(path) if self.exists(path) else ""

        diff = difflib.unified_diff(
            old_content.splitlines(keepends=True),
            new_content.splitlines(keepends=True),
            fromfile=f"a/{path}",
            tofile=f"b/{path}",
        )
        return "".join(diff)

    def exists(self, path: str) -> bool:
        target = self.workspace.resolve_path(path)
        return target.exists()
