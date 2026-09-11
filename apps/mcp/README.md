# Birdplane MCP (Sikku)

A compact Plane MCP server. It accepts project names, ticket identifiers, and
member/state/label names, resolves UUIDs internally, and returns bounded results.
Part of [Birdplane](../../BIRDPLANE.md), licensed under [AGPL-3.0](../../LICENSE.txt).

## Run

```sh
uv sync --frozen
# Set PLANE_BASE_URL, PLANE_WORKSPACE_SLUG and PLANE_API_KEY.
uv run sikku                 # stdio
uv run sikku --http          # Streamable HTTP: /mcp/, health: /healthz
```

HTTP requires `SIKKU_MCP_TOKEN` (at least 32 random characters) and
`SIKKU_ALLOWED_HOSTS` (comma-separated hostnames). Clients send
`Authorization: Bearer <token>`. Use HTTPS in production. This is a single-workspace
integration with the configured Plane account's permissions, without multi-user OAuth.
Existing Sikku environment variables and client configurations remain compatible.

## Tools

`list_projects`, `get_project`, `list_issues`, `get_issue`, `save_issue`,
`delete_issue`, `list_metadata`, `list_comments`, `get_comment`, `save_comment`.

Create with `save_issue(project="My project", title="Example", state="Todo")`;
update with `save_issue(id="PROJ-1", priority="high")`.
Omitted fields remain unchanged. Empty lists clear labels/assignees; null clears
parent/dates. Markdown descriptions render with embedded HTML disabled.
Ambiguous names fail before writing. Mutations are not automatically retried.

Lists default to 10 results, maximum 50; descriptions are omitted by default.
Detail bodies default to 4,000 characters with continuation offsets. Responses
use a single text JSON representation, avoiding duplicate payloads.

Community Edition search scans project pages internally, at most 500 tickets per
call. Follow `next_cursor` with identical arguments when `scan_limited=true`, even
if the result is empty. Pagination is live rather than a snapshot. Project-list
changes invalidate workspace cursors. Commercial-only operations and archive
workflows are outside this server's scope.

## Verify and build

```sh
uv run pytest -q
uv run ruff check sikku tests
docker build -t birdplane-mcp .
```

After dependency changes, update the lock and regenerate production requirements:
`uv export --frozen --no-dev --no-emit-project -o requirements.txt`.
Credentials, deployment snapshots, and live test output belong outside this repository.

### Recurring tasks (Birdplane)

Use `save_issue` to create a template, then `save_recurring_task` with `project`,
`template_issue` (for example `BIRD-1`), `frequency`, `starts_at` (an ISO timestamp
with UTC offset), and an IANA `timezone`. Supported frequencies: daily, weekly,
monthly, yearly; `interval` defaults to 1. The template is a saved snapshot.
Use `list_recurring_tasks` to inspect schedules and their last generated ticket.
Use `save_recurring_task` with `id` to edit, pause/resume, or end a schedule;
`delete_recurring_task` removes the schedule and keeps generated tickets.
See [recurrence semantics](../../deployments/birdplane/recurrence.md).
