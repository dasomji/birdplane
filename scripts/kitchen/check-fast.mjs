import { execFileSync } from "node:child_process";
import { existsSync, readFileSync } from "node:fs";
import { join } from "node:path";
import { checkCompose, checkWorkflows } from "./lib/infrastructure.mjs";
import { checkLinks } from "./lib/docs.mjs";
import { assertDisk, execute } from "./lib/process.mjs";
import { selectChecks } from "./lib/selection.mjs";
import { stagedSnapshot } from "./lib/staged.mjs";

const started = Date.now();
const root = execFileSync("git", ["rev-parse", "--show-toplevel"], { encoding: "utf8" }).trim();
let snapshot;
try {
  assertDisk();
  snapshot = stagedSnapshot(root);
  const { directory, paths, tracked } = snapshot;
  if (paths.length === 0) console.log("No staged files; nothing to check.");
  else {
    const baseline = JSON.parse(execFileSync("git", ["show", "HEAD:package.json"], { cwd: root, encoding: "utf8" }));
    const stagedPackage = JSON.parse(readFileSync(join(directory, "package.json"), "utf8"));
    delete baseline.scripts;
    delete stagedPackage.scripts;
    const selection = selectChecks(paths, {
      merging: snapshot.merging,
      scriptsOnly: JSON.stringify(baseline) === JSON.stringify(stagedPackage),
    });
    console.log(`Staged selection: ${JSON.stringify(selection)}`);
    const run = (command, args, options = {}) => execute(command, args, { cwd: directory, ...options });
    // Real workspace links in an independent install: no builds or typecheck read unstaged source.
    await run("pnpm", ["install", "--offline", "--frozen-lockfile", "--ignore-scripts"], {
      env: { HUSKY: "0" },
      timeout: 120_000,
    });
    if (selection.deferred.length)
      console.log(`Merge-only upstream paths deferred to mandatory L2 check:full: ${selection.deferred.join(", ")}`);
    const live = paths.filter((path) => !selection.deferred.includes(path) && existsSync(join(directory, path)));
    const formatted = live.filter((path) => /\.(?:[cm]?[jt]sx?|css|md|json|ya?ml)$/.test(path));
    if (formatted.length) await run("pnpm", ["exec", "oxfmt", "--check", ...formatted]);
    const linted = live.filter((path) => /\.[cm]?[jt]sx?$/.test(path));
    if (linted.length) await run("pnpm", ["exec", "oxlint", "--deny-warnings", ...linted]);
    for (const [prefix, version] of [
      ["apps/api/", "0.9.7"],
      ["apps/mcp/", "0.16.10"],
      ["deployments/birdplane/", "0.16.10"],
      ["scripts/kitchen/", "0.16.10"],
    ]) {
      const files = live.filter((path) => path.startsWith(prefix) && path.endsWith(".py"));
      if (files.length) {
        // oxlint-disable-next-line no-await-in-loop -- Bound resource use and stop at the first failed check.
        await run("uvx", ["--from", `ruff==${version}`, "ruff", "check", ...files]);
        // oxlint-disable-next-line no-await-in-loop -- Bound resource use and stop at the first failed check.
        await run("uvx", ["--from", `ruff==${version}`, "ruff", "format", "--check", ...files]);
      }
    }
    checkLinks(
      directory,
      live.filter((path) => path.endsWith(".md") && !path.includes("/"))
    );
    if (selection.packages.length) {
      const filters = selection.packages.includes("*") ? [] : selection.packages.map((name) => `--filter=...${name}`);
      for (const name of selection.packages.filter((item) => item !== "*")) {
        if (
          !tracked.some(
            (path) =>
              path.endsWith("/package.json") &&
              existsSync(join(directory, path)) &&
              JSON.parse(readFileSync(join(directory, path), "utf8")).name === name
          )
        )
          throw new Error(`Unknown workspace package ${name}`);
      }
      await run("pnpm", ["turbo", "run", "check:types", ...filters]);
      if (selection.tests.includes("workspace")) await run("pnpm", ["turbo", "run", "test", ...filters]);
    }
    if (selection.tests.includes("filters")) {
      await run("pnpm", ["turbo", "run", "build", "--filter=@plane/shared-state"]);
      await run("node", ["--test", "packages/shared-state/filters.test.mjs"]);
    }
    if (
      selection.tests.includes("branding") ||
      live.some((path) => /(?:metadata\.ts|manifest|favicon|locales\/)/.test(path))
    )
      await run("pnpm", ["test:branding"]);
    if (selection.tests.includes("kitchen"))
      await run("node", [
        "scripts/kitchen/run-tests.mjs",
        ...tracked.filter(
          (path) =>
            /^scripts\/kitchen\/.*\.test\.mjs$/.test(path) &&
            !path.endsWith("/browser.test.mjs") &&
            existsSync(join(directory, path))
        ),
      ]);
    if (selection.tests.includes("mcp")) {
      await run("uv", ["sync", "--frozen", "--python", "3.12"], { cwd: join(directory, "apps/mcp") });
      await run("uv", ["run", "--no-sync", "pytest", "-q"], { cwd: join(directory, "apps/mcp") });
    }
    if (selection.tests.includes("backups"))
      await run("python3", [
        "-m",
        "unittest",
        "discover",
        "-s",
        "deployments/birdplane",
        "-p",
        "test_backup_postgres.py",
      ]);
    const infrastructure = live.filter(
      (path) => selection.infrastructure.includes(path) || /^scripts\/kitchen\/.*\.ya?ml$/.test(path)
    );
    for (const file of infrastructure.filter((path) => !path.startsWith(".github/") && /\.ya?ml$/.test(path))) {
      // oxlint-disable-next-line no-await-in-loop -- Sequential offline config checks.
      await checkCompose(directory, file, run);
    }
    await checkWorkflows(
      directory,
      infrastructure.filter((path) => path.startsWith(".github/")),
      run
    );
    if (infrastructure.some((path) => /Dockerfile/.test(path)))
      console.log(
        "Deployment Dockerfile selects mandatory L2 deployment-dockerfiles BuildKit checks; no image resolution in L1."
      );
    if (selection.apiAtL2)
      console.log(
        "API pytest/migrations/boot require isolated services: mandatory L2 check:full coverage; no host pytest at L1."
      );
  }
  console.log(`check:fast PASS (${((Date.now() - started) / 1000).toFixed(2)}s)`);
} catch (error) {
  console.error(`check:fast FAIL: ${error.message}`);
  process.exitCode = 1;
} finally {
  snapshot?.cleanup();
}
