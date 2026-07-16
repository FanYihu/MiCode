from dataclasses import dataclass
from math import ceil


DEFAULT_CHARS_PER_TOKEN = 4


@dataclass
class TokenEstimate:
    """TokenEstimate 是轻量 token 估算结果，不依赖具体 tokenizer。"""

    name: str
    chars: int
    estimated_tokens: int
    strategy: str = "chars_per_token"
    chars_per_token: int = DEFAULT_CHARS_PER_TOKEN

    def to_dict(self) -> dict:
        """转成 trace metadata。"""
        return {
            "name": self.name,
            "chars": self.chars,
            "estimated_tokens": self.estimated_tokens,
            "strategy": self.strategy,
            "chars_per_token": self.chars_per_token,
        }


def estimate_tokens(
    text: str,
    chars_per_token: int = DEFAULT_CHARS_PER_TOKEN,
) -> int:
    """用字符数估算 token 数，先保证稳定可审计。"""
    content = text if isinstance(text, str) else str(text)
    if not content:
        return 0
    safe_ratio = max(1, chars_per_token)
    return ceil(len(content) / safe_ratio)


def estimate_text(
    name: str,
    text: str,
    chars_per_token: int = DEFAULT_CHARS_PER_TOKEN,
) -> TokenEstimate:
    """估算单段文本。"""
    content = text if isinstance(text, str) else str(text)
    return TokenEstimate(
        name=name,
        chars=len(content),
        estimated_tokens=estimate_tokens(content, chars_per_token),
        chars_per_token=max(1, chars_per_token),
    )


def estimate_text_parts(
    parts: dict[str, str],
    chars_per_token: int = DEFAULT_CHARS_PER_TOKEN,
) -> dict:
    """估算多段文本，并给出总量，适合写入 run metadata。"""
    estimates = [
        estimate_text(name, text, chars_per_token).to_dict()
        for name, text in parts.items()
    ]
    return {
        "strategy": "chars_per_token",
        "chars_per_token": max(1, chars_per_token),
        "total_chars": sum(item["chars"] for item in estimates),
        "estimated_tokens": sum(item["estimated_tokens"] for item in estimates),
        "parts": estimates,
    }
