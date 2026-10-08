# Deployment backups and temporary checks

Take a new snapshot before each deployment. Keep database dumps, uploads,
credentials, configuration snapshots, and manifests outside the repository in
a private directory. A replacement backup taken after a deployment is a current
snapshot, not a recreation of the earlier rollback point; record its capture time.

## Capture and transfer

Prefer direct container access and a binary file transfer. Run every PostgreSQL
client with `PGHOST=/var/run/postgresql`, `PGCONNECT_TIMEOUT=5`, and `-w` (never
prompt for a password). A socket override on `pg_dump` alone does not apply to
later `createdb`, `pg_restore`, `psql`, or `dropdb` calls. For remote databases,
provide the configured credentials privately and keep noninteractive behavior.
Use a bounded command timeout and propagate errors.

When direct access is unavailable, use [backup-postgres.py](backup-postgres.py):

```sh
python3 deployments/birdplane/backup-postgres.py \
  --url https://coolify.example.com \
  --token-file /private/coolify-token \
  --uuid APPLICATION_UUID --container plane-db \
  --output /private/new-backup-directory \
  --label 'Manual deployment backup TICKET'
```

The helper captures a custom-format dump, gets its exact byte count and SHA-256,
and transfers 512 KiB chunks. It rejects malformed/truncated base64, incorrect
chunk sizes, and checksum mismatches before publishing `database.dump`. Output
files are private; existing backups are never overwritten. It creates disabled
manual Coolify tasks, records execution metadata in `tasks.json`, and removes
successful tasks only after checking their final status. Failed or unfinished
tasks and the remote dump remain available for investigation. Do not blindly
repeat a timed-out request; inspect receipts and Coolify history first.

Never transfer a whole backup as base64 in execution output. The installed
Coolify execution output limit is 5 MB; even a task marked `success` can return
a truncated payload. A log is not a reliable file-transfer boundary.

## Verify the downloaded file

Compare the downloaded byte count and SHA-256 with the server manifest. Reading
the archive's table of contents (`pg_restore --list`) is insufficient: it can
succeed on a truncated archive. First read the entire archive with
`pg_restore --file=/dev/null`, then restore the downloaded file with
`pg_restore --exit-on-error` into a disposable, isolated PostgreSQL instance.
Use a compatible PostgreSQL client version, disable network access, and mount
only the backup file read-only. Inspect restored workspace, project, issue, and
migration records. Never restore verification data into the production database.

Record restore results and the verified file checksum in the private manifest.
Only then set `restore_verified` to `true` and accept the backup. Independently
verify uploads against their object manifest; a database dump does not contain
uploaded files. Clean up only the disposable verification instance and the
temporary files and tasks created by this operation.

## Notifications and diagnostics

Coolify's [notification selections](https://coolify.io/docs/core/notifications/events)
are configured per channel for the team. Keep Scheduled Task Failure, Backup
Failure, and resource/server failure events enabled. Muting scheduled-task
failures would also hide real maintenance failures.

Use direct shell/container access for exploratory probes when available.
If that access is unavailable, submit only prevalidated, noninteractive manual
commands and name them clearly as diagnostics or manual deployment checks.
Do not call a task "verified backup" before verification has passed. Disabled
tasks are still executable manually; disabling their schedule does not suppress
failure notifications or stop an existing run. Preserve failed execution
evidence, explain the outcome, and wait for an execution to finish before cleanup.
Never hide failures using `|| true`, lower exit codes, or temporary global alert
muting. Increase timeouts only for measured legitimate work, not password prompts.

Regression checks for the transfer helper:

```sh
python3 -m unittest discover -s deployments/birdplane -p 'test_backup_postgres.py'
```
