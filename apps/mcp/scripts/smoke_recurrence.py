"""Disposable live MCP check. Set MCP_URL, SIKKU_MCP_TOKEN, MCP_PROJECT.

Creates a template, pauses/resumes a schedule, waits for the real worker, reads
its generated ticket, edits/ends/deletes the schedule, and removes test tickets.
Never forces a scheduler run or changes database timestamps.
"""

import json
import os
import time
from datetime import UTC, datetime, timedelta

import httpx

url = os.environ["MCP_URL"]
project = os.environ["MCP_PROJECT"]
client = httpx.Client(
    timeout=40,
    headers={
        "Authorization": "Bearer " + os.environ["SIKKU_MCP_TOKEN"],
        "Accept": "application/json, text/event-stream",
    },
)
sequence = 0
calls = []


def rpc(method, params=None):
    global sequence
    sequence += 1
    response = client.post(
        url,
        json={
            "jsonrpc": "2.0",
            "id": sequence,
            "method": method,
            "params": params or {},
        },
    )
    response.raise_for_status()
    result = response.json()
    if "error" in result:
        raise RuntimeError(result["error"])
    return result["result"]


def call(name, **args):
    result = rpc("tools/call", {"name": name, "arguments": args})
    text = json.loads(next(c["text"] for c in result["content"] if c["type"] == "text"))
    if result.get("isError"):
        raise RuntimeError(text)
    calls.append(name)
    print(name, json.dumps(text), flush=True)
    return text


rpc(
    "initialize",
    {
        "protocolVersion": "2025-03-26",
        "capabilities": {},
        "clientInfo": {"name": "birdplane-recurrence-smoke", "version": "1"},
    },
)
schemas = rpc("tools/list")["tools"]
assert {"save_recurring_task", "list_recurring_tasks", "delete_recurring_task"} <= {
    t["name"] for t in schemas
}
print(
    "tools",
    len(schemas),
    "schema_bytes",
    len(json.dumps(schemas, separators=(",", ":")).encode()),
    flush=True,
)
ids = []
schedule_id = None
try:
    template = call(
        "save_issue",
        project=project,
        title="Birdplane recurrence smoke " + datetime.now(UTC).isoformat(),
        description="Recurring MCP smoke: snapshot body.",
        priority="low",
        start_date="2026-01-01",
        due_date="2026-01-03",
    )
    ids.append(template["id"])
    start = datetime.now(UTC) + timedelta(seconds=20)
    schedule = call(
        "save_recurring_task",
        project=project,
        template_issue=template["id"],
        frequency="daily",
        timezone="Europe/Vienna",
        starts_at=start.isoformat(),
        status="paused",
    )
    schedule_id = schedule["id"]
    time.sleep(25)
    paused = call("list_recurring_tasks", project=project, id=schedule_id)
    assert paused["last_issue"] is None and paused["status"] == "paused"
    call("save_recurring_task", project=project, id=schedule_id, status="active")
    deadline = time.monotonic() + 150
    while time.monotonic() < deadline:
        time.sleep(15)
        current = call("list_recurring_tasks", project=project, id=schedule_id)
        if current["last_issue"]:
            ids.append(current["last_issue"])
            break
    else:
        raise AssertionError("Worker did not generate an occurrence within 150 seconds")
    generated = call(
        "get_issue",
        project=project,
        id=ids[-1],
        fields=["title", "priority", "description", "start_date", "due_date"],
    )
    assert generated["priority"] == "low"
    assert "snapshot body" in generated["description"]["text"]
    assert (
        datetime.fromisoformat(generated["due_date"])
        - datetime.fromisoformat(generated["start_date"])
    ).days == 2
    next_start = datetime.now(UTC) + timedelta(days=2)
    edited = call(
        "save_recurring_task",
        project=project,
        id=schedule_id,
        frequency="weekly",
        interval=2,
        starts_at=next_start.isoformat(),
        ends_at=(next_start + timedelta(days=30)).isoformat(),
    )
    assert edited["frequency"] == "weekly" and edited["interval"] == 2
    ended = call("save_recurring_task", project=project, id=schedule_id, status="ended")
    assert ended["next_run_at"] is None
    call("delete_recurring_task", project=project, id=schedule_id)
    schedule_id = None
    call("get_issue", project=project, id=ids[-1], fields=["title"])
    print(
        "PASS: actual worker generation, snapshot, shifted dates, pause/resume, edit/end/delete; calls",
        len(calls),
        flush=True,
    )
finally:
    if schedule_id:
        current = call("list_recurring_tasks", project=project, id=schedule_id)
        if current.get("last_issue") and current["last_issue"] not in ids:
            ids.append(current["last_issue"])
        call("delete_recurring_task", project=project, id=schedule_id)
    for iid in reversed(ids):
        call("delete_issue", project=project, id=iid)
    client.close()
