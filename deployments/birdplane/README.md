# Birdplane on an existing Coolify Plane stack

Preserve the existing Coolify service UUID, Compose service names, named volumes,
database credentials, application secrets, object storage configuration and domain.
Changing a service UUID can silently create empty volumes. Never run `down -v`.

Before rollout, save the current Coolify service configuration privately, take a
PostgreSQL custom-format dump, verify a restore into a separate temporary database,
and back up object storage. Record volume names and existing project/ticket IDs.

For the backend, set all four services (`api`, `worker`, `beat-worker`, `migrator`)
to the same local image tag, e.g. `birdplane-backend:COMMIT`, with
`pull_policy: never`. Add the following build definition to `api`:

```yaml
build:
  context: https://github.com/dasomji/birdplane.git#COMMIT:apps/api
  dockerfile: Dockerfile.api
```

Replace COMMIT with a full reviewed commit SHA. Coolify's service start builds
the image before recreating containers. Keep frontend/admin/space/live/proxy
images at `makeplane/plane-*:v1.4.2` for the initial release. No schema changes
are introduced by Birdplane's initial additions.

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
