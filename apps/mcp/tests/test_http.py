from starlette.testclient import TestClient

from sikku.server import create_app


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
