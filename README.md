# ntfy-mcp

[![Python](https://img.shields.io/badge/python-3.11%2B-blue)](https://www.python.org/)
[![MCP](https://img.shields.io/badge/MCP-STDIO-green)](https://modelcontextprotocol.io/)
[![License: MIT](https://img.shields.io/badge/license-MIT-informational)](LICENSE)

`ntfy-mcp` is a small, security-focused MCP server that lets AI agents send push
notifications through [ntfy](https://ntfy.sh).

It is designed for the practical moments when a long-running agent needs your
attention:

- a build or test run finishes
- tests fail while you are away
- an approval is needed
- a PR is ready for review
- a task fails and needs human attention

The server exposes one MCP tool:

```text
notify_user
```

Under the hood it sends an HTTPS POST to an operator-configured ntfy topic. The
model can write the notification content, but it cannot choose arbitrary ntfy
servers, arbitrary topics, arbitrary headers, attachments, or action buttons.

## Why This Exists

Coding agents are increasingly good at running for several minutes without help.
The missing piece is often human attention. Desktop notifications tied to one
app are easy to miss, and polling a terminal is tedious.

`ntfy-mcp` gives MCP-capable clients a tiny, boring, auditable path to notify you
on your phone without turning ntfy into an unbounded exfiltration channel.

## Security Model

This project treats notification delivery as a security boundary, not as a thin
wrapper around ntfy.

The MCP model is considered untrusted input. It must not control:

- the ntfy base URL
- arbitrary topics
- auth headers
- arbitrary request headers
- file attachments
- action buttons

MVP controls:

- `NTFY_TOPIC` is required.
- `NTFY_ALLOWED_TOPICS` defaults to `NTFY_TOPIC`.
- Requested topics must be in the allow-list.
- Topics must match a conservative letters, numbers, `_`, `-` format.
- `NTFY_BASE_URL` must use HTTPS and cannot include credentials.
- Bearer auth only comes from `NTFY_TOKEN`.
- Priority is constrained to `1` through `5`.
- Long messages are truncated before sending.
- Obvious secret-like content is rejected before sending.
- `click_url` must be `http://` or `https://`.
- Only a fixed set of ntfy headers is sent.
- Full notification messages are not logged by default.
- `NTFY_DRY_RUN=true` validates and returns success without network I/O.

Secret detection is intentionally basic. It blocks obvious private keys, GitHub
tokens, OpenAI-style tokens, JWT-looking tokens, AWS access keys, and common
`token=`, `password=`, `api_key=` style assignments. It is a guardrail, not a
replacement for careful tool permissions.

## Quickstart

Install dependencies:

```bash
uv sync
```

Choose a long random topic:

```bash
openssl rand -hex 24
```

Run a dry-run MCP client smoke test:

```bash
NTFY_TOPIC="replace-with-long-random-topic" \
NTFY_ALLOWED_TOPICS="replace-with-long-random-topic" \
NTFY_DRY_RUN=true \
uv run python examples/mcp-client-smoke.py
```

Run the STDIO MCP server directly:

```bash
NTFY_TOPIC="replace-with-long-random-topic" \
NTFY_ALLOWED_TOPICS="replace-with-long-random-topic" \
uv run python -m ntfy_mcp.server
```

The server waits for MCP messages on STDIO. Use an MCP client to call
`notify_user`.

## Subscribe In The ntfy App

1. Install the ntfy mobile app.
2. Add a subscription.
3. Use `https://ntfy.sh` unless you self-host ntfy.
4. Enter your long random topic.
5. If your ntfy server requires auth, configure a token on the server and set
   `NTFY_TOKEN` for this MCP server.

Avoid short or guessable topics. Public ntfy topics are effectively bearer
secrets unless protected by server-side access control.

## Test ntfy Directly

Before wiring an MCP client, verify ntfy delivery:

```bash
curl -fsS \
  -H "Title: ntfy-mcp test" \
  -H "Priority: 3" \
  -d "hello from ntfy-mcp" \
  "https://ntfy.sh/$NTFY_TOPIC"
```

For protected topics:

```bash
curl -fsS \
  -H "Authorization: Bearer $NTFY_TOKEN" \
  -H "Title: ntfy-mcp test" \
  -d "hello from ntfy-mcp" \
  "https://ntfy.sh/$NTFY_TOPIC"
```

## Codex Setup

Add a server entry to `~/.codex/config.toml`:

```toml
[mcp_servers.ntfy]
command = "uv"
args = ["--directory", "/absolute/path/to/ntfy-mcp", "run", "python", "-m", "ntfy_mcp.server"]
enabled = true
enabled_tools = ["notify_user"]

[mcp_servers.ntfy.env]
NTFY_BASE_URL = "https://ntfy.sh"
NTFY_TOPIC = "replace-with-long-random-topic"
NTFY_ALLOWED_TOPICS = "replace-with-long-random-topic"
NTFY_SOURCE = "codex"
NTFY_DEFAULT_PRIORITY = "3"
NTFY_MAX_MESSAGE_LENGTH = "1800"
```

If your topic requires auth:

```toml
NTFY_TOKEN = "replace-with-ntfy-access-token"
```

Keep tokens in local config or a secret manager. Do not commit them.

## Claude Desktop Setup

Add a server entry to Claude Desktop's MCP configuration:

```json
{
  "mcpServers": {
    "ntfy": {
      "command": "uv",
      "args": [
        "--directory",
        "/absolute/path/to/ntfy-mcp",
        "run",
        "python",
        "-m",
        "ntfy_mcp.server"
      ],
      "env": {
        "NTFY_BASE_URL": "https://ntfy.sh",
        "NTFY_TOPIC": "replace-with-long-random-topic",
        "NTFY_ALLOWED_TOPICS": "replace-with-long-random-topic",
        "NTFY_SOURCE": "claude",
        "NTFY_DEFAULT_PRIORITY": "3",
        "NTFY_MAX_MESSAGE_LENGTH": "1800"
      }
    }
  }
}
```

Add `NTFY_TOKEN` inside `env` only if the ntfy topic requires bearer auth.

## Tool Input

`notify_user` accepts:

| Field | Type | Notes |
| --- | --- | --- |
| `title` | string | Required. Sent as the ntfy title. |
| `message` | string | Required. Truncated to `NTFY_MAX_MESSAGE_LENGTH`. |
| `severity` | `info`, `success`, `warning`, `error` | Required by schema default. |
| `priority` | integer | Optional. Must be `1` through `5`. |
| `tags` | list of strings | Optional. Conservative tag aliases only. |
| `click_url` | string | Optional. Must start with `http://` or `https://`. |
| `topic` | string | Optional. Must be in `NTFY_ALLOWED_TOPICS`. |

Severity adds a default tag:

| Severity | Default tag |
| --- | --- |
| `info` | `information_source` |
| `success` | `white_check_mark` |
| `warning` | `warning` |
| `error` | `rotating_light` |

Priority behavior:

- Explicit priority wins if it is `1` through `5`.
- `info` and `success` use `NTFY_DEFAULT_PRIORITY`.
- `warning` defaults to at least `4` when no explicit priority is supplied.
- `error` defaults to `5` when no explicit priority is supplied.

## Example Prompts

- "Notify me when the build finishes."
- "Notify me only if tests fail."
- "Notify me when you need approval."
- "Notify me when the PR is ready for review."

## Environment Variables

| Variable | Required | Default | Description |
| --- | --- | --- | --- |
| `NTFY_BASE_URL` | No | `https://ntfy.sh` | HTTPS ntfy server base URL. |
| `NTFY_TOPIC` | Yes | None | Default topic. Must pass topic validation. |
| `NTFY_ALLOWED_TOPICS` | No | `NTFY_TOPIC` | Comma-separated allow-list. |
| `NTFY_TOKEN` | No | None | Bearer token used for the `Authorization` header. |
| `NTFY_DEFAULT_PRIORITY` | No | `3` | Default priority for `info` and `success`. |
| `NTFY_MAX_MESSAGE_LENGTH` | No | `1800` | Maximum message length before truncation. |
| `NTFY_SOURCE` | No | `agent` | Operator-controlled source label. |
| `NTFY_DRY_RUN` | No | `false` | Validate and return success without network I/O. |

## Development

```bash
uv run pytest
uv run ruff check .
```

Dry-run the full MCP path:

```bash
NTFY_TOPIC="ntfymcp_smoke_topic_123" \
NTFY_ALLOWED_TOPICS="ntfymcp_smoke_topic_123" \
NTFY_DRY_RUN=true \
uv run python examples/mcp-client-smoke.py
```

## Limitations

- STDIO first.
- Remote Streamable HTTP mode is future work.
- Attachments are intentionally omitted from the MVP.
- Action buttons are intentionally omitted from the MVP.
- Secret detection is basic and intentionally conservative.
- No local rate limiting yet.

## Roadmap

- Optional local rate limiting and duplicate suppression.
- Streamable HTTP mode with authentication guidance.
- Stronger configurable secret scanning.
- Metadata-only audit logging.
- Notification templates for common agent states.
- Packaged releases and signed artifacts.

## License

MIT. See [LICENSE](LICENSE).

