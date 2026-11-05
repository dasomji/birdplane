import assert from "node:assert/strict";
import { execFileSync, spawnSync } from "node:child_process";
import { mkdirSync, mkdtempSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import test from "node:test";
import { isolatedEnvironment } from "./lib/environment.mjs";

function fixture(t) {
  const root = mkdtempSync(join(tmpdir(), "kitchen-fast-"));
  t.after(() => rmSync(root, { recursive: true, force: true }));
  const env = isolatedEnvironment();
  const git = (...args) => execFileSync("git", args, { cwd: root, env, encoding: "utf8", stdio: "pipe" });
  git("init", "-q", "-b", "fixture-main");
  git("config", "user.name", "Fixture");
  git("config", "user.email", "fixture@example.invalid");
  writeFileSync(join(root, "package.json"), "{}\n");
  git("add", ".");
  git("-c", "core.hooksPath=/dev/null", "commit", "-qm", "baseline");
  const bin = join(root, "bin");
  mkdirSync(bin);
  // Stub only external tools: this fixture exercises selection and CLI reporting.
  writeFileSync(join(bin, "pnpm"), "#!/bin/sh\nexit 0\n", { mode: 0o755 });
  writeFileSync(join(bin, "uvx"), "#!/bin/sh\necho unexpected-uvx >&2\nexit 1\n", { mode: 0o755 });
  const run = () =>
    spawnSync(process.execPath, [new URL("./check-fast.mjs", import.meta.url).pathname], {
      cwd: root,
      env: { ...env, PATH: `${bin}:${env.PATH}` },
      encoding: "utf8",
    });
  return { root, git, run };
}

test("staged API Python defers Ruff to the exact L2 exemption-aware check", (t) => {
  const { root, git, run } = fixture(t);
  mkdirSync(join(root, "apps/api"), { recursive: true });
  writeFileSync(join(root, "apps/api/upstream.py"), "value=  1\n");
  git("add", "apps/api/upstream.py");
  const result = run();
  assert.equal(result.status, 0, result.stdout + result.stderr);
  assert.match(result.stdout, /API Ruff check-only.*mandatory L2/);
  assert.doesNotMatch(result.stdout + result.stderr, /unexpected-uvx|ruff.*format/);
});

test("a real merge lists unmapped paths without promising full-gate coverage", (t) => {
  const { root, git, run } = fixture(t);
  git("checkout", "-qb", "upstream-update");
  writeFileSync(join(root, "upstream.config"), "upstream update\n");
  git("add", "upstream.config");
  git("-c", "core.hooksPath=/dev/null", "commit", "-qm", "upstream update");
  git("checkout", "-q", "fixture-main");
  git("-c", "core.hooksPath=/dev/null", "merge", "--no-ff", "--no-commit", "upstream-update");
  const result = run();
  assert.equal(result.status, 0, result.stdout + result.stderr);
  assert.match(result.stdout, /Unmapped paths in a merge commit have no fast check: upstream.config/);
  assert.match(result.stdout, /only by whichever check:full phases include them and by review/);
  assert.doesNotMatch(result.stdout, /deferred to mandatory L2 check:full/);
});
