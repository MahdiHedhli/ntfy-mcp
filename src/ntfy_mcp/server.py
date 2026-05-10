from __future__ import annotations

import sys
from typing import Any, Protocol

from mcp.server.fastmcp import FastMCP

from ntfy_mcp.config import ConfigError, NtfySettings, load_settings
from ntfy_mcp.models import NotificationRequest, NotificationResult, Severity
from ntfy_mcp.ntfy_client import NtfyClient


class NotificationSender(Protocol):
    async def send(self, request: NotificationRequest) -> NotificationResult:
        pass


async def notify_user_impl(
    sender: NotificationSender,
    *,
    title: str,
    message: str,
    severity: Severity = "info",
    priority: int | None = None,
    tags: list[str] | None = None,
    click_url: str | None = None,
    topic: str | None = None,
) -> dict[str, object]:
    result = await sender.send(
        NotificationRequest(
            title=title,
            message=message,
            severity=severity,
            priority=priority,
            tags=tags,
            click_url=click_url,
            topic=topic,
        )
    )
    return result.to_public_dict()


def create_server(
    settings: NtfySettings | None = None,
    sender: NotificationSender | None = None,
) -> FastMCP:
    if sender is None:
        resolved_settings = settings or load_settings()
        sender = NtfyClient(resolved_settings)

    mcp = FastMCP("ntfy-mcp")

    @mcp.tool()
    async def notify_user(
        title: str,
        message: str,
        severity: Severity = "info",
        priority: int | None = None,
        tags: list[str] | None = None,
        click_url: str | None = None,
        topic: str | None = None,
    ) -> dict[str, Any]:
        """Send an allow-listed ntfy push notification to the configured user."""
        return await notify_user_impl(
            sender,
            title=title,
            message=message,
            severity=severity,
            priority=priority,
            tags=tags,
            click_url=click_url,
            topic=topic,
        )

    return mcp


def main() -> None:
    try:
        mcp = create_server()
    except ConfigError as exc:
        sys.stderr.write(f"ntfy-mcp configuration error: {exc}\n")
        raise SystemExit(2) from exc
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()

