from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass
from urllib.parse import urlparse, urlunparse

from ntfy_mcp.validators import (
    ValidationError,
    parse_allowed_topics,
    validate_header_value,
    validate_priority,
    validate_source,
    validate_topic,
)


class ConfigError(ValueError):
    """Raised for unsafe or incomplete process configuration."""


@dataclass(frozen=True)
class NtfySettings:
    base_url: str
    topic: str
    allowed_topics: frozenset[str]
    token: str | None
    default_priority: int
    max_message_length: int
    source: str
    dry_run: bool
    timeout_seconds: float = 10.0


def load_settings(environ: Mapping[str, str] | None = None) -> NtfySettings:
    env = os.environ if environ is None else environ

    raw_topic = env.get("NTFY_TOPIC", "").strip()
    if not raw_topic:
        raise ConfigError("NTFY_TOPIC is required")

    try:
        topic = validate_topic(raw_topic)
        allowed_topics = parse_allowed_topics(env.get("NTFY_ALLOWED_TOPICS", topic))
        if topic not in allowed_topics:
            raise ConfigError("NTFY_TOPIC must be included in NTFY_ALLOWED_TOPICS")

        return NtfySettings(
            base_url=_normalize_base_url(env.get("NTFY_BASE_URL", "https://ntfy.sh")),
            topic=topic,
            allowed_topics=allowed_topics,
            token=_optional_header_value(env.get("NTFY_TOKEN"), "NTFY_TOKEN"),
            default_priority=_parse_priority(env.get("NTFY_DEFAULT_PRIORITY", "3")),
            max_message_length=_parse_positive_int(
                env.get("NTFY_MAX_MESSAGE_LENGTH", "1800"),
                "NTFY_MAX_MESSAGE_LENGTH",
            ),
            source=validate_source(env.get("NTFY_SOURCE", "agent")),
            dry_run=_parse_bool(env.get("NTFY_DRY_RUN", "false"), "NTFY_DRY_RUN"),
        )
    except ValidationError as exc:
        raise ConfigError(str(exc)) from exc


def _normalize_base_url(value: str) -> str:
    raw = value.strip().rstrip("/")
    parsed = urlparse(raw)
    if parsed.scheme != "https":
        raise ConfigError("NTFY_BASE_URL must use https")
    if not parsed.netloc:
        raise ConfigError("NTFY_BASE_URL must include a host")
    if parsed.username or parsed.password:
        raise ConfigError("NTFY_BASE_URL must not include credentials")
    if parsed.query or parsed.fragment:
        raise ConfigError("NTFY_BASE_URL must not include query parameters or fragments")
    return urlunparse((parsed.scheme, parsed.netloc, parsed.path.rstrip("/"), "", "", ""))


def _parse_priority(value: str) -> int:
    try:
        return validate_priority(int(value))
    except ValueError as exc:
        raise ConfigError("NTFY_DEFAULT_PRIORITY must be an integer between 1 and 5") from exc


def _parse_positive_int(value: str, env_name: str) -> int:
    try:
        parsed = int(value)
    except ValueError as exc:
        raise ConfigError(f"{env_name} must be a positive integer") from exc
    if parsed < 1:
        raise ConfigError(f"{env_name} must be a positive integer")
    return parsed


def _parse_bool(value: str, env_name: str) -> bool:
    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off", ""}:
        return False
    raise ConfigError(f"{env_name} must be true or false")


def _optional_header_value(value: str | None, env_name: str) -> str | None:
    if value is None:
        return None
    stripped = value.strip()
    if not stripped:
        return None
    return validate_header_value(stripped, env_name, max_length=512)
