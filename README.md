# Birdplane

Birdplane is a personal fork of [Plane](https://github.com/makeplane/plane), an open-source project management tool for work items, cycles, pages, and product roadmaps. This repository and its self-hosted apps are called **Birdplane** to distinguish the fork from upstream Plane and Plane Cloud.

See [BIRDPLANE.md](BIRDPLANE.md) for the upstream baseline, included MCP server, deployment instructions, and update strategy. Follow the [upstream update checklist](deployments/birdplane/upstream-update-checklist.md) when updating Plane.

## Development

Use Node.js 22.22 or newer, pnpm (the version in `package.json`), and Docker Compose.

```bash
git clone https://github.com/dasomji/birdplane.git
cd birdplane
./setup.sh
docker compose -f docker-compose-local.yml up -d
pnpm dev
```

The setup script creates the local environment files and installs dependencies. Review those files for your local configuration. Open the admin portal at `http://localhost:3001/god-mode/` to register the instance admin, then sign in at `http://localhost:3000`.

See [CONTRIBUTING.md](CONTRIBUTING.md) for architecture and contribution conventions, [AGENTS.md](AGENTS.md) for repository checks, and [the API test guide](apps/api/tests/RUNNING_TESTS.md) for the isolated Docker test stack.

## Checks

```bash
pnpm check
pnpm test:branding
pnpm build
```

Backend tests run through `docker-compose-test.yml`; see the API test guide for targeted runs and teardown.

## Fork identity and compatibility

Birdplane uses its own app titles, wordmarks, installable app names, localized product copy, and email branding. Existing `@plane/*` package names, the Python `plane` module, API routes and headers, environment variables, database values, and asset paths remain compatible with upstream. **Plane Query Language (PQL)** and upstream commercial product names remain named after their actual providers.

Report fork-specific bugs and feature requests in [Birdplane's issue tracker](https://github.com/dasomji/birdplane/issues). Upstream [product documentation](https://docs.plane.so/) and [developer documentation](https://developers.plane.so/) remain useful references; upstream services and commercial plans are provided by Plane.

## Attribution and license

Birdplane is based on work by Plane Software, Inc. and contributors. Original copyright notices and license terms are preserved. See [LICENSE.txt](LICENSE.txt) and the license headers in individual files.
