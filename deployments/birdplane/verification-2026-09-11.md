# Recurrence rollout verification — 2026-09-11

Runtime source: `af589ea213eae05ca45882934ee526356ef5320a`.
Upstream stable baseline: v1.4.2, also the current upstream master at verification.

- 7 backend tests passed against PostgreSQL, including concurrent workers,
  transaction rollback, pause/resume/end, permissions, CSRF, DST, and month ends.
- 11 MCP tests passed; lint passed.
- A fresh production database backup restored successfully into an isolated
  database. The additive recurrence migration applied; no missing migrations.
- Browser creation, pause, edit, and 390px viewport checks passed against the
  isolated restored database. Test containers and their data were removed.
- GitHub MCP and recurrence workflows passed for the deployed commit.
- Coolify backend and MCP deployments completed. Home page, instance API,
  recurrence page and MCP health endpoint returned HTTP 200.
- Live MCP exposed 13 tools, totaling 9,589 bytes of JSON tool schema.
- Live smoke used only MCP calls for ticket/schedule operations and waited for
  the real Celery worker: template BIRD-18 → generated occurrence BIRD-19.
  Verified paused schedules stay idle, resume generates automatically, copied
  content/priority and a two-day shifted due date, timing edits, final ending,
  and deletion preserving the generated ticket.
- The test schedule and both tickets were removed; empty schedule list and
  missing tickets were confirmed through MCP. BIRD-15 is Done.

Private backups, credentials, deployment configuration and raw smoke logs are
kept outside this public repository. The existing Coolify service identity,
volumes, environment, hostname, and MCP bearer configuration were retained.
