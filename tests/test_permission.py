from minicode.permissions import PermissionDecision, PermissionReviewer


def test_allows_common_text_file_write():
    result = PermissionReviewer().review_file_write("README.md")

    assert result.decision == PermissionDecision.ALLOW


def test_denies_sensitive_file_write():
    result = PermissionReviewer().review_file_write(".env")

    assert result.decision == PermissionDecision.DENY


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
