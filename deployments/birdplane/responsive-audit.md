# Mobile and tablet audit

BIRD-29 fixes accidental horizontal list scrolling and responsive navigation,
headers, settings controls and side panels. It also fixes archive lists that
remain in their loading state after a direct visit.

The evidence is in `reports/responsive-audit/report.html`. The HTML embeds the
original PNGs, works offline, filters comparisons by device/finding/page and
opens images at a larger size. The sibling manifests preserve measurements and
capture checks. Screenshots use 390 × 844 and 768 × 1024 CSS pixels. Interaction
checks cover 320, 360, 390, 414, 768, 820, 1024, 1280 and 1440px, with additional
iPhone 13 and iPad Mini touch/user-agent emulation.

## Reproduce

Use a disposable local API/database, the web production build, and the live
collaboration service. Never run the fixture/audit against production: layout
selection can update the audit user's display preferences. Use identical seeded
data for a frozen original build and the changed build. This run used original
commit `5797ba4c5` and branch `fix/mobile-tablet-layout-audit`.

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
an inactive webhook with a placeholder URL. Keep session files outside the
repository and never embed them in the report.

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
