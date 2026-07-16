from dataclasses import dataclass, field

from minicode.context.tokens import DEFAULT_CHARS_PER_TOKEN, estimate_tokens


TRUNCATION_MARKER = "\n... [layer truncated]"


@dataclass
class ContextLayer:
    """ContextLayer 表示一块可注入 Prompt 的上下文来源。"""

    name: str
    content: str
    priority: int = 0
    budget_chars: int = 0
    required: bool = False
    metadata: dict = field(default_factory=dict)


@dataclass
class ContextLayerResult:
    """ContextLayerResult 记录某一层最终是否进入 Prompt。"""

    name: str
    included: bool
    truncated: bool = False
    original_chars: int = 0
    used_chars: int = 0
    original_tokens: int = 0
    used_tokens: int = 0
    priority: int = 0
    omitted_reason: str = ""
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        """转成可写入 trace metadata 的 dict。"""
        return {
            "name": self.name,
            "included": self.included,
            "truncated": self.truncated,
            "original_chars": self.original_chars,
            "used_chars": self.used_chars,
            "original_tokens": self.original_tokens,
            "used_tokens": self.used_tokens,
            "priority": self.priority,
            "omitted_reason": self.omitted_reason,
            "metadata": self.metadata,
        }


@dataclass
class ContextAssembly:
    """ContextAssembly 是多层上下文拼装后的结果。"""

    context: str = ""
    layer_results: list[ContextLayerResult] = field(default_factory=list)
    budget_chars: int = 0
    used_chars: int = 0
    estimated_tokens: int = 0
    compaction: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        """转成 trace metadata。"""
        return {
            "budget_chars": self.budget_chars,
            "used_chars": self.used_chars,
            "estimated_tokens": self.estimated_tokens,
            "compaction": self.compaction,
            "layers": [result.to_dict() for result in self.layer_results],
        }


class ContextLayerAssembler:
    """按优先级、字符预算和可选 token 预算组合多层上下文。"""

    def __init__(
        self,
        budget_chars: int = 4000,
        budget_tokens: int = 0,
        chars_per_token: int = DEFAULT_CHARS_PER_TOKEN,
    ) -> None:
        self.budget_chars = max(0, budget_chars)
        self.budget_tokens = max(0, budget_tokens)
        self.chars_per_token = max(1, chars_per_token)

    def assemble(self, layers: list[ContextLayer]) -> ContextAssembly:
        """把多个 ContextLayer 组合成最终 prompt context。"""
        effective_budget_chars = self._effective_budget_chars()
        ordered_layers = sorted(
            layers,
            key=lambda layer: (layer.required, layer.priority),
            reverse=True,
        )
        parts = []
        results = []
        raw_context = "\n\n".join(
            layer.content.strip()
            for layer in ordered_layers
            if layer.content.strip()
        )

        for layer in ordered_layers:
            content = layer.content.strip()
            original_chars = len(content)
            if not content:
                results.append(
                    ContextLayerResult(
                        name=layer.name,
                        included=False,
                        original_chars=0,
                        original_tokens=0,
                        priority=layer.priority,
                        omitted_reason="empty",
                        metadata=layer.metadata,
                    )
                )
                continue

            separator_chars = 2 if parts else 0
            remaining = (
                effective_budget_chars
                - len("\n\n".join(parts))
                - separator_chars
            )
            if remaining <= 0:
                results.append(omitted_result(layer, original_chars, "budget_exhausted"))
                continue

            layer_budget = layer.budget_chars if layer.budget_chars > 0 else remaining
            allowed = min(layer_budget, remaining)
            trimmed, truncated = trim_layer_content(content, allowed)
            if not trimmed:
                results.append(omitted_result(layer, original_chars, "layer_too_small"))
                continue

            parts.append(trimmed)
            results.append(
                ContextLayerResult(
                    name=layer.name,
                    included=True,
                    truncated=truncated,
                    original_chars=original_chars,
                    used_chars=len(trimmed),
                    original_tokens=estimate_tokens(content),
                    used_tokens=estimate_tokens(trimmed),
                    priority=layer.priority,
                    metadata=layer.metadata,
                )
            )

        context = "\n\n".join(parts)
        compaction = build_compaction_metadata(
            raw_context=raw_context,
            results=results,
            budget_chars=self.budget_chars,
            effective_budget_chars=effective_budget_chars,
            budget_tokens=self.budget_tokens,
            chars_per_token=self.chars_per_token,
        )
        return ContextAssembly(
            context=context,
            layer_results=results,
            budget_chars=self.budget_chars,
            used_chars=len(context),
            estimated_tokens=estimate_tokens(context),
            compaction=compaction,
        )

    def _effective_budget_chars(self) -> int:
        """token 预算存在时，把它转换成更保守的字符预算。"""
        if self.budget_tokens <= 0:
            return self.budget_chars
        token_budget_chars = self.budget_tokens * self.chars_per_token
        if self.budget_chars <= 0:
            return token_budget_chars
        return min(self.budget_chars, token_budget_chars)


def trim_layer_content(content: str, max_chars: int) -> tuple[str, bool]:
    """按字符数裁剪单层内容，保留截断标记。"""
    if max_chars <= 0:
        return "", False
    if len(content) <= max_chars:
        return content, False
    if max_chars <= len(TRUNCATION_MARKER) + 12:
        return "", True

    keep_chars = max_chars - len(TRUNCATION_MARKER)
    return content[:keep_chars].rstrip() + TRUNCATION_MARKER, True


def omitted_result(
    layer: ContextLayer,
    original_chars: int,
    reason: str,
) -> ContextLayerResult:
    """生成未注入层的结果记录。"""
    return ContextLayerResult(
        name=layer.name,
        included=False,
        original_chars=original_chars,
        original_tokens=estimate_tokens(layer.content.strip()),
        priority=layer.priority,
        omitted_reason=reason,
        metadata=layer.metadata,
    )


def build_compaction_metadata(
    raw_context: str,
    results: list[ContextLayerResult],
    budget_chars: int,
    effective_budget_chars: int,
    budget_tokens: int,
    chars_per_token: int,
) -> dict:
    """根据最终层结果生成自动压缩审计信息。"""
    actions = []
    for result in results:
        if result.included and result.truncated:
            action = "truncate"
        elif not result.included and result.omitted_reason not in {"empty"}:
            action = "omit"
        else:
            action = "keep" if result.included else "skip"
        actions.append(
            {
                "layer": result.name,
                "action": action,
                "reason": result.omitted_reason or (
                    "layer_budget" if result.truncated else "within_budget"
                ),
                "original_chars": result.original_chars,
                "used_chars": result.used_chars,
                "original_tokens": result.original_tokens,
                "used_tokens": result.used_tokens,
            }
        )

    raw_chars = len(raw_context)
    raw_tokens = estimate_tokens(raw_context, chars_per_token)
    included_count = sum(1 for result in results if result.included)
    used_chars = (
        sum(result.used_chars for result in results)
        + max(0, included_count - 1) * 2
    )
    used_tokens = sum(result.used_tokens for result in results)
    compacted = any(
        action["action"] in {"truncate", "omit"}
        for action in actions
    )
    return {
        "enabled": True,
        "compacted": compacted,
        "strategy": "priority_layer_budget",
        "chars_per_token": chars_per_token,
        "budget_chars": budget_chars,
        "effective_budget_chars": effective_budget_chars,
        "budget_tokens": budget_tokens,
        "raw_chars": raw_chars,
        "raw_tokens": raw_tokens,
        "used_chars": used_chars,
        "used_tokens": used_tokens,
        "saved_chars": max(0, raw_chars - used_chars),
        "saved_tokens": max(0, raw_tokens - used_tokens),
        "actions": actions,
    }
