# Birdplane

Birdplane is a community fork of [Plane](https://github.com/makeplane/plane),
with the Sikku MCP server included at [`apps/mcp`](apps/mcp). The source is
public at <https://github.com/dasomji/birdplane> and uses the same GNU Affero
General Public License v3 as Plane; see [LICENSE.txt](LICENSE.txt).

## Upstream alignment

The initial production baseline is Plane **v1.4.2**, commit
`5f7d92784c403f76284f0f16718f320221dc7fec`. The `birdplane` branch carries our
additions. Upstream history, license, notices, app code and build files are
preserved. This is an independent community fork, not an official Plane release.

Keep fork-specific components in `apps/mcp` and `deployments/birdplane` where
possible. Avoid broad renaming of upstream packages or database tables.
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
The initial deployment builds the backend and MCP from this repository, while
using the unchanged upstream v1.4.2 web, admin, space, live and proxy images.
The application UI remains Plane's UI in this first milestone.

Recurring tasks are implemented in the isolated `plane.recurrence` Django app,
with a management page and compact MCP tools. See
[recurrence documentation](deployments/birdplane/recurrence.md).
