import assert from "node:assert/strict";
import test from "node:test";
import { selectChecks, selectFullPhases } from "./lib/selection.mjs";

test("focused full-gate diagnostics accept only explicit independent phases", () => {
  assert.equal(selectFullPhases([]), null);
  assert.deepEqual(selectFullPhases(["--phase", "api-ruff", "--phase", "root-docs-links"]), [
    "api-ruff",
    "root-docs-links",
  ]);
  for (const args of [["--phase"], ["--phase", "api-pytest"], ["--skip", "api-ruff"]])
    assert.throws(() => selectFullPhases(args), /Expected --phase/);
});

test("gate runner edits select their public contract tests", () => {
  const selection = selectChecks(["scripts/kitchen/check-fast.mjs"]);
  assert.deepEqual(selection.tests, ["kitchen"]);
  assert.deepEqual(selection.packages, []);
});

test("package edits check dependent consumers and filter contracts", () => {
  const selection = selectChecks(["packages/utils/src/filter.ts", "packages/shared-state/filters.test.mjs"]);
  assert.deepEqual(selection.packages, ["@plane/shared-state", "@plane/utils"]);
  assert.deepEqual(selection.tests, ["filters", "workspace"]);
});

test("API code selects complete isolated discovery at L2, never host pytest", () => {
  const selection = selectChecks(["apps/api/plane/api/views/state.py"]);
  assert.deepEqual(selection.tests, []);
  assert.equal(selection.apiAtL2, true);
  assert.deepEqual(selection.packages, []);
});

test("MCP, branding and backup changes include their independent suites", () => {
  const selection = selectChecks([
    "apps/mcp/sikku/server.py",
    "tests/branding.test.mjs",
    "deployments/birdplane/backup-postgres.py",
  ]);
  assert.deepEqual(selection.tests, ["backups", "branding", "mcp"]);
  assert.deepEqual(selection.packages, []);
});

test("unknown infrastructure paths fail closed", () => {
  assert.throws(() => selectChecks(["deployments/unknown.sh"]), /No fast-check contract/);
});

test("docs and gate metadata need no product build; dependency changes do", () => {
  assert.deepEqual(
    selectChecks(
      ["README.md", ".husky/pre-commit", ".github/workflows/birdplane-checks.yml", ".gitignore", "package.json"],
      { scriptsOnly: true }
    ).tests,
    ["kitchen"]
  );
  assert.deepEqual(selectChecks(["pnpm-lock.yaml"]).tests, ["branding", "filters", "workspace"]);
  assert.deepEqual(selectChecks(["package.json"]).packages, ["*"]);
});

test("bundled MCP Markdown is runtime guidance and selects MCP tests", () => {
  assert.deepEqual(selectChecks(["apps/mcp/sikku/skills/plane-project-management/SKILL.md"]).tests, ["mcp"]);
});

test("product metadata and app manifests select branding assertions", () => {
  assert.deepEqual(selectChecks(["packages/constants/src/metadata.ts"]).tests, ["branding", "filters", "workspace"]);
  assert.deepEqual(selectChecks(["apps/web/public/manifest.json"]).tests, ["branding", "workspace"]);
});
