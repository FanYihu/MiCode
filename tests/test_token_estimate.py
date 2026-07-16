from minicode.context.tokens import estimate_text, estimate_text_parts, estimate_tokens


def test_estimate_tokens_uses_ceil_chars_per_token():
    assert estimate_tokens("") == 0
    assert estimate_tokens("abcd") == 1
    assert estimate_tokens("abcde") == 2


def test_estimate_text_returns_trace_ready_metadata():
    estimate = estimate_text("task", "x" * 9)

    assert estimate.to_dict() == {
        "name": "task",
        "chars": 9,
        "estimated_tokens": 3,
        "strategy": "chars_per_token",
        "chars_per_token": 4,
    }


def test_estimate_text_parts_sums_parts():
    estimate = estimate_text_parts(
        {
            "task": "abcd",
            "context": "abcdef",
        }
    )

    assert estimate["total_chars"] == 10
    assert estimate["estimated_tokens"] == 3
    assert [part["name"] for part in estimate["parts"]] == ["task", "context"]
