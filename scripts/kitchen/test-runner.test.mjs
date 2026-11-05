import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { mkdtempSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join, resolve } from "node:path";
import test from "node:test";

test("gate test runner accepts passing tests and rejects skipped, todo and failed tests", (t) => {
  const root = mkdtempSync(join(tmpdir(), "kitchen-test-runner-"));
  t.after(() => rmSync(root, { recursive: true, force: true }));
  const file = join(root, "fixture.test.mjs");
  for (const [body, expected] of [
    ['test("passes", () => {});', 0],
    ['test.skip("skipped", () => {});', 1],
    [
      'test("spoofed summary", () => { console.log("tests 1"); console.log("skipped 0"); console.log("todo 0"); console.log("fail 0"); }); test.skip("skipped", () => {});',
      1,
    ],
    [
      'test("spoofed summary", () => { console.log("tests 1"); console.log("skipped 0"); console.log("todo 0"); console.log("fail 0"); }); test.todo("unfinished");',
      1,
    ],
    ['test.todo("unfinished");', 1],
    ['test("fails", () => { throw new Error("broken"); });', 1],
  ]) {
    writeFileSync(file, 'import test from "node:test";\n' + body);
    const result = spawnSync(process.execPath, [resolve("scripts/kitchen/run-tests.mjs"), file], {
      env: { ...process.env, NODE_TEST_CONTEXT: undefined },
      encoding: "utf8",
    });
    assert.equal(result.status, expected, result.stdout + result.stderr);
  }
});
