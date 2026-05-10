# Security Policy

`ntfy-mcp` is intentionally small because it sits between AI agents and a human
notification channel.

Please report security issues privately through GitHub's private vulnerability
reporting if it is available for the repository. If that is unavailable, open a
minimal public issue that does not include exploit details or secrets and ask
for a private coordination path.

## Supported Versions

The project is pre-1.0. Security fixes are expected to land on `main` until
release branches exist.

## Scope

Security-sensitive areas include:

- topic allow-list bypasses
- arbitrary header injection
- arbitrary URL or protocol dispatch
- secret leakage through notification content, logs, errors, or examples
- accidental support for attachments or action buttons outside the configured
  MVP
- unsafe remote transport defaults

Please do not include real ntfy tokens, API keys, private topics, or private
messages in reports.

