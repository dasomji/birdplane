import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import test from "node:test";

const entry = new URL("../verify-app.mjs", import.meta.url).pathname;
test("upload requires a ticket before starting verification", () => {
  const result = spawnSync(process.execPath, [entry, "--upload"], { encoding: "utf8" });
  assert.equal(result.status, 1);
  assert.match(result.stderr, /--upload requires --ticket/);
  assert.doesNotMatch(result.stdout, /Tested git SHA|PASS|Evidence:/);
});
test("upload resolves evidence from PATH before starting verification", () => {
  const result = spawnSync(
    process.execPath,
    [entry, "--upload", "--ticket", "BIRD-99", "--pr", "https://github.com/dasomji/birdplane/pull/99"],
    { env: { PATH: "/nonexistent" }, encoding: "utf8" }
  );
  assert.equal(result.status, 1);
  assert.match(result.stderr, /evidence.*PATH/);
  assert.doesNotMatch(result.stdout, /Tested git SHA|PASS|Evidence:/);
});

test("ticket and PR metadata require upload before starting verification", () => {
  for (const args of [
    ["--ticket", "BIRD-34"],
    ["--pr", "https://github.com/dasomji/birdplane/pull/34"],
  ]) {
    const result = spawnSync(process.execPath, [entry, ...args], {
      env: { PATH: "/nonexistent" },
      encoding: "utf8",
    });
    assert.equal(result.status, 1);
    assert.match(result.stderr, /--ticket and --pr require --upload/);
    assert.doesNotMatch(result.stdout, /Tested git SHA|PASS|Evidence:/);
  }
});
