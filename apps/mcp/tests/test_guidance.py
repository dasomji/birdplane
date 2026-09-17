import sys

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from starlette.testclient import TestClient

from sikku.server import GUIDE, GUIDE_URI, create_app


def assert_guidance(text):
    assert "Workspace slug:" in text
    assert "Workspace ID:" in text
    assert "Project ID:" in text
    assert "AGENTS.md" in text
    assert "list_workspaces" in text


def test_http_delivers_bundled_guidance_without_plane_access(monkeypatch):
    monkeypatch.setenv("PLANE_BASE_URL", "https://plane.invalid")
    monkeypatch.setenv("PLANE_API_KEY", "not-a-real-key")
    monkeypatch.delenv("PLANE_WORKSPACE_SLUG", raising=False)
    monkeypatch.setenv("SIKKU_MCP_TOKEN", "x" * 48)
    monkeypatch.setenv("SIKKU_ALLOWED_HOSTS", "testserver")
    headers = {
        "Authorization": "Bearer " + "x" * 48,
        "Accept": "application/json, text/event-stream",
    }
    with TestClient(create_app()) as client:

        def rpc(method, params):
            response = client.post(
                "/mcp/",
                headers=headers,
                json={
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": method,
                    "params": params,
                },
            )
            assert response.status_code == 200
            return response.json()

        result = rpc(
            "initialize",
            {
                "protocolVersion": "2025-03-26",
                "capabilities": {},
                "clientInfo": {"name": "guidance-test", "version": "1"},
            },
        )["result"]
        assert_guidance(result["instructions"])
        assert result["instructions"] == GUIDE.split("---", 2)[2].strip()
        assert "resources" in result["capabilities"]
        resources = rpc("resources/list", {})["result"]["resources"]
        assert len(resources) == 1
        assert resources[0]["uri"] == GUIDE_URI
        content = rpc("resources/read", {"uri": GUIDE_URI})["result"]["contents"][0]
        assert content["text"] == GUIDE
        assert content["mimeType"] == "text/markdown"
        assert "error" in rpc("resources/read", {"uri": "birdplane://skills/missing"})
        assert (
            client.post(
                "/mcp/",
                json={
                    "jsonrpc": "2.0",
                    "id": 2,
                    "method": "resources/read",
                    "params": {"uri": GUIDE_URI},
                },
            ).status_code
            == 401
        )


async def test_stdio_delivers_same_bundled_guidance():
    parameters = StdioServerParameters(
        command=sys.executable,
        args=["-m", "sikku.server"],
        env={"PLANE_BASE_URL": "https://plane.invalid", "PLANE_API_KEY": "test-key"},
    )
    async with (
        stdio_client(parameters) as (read, write),
        ClientSession(read, write) as session,
    ):
        initialized = await session.initialize()
        assert_guidance(initialized.instructions)
        resources = await session.list_resources()
        assert str(resources.resources[0].uri) == GUIDE_URI
        resource = await session.read_resource(GUIDE_URI)
        assert resource.contents[0].text == GUIDE
