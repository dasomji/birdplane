import assert from "node:assert/strict";
import { execFileSync } from "node:child_process";
import { mkdtempSync, readFileSync, writeFileSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import test from "node:test";
import { isolatedEnvironment } from "./lib/environment.mjs";
import { stagedSnapshot } from "./lib/staged.mjs";

test("snapshot reads staged bytes, retains deleted and both renamed paths, leaves worktree intact", () => {
  const repo = mkdtempSync(join(tmpdir(), "kitchen-index-test-"));
  const git = (...args) => execFileSync("git", args, { cwd: repo, encoding: "utf8", env: isolatedEnvironment() });
  try {
    git("init", "-q");
    git("config", "user.name", "Test");
    git("config", "user.email", "test@example.invalid");
    for (const name of ["partial.md", "old.md", "delete.md"]) writeFileSync(join(repo, name), "original\n");
    git("add", ".");
    git("-c", "core.hooksPath=/dev/null", "commit", "-qm", "fixture baseline");
    git("mv", "old.md", "new.md");
    git("rm", "delete.md");
    writeFileSync(join(repo, "partial.md"), "staged\n");
    git("add", "partial.md");
    writeFileSync(join(repo, "partial.md"), "unstaged\n");
    const before = git("diff");
    const snapshot = stagedSnapshot(repo);
    try {
      assert.ok(snapshot.directory.startsWith(join(repo, ".kitchen/tmp") + "/"));
      assert.equal(snapshot.merging, false);
      writeFileSync(join(repo, ".git/MERGE_HEAD"), git("rev-parse", "HEAD"));
      const mergingSnapshot = stagedSnapshot(repo);
      try {
        assert.equal(mergingSnapshot.merging, true);
      } finally {
        mergingSnapshot.cleanup();
      }
      assert.deepEqual(snapshot.paths.toSorted(), ["delete.md", "new.md", "old.md", "partial.md"]);
      assert.equal(readFileSync(join(snapshot.directory, "partial.md"), "utf8"), "staged\n");
      assert.equal(git("diff"), before);
      assert.equal(readFileSync(join(repo, "partial.md"), "utf8"), "unstaged\n");
    } finally {
      snapshot.cleanup();
    }
  } finally {
    rmSync(repo, { recursive: true, force: true });
  }
});
