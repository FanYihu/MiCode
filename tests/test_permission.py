from minicode.permissions import (
    PermissionDecision,
    PermissionReviewer,
    PermissionRule,
    default_permission_rules,
)


def test_allows_common_text_file_write():
    result = PermissionReviewer().review_file_write("README.md")

    assert result.decision == PermissionDecision.ALLOW
    assert result.rule_name == "allow_common_text_file_write"
    assert result.layer == "allow"


def test_denies_sensitive_file_write():
    result = PermissionReviewer().review_file_write(".env")

    assert result.decision == PermissionDecision.DENY
    assert result.rule_name == "deny_sensitive_file_write"


def test_reviews_unknown_file_type():
    result = PermissionReviewer().review_file_write("data.sqlite")

    assert result.decision == PermissionDecision.REVIEW
    assert "data.sqlite" in result.review_message


def test_allows_low_risk_shell_command():
    result = PermissionReviewer().review_shell_command("python3 -m pytest")

    assert result.decision == PermissionDecision.ALLOW


def test_denies_dangerous_shell_command():
    result = PermissionReviewer().review_shell_command("rm -rf /")

    assert result.decision == PermissionDecision.DENY


def test_reviews_unknown_shell_command():
    result = PermissionReviewer().review_shell_command("curl https://example.com")

    assert result.decision == PermissionDecision.REVIEW
    assert "curl" in result.review_message


def test_deny_layer_wins_over_allow_layer_for_shell_command():
    result = PermissionReviewer().review_shell_command("python3 -c 'sudo reboot'")

    assert result.decision == PermissionDecision.DENY
    assert result.rule_name == "deny_dangerous_shell_command"
    assert result.layer == "deny"


def test_custom_rule_can_be_injected_before_defaults():
    rules = [
        PermissionRule(
            name="deny_generated_file",
            layer="deny",
            kinds=("file_write",),
            decision=PermissionDecision.DENY,
            reason="拒绝写入生成文件",
            suffixes=(".generated.py",),
        ),
        *default_permission_rules(),
    ]

    result = PermissionReviewer(rules).review_file_write("client.generated.py")

    assert result.decision == PermissionDecision.DENY
    assert result.rule_name == "deny_generated_file"


def test_review_layer_remains_fallback_for_unknown_file_type():
    result = PermissionReviewer().review_file_write("data.sqlite")

    assert result.decision == PermissionDecision.REVIEW
    assert result.rule_name == "review_unknown_file_write"
    assert result.layer == "review"
