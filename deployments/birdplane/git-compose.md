# Git-connected production deployment

The production Compose definition is [compose.yml](compose.yml). Coolify checks
out the `birdplane` release branch and builds the web and backend from that
checkout. Connect the application through the installed `dasomji-coolify` GitHub
App and enable Auto Deploy after the initial migration is verified. Keep
pull-request previews disabled: this definition references production storage.

## Coolify configuration

- Build pack: Docker Compose.
- Base Directory: `/`.
- Docker Compose Location: `/deployments/birdplane/compose.yml`.
- Repository: `dasomji/birdplane`; branch: `birdplane`.
- The `proxy` service's Traefik labels route `https://plane.audiopoesis.com` to port 80.
- Preserve the separate MCP application's higher-priority `/mcp/` route.
- Copy the existing runtime environment values privately into the application's
  environment settings. Never commit credentials or database/upload backups.
  Enable both build-time and runtime availability: Docker Compose interpolates
  the entire definition during builds. Keep Inject Build Args to Dockerfile off;
  these configuration values must not become image build arguments.
- Enable Raw Compose Deployment. The installed Coolify version's normal parser
  rewrites external volume mounts; raw mode preserves the exact Docker definition.
  The file supplies routing, networks, and management labels explicitly.
- Set `BIRDPLANE_APPLICATION_UUID` and `BIRDPLANE_APPLICATION_ID` to the new
  application's verified UUID and numeric ID. These label its containers for
  Coolify monitoring and lifecycle operations.

Every persistent volume has an explicit existing name and `external: true`.
A missing volume fails deployment instead of creating an empty installation.
Keep these names during application recreation. Preview deployments must never
mount these volumes. The web and backend use shared local image tags that are
rebuilt from the checked-out commit; workers and migrations use that same backend
image. Record the deployed commit from Coolify's deployment history.

MinIO is built from the exact `RELEASE.2025-09-07T16-13-09Z` source commit because
the former official container image and binary downloads are unavailable. This
preserves its release version while making deployments independent of that
removed image. See [Dockerfile.minio](Dockerfile.minio).

## Migration

1. Save the existing resource configuration, generated Compose, environment,
   routes, and volume identities privately.
2. Take a fresh PostgreSQL custom-format dump and export uploads with an object
   manifest. Verify the exported dump checksum, restore with
   `pg_restore --exit-on-error` into a separate database, and verify every upload
   checksum. Restore the downloaded file, not just the server-side dump; follow
   [backup transfer and verification](backups.md). Record workspace, project,
   and issue identities.
3. Create the Git-connected application with Auto Deploy and previews disabled.
   Copy the unchanged credentials and environment values. Inspect its parsed
   volumes before starting any container.
4. Build and create the replacement containers without starting them. Temporarily
   set Coolify's Custom Start Command to
   `docker compose --env-file .env --project-directory . -f deployments/birdplane/compose.yml create`.
   Explicit relative paths avoid this Coolify version injecting a host-only env
   path into the build helper. Keep the existing production stack running while
   images build.
5. Before cutover, take a final backup and record identities again. Stop the old
   stack without deleting its resource or volumes. Confirm its database process
   has stopped before starting the replacement database on the same volume.
6. Clear the temporary Custom Start Command and
   deploy the replacement application. Verify migrations, existing records,
   uploads, API/MCP health, and workspace layout/grouping controls.
7. Enable Auto Deploy for `birdplane` and verify a real GitHub push causes a
   deployment of that commit. Retain the stopped old resource for rollback.

## Rollback

Stop the replacement application before restarting the old stack. Preserve all
external volumes and use the privately saved original configuration. Do not run
both databases against the same volume. Do not delete the old resource or its
volumes while it remains the rollback path. An application rollback must also
account for any new schema migrations; restoring an old dump over live writes
requires a separate recovery decision.

This Coolify version queues Docker image cleanup when stopping a service. The
old resource's configuration and volumes survive, but its locally built image
tags may need rebuilding before restart. Rebuild the web from
`74965ca1faa7c034dc4b79317cc4253105bff121` and backend from
`0510b75a043c291cb6a4be700aca160dba0858e4`, using their Dockerfiles and original
image tags recorded in the private configuration snapshot. Build
`Dockerfile.minio` and tag that same release as
`minio/minio:RELEASE.2025-09-07T16-13-09Z` for the legacy definition. Verify those
images exist before stopping the replacement; avoid a lifecycle operation that
prunes them during rollback.

For upstream upgrades, retain the existing
[upstream update checklist](upstream-update-checklist.md) and test with a restored
backup before merging to the auto-deployed release branch.

## Cutover verification — 2026-10-02

- Production application: `r7leiczgbsrhh29agsk8oy2f`; legacy service retained
  stopped: `hnslaatmrmfginhfa1kemiam`.
- Auto Deploy follows `birdplane`, the fork's release/default branch. PR previews
  are disabled. Custom build/start commands are cleared.
- GitHub's merge push for PR #10 triggered deployment
  `n7srkdq7ixwvfinbkwg98stc` with `is_webhook: true`; it finished at commit
  `1cbfe98ab607a129c5d505e908fe94b3c5abcabc`.
- Final PostgreSQL dump: 6,777,997 bytes; SHA256
  `f7f3e6b8316c07516f1090289e1f9ad48dfa0f13ed5b5303324b7ec1adc0ce8c`.
  Restored successfully with `pg_restore --exit-on-error` in an isolated database.
- All 2 workspace, 24 project, and 229 issue table identities were retained,
  including soft-deleted records. No schema migrations were pending.
- All six uploaded objects matched the final backup by key, size, and SHA256.
  MinIO reports the original release and exact source commit.
- Signed-in production browser verification confirmed all five layout selectors,
  rendered List, Calendar, Spreadsheet, and Gantt views, and Project grouping.
- Backups and original configuration are stored privately outside the repository
  under `~/.local/state/birdplane/BIRD-27-20261002/` on the operator workstation.
