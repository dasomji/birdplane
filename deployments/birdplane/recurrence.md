# Recurring tasks

Birdplane adds recurrence in `apps/api/plane/recurrence`, with its own tables and
migration. Only Django app registration, URL inclusion, and Celery configuration
extend upstream files. Plane's latest stable baseline remains v1.4.2 (upstream
master was checked on 2026-09-10).

## Use

Open `/api/birdplane/recurring/` on your Plane instance after signing in. Enter
the workspace slug, choose a project, and choose a template ticket. The page
supports creation, editing, pausing, resuming, ending, and deleting schedules.
Project and template pickers return at most 100 projects and 50 matching tickets;
search the ticket title to narrow matches. The MCP accepts any project name/UUID
and ticket identifier accessible to its configured account.

MCP example:

```json
{
  "project": "Birdplane",
  "template_issue": "BIRD-1",
  "frequency": "weekly",
  "interval": 1,
  "timezone": "Europe/Vienna",
  "starts_at": "2027-01-04T09:00:00+01:00"
}
```

Pass that to `save_recurring_task`. Read with `list_recurring_tasks`; update with
`save_recurring_task` plus schedule `id`; remove with `delete_recurring_task`.
Creation requires a future first run. Changing timing requires a future first
run too. Omitted fields remain unchanged; `ends_at: null` clears the end.

## Semantics

- A schedule snapshots the template's title, HTML description, priority, state,
  assignees, labels, and duration between start and due dates. Each occurrence
  starts on its scheduled local date; its due date shifts by that duration.
  Without both template dates, no due date is assigned. Subtasks, attachments,
  comments, cycles, modules, and parent links are not copied.
- Completed/cancelled or removed template states fall back to an open project
  state. Removed labels/assignees are omitted. Later edits/deletion of the
  original template do not affect the snapshot. Selecting a template again
  while editing explicitly refreshes it.
- Daily/weekly/monthly/yearly intervals follow local wall time. Month ends clamp
  without drifting (Jan 31 → Feb 28 → Mar 31). Leap years work likewise.
  DST gaps shift forward by the gap; repeated local times run once, at the first
  occurrence.
- Celery beat checks every minute. A database transaction locks each schedule,
  creates its ticket and unique occurrence record, and advances the schedule
  together. Concurrent workers/retries cannot create duplicate occurrences.
- Downtime/resuming a paused schedule coalesces missed runs into one ticket for
  the latest scheduled time at or before now (and at or before the inclusive
  end). It never creates an unbounded backlog. Ending is final; create a new
  schedule to restart. Deleting a schedule preserves generated tickets.
- Only active workspace/project members or admins can manage schedules. The
  worker rechecks the creator's access; revoked access or archived/deleted
  projects pause generation. The UI uses session authentication with CSRF;
  API clients use Plane API keys and the existing throttle.

## Deployment and testing

Build the backend and MCP from the same reviewed Birdplane commit. The existing
migrator applies `recurrence/0001_initial`; restart API, worker and beat together.
The migration only creates new tables. Rolling back code can leave these tables
in place; never restore an old database over newer user work.

Local isolated tests (first build the image from `apps/api/Dockerfile.api`):

```sh
docker build -t birdplane-backend:verify -f apps/api/Dockerfile.api apps/api
docker compose -p birdplane-recurrence-tests -f deployments/birdplane/recurrence-test.yml up -d redis
docker compose -p birdplane-recurrence-tests -f deployments/birdplane/recurrence-test.yml run --rm tests
docker compose -p birdplane-recurrence-tests -f deployments/birdplane/recurrence-test.yml down -v
cd apps/mcp && uv run pytest && uv run ruff check .
```

Live verification must use disposable templates/schedules, wait for the actual
Celery worker to generate a ticket, read the ticket through MCP, exercise
pause/resume/edit/end, and delete the schedules and disposable tickets afterwards.
