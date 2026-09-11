import json

import httpx
import pytest

from sikku.plane import Plane, PlaneError, body_chunk, markdown

PID = "11111111-1111-4111-8111-111111111111"
IID = "22222222-2222-4222-8222-222222222222"


def client(handler):
    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


def test_ambiguous_names_fail_closed():
    with pytest.raises(PlaneError) as error:
        Plane.resolve(
            [{"id": "a", "name": "Done"}, {"id": "b", "name": "done"}], "DONE", "state"
        )
    assert error.value.payload["error"] == "ambiguous_name"


def test_html_is_escaped_and_chunks_reconstruct():
    assert "<script>" not in markdown("<script>alert(1)</script>")
    text = "a😀b" * 2000
    chunks = []
    offset = 0
    while True:
        chunk = body_chunk(text, offset, 500)
        chunks.append(chunk["text"])
        if "next_offset" not in chunk:
            break
        offset = chunk["next_offset"]
    assert "".join(chunks) == text


async def test_write_omission_and_explicit_null():
    written = []

    def handler(request):
        if request.method == "PATCH":
            written.append(json.loads(request.content))
            return httpx.Response(200, json={"id": IID, "name": "Existing"})
        return httpx.Response(
            200,
            json={
                "id": IID,
                "project": {"id": PID},
                "name": "Existing",
                "description_html": "keep me",
            },
        )

    async with client(handler) as c:
        p = Plane(c, "https://plane.test", "ws")
        await p.save_issue({"id": "TEST-1", "due_date": None, "assignees": []})
    assert written == [{"target_date": None, "assignees": []}]


async def test_name_failure_never_writes():
    calls = []

    def handler(request):
        calls.append(request.method)
        return httpx.Response(
            200, json={"results": [{"id": PID, "name": "Test", "identifier": "TEST"}]}
        )

    async with client(handler) as c:
        p = Plane(c, "https://plane.test", "ws")
        with pytest.raises(PlaneError):
            await p.save_issue({"project": "missing", "title": "test"})
    assert calls == ["GET"]


async def test_rate_limit_does_not_retry_mutations_or_echo_body():
    calls = []

    def handler(request):
        calls.append(request.method)
        return httpx.Response(
            429, json={"secret": "never return this"}, headers={"retry-after": "10"}
        )

    async with client(handler) as c:
        with pytest.raises(PlaneError) as err:
            await Plane(c, "https://plane.test", "ws").request(
                "POST", "work-items", json={}
            )
    assert calls == ["POST"]
    assert err.value.payload["retry_after_seconds"] == 10
    assert "secret" not in json.dumps(err.value.payload)


async def test_filtered_pagination_keeps_matches_and_stops_scanning():
    def handler(request):
        if request.url.path.endswith("/projects-lite/"):
            return httpx.Response(200, json={"results": [{"id": PID}]})
        assert "pql" not in request.url.params
        page = int(request.url.params.get("cursor", "0"))
        rows = [
            {
                "id": str(page * 100 + i),
                "name": "needle" if i in [5, 90] else "hay",
                "project": {"id": PID, "identifier": "TEST"},
                "sequence_id": page * 100 + i,
            }
            for i in range(100)
        ]
        return httpx.Response(
            200,
            json={
                "results": rows,
                "next_page_results": page < 1,
                "next_cursor": str(page + 1),
            },
        )

    async with client(handler) as c:
        p = Plane(c, "https://plane.test", "ws")
        cursor = None
        found = []
        while True:
            args = {"query": "needle", "limit": 1}
            if cursor:
                args["cursor"] = cursor
            result = await p.list_issues(args)
            found.extend(r["id"] for r in result["results"])
            cursor = result["next_cursor"]
            if not cursor:
                break
        assert found == ["5", "90", "105", "190"]


async def test_scan_limit_returns_continuation_even_when_no_matches():
    requests = []

    def handler(request):
        if request.url.path.endswith("/projects-lite/"):
            return httpx.Response(200, json={"results": [{"id": PID}]})
        page = int(request.url.params.get("cursor", "0"))
        requests.append(page)
        return httpx.Response(
            200,
            json={
                "results": [{"id": str(page), "name": "hay"}],
                "next_page_results": True,
                "next_cursor": str(page + 1),
            },
        )

    async with client(handler) as c:
        result = await Plane(c, "https://plane.test", "ws").list_issues(
            {"query": "needle"}
        )
    assert result["scan_limited"] and result["next_cursor"]
    assert requests == [0, 1, 2, 3, 4]


async def test_cursor_filter_mismatch():
    async with client(
        lambda r: httpx.Response(
            200,
            json={"results": [{"id": "1", "name": "one"}, {"id": "2", "name": "two"}]},
        )
    ) as c:
        p = Plane(c, "https://plane.test", "ws")
        page = await p.list_issues({"limit": 1})
        with pytest.raises(PlaneError) as err:
            await p.list_issues(
                {"limit": 1, "query": "changed", "cursor": page["next_cursor"]}
            )
        assert err.value.payload["error"] == "invalid_cursor"


async def test_project_description_continuation():
    async with client(
        lambda r: httpx.Response(
            200, json={"id": PID, "description": "a" * 4000 + "tail"}
        )
    ) as c:
        p = Plane(c, "https://plane.test", "ws")
        first = await p.dispatch("get_project", {"project": PID})
        last = await p.dispatch(
            "get_project",
            {"project": PID, "description_offset": first["description"]["next_offset"]},
        )
        assert last["description"]["text"] == "tail"


async def test_recurring_task_resolves_template_and_preserves_omissions():
    calls = []

    def handler(request):
        calls.append(
            (
                request.method,
                request.url.path,
                json.loads(request.content) if request.content else None,
            )
        )
        if request.method == "POST":
            return httpx.Response(201, json={"id": IID, "status": "active"})
        if request.method == "PATCH":
            return httpx.Response(200, json={"id": IID, "status": "paused"})
        if request.method == "DELETE":
            return httpx.Response(204)
        if request.url.path.endswith(f"/projects/{PID}/"):
            return httpx.Response(
                200, json={"id": PID, "name": "Test", "identifier": "TEST"}
            )
        if "projects-lite" in request.url.path:
            return httpx.Response(
                200, json=[{"id": PID, "name": "Test", "identifier": "TEST"}]
            )
        return httpx.Response(200, json={"id": IID, "project": PID})

    async with client(handler) as c:
        p = Plane(c, "https://plane.test", "ws")
        await p.dispatch(
            "save_recurring_task",
            {
                "project": "TEST",
                "template_issue": "TEST-1",
                "frequency": "weekly",
                "starts_at": "2030-01-01T09:00:00Z",
            },
        )
        await p.dispatch(
            "save_recurring_task", {"project": "TEST", "id": IID, "status": "paused"}
        )
        await p.dispatch("delete_recurring_task", {"project": "TEST", "id": IID})
    writes = [x for x in calls if x[0] in ("POST", "PATCH", "DELETE")]
    assert writes[0][2]["template_issue"] == IID
    assert writes[1][2] == {"status": "paused"}
    assert writes[2][1].endswith(f"/recurring-tasks/{IID}/")
