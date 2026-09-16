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

### Project display names containing hyphens

- **Status:** active local fix; prepared on 2026-09-16, not deployed as of that date.
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
- **Research and verification:** [project-name-validation.md](project-name-validation.md).
- **Last upstream review:** 2026-09-16; no retirement decision yet. Record the
  next reviewed release, outcome, and evidence here when performing an update.
