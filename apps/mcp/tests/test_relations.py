"""Relations through the actual MCP HTTP boundary, including legacy servers."""

import json

import httpx
import pytest
from starlette.testclient import TestClient

from sikku.server import create_app

PID = "11111111-1111-4111-8111-111111111111"
DEPENDENT = "22222222-2222-4222-8222-222222222222"
BLOCKER = "33333333-3333-4333-8333-333333333333"
TYPES = [
    "blocked_by",
    "blocking",
    "relates_to",
    "duplicate",
    "start_before",
    "start_after",
    "finish_before",
    "finish_after",
]


@pytest.fixture
def relations_mcp(monkeypatch):
    requests = []
    config = {
        "options_status": 200,
        "relation_status": 200,
        "source_status": 200,
        "edge": False,
        "mutation_status": 200,
        "create_conflict": False,
        "groups": None,
    }

    def handler(request):
        requests.append(request)
        assert request.headers["x-api-key"] == "test-key"
        assert request.url.path.startswith("/api/v1/workspaces/personal/")
        path = request.url.path
        if path.endswith("/relations/"):
            methods = (
                "GET, POST, DELETE, OPTIONS"
                if config["options_status"] == 200
                else "GET, POST"
            )
            if request.method == "OPTIONS":
                return httpx.Response(
                    config["options_status"],
                    headers={"Allow": methods},
                    json={
                        "relation_types": [
                            {
                                "relation_type": name,
                                "inverse": {
                                    "blocked_by": "blocking",
                                    "blocking": "blocked_by",
                                }.get(name, name),
                            }
                            for name in TYPES
                        ]
                    },
                )
            if config["relation_status"] != 200:
                return httpx.Response(
                    config["relation_status"], text="private upstream body"
                )
            source = DEPENDENT if f"/{DEPENDENT}/" in path else BLOCKER
            if request.method == "GET":
                if config["groups"] is not None:
                    return httpx.Response(200, json=config["groups"])
                groups = {name: [] for name in TYPES}
                if config["edge"]:
                    groups["blocked_by" if source == DEPENDENT else "blocking"] = [
                        {
                            "issue_id": BLOCKER if source == DEPENDENT else DEPENDENT,
                            "project_id": PID,
                        }
                    ]
                return httpx.Response(200, json=groups)
            body = json.loads(request.content)
            if config["mutation_status"] != 200:
                return httpx.Response(
                    config["mutation_status"], text="private upstream body"
                )
            assert source == DEPENDENT
            assert body["relation_type"] == "blocked_by"
            if request.method == "POST":
                assert body["issues"] == [BLOCKER]
                if config["create_conflict"]:
                    return httpx.Response(201, json=[])
                config["edge"] = True
                return httpx.Response(201, json=[{"id": BLOCKER, "project_id": PID}])
            assert request.method == "DELETE"
            assert body["related_issue"] == BLOCKER
            config["edge"] = False
            return httpx.Response(204)
        if path.endswith(f"/projects/{PID}/"):
            return httpx.Response(200, json={"id": PID, "identifier": "REL"})
        if "/work-items/" in path:
            iid = BLOCKER if path.endswith(("/REL-2/", f"/{BLOCKER}/")) else DEPENDENT
            return httpx.Response(
                config["source_status"],
                json={"id": iid, "project": {"id": PID, "identifier": "REL"}},
            )
        raise AssertionError(f"Unexpected request: {request.url}")

    real_client = httpx.AsyncClient
    monkeypatch.setattr(
        "sikku.server.httpx.AsyncClient",
        lambda **kw: real_client(transport=httpx.MockTransport(handler), **kw),
    )
    for key, value in {
        "PLANE_BASE_URL": "https://plane.invalid",
        "PLANE_WORKSPACE_SLUG": "wrong-default",
        "PLANE_API_KEY": "test-key",
        "SIKKU_MCP_TOKEN": "x" * 48,
        "SIKKU_ALLOWED_HOSTS": "testserver",
    }.items():
        monkeypatch.setenv(key, value)

    def call(client, action, **args):
        result = client.post(
            "/mcp/",
            headers={
                "Authorization": "Bearer " + "x" * 48,
                "Accept": "application/json, text/event-stream",
            },
            json={
                "jsonrpc": "2.0",
                "id": 1,
                "method": "tools/call",
                "params": {
                    "name": "workitem_relation",
                    "arguments": {
                        "workspace": "personal",
                        "issue": "REL-1",
                        "action": action,
                        **args,
                    },
                },
            },
        ).json()["result"]
        return result["isError"], json.loads(result["content"][0]["text"])

    return requests, config, call


def test_definitions_and_directed_lifecycle(relations_mcp):
    requests, config, call = relations_mcp
    with TestClient(create_app()) as client:
        failed, definitions = call(client, "list_definitions")
        assert not failed, definitions
        assert {row["relation_type"]: row["inverse"] for row in definitions["results"]}[
            "blocked_by"
        ] == "blocking"
        assert definitions["actions"] == ["list", "create", "delete"]
        failed, receipt = call(
            client, "create", relation_type="blocked_by", related_issue="REL-2"
        )
        assert not failed, receipt
        assert receipt["issue"] == DEPENDENT
        assert receipt["related_issue"] == BLOCKER
        assert call(client, "list")[1]["results"] == [
            {"relation_type": "blocked_by", "issue_id": BLOCKER, "project_id": PID}
        ]
        assert (
            call(client, "list", issue="REL-2")[1]["results"][0]["relation_type"]
            == "blocking"
        )
        assert not call(
            client, "delete", relation_type="blocked_by", related_issue="REL-2"
        )[0]
        assert call(client, "list")[1]["results"] == []
    assert not config["edge"]
    assert [
        request.method for request in requests if request.method in ("POST", "DELETE")
    ] == ["POST", "DELETE"]


@pytest.mark.parametrize("status", [404, 405, 501])
def test_legacy_definitions_fallback_and_unsupported_delete(relations_mcp, status):
    requests, config, call = relations_mcp
    config["options_status"] = status
    with TestClient(create_app()) as client:
        failed, definitions = call(client, "list_definitions")
        assert not failed, definitions
        assert definitions["source"] == "legacy_relations"
        assert "delete" not in definitions["actions"]
        failed, error = call(
            client, "delete", relation_type="blocked_by", related_issue="REL-2"
        )
        assert failed
        assert error["error"] == "unsupported"
    assert not any(request.method == "DELETE" for request in requests)


@pytest.mark.parametrize("status", [404, 405, 501])
def test_absent_relations_is_clear_unsupported(relations_mcp, status):
    _, config, call = relations_mcp
    config.update(options_status=405, relation_status=status)
    with TestClient(create_app()) as client:
        failed, error = call(client, "list_definitions")
    assert failed
    assert error["error"] == "unsupported"
    assert "private upstream body" not in json.dumps(error)


@pytest.mark.parametrize("status", [401, 403, 429, 500])
def test_capability_errors_are_not_hidden_by_fallback(relations_mcp, status):
    requests, config, call = relations_mcp
    config["options_status"] = status
    with TestClient(create_app()) as client:
        failed, error = call(client, "list_definitions")
    assert failed
    assert error["error"] == "plane_api_error"
    assert error["status"] == status
    assert not any(
        request.method == "GET" and request.url.path.endswith("/relations/")
        for request in requests
    )


def test_missing_issue_is_not_unsupported(relations_mcp):
    requests, config, call = relations_mcp
    config["source_status"] = 404
    with TestClient(create_app()) as client:
        failed, error = call(client, "list_definitions")
    assert failed
    assert error["error"] == "plane_api_error"
    assert not any(request.url.path.endswith("/relations/") for request in requests)


@pytest.mark.parametrize(
    "args",
    [
        {},
        {"relation_type": "blocked_by"},
        {"relation_type": "unknown", "related_issue": "REL-2"},
    ],
)
def test_invalid_mutation_is_rejected_before_plane(relations_mcp, args):
    requests, _, call = relations_mcp
    with TestClient(create_app()) as client:
        failed, error = call(client, "create", **args)
    assert failed
    assert error["error"] == "invalid_arguments"
    assert requests == []


@pytest.mark.parametrize("status", [400, 403, 404, 405, 429, 500])
def test_mutation_errors_are_not_retried(relations_mcp, status):
    requests, config, call = relations_mcp
    config["mutation_status"] = status
    with TestClient(create_app()) as client:
        failed, error = call(
            client, "delete", relation_type="blocked_by", related_issue="REL-2"
        )
    assert failed
    assert error["error"] == ("unsupported" if status == 405 else "plane_api_error")
    assert "private upstream body" not in json.dumps(error)
    assert len([request for request in requests if request.method == "DELETE"]) == 1


def test_create_conflict_is_not_a_success_receipt(relations_mcp):
    requests, config, call = relations_mcp
    config["create_conflict"] = True
    with TestClient(create_app()) as client:
        failed, error = call(
            client, "create", relation_type="blocked_by", related_issue="REL-2"
        )
    assert failed
    assert error["error"] == "relation_conflict"
    assert len([request for request in requests if request.method == "POST"]) == 1


def test_self_relation_never_writes(relations_mcp):
    requests, _, call = relations_mcp
    with TestClient(create_app()) as client:
        failed, error = call(
            client, "create", relation_type="blocked_by", related_issue="REL-1"
        )
    assert failed
    assert error["error"] == "invalid_relation"
    assert not any(request.method == "POST" for request in requests)


def test_legacy_create_uses_existing_public_route(relations_mcp):
    _, config, call = relations_mcp
    config["options_status"] = 405
    with TestClient(create_app()) as client:
        failed, receipt = call(
            client, "create", relation_type="blocked_by", related_issue="REL-2"
        )
    assert not failed, receipt
    assert config["edge"]


def test_relation_pagination_is_bounded_and_bound_to_source_and_filter(relations_mcp):
    _, config, call = relations_mcp
    refs = [{"issue_id": str(index), "project_id": PID} for index in range(3)]
    config["groups"] = {"blocked_by": refs}
    with TestClient(create_app()) as client:
        failed, first = call(client, "list", limit=2, relation_type="blocked_by")
        assert not failed, first
        assert len(first["results"]) == 2
        failed, second = call(
            client,
            "list",
            limit=2,
            relation_type="blocked_by",
            cursor=first["next_cursor"],
        )
        assert not failed, second
        assert second["results"][0]["issue_id"] == "2"
        assert second["next_cursor"] is None
        for changed in (
            {"issue": "REL-2", "relation_type": "blocked_by"},
            {"relation_type": "blocking"},
        ):
            failed, error = call(client, "list", cursor=first["next_cursor"], **changed)
            assert failed
            assert error["error"] == "invalid_cursor"
