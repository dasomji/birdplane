# Birdplane development

Birdplane is a pnpm/Turbo monorepo. `apps/web`, `apps/admin` (instance administration)
and `apps/space` (published projects) use React Router and Vite. `apps/live` provides
live collaboration. `apps/api` is Django with PostgreSQL, Redis/Valkey and Celery.
The separate Python package in `apps/mcp` exposes the API through MCP.

Use Node **>=22.18.0** and the `packageManager` version in root `package.json`
(currently **pnpm 11.10.0**, through Corepack). API CI uses Python **3.12**;
MCP requires Python **>=3.11** and has its own `uv.lock`. Use `uv sync --locked`
for MCP. Docker with Compose v2 and Buildx is required for isolated verification;
the current Docker context must be a development context on Coolify. Install
`uv`, and install workspace JavaScript dependencies with
`pnpm install --frozen-lockfile`. Playwright's Chromium requires the usual Linux
browser libraries; the verifier downloads a pinned browser if it is absent.
Keep at least **8 GiB** free on `/`; the verifier checks this before and during work.

## Isolated development stack

Run development and verification on Coolify. Never reuse deployment Compose,
production environment files, volumes, accounts or databases. The upstream
`setup.sh` writes `.env` files into the checkout and starts from shared service
names/ports; it is not the verification setup path.

The fork-owned `scripts/kitchen/verify-app/compose.yml` is a standalone definition.
It runs PostgreSQL 15.7, Valkey 7.2.11, the current Django source and one Celery
worker. Celery uses the disposable Valkey broker; RabbitMQ is unnecessary for
these journeys. PostgreSQL disables fsync/synchronous commit/full-page writes
for this disposable database; this harness does not test crash durability. The web app runs as a supervised local React Router development
process on an ephemeral loopback port. MCP runs as a Python stdio subprocess
through its real client/server protocol. No Tailscale or proxy configuration is
needed. Beat is omitted because these journeys do not depend on scheduled work.

Every invocation allocates a name containing the worktree hash and random run ID,
and creates private generated configuration under
`$HOME/.local/share/kitchen/verify-app/<run>/`. The database volume and network
are Compose-project scoped. The API image and Buildx builder also belong to that
run; cleanup removes both, including the builder's build cache. The API/worker image copies the current API source and the test settings
module; it never writes into the checkout. Database/media/runtime data stay
outside the checkout. Only evidence is written under ignored `.kitchen/`.

The runner does not inherit application configuration from the shell. It refuses
checkout `.env` and `.env.*` files (except templates ending in `.example`) in the
root, API, web and MCP directories before starting anything. Generated
`api.env` selects `plane.settings.kitchen_verify`, which checks the disposable project pattern,
database name/user/host and Redis host **before any Django database connection**.
The migration/seed processes use that same configuration. Unknown destinations
fail closed. Never change these guards to connect to production.

For an isolated boot, migration and seed, run:

```sh
node scripts/kitchen/verify-app.mjs --keep
```

This performs the same migrations and seeding as the verifier and retains its
owned services for debugging. It prints API/web origins and the exact cleanup
command. From the same worktree, inspect or rerun commands using the printed run
name; use the generated environment, never a checkout `.env`:

```sh
# Substitute the exact kitchen-verify-... name printed by this invocation.
run=kitchen-verify-WORKTREEHASH-RUNID
runtime="$HOME/.local/share/kitchen/verify-app/$run"
docker compose --env-file "$runtime/compose.env" -p "$run" \
  -f scripts/kitchen/verify-app/compose.yml logs --tail 100 api worker
docker compose --env-file "$runtime/compose.env" -p "$run" \
  -f scripts/kitchen/verify-app/compose.yml run --rm --no-deps api \
  python manage.py migrate --noinput
node scripts/kitchen/verify-app.mjs --cleanup "$run"
```

The automated initial seed command is `python manage.py shell < /verification/seed.py`
inside the API container. It requires an empty database and deliberately refuses
to reseed an existing DB. Seeded accounts are **admin@test.com** and
**user@test.com**, both with password **password**. These D12 accounts are for
disposable development/test databases only, **never production**. Both join the
`kitchen-test` workspace; the regular user initially joins only `Joined project`.
Generated API tokens stay in a private runtime file and are not printed.

## Functional verification

`pnpm verify:app` invokes `node scripts/kitchen/verify-app.mjs`. Run it after
`pnpm install --frozen-lockfile`. It uses a headless disposable stack instead of
a Lizardtail preview so empty-database migrations, test accounts and cleanup are
reproducible without host routing/ACL setup. Lizardtail remains an optional
follow-up for human try-it work; it is not required by this runner.

The verifier prints the full tested git SHA, each journey's result/duration,
evidence directory and exit code. Exit **0** means every journey and failure
case passed and requested cleanup succeeded; any failure returns nonzero.
It stops dependent journeys after the first failure and still attempts cleanup.
`results.json` records the SHA, dirty-tree indicator, timings and disk snapshots.
For a handoff receipt run at the committed SHA with a clean tracked tree.

Journeys use real browser, HTTP API and MCP boundaries:

1. Build the API environment, migrate an empty disposable database and seed D12.
2. Build web workspace dependencies and boot API/worker/web; install pinned Playwright and MCP's locked environment.
   Web readiness also launches the real browser and requires a visible login
   form after startup network activity settles, within the original 60-second
   budget. A same-origin Vite `504 Outdated Optimize Dep` triggers a fresh
   navigation within that budget: a rejected startup module can leave a blank
   document without loading the HMR client. Other blank pages fail without
   reloads. Existing build/route output is retained; no checkout artifacts are
   deleted to make verification pass. Readiness attempts and optimizer
   invalidations are recorded in `results.json`.
3. Reject an incorrect password through the browser and confirm unauthenticated
   app/public API requests return 401 or 403.
4. Sign in as `admin@test.com` through the web form and confirm the authenticated
   user and workspace page.
5. Create a private project through the authenticated app API (the public v1
   create schema does not accept `network`) and assert its actual default states:
   Backlog (default/backlog), Todo (unstarted), In Progress (started), Done
   (completed), Cancelled (cancelled). Internal Triage states are excluded by the
   API state manager. Record the returned state set.
6. Create a work item, move it to In Progress, check both matching and excluding
   PQL filters, and confirm the work item renders in the browser.
7. Check that `user@test.com` lists only its joined private project and cannot
   read work items in the unjoined private project.
8. Initialize the shipped MCP stdio server, discover its tools and call
   `list_issues`; the created work item must be present.

Screenshots, bounded sanitized service/build logs, resource snapshots and textual
results go to `.kitchen/evidence/verify-app/<full-sha>/<run>/`. Browser page errors
are retained in `browser-errors.log`; `browser-diagnostics.log` retains console
messages, failed requests and HTTP errors (bounded to the latest 500 entries of
2,000 characters per stream, with request query strings omitted). The last page's
HTML is saved as `last-page.html` alongside its screenshot. These local diagnostic
files are sanitized against the run's generated secrets; successful journey
assertions do not imply an error-free console. API tokens and
generated secrets are withheld/redacted; no production data is involved.
`--upload` requires `--ticket <ticket>` and an executable `evidence` on `PATH`;
both are checked before builds or services start. Optional `--pr <url>` associates
the upload with a GitHub PR. It uploads only the synthetic-data result summary
using `evidence put ... --ticket <ticket> --note ... --markdown`, printing returned
links. For example: `pnpm verify:app --upload --ticket <ticket> --pr <url>`. Visually review screenshots before uploading them separately with the same
`evidence put` command; raw logs/configuration are never uploaded. Evidence links expire; retain the textual result with the link.

`--keep` retains this run's services and private runtime data for debugging.
`--cleanup <run>` validates ownership and removes only that retained run.
Normal cleanup stops the owned web process group, removes the exact Compose
project's containers/volume/network, verifies empty resource-label queries,
removes its image/builder and runtime directory, and fails on cleanup errors.
Never run a generic `docker compose down -v` on shared names.

The runner executes real-Chromium browser readiness/diagnostic regression tests
as the named `browser startup regression tests` journey, using its pinned browser
install before cleanup. A failure fails the run; missing browser prerequisites
fail instead of silently skipping. L1/L2 kitchen tests exclude this one browser
suite and reject any skipped or todo tests in the remaining suites.

For focused L0 checks while a `--keep` runtime is retained:

```sh
VERIFY_BROWSER_PACKAGE="$runtime/browser/package.json" \
  node scripts/kitchen/run-tests.mjs scripts/kitchen/*.test.mjs scripts/kitchen/verify-app/*.test.mjs
```

Run this before cleaning up the retained runtime. Every test must pass with zero
skipped or todo tests.

This is a functional smoke, not full product coverage: it does not launch the
admin/space apps, live collaboration server, object storage/uploads, email,
scheduled recurrence/beat, MCP HTTP authentication/OAuth or layout audits.
Those need targeted verification when affected. See [verification](verify.md)
for the full repository gates; this command does not replace them.
