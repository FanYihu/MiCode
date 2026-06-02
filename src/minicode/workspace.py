from pathlib import Path
from typing import List


class Workspace:
    """Workspace 负责在受限根目录内读取和搜索代码文件。"""

    ignored_dirs = {".git", ".pytest_cache", "__pycache__"}

    def __init__(self, root: str) -> None:
        self.root = Path(root).resolve()

    def resolve_path(self, path: str) -> Path:
        """把用户传入路径解析到工作区内，并阻止 ../ 越界访问。"""
        target = (self.root / path).resolve()

        if target != self.root and self.root not in target.parents:
            raise ValueError("路径越过工作区边界")

        return target

    def read_text(self, path: str) -> str:
        """读取工作区内的 UTF-8 文本文件。"""
        target = self.resolve_path(path)
        return target.read_text(encoding="utf-8")

    def list_files(self) -> List[str]:
        """列出工作区内所有非忽略目录下的文件相对路径。"""
        files = []

        for path in self.root.rglob("*"):
            if not path.is_file():
                continue

            relative = path.relative_to(self.root)
            if any(part in self.ignored_dirs for part in relative.parts):
                continue

            files.append(relative.as_posix())

        return sorted(files)

    def search_text(self, keyword: str) -> List[dict]:
        """在工作区文本文件中搜索关键词，返回命中的路径、行号和文本。"""
        matches = []

        for file_path in self.list_files():
            try:
                content = self.read_text(file_path)
            except UnicodeDecodeError:
                continue

            for line_number, line in enumerate(content.splitlines(), start=1):
                if keyword in line:
                    matches.append(
                        {
                            "path": file_path,
                            "line": line_number,
                            "text": line,
                        }
                    )

        return matches
