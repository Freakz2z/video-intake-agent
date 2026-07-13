"""Small stdio client used to verify the packaged MCP server end to end."""

from __future__ import annotations

import asyncio
import json
import sys
from typing import Any

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


async def inspect_server() -> dict[str, Any]:
    parameters = StdioServerParameters(
        command=sys.executable,
        args=["-m", "video_intake_mcp"],
    )
    async with stdio_client(parameters) as (read_stream, write_stream):
        async with ClientSession(read_stream, write_stream) as session:
            initialized = await session.initialize()
            tools = await session.list_tools()
            resources = await session.list_resources()
            prompts = await session.list_prompts()
            doctor = await session.call_tool("doctor", {})
            return {
                "server": initialized.serverInfo.model_dump(by_alias=True),
                "tools": [tool.name for tool in tools.tools],
                "resources": [str(resource.uri) for resource in resources.resources],
                "prompts": [prompt.name for prompt in prompts.prompts],
                "doctor": doctor.structuredContent,
            }


def main() -> None:
    print(json.dumps(asyncio.run(inspect_server()), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
