// Browser actions share state and must run in order.
/* eslint-disable no-await-in-loop */
import assert from "node:assert/strict";
import fs from "node:fs/promises";
import path from "node:path";
const { chromium, devices } = await import(process.env.PLAYWRIGHT_MODULE || "playwright");
const fixture = JSON.parse(await fs.readFile(process.env.AUDIT_FIXTURE, "utf8"));
const base = process.env.AUDIT_BASE_URL || "http://localhost:18031";
const workspace = process.env.AUDIT_WORKSPACE || "audit";
const project = `/${workspace}/projects/${fixture.projects[0].id}`;
const browser = await chromium.launch({ headless: true });
const results = [];
const touch = process.env.AUDIT_TOUCH === "1";
for (const width of touch ? [390, 768] : [320, 360, 390, 414, 768, 820, 1024, 1280, 1440]) {
  const context = await browser.newContext({
    ...(touch ? devices[width === 390 ? "iPhone 13" : "iPad Mini"] : {}),
    viewport: { width, height: width < 600 ? 844 : 1024 },
  });
  await context.addCookies([{ name: fixture.cookieName, value: fixture.cookie, url: base }]);
  await context.addInitScript(() => localStorage.setItem("app_sidebar_collapsed", "false"));
  const page = await context.newPage();
  const errors = [];
  let pending = new Set(),
    lastRequest = Date.now();
  page.on("pageerror", (error) => errors.push(error.message));
  page.on("request", (request) => {
    if (request.url().includes("/api/")) {
      pending.add(request);
      lastRequest = Date.now();
    }
  });
  for (const event of ["requestfinished", "requestfailed"])
    page.on(event, (request) => {
      pending.delete(request);
      lastRequest = Date.now();
    });
  async function settle() {
    await page.evaluate(() => document.fonts.ready);
    const start = Date.now();
    while ((pending.size || Date.now() - lastRequest < 500) && Date.now() - start < 15000)
      await page.waitForTimeout(100);
    assert.equal(pending.size, 0, "API requests must finish");
    await page.waitForTimeout(700);
    await page.waitForFunction(() =>
      document
        .getAnimations()
        .every(
          (animation) =>
            animation.playState !== "running" || animation.effect?.getComputedTiming().iterations === Infinity
        )
    );
  }
  async function visit(url) {
    pending = new Set();
    await page.goto(base + url);
    await settle();
  }
  async function bounds(locator) {
    const rect = await locator.boundingBox();
    assert(
      rect && rect.x >= -2 && rect.x + rect.width <= width + 2,
      `Control must fit at ${width}px (${await locator.count()} matches, ${page.url()}): ${JSON.stringify(rect)}`
    );
  }
  async function listFits() {
    const measure = await page
      .locator(".vertical-scrollbar.size-full")
      .last()
      .evaluate((element) => ({ width: element.clientWidth, scroll: element.scrollWidth }));
    assert(measure.width > 200, `Usable list width at ${width}px`);
    assert(measure.scroll <= measure.width + 2, `List overflow at ${width}px: ${JSON.stringify(measure)}`);
    assert(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 2));
    return measure;
  }
  try {
    await visit(`${project}/issues`);
    await page.locator('[id^="issue-"]').first().waitFor();
    await settle();
    const list = await listFits();
    await page
      .locator(".vertical-scrollbar.size-full")
      .last()
      .evaluate((element) => {
        element.scrollLeft = element.scrollWidth;
        element.scrollTop = element.scrollHeight;
      });
    await settle();
    await listFits();
    assert.equal(
      await page
        .locator(".vertical-scrollbar.size-full")
        .last()
        .evaluate((element) => element.scrollLeft),
      0
    );
    if (width < 1024) {
      const toggle = page.getByRole("button", { name: "Toggle navigation sidebar" }).first();
      await toggle.click();
      await settle();
      assert.equal(await page.locator("#main-sidebar").getAttribute("aria-hidden"), "false");
      assert.equal((await listFits()).width, list.width, "Overlay navigation must preserve list width");
      await toggle.click();
      await settle();
      assert.equal(await page.locator("#main-sidebar").getAttribute("aria-hidden"), "true");
      await toggle.click();
      await settle();
      await page
        .getByRole("button", { name: "Close navigation sidebar" })
        .click({ position: { x: width - 20, y: 200 } });
      await settle();
      assert.equal(await page.locator("#main-sidebar").getAttribute("aria-hidden"), "true");
    }
    await page.getByRole("textbox", { name: "Search commands", exact: true }).click();
    await settle();
    await bounds(page.locator("[cmdk-root]:visible").first());
    await visit(`/settings/profile/security`);
    for (const input of await page.locator('input[type="password"]').all()) await bounds(input);
    if (width < 1024) {
      await page.getByRole("combobox", { name: "Profile settings page" }).selectOption("preferences");
      await page.waitForURL(/\/settings\/profile\/preferences\/?$/);
      await settle();
      assert((await page.locator("body").innerText()).includes("Language & Time"));
    }
    await visit(`/${workspace}/settings/members`);
    await bounds(page.getByRole("button", { name: "Add member", exact: true }));
    await visit(`/${workspace}/settings/webhooks/${fixture.webhook}`);
    await bounds(page.getByRole("button", { name: "Re-generate key", exact: true }));
    await visit(`/${workspace}/browse/FLIGHTCTL-1`);
    await page.locator("#work-item-properties").waitFor({ state: "attached" });
    await settle();
    const properties = page.getByRole("button", { name: "Toggle work item properties" });
    if ((await properties.getAttribute("aria-expanded")) === "false") await properties.click();
    await settle();
    await bounds(page.locator("#work-item-properties"));
    for (const button of await page.locator("#work-item-properties button:visible").all()) await bounds(button);
    await properties.click();
    await settle();
    assert.equal(await properties.getAttribute("aria-expanded"), "false");
    await visit(`/${workspace}/profile/${fixture.user}/assigned`);
    await page.locator("#profile-details").waitFor({ state: "attached" });
    await settle();
    const profile = page.getByRole("button", { name: "Toggle profile details" });
    if ((await profile.getAttribute("aria-expanded")) === "false") await profile.click();
    await settle();
    await bounds(page.locator("#profile-details"));
    await profile.click();
    await settle();
    assert.equal(await profile.getAttribute("aria-expanded"), "false");
    if (width < 1024) await listFits();
    for (const kind of ["cycle", "module"]) {
      await visit(`${project}/${kind}s/${fixture.projects[0][kind]}`);
      await page.locator('[id^="issue-"]').first().waitFor();
      await settle();
      const toggle = page.getByRole("button", { name: `Toggle ${kind} analytics` });
      if (width < 1024) assert.equal(await toggle.getAttribute("aria-expanded"), "false");
      if ((await toggle.getAttribute("aria-expanded")) === "false") await toggle.click();
      await settle();
      assert.equal(await toggle.getAttribute("aria-expanded"), "true");
      await bounds(page.locator(".vertical-scrollbar.absolute.right-0").last());
      if (width < 1024) await listFits();
      await toggle.click();
      await settle();
      assert.equal(await toggle.getAttribute("aria-expanded"), "false");
      await listFits();
    }
    assert.equal(errors.length, 0, errors.join("; "));
    results.push({
      width,
      touch,
      passed: true,
      list,
      checks: [
        "virtualized list",
        "navigation overlay and close",
        "search panel",
        "profile settings navigation",
        "password inputs",
        "member actions",
        "webhook controls",
        "work item properties",
        "profile details",
        "cycle and module analytics open and close",
      ],
    });
    console.log(`PASS ${width}px`);
  } catch (error) {
    results.push({ width, passed: false, error: String(error), stack: error.stack });
    await page.screenshot({ path: `/tmp/bird29-verification-${width}.png` });
    console.log(`FAIL ${width}px ${error}`);
  }
  await context.close();
}
await browser.close();
const out = path.resolve(process.argv[2] || "reports/responsive-audit");
await fs.mkdir(out, { recursive: true });
await fs.writeFile(
  path.join(out, touch ? "touch-verification.json" : "verification.json"),
  JSON.stringify(results, null, 2)
);
if (results.some((result) => !result.passed)) process.exitCode = 1;
