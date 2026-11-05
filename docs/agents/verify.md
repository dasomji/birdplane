# Verification

`check:full` was measured green on Coolify: **20/20 phases**, **1064 seconds**
at `e2c7c0a2f260a87f50c7f396237a575b0e4bcc3f`, with the four pinned
upstream exemptions below applied. A nonzero aggregate, failed phase, missing
prerequisite or unexpected skip is not a passing L2 receipt. A green L5 run on
GitHub at the PR head is still required before merge.

Run on Coolify with Node from `.mise.toml` (22.18.0; engines >=22.18.0), pnpm from
`packageManager` (11.10.0), Python 3.12, uv and Docker with Compose v2/buildx.
Install dependencies with `pnpm install --frozen-lockfile`. CI pins uv 0.8.22;
Ruff is pinned per component to match the existing lanes/API development tooling.
Keep at least 8 GiB free on `/`. The runners refuse work below this reserve and
terminate their child process group if it drops below it. Never prune shared Docker
resources. Staged source snapshots live under ignored `.kitchen/tmp/` on the repository
filesystem so offline pnpm imports do not cross filesystem boundaries; they are
removed after each run. Inside a `.kitchen/tmp/` snapshot, Git-aware tools resolve
to the parent repository. Build contexts and disposable product data live outside
the checkout.

## Commands and coverage

| Rung     | Command                                  | Coverage                                                                                                                                          |
| -------- | ---------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------- |
| L0       | `node --test scripts/kitchen/*.test.mjs` | Gate selection, staged-index behavior and upstream exemption contracts. For product edits also run the affected module's focused tests/typecheck. |
| L1       | `pnpm check:fast`                        | Staged formatting, lint, dependent-package typechecks/builds and related suites. Enforced after `pnpm lint-staged` by `.husky/pre-commit`.        |
| L2       | `pnpm check:full`                        | Named full phases listed below, with failing aggregate for any failed/blocked/missing phase.                                                      |
| L3       | `pnpm verify:app`                        | Functional journeys plus a failure case at the tested SHA. See [functional verification](development.md#functional-verification).                 |
| L3 smoke | `pnpm verify:app`                        | The same isolated smoke/journey contract; there is no separate reduced command claiming functional proof.                                         |

`check:fast` exports the entire Git index under `.kitchen/tmp/`, installs an
offline frozen workspace there, and checks that snapshot. It never formats source
in the checkout. Child checks strip Git's exported repository/index overrides:
worktree hooks export an absolute `GIT_DIR`, which must never leak into temporary
fixture repositories. A regression test injects those overrides and verifies that
the invoking repository's HEAD/index stay unchanged. Renames select both old/new paths; deletions still select related
checks. `lint-staged` retains its existing stash/partial-staging behavior.
JS/TS/CSS/Markdown/JSON/YAML use oxfmt; JS/TS use OxLint with zero warnings. Python
under MCP, deployment scripts and kitchen scripts uses Ruff check and format check.
API Python uses Ruff **check only** at L2, with the exemption register applied;
L1 defers all API Ruff checks via `apiAtL2` rather than imposing stricter formatting.
Neither L1 nor L2 runs API Ruff formatting checks. Root Markdown
also gets an offline relative-destination link check. Dependency installs must have
populated pnpm's local store before the offline snapshot install.

Workspace source edits select the package and dependent consumers through Turbo;
`check:types` builds dependency outputs first. Related workspace tests run with the
same dependent filter. Package edits also build shared-state before its explicit
Node filter tests. Branding paths select branding tests; MCP selects its full unit
suite; backup edits select backup unittests. Scripts-only root package changes and
gate metadata select gate contract tests. Unknown infrastructure paths fail closed:
add a reviewed selection contract instead of bypassing the hook. During an
upstream merge (`MERGE_HEAD` exists), mapped paths still run their normal checks;
unmapped paths are listed as having no fast check. They are covered only by
whichever `check:full` phases include them and by review; `check:full` has no
catch-all phase for arbitrary paths.
Unknown fork deployment paths still fail closed. Outside merges every unknown
path fails closed.

Deployment `.mjs` files get oxfmt/OxLint; deployment `.py` files get pinned Ruff
check and format check. Root `docker-compose*.yml`, deployment Compose and kitchen
Compose definitions get `docker compose --env-file /dev/null -f <temporary-copy>
config --quiet`: copies replace service `env_file` declarations with `/dev/null`,
use synthetic interpolation values and a clean environment, and never start
services or access a daemon/network. External Compose includes/extends fail closed
until they have an explicit isolated contract. Workflow YAML is parsed with the frozen
workspace's YAML parser (Vite's locked optional peer); actionlint also runs when
already on `PATH`, with no hook download. Deployment Dockerfiles explicitly select
L2 BuildKit `--check --network=none` in the owned builder; resolving pinned base
images is L2 work. No Dockerfile build instructions execute.

API pytest is mandatory L2 coverage, rather than host pytest in a commit hook:
starting PostgreSQL, Valkey, RabbitMQ and object storage plus migrations is outside
the roughly 60-second L1 target. API Ruff is also deferred to L2 so its
check-only and exact upstream-exemption policy has one execution path. MCP unit
and packaging checks need no database because its tests mock Plane's HTTP boundary;
Birdplane's actual database/app checks remain required in L2 and L3.

`check:full` runs, in order:

1. Gate Node contract tests with zero skipped/todo tests (real-browser regressions
   run under `verify:app` with its pinned install); `pnpm check`; `pnpm build`; `pnpm turbo run test`;
   branding; explicit shared-state build and Node filter tests.
2. Full API Ruff **check only**, isolated image build, healthy test services,
   unrestricted pytest discovery with `-o "python_files=test_*.py tests.py"` and
   `--migrations --create-db` (including recurrence's `tests.py`), then migration
   apply/check and real API HTTP health success plus unreachable-database refusal.
3. MCP frozen sync, all pytest, Ruff, wheel build with source/bundled guidance byte
   equality, Docker build and bundled guidance assertions matching the existing lane.
4. Backup unittests plus Ruff check/format check; deployment JavaScript format/lint,
   all deployment Python Ruff check/format, all Compose config, all workflow YAML
   and deployment Dockerfile checks; root/agent Markdown formatting and relative
   local-link destinations; owned-resource cleanup. These add five named phases:
   `deployment-javascript`, `deployment-python`, `compose-config`, `workflow-yaml`
   and `deployment-dockerfiles` (25 total).

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
without using the network. When the register's selected release tag is available locally they also require
`git rev-parse refs/tags/<upstreamRef>:<path>` to equal the registered blob, so editing
both the source and register cannot forge provenance. A missing local tag prints
an explicit tag-cross-check-unavailable message; the file blob check still runs.
The register JSON is the single source of truth for that tag; the library and CI
read it there. All entries must select the same release. CI fetches only that
release tag at depth one for this cross-check. A changed or missing file fails: it is
now fork-owned and must be fixed and removed from the register. An exemption whose
violation no longer occurs also fails as stale and must be removed. Invalid and
duplicate entries fail. The register shrinks as these violations disappear.
Re-pinning is allowed only during an upstream update through the
[temporary-workaround checklist](../../deployments/birdplane/upstream-update-checklist.md#upstream-verification-exemptions);
never re-pin a fork-modified file. It is never a component-wide or repository-wide waiver. Each applied exemption is
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

The historical unfiltered Coolify run at
`e2c7c0a2f260a87f50c7f396237a575b0e4bcc3f` passed **20/20 phases in 1064 seconds**
with the three API F401 and one SECURITY.md formatting exemptions applied.
This is a measured baseline, not a receipt for a later commit. The expanded gate
has 25 phases; use its same-SHA report for handoff timings and results.

An expanded-gate diagnostic on Coolify on 2026-11-05 passed **25/25 phases in
828.92 seconds**, with 19.92 GiB minimum free disk. It ran on the staged
implementation based on `eda9dcf59181b0be79e1e8b63964313dc5ad038a`;
this pre-commit measurement is a capacity benchmark, not a same-SHA handoff receipt.
The new phases measured:

| Phase                    | Seconds | Result |
| ------------------------ | ------- | ------ |
| `deployment-javascript`  | 1.54    | pass   |
| `deployment-python`      | 0.17    | pass   |
| `compose-config`         | 0.71    | pass   |
| `workflow-yaml`          | 0.05    | pass   |
| `deployment-dockerfiles` | 1.39    | pass   |

The gate-only fast check took **10.38 seconds** in the disposable clone. Both
syntax rejection (lint-staged) and a valid-but-failing staged test (check:fast)
blocked commits without moving HEAD; a successful hook preserved an unstaged
hunk while committing the staged hunk. Product/package selections may take
longer because their dependency builds and dependent typechecks are real.

The API Ruff and upstream `SECURITY.md` formatting violations are covered only by
the exact, blob-guarded exemptions above. Missing links have no exemption.

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
evidence put .kitchen/evidence/<file> --ticket <ticket> --note '<verified result>' --markdown
```

Add `--pr <url>` when a PR exists. Keep textual outcomes beside links because uploaded
evidence expires. The Ubuntu `birdplane-checks / check-full` lane runs this same L2
command on every PR targeting `birdplane` and every push to it, including docs-only
changes. Existing focused lanes remain enabled. CI has no deploy/publish step.

The first GitHub run of the new full-gate workflow occurs on the PR. Its green
`birdplane-checks / check-full` result is a merge precondition and cannot be
inferred from Coolify results. The ephemeral GitHub runner reclaims preinstalled
toolchains/images before installation and prints free disk before/after; shared
Coolify resources must never be pruned this way.
