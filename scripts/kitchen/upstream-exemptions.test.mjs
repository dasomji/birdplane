import assert from "node:assert/strict";
import { execFileSync } from "node:child_process";
import { mkdtempSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import test from "node:test";
import { docsFormatPaths, verifyRuffExemptions } from "./lib/upstream-exemptions.mjs";

function fixture(t) {
  const root = mkdtempSync(join(tmpdir(), "kitchen-upstream-"));
  t.after(() => rmSync(root, { recursive: true, force: true }));
  writeFileSync(join(root, "upstream.py"), "from example import User\n");
  const entry = {
    path: "upstream.py",
    check: "api-ruff",
    rule: "F401",
    symbol: "example.User",
    line: 1,
    column: 21,
    endLine: 1,
    endColumn: 25,
    upstreamRef: "v1.4.3",
    upstreamBlob: execFileSync("git", ["hash-object", join(root, "upstream.py")], { encoding: "utf8" }).trim(),
    justification: "Preserve unchanged upstream source.",
  };
  const diagnostic = {
    filename: join(root, "upstream.py"),
    code: "F401",
    message: "`example.User` imported but unused",
    location: { row: 1, column: 21 },
    end_location: { row: 1, column: 25 },
  };
  return { root, entry, diagnostic };
}

test("only registered Ruff violations are accepted and reported individually", (t) => {
  const { root, entry, diagnostic } = fixture(t);
  assert.deepEqual(verifyRuffExemptions(root, [entry], [diagnostic]), [entry]);
  for (const extra of [
    { ...diagnostic, filename: join(root, "fork.py") },
    { ...diagnostic, code: "F821" },
    { ...diagnostic, message: "`example.Other` imported but unused" },
    { ...diagnostic, location: { row: 2, column: 21 } },
    { ...diagnostic, location: { row: 1, column: 22 } },
    { ...diagnostic, end_location: { row: 1, column: 26 } },
    diagnostic,
  ]) {
    assert.throws(() => verifyRuffExemptions(root, [entry], [diagnostic, extra]), /Unexempted Ruff diagnostic/);
  }
});

test("a missing registered Ruff violation fails as stale even when Ruff is clean", (t) => {
  const { root, entry } = fixture(t);
  assert.throws(() => verifyRuffExemptions(root, [entry], []), /Stale.*upstream.py/);
  assert.deepEqual(verifyRuffExemptions(root, [], []), []);
});

test("edited or missing upstream files cannot retain exemptions", (t) => {
  const { root, entry, diagnostic } = fixture(t);
  writeFileSync(join(root, entry.path), "# Fork-owned now\nfrom example import User\n");
  assert.throws(() => verifyRuffExemptions(root, [entry], [diagnostic]), /blob changed.*upstream.py/);
  rmSync(join(root, entry.path));
  assert.throws(() => verifyRuffExemptions(root, [entry], [diagnostic]), /upstream.py/);
});

test("docs formatting excludes only registered unchanged files that still fail formatting", (t) => {
  const { root, entry } = fixture(t);
  const docsEntry = { ...entry, check: "docs-format", rule: "oxfmt" };
  const paths = [entry.path, "fork.md"];
  assert.deepEqual(docsFormatPaths(root, [docsEntry], paths, [entry.path]), ["fork.md"]);
  assert.throws(() => docsFormatPaths(root, [docsEntry], paths, []), /Stale.*upstream.py/);
  assert.throws(() => docsFormatPaths(root, [docsEntry], ["fork.md"], [entry.path]), /Stale.*upstream.py/);
  writeFileSync(join(root, entry.path), "fork owned\n");
  assert.throws(() => docsFormatPaths(root, [docsEntry], paths, [entry.path]), /blob changed.*upstream.py/);
});

test("invalid or duplicate register entries cannot silently bypass checking", (t) => {
  const { root, entry, diagnostic } = fixture(t);
  for (const invalid of [
    { ...entry, check: "typo" },
    { ...entry, upstreamRef: "main" },
    { ...entry, upstreamBlob: "" },
    { ...entry, justification: "" },
    { ...entry, path: "../upstream.py" },
    { ...entry, line: undefined },
    { ...entry, rule: "F821" },
  ])
    assert.throws(() => verifyRuffExemptions(root, [invalid], []), /Invalid upstream exemption/);
  const docs = { ...entry, check: "docs-format", rule: "oxfmt" };
  assert.throws(() => docsFormatPaths(root, [docs, docs], [entry.path], [entry.path]), /Duplicate upstream exemption/);
  assert.throws(() => verifyRuffExemptions(root, [entry, entry], [diagnostic]), /Duplicate upstream exemption/);
});
