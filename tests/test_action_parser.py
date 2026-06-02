import pytest

from minicode.agent import (
    AgentAction,
    InvalidActionText,
    InvalidAgentAction,
    parse_action,
    validate_action,
)


def test_validate_action_allows_list_files():
    validate_action(AgentAction(tool="list_files", args={}))


def test_parse_read_file_json():
    action = parse_action('{"tool":"read_file","args":{"path":"README.md"},"final":false}')

    assert action.tool == "read_file"
    assert action.args == {"path": "README.md"}
    assert action.final is False


def test_parse_final_json():
    action = parse_action('{"tool":"","args":{"answer":"完成"},"final":true}')

    assert action.final is True
    assert action.args["answer"] == "完成"


def test_parse_non_json_raises():
    with pytest.raises(InvalidActionText):
        parse_action("read README")


def test_parse_json_array_raises():
    with pytest.raises(InvalidActionText):
        parse_action("[]")


def test_read_file_missing_path_raises():
    with pytest.raises(InvalidAgentAction):
        parse_action('{"tool":"read_file","args":{},"final":false}')


def test_run_shell_missing_command_raises():
    with pytest.raises(InvalidAgentAction):
        parse_action('{"tool":"run_shell","args":{},"final":false}')


def test_unknown_tool_raises():
    with pytest.raises(InvalidAgentAction):
        parse_action('{"tool":"unknown","args":{},"final":false}')
