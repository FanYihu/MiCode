import difflib

from micode.workspace import Workspace


class EmptySearchText(ValueError):
    """替换工具要求 old 文本非空，避免空字符串匹配到任意位置。"""


class SearchTextNotFound(ValueError):
    """文件中找不到要替换的精确文本。"""


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

    def replace_text(self, path: str, old: str, new: str) -> str:
        """精确替换文件中的第一处文本，并返回本次修改 diff。"""
        if old == "":
            raise EmptySearchText("old text must not be empty")

        content = self.read_file(path)
        if old not in content:
            raise SearchTextNotFound(f"'{old}' not found in {path}")

        # 只替换第一处匹配，保持 Agent 自动编辑时的修改范围可控。
        new_content = content.replace(old, new, 1)
        diff = self.preview_write(path, new_content)
        self.write_file(path, new_content)
        return diff

    def exists(self, path: str) -> bool:
        target = self.workspace.resolve_path(path)
        return target.exists()
