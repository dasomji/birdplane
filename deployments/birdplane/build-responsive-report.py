"""Build a self-contained report from the checked responsive audit evidence."""
import base64
import html
import json
from datetime import datetime, timezone
from pathlib import Path
import sys

root = Path(sys.argv[1] if len(sys.argv) > 1 else "reports/responsive-audit")
before = {row["key"]: row for row in json.loads((root / "before.json").read_text())}
after = {row["key"]: row for row in json.loads((root / "after.json").read_text())}
verification = json.loads((root / "verification.json").read_text())
touch_verification = json.loads((root / "touch-verification.json").read_text())
scroll_verification = json.loads((root / "intentional-scroll-verification.json").read_text())
assert len(scroll_verification) == 6 and all(row["passed"] for row in scroll_verification)
assert before.keys() == after.keys(), "Before and after coverage must match"
assert all(row.get("screenshot") and not row.get("errors") for row in [*before.values(), *after.values()])
assert {row["width"] for row in verification} == {320, 360, 390, 414, 768, 820, 1024, 1280, 1440}
assert {row["width"] for row in touch_verification} == {390, 768}
assert all(row["passed"] for row in [*verification, *touch_verification]), "Interaction checks must pass"
assert all("cycle and module analytics open and close" in row["checks"] for row in [*verification, *touch_verification])
for row in [*before.values(), *after.values()]:
    proof = row["proof"]
    assert proof["ready"] == "complete" and proof["fonts"] == "loaded"
    assert proof["finiteAnimations"] == 0 and proof["images"] == 0

findings = [
 ("F01", "Lists fit their actual container", "Offscreen virtualized placeholders had fixed widths. Tablet rows also kept property groups from shrinking.", "Bound placeholders; stack rows by container width and wrap properties. Horizontal swipes no longer move the list, including after vertical scrolling.", ["project-list", "workspace-list", "list-horizontal-end", "saved-project-view", "profile-assigned"]),
 ("F02", "Navigation preserves the content width", "Two mounted sidebar wrappers toggled the same state twice, leaving the sidebar open on narrow screens.", "Set collapse explicitly below 1024px; open navigation as an overlay, close it reliably, and make hidden navigation inert.", ["home", "navigation-sidebar"]),
 ("F03", "Top navigation and command search stay in view", "The search input and popup used fixed desktop widths, pushing account and help controls outside the viewport.", "Use flexible columns and a bounded popup on narrow screens. Workspace, search, inbox, help and account remain accessible; the GitHub promotion remains on large desktop screens.", ["navigation-search", "projects", "notifications"]),
 ("F04", "Headers wrap instead of clipping actions", "Fixed header heights and shrinking action groups overlapped long breadcrumbs and buttons.", "Allow primary headers and their action groups to wrap. Keep controls from shrinking into each other.", ["workspace-views", "cycles", "modules", "project-views", "saved-workspace-view", "pages", "create-project-modal", "create-issue-modal"]),
 ("F05", "Profile settings use the screen width", "A fixed sidebar and unshrinkable content clipped profile, password and token controls.", "Use a compact page selector below 1024px and flexible content with smaller narrow-screen padding. Verify all five settings pages and selector navigation.", ["profile-settings-general", "profile-settings-preferences", "profile-settings-notifications", "profile-settings-security", "profile-settings-api-tokens"]),
 ("F06", "Work-item properties open without squeezing the detail", "The property sidebar consumed tablet content space and long property values escaped the panel. Closing was also overwritten by an effect.", "Collapse it initially on narrow screens and provide an accessible toggle. Use an overlay and container-aware labels and values; retain manual close state.", ["issue-detail", "issue-properties", "archived-issue-detail"]),
 ("F07", "Profile details collapse fully", "Closed profile panels retained width or moved controls offscreen; tablet navigation could squeeze the main content.", "Remove closed panels from layout, use overlays below 1024px, and expose a working details toggle.", ["your-work", "profile-activity", "profile-details", "profile-created", "profile-subscribed"]),
 ("F08", "Cycle and module analytics stay bounded", "Their side panels opened by default over the list and the module panel exceeded narrow content widths.", "Start collapsed below 1024px, make the analytics toggle available on phones, and cap open panels at the container width.", ["cycle-detail", "module-detail", "cycle-analytics", "module-analytics"]),
 ("F09", "Member actions remain reachable", "The member heading, search, filters and invite action shared an inflexible row, clipping Add member.", "Wrap the controls and allow the search field to shrink. Contain member-table scrolling within the table.", ["workspace-settings-members", "project-settings-members"]),
 ("F10", "Analytics controls wrap", "Customized insights kept several selectors on one line beside a heading, clipping Add Property.", "Wrap section headings and selectors within the available width.", ["analytics-work-items", "analytics"]),
 ("F11", "Webhook key controls fit", "The secret field and regenerate action forced a wider row at tablet widths.", "Allow the row to wrap and the masked field to shrink; verify the regenerate button bounds without invoking it.", ["webhook-detail", "workspace-settings-webhooks"]),
 ("F12", "Page outline is an overlay on narrow screens", "The fixed-width outline reduced the editor to almost no usable space. Closed controls also remained offscreen.", "Use a bounded overlay below 1024px and remove the closed pane from layout. Verify the fully synced editor and outline state.", ["page-outline", "page-detail"]),
 ("F13", "Direct archive visits finish loading", "Archived cycle/module requests succeeded, but the computed lists waited for the unrelated regular-list fetch flag.", "Track archive fetch completion separately. Empty archives now show the intended empty state without pretending regular lists were fetched.", ["archived-cycles", "archived-modules"]),
]
by_name = {}
for code, title, cause, fix, names in findings:
    for name in names:
        by_name.setdefault(name, []).append(code)

h = html.escape

def image(row):
    data = base64.b64encode((root / row["screenshot"]).read_bytes()).decode()
    label = f'{row["phase"].title()} · {row["device"].title()} · {row["name"].replace("-", " ")}'
    return f'<button class="image-button" type="button" aria-label="Enlarge {h(label)}" data-label="{h(label)}"><img loading="lazy" decoding="async" width="{row["measure"]["viewport"]["width"]}" height="{row["measure"]["viewport"]["height"]}" alt="{h(label)}" src="data:image/png;base64,{data}"></button>'

def list_size(row):
    lists = [s for s in row["measure"]["scrolls"] if "vertical-scrollbar relative scrollbar-lg size-full" in s["class"]]
    if lists:
        return f'List width {lists[0]["width"]}px / content {lists[0]["scrollWidth"]}px'
    return "List fits without horizontal overflow"

cards = []
ordered_names = list(dict.fromkeys(name for finding in findings for name in finding[4]))
ordered_names += sorted({row["name"] for row in after.values()} - set(ordered_names))
for name in ordered_names:
    for device in ["mobile", "tablet"]:
        key = f"{device}-{name}"
        b, a = before[key], after[key]
        codes = by_name.get(name, [])
        status = "unavailable" if name == "workspace-settings-integrations" else ("fixed" if codes else "checked")
        if name == "workspace-settings-integrations":
            note = "This route is not enabled in this build; both images show its responsive 404 state. The integration feature itself is outside the available edition."
        elif name in ["workspace-board", "workspace-table", "workspace-timeline"]:
            note = "Wide board/table/timeline content intentionally scrolls inside its own surface. The page and surrounding controls remain bounded."
        elif name in ["workspace-settings-members", "project-settings-members", "workspace-settings-billing"]:
            note = "Member and plan-comparison tables retain intentional internal horizontal scrolling; surrounding controls fit."
        elif name in ["archived-cycles", "archived-modules"]:
            note = "The before loader persisted after its successful request and an additional 10-second wait. It is the diagnosed defect, not a premature capture. The after image shows the completed empty state."
        elif name in ["active-cycles", "workspace-settings-billing"]:
            note = "Captured the available Community/upgrade state. Paid-only content was not enabled."
        elif name.startswith("onboarding-") or name in ["sign-in", "sign-up", "forgot-password", "reset-password", "set-password"]:
            note = "Local identity/profile responses select the relevant auth state. Forms were inspected without sending emails or changing passwords."
        elif name in ["page-detail", "page-outline"]:
            note = "Captured after the collaboration connection synced and editor content loaded. The tablet formatting toolbar keeps intentional internal scrolling."
        elif name == "create-project-modal":
            note = "The modal fits both viewports. Its decorative cover is randomly selected on each opening; a different cover is unrelated to the layout fixes."
        elif codes:
            note = "Related fixes: " + ", ".join(codes) + ". Shared navigation/header changes also apply where present."
        else:
            note = "No additional page-specific defect found. Shared responsive layout fixes were verified where present."
        viewport = a["measure"]["viewport"]
        badges = f'{device.title()} · {viewport["width"]} × {viewport["height"]}'
        metric = ""
        if name in ["project-list", "workspace-list", "list-horizontal-end", "saved-project-view", "profile-assigned", "cycle-detail", "module-detail"]:
            metric = f'<div class="metric"><span>Before: {h(list_size(b))}</span><span>After: {h(list_size(a))}</span></div>'
        cards.append(f'''<article class="comparison" id="{key}" data-device="{device}" data-status="{status}" data-codes="{' '.join(codes)}" data-search="{h(name+' '+note)}">
<div class="card-heading"><h3>{h(name.replace('-', ' ').title())}</h3><span class="badge {status}">{h(badges)} · {status.title()}</span></div>
<p class="note">{h(note)}</p>{metric}<div class="pair"><figure><figcaption>Before</figcaption>{image(b)}</figure><figure><figcaption>After</figcaption>{image(a)}</figure></div>
<details class="proof"><summary>Capture checks and route</summary><p><code>{h(a['url'])}</code></p><p>Both captures: document complete; fonts loaded; 0 unfinished visible images; 0 running finite animations; 0 page errors. Requests settled before capture. After document width: {a['measure']['documentWidth']}px / viewport: {viewport['width']}px.</p></details></article>''')

finding_cards = []
for code, title, cause, fix, names in findings:
    links = ' '.join(f'<a class="evidence-link" href="#{device}-{names[0]}" data-target="{device}-{names[0]}">{device.title()} evidence ↗</a>' for device in ["mobile", "tablet"])
    finding_cards.append(f'<article class="finding"><span class="finding-id">{code} · Fixed</span><h3>{h(title)}</h3><p>{h(cause)}</p><p class="fix">{h(fix)}</p><div class="links">{links}</div></article>')

options = ''.join(f'<option value="{code}">{code} · {h(title)}</option>' for code, title, *_ in findings)
widths = ' · '.join(f'{row["width"]}px' for row in verification)
now = datetime.now(timezone.utc).strftime("%d %B %Y · %H:%M UTC")
html_document = '''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Birdplane mobile & tablet audit</title><style>
:root{font:15px/1.6 system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;color:#172337;background:#edf2f7}*{box-sizing:border-box}body{margin:0}a{color:#086287}header{background:#112a3c;color:white;padding:48px max(24px,calc((100vw - 1240px)/2)) 38px}h1{font-size:clamp(28px,4vw,46px);line-height:1.12;margin:8px 0 16px;letter-spacing:-.04em}h2{font-size:27px;line-height:1.25;letter-spacing:-.025em;margin:32px 0 16px}h3{font-size:18px;line-height:1.35;margin:6px 0 10px}.eyebrow{font-size:12px;font-weight:650;letter-spacing:.14em;text-transform:uppercase;color:#a9dfe9}.intro{max-width:860px;color:#d8e8f1}.stats{display:flex;flex-wrap:wrap;gap:12px;margin-top:26px}.stats span{padding:8px 14px;border:1px solid #3e586b;border-radius:8px;background:#193648}.stats strong{font-size:22px;color:#b4eecc;margin-right:5px}main{max-width:1288px;margin:auto;padding:0 24px 48px}.panel{background:white;border:1px solid #d8e2eb;border-radius:12px;padding:24px;margin-top:24px}.panel p{margin:0 0 12px}.subtle{color:#526579;font-size:13px}.findings{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:16px}.finding{background:white;border:1px solid #d8e2eb;border-radius:12px;padding:22px}.finding-id{font-size:11px;font-weight:750;color:#13703b;letter-spacing:.06em}.finding p{font-size:13px;color:#526579;margin:0 0 12px}.finding .fix{color:#213b4e}.links{display:flex;gap:12px}.evidence-link{font-size:12px;font-weight:650;text-decoration:none}.filters{position:sticky;top:0;z-index:5;background:#edf2f7ee;backdrop-filter:blur(10px);display:flex;align-items:flex-end;flex-wrap:wrap;gap:12px;padding:14px 0;border-bottom:1px solid #cedae4;margin-bottom:20px}.filters label{font-size:11px;text-transform:uppercase;letter-spacing:.07em;color:#526579;display:flex;flex-direction:column;gap:4px}.filters select,.filters input{background:white;border:1px solid #bcccd9;border-radius:7px;padding:9px;font:inherit;text-transform:none;letter-spacing:normal;color:#172337;height:40px;max-width:100%}.filters input{width:210px}.filters select{max-width:350px}#shown{margin-left:auto;align-self:center;font-size:12px;color:#526579}.comparison{background:white;border:1px solid #cedae4;border-radius:12px;margin:0 0 24px;overflow:hidden;scroll-margin-top:118px}.card-heading{display:flex;gap:10px;align-items:center;justify-content:space-between;padding:18px 22px 0;flex-wrap:wrap}.badge{font-size:11px;border-radius:20px;background:#e8eef4;padding:5px 10px;white-space:nowrap}.badge.fixed{background:#e5f4e9;color:#19693c}.badge.unavailable{background:#fff0cd;color:#795100}.note{font-size:12px;color:#526579;padding:0 22px;margin:8px 0 15px}.metric{display:grid;grid-template-columns:1fr 1fr;padding:8px 22px;background:#f2f7fa;font-size:12px;gap:12px}.pair{display:grid;grid-template-columns:1fr 1fr;gap:16px;padding:16px 22px 22px;background:#f7f9fc;align-items:start}.pair figure{margin:0;min-width:0;display:flex;flex-direction:column;align-items:center}.pair figcaption{align-self:stretch;font-size:12px;font-weight:700;margin-bottom:8px}.image-button{display:block;border:1px solid #d6e1e9;padding:0;background:white;border-radius:6px;overflow:hidden;max-width:100%;cursor:zoom-in;box-shadow:0 2px 5px #112a3c0a}.image-button img{display:block;width:100%;height:auto;max-width:100%}.comparison[data-device=mobile] .image-button{max-width:390px}.proof{padding:10px 22px;border-top:1px solid #d8e2eb;color:#526579;font-size:12px}.proof summary{cursor:pointer}.proof code{overflow-wrap:anywhere}.matrix{border-collapse:collapse;width:100%;font-size:13px}.matrix td,.matrix th{padding:10px;border-bottom:1px solid #dfE7ee;text-align:left;vertical-align:top}.matrix th{width:210px;color:#526579;font-weight:500}.pass{color:#13703b;font-weight:700}dialog{padding:16px;background:#112a3c;color:white;border:0;border-radius:10px;max-width:96vw;max-height:96vh}dialog::backdrop{background:#081522dd}dialog img{display:block;max-width:90vw;max-height:83vh;object-fit:contain;width:auto;height:auto}dialog button{background:white;color:#172337;border:0;padding:7px 14px;border-radius:6px;cursor:pointer}dialog .dialog-bar{display:flex;justify-content:space-between;gap:20px;margin-bottom:12px;font-size:13px}.footer{font-size:12px;color:#526579;margin-top:28px} [hidden]{display:none!important}@media(max-width:700px){header{padding:32px 18px}main{padding:0 12px 24px}.findings{grid-template-columns:1fr}.panel{padding:18px}.pair{gap:8px;padding:12px 10px}.card-heading{padding:14px 12px 0}.note{padding:0 12px}.metric{padding:8px 12px}.filters{position:static}.filters label{max-width:100%}.matrix th{width:120px}.badge{white-space:normal}#shown{margin-left:0}}@media print{.filters,.links,dialog{display:none}.comparison{break-inside:avoid}.findings{display:block}.finding{margin-bottom:10px}.pair{gap:12px}header{color:black;background:white}.intro,.eyebrow{color:black}.stats span{color:black;border-color:#aaa}.stats strong{color:#19693c}}
</style></head><body>'''
html_document += f'''<header><div class="eyebrow">Birdplane · Responsive verification</div><h1>Mobile & tablet layout audit</h1><p class="intro">The list now fits its container. The wider audit also corrected navigation, headers, settings controls, side panels and two archive loading states. This report contains before-and-after evidence for every audited page/state.</p><div class="stats"><span><strong>{len(findings)}</strong> findings fixed</span><span><strong>{len(ordered_names)}</strong> page/state scenarios</span><span><strong>{len(after)}</strong> comparison pairs</span><span><strong>{len(verification)}</strong> verified widths</span></div><p class="subtle" style="color:#a7c3d4;margin-top:20px">{now} · Local build based on 5797ba4c5 · Chromium · Mobile 390 × 844 · Tablet 768 × 1024</p></header>
<main><section class="panel"><h2 style="margin-top:0">What was verified</h2><p>All available main web-app route families were exercised with disposable local data: two projects, long issue titles and properties, saved views, cycles, modules, a collaborative page, invitations and a disabled webhook. Auth and onboarding states use local response overrides. No production data, email delivery, password changes or webhook calls were involved.</p><p>The report covers available Community screens and paid-feature upgrade states. Integrations is not registered in this build; its 404 is recorded as unavailable. Admin and public sharing are separate applications and are outside this workspace web-app audit.</p><table class="matrix"><tr><th>Interaction checks</th><td class="pass">Passed at {widths}; also iPhone 13 and iPad Mini with touch and mobile user agents.</td></tr><tr><th>Browser assertions</th><td>List scroll width, virtualized rows after scrolling, navigation toggle/backdrop, search bounds, profile selector, password fields, member actions, webhook controls, work-item, profile, cycle and module panels.</td></tr><tr><th>Automated checks</th><td class="pass">47 web unit tests · Web and UI type checks · Web and UI lint · Production build</td></tr><tr><th>Screenshot quality</th><td>Fonts and visible images loaded; API requests settled; finite animations finished; no page errors. Page editor captures also wait for collaboration sync. All pairs were visually reviewed. The two before archive loaders are persistent defects, verified after completed requests and an extra wait.</td></tr><tr><th>Expected horizontal scrolling</th><td>Boards, tables, timelines, member/plan tables and tablet editor toolbars retain internal scrolling. Board, table and timeline scrolling was exercised at both screenshot widths. Ordinary lists and the page viewport must fit.</td></tr><tr><th>Delivery</th><td>The implementation was audited on <code>fix/mobile-tablet-layout-audit</code>. The report is self-contained; images remain available without its sibling files. Lint passes with the repository's existing warning allowances.</td></tr></table></section>
<h2>Findings and fixes</h2><div class="findings">{''.join(finding_cards)}</div><h2 id="gallery">Before / after evidence</h2><p class="subtle">Choose a device or finding. Click either image to enlarge it. Every comparison uses the same viewport dimensions.</p><div class="filters"><label>Device<select id="device"><option value="">Both devices</option><option value="mobile">Mobile · 390px</option><option value="tablet">Tablet · 768px</option></select></label><label>Finding<select id="finding"><option value="">All findings and pages</option>{options}</select></label><label>Coverage<select id="status"><option value="">All scenarios</option><option value="fixed">Related to a fix</option><option value="checked">No additional finding</option><option value="unavailable">Unavailable route</option></select></label><label>Search<input id="query" type="search" placeholder="Page or state name"></label><span id="shown"></span></div>{''.join(cards)}<p class="footer">Generated from before.json, after.json and verification.json. Original PNGs and capture scripts accompany the report. Empty states are intentional fixture states. Reset/set-password tokens are display-only fixtures; submission and email delivery were not tested.</p></main><dialog id="zoom"><div class="dialog-bar"><span id="zoom-label"></span><button type="button" id="close-zoom">Close ✕</button></div><img id="zoom-image" alt=""></dialog>
<script>
const cards=[...document.querySelectorAll('.comparison')],controls=['device','finding','status','query'].map(id=>document.getElementById(id));
function filter(){{const[d,f,s,q]=controls.map(e=>e.value.toLowerCase());let shown=0;for(const card of cards){{const visible=(!d||card.dataset.device===d)&&(!f||card.dataset.codes.toLowerCase().split(' ').includes(f))&&(!s||card.dataset.status===s)&&(!q||card.dataset.search.toLowerCase().includes(q));card.hidden=!visible;if(visible)shown++;}}document.getElementById('shown').textContent=shown+' / '+cards.length+' comparisons';}}
for(const control of controls)control.addEventListener('input',filter);filter();
for(const link of document.querySelectorAll('[data-target]'))link.addEventListener('click',()=>{{controls.forEach(e=>e.value='');filter();}});
const dialog=document.getElementById('zoom');for(const button of document.querySelectorAll('.image-button'))button.addEventListener('click',()=>{{document.getElementById('zoom-label').textContent=button.dataset.label;const img=document.getElementById('zoom-image');img.src=button.querySelector('img').src;img.alt=button.dataset.label;dialog.showModal();}});
document.getElementById('close-zoom').addEventListener('click',()=>dialog.close());dialog.addEventListener('click',e=>{{if(e.target===dialog)dialog.close();}});
</script></body></html>'''
(root / "report.html").write_text(html_document)
print(f"Created {root / 'report.html'}: {len(after)} pairs, {len(findings)} findings")
