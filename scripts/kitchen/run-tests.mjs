// Preserve Node's real exit status and TAP diagnostics; skips/todos are not proof.
import { spawnSync } from "node:child_process";
const files = process.argv.slice(2);
if (!files.length) throw new Error("Expected explicit test files");
const result = spawnSync(process.execPath, ["--test", "--test-reporter=tap", ...files], {
  encoding: "utf8",
  maxBuffer: 16 * 1024 * 1024,
  env: { ...process.env, NODE_TEST_CONTEXT: undefined },
});
process.stdout.write(result.stdout ?? "");
process.stderr.write(result.stderr ?? "");
if (result.error) throw result.error;
const complete =
  /^# tests [1-9][0-9]*$/m.test(result.stdout) &&
  /^# skipped 0$/m.test(result.stdout) &&
  /^# todo 0$/m.test(result.stdout);
if (!complete) console.error("Gate requires at least one test and zero skipped/todo tests");
process.exitCode = result.status === 0 && complete ? 0 : 1;
