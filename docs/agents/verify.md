# Verification

`check:full` is **blocked as an implementation contract until measured green**.
A nonzero aggregate, failed phase, missing prerequisite or unexpected skip is not a
passing L2 receipt. This migration hands back in evidence mode for Daniel's review.

Run on Coolify with Node from `.mise.toml` (22.18.0; engines >=22.18.0), pnpm from
`packageManager` (11.10.0), Python 3.12, uv and Docker with Compose v2/buildx.
Install dependencies with `pnpm install --frozen-lockfile`. CI pins uv 0.8.22;
Ruff is pinned per component to match the existing lanes/API development tooling.
Keep at least 8 GiB free on `/`. The runners refuse work below this reserve and
terminate their child process group if it drops below it. Never prune shared Docker
resources. Temporary source snapshots and test data live outside the checkout.

## Commands and coverage

| Rung     | Command                                  | Coverage                                                                                                                                          |
| -------- | ---------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------- |
| L0       | `node --test scripts/kitchen/*.test.mjs` | Gate selection, staged-index behavior and upstream exemption contracts. For product edits also run the affected module's focused tests/typecheck. |
| L1       | `pnpm check:fast`                        | Staged formatting, lint, dependent-package typechecks/builds and related suites. Enforced after `pnpm lint-staged` by `.husky/pre-commit`.        |
| L2       | `pnpm check:full`                        | Named full phases listed below, with failing aggregate for any failed/blocked/missing phase.                                                      |
| L3       | `pnpm verify:app`                        | Functional journeys plus a failure case at the tested SHA. See [functional verification](development.md#functional-verification).                 |
| L3 smoke | `pnpm verify:app`                        | The same isolated smoke/journey contract; there is no separate reduced command claiming functional proof.                                         |

`check:fast` exports the entire Git index to a temporary directory, installs an
offline frozen workspace there, and checks that snapshot. It never formats source
in the checkout. Child checks strip Git's exported repository/index overrides:
worktree hooks export an absolute `GIT_DIR`, which must never leak into temporary
fixture repositories. A regression test injects those overrides and verifies that
the invoking repository's HEAD/index stay unchanged. Renames select both old/new paths; deletions still select related
checks. `lint-staged` retains its existing stash/partial-staging behavior.
JS/TS/CSS/Markdown/JSON/YAML use oxfmt; JS/TS use OxLint with zero warnings. Python
under API, MCP and backup scripts uses Ruff check and format check. Root Markdown
also gets an offline relative-destination link check. Dependency installs must have
populated pnpm's local store before the offline snapshot install.

Workspace source edits select the package and dependent consumers through Turbo;
`check:types` builds dependency outputs first. Related workspace tests run with the
same dependent filter. Package edits also build shared-state before its explicit
Node filter tests. Branding paths select branding tests; MCP selects its full unit
suite; backup edits select backup unittests. Scripts-only root package changes and
gate metadata select gate contract tests. Unknown infrastructure paths fail closed:
add a reviewed selection contract instead of bypassing the hook.

API pytest is mandatory L2 coverage, rather than host pytest in a commit hook:
starting PostgreSQL, Valkey, RabbitMQ and object storage plus migrations is outside
the roughly 60-second L1 target. L1 still checks changed Python with Ruff. MCP unit
and packaging checks need no database because its tests mock Plane's HTTP boundary;
Birdplane's actual database/app checks remain required in L2 and L3.

`check:full` runs, in order:

1. Gate Node contract tests; `pnpm check`; `pnpm build`; `pnpm turbo run test`;
   branding; explicit shared-state build and Node filter tests.
2. Full API Ruff **check only**, isolated image build, healthy test services,
   unrestricted pytest discovery with `-o "python_files=test_*.py tests.py"` and
   `--migrations --create-db` (including recurrence's `tests.py`), then migration
   apply/check and real API HTTP health success plus unreachable-database refusal.
3. MCP frozen sync, all pytest, Ruff, wheel build with source/bundled guidance byte
   equality, Docker build and bundled guidance assertions matching the existing lane.
4. Backup unittests plus Ruff check/format check; root/agent Markdown formatting and
   relative local-link destinations; owned-resource cleanup.

Turbo concurrency is capped at two to bound memory, without dropping tasks. Existing
upstream per-package warning budgets stay exactly as declared in their scripts;
this is an explicit compatibility policy, not an increased allowance. The full gate
reports their real exit status. Newly staged JS/TS has zero warnings. Only the exact
unchanged-upstream violations registered below are exempted; every other diagnostic
fails. Remote links/heading fragments are not network-validated by the offline
relative-link check.

The API stack is the standalone fork-owned
`scripts/kitchen/compose/api-tests.yml`; never combine it with production Compose or
`docker-compose-test.yml`. Build contexts include tracked source only and exclude
`.env` files. No local `.env` is read, source is not bind mounted, no ports are
published, database/service data is temporary, and every run has its own project,
image tags and buildx builder. Cleanup waits for commands and contributes to the
aggregate. A failed prerequisite marks dependent phases blocked. Independent phases
still run to expose the full baseline.

## Per-component justified exceptions

The fork-owned [upstream exemption register](../../scripts/kitchen/upstream-exemptions.json)
records individual violations, their check/rule, exact source locations and symbols
where applicable, the selected `upstreamRef` (`v1.4.3`), its Git blob SHA and a
one-line justification. It contains three API `F401` diagnostics (`Func`, `Q` and
`User`) and the `SECURITY.md` oxfmt violation. These files remain byte-identical to
the selected upstream release; no upstream source or document is rewritten.

The `api-ruff` phase runs the entire API check without fixes, with Ruff's JSON
output. Every diagnostic must match one register entry by file, code, symbol/message
and start/end location, exactly once. Any additional diagnostic fails. The
`root-docs-format` phase rechecks registered documents with oxfmt's
`--list-different`, then excludes only those exact paths from its formatting check.
Registered documents remain subject to the relative-link check.

Both components compare `git hash-object <path>` against the recorded upstream blob
without fetching tags or using the network. A changed or missing file fails: it is
now fork-owned and must be fixed and removed from the register. An exemption whose
violation no longer occurs also fails as stale and must be removed. Invalid and
duplicate entries fail. The register can only shrink as these violations disappear;
it is never a component-wide or repository-wide waiver. Each applied exemption is
printed with its location, rule, blob and justification in the phase output/log.

For cheap diagnostics, select any combination of `kitchen-tests`, `api-ruff`,
`root-docs-format` and `root-docs-links`:

```sh
pnpm check:full --phase api-ruff --phase root-docs-format --phase root-docs-links
```

Cleanup still runs. Omitted phases keep the aggregate **blocked** and the command
nonzero even when all selected phases pass; this is never a full L2 pass. Run the
unfiltered gate after integration to measure the implementation contract.

## Measurements and evidence

Coolify's initial diagnostic baseline on 2026-11-05 took **1319.44 seconds
(21 min 59 s)** and returned **blocked**. It ran against base `55a18ee93` plus the
uncommitted gate implementation, using Node 22.22.2, pnpm 11.10.0 and uv 0.11.14.
This diagnostic run collected 852 API tests; the final runner expands discovery to
include recurrence's `tests.py`. Use the report/receipt for the actual handoff SHA,
not this pre-commit benchmark, as execution evidence.

| Phase                  | Seconds | Result |
| ---------------------- | ------- | ------ |
| `kitchen-tests`        | 2.48    | pass   |
| `workspace-check`      | 104.45  | pass   |
| `workspace-build`      | 93.25   | pass   |
| `workspace-tests`      | 14.21   | pass   |
| `branding`             | 0.80    | pass   |
| `shared-state-filters` | 2.56    | pass   |
| `api-ruff`             | 0.36    | fail   |
| `api-image`            | 355.49  | pass   |
| `api-services`         | 8.34    | pass   |
| `api-pytest`           | 440.60  | pass   |
| `api-migration-boot`   | 188.01  | pass   |
| `mcp-sync`             | 0.66    | pass   |
| `mcp-pytest`           | 4.53    | pass   |
| `mcp-ruff`             | 0.09    | pass   |
| `mcp-wheel-guidance`   | 0.44    | pass   |
| `mcp-docker-guidance`  | 60.88   | pass   |
| `backup-tests-ruff`    | 0.93    | pass   |
| `root-docs-format`     | 1.55    | fail   |
| `root-docs-links`      | 0.01    | fail   |
| `cleanup`              | 39.75   | pass   |

The API suite passed 852 tests with 92 warnings; MCP passed 68 tests with two
warnings; backup unittests passed 12 tests. Pytest retains its existing visible
warning/exit policy; no warning filters or increased budgets were added. The
full gate observed 2964.4 MiB peak sampled runner-process-tree RSS, 21856.2 MiB
peak host used memory, 5.24 GiB maximum root-filesystem growth, and 18.57 GiB
minimum free disk. Host memory and disk figures include concurrent workloads;
these are reserve/capacity observations, not exclusive allocation measurements.
Docker/BuildKit memory is outside process-tree RSS. Cleanup passed and removed
this run's Compose stack, output image tags and private builder/cache.

The gate-only fast check took **10.38 seconds** in the disposable clone. Both
syntax rejection (lint-staged) and a valid-but-failing staged test (check:fast)
blocked commits without moving HEAD; a successful hook preserved an unstaged
hunk while committing the staged hunk. Product/package selections may take
longer because their dependency builds and dependent typechecks are real.

The baseline API Ruff and upstream `SECURITY.md` formatting failures are covered
only by the exact, blob-guarded exemptions above. Integration still requires this
guide's `development.md` target from chunk 2b, its L3 implementation, and a green
unfiltered full-gate measurement. Missing links have no exemption.

Per-phase durations and outcomes, minimum free disk, peak disk growth and sampled
peak runner process-tree RSS are written to `.kitchen/evidence/check-full-<UTC>-<pid>/results.json`, beside complete
phase logs. Host used memory is also sampled; it includes other host workloads.
Docker/BuildKit process memory is outside runner RSS, so that metric is not a total
container-memory measurement. Local runtime and green status must be measured,
never inferred from historical CI lanes.

Append actual checks to ignored `.kitchen/receipts.jsonl` with UTC timestamps and the
full tested commit SHA. Example shape (replace values with an actual run):

```json
{ "rung": "L1", "command": "pnpm check:fast", "sha": "<full sha>", "result": "pass", "time": "<UTC ISO>" }
```

Record L1 at the new HEAD after the commit succeeds; failed/blocked results remain
failed/blocked. Receipts from a different SHA require an explicit diff-based carry
explanation and are not new executions. Evidence lives in ignored
`.kitchen/evidence/`, never Git. Review logs/captures for sensitive data, then upload:

```sh
evidence put .kitchen/evidence/<file> --ticket BIRD-34 --note '<verified result>' --markdown
```

Add `--pr <url>` when a PR exists. Keep textual outcomes beside links because uploaded
evidence expires. The Ubuntu `birdplane-checks / check-full` lane runs this same L2
command on every PR targeting `birdplane` and every push to it, including docs-only
changes. Existing focused lanes remain enabled. CI has no deploy/publish step.
