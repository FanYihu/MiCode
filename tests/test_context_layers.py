from minicode.context.layers import (
    ContextLayer,
    ContextLayerAssembler,
    TRUNCATION_MARKER,
    trim_layer_content,
)


def test_context_layer_assembler_orders_by_required_then_priority():
    assembly = ContextLayerAssembler(budget_chars=500).assemble(
        [
            ContextLayer(name="low", content="LOW", priority=10),
            ContextLayer(name="required", content="REQUIRED", priority=1, required=True),
            ContextLayer(name="high", content="HIGH", priority=90),
        ]
    )

    assert assembly.context.split("\n\n") == ["REQUIRED", "HIGH", "LOW"]
    assert [result.name for result in assembly.layer_results] == [
        "required",
        "high",
        "low",
    ]


def test_context_layer_assembler_respects_total_and_layer_budget():
    assembly = ContextLayerAssembler(budget_chars=90).assemble(
        [
            ContextLayer(
                name="session",
                content="S" * 80,
                priority=100,
                budget_chars=50,
            ),
            ContextLayer(
                name="memory",
                content="M" * 80,
                priority=80,
                budget_chars=50,
            ),
        ]
    )

    result_by_name = {result.name: result for result in assembly.layer_results}
    assert assembly.used_chars <= 90
    assert result_by_name["session"].truncated is True
    assert result_by_name["memory"].included is True
    assert result_by_name["memory"].truncated is True


def test_context_layer_assembler_omits_when_remaining_budget_is_too_small():
    assembly = ContextLayerAssembler(budget_chars=70).assemble(
        [
            ContextLayer(
                name="session",
                content="S" * 80,
                priority=100,
                budget_chars=50,
            ),
            ContextLayer(
                name="memory",
                content="M" * 80,
                priority=80,
                budget_chars=50,
            ),
        ]
    )

    result_by_name = {result.name: result for result in assembly.layer_results}
    assert result_by_name["memory"].included is False
    assert result_by_name["memory"].omitted_reason == "layer_too_small"


def test_context_layer_assembler_records_empty_layers():
    assembly = ContextLayerAssembler(budget_chars=100).assemble(
        [ContextLayer(name="empty", content="")]
    )

    assert assembly.context == ""
    assert assembly.layer_results[0].included is False
    assert assembly.layer_results[0].omitted_reason == "empty"


def test_context_layer_assembly_to_dict_is_trace_ready():
    assembly = ContextLayerAssembler(budget_chars=100).assemble(
        [ContextLayer(name="session", content="hello", priority=10)]
    )

    data = assembly.to_dict()

    assert data["budget_chars"] == 100
    assert data["used_chars"] == len("hello")
    assert data["estimated_tokens"] == 2
    assert data["layers"][0]["name"] == "session"
    assert data["layers"][0]["included"] is True
    assert data["layers"][0]["used_tokens"] == 2
    assert data["compaction"]["enabled"] is True
    assert data["compaction"]["compacted"] is False


def test_trim_layer_content_adds_marker_when_truncated():
    trimmed, truncated = trim_layer_content("abcdef" * 20, 50)

    assert truncated is True
    assert trimmed.endswith(TRUNCATION_MARKER)
    assert len(trimmed) <= 50


def test_trim_layer_content_omits_when_budget_too_small_for_marker():
    trimmed, truncated = trim_layer_content("abcdef", 5)

    assert trimmed == ""
    assert truncated is True


def test_context_layer_assembler_records_auto_compaction_actions():
    assembly = ContextLayerAssembler(budget_chars=90).assemble(
        [
            ContextLayer(
                name="session",
                content="S" * 80,
                priority=100,
                budget_chars=50,
            ),
            ContextLayer(
                name="memory",
                content="M" * 80,
                priority=80,
                budget_chars=50,
            ),
        ]
    )

    compaction = assembly.to_dict()["compaction"]
    actions = {item["layer"]: item for item in compaction["actions"]}

    assert compaction["compacted"] is True
    assert compaction["raw_chars"] > compaction["used_chars"]
    assert compaction["saved_chars"] > 0
    assert actions["session"]["action"] == "truncate"
    assert actions["memory"]["action"] == "truncate"


def test_context_layer_assembler_uses_token_budget_as_effective_budget():
    assembly = ContextLayerAssembler(
        budget_chars=500,
        budget_tokens=20,
    ).assemble(
        [
            ContextLayer(
                name="session",
                content="S" * 300,
                priority=100,
            )
        ]
    )

    data = assembly.to_dict()

    assert data["used_chars"] <= 80
    assert data["compaction"]["budget_chars"] == 500
    assert data["compaction"]["budget_tokens"] == 20
    assert data["compaction"]["effective_budget_chars"] == 80
    assert data["compaction"]["actions"][0]["action"] == "truncate"
