import assert from "node:assert/strict";
import { createRequire } from "node:module";
import path from "node:path";

const rows = (data) => (Array.isArray(data) ? data : data.results);

export function journeys(ctx) {
  async function api(suffix, { method = "GET", body, role = "admin", expected = 200 } = {}) {
    const response = await fetch(`${ctx.api}/api/v1/workspaces/kitchen-test/${suffix}`, {
      method,
      headers: { "x-api-key": ctx.seed[role], "Content-Type": "application/json" },
      ...(body ? { body: JSON.stringify(body) } : {}),
      signal: AbortSignal.timeout(30_000),
    });
    assert.equal(response.status, expected, `${method} ${suffix}: ${response.status} ${await response.clone().text()}`);
    return await response.json();
  }

  async function signIn(password) {
    await ctx.page.goto(ctx.web);
    await ctx.page.locator('input[type="email"]').fill("admin@test.com");
    await ctx.page.locator('button[type="submit"]').click();
    await ctx.page.locator('input[name="password"]').fill(password);
    await ctx.page.locator('button[type="submit"]').click();
  }

  return [
    [
      "wrong password rejected and unauthenticated API denied",
      async () => {
        const require = createRequire(path.join(ctx.runtime, "browser/package.json"));
        const { chromium } = require("playwright");
        ctx.browser = await chromium.launch({ headless: true });
        ctx.page = await ctx.browser.newPage({ viewport: { width: 1440, height: 1000 } });
        ctx.page.setDefaultTimeout(60_000);
        ctx.page.on("pageerror", (error) => {
          const detail = error.stack || String(error);
          ctx.browserErrors.push(`${new Date().toISOString()} ${detail}`);
          console.error(`Browser error: ${detail}`);
        });
        try {
          await signIn("wrong-password");
          await ctx.page.waitForURL((url) => url.searchParams.has("error_code"), { timeout: 60_000 });
          const denied = await ctx.page.request.get(`${ctx.api}/api/users/me/`);
          assert.ok([401, 403].includes(denied.status()), `Anonymous /users/me returned ${denied.status()}`);
          const anonymous = await fetch(`${ctx.api}/api/v1/workspaces/kitchen-test/projects/`);
          assert.ok([401, 403].includes(anonymous.status), `Anonymous public API returned ${anonymous.status}`);
          await ctx.page.screenshot({ path: path.join(ctx.evidence, "wrong-password.png") });
          return {
            wrongPassword: "error_code redirect; no authenticated session",
            unauthenticatedAPI: anonymous.status,
          };
        } catch (error) {
          await ctx.page.screenshot({ path: path.join(ctx.evidence, "failure.png") });
          throw error;
        }
      },
    ],
    [
      "admin signs in through web app",
      async () => {
        try {
          await signIn("password");
          await ctx.page.waitForURL((url) => url.pathname.startsWith("/kitchen-test/"));
          const me = await ctx.page.request.get(`${ctx.api}/api/users/me/`);
          assert.equal(me.status(), 200);
          assert.equal((await me.json()).email, "admin@test.com");
          await ctx.page.getByText("Kitchen Verification", { exact: true }).first().waitFor();
          await ctx.page.screenshot({ path: path.join(ctx.evidence, "admin-signed-in.png") });
          return "UI form login and authenticated /users/me confirmed admin@test.com";
        } catch (error) {
          await ctx.page.screenshot({ path: path.join(ctx.evidence, "failure.png") });
          throw error;
        }
      },
    ],
    [
      "create project and verify default states",
      async () => {
        // The public v1 create schema does not accept network. Use the same
        // authenticated app endpoint as the web project's private/public picker.
        const csrf = await (await ctx.page.request.get(`${ctx.api}/auth/get-csrf-token/`)).json();
        const response = await ctx.page.request.post(`${ctx.api}/api/workspaces/kitchen-test/projects/`, {
          data: { name: "Verification project", identifier: "VERIFY", network: 0 },
          headers: { "X-CSRFToken": csrf.csrf_token, Origin: ctx.web },
        });
        assert.equal(response.status(), 201, await response.text());
        const project = await response.json();
        assert.equal(project.network, 0, "Permission fixture must actually be private");
        ctx.project = project.id;
        ctx.states = rows(await api(`projects/${ctx.project}/states/`));
        const actual = ctx.states
          .map(({ name, group, default: isDefault }) => ({ name, group, default: isDefault }))
          .toSorted((a, b) => a.name.localeCompare(b.name));
        assert.deepEqual(
          actual.map((s) => [s.name, s.group]),
          [
            ["Backlog", "backlog"],
            ["Cancelled", "cancelled"],
            ["Done", "completed"],
            ["In Progress", "started"],
            ["Todo", "unstarted"],
          ]
        );
        assert.equal(actual.filter((s) => s.default).length, 1);
        assert.equal(actual.find((s) => s.default).name, "Backlog");
        return actual;
      },
    ],
    [
      "create work item, move state and filter with PQL",
      async () => {
        const base = `projects/${ctx.project}/work-items/`;
        const item = await api(base, {
          method: "POST",
          expected: 201,
          body: { name: "Kitchen functional work item", priority: "high" },
        });
        ctx.item = item.id;
        const started = ctx.states.find((s) => s.name === "In Progress").id;
        await api(`${base}${item.id}/`, { method: "PATCH", body: { state: started } });
        const fetched = await api(`${base}${item.id}/`);
        assert.equal(typeof fetched.state === "object" ? fetched.state.id : fetched.state, started);
        const matching = rows(
          await api(
            `${base}?pql=${encodeURIComponent("priority = High AND stateGroup = started AND createdAt = today()")}`
          )
        );
        assert.deepEqual(
          matching.map((i) => i.id),
          [item.id]
        );
        const excluded = rows(await api(`${base}?pql=${encodeURIComponent("priority = Low")}`));
        assert.deepEqual(excluded, []);
        // Confirm API-created product data actually renders in the web app.
        await ctx.page.goto(`${ctx.web}/kitchen-test/projects/${ctx.project}/issues/`);
        await ctx.page.getByText("Kitchen functional work item", { exact: true }).first().waitFor();
        await ctx.page.screenshot({ path: path.join(ctx.evidence, "work-item-state.png") });
        return "work item persisted In Progress; matching/excluding PQL verified; rendered in web";
      },
    ],
    [
      "user sees only joined private projects",
      async () => {
        const projects = rows(await api("projects/", { role: "user" }));
        assert.deepEqual(
          projects.map((p) => p.id),
          [ctx.seed.joinedProject]
        );
        const response = await fetch(`${ctx.api}/api/v1/workspaces/kitchen-test/projects/${ctx.project}/work-items/`, {
          headers: { "x-api-key": ctx.seed.user },
        });
        assert.ok([403, 404].includes(response.status), `Unjoined private project returned ${response.status}`);
        return { visible: ["Joined project"], privateWorkItemsDenied: response.status };
      },
    ],
    [
      "MCP tools/list and list_issues use disposable API",
      async () => {
        // The subprocess receives generated API credentials from a private runtime file.
        return await ctx.command(
          path.join(ctx.runtime, "mcp-venv/bin/python"),
          [path.join(import.meta.dirname, "mcp_journey.py"), ctx.api, ctx.runtime, ctx.project, ctx.item],
          {
            cwd: path.resolve(import.meta.dirname, "../../../apps/mcp"),
            log: path.join(ctx.evidence, "mcp-journey.log"),
            timeout: 60_000,
          }
        );
      },
    ],
  ];
}
