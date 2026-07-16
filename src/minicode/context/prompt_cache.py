import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

from minicode.memory.session import utc_now_iso


@dataclass
class PromptCacheEntry:
    """PromptCacheEntry 记录一段稳定 prompt 上下文的指纹。"""

    key: str
    path: str
    size_chars: int
    sha256: str
    created: bool = False

    def to_metadata(self) -> dict:
        """转成 trace metadata。"""
        return {
            "prompt_cache_key": self.key,
            "prompt_cache_path": self.path,
            "prompt_cache_size_chars": self.size_chars,
            "prompt_cache_sha256": self.sha256,
            "prompt_cache_created": self.created,
        }


class PromptCacheStore:
    """本地 prompt cache 索引，用稳定 hash 表示可复用上下文。"""

    def __init__(self, cache_dir: str = ".minicode/prompt-cache") -> None:
        self.cache_dir = Path(cache_dir)

    def put(self, content: str, metadata: dict = None) -> PromptCacheEntry:
        """幂等写入 prompt context；相同内容得到相同 cache key。"""
        digest = hashlib.sha256(content.encode("utf-8")).hexdigest()
        key = f"prompt-cache:{digest[:24]}"
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        path = self.cache_dir / f"{safe_cache_filename(key)}.json"
        created = False
        if not path.exists():
            payload = {
                "key": key,
                "content": content,
                "size_chars": len(content),
                "sha256": digest,
                "created_at": utc_now_iso(),
                "metadata": metadata or {},
            }
            path.write_text(
                json.dumps(payload, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            created = True
        return PromptCacheEntry(
            key=key,
            path=str(path),
            size_chars=len(content),
            sha256=digest,
            created=created,
        )


def safe_cache_filename(cache_key: str) -> str:
    """把 prompt cache key 转成文件系统友好名称。"""
    return "".join(char if char.isalnum() else "-" for char in cache_key).strip("-")
