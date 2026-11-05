# Mobile and tablet audit

BIRD-29 fixes accidental horizontal list scrolling and responsive navigation,
headers, settings controls and side panels. It also fixes archive lists that
remain in their loading state after a direct visit.

The BIRD-34 migration PR's evidence summary contains the historical audit's
sanitized downloads and textual results; its links expire on 2026-12-05. The
originals stay in git history: `git show d83d613d1:reports/responsive-audit/<file>`
(for example `report.html` or `before.json`). Generated evidence is no longer
tracked in git; keep textual outcomes in each PR.

All four producers default to `.kitchen/evidence/responsive-audit/` relative to
the repository root, regardless of the current working directory. The HTML
report embeds the original PNGs, works offline, filters comparisons by
device/finding/page and opens images at a larger size. The sibling manifests
preserve measurements and capture checks. Screenshots use 390 × 844 and
768 × 1024 CSS pixels. Interaction checks cover 320, 360, 390, 414, 768, 820,
1024, 1280 and 1440px, with additional iPhone 13 and iPad Mini touch/user-agent
emulation.

## Reproduce

Use a disposable local API/database, the web production build, and the live
collaboration service. Follow the repository's [verification guide](../../docs/agents/verify.md)
for the current verification contracts. Never run the fixture/audit against
production: layout selection can update the audit user's display preferences.
Use identical seeded data for a frozen original build and the changed build.
The historical run used original commit `5797ba4c5` and branch
`fix/mobile-tablet-layout-audit`; choose and record both SHAs for a new run.

Install Playwright in your development tooling, or point `PLAYWRIGHT_MODULE` to
its ESM entry. The `AUDIT_FIXTURE` file must contain:

```json
{
  "cookieName": "sessionid",
  "cookie": "DISPOSABLE_LOCAL_SESSION_ONLY",
  "user": "USER_UUID",
  "projects": [
    {
      "id": "PROJECT_UUID",
      "cycle": "CYCLE_UUID",
      "module": "MODULE_UUID",
      "view": "PROJECT_VIEW_UUID",
      "issue": "ISSUE_UUID"
    }
  ],
  "view": "WORKSPACE_VIEW_UUID",
  "page": "PAGE_UUID",
  "archivedIssue": "ARCHIVED_ISSUE_UUID",
  "webhook": "DISABLED_WEBHOOK_UUID",
  "invitation": "INVITATION_UUID"
}
```

The default workspace slug is `audit` and the detail identifier is `FLIGHTCTL-1`.
Seed long titles, labels, dates, assignees, cycles and modules. Set the invitation
token to `disposable-local-invitation`; do not accept it during the audit. Provide
an inactive webhook with a placeholder URL. Keep fixtures and session files
outside the repository and never embed them in the report or upload them.

Run from the repository root:

```bash
export AUDIT_FIXTURE=/tmp/disposable-audit/session.json
export PLAYWRIGHT_MODULE=/path/to/playwright/index.mjs
export AUDIT_BASE_URL=http://localhost:18030
node deployments/birdplane/responsive-audit.mjs before

export AUDIT_BASE_URL=http://localhost:18031
node deployments/birdplane/responsive-audit.mjs after
node deployments/birdplane/verify-responsive.mjs
AUDIT_TOUCH=1 node deployments/birdplane/verify-responsive.mjs
node deployments/birdplane/verify-scroll-surfaces.mjs
python3 deployments/birdplane/build-responsive-report.py
```

Set `AUDIT_OUTPUT_DIR` to use another directory for **all four commands**. Relative
values resolve from the repository root; absolute values stay absolute. Each
command also retains its optional positional output directory, which takes
precedence over the environment variable (`responsive-audit.mjs before DIR`,
`verify-responsive.mjs DIR`, `verify-scroll-surfaces.mjs DIR`, and
`build-responsive-report.py DIR`). The report builder reads manifests/PNGs and
writes `report.html` in that same directory. Keep every override outside tracked
paths. Interaction-failure screenshots also go into the chosen output directory.

Use `--help` for usage and `--print-output-dir` for a dry run without fixtures,
Playwright or input files. For example:

```bash
node deployments/birdplane/responsive-audit.mjs before --print-output-dir
node deployments/birdplane/verify-responsive.mjs --print-output-dir
node deployments/birdplane/verify-scroll-surfaces.mjs --print-output-dir
python3 deployments/birdplane/build-responsive-report.py --print-output-dir
```

For a retake, set `AUDIT_CASES` to comma-separated case names. It replaces those
entries while preserving the other captures. Run captures for a given phase
sequentially, and keep the served build unchanged during each run.

The runner waits for fonts, network requests and finite animations, rejects page
and API errors, and requires collaborative editor content to be synced. Visually
review every pair after capture: these checks alone cannot distinguish all
loading placeholders from completed content. The original archive loaders are
an explicit exception because they persist after completed requests and an
additional wait; their after captures must show completed empty/content states.

Board/table/timeline surfaces, member and plan-comparison tables, and the tablet
editor toolbar intentionally support internal horizontal scrolling. Normal lists
and viewport-level content do not. The integrations route is unregistered in this
edition; the report records its 404 as unavailable. Separate admin/public-sharing
applications and paid-only feature content are outside this workspace web audit.

## Publish reviewed evidence

Review every PNG, every manifest and the HTML (including inline images) for
secrets and private data before upload. Links are public to their holders. Remove
sensitive material from upload copies, including unnecessary fixture token query
parameters; retain the originals outside git until sanitized uploads succeed.
Record UTC capture dates, both tested SHAs, routes/viewports, pass/fail counts,
notable findings and coverage limits in the PR because the links expire.

The evidence CLI accepts PNG and plain text, but currently rejects HTML, JSON and
archives. Copy reviewed HTML/JSON to a scratch directory outside the repository
with `.txt` appended, keeping their original formats; document any sanitization.
Readers download these files and remove the final `.txt` extension to open the
report offline or parse the manifests. Publish PNGs individually in a batch:

```bash
evidence check
evidence put /tmp/reviewed-audit/report.html.txt /tmp/reviewed-audit/*.json.txt \
  --ticket <ticket> --note "Reviewed responsive report and measurements" --markdown
evidence put .kitchen/evidence/responsive-audit/screenshots/*.png \
  --ticket <ticket> --note "Reviewed mobile/tablet comparisons" --markdown
```

Use the current ticket for subsequent audits. Each file must be under 100 MB.
For a large batch, publish a plain-text index mapping filenames to returned links
and checksums so each capture remains discoverable. Confirm returned links with
`curl -sI --fail URL`, then add the index, report and manifest links and their
expected 30-day expiry date to the PR's textual summary. Remove tracked proof
only after sanitized uploads and link checks succeed; never rewrite history.
