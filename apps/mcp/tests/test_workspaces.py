import json
from concurrent.futures import ThreadPoolExecutor

import httpx
import pytest
from starlette.testclient import TestClient

from sikku.plane import Plane, PlaneError
from sikku.server import create_app


@pytest.fixture
def mcp(monkeypatch):
    requests = []

    def handler(request):
        requests.append(request)
        assert request.headers["x-api-key"] == "test-key"
        path = request.url.path
        if path == "/api/v1/workspaces/":
            second = "cursor" in request.url.params
            return httpx.Response(
                200,
                json={
                    "results": [
                        {
                            "id": "w2" if second else "w1",
                            "name": "Personal" if second else "Company",
                            "slug": "personal" if second else "company",
                            "secret": "omitted",
                        }
                    ],
                    "next_page_results": not second,
                    "next_cursor": "1:1:0",
                },
            )
        if "/denied/" in path:
            return httpx.Response(403, json={"secret": "upstream"})
        slug = path.split("/")[4]
        if request.method == "POST":
            body = json.loads(request.content)
            assert "workspace" not in body
            return httpx.Response(201, json={"id": slug, **body})
        return httpx.Response(
            200,
            json=[
                {"id": slug + "1", "name": "Shared", "identifier": "APP"},
                {"id": slug + "2", "name": "Other", "identifier": "OTHER"},
            ],
        )

    real_client = httpx.AsyncClient
    monkeypatch.setattr(
        "sikku.server.httpx.AsyncClient",
        lambda **kw: real_client(transport=httpx.MockTransport(handler), **kw),
    )
    for key, value in {
        "PLANE_BASE_URL": "https://plane.invalid",
        "PLANE_API_KEY": "test-key",
        "SIKKU_MCP_TOKEN": "x" * 48,
        "SIKKU_ALLOWED_HOSTS": "testserver",
    }.items():
        monkeypatch.setenv(key, value)
    monkeypatch.delenv("PLANE_WORKSPACE_SLUG", raising=False)

    def call(client, tool_name, **args):
        response = client.post(
            "/mcp/",
            headers={
                "Authorization": "Bearer " + "x" * 48,
                "Accept": "application/json, text/event-stream",
            },
            json={
                "jsonrpc": "2.0",
                "id": 1,
                "method": "tools/call",
                "params": {"name": tool_name, "arguments": args},
            },
        )
        return json.loads(response.json()["result"]["content"][0]["text"])

    return requests, call


def test_discovery_without_default_and_selection(mcp):
    requests, call = mcp
    with TestClient(create_app()) as client:
        first = call(client, "list_workspaces", limit=1, query="o")
        assert first["default_workspace"] is None
        assert first["results"] == [{"id": "w1", "name": "Company", "slug": "company"}]
        second = call(
            client, "list_workspaces", limit=1, query="o", cursor=first["next_cursor"]
        )
        assert second["results"][0]["slug"] == "personal"
        assert second["next_cursor"] is None
        assert dict(requests[1].url.params) == {
            "per_page": "1",
            "query": "o",
            "cursor": "1:1:0",
        }
        assert call(client, "list_projects")["error"] == "workspace_required"
        assert len(requests) == 2
        for slug in ("company", "personal", "company"):
            assert (
                call(client, "list_projects", workspace=slug)["results"][0]["id"]
                == slug + "1"
            )
            assert (
                call(
                    client,
                    "create_project",
                    workspace=slug,
                    name="Shared",
                    identifier="APP",
                )["id"]
                == slug
            )
        assert call(client, "list_projects", workspace="denied")["status"] == 403
        for slug in (
            "",
            "..",
            "../company",
            "company/personal",
            "https://evil.invalid",
            None,
        ):
            count = len(requests)
            assert (
                call(client, "list_projects", workspace=slug)["error"]
                == "invalid_arguments"
            )
            assert len(requests) == count


def test_default_and_workspace_bound_project_cursor(mcp, monkeypatch):
    _, call = mcp
    monkeypatch.setenv("PLANE_WORKSPACE_SLUG", "company")
    with TestClient(create_app()) as client:
        assert call(client, "list_workspaces")["default_workspace"] == "company"
        first = call(client, "list_projects", limit=1)
        assert first["results"][0]["id"] == "company1"
        assert (
            call(
                client,
                "list_projects",
                workspace="personal",
                limit=1,
                cursor=first["next_cursor"],
            )["error"]
            == "invalid_cursor"
        )
        assert (
            call(
                client,
                "list_projects",
                workspace="company",
                limit=1,
                cursor=first["next_cursor"],
            )["results"][0]["id"]
            == "company2"
        )
        assert call(client, "list_projects")["results"][0]["id"] == "company1"


def test_concurrent_calls_keep_workspace_selection_local(mcp):
    _, call = mcp
    with TestClient(create_app()) as client, ThreadPoolExecutor(max_workers=4) as pool:
        slugs = ["company", "personal"] * 4
        results = list(
            pool.map(lambda slug: call(client, "list_projects", workspace=slug), slugs)
        )
        assert [result["results"][0]["id"] for result in results] == [
            slug + "1" for slug in slugs
        ]


async def test_issue_cursor_cannot_cross_workspaces():
    pid = "11111111-1111-4111-8111-111111111111"

    def handler(request):
        if request.url.path.endswith(f"/projects/{pid}/"):
            return httpx.Response(200, json={"id": pid})
        return httpx.Response(
            200,
            json={
                "results": [
                    {
                        "id": "first",
                        "name": "First",
                        "project": {"id": pid, "identifier": "APP"},
                        "sequence_id": 1,
                    },
                    {
                        "id": "second",
                        "name": "Second",
                        "project": {"id": pid, "identifier": "APP"},
                        "sequence_id": 2,
                    },
                ],
                "next_page_results": False,
            },
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        first = await Plane(client, "https://plane.invalid", "company").dispatch(
            "list_issues", {"project": pid, "limit": 1}
        )
        with pytest.raises(PlaneError) as exc:
            await Plane(client, "https://plane.invalid", "personal").dispatch(
                "list_issues",
                {"project": pid, "limit": 1, "cursor": first["next_cursor"]},
            )
        assert exc.value.payload["error"] == "invalid_cursor"
