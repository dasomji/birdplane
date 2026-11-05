# Upstream update checklist

Use this checklist for every Plane upstream update, before merging the update
branch into `birdplane` or deploying it. Review temporary fixes even when Git
reports no merge conflicts: an upstream fix can make a local patch redundant
without touching the same lines.

## For each update

- [ ] Record the current upstream baseline and the target release tag and commit
      in the update PR. Follow the branch workflow in [BIRDPLANE.md](../../BIRDPLANE.md).
- [ ] Review upstream release notes, migrations, and compatibility changes.
- [ ] Review every active entry in the temporary-fix register below. Check its
      linked upstream discussion, then inspect the implementation **in the target
      release**. A closed issue or merged PR alone does not establish that the chosen
      release contains an equivalent fix.
- [ ] For each entry, record **retain**, **replace with upstream**, or **adapt**
      in the update PR, with the target commit, evidence, and verification results.
      If upstream coverage is incomplete, retain the needed local behavior and
      record the gap.
- [ ] When upstream covers a fix, remove the redundant local implementation
      in the update branch and run the behavior regression tests against the
      upstream implementation. Keep useful regression tests; remove duplicates
      only when upstream tests cover the same behavior.
- [ ] Review the remaining fork diff for other temporary workarounds missing
      from this register. Add any discovered entries. This register is not an
      exhaustive inventory of Birdplane features.
- [ ] Test the update with a restored backup and check Birdplane's MCP, filters,
      recurrence, and editor behavior. Follow the [deployment guide](README.md)
      for backups, rollout, and rollback.
- [ ] Update the upstream baseline in `BIRDPLANE.md`. Mark replaced entries
      retired, recording the upstream release/commit and local removal commit or
      PR. Preserve that history so the workaround is not accidentally reintroduced.

## Temporary-fix register

Add an entry whenever introducing a workaround intended to disappear once
upstream provides the behavior. Include its reason, upstream links, affected
code, removal condition, and verification. Permanent Birdplane features do not
belong here solely because they differ from upstream.

### Project publish authorization (SECUR-247)

- **Status:** retired on 2026-10-29 by the v1.4.3 update (branch
  `sync/upstream-v1.4.3`); **replace with upstream**.
- **Upstream:** [fix #10034](https://github.com/makeplane/plane/pull/10034),
  commit `dc93e1699c7d6e770900c17fc24d04c4e89254e0`, included in v1.4.3
  (`37a15d99231042b3ff5a4401fed479fdbec9effe`).
- **Evidence:** after merging v1.4.3, `apps/api/plane/app/permissions/project.py`,
  `apps/api/plane/utils/permissions/project.py`,
  `apps/api/plane/app/views/project/base.py`, and
  `plane/tests/contract/app/test_deploy_board_project_scope_app.py` are
  byte-identical to the v1.4.3 tag (`git diff v1.4.3 -- <files>` is empty).
  No separate local implementation remains.
- **Verification:** keep running
  `plane/tests/contract/app/test_deploy_board_project_scope_app.py`; it is now
  upstream's own regression test.

### MinIO release image unavailable

- **Status:** retired on 2026-10-29 by the v1.4.3 update (branch
  `sync/upstream-v1.4.3`); **replace with upstream's choice**. The owner chose
  to adopt Silo. Retirement takes effect when that branch is deployed.
- **Reason it existed:** the official Docker Hub and Quay image for MinIO
  `RELEASE.2025-09-07T16-13-09Z` cannot be pulled; its binary download returns 410. `Dockerfile.minio` built that exact source release (commit
  `07c3a429bfed433e49018cb0f78a52145d4bedeb`). The file is kept for rollback.
- **Replacement:** `docker.io/pgsty/silo:RELEASE.2026-09-16T00-00-00Z`, index
  digest `sha256:635197cb9f36d01bee221d34d1c7d7960f6a95c48b0b6c01d99cd13bdae51a46`,
  as pinned by upstream Plane v1.4.3 (#9963). Silo is PGSTY's maintained MinIO
  fork; its [migration guide](https://silo.pigsty.io/compatibility/migration/)
  describes an in-place image swap with unchanged object layout, `.minio.sys`,
  `MINIO_*` variables, and server flags. Only the legacy `fs` backend is rejected.
- **Pre-switch inspection (2026-10-29, read-only Coolify task):** production
  `.minio.sys/format.json` is `xl-single`; MinIO runs as root (uid 0) and the
  data is root-owned; one bucket, `uploads`, holds 8 objects (about 3.4 MB).
  The Silo image also runs as root and translates `server ...` to `silo server`.
  No data migration is required.
- **Rollout:** Silo may update `.minio.sys` metadata, so an older MinIO cannot be
  assumed to read the volume afterwards. Before deploying, stop `plane-minio`,
  archive the whole uploads volume (including `.minio.sys`) with ownership
  preserved, record every object's key, size, and SHA256, and keep that archive
  as the rollback point. Never run MinIO and Silo against the volume at once.
- **Verification:** after deployment confirm the running image digest, that the
  `uploads` bucket and all objects match the recorded keys, sizes, and SHA256,
  and that uploading, viewing, and deleting a disposable attachment work in
  Birdplane. Check `silo` logs for metadata or format warnings.
- **Rollback:** restore the pre-switch volume archive and redeploy the previous
  `compose.yml` (built from `Dockerfile.minio`); reconcile any uploads made in between.

### Project display names containing hyphens

- **Status:** active local fix. BIRD-20 records merge and deployment on 2026-09-16;
  this is historical ticket evidence, not a fresh runtime inspection.
- **Tracking:** BIRD-20.
- **Reason:** upstream applies the ticket-identifier punctuation blacklist to
  display names, rejecting creation and rename of names such as `me-tracker-ts`.
- **Upstream:** [issue #9226](https://github.com/makeplane/plane/issues/9226),
  [hyphen-specific issue #9280](https://github.com/makeplane/plane/issues/9280),
  and [proposed fix #9341](https://github.com/makeplane/plane/pull/9341).
  The [maintainer's response](https://github.com/makeplane/plane/issues/9226#issuecomment-4908346539)
  permits hyphens but rejects simply removing all name validation. Follow any
  replacement PR linked from that discussion.
- **Local implementation:** `FORBIDDEN_NAME_CHARS_PATTERN` in
  `apps/api/plane/db/models/project.py`, used by the project serializers in
  `apps/api/plane/api/serializers/project.py` and
  `apps/api/plane/app/serializers/project.py`.
- **Remove when:** the target upstream release supports creating and renaming
  hyphenated project names through both public and browser APIs, while retaining
  appropriate identifier validation. Compare any broader validation changes
  explicitly rather than assuming a matching issue title means equivalence.
- **Verify after removal:** run
  `plane/tests/contract/api/test_projects.py` and
  `plane/tests/contract/app/test_project_app.py` in the backend test stack.
  The hyphen regression tests cover creation, rename, and rejection of a
  hyphenated ticket identifier. Run the MCP suite as well and verify project
  creation through MCP against the candidate backend.
- **Separate concern:** the MCP error-message improvement in
  `apps/mcp/sikku/plane.py` is not the hyphen workaround. Reassess it against
  upstream's error format; do not automatically remove useful diagnostics
  when retiring the backend patch.
- **Rationale and lineage:** [original validation PR #8529](https://github.com/makeplane/plane/pull/8529)
  introduced a shared blacklist. Its committed identifier regex includes hyphens;
  the local display-name regex permits them while retaining all other existing
  restrictions and preserving identifier validation. Underscores were already
  allowed. The maintainer response linked above favors targeted validation over
  removing every name restriction. Do not infer technical necessity for banning
  display-name hyphens from that discussion.
- **Historical outcome (2026-09-16):** investigation initially recorded 36
  public/browser contract tests and 33 MCP tests passing. BIRD-20 subsequently
  records merge/deployment of `78d893e250b61d3d52bc0d7e608dc9c8d236b799`, successful
  live MCP project creation and disposable ticket cleanup. September's initial
  “not deployed” statement is superseded. These are dated outcomes, not receipts
  for a future update.
- **Last upstream review:** v1.4.3 (2026-10-29): **retain**. The tag's
  `apps/api/plane/db/models/project.py` still has only
  `FORBIDDEN_IDENTIFIER_CHARS_PATTERN` (which includes `-`) and applies it to
  names, so hyphenated names would be rejected again without this patch.
  Record the next reviewed release, outcome, and evidence here.

### Upstream verification exemptions

- **Status:** active; BIRD-34.
- **Reason:** selected upstream source has three API Ruff `F401` diagnostics and
  `SECURITY.md` formatting drift. Exact, blob-guarded exceptions preserve upstream
  files without waiving any other diagnostic or formatting failure.
- **Upstream:** the selected release in the fork-owned
  [exemption register](../../scripts/kitchen/upstream-exemptions.json), currently
  v1.4.3. This register is the single source of truth for the release ref read by
  the exemption library and CI tag fetch.
- **Local implementation:** `scripts/kitchen/upstream-exemptions.json`,
  `scripts/kitchen/lib/upstream-exemptions.mjs` and
  `scripts/kitchen/check-upstream.mjs`; see the
  [verification contract](../../docs/agents/verify.md#per-component-justified-exceptions).
- **Re-pin during an upstream update only:** inspect every entry against the
  target release, including whether its file changed upstream. For each changed
  upstream file, either the new upstream file still has the exact registered
  violation (same rule, symbol/message and location), in which case update
  `upstreamRef` and `upstreamBlob`, or it no longer does, in which case delete the
  entry and fix any unregistered violation normally. Verify each retained blob
  with `git rev-parse <tag>:<path>` and confirm the fork file is byte-identical to
  that target upstream blob. Advance every retained entry's `upstreamRef` to the
  same target tag, including unchanged files; verify their blobs too. Never pin
  a fork-modified file. Record retain/remove decisions and evidence in the update
  PR; a changed diagnostic does not justify expanding the register.
- **Remove when:** upstream eliminates each exact violation, or the file becomes
  fork-modified and must satisfy the normal check. Remove stale entries as they
  disappear; retire this workaround when the register is empty.
- **Regression checks:** run `node scripts/kitchen/run-tests.mjs
scripts/kitchen/upstream-exemptions.test.mjs scripts/kitchen/fast.test.mjs`,
  then the unfiltered `pnpm check:full`. Confirm `api-ruff` and `root-docs-format`
  authenticate every retained blob/tag and reject stale, changed, duplicate or
  additional violations. API Ruff remains check-only at L2; L1 defers via
  `apiAtL2`.

## Agent verification routing

Use the [verification guide](../../docs/agents/verify.md) for current gate commands
and the [doors](../../docs/agents/doors.md) for deployment/data review boundaries.
The [fork-boundary ADR](../../docs/adr/0001-preserve-fork-boundaries-and-selected-releases.md)
records the separate-file policy and inherited-document exception.
