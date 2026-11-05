# Birdplane

Birdplane is a community fork of [Plane](https://github.com/makeplane/plane),
with the Sikku MCP server included at [`apps/mcp`](apps/mcp). The source is
public at <https://github.com/dasomji/birdplane> and uses the same GNU Affero
General Public License v3 as Plane; see [LICENSE.txt](LICENSE.txt).

## Upstream alignment

The current upstream baseline is Plane **v1.4.3**, commit
`37a15d99231042b3ff5a4401fed479fdbec9effe` (update prepared 2026-10-29). The initial
production baseline was v1.4.2, commit
`5f7d92784c403f76284f0f16718f320221dc7fec`. The `birdplane` branch carries our
additions. Upstream history, license, notices, app code and build files are
preserved. This is an independent community fork, not an official Plane release.

Keep fork-specific components in `apps/mcp` and `deployments/birdplane` where
possible. Avoid broad renaming of upstream packages or database tables.
For every update, complete the
[upstream update checklist and temporary-fix review](deployments/birdplane/upstream-update-checklist.md).
Fetch upstream releases and merge a selected release into a review branch:

```sh
git remote add upstream https://github.com/makeplane/plane.git # once
git fetch upstream --tags
git switch -c upgrade/plane-VERSION birdplane
git merge vVERSION
```

Review release notes and migrations, test with a restored backup, and upgrade
all upstream image versions together. Pin production builds to a reviewed commit.
Do not merge upstream's moving preview branch directly into production.

## Deployment

See [`deployments/birdplane/README.md`](deployments/birdplane/README.md).
The Git-connected deployment builds the backend, web and admin apps, Silo object storage, and
MCP from this repository, while using upstream v1.4.3 space, live, and proxy
images. Birdplane adds
`is`, `is not`, and `is empty` to Plane's existing filter UI and MCP; see
[filter documentation](deployments/birdplane/filters.md).

Recurring tasks are implemented in the isolated `plane.recurrence` Django app,
with a management page and compact MCP tools. See
[recurrence documentation](deployments/birdplane/recurrence.md).

## Agent development

Use the [development guide](docs/agents/development.md) for isolated environments,
[verification guide](docs/agents/verify.md) for checks, [doors](docs/agents/doors.md)
for review boundaries, and [GitHub targeting](docs/agents/fork-github.md) for fork
operations. Shared terms live in [GLOSSARY.md](GLOSSARY.md); consequential choices
live in [ADRs](docs/adr/). These guides do not authorize production operations.

Birdplane changes product branding while retaining upstream `@plane/*` packages,
Python `plane` modules, API routes/headers, environment and database values, and
asset paths. PQL and upstream commercial product names retain their provider names.
