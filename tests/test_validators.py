import pytest

from ntfy_mcp.validators import (
    ValidationError,
    default_tags_for_severity,
    normalize_tags,
    resolve_priority,
    resolve_topic,
    truncate_message,
    validate_click_url,
    validate_priority,
    validate_topic,
)


def test_valid_topic_passes() -> None:
    assert validate_topic("topic_ABC-123") == "topic_ABC-123"


def test_non_allowed_topic_fails() -> None:
    with pytest.raises(ValidationError, match="allow-list"):
        resolve_topic("other-topic", "default-topic", {"default-topic"})


def test_invalid_topic_format_fails() -> None:
    with pytest.raises(ValidationError, match="topic must be"):
        validate_topic("../bad")


def test_priority_below_one_fails() -> None:
    with pytest.raises(ValidationError, match="between 1 and 5"):
        validate_priority(0)


def test_priority_above_five_fails() -> None:
    with pytest.raises(ValidationError, match="between 1 and 5"):
        validate_priority(6)


def test_long_message_is_truncated() -> None:
    assert truncate_message("x" * 20, 10) == "xxxxxxx..."


def test_click_url_with_https_passes() -> None:
    assert validate_click_url("https://example.com/build/123") == "https://example.com/build/123"


def test_click_url_with_javascript_fails() -> None:
    with pytest.raises(ValidationError, match="http:// or https://"):
        validate_click_url("javascript:alert(1)")


def test_severity_maps_to_expected_default_tags() -> None:
    assert default_tags_for_severity("info") == ("information_source",)
    assert default_tags_for_severity("success") == ("white_check_mark",)
    assert default_tags_for_severity("warning") == ("warning",)
    assert default_tags_for_severity("error") == ("rotating_light",)


def test_error_severity_elevates_priority_without_explicit_priority() -> None:
    assert resolve_priority("error", None, default_priority=3) == 5


def test_explicit_priority_is_not_overridden_by_error_severity() -> None:
    assert resolve_priority("error", 2, default_priority=3) == 2


def test_warning_severity_elevates_priority_without_explicit_priority() -> None:
    assert resolve_priority("warning", None, default_priority=3) == 4


def test_custom_tags_are_appended_after_severity_tag() -> None:
    assert normalize_tags("success", ["build", "ci"]) == ("white_check_mark", "build", "ci")


def test_invalid_tag_format_fails() -> None:
    with pytest.raises(ValidationError, match="tags must use"):
        normalize_tags("info", ["bad,tag"])

