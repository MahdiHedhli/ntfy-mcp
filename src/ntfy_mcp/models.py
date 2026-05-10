from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal

Severity = Literal["info", "success", "warning", "error"]


@dataclass(frozen=True)
class NotificationRequest:
    title: str
    message: str
    severity: Severity = "info"
    priority: int | None = None
    tags: Sequence[str] | None = None
    click_url: str | None = None
    topic: str | None = None


@dataclass(frozen=True)
class NotificationResult:
    sent: bool
    dry_run: bool
    topic: str
    priority: int
    tags: tuple[str, ...]
    message_length: int
    status_code: int | None = None
    detail: str = "sent"

    def to_public_dict(self) -> dict[str, object]:
        return {
            "ok": True,
            "sent": self.sent,
            "dry_run": self.dry_run,
            "topic": self.topic,
            "priority": self.priority,
            "tags": list(self.tags),
            "message_length": self.message_length,
            "status_code": self.status_code,
            "detail": self.detail,
        }

