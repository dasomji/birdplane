# Filter rollout verification — 2026-09-11

Deployed source: `25fb2eabda311268836a4352d77f1edeab29d6ef` for backend, web, and MCP.

## Automated checks

- 17 backend tests passed with real migrations in an isolated PostgreSQL/Valkey stack, covering filters, date regressions, and recurring tasks.
- 25 MCP tests passed, including name resolution, validation, and upstream filter serialization.
- Two frontend state tests passed: operator transitions, immediate empty-filter application, and saved-filter round trips.
- TypeScript checks passed for web, shared-state, utils, and types.
- Changed frontend files passed lint/format checks; MCP passed Ruff checks.
- Production web build and Docker image build passed.
- GitHub checks passed: [UI](https://github.com/dasomji/birdplane/actions/runs/34550686492), [MCP](https://github.com/dasomji/birdplane/actions/runs/34550686524), [backend/recurrence](https://github.com/dasomji/birdplane/actions/runs/34550686441).

The first combined migration run encountered a reused test database previously created without migrations. The isolated runner now explicitly recreates its test database; the full migration-backed rerun passed. Production was unaffected.

## Browser verification

Restored the pre-deployment database backup into an isolated local stack and served the production web image. A local-only label assignment provided matching and nonmatching tickets.

- Operator dropdown offered `is`, `is not`, and `is empty`.
- `is empty` applied without a value picker, returned only unlabeled tickets, and persisted after reload.
- `is not` excluded the labeled ticket; the network request used `label_id__not_in` and returned HTTP 200.
- Switching to `is` retained the chosen label and returned only its matching ticket.
- The positive filter also persisted after reload.
- Removed the browser tab, temporary session file, containers, and restored data copy afterward.

## Deployment and live MCP

Verified the pre-deployment PostgreSQL dump (1,056,302 bytes) and restored it locally. The Coolify update preserved service identities, all named volumes, environments, and volume mounts. No new database migration was required.

Coolify service is running; MCP deployment `wb8lik6enf3xk1zaxj41km6v` finished and is healthy. The live structured-filter API returned HTTP 200. All 32 deployed web entry assets matched the browser-tested production image, excluding the generated per-build manifest ID.

Used authenticated JSON-RPC against the deployed `/mcp/` endpoint, including initialization and tool discovery. Created one disposable project, two labels, and three tickets through MCP. Fourteen checks passed:

1. Label inclusion.
2. Inclusion of any selected label.
3. Exclusion of a label on a ticket with multiple labels.
4. Exclusion of every selected label.
5. Empty labels.
6. Empty assignees.
7. Assignee exclusion using `me`.
8. Empty priority (`none`).
9. Empty due date.
10. Date equality.
11. Date inequality, including undated tickets.
12. Combined AND conditions.
13. Filtered cursor pagination without duplicates or missing matches.
14. Updated label assignments immediately changing empty-filter results.

Deleted the disposable tickets through MCP and removed their labels/project; a follow-up project read returned 404. No fixture remains active.

The tool catalog remains at **15 tools**, totaling **11,707 bytes** of compact JSON (720 bytes above the previous catalog). Filter result payloads in this test were 271–510 bytes. Across 27 MCP requests, median response time was **0.35 seconds**, excluding deliberate pacing for upstream rate limits. These small-fixture measurements are a smoke test, not a large-workspace performance benchmark.

Credentials, raw test output, configuration snapshots, and the database backup remain outside the public repository. Existing MCP endpoint and authentication are unchanged; clients that cache tool schemas may need to reconnect.
