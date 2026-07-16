from __future__ import annotations

from dataclasses import asdict, dataclass
from hashlib import sha256
from pathlib import Path
from shutil import copy2
from typing import List


@dataclass(frozen=True)
class MigratedFile:
    """记录单个状态文件的迁移和校验结果。"""

    path: str
    sha256: str
    status: str
    detail: str = ""


def file_sha256(path: Path) -> str:
    """流式计算文件哈希，避免大型 Artifact 一次性进入内存。"""
    digest = sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def migrate_state(
    source_dir: str = ".minicode",
    target_dir: str = ".micode",
) -> dict:
    """把旧状态复制到新目录，并用 SHA-256 做逐文件校验。

    迁移不会删除旧目录，也不会覆盖内容不同的目标文件。相同输入重复执行时，
    已迁移文件会被标记为 ``unchanged``，因此该操作是幂等的。
    """
    source = Path(source_dir).expanduser()
    target = Path(target_dir).expanduser()
    source_resolved = source.resolve(strict=False)
    target_resolved = target.resolve(strict=False)
    if source_resolved == target_resolved:
        raise ValueError("source_dir and target_dir must be different")

    if not source.exists():
        return {
            "ok": True,
            "source": str(source),
            "target": str(target),
            "source_exists": False,
            "copied": 0,
            "unchanged": 0,
            "conflicts": 0,
            "files": [],
        }
    if not source.is_dir():
        raise ValueError(f"source_dir is not a directory: {source}")

    records: List[MigratedFile] = []
    for source_path in sorted(source.rglob("*")):
        relative_path = source_path.relative_to(source)
        target_path = target / relative_path

        # 状态目录只迁移普通文件；符号链接可能逃逸到目录边界之外。
        if source_path.is_symlink():
            records.append(
                MigratedFile(
                    path=relative_path.as_posix(),
                    sha256="",
                    status="conflict",
                    detail="symbolic links are not migrated",
                )
            )
            continue
        if source_path.is_dir():
            continue

        source_hash = file_sha256(source_path)
        if target_path.exists():
            if not target_path.is_file() or target_path.is_symlink():
                records.append(
                    MigratedFile(
                        path=relative_path.as_posix(),
                        sha256=source_hash,
                        status="conflict",
                        detail="target path is not a regular file",
                    )
                )
                continue
            if file_sha256(target_path) != source_hash:
                records.append(
                    MigratedFile(
                        path=relative_path.as_posix(),
                        sha256=source_hash,
                        status="conflict",
                        detail="target file has different content",
                    )
                )
                continue
            status = "unchanged"
        else:
            target_path.parent.mkdir(parents=True, exist_ok=True)
            copy2(source_path, target_path)
            status = "copied"

        # 复制和幂等命中都再次校验，报告中的成功只代表真实字节一致。
        if file_sha256(target_path) != source_hash:
            records.append(
                MigratedFile(
                    path=relative_path.as_posix(),
                    sha256=source_hash,
                    status="conflict",
                    detail="post-copy SHA-256 verification failed",
                )
            )
            continue
        records.append(
            MigratedFile(
                path=relative_path.as_posix(),
                sha256=source_hash,
                status=status,
            )
        )

    copied = sum(record.status == "copied" for record in records)
    unchanged = sum(record.status == "unchanged" for record in records)
    conflicts = sum(record.status == "conflict" for record in records)
    return {
        "ok": conflicts == 0,
        "source": str(source),
        "target": str(target),
        "source_exists": True,
        "copied": copied,
        "unchanged": unchanged,
        "conflicts": conflicts,
        "files": [asdict(record) for record in records],
    }
