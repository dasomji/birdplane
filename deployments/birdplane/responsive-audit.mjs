// Browser actions share state and must run in order.
/* eslint-disable no-await-in-loop */
import fs from "node:fs/promises";
import path from "node:path";
const { chromium } = await import(process.env.PLAYWRIGHT_MODULE || "playwright");
const phase = process.argv[2] || "before";
const out = path.resolve(process.argv[3] || "reports/responsive-audit");
const fixture = JSON.parse(await fs.readFile(process.env.AUDIT_FIXTURE, "utf8"));
const base = process.env.AUDIT_BASE_URL || "http://localhost:18030";
const w = process.env.AUDIT_WORKSPACE || "audit",
  p = fixture.projects[0],
  project = `/${w}/projects/${p.id}`;
const cases = [
  ...["assigned", "created", "subscribed"].map((tab) => [
    `profile-${tab}`,
    `/${w}/profile/${fixture.user}/${tab}`,
    { layout: "List" },
  ]),
  ["archived-issue-detail", `${project}/archives/issues/${fixture.archivedIssue}`],
  ["analytics-work-items", `/${w}/analytics/work-items`],
  ["profile-details", `/${w}/profile/${fixture.user}/assigned`, { profileDetails: true, layout: "List" }],
  ["home", `/${w}`],
  ["drafts", `/${w}/drafts`],
  ["your-work", `/${w}/profile/${fixture.user}`],
  ["profile-activity", `/${w}/profile/${fixture.user}/activity`],
  ["stickies", `/${w}/stickies`],
  ["notifications", `/${w}/notifications`],
  ["projects", `/${w}/projects`],
  ["archived-projects", `/${w}/projects/archives`],
  ["workspace-views", `/${w}/workspace-views`],
  ...["List", "Board", "Calendar", "Table", "Timeline"].map((layout) => [
    `workspace-${layout.toLowerCase()}`,
    `/${w}/workspace-views/all-issues`,
    { layout },
  ]),
  ["saved-workspace-view", `/${w}/workspace-views/${fixture.view}`, { layout: "List" }],
  ["project-list", `${project}/issues`, { layout: "List" }],
  ["issue-detail", `/${w}/browse/FLIGHTCTL-1`],
  ["issue-properties", `/${w}/browse/FLIGHTCTL-1`, { properties: true }],
  ["list-horizontal-end", `${project}/issues`, { layout: "List", scrollX: true }],
  ["cycle-analytics", `${project}/cycles/${p.cycle}`, { layout: "List", analytics: "cycle" }],
  ["module-analytics", `${project}/modules/${p.module}`, { layout: "List", analytics: "module" }],
  ["cycles", `${project}/cycles`],
  ["cycle-detail", `${project}/cycles/${p.cycle}`, { layout: "List" }],
  ["active-cycles", `/${w}/active-cycles`],
  ["modules", `${project}/modules`],
  ["module-detail", `${project}/modules/${p.module}`, { layout: "List" }],
  ["project-views", `${project}/views`],
  ["saved-project-view", `${project}/views/${p.view}`, { layout: "List" }],
  ["pages", `${project}/pages`],
  ["page-outline", `${project}/pages/${fixture.page}?paneTab=outline`, { editor: true }],
  ["page-detail", `${project}/pages/${fixture.page}`, { editor: true }],
  ["intake", `${project}/intake`],
  ["archived-issues", `${project}/archives/issues`],
  ["archived-cycles", `${project}/archives/cycles`],
  ["archived-modules", `${project}/archives/modules`],
  ["analytics", `/${w}/analytics/overview`],
  ...["", "members", "billing", "exports", "integrations", "webhooks"].map((tab) => [
    `workspace-settings-${tab || "general"}`,
    `/${w}/settings${tab ? "/" + tab : ""}`,
  ]),
  ["webhook-detail", `/${w}/settings/webhooks/${fixture.webhook}`],
  ["settings-projects", `/${w}/settings/projects`],
  ...[
    "",
    "members",
    "features/cycles",
    "features/modules",
    "features/views",
    "features/pages",
    "features/intake",
    "states",
    "labels",
    "estimates",
    "automations",
  ].map((tab) => [
    `project-settings-${tab.replace("/", "-") || "general"}`,
    `/${w}/settings/projects/${p.id}${tab ? "/" + tab : ""}`,
  ]),
  ...["general", "preferences", "notifications", "security", "api-tokens"].map((tab) => [
    `profile-settings-${tab}`,
    `/settings/profile/${tab}`,
  ]),
  ["create-workspace", "/create-workspace"],
  ["invitations", "/invitations"],
  [
    "workspace-invitations",
    `/workspace-invitations?slug=${w}&invitation_id=${fixture.invitation}&token=disposable-local-invitation`,
  ],
  ["not-found", "/audit/unknown-page"],
  ["sign-in", "/", { anonymous: true }],
  ["sign-up", "/sign-up", { anonymous: true }],
  ["forgot-password", "/accounts/forgot-password", { anonymous: true }],
  [
    "reset-password",
    "/accounts/reset-password?email=audit%40example.invalid&uidb64=fixture&token=fixture",
    { anonymous: true },
  ],
  ["set-password", "/accounts/set-password?email=audit%40example.invalid", { setPassword: true }],
  ...["profile", "workspace", "invite"].map((step) => [`onboarding-${step}`, "/onboarding", { onboarding: step }]),
  ["navigation-search", `/${w}/projects`, { search: true }],
  ["navigation-sidebar", `/${w}/projects`, { sidebar: true }],
  ["create-project-modal", `/${w}/projects`, { modal: "project" }],
  ["create-issue-modal", `${project}/issues`, { modal: "issue", layout: "List" }],
];
await fs.mkdir(path.join(out, "screenshots"), { recursive: true });
const browser = await chromium.launch({ headless: true });
const context = await browser.newContext({
  viewport: { width: 390, height: 844 },
  deviceScaleFactor: 1,
  colorScheme: "light",
});
const page = await context.newPage();
let activeOptions = {};
await context.addCookies([{ name: fixture.cookieName, value: fixture.cookie, url: base }]);

await context.route("**/api/users/me/**", async (route) => {
  const pathname = new URL(route.request().url()).pathname;
  if (activeOptions.anonymous && pathname === "/api/users/me/")
    return route.fulfill({ status: 401, json: { detail: "Not authenticated." } });
  if (
    (activeOptions.onboarding && pathname === "/api/users/me/profile/") ||
    (activeOptions.setPassword && pathname === "/api/users/me/")
  ) {
    const response = await route.fetch();
    const data = await response.json();
    if (activeOptions.setPassword) data.is_password_autoset = true;
    else {
      data.is_onboarded = false;
      data.onboarding_step = {
        profile_complete: activeOptions.onboarding !== "profile",
        workspace_create: activeOptions.onboarding === "invite",
        workspace_invite: false,
        workspace_join: false,
      };
    }
    return route.fulfill({ response, json: data });
  }
  return route.continue();
});
let pending = new Set(),
  lastRequest = 0,
  errors = [];
page.on("request", (r) => {
  if (/\/api\//.test(r.url())) {
    pending.add(r);
    lastRequest = Date.now();
  }
});
for (const event of ["requestfinished", "requestfailed"])
  page.on(event, (r) => {
    pending.delete(r);
    lastRequest = Date.now();
  });
page.on("pageerror", (e) => errors.push(e.message));
page.on("response", (response) => {
  if (
    response.url().includes("/api/") &&
    response.status() >= 400 &&
    !(activeOptions.anonymous && response.status() === 401)
  ) {
    errors.push(`${response.status()} ${new URL(response.url()).pathname}`);
  }
});
await context.addInitScript(() => {
  localStorage.setItem("app_sidebar_collapsed", "false");
  localStorage.setItem("theme", "light");
});
async function settled() {
  await page.waitForFunction(() => document.body.innerText.trim().length > 30, {}, { timeout: 25000 });
  await page.evaluate(() => document.fonts.ready);
  const start = Date.now();
  while ((pending.size || Date.now() - lastRequest < 500) && Date.now() - start < 15000) await page.waitForTimeout(100);
  await page.waitForTimeout(500);
  await page.waitForFunction(
    () =>
      document
        .getAnimations()
        .every((a) => a.playState !== "running" || a.effect?.getComputedTiming().iterations === Infinity),
    {},
    { timeout: 10000 }
  );
  const proof = await page.evaluate(() => ({
    ready: document.readyState,
    fonts: document.fonts.status,
    finiteAnimations: document
      .getAnimations()
      .filter((a) => a.playState === "running" && a.effect?.getComputedTiming().iterations !== Infinity).length,
    text: document.querySelector("main")?.innerText.slice(-300) || document.body.innerText.slice(-300),
    images: [...document.images].filter((i) => i.getBoundingClientRect().width > 0 && !i.complete).length,
  }));
  if (pending.size || proof.fonts !== "loaded" || proof.finiteAnimations || proof.images)
    throw Error(
      "Page did not settle: " +
        JSON.stringify({ ...proof, pending: pending.size, pendingUrls: [...pending].map((r) => r.url()) })
    );
  return proof;
}
async function metrics() {
  return page.evaluate(() => {
    const W = innerWidth,
      H = innerHeight;
    function visible(e) {
      let r = e.getBoundingClientRect();
      if (!r.width || !r.height || r.bottom <= 0 || r.top >= H) return false;
      for (let n = e; n; n = n.parentElement) {
        const s = getComputedStyle(n);
        if (
          s.visibility === "hidden" ||
          s.display === "none" ||
          s.opacity === "0" ||
          n.hasAttribute("inert") ||
          n.getAttribute("aria-hidden") === "true"
        )
          return false;
      }
      return true;
    }
    const scrolls = [...document.querySelectorAll("*")]
      .filter(
        (e) =>
          visible(e) &&
          e.clientWidth &&
          e.scrollWidth > e.clientWidth + 2 &&
          ["auto", "scroll"].includes(getComputedStyle(e).overflowX)
      )
      .map((e) => ({
        tag: e.tagName,
        id: e.id,
        class: String(e.className),
        width: e.clientWidth,
        scrollWidth: e.scrollWidth,
        text: e.innerText?.slice(0, 80),
      }));
    const offscreen = [...document.querySelectorAll("button,input,a,h1,h2")]
      .filter(
        (e) =>
          visible(e) &&
          e.getBoundingClientRect().right > W + 2 &&
          !e.closest('#main-sidebar,[aria-label="Sidebar peek view"]')
      )
      .map((e) => ({
        tag: e.tagName,
        text: e.innerText?.slice(0, 50) || e.getAttribute("aria-label") || e.getAttribute("placeholder"),
        x: Math.round(e.getBoundingClientRect().x),
        right: Math.round(e.getBoundingClientRect().right),
      }))
      .slice(0, 20);
    return {
      url: location.pathname,
      viewport: { width: W, height: H },
      documentWidth: document.documentElement.scrollWidth,
      scrolls,
      offscreen,
      issues: document.querySelectorAll('[id^="issue-"]').length,
    };
  });
}
let results = [];
if (process.env.AUDIT_CASES) {
  try {
    results = JSON.parse(await fs.readFile(path.join(out, `${phase}.json`), "utf8"));
  } catch {}
}
for (const viewport of [
  { name: "mobile", width: 390, height: 844 },
  { name: "tablet", width: 768, height: 1024 },
]) {
  for (const [name, url, options = {}] of cases) {
    if (process.env.AUDIT_CASES && !process.env.AUDIT_CASES.split(",").includes(name)) continue;
    const key = `${viewport.name}-${name}`;
    errors = [];
    pending = new Set();
    activeOptions = options;
    results = results.filter((r) => r.key !== key);
    try {
      await page.setViewportSize(options.layout ? { width: 1280, height: 900 } : viewport);
      await page.goto(base + url, { waitUntil: "load", timeout: 30000 });
      if (["archived-cycles", "archived-modules"].includes(name)) {
        if (phase === "before") await page.waitForTimeout(10000);
        else
          await page.waitForFunction(
            () => ![...document.querySelectorAll(".animate-pulse")].some((e) => e.getBoundingClientRect().height > 0),
            {},
            { timeout: 15000 }
          );
      }
      if (options.editor) {
        await page
          .locator(phase === "before" ? ".tiptap.ProseMirror" : ".tiptap.ProseMirror:visible")
          .first()
          .waitFor({ state: phase === "before" ? "attached" : "visible", timeout: 45000 });
        await page.waitForFunction(
          () => !document.body.innerText.includes("Syncing...") && !document.body.innerText.includes("Connection lost"),
          {},
          { timeout: 45000 }
        );
      }
      if (
        options.layout ||
        options.search ||
        options.sidebar ||
        options.modal ||
        options.properties ||
        options.profileDetails ||
        options.analytics
      )
        await settled();
      if (options.layout) {
        const indices = { List: 0, Board: 1, Calendar: 2, Table: 3, Timeline: 4 };
        const controls = page.locator(".bg-layer-3 button:visible");
        if ((await controls.count()) >= 5) {
          const control = controls.nth(indices[options.layout]);
          if (!(await control.getAttribute("class")).includes("bg-layer-transparent-active")) {
            await control.click({ force: phase === "before" });
            await settled();
          }
        }
        await page.setViewportSize(viewport);
      }
      if (
        options.search ||
        options.sidebar ||
        options.modal ||
        options.properties ||
        options.profileDetails ||
        options.analytics
      )
        await settled();
      if (options.analytics) {
        const toggle = page.getByRole("button", { name: `Toggle ${options.analytics} analytics` });
        if (phase === "after" && !(await toggle.count())) throw Error("Analytics toggle must be accessible");
        if ((await toggle.count()) && (await toggle.getAttribute("aria-expanded")) === "false") {
          await toggle.click();
          await settled();
        }
        if (phase === "after" && (await toggle.getAttribute("aria-expanded")) !== "true")
          throw Error("Analytics panel must be open for this capture");
      }
      if (options.search) {
        await page.getByPlaceholder("Search commands...").click();
        await settled();
      }
      if (options.sidebar) {
        const collapsed = await page.locator("#main-sidebar").evaluate((e) => e.clientWidth < 10);
        if (collapsed) {
          if (phase === "after") await page.getByRole("button", { name: "Toggle navigation sidebar" }).first().click();
          else
            await page
              .locator("main button:visible")
              .filter({ has: page.locator("svg.lucide-panel-left") })
              .first()
              .click();
          await settled();
        }
        if (phase === "after" && (await page.locator("#main-sidebar").getAttribute("aria-hidden")) !== "false")
          throw Error("Navigation must be open for this capture");
      }
      if (options.modal === "project") {
        await page
          .getByRole("button", { name: /^(Project|Add project)$/i })
          .last()
          .click();
        await settled();
      }
      if (options.profileDetails) {
        const toggle = page.getByRole("button", { name: "Toggle profile details" });
        if (await toggle.count()) {
          if ((await toggle.getAttribute("aria-expanded")) === "false") await toggle.click();
          await settled();
        } else {
          const button = page.locator("main button:visible").filter({ has: page.locator("svg.lucide-panel-right") });
          if (await button.count()) {
            await button.first().click();
            await settled();
          }
        }
      }
      if (options.properties) {
        const toggle = page.getByRole("button", { name: "Toggle work item properties" });
        if (await toggle.count()) {
          if ((await toggle.getAttribute("aria-expanded")) === "false") await toggle.click();
          await settled();
        }
      }
      if (options.scrollX) {
        await page
          .locator(".vertical-scrollbar.size-full")
          .last()
          .evaluate((e) => (e.scrollLeft = e.scrollWidth));
        await settled();
      }
      if (options.modal === "issue") {
        const headerCreate = page.locator("main").getByRole("button", { name: /^(Work item|Add work item)$/ });
        if (await headerCreate.count()) {
          await headerCreate.first().click();
          await settled();
        } else {
          const collapsed = await page.locator("#main-sidebar").evaluate((e) => e.clientWidth < 10);
          if (collapsed) {
            await page
              .locator("main button:visible")
              .filter({ has: page.locator("svg.lucide-panel-left") })
              .first()
              .click();
            await settled();
          }
          await page.locator("#main-sidebar").getByRole("button", { name: "New work item", exact: true }).click();
          await settled();
        }
      }
      if (
        [
          "project-list",
          "workspace-list",
          "saved-workspace-view",
          "saved-project-view",
          "cycle-detail",
          "module-detail",
          "list-horizontal-end",
        ].includes(name)
      ) {
        await page.locator('[id^="issue-"]').first().waitFor({ state: "attached", timeout: 30000 });
      }
      const proof = await settled(),
        measure = await metrics();
      if (measure.url !== new URL(base + url).pathname && !["not-found", "settings-projects"].includes(name))
        throw Error("Unexpected redirect to " + measure.url);
      if (errors.length) throw Error("Page errors: " + errors.join("; "));
      const screenshot = `screenshots/${phase}-${key}.png`;
      await page.screenshot({ path: path.join(out, screenshot), animations: "disabled" });
      const entry = { key, name, url, device: viewport.name, phase, screenshot, proof, measure, errors };
      results.push(entry);
      console.log(
        JSON.stringify({
          key,
          scrolls: measure.scrolls.map((s) => [s.width, s.scrollWidth, s.class.slice(0, 50)]),
          offscreen: measure.offscreen.slice(0, 5),
          errors: errors.length,
        })
      );
    } catch (error) {
      results.push({ key, name, url, device: viewport.name, phase, error: String(error), errors });
      console.log("CAPTURE ERROR", key, String(error).slice(0, 250));
    }
    await fs.writeFile(path.join(out, `${phase}.json`), JSON.stringify(results, null, 2));
  }
}
await browser.close();
console.log(`Captured ${results.filter((r) => r.screenshot).length}/${results.length} settled screenshots`);
