from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


async def main() -> None:
    project_root = Path(__file__).resolve().parents[1]
    env = os.environ.copy()
    env.setdefault("NTFY_TOPIC", "ntfymcp_smoke_topic_123")
    env.setdefault("NTFY_ALLOWED_TOPICS", env["NTFY_TOPIC"])
    env.setdefault("NTFY_DRY_RUN", "true")

    server = StdioServerParameters(
        command="uv",
        args=[
            "--directory",
            str(project_root),
            "run",
            "python",
            "-m",
            "ntfy_mcp.server",
        ],
        env=env,
    )

    async with (
        stdio_client(server) as (read_stream, write_stream),
        ClientSession(read_stream, write_stream) as session,
    ):
        await session.initialize()
        result = await session.call_tool(
            "notify_user",
            arguments={
                "title": "ntfy-mcp smoke test",
                "message": "MCP client call completed",
                "severity": "success",
            },
        )
        print(json.dumps(result.model_dump(mode="json"), indent=2))


if __name__ == "__main__":
    asyncio.run(main())
