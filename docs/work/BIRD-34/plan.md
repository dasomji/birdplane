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

| # | Outcome | Owned files | Depends on | Status |
|---|---|---|---|---|
| 1 | Docs and repository contracts: lean fork section of `AGENTS.md` with documented scoped exception, `CLAUDE.md` wrappers, `GLOSSARY.md`, ADRs, out-of-scope (only if established), `docs/agents/{development,doors}.md` + gotcha guides, narrow links in `README.md`/`BIRDPLANE.md`/`CONTRIBUTING.md`; extract then retire the 4 work-scoped docs and dated sections of mixed guides | `AGENTS.md`, `CLAUDE.md`, `packages/tailwind-config/CLAUDE.md`, `GLOSSARY.md`, `docs/adr/**`, `docs/out-of-scope/**`, `docs/agents/**` except `verify.md`, `README.md`, `BIRDPLANE.md`, `CONTRIBUTING.md`, `deployments/birdplane/*.md` except `responsive-audit.md`, `docs/birdplane/**`, `apps/mcp/README.md`, `apps/api/plane/utils/filters/README.md` (links only) | — | todo |
| 2 | Verification contract: real `check:fast`, `check:full`, `verify:app`; pre-commit hook preserving lint-staged; ignored `.kitchen/`; Ubuntu CI on PRs/pushes to `birdplane`; `docs/agents/verify.md`; measured `check:full` baseline on Coolify | `scripts/kitchen/**`, `package.json` (scripts only), `.husky/pre-commit`, `.gitignore`, `.github/workflows/birdplane-checks.yml`, `docs/agents/verify.md`, test-only config/override files it adds | — | todo |
| 3 | Responsive-audit evidence: producers write to ignored `.kitchen/evidence/responsive-audit/`; sanitize and `evidence put` the 335 tracked files with textual outcomes; remove tracked `reports/responsive-audit/**`; update `deployments/birdplane/responsive-audit.md` | 4 producer scripts, `deployments/birdplane/responsive-audit.md`, `reports/responsive-audit/**` | `.kitchen/` ignore from chunk 2 at integration | todo |
| 4 | Integration, L2 at integrated SHA, L3 verifier, cross-family L4, retire `docs/work/BIRD-34/`, file-pr | — | 1–3 | todo |

Shared-file rule: `.gitignore` belongs to chunk 2 only (it ignores `.kitchen/`). Chunk 1
links `docs/agents/verify.md` but chunk 2 writes it.

## Findings / follow-ups

- (none yet)
