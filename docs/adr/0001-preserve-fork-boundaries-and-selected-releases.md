# 0001 — Preserve fork boundaries and update from selected releases

- Date: 2026-11-05
- Status: accepted for the BIRD-34 documentation migration; Daniel reviews and merges.

## Context and decision

Birdplane is an independent AGPL community fork with upstream history and compatible
package, module, database and API names. Keep permanent fork seams in `apps/mcp`,
`apps/api/plane/recurrence`, and `deployments/birdplane` where practical. Keep
Kitchen additions in separate new files rather than rewriting upstream guidance.
Retain the 29 documents unchanged against the selected v1.4.3 tag byte for byte.
The shipped [MCP guidance](../../apps/mcp/sikku/skills/plane-project-management/SKILL.md)
is a product asset, not a local memory to relocate; its
[packaging tests](../../apps/mcp/tests/test_guidance.py) depend on that contract.

Merge selected release tags into review branches; review migrations and each
retain/replace/adapt entry in the [update checklist](../../deployments/birdplane/upstream-update-checklist.md).
A merged upstream PR is insufficient: the selected tag must contain equivalent
behavior and pass the regression checks before retiring a patch. Keep source
baseline and live rollout evidence distinct. At this decision, v1.4.3 resolves to
`37a15d99231042b3ff5a4401fed479fdbec9effe` and is an ancestor of the fork; the
[overview](../../BIRDPLANE.md#upstream-alignment), root
[package version](../../package.json), and production
[Compose definition](../../deployments/birdplane/compose.yml) agree on v1.4.3.

## Scoped lean-AGENTS exception

Kitchen normally requires the whole root AGENTS to be lean. Fork preservation
requires retaining its inherited Commands, Code Style and Backend tests body
from v1.4.3 in place. Apply the lean rule to the delimited Birdplane fork section:
verified Plane mapping, routing, verification pointers and unusual environment
facts. Keep the inherited body intact; this exception does not license copying
more shared policy into it. Root and tailwind-scoped CLAUDE wrappers contain only
`@AGENTS.md` plus a newline; the tailwind AGENTS itself remains untouched.

[README](../../README.md) and [CONTRIBUTING](../../CONTRIBUTING.md) likewise put
fork instructions in small delimited sections and retain the inherited body.
README's previously replaced upstream body is restored from the selected tag;
CONTRIBUTING's scattered fork edits move to its fork section. Markdown range-ignore
comments preserve inherited formatting while allowing the fork sections to be
formatted. This avoids a recurring upstream formatting diff.

## Consequences and sources

Upstream instructions may describe upstream offerings, clone URLs and `preview`
workflows. The fork section and [GitHub targeting guide](../agents/fork-github.md)
route contributors to Birdplane's actual release branch and checks. Do not treat
inherited workflows as the fork gate. This accepts some inherited verbosity in
exchange for a smaller continuing merge conflict surface.

Sources: v1.4.3 versions of `AGENTS.md`, `README.md`, and `CONTRIBUTING.md`;
[fork overview](../../BIRDPLANE.md), [update checklist](../../deployments/birdplane/upstream-update-checklist.md),
and [deployment branch contract](../../deployments/birdplane/git-compose.md).
