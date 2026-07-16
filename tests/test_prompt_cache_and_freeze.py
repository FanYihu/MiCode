import json

from minicode.context.decision import freeze_decision
from minicode.context.prompt_cache import PromptCacheStore


def test_prompt_cache_store_writes_same_context_idempotently(tmp_path):
    store = PromptCacheStore(str(tmp_path / "prompt-cache"))

    first = store.put("stable context", metadata={"run": "one"})
    second = store.put("stable context", metadata={"run": "two"})
    data = json.loads(open(first.path, encoding="utf-8").read())

    assert first.key == second.key
    assert first.path == second.path
    assert first.created is True
    assert second.created is False
    assert data["content"] == "stable context"
    assert data["metadata"] == {"run": "one"}


def test_prompt_cache_store_changes_key_when_context_changes(tmp_path):
    store = PromptCacheStore(str(tmp_path / "prompt-cache"))

    first = store.put("context a")
    second = store.put("context b")

    assert first.key != second.key


def test_decision_freeze_is_stable_for_same_inputs():
    first = freeze_decision(
        "task",
        ["obs"],
        session_context="context",
        turn_index=1,
        prompt_cache_key="prompt-cache:abc",
    )
    second = freeze_decision(
        "task",
        ["obs"],
        session_context="context",
        turn_index=1,
        prompt_cache_key="prompt-cache:abc",
    )

    assert first.id == second.id
    assert first.prompt_cache_key == "prompt-cache:abc"
    assert first.to_dict()["observations_hash"] == second.to_dict()["observations_hash"]
