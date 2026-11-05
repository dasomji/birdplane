import assert from "node:assert/strict";
import { createServer } from "node:http";
import { createRequire } from "node:module";
import test from "node:test";
import * as startup from "./browser.mjs";
const { waitForLogin } = startup;

// The runner installs pinned Playwright outside the checkout. Opt in with that
// package.json path; fast guards remain runnable without a downloaded browser.
const browserPackage = process.env.VERIFY_BROWSER_PACKAGE;

test(
  "login readiness recovers an invalidated Vite module instead of accepting a blank HTTP 200 shell",
  {
    skip: !browserPackage && "Set VERIFY_BROWSER_PACKAGE to the verifier's browser/package.json",
  },
  async (t) => {
    const { chromium } = createRequire(browserPackage)("playwright");
    const browser = await chromium.launch({ headless: true });
    t.after(() => browser.close());
    let navigations = 0;
    const server = createServer((req, res) => {
      if (req.url === "/") {
        navigations++;
        res.writeHead(200, { "Content-Type": "text/html" });
        res.end(
          navigations === 1
            ? '<script type="module" src="/node_modules/.vite/deps/login.js?v=old"></script>'
            : '<input type="email"><button type="submit">Continue</button>'
        );
      } else {
        res.writeHead(504, "Outdated Optimize Dep", { "Content-Type": "text/javascript" });
        res.end("Outdated Optimize Dep");
      }
    });
    await new Promise((resolve) => server.listen(0, "127.0.0.1", resolve));
    t.after(() => new Promise((resolve) => server.close(resolve)));
    const page = await browser.newPage();
    const url = `http://127.0.0.1:${server.address().port}`;
    await waitForLogin(page, url, { timeout: 3000, attemptTimeout: 500 });
    assert.equal(await page.locator('input[type="email"]').isVisible(), true);
    assert.equal(navigations, 2);
  }
);

test(
  "a blank application without a Vite invalidation fails without a reload and retains browser diagnostics",
  {
    skip: !browserPackage && "Set VERIFY_BROWSER_PACKAGE to the verifier's browser/package.json",
  },
  async (t) => {
    const { chromium } = createRequire(browserPackage)("playwright");
    const browser = await chromium.launch({ headless: true });
    t.after(() => browser.close());
    let navigations = 0;
    const server = createServer((req, res) => {
      if (req.url === "/") {
        navigations++;
        res.writeHead(200, { "Content-Type": "text/html" });
        res.end(`<script>console.warn("startup warning"); setTimeout(() => { throw new Error("startup exception"); }, 0);</script>
        <script src="/broken.js?credential=do-not-retain"></script><script src="/missing.js"></script>`);
      } else if (req.url.startsWith("/broken.js")) {
        req.socket.destroy();
      } else {
        res.writeHead(503, { "Content-Type": "text/javascript" });
        res.end("unavailable");
      }
    });
    await new Promise((resolve) => server.listen(0, "127.0.0.1", resolve));
    t.after(() => new Promise((resolve) => server.close(resolve)));
    const page = await browser.newPage();
    const diagnostics = startup.observeBrowser(page);
    await assert.rejects(
      waitForLogin(page, `http://127.0.0.1:${server.address().port}`, {
        timeout: 1500,
        attemptTimeout: 500,
      }),
      /Timeout/
    );
    assert.equal(navigations, 1);
    const lines = diagnostics.events.join("\n");
    assert.match(lines, /console warning.*startup warning/);
    assert.match(lines, /requestfailed.*broken\.js/);
    assert.match(lines, /response 503.*missing\.js/);
    assert.match(diagnostics.pageErrors.join("\n"), /startup exception/);
    assert.doesNotMatch(lines, /do-not-retain/);
  }
);
