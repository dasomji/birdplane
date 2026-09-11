import json

import httpx
import pytest
from starlette.testclient import TestClient

from sikku.server import create_app

PID = "11111111-1111-4111-8111-111111111111"
IID = "22222222-2222-4222-8222-222222222222"


def test_http_authentication_host_and_protocol(monkeypatch):
    monkeypatch.setenv("PLANE_BASE_URL", "https://plane.invalid")
    monkeypatch.setenv("PLANE_WORKSPACE_SLUG", "test")
    monkeypatch.setenv("PLANE_API_KEY", "not-a-real-key")
    monkeypatch.setenv("SIKKU_MCP_TOKEN", "x" * 48)
    monkeypatch.setenv("SIKKU_ALLOWED_HOSTS", "testserver")
    with TestClient(create_app()) as client:
        assert client.get("/healthz").status_code == 200
        assert client.post("/mcp/", json={}).status_code == 401
        assert (
            client.post(
                "/mcp/", headers={"Authorization": "Bearer wrong"}, json={}
            ).status_code
            == 401
        )
        headers = {
            "Authorization": "Bearer " + "x" * 48,
            "Accept": "application/json, text/event-stream",
        }
        init = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2025-03-26",
                "capabilities": {},
                "clientInfo": {"name": "test", "version": "1"},
            },
        }
        r = client.post("/mcp/", json=init, headers=headers)
        assert r.status_code == 200
        assert r.json()["result"]["serverInfo"]["name"] == "sikku"
        assert "mcp-session-id" not in r.headers
        r = client.post(
            "/mcp/",
            json={"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
            headers=headers,
        )
        assert len(r.json()["result"]["tools"]) == 15
        for name, arguments in [
            ("create_project", {"name": "Test"}),
            ("create_project", {"name": "  ", "identifier": "TEST"}),
            ("create_project", {"name": "Test", "identifier": "bad/prefix"}),
            ("create_label", {"project": "TEST", "name": "Bug", "color": "red"}),
        ]:
            rejected = client.post(
                "/mcp/",
                headers=headers,
                json={
                    "jsonrpc": "2.0",
                    "id": 3,
                    "method": "tools/call",
                    "params": {"name": name, "arguments": arguments},
                },
            ).json()["result"]
            assert rejected["isError"]
            assert '"error":"invalid_arguments"' in rejected["content"][0]["text"]
        r = client.post("/mcp/", json=init, headers={**headers, "host": "evil.example"})
        assert r.status_code == 421
        r = client.post(
            "/mcp/", json=init, headers={**headers, "origin": "https://evil.example"}
        )
        assert r.status_code == 403
        r = client.post("/mcp/", content=b"x" * 1048577, headers=headers)
        assert r.status_code == 413
        r = client.post(
            "/mcp/", content=b"{}", headers={**headers, "content-length": "invalid"}
        )
        assert r.status_code == 400


def test_list_issues_advertises_and_forwards_pql(monkeypatch):
    pql = "dueDate < today() AND priority = High"
    work_item_requests = []

    def handler(request):
        if request.url.path.endswith(f"/projects/{PID}/"):
            return httpx.Response(200, json={"id": PID})
        if request.url.path.endswith(f"/projects/{PID}/work-items/"):
            work_item_requests.append(request)
            return httpx.Response(
                200,
                json={
                    "results": [
                        {
                            "id": IID,
                            "name": "Follow up",
                            "sequence_id": 7,
                            "project": {
                                "id": PID,
                                "identifier": "TEST",
                            },
                            "state": {"id": "state-1", "name": "Open"},
                            "priority": "high",
                        }
                    ],
                    "next_page_results": False,
                },
            )
        raise AssertionError(f"Unexpected Plane request: {request.url}")

    real_async_client = httpx.AsyncClient
    monkeypatch.setattr(
        "sikku.server.httpx.AsyncClient",
        lambda **kwargs: real_async_client(
            transport=httpx.MockTransport(handler), **kwargs
        ),
    )
    monkeypatch.setenv("PLANE_BASE_URL", "https://plane.invalid")
    monkeypatch.setenv("PLANE_WORKSPACE_SLUG", "test")
    monkeypatch.setenv("PLANE_API_KEY", "not-a-real-key")
    monkeypatch.setenv("SIKKU_MCP_TOKEN", "x" * 48)
    monkeypatch.setenv("SIKKU_ALLOWED_HOSTS", "testserver")
    headers = {
        "Authorization": "Bearer " + "x" * 48,
        "Accept": "application/json, text/event-stream",
    }

    with TestClient(create_app()) as client:
        listed = client.post(
            "/mcp/",
            json={"jsonrpc": "2.0", "id": 1, "method": "tools/list"},
            headers=headers,
        ).json()["result"]["tools"]
        list_issues = next(tool for tool in listed if tool["name"] == "list_issues")
        pql_schema = list_issues["inputSchema"]["properties"]["pql"]
        assert pql_schema["type"] == "string"
        assert pql_schema["minLength"] == 1
        assert pql_schema["maxLength"] == 500

        response = client.post(
            "/mcp/",
            json={
                "jsonrpc": "2.0",
                "id": 2,
                "method": "tools/call",
                "params": {
                    "name": "list_issues",
                    "arguments": {
                        "project": PID,
                        "pql": pql,
                        "filters": [
                            {
                                "field": "priority",
                                "operator": "is",
                                "value": "high",
                            }
                        ],
                    },
                },
            },
            headers=headers,
        ).json()["result"]

    assert not response["isError"]
    assert json.loads(response["content"][0]["text"])["results"] == [
        {
            "id": IID,
            "identifier": "TEST-7",
            "url": f"https://plane.invalid/test/projects/{PID}/work-items/{IID}",
            "title": "Follow up",
            "state": {"id": "state-1", "name": "Open"},
            "priority": "high",
            "project": {"id": PID, "identifier": "TEST"},
        }
    ]
    assert len(work_item_requests) == 1
    assert work_item_requests[0].url.params["pql"] == pql
    assert json.loads(work_item_requests[0].url.params["filters"]) == {
        "and": [{"priority__in": "high"}]
    }


def test_list_issues_pql_is_bound_to_pagination_cursor(monkeypatch):
    pql = "dueDate < today()"
    work_item_requests = []

    def handler(request):
        if request.url.path.endswith(f"/projects/{PID}/"):
            return httpx.Response(200, json={"id": PID})
        if request.url.path.endswith(f"/projects/{PID}/work-items/"):
            work_item_requests.append(request)
            return httpx.Response(
                200,
                json={
                    "results": [
                        {
                            "id": IID,
                            "name": "First",
                            "sequence_id": 7,
                            "project": {"id": PID, "identifier": "TEST"},
                        },
                        {
                            "id": "33333333-3333-4333-8333-333333333333",
                            "name": "Second",
                            "sequence_id": 8,
                            "project": {"id": PID, "identifier": "TEST"},
                        },
                    ],
                    "next_page_results": False,
                },
            )
        raise AssertionError(f"Unexpected Plane request: {request.url}")

    real_async_client = httpx.AsyncClient
    monkeypatch.setattr(
        "sikku.server.httpx.AsyncClient",
        lambda **kwargs: real_async_client(
            transport=httpx.MockTransport(handler), **kwargs
        ),
    )
    monkeypatch.setenv("PLANE_BASE_URL", "https://plane.invalid")
    monkeypatch.setenv("PLANE_WORKSPACE_SLUG", "test")
    monkeypatch.setenv("PLANE_API_KEY", "not-a-real-key")
    monkeypatch.setenv("SIKKU_MCP_TOKEN", "x" * 48)
    monkeypatch.setenv("SIKKU_ALLOWED_HOSTS", "testserver")
    headers = {
        "Authorization": "Bearer " + "x" * 48,
        "Accept": "application/json, text/event-stream",
    }

    def call(client, request_id, requested_pql, cursor=None):
        arguments = {"project": PID, "pql": requested_pql, "limit": 1}
        if cursor:
            arguments["cursor"] = cursor
        return client.post(
            "/mcp/",
            json={
                "jsonrpc": "2.0",
                "id": request_id,
                "method": "tools/call",
                "params": {"name": "list_issues", "arguments": arguments},
            },
            headers=headers,
        ).json()["result"]

    with TestClient(create_app()) as client:
        first = json.loads(call(client, 1, pql)["content"][0]["text"])
        second = json.loads(
            call(client, 2, pql, first["next_cursor"])["content"][0]["text"]
        )
        changed = call(client, 3, "dueDate < daysFromNow(1)", first["next_cursor"])

    assert [first["results"][0]["title"], second["results"][0]["title"]] == [
        "First",
        "Second",
    ]
    assert [request.url.params["pql"] for request in work_item_requests] == [pql, pql]
    assert changed["isError"]
    assert json.loads(changed["content"][0]["text"])["error"] == "invalid_cursor"


@pytest.mark.parametrize("pql", ["", "x" * 501, 42])
def test_list_issues_rejects_invalid_pql_before_plane(monkeypatch, pql):
    plane_requests = []

    def handler(request):
        plane_requests.append(request)
        return httpx.Response(200, json={})

    real_async_client = httpx.AsyncClient
    monkeypatch.setattr(
        "sikku.server.httpx.AsyncClient",
        lambda **kwargs: real_async_client(
            transport=httpx.MockTransport(handler), **kwargs
        ),
    )
    monkeypatch.setenv("PLANE_BASE_URL", "https://plane.invalid")
    monkeypatch.setenv("PLANE_WORKSPACE_SLUG", "test")
    monkeypatch.setenv("PLANE_API_KEY", "not-a-real-key")
    monkeypatch.setenv("SIKKU_MCP_TOKEN", "x" * 48)
    monkeypatch.setenv("SIKKU_ALLOWED_HOSTS", "testserver")
    headers = {
        "Authorization": "Bearer " + "x" * 48,
        "Accept": "application/json, text/event-stream",
    }

    with TestClient(create_app()) as client:
        result = client.post(
            "/mcp/",
            json={
                "jsonrpc": "2.0",
                "id": 1,
                "method": "tools/call",
                "params": {
                    "name": "list_issues",
                    "arguments": {"project": PID, "pql": pql},
                },
            },
            headers=headers,
        ).json()["result"]

    assert result["isError"]
    assert json.loads(result["content"][0]["text"])["error"] == "invalid_arguments"
    assert plane_requests == []


def test_list_issues_surfaces_pql_upstream_rejection_as_tool_error(monkeypatch):
    pql = "dueDate < today()"

    def handler(request):
        if request.url.path.endswith(f"/projects/{PID}/"):
            return httpx.Response(200, json={"id": PID})
        if request.url.path.endswith(f"/projects/{PID}/work-items/"):
            assert request.url.params["pql"] == pql
            return httpx.Response(400, json={"detail": "parser internals"})
        raise AssertionError(f"Unexpected Plane request: {request.url}")

    real_async_client = httpx.AsyncClient
    monkeypatch.setattr(
        "sikku.server.httpx.AsyncClient",
        lambda **kwargs: real_async_client(
            transport=httpx.MockTransport(handler), **kwargs
        ),
    )
    monkeypatch.setenv("PLANE_BASE_URL", "https://plane.invalid")
    monkeypatch.setenv("PLANE_WORKSPACE_SLUG", "test")
    monkeypatch.setenv("PLANE_API_KEY", "not-a-real-key")
    monkeypatch.setenv("SIKKU_MCP_TOKEN", "x" * 48)
    monkeypatch.setenv("SIKKU_ALLOWED_HOSTS", "testserver")
    headers = {
        "Authorization": "Bearer " + "x" * 48,
        "Accept": "application/json, text/event-stream",
    }

    with TestClient(create_app()) as client:
        result = client.post(
            "/mcp/",
            json={
                "jsonrpc": "2.0",
                "id": 1,
                "method": "tools/call",
                "params": {
                    "name": "list_issues",
                    "arguments": {"project": PID, "pql": pql},
                },
            },
            headers=headers,
        ).json()["result"]

    assert result["isError"]
    assert json.loads(result["content"][0]["text"]) == {
        "error": "plane_api_error",
        "message": "Plane rejected the fields or filter.",
        "status": 400,
    }
