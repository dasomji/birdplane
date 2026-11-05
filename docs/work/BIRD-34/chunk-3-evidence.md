# BIRD-34 chunk 3 — responsive-audit evidence

Review mode: evidence. Preservation performed on Coolify on 2026-11-05 from
`55a18ee93bfe6bbd0d27c9612a4265ca69c8da0b`. This is migration of historical
BIRD-29 proof, not a new responsive audit of the migration branch.

## Preserved results

- Inventory: **335 files, 42,219,471 bytes**: one HTML report, six JSON manifests,
  328 PNGs. Only this evidence subtree was tracked under `reports/`; no unrelated
  tracked report content was removed. No history rewrite.
- **82 page/state scenarios**, each at **390 × 844** and **768 × 1024** CSS pixels,
  in both before and after phases: **164 pairs / 328 screenshots**.
- Routes/states include workspace home, drafts, work/profile views, stickies,
  notifications, projects/archives, workspace and saved views, list/board/calendar/
  table/timeline layouts, work-item detail/properties, cycles/modules and analytics,
  collaborative pages/outline, intake, workspace/project/profile settings,
  webhook controls, auth, onboarding, invitations, navigation and create modals.
- Capture manifests: **328/328** have no recorded page errors; readiness is complete,
  fonts loaded, zero unfinished visible images and zero finite animations. Both
  phases have zero document-width overflows under the audit's >2px tolerance;
  this does not imply there were no internal layout defects.
- Non-touch interaction runs: **9 passed / 0 failed**, at **320, 360, 390, 414,
  768, 820, 1024, 1280, 1440px**. Each records ten checks: virtualized list,
  navigation overlay/close, search panel, profile settings navigation, password
  inputs, member actions, webhook controls, work-item properties, profile details,
  and cycle/module analytics open/close.
- Touch runs: **2 passed / 0 failed**, at 390px (iPhone 13) and 768px (iPad Mini).
  Intentional horizontal-scroll runs: **6 passed / 0 failed** (board, table,
  timeline at both screenshot widths). All six moved scrollLeft to 100px while
  retaining document bounds. Ordinary lists must fit their containers.
- The report classifies **90 pairs related to fixes**, **72 checked without an
  additional finding**, and **2 unavailable** (the integrations route at both
  widths). It records **13 findings fixed**: list sizing; navigation/sidebar;
  top navigation/search; wrapping headers; profile settings; work-item properties;
  profile details; cycle/module analytics; member actions; analytics controls;
  webhook controls; page outline; persistent archive-cycle/module loaders.
- Example measurements: before project-list internal width/scrollWidth was
  **371/554px** on mobile and **500/518px** on tablet; after captures report no
  overflowing internal scroll surfaces on that route. Interaction checks record
  matching list client/scroll widths at all eleven non-touch/touch runs.
- `report-verification.json` records `passed: true`, 164 pairs, 328 decoded images,
  13 findings, plus device/finding/search filters, zoom dialog, mobile document
  bounds and no page errors. The report also claims 47 web unit tests, web/UI
  types/lint and a production build passed historically; those were **not rerun**
  as part of this preservation work and are not current-head receipts.
- **Date/SHA provenance limit:** none of the six manifests contains a capture
  timestamp or commit SHA. The report header says **2026-10-06 19:12 UTC**, based
  on **5797ba4c5** (resolves locally to
  `5797ba4c52d1efbdd5b33d2893c8b0f366d6c3e7`) and branch
  `fix/mobile-tablet-layout-audit`. This is the report's generation date and
  stated original baseline, not proof of a precise timestamp for each capture or
  an after-build SHA. Screenshot UI dates corroborate October 6; the exact
  after-build SHA remains unavailable in the supplied artifacts.

## Sanitize review

Reviewed all 335 files before uploading:

- Parsed all six JSON documents and the HTML's text, attributes, scripts, URLs and
  inline image data. Scanned for email addresses, names, private hostnames/IPs,
  credentials/session cookies, API keys, authorization markers and URL tokens.
- Decoded all **328 inline PNGs** and compared SHA-256 sets with the standalone
  PNGs: every embedded image is byte-identical to a tracked image (295 distinct
  image hashes; duplicates are expected empty/unchanged states).
- Opened **all 82 contact sheets**, four named captures per sheet, spanning every
  before/after mobile/tablet PNG. Inspected full-size before/after tablet webhook,
  onboarding-invite, profile-general and stickies captures to resolve small text.
  The stickies preview is the shipped empty-state illustration, confirmed against
  `apps/web/core/components/stickies/layout/stickies-list.tsx`'s static asset.
- Validated all PNGs decode. They contain only IHDR, IDAT and IEND chunks: no
  embedded text/EXIF metadata and no bytes after IEND.
- Visible identity is the disposable **Audit Tester / audit@example.invalid**
  fixture. Workspace URLs use **localhost:18030/18031**; the disabled webhook
  points to **audit.example.invalid**. API-token pages are empty, password inputs
  are empty and webhook secrets are masked. No exposed session cookie, usable
  credential, private host/IP or real user data was found.
- The onboarding invitation fields show three `frstflt.com` email placeholders.
  Verified these are hardcoded `placeholderEmails` in both onboarding components,
  rendered as the input's `placeholder`, not actual invitees or account data.
- No unsafe artifact was uploaded. Original files were unchanged until uploads
  and download verification succeeded. Exact originals and review scratch remain
  outside git at `/tmp/bird-34-chunk3-bL8tip/originals` (temporary, not durable storage).

The installed CLI rejects HTML/JSON/ZIP file types, so PNGs were uploaded
individually and the report/manifests as UTF-8 `.txt` downloads. Its credential
scanner also rejected the known display-only fixture URL tokens. Sanitized upload
copies of **before.json, after.json and report.html** remove only four
`token=fixture` / `token=disposable-local-invitation` query-parameter occurrences
per file; no image bytes, measurement values, route paths or assertion results
changed. Remove the final `.txt` extension after download. The other four
manifests and all 328 PNGs are byte-identical to their originals. The unsupported
ZIP was not uploaded.

## Uploaded evidence

Uploaded **2026-11-05** with `evidence put --ticket BIRD-34 --note ... --markdown`.
Expected expiry: **2026-12-05** (30-day retention). `evidence check` passed the
credential/bucket and public upload/read/delete probe; bucket lifecycle could not
be independently read using the object token, so the expiry is expected under
the evidence-service contract, not a read-back lifecycle verification.

All **336 returned links** (335 artifacts plus PNG index) returned HTTP 200 via
`curl -sI --fail`. Every uploaded object was also downloaded: all PNG SHA-256
hashes match the tracked originals; the report/manifests/index hashes match the
reviewed upload copies. The PNG index exposes each original image directly.

| Download                                                                                                                                                          | Contents                                                                                                                          |
| ----------------------------------------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------- |
| [report.html.txt](https://evidence.audiopoesis.com/2026-11-05/d8104b73b9a394d5ce3022e3d7c57ce8/report.html.txt)                                                   | Self-contained offline HTML report; 164 comparison pairs and all 328 embedded PNGs. Download and remove the final .txt extension. |
| [before.json.txt](https://evidence.audiopoesis.com/2026-11-05/f910a5a86950e5412862eb1a3cc2aa6c/before.json.txt)                                                   | 164 before captures: route, viewport, layout measurements, readiness and page-error checks.                                       |
| [after.json.txt](https://evidence.audiopoesis.com/2026-11-05/5c21246be3b7605ee81d3637b7cd80c1/after.json.txt)                                                     | 164 after captures with matching coverage and measurement fields.                                                                 |
| [verification.json.txt](https://evidence.audiopoesis.com/2026-11-05/afd73af75ba0412594a26bacfa10e271/verification.json.txt)                                       | Nine desktop-user-agent interaction checks at widths 320–1440px.                                                                  |
| [touch-verification.json.txt](https://evidence.audiopoesis.com/2026-11-05/cf5281fb8da34ee75ccef2df4302158b/touch-verification.json.txt)                           | Two interaction checks with iPhone 13/iPad Mini touch and mobile user-agent emulation.                                            |
| [intentional-scroll-verification.json.txt](https://evidence.audiopoesis.com/2026-11-05/3240286fce54a1d28c244fb7d4d9a41b/intentional-scroll-verification.json.txt) | Six board/table/timeline internal-scroll checks at 390px and 768px.                                                               |
| [report-verification.json.txt](https://evidence.audiopoesis.com/2026-11-05/57b474b09b7c71a686f6ed331962db6e/report-verification.json.txt)                         | Historical report checks: image decoding, filters, zoom, document bounds and page errors.                                         |
| [responsive-audit-png-index.txt](https://evidence.audiopoesis.com/2026-11-05/ef6339a687d3f4152094a7d8030cafec/responsive-audit-png-index.txt)                     | All 328 original PNG filenames, individual public links and original SHA-256 checksums.                                           |

## Implementation and integration notes

- All four producers now default to `.kitchen/evidence/responsive-audit/` from
  the repository root. `AUDIT_OUTPUT_DIR` overrides this consistently; legacy
  positional directories take precedence. Relative overrides are repo-relative;
  absolute overrides stay absolute. The builder reads and writes the same root.
- Added `--help` and side-effect-free `--print-output-dir` to all four. Interaction
  failure screenshots now stay in the chosen output directory; the scroll checker
  creates its output directory when needed.
- Path-resolution dry run covered 24 combinations from an unrelated working
  directory, with no fixtures or Playwright available: default, empty environment,
  relative/absolute environment, and relative/absolute positional precedence.
  All passed. All four help commands, three Node syntax checks and Python compile
  passed. A rebuild from copied originals produced 164 pairs / 13 findings and
  all 328 original embedded images. Focused OxLint and formatting checks pass.
- The commit uses the existing Husky/lint-staged hook. The new `check:fast`/
  `check:full` contracts and `.kitchen/` ignore belong to chunk 2a and are absent
  at this starting SHA. No whole-app L2/L3 claim is made for this chunk; integrated
  verification belongs to chunk 4.
- `responsive-audit.md` now documents paths, reruns, upload limitations/sanitization,
  textual retention and fixture handling; preserves viewport, readiness,
  intentional-scroll and unavailable-edition guidance. Admin/public-sharing apps
  and unavailable paid-only content remain outside workspace web-app coverage.
- **Outside-owned-file follow-up:** the shared `docs/work/BIRD-34/plan.md` retains
  two historical inventory/scope mentions of the retired directory; these are
  not live readers. No other reader outside the owned files needs a link update.
  Chunk 2a must supply the linked `docs/agents/verify.md` and `.kitchen/` ignore.
  Carry this summary into the PR before integration deletes `docs/work/BIRD-34/`.
