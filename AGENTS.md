# Agent Development Guide

<!-- BEGIN BIRDPLANE FORK -->

## Birdplane agent routing

<!-- BEGIN PLANE PROJECT -->

### Plane project

- Instance URL: https://plane.audiopoesis.com
- Workspace: Personal
- Workspace slug: personal
- Workspace ID: c51280e8-6121-4a07-b25a-244d6dc466b2
- Name: Birdplane
- Identifier: BIRD
- Project ID: a5b675f4-e0b9-41f8-9600-cf0ad45daeb6

<!-- END PLANE PROJECT -->

- [Development and isolated environments](docs/agents/development.md),
  [verification commands](docs/agents/verify.md), and [merge doors](docs/agents/doors.md).
- [Fork GitHub targeting](docs/agents/fork-github.md): always use `--repo dasomji/birdplane`
  and base `birdplane`. Release-branch pushes trigger production deployment.
- [Glossary](GLOSSARY.md) and [decisions](docs/adr/), including the
  [scoped upstream-body exception](docs/adr/0001-preserve-fork-boundaries-and-selected-releases.md).
- Complete the [upstream-update checklist](deployments/birdplane/upstream-update-checklist.md)
  before merging or deploying an upstream update; register each temporary workaround there.
- Follow [backup and Coolify diagnostic rules](deployments/birdplane/backups.md).
  Production Compose uses external production volumes; never use it for previews/tests.

<!-- END BIRDPLANE FORK -->

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
