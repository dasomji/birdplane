import assert from "node:assert/strict";
import { execFileSync } from "node:child_process";
import { mkdtempSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join, resolve } from "node:path";
import test from "node:test";
import { isolatedEnvironment } from "./lib/environment.mjs";
import { execute } from "./lib/process.mjs";

test("checks spawned from a hook cannot change the invoking repository through Git overrides", async () => {
  const repository = mkdtempSync(join(tmpdir(), "kitchen-hook-environment-"));
  const clean = isolatedEnvironment();
  const git = (...args) => execFileSync("git", args, { cwd: repository, encoding: "utf8", env: clean });
  const overrides = {
    GIT_DIR: join(repository, ".git"),
    GIT_COMMON_DIR: join(repository, ".git"),
    GIT_WORK_TREE: repository,
    GIT_INDEX_FILE: join(repository, ".git/index"),
  };
  const previous = Object.fromEntries(Object.keys(overrides).map((key) => [key, process.env[key]]));
  try {
    git("init", "-q");
    git("config", "user.name", "Fixture");
    git("config", "user.email", "fixture@example.invalid");
    writeFileSync(join(repository, "sentinel.txt"), "original\n");
    git("add", ".");
    git("-c", "core.hooksPath=/dev/null", "commit", "-qm", "disposable invoking repository");
    const head = git("rev-parse", "HEAD");
    const index = readFileSync(join(repository, ".git/index"));
    Object.assign(process.env, overrides);
    await execute("node", ["--test", resolve("scripts/kitchen/staged.test.mjs")], {
      // Node propagates this marker to test children; clear it to run a real nested CLI.
      env: { NODE_TEST_CONTEXT: undefined },
    });
    assert.equal(git("rev-parse", "HEAD"), head);
    assert.deepEqual(readFileSync(join(repository, ".git/index")), index);
    assert.equal(readFileSync(join(repository, "sentinel.txt"), "utf8"), "original\n");
  } finally {
    for (const [key, value] of Object.entries(previous)) {
      if (value === undefined) delete process.env[key];
      else process.env[key] = value;
    }
    rmSync(repository, { recursive: true, force: true });
  }
});
