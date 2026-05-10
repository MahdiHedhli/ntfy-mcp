from __future__ import annotations

import logging
from dataclasses import dataclass

import httpx

from ntfy_mcp.config import NtfySettings
from ntfy_mcp.models import NotificationRequest, NotificationResult
from ntfy_mcp.validators import (
    ValidationError,
    assert_no_secret_like_text,
    normalize_tags,
    resolve_priority,
    resolve_topic,
    truncate_message,
    validate_click_url,
    validate_header_value,
    validate_severity,
)

LOG = logging.getLogger(__name__)


class NtfyDeliveryError(RuntimeError):
    """Raised when ntfy cannot accept the notification."""


@dataclass(frozen=True)
class PreparedNotification:
    title: str
    message: str
    severity: str
    priority: int
    tags: tuple[str, ...]
    click_url: str | None
    topic: str


class NtfyClient:
    def __init__(
        self,
        settings: NtfySettings,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        self._settings = settings
        self._http_client = http_client

    async def send(self, request: NotificationRequest) -> NotificationResult:
        prepared = prepare_notification(self._settings, request)

        if self._settings.dry_run:
            LOG.info(
                "ntfy dry-run notification topic=%s severity=%s priority=%s message_length=%s",
                prepared.topic,
                prepared.severity,
                prepared.priority,
                len(prepared.message),
            )
            return NotificationResult(
                sent=False,
                dry_run=True,
                topic=prepared.topic,
                priority=prepared.priority,
                tags=prepared.tags,
                message_length=len(prepared.message),
                detail="dry_run",
            )

        close_client = self._http_client is None
        http_client = self._http_client or httpx.AsyncClient(timeout=self._settings.timeout_seconds)
        try:
            response = await http_client.post(
                f"{self._settings.base_url}/{prepared.topic}",
                content=prepared.message.encode("utf-8"),
                headers=self._headers(prepared),
            )
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            status_code = exc.response.status_code
            raise NtfyDeliveryError(f"ntfy returned HTTP {status_code}") from None
        except httpx.RequestError as exc:
            raise NtfyDeliveryError(f"ntfy request failed: {exc.__class__.__name__}") from None
        finally:
            if close_client:
                await http_client.aclose()

        LOG.info(
            "sent ntfy notification topic=%s severity=%s priority=%s "
            "status_code=%s message_length=%s",
            prepared.topic,
            prepared.severity,
            prepared.priority,
            response.status_code,
            len(prepared.message),
        )
        return NotificationResult(
            sent=True,
            dry_run=False,
            topic=prepared.topic,
            priority=prepared.priority,
            tags=prepared.tags,
            message_length=len(prepared.message),
            status_code=response.status_code,
        )

    def _headers(self, prepared: PreparedNotification) -> dict[str, str]:
        headers = {
            "Title": prepared.title,
            "Priority": str(prepared.priority),
            "Tags": ",".join(prepared.tags),
            "X-NTFY-MCP-Source": self._settings.source,
        }
        if prepared.click_url:
            headers["Click"] = prepared.click_url
        if self._settings.token:
            headers["Authorization"] = f"Bearer {self._settings.token}"
        return headers


def prepare_notification(
    settings: NtfySettings,
    request: NotificationRequest,
) -> PreparedNotification:
    severity = validate_severity(request.severity)

    title = validate_header_value(request.title, "title", max_length=160)
    message = request.message.strip()
    if not message:
        raise ValidationError("message must not be empty")

    assert_no_secret_like_text(title, "title")
    assert_no_secret_like_text(message, "message")

    topic = resolve_topic(request.topic, settings.topic, settings.allowed_topics)
    priority = resolve_priority(severity, request.priority, settings.default_priority)
    tags = normalize_tags(severity, request.tags)
    click_url = validate_click_url(request.click_url)
    truncated_message = truncate_message(message, settings.max_message_length)

    return PreparedNotification(
        title=title,
        message=truncated_message,
        severity=severity,
        priority=priority,
        tags=tags,
        click_url=click_url,
        topic=topic,
    )
