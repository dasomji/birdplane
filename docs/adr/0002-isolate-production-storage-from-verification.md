# 0002 — Isolate production storage from previews and verification

- Date: 2026-11-05
- Status: accepted; documents the existing deployment and backup boundary.

## Context and decision

The production [Compose definition](../../deployments/birdplane/compose.yml)
references explicitly named external volumes and networks. Preserve those resource
identities across application recreation. A missing external volume must fail
instead of silently creating an empty installation. Keep Coolify Raw Compose
Deployment enabled because the normal parser rewrites external volume mounts,
as recorded in the maintained [Git deployment guide](../../deployments/birdplane/git-compose.md).

Never use that definition for PR previews, tests, fixture seeding, or migration
verification. Product data belongs in product-owned storage outside worktrees.
Use separately named, owned disposable services and storage for verification;
restore only into the isolated database, with the downloaded backup mounted
read-only. Follow [backup verification](../../deployments/birdplane/backups.md)
for complete transfer, matching size/hash and `pg_restore --exit-on-error`.
A table-of-contents check alone cannot verify a backup. The
[API test stack](../../docker-compose-test.yml) and
[recurrence test stack](../../deployments/birdplane/recurrence-test.yml) are separate
from production; the new agent [development](../agents/development.md) and
[verification](../agents/verify.md) guides own safe run and cleanup commands.

## Consequences

Preview lifecycle is reversible only for owned disposable resources and only
when functional verification covers it. Do not delete shared/production volumes
as cleanup or run two database processes on one volume. Reverting application
code does not undo schema changes, live writes, or object-storage format changes.
The [Silo update entry](../../deployments/birdplane/upstream-update-checklist.md#minio-release-image-unavailable)
therefore requires a pre-switch volume archive and reconciliation of later uploads.

For a rate-limit-only rollback, change only the rate setting on all four backend
services and recreate them. Do not restore an older database over live writes.
See [rate-limit rollback](../../deployments/birdplane/README.md#api-key-rate-limit)
and the broader [application rollback boundary](../../deployments/birdplane/git-compose.md#rollback).
Release-branch pushes auto-deploy, so merging to `birdplane` is a production
trigger; use the [door rules](../agents/doors.md) and evidence review for this migration.
This ADR records the storage/verification boundary; it does not authorize a
production operation or assert that a new preview harness has passed verification.
