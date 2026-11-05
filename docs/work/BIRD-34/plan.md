# BIRD-34 — migrate birdplane onto the Chef's Kitchen layout (pilot)

Skill: migrate (kitchen `skills/migrate/SKILL.md` + `checklist.md`, main `01c8d68`).
Plan source: kitchen `research/33-migration-dry-run-birdplane.md` (dry run 2026-11-05).
Review mode: **evidence**. Daniel reviews and merges. No PR auto-merge, no GitHub
settings changes before Daniel merges (migrate step 8 runs only after merge).

## Baseline (recorded 2026-11-05)

- Origin `https://github.com/dasomji/birdplane.git`; upstream `makeplane/plane`.
- Default branch **`birdplane`** (`gh repo view dasomji/birdplane`). Gotcha: without
  `gh repo set-default`, `gh` in this checkout resolves upstream `makeplane/plane`
  (default `preview`). Set to `dasomji/birdplane` in this clone's git config.
- Work branch `t3/bird-34-migration` from `origin/birdplane` =
  `d83d613d124a26c76bef869d2ada5b644557010f` (dry-run hold: Coolify's old checkout was
  36 commits behind; this baseline is current). Clean status at start.
- Fork-doc inventory at this HEAD against `v1.4.3` (and upstream/preview merge base
  `37a15d9`): **19 fork-owned** (16 added, 3 modified: `AGENTS.md`, `CONTRIBUTING.md`,
  `README.md`), **29 unchanged upstream docs — never migrated**, 335 tracked files under
  `reports/responsive-audit/**` (evidence).
- Plane: BIRD mapping, states Todo/In Progress/In Review/Done and `ready-for-agent`
  verified in the dry run; BIRD-34 In Progress with dispatcher claim `bbb1f797`.
- Memories: no `~/.claude/projects/*birdplane*/memory/` on Coolify; primary kitchen clone
  has no `memories/`. Mac uninspected (no known Mac-only birdplane memories).

## Holds (from ticket)

1. Work from current `origin/birdplane` — satisfied (`d83d613`).
2. `check:full` stays **blocked as an implementation contract** until measured green for
   this monorepo; exceptions are per component and justified, never whole-repo.
3. Upstream-unchanged docs stay byte-identical. Kitchen additions live in separate files.

## Chunks

| #   | Outcome                                                                                                                                                                                                                                                                                                                                                                                      | Owned files                                                                                                                                                                                                                                                                                                                                                                             | Depends on                                | Status                                                                                                                                                                                                                    |
| --- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 1   | Docs and repository contracts: lean fork section of `AGENTS.md` with documented scoped exception and Plane managed block, `CLAUDE.md` wrappers, `GLOSSARY.md`, ADRs, out-of-scope (only if established), `docs/agents/doors.md` + gotcha guides, narrow links in `README.md`/`BIRDPLANE.md`/`CONTRIBUTING.md`; extract then retire the 4 work-scoped docs and dated sections of mixed guides | `AGENTS.md`, `CLAUDE.md`, `packages/tailwind-config/CLAUDE.md`, `GLOSSARY.md`, `docs/adr/**`, `docs/out-of-scope/**`, `docs/agents/**` except `verify.md`/`development.md`, `README.md`, `BIRDPLANE.md`, `CONTRIBUTING.md`, `deployments/birdplane/*.md` except `responsive-audit.md`, `docs/birdplane/**`, `apps/mcp/README.md`, `apps/api/plane/utils/filters/README.md` (links only) | —                                         | todo                                                                                                                                                                                                                      |
| 2a  | Gates: real `check:fast` and `check:full`, pre-commit hook preserving lint-staged, ignored `.kitchen/`, Ubuntu CI on every PR/push to `birdplane`, `docs/agents/verify.md`; measured `check:full` baseline on Coolify                                                                                                                                                                        | `scripts/kitchen/check-*.mjs` + helpers, `package.json` (scripts only, incl. `verify:app` alias), `.husky/pre-commit`, `.gitignore`, `.github/workflows/birdplane-checks.yml`, `docs/agents/verify.md`, isolated API-test override it adds                                                                                                                                              | —                                         | **done** — merged `d1770a3`; fix `4c3faac` adds the pinned upstream-exemption register (3 F401 in two v1.4.3 API views, `SECURITY.md` format) and `CLAUDE.md` negations. Measured 859.9 s at `d1770a3`: 17/20 phases pass |
| 2b  | App verification: `scripts/kitchen/verify-app.mjs` disposable stack, D12 seeding, journeys + failure case, evidence upload; `docs/agents/development.md` (stack, isolated boot/seed/migrations)                                                                                                                                                                                              | `scripts/kitchen/verify-app.mjs` + `scripts/kitchen/verify-app/**`, `docs/agents/development.md`                                                                                                                                                                                                                                                                                        | interface contract fixed in briefs        | **done** — merged `fd51988`; disposable stack, all journeys + failure cases pass in 317 s                                                                                                                                 |
| 3   | Responsive-audit evidence: producers write to ignored `.kitchen/evidence/responsive-audit/`; sanitize and `evidence put` the 335 tracked files with textual outcomes; remove tracked `reports/responsive-audit/**`; update `deployments/birdplane/responsive-audit.md`                                                                                                                       | 4 producers in `deployments/birdplane/`, `deployments/birdplane/responsive-audit.md`, `reports/responsive-audit/**`                                                                                                                                                                                                                                                                     | `.kitchen/` ignore from 2a at integration | **done** — merged `3beed30` (branch `t3/responsive-audit-evidence`); 335 files sanitized, uploaded (expire 2026-12-05), removed; summary in `chunk-3-evidence.md`                                                         |
| 4   | Integration, L2 at integrated SHA, L3 verifier, cross-family L4, retire `docs/work/BIRD-34/`, file-pr                                                                                                                                                                                                                                                                                        | —                                                                                                                                                                                                                                                                                                                                                                                       | 1–3                                       | in progress — integrated at `926a545`                                                                                                                                                                                     |

Interface contract 2a↔2b: `pnpm verify:app` = `node scripts/kitchen/verify-app.mjs`; exit 0 only
when every journey and the failure case pass; non-zero otherwise; prints the tested SHA.
`verify.md` links `development.md#functional-verification` for details.

Shared-file rule: `.gitignore` belongs to chunk 2 only (it ignores `.kitchen/`). Chunk 1
links `docs/agents/verify.md` but chunk 2 writes it.

## Findings / follow-ups

- Chunk 1 restored upstream's README body, reversing BIRD-24's fork branding. Fixed in
  scope: README stays fork-owned with routing links; ADR 0001 records the exception.
- `.gitignore` line `CLAUDE.md` ignores wrappers; chunk 1 force-added both. Chunk 2a/
  integration: add negations for tracked wrappers so future scoped wrappers aren't silently ignored.
- Open candidates from the retired forum-findings doc filed as Backlog investigations:
  BIRD-35 (workspace-view favorites), BIRD-36 (cycle filtering in workspace views).
- Link check: refs to `docs/agents/{development,verify}.md` resolve after integration (root-docs-links pass).
- `check:full` upstream exemptions (pinned blobs, fail closed): F401 x3 in two v1.4.3 API views; `SECURITY.md` format.
- `check:fast` measured 5–7 s for docs commits but 109 s for a staged package/dependent-typecheck trial (> ~60 s target).
- `verify:app` root cause at integration: Vite optimizer invalidation on cold start; verifier now proves login renders and keeps diagnostics.
- `scripts/kitchen/verify-app/browser.test.mjs` (2 tests) skips unless `VERIFY_BROWSER_PACKAGE` is set, so check:full/CI don't execute it; behavior covered by `verify:app`. Reviewer to judge.
- Upload CLI refuses raw check:full logs (lint excerpts trip its credential-pattern scanner); evidence uses phase results + log without lint excerpts.
