// Each layout change must settle before checking its scroll surface.
/* eslint-disable no-await-in-loop */
import assert from "node:assert/strict";
import fs from "node:fs";
const { chromium } = await import(process.env.PLAYWRIGHT_MODULE || "playwright");
const f = JSON.parse(fs.readFileSync(process.env.AUDIT_FIXTURE));
const base = process.env.AUDIT_BASE_URL || "http://localhost:18031";
const workspace = process.env.AUDIT_WORKSPACE || "audit";
const b = await chromium.launch({ headless: true });
const results = [];
for (const width of [390, 768])
  for (const [name, index] of [
    ["board", 1],
    ["table", 3],
    ["timeline", 4],
  ]) {
    const c = await b.newContext({ viewport: { width: 1280, height: 1024 } });
    await c.addCookies([{ name: f.cookieName, value: f.cookie, url: base }]);
    const p = await c.newPage();
    await p.goto(`${base}/${workspace}/workspace-views/all-issues`);
    await p.locator('[id^="issue-"]').first().waitFor({ state: "attached" });
    await p.waitForTimeout(1000);
    const t = p.locator(".bg-layer-3 button:visible").nth(index);
    if (!(await t.getAttribute("class")).includes("bg-layer-transparent-active")) await t.click();
    await p.setViewportSize({ width, height: 1024 });
    await p.waitForTimeout(1500);
    const scroll = p.locator(".horizontal-scrollbar").filter({ visible: true });
    const measured = await scroll.evaluateAll((es) =>
      es.map((e) => {
        e.scrollLeft = 100;
        return { width: e.clientWidth, scrollWidth: e.scrollWidth, left: e.scrollLeft };
      })
    );
    assert(measured.some((m) => m.left > 0));
    assert(await p.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 2));
    results.push({ width, name, passed: true, measured });
    console.log("PASS", width, name);
    await c.close();
  }
fs.writeFileSync(
  `${process.argv[2] || "reports/responsive-audit"}/intentional-scroll-verification.json`,
  JSON.stringify(results, null, 2)
);
await b.close();
