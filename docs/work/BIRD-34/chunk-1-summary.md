# BIRD-34 chunk 1 — documentation and repository contracts

## Scope and decisions

Implemented on Coolify from `55a18ee93bfe6bbd0d27c9612a4265ca69c8da0b`, branch
`t3/migrate-birdplane-kitchen-layout`. No production operations, Plane writes,
push, PR creation, workflow changes, or product-data moves. Review mode remains
**evidence**; Daniel reviews and merges. The owner integrates other chunks,
runs applicable later ladder rungs, carries the dated outcomes below into the PR,
and removes `docs/work/BIRD-34/` before merge.

The v1.4.3 tag is `37a15d99231042b3ff5a4401fed479fdbec9effe`, an ancestor of the
starting HEAD; package version, selected-release docs and production image pins
agree. It identifies source ancestry, not freshly inspected running production.
Explicit `gh repo view dasomji/birdplane` confirms default `birdplane`.
Current clone configuration resolves the fork; setup's earlier upstream-targeting
observation remains a real gotcha for unconfigured clones.

New ADRs record fork boundaries/selected-release updates (including the scoped
lean-AGENTS exception) and production storage isolation. Root AGENTS retains its
inherited Commands/Code Style/Backend tests body and reduces fork content to
routing, mapping and unusual facts. The duplicate URL is gone. Existing backup
rules already cover the root's detailed paragraph; they remain in `backups.md`.
README's inherited upstream body, replaced before this ticket, is restored from
v1.4.3. CONTRIBUTING's scattered fork edits move into a delimited section.
Range-ignore comments protect those inherited bodies from formatter churn; fork
sections remain checked. CLAUDE wrappers are regular files with exactly
`@AGENTS.md` plus newline; the existing ignore rule requires force-adding these
owned files (no `.gitignore` edit).

No out-of-scope document was invented: forum scouting is not an accepted feature
commitment or a sourced rejection. Existing product contracts remain close to
code; the glossary links PQL and recurrence semantics instead of duplicating them.
The proposed doors/opt-in take effect only after Daniel merges and never authorize
this migration PR. Release pushes are production triggers; docs-only extraction
is reversible when the resulting deployment does not alter runtime behavior.

## Inventory — 19 original fork-owned documents, counted once

All classes refer to the original source, even when it mixed durable knowledge
and dated proof. Producer → reader is stated for each source. New work files and
new contract files are outside this original denominator.

| Source                                                          | Class; producer → reader                                     | Action / destination                                                                                                                                        |
| --------------------------------------------------------------- | ------------------------------------------------------------ | ----------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `AGENTS.md`                                                     | Durable; upstream/fork maintainers → agents                  | Keep inherited body; lean delimited fork section routes to agent guides, glossary, ADRs, backups and update register.                                       |
| `README.md`                                                     | Durable; maintainers → contributors/users                    | Restore inherited body; small delimited fork identity/license/routing section. Fork compatibility detail lives in `BIRDPLANE.md`.                           |
| `BIRDPLANE.md`                                                  | Durable; fork maintainers → contributors/operators           | Retain baseline and AGPL/fork notices; correct object-storage name to Silo, link agent guides, preserve compatibility explanation.                          |
| `CONTRIBUTING.md`                                               | Durable; upstream/fork maintainers → contributors            | Preserve inherited guide; move fork clone/PR instructions into a small delimited section with guide links.                                                  |
| `apps/api/plane/utils/filters/README.md`                        | Durable; filter maintainers → API/MCP developers             | Retain product contract; link-only glossary/verification additions.                                                                                         |
| `apps/mcp/README.md`                                            | Durable; MCP maintainers → clients/developers                | Retain shipped interface; link-only development/verification/glossary additions.                                                                            |
| `apps/mcp/sikku/skills/plane-project-management/SKILL.md`       | Durable shipped product asset; MCP packaging/server → agents | Untouched; guidance packaging contract retained.                                                                                                            |
| `deployments/birdplane/README.md`                               | Durable; operators → deployers                               | Keep legacy topology clearly labeled, rate rollback/no-old-database-restore rule, repair retired-report reader and add isolated-guide links.                |
| `deployments/birdplane/backups.md`                              | Durable; backup implementation/operators → operators         | Retain transfer/restore/notification rules; explicitly keep private product storage outside worktrees. Root routes here.                                    |
| `deployments/birdplane/filters.md`                              | Durable; feature maintainers → users/operators               | Keep semantics; reconcile source baseline to v1.4.3, remove unbounded tool-count claim, link complete verification.                                         |
| `deployments/birdplane/recurrence.md`                           | Durable; feature maintainers → users/operators               | Keep contract, permissions and rollback; replace stale v1.4.2/latest-master claim with selected v1.4.3 baseline and guide links.                            |
| `deployments/birdplane/git-compose.md`                          | Durable mixed; operators → deployers                         | Keep deployment/raw-Compose/external-volume/rollback guidance; extract cutover outcome below, retain isolation rationale in ADR 0002, retire dated section. |
| `deployments/birdplane/project-name-validation.md`              | Durable mixed; investigation → update owners                 | Consolidate rationale, upstream lineage and dated outcome into the maintained temporary-fix register; retire separate investigation.                        |
| `deployments/birdplane/responsive-audit.md`                     | Durable; capture maintainers → verifiers                     | Untouched; owned by chunk 3, including evidence/link changes.                                                                                               |
| `deployments/birdplane/upstream-update-checklist.md`            | Durable; maintainers → upstream-update reviewers             | Keep register/history/removal checks; consolidate hyphen investigation, supersede stale not-deployed claim, add agent routing.                              |
| `deployments/birdplane/api-rate-limit-2026-10-01.md`            | Work-scoped; rollout operator → reviewers                    | Retire completed BIRD-25 report after preserving rate-only rollback in deployment guide/ADR 0002 and dated outcome below.                                   |
| `deployments/birdplane/filter-verification-2026-09-11.md`       | Work-scoped; rollout verifier → reviewers                    | Retire completed report; outcome below and migration-isolation/cleanup notes for verify.md owner.                                                           |
| `deployments/birdplane/verification-2026-09-11.md`              | Work-scoped; recurrence verifier → reviewers                 | Retire completed report; outcome below and real-worker/cleanup notes for verify.md owner.                                                                   |
| `docs/birdplane/community-edition-forum-findings-2026-09-11.md` | Work-scoped; forum scouts → feature planners                 | Retire dated scouting; implemented PQL/filter work stays in product contracts; unresolved candidates remain explicit proposed investigations below.         |

## Dated textual outcomes to carry into the PR

These summarize the retired sources and read-only ticket reconciliation on
2026-11-05. They are historical reports, not same-head verification receipts.
No private configuration/backup locations or credentials are reproduced.

- **API rate limit, 2026-10-01 (BIRD-25, Done):** report records all four backend
  service settings changed from 60 to 300 requests/minute with runtime
  allowance/rejection/independent-key/expiry checks passing and public/MCP health
  HTTP 200. Three unit tests passed; polling briefly saw 503 during recreation,
  then five observed rounds had no errors. Existing identities were preserved;
  downloaded database restore and upload checksum verification were reported.
  Rollback changes rate settings only, never an old database restore over writes.
- **Filters, 2026-09-11:** report records 17 backend, 25 MCP and two frontend
  state tests passing, plus targeted types, production web build and focused CI.
  A migrationless reused test DB caused the first migration run to fail;
  explicit recreation and a migration-backed rerun passed. Isolated restored-data
  browser checks verified operators and persistence; 14 small-fixture live MCP
  checks passed, including pagination/negation/date behavior. Disposable tickets,
  labels and project were removed and absence confirmed. Old tool counts and
  small-fixture timings are retired, not current catalog/performance claims.
- **Recurrence, 2026-09-11 (BIRD-15, Done):** report records seven backend and 11
  MCP tests passing, isolated restore plus additive migration, browser checks,
  deployment/health checks and actual Celery generation. Pause/resume/edit/end,
  copied fields/due-date shift and schedule deletion preserving a generated ticket
  were checked. Test schedule and tickets were removed and absence confirmed.
- **Forum scouting, 2026-09-11:** dated staff statements distinguished plan
  restrictions, feature requests and bugs; they did not establish all current CE
  entitlements. Negative filters and relative-date PQL are now implemented in
  local contracts/code. Workspace-view favorites and cycle filtering remain
  candidates to investigate below; no feature commitment or rejection was made.
  Other scouting topics (mobile/desktop apps, importers/types, timers, private
  wiki, cross-project cycles, custom-property columns, templates, burndown,
  OAuth, AI and governance) were observations, not accepted requirements. Their
  historical source remains available in git; do not promote it to current claims.
- **Git cutover, 2026-10-02 (BIRD-27, Done):** report records a release merge push
  triggering a completed Git-connected deployment, PR previews disabled, and
  old service retained stopped. Downloaded DB restore passed; two workspace,
  24 project and 229 issue identities (including deleted rows) and six upload
  objects were preserved; no pending migrations. Signed-in checks covered five
  layout selectors, List/Calendar/Spreadsheet/Gantt rendering and Project grouping.
  Durable deployment/rollback rules remain in `git-compose.md` and ADR 0002.
- **Hyphen investigation, 2026-09-16 (BIRD-20, Done):** initial investigation
  reported 36 public/browser contract and 33 MCP tests passing. The ticket now
  records merge/deployment at `78d893e250b61d3d52bc0d7e608dc9c8d236b799`, successful
  live MCP creation of a hyphenated project and disposable ticket cleanup. The
  initial not-deployed claim is obsolete. Current code still separates display
  names from identifier validation; v1.4.3 lacks that fix. Rationale, upstream
  links, removal condition and regression checks stay in the update register.

## Open requirements and proposed Plane follow-ups — do not create here

Read-only `list_issues` returned the complete BIRD project page. BIRD-25, BIRD-27,
BIRD-20, BIRD-15 and the filter/layout follow-on BIRD-28 are Done. No writes were
made. Preserve BIRD-33 and BIRD-26 as existing open work; do not duplicate them.

- **Existing BIRD-33, Todo — resolve part-2 scope before implementation.** Its
  description still requires workspace-configurable default state sets,
  list/create/update MCP tooling and idempotent multi-workspace backfill; comments
  abbreviate defaults/create/list and add the local webhook route. Acceptance:
  agree the remaining scope; preserve custom states, ordering and initial-state
  semantics; test UI/API/MCP project creation, workspace isolation and any backfill
  idempotency in disposable storage; verify narrowly approved webhook acceptance
  and actual worker delivery plus negative targets. Do not replay completed
  production part 1. Current DEFAULT_STATES still lacks In Review; current BIRD
  metadata includes it in group `started`, confirming these are separate facts.
- **Proposed investigation: workspace-view favorites.** Source candidate:
  [dated forum thread](https://forum.plane.so/t/select-where-to-quick-link/44).
  Current `WorkspaceViewViewSet` does not annotate favorite status, while project
  views do; workspace list items expose Edit/Delete, and generic favorites storage
  exists. This is bounded source evidence, not an end-to-end failure proof.
  Acceptance: reproduce the exact workspace-view action and persistence in an
  isolated account, audit shared menu/favorite permissions and decide whether a
  gap remains; if so specify create/remove/reload and workspace-isolation tests.
- **Proposed investigation: cycle selection in workspace Views.** Source candidate:
  [dated forum thread](https://forum.plane.so/t/how-can-i-make-a-cycle-filter-in-workspace-view/103).
  The backend annotates cycle IDs and project filter constants include cycles;
  this does not prove workspace-view picker availability. Acceptance: audit the
  `EIssuesStoreType.GLOBAL` rich-filter configuration and reproduce selection,
  save/reload, positive/negative matching and permissions across projects; close
  as supported if those pass, otherwise propose a separately signed-off change.
- Relative dates need **no duplicate follow-up**: current
  `apps/api/plane/utils/filters/pql.py`, validation endpoint and PQL/filter contract
  implement calendar and hourly cases. Existing unrelated admin startup BIRD-26
  remains Todo; this chunk neither diagnoses nor changes it.

## Notes for verify.md / development.md owners

- Link targets to your two guides are intentional integration dependencies; this
  chunk must not create your files. Run link validation after integration, including
  ADR and root routing. `check:full` remains blocked until chunk 2 measures green.
- Retired filter report's reused migrationless database failure: recreate the
  disposable test database and use `--migrations --create-db`; do not inherit
  pytest's migrationless/reuse defaults as migration proof. Cover all applicable
  API discovery and SSRF modules, not only the old selected recurrence list.
- Keep test/preview resources and data outside worktrees, unique and owned; never
  mount production external volumes or use production Compose. Restore the
  downloaded file with `--exit-on-error`; count/hash match precedes acceptance.
- Verify real Celery generation plus pause/resume/edit/end and deletion preserving
  generated tickets. Track every disposable schedule/ticket/label/project/session;
  confirm absence after cleanup, wait for terminal cleanup results and propagate
  cleanup errors. Historical production fixture operations grant no new authority.
- Keep existing account/auth/permission boundaries. Use only isolated dev/test
  accounts for seeds. For webhook tests cover full serializer/URL validation,
  pinned transport, redirect refusal and real worker delivery; no real token URL
  in source/logs. Production webhook switching is separate authorized work.
- Existing backup guide already covers diagnostic failures/alerts, disabled task
  execution, socket/noninteractive clients and truncated-log transfer hazards.
  Link it instead of copying the operational paragraph back into AGENTS.

## Memory coverage, holds and verification limits

Coolify name-based discovery found two Birdplane aliases under
`/home/dev/.claude/projects/`: `-home-dev--t3-worktrees-birdplane-sync-upstream-v1-4-3`
and `-home-dev--t3-worktrees-birdplane-t3-105d33e0`; neither has a `memory/`
directory. No memory alias symlinks were found in the bounded discovery. The
primary Kitchen clone `/home/dev/Development/chefs-kitchen` has neither
`memories/` nor `memories/README.md`. No contents were copied/deleted and no
settings changed; keep automatic memory disabled. Mac remains uninspected,
with no known Mac-only source. There are no inspected memory originals to
recommend deleting; any later-discovered source requires its own extraction.
Ignored environments, credentials, runtime mounts and every possible ignored
store were not audited. No product data was found in the owned documentation
scope; that is not a whole-machine absence claim.

Holds: the two other-owned guide targets are absent in this chunk; the complete
gate, hook rejection proof, L2/L3/L4 and evidence migration belong to later chunks
and remain unverified here. The existing pre-commit hook is lint-staged only;
its success is not a claim that the new `check:fast` contract exists. Root agent
instruction changes have no blanket later-rung skip under ladder. Chunk 3 owns
responsive evidence sanitization/upload and source retirement. No new out-of-scope
or feature-policy decision is implied by historical report retirement.

The focused link check inspected 90 added/changed local references: 67 resolve;
23 references share the two pending other-owned guide targets. This is an explicit
failed integration check, not a waived green result. L0 checks and the existing
hook's L1 result are reported with the final commit in the handoff receipts. Inherited AGENTS bytes, restored README/CONTRIBUTING bodies,
29 unchanged upstream documents, shipped MCP guidance and upstream workflows are
checked explicitly. No runtime behavior was changed or tested in this chunk.
