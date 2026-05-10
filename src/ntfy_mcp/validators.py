from __future__ import annotations

import re
from collections.abc import Collection, Sequence
from urllib.parse import urlparse

from ntfy_mcp.models import Severity


class ValidationError(ValueError):
    """Raised when user-controlled notification input is unsafe or invalid."""


TOPIC_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{2,127}$")
TAG_RE = re.compile(r"^[A-Za-z0-9_+-]{1,32}$")
SOURCE_RE = re.compile(r"^[A-Za-z0-9_.:-]{1,64}$")
HEADER_CRLF_RE = re.compile(r"[\r\n]")

DEFAULT_SEVERITY_TAGS: dict[Severity, str] = {
    "info": "information_source",
    "success": "white_check_mark",
    "warning": "warning",
    "error": "rotating_light",
}

SECRET_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    (
        "private key",
        re.compile(r"-----BEGIN [A-Z0-9 ]*PRIVATE KEY-----", re.IGNORECASE),
    ),
    (
        "github token",
        re.compile(r"\b(?:ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9_]{20,}\b"),
    ),
    (
        "github fine-grained token",
        re.compile(r"\bgithub_pat_[A-Za-z0-9_]{20,}\b"),
    ),
    (
        "openai token",
        re.compile(r"\bsk-[A-Za-z0-9_-]{20,}\b"),
    ),
    (
        "jwt token",
        re.compile(
            r"\beyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\b"
        ),
    ),
    (
        "aws access key",
        re.compile(r"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b"),
    ),
    (
        "assigned secret",
        re.compile(
            r"(?i)\b(?:api[_-]?key|access[_-]?token|auth[_-]?token|token|secret|"
            r"password|passwd|pwd)\b\s*[:=]\s*['\"]?[A-Za-z0-9_./+=:@-]{8,}['\"]?"
        ),
    ),
)


def validate_topic(topic: str) -> str:
    normalized = topic.strip()
    if not TOPIC_RE.fullmatch(normalized):
        raise ValidationError(
            "topic must be 3-128 characters using only letters, numbers, '_' or '-'"
        )
    return normalized


def resolve_topic(
    requested_topic: str | None,
    default_topic: str,
    allowed_topics: Collection[str],
) -> str:
    topic = validate_topic(requested_topic) if requested_topic else default_topic
    if topic not in allowed_topics:
        raise ValidationError("topic is not in the configured allow-list")
    return topic


def parse_allowed_topics(value: str) -> frozenset[str]:
    topics = [part.strip() for part in value.split(",") if part.strip()]
    if not topics:
        raise ValidationError("NTFY_ALLOWED_TOPICS must contain at least one topic")
    return frozenset(validate_topic(topic) for topic in topics)


def validate_priority(priority: int) -> int:
    if not 1 <= priority <= 5:
        raise ValidationError("priority must be between 1 and 5")
    return priority


def validate_severity(severity: str) -> Severity:
    if severity not in DEFAULT_SEVERITY_TAGS:
        raise ValidationError("severity must be one of: info, success, warning, error")
    return severity  # type: ignore[return-value]


def resolve_priority(
    severity: Severity,
    explicit_priority: int | None,
    default_priority: int,
) -> int:
    if explicit_priority is not None:
        return validate_priority(explicit_priority)

    default = validate_priority(default_priority)
    if severity == "error":
        return 5
    if severity == "warning":
        return max(default, 4)
    return default


def default_tags_for_severity(severity: Severity) -> tuple[str, ...]:
    return (DEFAULT_SEVERITY_TAGS[severity],)


def normalize_tags(severity: Severity, tags: Sequence[str] | None) -> tuple[str, ...]:
    normalized = [DEFAULT_SEVERITY_TAGS[severity]]
    for tag in tags or ():
        stripped = tag.strip()
        if not stripped:
            raise ValidationError("tags must not contain empty values")
        if not TAG_RE.fullmatch(stripped):
            raise ValidationError(
                "tags must use 1-32 characters from letters, numbers, '_', '-' or '+'"
            )
        if stripped not in normalized:
            normalized.append(stripped)
    if len(normalized) > 8:
        raise ValidationError("at most 7 custom tags are allowed")
    return tuple(normalized)


def validate_click_url(click_url: str | None) -> str | None:
    if click_url is None:
        return None
    normalized = click_url.strip()
    if not normalized:
        return None
    parsed = urlparse(normalized)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValidationError("click_url must start with http:// or https://")
    assert_no_secret_like_text(normalized, "click_url")
    return normalized


def validate_header_value(value: str, field_name: str, max_length: int = 256) -> str:
    normalized = value.strip()
    if not normalized:
        raise ValidationError(f"{field_name} must not be empty")
    if len(normalized) > max_length:
        raise ValidationError(f"{field_name} must be at most {max_length} characters")
    if HEADER_CRLF_RE.search(normalized):
        raise ValidationError(f"{field_name} must not contain newlines")
    return normalized


def validate_source(value: str) -> str:
    normalized = value.strip()
    if not SOURCE_RE.fullmatch(normalized):
        raise ValidationError(
            "NTFY_SOURCE must be 1-64 characters using letters, numbers, '_', '.', ':' or '-'"
        )
    return normalized


def assert_no_secret_like_text(value: str, field_name: str) -> None:
    if not value:
        return
    for secret_name, pattern in SECRET_PATTERNS:
        if pattern.search(value):
            raise ValidationError(
                f"{field_name} contains secret-like content ({secret_name}); refusing to send"
            )


def truncate_message(message: str, max_length: int) -> str:
    if max_length < 1:
        raise ValidationError("max message length must be at least 1")
    if len(message) <= max_length:
        return message
    if max_length <= 3:
        return message[:max_length]
    return f"{message[: max_length - 3].rstrip()}..."
