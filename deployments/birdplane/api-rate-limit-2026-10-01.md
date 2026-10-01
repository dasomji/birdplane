# BIRD-25: API key rate limit deployment

On 2026-10-01, the existing Coolify Birdplane service
`hnslaatmrmfginhfa1kemiam` was updated from `60/minute` to `300/minute`
per API key. The `api`, `worker`, `beat-worker`, and `migrator` environment
values match in both saved and generated Compose configuration.

## Configuration and rollout

The raw Compose patch changes exactly those four values. The generated Compose
also refreshes Coolify's own version labels from `4.3.21` to `4.3.23`; after
excluding those labels and the four rate values, it matches the previous
configuration. The service, application, database, server, environment, and
destination identities, named volumes, credentials, routes, and images were
preserved. Backend images remain
`birdplane-backend:0510b75a043c291cb6a4be700aca160dba0858e4`; web remains
`birdplane-web:74965ca1faa7c034dc4b79317cc4253105bff121`.

The configuration was saved and read back before deploying the same service
through `POST /api/v1/deploy`. The rollout was requested at 09:31 UTC and the
service returned to `running:unknown` by 09:35 UTC, its baseline status for
containers without health checks. The one-shot migrator is exited as expected;
the long-running applications and database are running.

Private configuration snapshots and data backups are stored under
`/home/dev/.local/state/birdplane/BIRD-25-20261001/` on the operations host.
No secrets or backup payloads are included in this repository. The PostgreSQL
custom-format dump was exported in chunks to avoid Coolify's output truncation
and restored with `pg_restore --exit-on-error` into a separate temporary database.
All six uploaded objects were archived and checksum-verified. SHA-256 checksums:

| Backup          | SHA-256                                                            |
| --------------- | ------------------------------------------------------------------ |
| `database.dump` | `88ea4e2b744131e9b4518725066133c004cd5791dd47de49fb244f0ba1317c3a` |
| `uploads.zip`   | `a049ae6eac0b717c1fa198ad38367b4fb035abc8c5c98c58e75422902e2431bb` |

## Verification

- `./setup.sh` completed successfully.
- Three API pytest unit tests passed: the 300-request allowance and retry wait,
  independent key allowances, and expiry at the 60-second boundary. They ran
  through `docker-compose-test.yml` using an existing compatible test image,
  without starting database dependencies for these cache-only tests:
  `docker compose -p bird25-tests -f docker-compose-test.yml run --rm --no-deps api-tests pytest plane/tests/unit/api/test_rate_limit.py`.
- The [runtime verifier](verify-api-rate-limit.py) passed inside the recreated
  production API container. The actual Django setting and loaded throttle both
  read `300/minute`; the parsed allowance is 300 requests per 60 seconds.
  Synthetic request 301 was rejected with a 60-second wait; another key retained
  its allowance, and the first key recovered at expiry. Remaining-request headers
  were checked after every allowed request. An isolated process-local cache was
  used, with zero production HTTP requests or Redis-history changes.
- Runtime environment checks in both worker containers read `300/minute`.
  The migrator's saved/generated environment also reads `300/minute`.
- Public UI, `/api/instances/`, and `/mcp/healthz` returned HTTP 200. MCP health
  reported `status: ok`, and Coolify reported the MCP application healthy.
- Three concurrent authenticated MCP reads passed, including an In Progress
  filter resolved on the server. Repeating this run's original Clockwork claim
  command after rollout succeeded at 09:37 UTC, retaining the same ownership.
- The Clockwork poll during recreation at 09:35 UTC was degraded by transient
  HTTP 503 responses. Five subsequent rounds from 09:36 through 09:40 UTC
  covered all 11 projects with zero errors. API logs sampled after restart contained no HTTP 429 or
  throttling events during normal polling and concurrent MCP reads. This is
  bounded operational evidence, not a production saturation test.
- Workspace and project ID checksums matched before and after deployment.
  All 194 pre-existing issue IDs also matched. The issue count increased to 195
  because BIRD-26 was independently created at 09:37 UTC.
- Ruff lint/format, YAML formatting, and `git diff --check` passed. Compose
  rendering confirmed `300/minute` on all four backend services and the
  `60/minute` rollback override.
- Temporary Coolify verification schedules, container scratch files, the local
  restore container, and the test network were removed. The existing diagnostic
  schedule was retained; private backups remain available.

Clockwork's metadata cache, server-side filtering, and Retry-After backoff were
left in place. The production change requires no application code or schema
migration.

## Rollback

Change only `API_KEY_RATE_LIMIT` back to `60/minute` in the four backend
environments, read back the saved/generated Compose, and redeploy
`hnslaatmrmfginhfa1kemiam`. For future overlay rendering, explicitly set
`API_KEY_RATE_LIMIT=60/minute`. Run the verifier with `--expect 60/minute`, then
check API/MCP health and normal polling. Preserve the same images, identities,
credentials, and volumes. Do not restore an older database over live writes for
a rate-only rollback.
