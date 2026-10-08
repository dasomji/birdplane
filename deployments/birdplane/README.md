# Birdplane on an existing Coolify Plane stack

For Git-connected Compose and automatic deployment from the `birdplane` release
branch, use [the Git deployment guide](git-compose.md) and [compose.yml](compose.yml).
The instructions below describe the original manually pinned Compose Service
and its rollback configuration.

For upstream Plane version updates, complete the
[upstream update checklist](upstream-update-checklist.md) before rollout,
including review and retirement of temporary local fixes.

Preserve the existing Coolify service UUID, Compose service names, named volumes,
database credentials, application secrets, object storage configuration and domain.
Changing a service UUID can silently create empty volumes. Never run `down -v`.

Before rollout, save the current Coolify service configuration privately, take a
PostgreSQL custom-format dump, verify a restore into a separate temporary database,
and back up object storage. Record volume names and existing project/ticket IDs.
Follow [backup transfer and verification](backups.md) for complete file transfers
and notification-aware manual checks.

For the backend, set all four services (`api`, `worker`, `beat-worker`, `migrator`)
to the same local image tag, e.g. `birdplane-backend:COMMIT`, with
`pull_policy: never`. Add the following build definition to `api`:

```yaml
build:
  context: https://github.com/dasomji/birdplane.git#COMMIT:apps/api
  dockerfile: Dockerfile.api
```

Replace COMMIT with a full reviewed commit SHA. A reusable Compose overlay is
provided in [`backend.override.yml`](backend.override.yml). Render variables
before saving the merged configuration in Coolify.

For an already running service, use Coolify's `POST /api/v1/deploy` with its
existing service UUID. This builds the image before recreating containers.
The `/services/{uuid}/start` endpoint rejects services that are already running;
the restart endpoint can stop containers before the build finishes.
Build `web` from the same pinned commit using `apps/web/Dockerfile.web` and the
repository root as build context; use `birdplane-web:COMMIT` with `pull_policy: never`.
The overlay includes this definition. Keep admin/space/live/proxy images at
`makeplane/plane-*:v1.4.2`. The filter additions introduce no database migration;
recurring tasks have their own additive migration.

The MCP is a separate Coolify application from this same repository, with base
directory `/apps/mcp` and Dockerfile `/Dockerfile`. Retain its runtime environment
and bearer token. A high-priority Traefik route for `/mcp/` can share the existing
Plane domain. Preserve that route when changing application source settings.

Verify the deployment finishes, public UI loads, MCP health is healthy, existing
records are readable, and disposable issue creation/update/deletion works. Record
the deployed source SHA and local backup locations outside the public repository.

## Rollback

Before schema upgrades, reverting the backend images and MCP source settings to
the saved configuration is sufficient; redeploy the same service with the same
volumes. Do not restore an older database over new user writes unless a migration
requires it and an explicit recovery plan accounts for those writes.

Production credentials, database dumps and uploads must never be committed.

## API key rate limit

Birdplane production uses `API_KEY_RATE_LIMIT=300/minute` per API key. Set the
same value on `api`, `worker`, `beat-worker`, and `migrator`; the backend overlay
includes all four. Explicitly set `API_KEY_RATE_LIMIT=300/minute` when rendering
the overlay if your environment file still contains the upstream `60/minute`
default. This deployment setting is read by `ApiKeyRateThrottle` at process
startup, so recreate the backend containers after saving it in Coolify.

For an existing stack, update only those four environment values in its saved
Compose configuration. Preserve its pinned images, build contexts, secrets,
service names, resource UUIDs, volumes, and routes. Coolify accepts base64-encoded
Compose through its [service update endpoint](https://coolify.io/docs/api/endpoints/services/update-service-by-uuid).
Save with `instant_deploy: false`, read back the configuration and compare it
against the snapshot, then deploy the same service UUID through `POST /api/v1/deploy`.
Coolify may also refresh its own generated version labels during parsing.

Copy [`verify-api-rate-limit.py`](verify-api-rate-limit.py) into the running API
container, then run it from `/code` with `PYTHONPATH=/code`:

```sh
PYTHONPATH=/code python /tmp/verify-api-rate-limit.py --expect 300/minute
```

The check reads the real Django setting and loaded throttle class. It uses
synthetic requests and an instance-local memory cache to check the allowance,
remaining-request header, rejection and wait time, independent keys, and window
expiry. It sends no HTTP requests and never touches production Redis histories.
Follow it with a few authenticated API/MCP reads and writes, public health checks,
and observation of normal Clockwork polling and HTTP 429 logs during agent activity.
Keep Clockwork's metadata caching, server-side filters, and Retry-After handling.

To roll back, restore `API_KEY_RATE_LIMIT=60/minute` on all four services and
redeploy the same UUID. `API_KEY_RATE_LIMIT=60/minute` also overrides the overlay
default. A rate-only rollback requires no image, credential, volume, or database
restore. See the [BIRD-25 deployment evidence](api-rate-limit-2026-10-01.md).
