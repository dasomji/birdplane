"""Exercise MCP -> real local Birdplane API relation definitions and lifecycle.

Set PLANE_BASE_URL, PLANE_API_KEY, PLANE_WORKSPACE_SLUG and SIKKU_TEST_PROJECT.
The project must be disposable. Only localhost URLs are accepted.
"""

import asyncio
import json
import os
import sys

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


async def main():
    base = os.environ["PLANE_BASE_URL"]
    if not base.startswith("http://127.0.0.1:"):
        raise ValueError("This integration smoke test requires an isolated local API.")
    workspace = os.environ["PLANE_WORKSPACE_SLUG"]
    project = os.environ["SIKKU_TEST_PROJECT"]
    params = StdioServerParameters(
        command=sys.executable,
        args=["-m", "sikku.server"],
        env={
            key: os.environ[key]
            for key in ("PLANE_BASE_URL", "PLANE_API_KEY", "PLANE_WORKSPACE_SLUG")
        },
    )
    async with (
        stdio_client(params) as (read, write),
        ClientSession(read, write) as session,
    ):
        await session.initialize()

        async def call(name, **arguments):
            result = await session.call_tool(
                name, {"workspace": workspace, **arguments}
            )
            payload = json.loads(result.content[0].text)
            assert not result.isError, payload
            return payload

        items = []
        try:
            for title in ("BIRD-1 smoke dependent", "BIRD-1 smoke blocker"):
                items.append(await call("save_issue", project=project, title=title))
            dependent, blocker = (row["id"] for row in items)

            async def relation(action, issue=dependent, **arguments):
                return await call(
                    "workitem_relation",
                    action=action,
                    project=project,
                    issue=issue,
                    **arguments,
                )

            definitions = await relation("list_definitions")
            assert definitions["source"] == "options"
            assert definitions["actions"] == ["list", "create", "delete"]
            assert (
                next(
                    row
                    for row in definitions["results"]
                    if row["relation_type"] == "blocked_by"
                )["inverse"]
                == "blocking"
            )
            await relation("create", relation_type="blocked_by", related_issue=blocker)
            assert (await relation("list"))["results"] == [
                {
                    "relation_type": "blocked_by",
                    "issue_id": blocker,
                    "project_id": project,
                }
            ]
            assert (await relation("list", issue=blocker))["results"] == [
                {
                    "relation_type": "blocking",
                    "issue_id": dependent,
                    "project_id": project,
                }
            ]
            await relation("delete", relation_type="blocked_by", related_issue=blocker)
            assert (await relation("list"))["results"] == []
            assert (await relation("list", issue=blocker))["results"] == []
            print(
                "PASS: MCP definitions and directed blocked_by create/list/delete against local Birdplane API"
            )
        finally:
            for row in items:
                await call("delete_issue", id=row["id"], project=project)


if __name__ == "__main__":
    asyncio.run(main())
