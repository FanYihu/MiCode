from minicode.agent import build_action_prompt


def test_prompt_contains_task_tools_observations_and_json_rule():
    prompt = build_action_prompt("读取 README", ["README.md", "hello minicode"])

    assert "读取 README" in prompt
    assert "list_files" in prompt
    assert "read_file" in prompt
    assert "run_shell" in prompt
    assert "README.md" in prompt
    assert "hello minicode" in prompt
    assert "Return exactly one JSON object" in prompt
