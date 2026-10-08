# Agent Development Guide

<!-- BEGIN PLANE PROJECT -->

## Plane project

- Instance URL: https://plane.audiopoesis.com
- Workspace: Personal
- Workspace slug: personal
- Workspace ID: c51280e8-6121-4a07-b25a-244d6dc466b2
- Name: Birdplane
- Identifier: BIRD
- Project ID: a5b675f4-e0b9-41f8-9600-cf0ad45daeb6
- Instance URL: https://plane.audiopoesis.com
<!-- END PLANE PROJECT -->

## Upstream updates and temporary fixes

Before merging or deploying an upstream Plane update, complete
[`deployments/birdplane/upstream-update-checklist.md`](deployments/birdplane/upstream-update-checklist.md)
and record the disposition of each active temporary fix in the update PR.
When adding a temporary upstream workaround, add its removal condition and
regression checks to that document's register. Retire redundant local patches
only after verifying equivalent behavior in the selected upstream release.

## Coolify operations and backup verification

Follow [`deployments/birdplane/backups.md`](deployments/birdplane/backups.md)
for deployment backups and temporary checks. Keep genuine scheduled-task,
backup, and service failure notifications enabled. Use direct container access
for exploratory diagnostics when available; disabled Coolify tasks still send
failure notifications when manually executed. If direct access is unavailable,
use prevalidated, clearly named manual tasks with explicit connection settings,
bounded timeouts, and no interactive password prompts. Preserve failed execution
evidence before cleanup, and wait for terminal status before removing tasks.

Use the local PostgreSQL socket consistently and pass `-w` to every client.
Transfer backups as files or bounded chunks, never as a single execution-log
payload. Match the downloaded file's size and SHA-256 to the server and restore
that downloaded file into an isolated database with `--exit-on-error` before
calling it verified. Never suppress a failure with `|| true`, globally mute
alerts to test a command, or report a verified server dump as a verified download.

## Commands

- `pnpm dev` - Start all dev servers (web:3000, admin:3001)
- `pnpm build` - Build all packages and apps
- `pnpm check` - Run all checks (format, lint, types)
- `pnpm check:lint` - OxLint across all packages
- `pnpm check:types` - TypeScript type checking
- `pnpm fix` - Auto-fix format and lint issues
- `pnpm turbo run <command> --filter=<package>` - Target specific package/app
- `pnpm --filter=@plane/ui storybook` - Start Storybook on port 6006

## Code Style

- **Imports**: Use `workspace:*` for internal packages, `catalog:` for external deps
- **TypeScript**: Strict mode enabled, all files must be typed
- **Formatting**: oxfmt, run `pnpm fix:format`
- **Linting**: OxLint with shared `.oxlintrc.json` config
- **Naming**: camelCase for variables/functions, PascalCase for components/types
- **Error Handling**: Use try-catch with proper error types, log errors appropriately
- **State Management**: MobX stores in `packages/shared-state`, reactive patterns
- **Testing**: All features require unit tests, use existing test framework per package
- **Components**: Build in `@plane/ui` with Storybook for isolated development

## Backend tests (Docker)

The Django/pytest suite for `apps/api` runs in an isolated stack defined by `docker-compose-test.yml` at the repo root.

Prereq (once): `./setup.sh` — generates `apps/api/.env` from `.env.example`.

- Full suite: `docker compose -f docker-compose-test.yml up --build --abort-on-container-exit --exit-code-from api-tests`
- Subset: `docker compose -f docker-compose-test.yml run --rm api-tests pytest -m unit`
- Teardown: `docker compose -f docker-compose-test.yml down -v`

See `apps/api/tests/RUNNING_TESTS.md` for the full walkthrough and troubleshooting; see `apps/api/tests/TESTING_GUIDE.md` for test conventions and fixtures.
