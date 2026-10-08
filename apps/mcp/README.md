# Birdplane MCP (Sikku)

A compact Plane MCP server. It accepts project names, ticket identifiers, and
member/state/label names, resolves UUIDs internally, and returns bounded results.
Part of [Birdplane](../../BIRDPLANE.md), licensed under [AGPL-3.0](../../LICENSE.txt).

## Run

```sh
uv sync --frozen
# Set PLANE_BASE_URL and PLANE_API_KEY.
# Optionally set PLANE_WORKSPACE_SLUG as the default workspace.
uv run sikku                 # stdio
uv run sikku --http          # Streamable HTTP: /mcp/, health: /healthz
```

HTTP requires `SIKKU_MCP_TOKEN` (at least 32 random characters) and
`SIKKU_ALLOWED_HOSTS` (comma-separated hostnames). Clients send
`Authorization: Bearer <token>`. Use HTTPS in production. This integration can access
all workspaces available to the configured Plane account, without multi-user OAuth.
Everyone holding the MCP bearer token uses that account's permissions.
Existing Sikku environment variables and client configurations remain compatible.

Call `list_workspaces()` to discover workspace IDs, names and slugs. It accepts
`query` (name or slug), `limit` (default 10, maximum 50) and `cursor`. Its response
also identifies `default_workspace`, or null when none is configured.
Every other tool accepts an optional `workspace` slug:

```python
list_projects(workspace="audiopoesis")
save_issue(workspace="personal", project="TODO", title="Book appointment")
```

Use the actual slugs returned by discovery. Selection applies only to that call;
there is no shared switch-workspace state. Omitted workspace uses
`PLANE_WORKSPACE_SLUG`; without a default, tools require an explicit workspace.
Searches operate within one workspace per call. To search across workspaces,
discover them and call `list_issues` for each. Keep the workspace unchanged when
following pagination cursors. Existing cursors should be restarted after upgrading.

Discovery requires Birdplane's `GET /api/v1/workspaces/` endpoint: deploy the API
and MCP changes together (API first). The endpoint returns only active, undeleted
memberships and workspaces; project operations retain their existing permissions.
Reconnect MCP clients after upgrading to refresh the tool schemas.

## Tools

### AI agent assignment

Instance admins create profiles under **AI agents** in admin settings. Each
profile has a creator, optional colleagues allowed to assign it, and selected
workspaces/projects. Only the creator can assign a new profile by default.
An assignment grant does not grant access to a workspace or project. The API
enforces assignment permissions using the account behind the API key; MCP has
the same permissions as that account.

```python
list_metadata(workspace="personal", project="BIRD", kind="agents")
save_issue(workspace="personal", id="BIRD-30", agent="My coding agent")
list_issues(workspace="personal", project="BIRD", agent="<agent UUID>",
            fields=["title", "state", "agent", "labels"])
save_issue(workspace="personal", id="BIRD-30", agent=None)
```

Assigning an agent clears human assignees. To switch back to humans, pass
`agent=None` and `assignees=[...]` together, or remove the agent first. Replacing
or removing an agent requires permission for the currently assigned profile.
Use the agent UUID for scripts; duplicate names require UUIDs. Agent filtering
runs on the API before pagination. Disabled profiles and assignments outside
the profile's current scopes are excluded from an agent-filtered queue.

Direct API clients use `agent_id` on work-item create/update requests and
`?agent_id=<UUID>` on project work-item lists. Discover profiles through
`GET /api/v1/workspaces/<slug>/projects/<UUID>/agents/`.

Assignment is independent of readiness. External runners can combine it with
states or labels; Birdplane does not execute agents or start automations. Deploy
the API migration and UI changes alongside the MCP update, then reconnect MCP
clients to refresh their schemas.

### Bundled agent guidance

The server ships its [project-management skill](sikku/skills/plane-project-management/SKILL.md)
inside the Python package and Docker image. Its body is sent in MCP initialization
`instructions` on every connection; the complete file is also available through
`resources/list` and `resources/read` at
`birdplane://skills/plane-project-management`. No separate local skill installation
is required. Clients must expose MCP server instructions or resources to their agent.

The guidance tells agents to persist verified workspace and project identifiers
in the repository's root `AGENTS.md`, use the workspace explicitly on every call,
and resolve ambiguity with the user. The agent writes that configuration using
its host's filesystem capabilities; the MCP server itself does not edit client files.

### Available tools

`list_workspaces`, `create_project`, `list_projects`, `get_project`, `create_label`,
`list_issues`, `get_issue`, `save_issue`,
`delete_issue`, `list_metadata`, `list_comments`, `get_comment`, `save_comment`,
`list_recurring_tasks`, `save_recurring_task`, `delete_recurring_task`,
`workitem_relation`.

Create a project with `create_project(name="My project", identifier="APP")`.
Create a label with `create_label(project="APP", name="Bug", color="#EF4444")`.
Project descriptions are plain text; project timezone and label descriptions are
optional. Ticket prefixes are uppercased. Duplicate names/prefixes and permission
errors are reported without retrying the write. Labels can then be assigned by
name with `save_issue(project="APP", title="Example", labels=["Bug"])`.

Create with `save_issue(project="My project", title="Example", state="Todo")`;
update with `save_issue(id="PROJ-1", priority="high")`.
Omitted fields remain unchanged. Empty lists clear labels/assignees; null clears
parent/dates. Markdown descriptions render with embedded HTML disabled.
Ambiguous names fail before writing. Mutations are not automatically retried.

Lists default to 10 results, maximum 50; descriptions are omitted by default.
Detail bodies default to 4,000 characters with continuation offsets. Responses
use a single text JSON representation, avoiding duplicate payloads.

Birdplane supports server-side `filters` on `list_issues`, with `is`, `is_not`,
and `is_empty` operators. Names resolve internally; conditions combine with AND.
See [filter examples and semantics](../../deployments/birdplane/filters.md).

`list_issues` also accepts relative-date PQL, alone or alongside `filters`. For
example, use `pql="createdAt >= daysAgo(7)"` or
`pql="dueDate < today() AND priority IN (High, Urgent)"`. Calendar functions
such as `today()`, `daysAgo()`, and `startOfWeek()` use the requesting user's
timezone and calendar boundaries. `hoursAgo()` and `hoursFromNow()` are rolling
timestamp windows supported only for `createdAt` and `updatedAt`. Follow
`next_cursor` with the identical PQL and other arguments.
See the [full supported PQL syntax](../api/plane/utils/filters/README.md).

Legacy scalar search arguments scan project pages internally, at most 500 tickets per
call. Follow `next_cursor` with identical arguments when `scan_limited=true`, even
if the result is empty. Pagination is live rather than a snapshot. Project-list
changes invalidate workspace cursors. Commercial-only operations and archive
workflows are outside this server's scope.

### Work item relations

`workitem_relation` supports `list_definitions`, `list`, `create`, and `delete`.
Every action requires an existing `issue` (identifier or UUID plus `project`),
so capability discovery runs within the caller's actual permissions:

```python
workitem_relation(workspace="personal", issue="APP-1", action="list_definitions")
workitem_relation(workspace="personal", issue="APP-1", action="create",
                  relation_type="blocked_by", related_issue="APP-2")
workitem_relation(workspace="personal", issue="APP-2", action="list")
workitem_relation(workspace="personal", issue="APP-1", action="delete",
                  relation_type="blocked_by", related_issue="APP-2")
```

Here APP-1 depends on APP-2; APP-2 lists the inverse `blocking` relation.
Deletion specifies the type and direction, preserving unrelated edges. Related
identifiers can refer to another accessible project in the same workspace;
related UUIDs default to the source project, or use `related_project` explicitly.
Self-relations are rejected. Lists are bounded with `limit`/`cursor` and an optional
`relation_type` filter; retain workspace, issue and filter when continuing.

The supported API is `/api/v1/workspaces/{slug}/projects/{project_id}/work-items/{issue_id}/relations/`.
Birdplane exposes definitions and inverse names through authenticated `OPTIONS`,
and supported methods through `Allow`. It adds directed `DELETE` with a JSON body
containing `relation_type` and `related_issue`; `POST` uses `relation_type` and
`issues`. Deploy the API before the MCP and reconnect clients to refresh tools.

On older Plane servers, discovery falls back to the keys returned by `GET` on
this route, using `Allow` to detect write support. It does not call a separate
commercial/version-specific definitions endpoint or use browser-session APIs.
If the route or action is absent, the tool returns `error="unsupported"` with a
description/UI workaround. Authentication, permission, rate-limit and server
errors remain errors; writes are never automatically retried. A missing ticket
or missing edge retains its resource error. Definitions describe API support,
while individual writes still enforce the caller's permissions.

## Verify and build

```sh
uv run pytest -q
uv run ruff check sikku tests
docker build -t birdplane-mcp .
```

After dependency changes, update the lock and regenerate production requirements:
`uv export --frozen --no-dev --no-emit-project -o requirements.txt`.
Credentials, deployment snapshots, and live test output belong outside this repository.

For an isolated local API with a disposable project, run the real MCP/API
integration smoke test (it creates and cleans up two tickets):

```sh
PLANE_BASE_URL=http://127.0.0.1:8000 PLANE_API_KEY=local-test-key \
PLANE_WORKSPACE_SLUG=test SIKKU_TEST_PROJECT=PROJECT_UUID \
uv run python scripts/smoke_relations.py
```

The backend regression suite is
`plane/tests/contract/api/test_work_item_relations.py`. It covers discovery,
directed and inverse deletion, validation and permission/project isolation.

### Recurring tasks (Birdplane)

Use `save_issue` to create a template, then `save_recurring_task` with `project`,
`template_issue` (for example `BIRD-1`), `frequency`, `starts_at` (an ISO timestamp
with UTC offset), and an IANA `timezone`. Supported frequencies: daily, weekly,
monthly, yearly; `interval` defaults to 1. The template is a saved snapshot.
Use `list_recurring_tasks` to inspect schedules and their last generated ticket.
Use `save_recurring_task` with `id` to edit, pause/resume, or end a schedule;
`delete_recurring_task` removes the schedule and keeps generated tickets.
See [recurrence semantics](../../deployments/birdplane/recurrence.md).
