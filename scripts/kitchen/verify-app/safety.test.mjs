import assert from "node:assert/strict";
import test from "node:test";
import { spawnSync } from "node:child_process";
import { assertDisposable } from "./safety.mjs";

test("rejects production destinations before any connection", () => {
  for (const patch of [
    { project: "birdplane" },
    { databaseUrl: "postgresql://verify:password@production:5432/verify" },
    { databaseUrl: "postgresql://verify:password@verify-db:5432/plane" },
    { redisUrl: "redis://production:6379/0" },
  ]) {
    assert.throws(
      () =>
        assertDisposable({
          project: "kitchen-verify-a123456789ab-b123456789ab",
          image: "kitchen-verify-a123456789ab-b123456789ab:test",
          databaseUrl: "postgresql://verify:password@verify-db:5432/verify",
          redisUrl: "redis://verify-redis:6379/0",
          ...patch,
        }),
      /disposable/
    );
  }
});

test("cleanup refuses an image outside its disposable run", () => {
  assert.throws(
    () =>
      assertDisposable({
        project: "kitchen-verify-a123456789ab-b123456789ab",
        image: "birdplane-api:production",
        databaseUrl: "postgresql://verify:password@verify-db:5432/verify",
        redisUrl: "redis://verify-redis:6379/0",
      }),
    /disposable/
  );
});

test("Django settings reject an unknown DB host before importing Django", () => {
  const result = spawnSync("python3", [new URL("verify_settings.py", import.meta.url).pathname], {
    env: {
      VERIFY_PROJECT: "kitchen-verify-a123456789ab-b123456789ab",
      DATABASE_URL: "postgresql://verify:password@production.invalid:5432/verify",
      REDIS_URL: "redis://verify-redis:6379/0",
    },
    encoding: "utf8",
  });
  assert.equal(result.status, 1);
  assert.match(result.stderr, /Refusing non-disposable/);
  assert.doesNotMatch(result.stderr, /ModuleNotFoundError/);
});
