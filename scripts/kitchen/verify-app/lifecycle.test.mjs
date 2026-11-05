import assert from "node:assert/strict";
import test from "node:test";
import { verify } from "./lifecycle.mjs";

test("a journey failure is nonzero and still cleans owned resources", async () => {
  let cleaned = false;
  const result = await verify({
    journeys: [
      [
        "login",
        async () => {
          throw new Error("rejected");
        },
      ],
    ],
    cleanup: async () => {
      cleaned = true;
    },
  });
  assert.equal(result.exitCode, 1);
  assert.equal(result.results[0].result, "fail");
  assert.equal(cleaned, true);
});

test("cleanup failure prevents a green verification", async () => {
  const result = await verify({
    journeys: [["login", async () => "signed in"]],
    cleanup: async () => {
      throw new Error("container still exists");
    },
  });
  assert.equal(result.exitCode, 1);
  assert.equal(result.results.at(-1).result, "fail");
});

test("reports dependent journeys as blocked after a failure", async () => {
  let called = false;
  const result = await verify({
    journeys: [
      [
        "boot",
        async () => {
          throw new Error("failed boot");
        },
      ],
      [
        "login",
        async () => {
          called = true;
        },
      ],
    ],
    cleanup: async () => {},
  });
  assert.equal(called, false);
  assert.equal(result.results.find((r) => r.name === "login")?.result, "blocked");
});
