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

test("deployment scripts, Compose, Dockerfiles and all workflows have explicit contracts", () => {
  const selection = selectChecks([
    "deployments/birdplane/responsive-audit.mjs",
    "deployments/birdplane/verify-responsive.mjs",
    "deployments/birdplane/verify-scroll-surfaces.mjs",
    "deployments/birdplane/build-responsive-report.py",
    "deployments/birdplane/compose.yml",
    "deployments/birdplane/Dockerfile.minio",
    "docker-compose-test.yml",
    ".github/workflows/codeql.yml",
  ]);
  assert.deepEqual(selection.infrastructure, [
    ".github/workflows/codeql.yml",
    "deployments/birdplane/Dockerfile.minio",
    "deployments/birdplane/compose.yml",
    "docker-compose-test.yml",
  ]);
  assert.deepEqual(selection.deferred, []);
});

test("merge selection keeps mapped checks and defers only unmapped upstream paths to L2", () => {
  const selection = selectChecks(["upstream/new-tool.sh", "apps/web/app/page.tsx", "docker-compose.yml"], {
    merging: true,
  });
  assert.deepEqual(selection.deferred, ["upstream/new-tool.sh"]);
  assert.deepEqual(selection.packages, ["web"]);
  assert.deepEqual(selection.infrastructure, ["docker-compose.yml"]);
  assert.throws(() => selectChecks(["deployments/birdplane/unknown.sh"], { merging: true }), /No fast-check contract/);
});
