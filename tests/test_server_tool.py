import pytest

from ntfy_mcp.models import NotificationRequest, NotificationResult
from ntfy_mcp.server import notify_user_impl


class FakeSender:
    def __init__(self) -> None:
        self.requests: list[NotificationRequest] = []

    async def send(self, request: NotificationRequest) -> NotificationResult:
        self.requests.append(request)
        return NotificationResult(
            sent=False,
            dry_run=True,
            topic=request.topic or "default-topic",
            priority=request.priority or 3,
            tags=("white_check_mark",),
            message_length=len(request.message),
            detail="dry_run",
        )


@pytest.mark.asyncio
async def test_notify_user_impl_returns_public_success_response() -> None:
    sender = FakeSender()

    result = await notify_user_impl(
        sender,
        title="Build finished",
        message="All tests passed",
        severity="success",
        tags=["build"],
    )

    assert result["ok"] is True
    assert result["dry_run"] is True
    assert result["topic"] == "default-topic"
    assert sender.requests == [
        NotificationRequest(
            title="Build finished",
            message="All tests passed",
            severity="success",
            tags=["build"],
        )
    ]

