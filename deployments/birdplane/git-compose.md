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

## Migration

1. Save the existing resource configuration, generated Compose, environment,
   routes, and volume identities privately.
2. Take a fresh PostgreSQL custom-format dump and export uploads with an object
   manifest. Verify the exported dump checksum, restore with
   `pg_restore --exit-on-error` into a separate database, and verify every upload
   checksum. Record workspace, project, and issue identities.
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

For upstream upgrades, retain the existing
[upstream update checklist](upstream-update-checklist.md) and test with a restored
backup before merging to the auto-deployed release branch.
