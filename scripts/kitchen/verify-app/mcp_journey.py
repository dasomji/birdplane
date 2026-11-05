"""Exercise the shipped MCP entry point using a real MCP client over stdio."""

import asyncio
import json
import os
import sys
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


async def main():
    api, runtime, project, item = sys.argv[1:]
    assert api.startswith("http://127.0.0.1:")
    seed = json.loads((Path(runtime) / "seed.json").read_text())
    env = {k: os.environ[k] for k in ("PATH", "HOME") if k in os.environ}
    env.update(
        PLANE_BASE_URL=api,
        PLANE_API_KEY=seed["admin"],
        PLANE_WORKSPACE_SLUG="kitchen-test",
        PYTHONDONTWRITEBYTECODE="1",
    )
    async with (
        stdio_client(
            StdioServerParameters(
                command=sys.executable, args=["-m", "sikku.server"], env=env
            )
        ) as (read, write),
        ClientSession(read, write) as client,
    ):
        await client.initialize()
        tools = await client.list_tools()
        assert "list_issues" in [tool.name for tool in tools.tools]
        result = await client.call_tool("list_issues", {"project": project})
        assert not result.isError, result
        data = json.loads(result.content[0].text)
        assert item in json.dumps(data), data
        print(
            json.dumps(
                {
                    "tools": len(tools.tools),
                    "list_issues": "created work item returned",
                }
            )
        )


asyncio.run(main())
