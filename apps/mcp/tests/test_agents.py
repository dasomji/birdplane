import json

import httpx
import pytest
from sikku.plane import Plane, PlaneError
from sikku.schema import TOOLS

PID = "11111111-1111-4111-8111-111111111111"
IID = "22222222-2222-4222-8222-222222222222"
AID = "33333333-3333-4333-8333-333333333333"


async def test_assign_agent_by_name_clears_humans_and_null_removes_agent():
    writes = []

    def handler(request):
        if request.url.path.endswith("/agents/"):
            return httpx.Response(
                200, json=[{"id": AID, "name": "My agent", "can_assign": True}]
            )
        if request.method == "PATCH":
            writes.append(json.loads(request.content))
        return httpx.Response(200, json={"id": IID, "project": PID, "name": "Task"})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        plane = Plane(client, "https://plane.test", "ws")
        await plane.save_issue({"id": "TEST-1", "agent": "My agent"})
        await plane.save_issue({"id": "TEST-1", "agent": None})
    assert writes == [{"agent_id": AID, "assignees": []}, {"agent_id": None}]


async def test_agent_filter_is_sent_before_pagination_and_returned_in_projection():
    def handler(request):
        if request.url.path.endswith(f"/projects/{PID}/"):
            return httpx.Response(200, json={"id": PID, "identifier": "TEST"})
        assert request.url.params["agent_id"] == AID
        assert "agent_id" in request.url.params["fields"]
        return httpx.Response(
            200,
            json={
                "results": [
                    {"id": IID, "project": PID, "agent_id": AID, "name": "Task"}
                ],
                "next_cursor": None,
            },
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        result = await Plane(client, "https://plane.test", "ws").list_issues(
            {"project": PID, "agent": AID, "fields": ["title", "agent"]}
        )
    assert result["results"][0]["agent"] == AID


async def test_api_permission_denial_is_not_retried():
    writes = []

    def handler(request):
        if request.method == "PATCH":
            writes.append(request.method)
            return httpx.Response(403, json={"detail": "Forbidden"})
        return httpx.Response(200, json={"id": IID, "project": PID})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(PlaneError):
            await Plane(client, "https://plane.test", "ws").save_issue(
                {"id": "TEST-1", "agent": AID}
            )
    assert writes == ["PATCH"]


def test_agent_fields_are_in_tool_schemas():
    tools = {tool.name: tool.inputSchema["properties"] for tool in TOOLS}
    assert "agent" in tools["save_issue"]
    assert "agent" in tools["list_issues"]
    assert "agents" in tools["list_metadata"]["kind"]["enum"]
