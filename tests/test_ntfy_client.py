import httpx
import pytest

from ntfy_mcp.config import NtfySettings
from ntfy_mcp.models import NotificationRequest
from ntfy_mcp.ntfy_client import NtfyClient, prepare_notification
from ntfy_mcp.validators import ValidationError


def make_settings(**overrides: object) -> NtfySettings:
    values = {
        "base_url": "https://ntfy.example.com",
        "topic": "default-topic",
        "allowed_topics": frozenset({"default-topic", "alerts-topic"}),
        "token": None,
        "default_priority": 3,
        "max_message_length": 1800,
        "source": "pytest",
        "dry_run": False,
        "timeout_seconds": 10.0,
    }
    values.update(overrides)
    return NtfySettings(**values)  # type: ignore[arg-type]


@pytest.mark.asyncio
async def test_bearer_token_is_applied_from_environment_config_only() -> None:
    captured_headers: httpx.Headers | None = None

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal captured_headers
        captured_headers = request.headers
        return httpx.Response(200, json={"ok": True})

    settings = make_settings(token="env-token")
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http_client:
        client = NtfyClient(settings, http_client=http_client)
        await client.send(
            NotificationRequest(
                title="Build finished",
                message="Build completed",
                tags=["auth_marker"],
            )
        )

    assert captured_headers is not None
    assert captured_headers["Authorization"] == "Bearer env-token"
    assert "auth_marker" in captured_headers["Tags"]


@pytest.mark.asyncio
async def test_no_authorization_header_without_configured_token() -> None:
    captured_headers: httpx.Headers | None = None

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal captured_headers
        captured_headers = request.headers
        return httpx.Response(200, json={"ok": True})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http_client:
        client = NtfyClient(make_settings(), http_client=http_client)
        await client.send(NotificationRequest(title="Done", message="Task completed"))

    assert captured_headers is not None
    assert "Authorization" not in captured_headers


@pytest.mark.asyncio
async def test_dry_run_mode_does_not_perform_network_call() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise AssertionError(f"unexpected network call to {request.url}")

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http_client:
        client = NtfyClient(make_settings(dry_run=True), http_client=http_client)
        result = await client.send(NotificationRequest(title="Done", message="Task completed"))

    assert result.sent is False
    assert result.dry_run is True
    assert result.detail == "dry_run"


@pytest.mark.asyncio
async def test_long_message_is_truncated_before_sending() -> None:
    captured_body = b""

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal captured_body
        captured_body = request.content
        return httpx.Response(200, json={"ok": True})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http_client:
        client = NtfyClient(make_settings(max_message_length=12), http_client=http_client)
        result = await client.send(NotificationRequest(title="Done", message="x" * 20))

    assert captured_body.decode("utf-8") == "xxxxxxxxx..."
    assert result.message_length == 12


@pytest.mark.asyncio
async def test_secret_like_message_is_rejected_before_sending() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise AssertionError(f"unexpected network call to {request.url}")

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http_client:
        client = NtfyClient(make_settings(), http_client=http_client)
        with pytest.raises(ValidationError, match="secret-like"):
            await client.send(
                NotificationRequest(
                    title="Need attention",
                    message="OPENAI_API_KEY=" + "sk-" + ("a" * 32),
                )
            )


def test_prepare_notification_uses_allowed_requested_topic() -> None:
    prepared = prepare_notification(
        make_settings(),
        NotificationRequest(title="Done", message="Task completed", topic="alerts-topic"),
    )

    assert prepared.topic == "alerts-topic"


def test_prepare_notification_rejects_disallowed_requested_topic() -> None:
    with pytest.raises(ValidationError, match="allow-list"):
        prepare_notification(
            make_settings(),
            NotificationRequest(title="Done", message="Task completed", topic="other-topic"),
        )


def test_prepare_notification_allows_https_click_url() -> None:
    prepared = prepare_notification(
        make_settings(),
        NotificationRequest(
            title="PR ready",
            message="Review is ready",
            click_url="https://github.com/example/repo/pull/1",
        ),
    )

    assert prepared.click_url == "https://github.com/example/repo/pull/1"


def test_prepare_notification_rejects_javascript_click_url() -> None:
    with pytest.raises(ValidationError, match="http:// or https://"):
        prepare_notification(
            make_settings(),
            NotificationRequest(
                title="Bad link",
                message="Do not open",
                click_url="javascript:alert(1)",
            ),
        )


def test_error_severity_can_elevate_priority() -> None:
    prepared = prepare_notification(
        make_settings(default_priority=3),
        NotificationRequest(title="Failed", message="Tests failed", severity="error"),
    )

    assert prepared.priority == 5
    assert prepared.tags == ("rotating_light",)
