import assert from "node:assert/strict";
import { execFileSync } from "node:child_process";
import { mkdtempSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import test from "node:test";
import { checkCompose, checkWorkflows } from "./lib/infrastructure.mjs";

test("Compose config validates synthetic input without reading env files or inheriting shell values", async (t) => {
  const root = mkdtempSync(join(tmpdir(), "kitchen-compose-config-"));
  const previousImage = process.env.IMAGE;
  process.env.IMAGE = "must-not-inherit";
  t.after(() => {
    if (previousImage === undefined) delete process.env.IMAGE;
    else process.env.IMAGE = previousImage;
  });
  t.after(() => rmSync(root, { recursive: true, force: true }));
  writeFileSync(join(root, ".env"), "not valid env content\u0000");
  writeFileSync(
    join(root, "compose.yml"),
    'services:\n  app:\n    image: "${IMAGE:?required}"\n    env_file: ./missing.env\n    ports: ["${LISTEN_HTTP_PORT}:80"]\n'
  );
  const run = async (bin, args, options) => {
    assert.equal(options.inheritEnv, false);
    assert.notEqual(options.env.IMAGE, process.env.IMAGE);
    execFileSync(bin, args, { cwd: root, env: options.env, stdio: "pipe" });
  };
  await checkCompose(root, "compose.yml", run);
  writeFileSync(
    join(root, "compose.yml"),
    "x-base: &base { image: busybox, env_file: ./missing.env }\nservices: { app: { <<: *base } }\n"
  );
  await checkCompose(root, "compose.yml", run);
  writeFileSync(join(root, "compose.yml"), "services: { app: { image: busybox, env_file: 42 } }");
  await assert.rejects(checkCompose(root, "compose.yml", run));
  writeFileSync(join(root, "compose.yml"), "services: { app: { nonsense: true } }");
  await assert.rejects(checkCompose(root, "compose.yml", run));
});

test("workflow YAML syntax errors fail before optional actionlint", async (t) => {
  const root = mkdtempSync(join(tmpdir(), "kitchen-workflow-"));
  t.after(() => rmSync(root, { recursive: true, force: true }));
  writeFileSync(join(root, "workflow.yml"), "jobs: [broken\n");
  await assert.rejects(
    checkWorkflows(root, ["workflow.yml"], async () => {}),
    /YAML|parse|flow/
  );
});

test("external Compose includes and extends require their own isolated contract", async (t) => {
  const root = mkdtempSync(join(tmpdir(), "kitchen-compose-external-"));
  t.after(() => rmSync(root, { recursive: true, force: true }));
  for (const source of [
    "include: [https://example.invalid/compose.yml]\nservices: {}\n",
    "services: { app: { extends: { file: ./other.yml, service: app } } }\n",
  ]) {
    writeFileSync(join(root, "compose.yml"), source);
    // oxlint-disable-next-line no-await-in-loop -- Each case rewrites the same fixture file.
    await assert.rejects(
      checkCompose(root, "compose.yml", async () => {
        throw new Error("external configuration reached Compose");
      }),
      /External Compose/
    );
  }
});
